#!/usr/bin/env python3
"""
Construit l'index de recherche hors connexion d'une région (SQLite + FTS4).

- Adresses françaises : Base Adresse Nationale (fichiers CSV par département), regroupées par rue.
- Lieux (villes, villages, commerces, stations-service…) : OpenStreetMap (fichier .osm.pbf).

Coordonnées stockées en micro-degrés (entiers) pour réduire la taille.
Tokeniseur FTS4 « unicode61 remove_diacritics » : disponible sur tous les Android depuis la version 5.
"""
import argparse
import csv
import gzip
import io
import os
import sqlite3
import sys

import osmium

E6 = 1_000_000

CATEGORIES = {
    ("amenity", "fuel"): ("Station-service", 40),
    ("amenity", "charging_station"): ("Borne de recharge", 35),
    ("amenity", "restaurant"): ("Restaurant", 20),
    ("amenity", "fast_food"): ("Restauration rapide", 15),
    ("amenity", "cafe"): ("Café", 15),
    ("amenity", "bar"): ("Bar", 10),
    ("amenity", "parking"): ("Parking", 25),
    ("amenity", "pharmacy"): ("Pharmacie", 35),
    ("amenity", "hospital"): ("Hôpital", 50),
    ("amenity", "clinic"): ("Clinique", 30),
    ("amenity", "police"): ("Police", 30),
    ("amenity", "townhall"): ("Mairie", 35),
    ("amenity", "school"): ("École", 15),
    ("amenity", "university"): ("Université", 30),
    ("amenity", "post_office"): ("Poste", 20),
    ("amenity", "bank"): ("Banque", 10),
    ("amenity", "car_wash"): ("Station de lavage", 20),
    ("tourism", "hotel"): ("Hôtel", 25),
    ("tourism", "motel"): ("Motel", 20),
    ("tourism", "museum"): ("Musée", 30),
    ("tourism", "attraction"): ("Site touristique", 30),
    ("tourism", "camp_site"): ("Camping", 20),
    ("shop", "supermarket"): ("Supermarché", 30),
    ("shop", "butcher"): ("Boucherie", 15),
    ("shop", "bakery"): ("Boulangerie", 15),
    ("shop", "mall"): ("Centre commercial", 35),
    ("shop", "car_repair"): ("Garage", 15),
    ("highway", "rest_area"): ("Aire de repos", 40),
    ("highway", "services"): ("Aire de services", 45),
    ("railway", "station"): ("Gare", 45),
    ("aeroway", "aerodrome"): ("Aéroport", 60),
    ("place", "city"): ("Ville", 100),
    ("place", "town"): ("Ville", 80),
    ("place", "village"): ("Village", 60),
    ("place", "suburb"): ("Quartier", 50),
    ("place", "hamlet"): ("Hameau", 30),
    ("place", "locality"): ("Lieu-dit", 20),
}
KEYS = ("place", "amenity", "shop", "tourism", "highway", "railway", "aeroway")


def category_of(tags):
    for key in KEYS:
        value = tags.get(key)
        if value and (key, value) in CATEGORIES:
            return CATEGORIES[(key, value)]
    return None


class PoiHandler(osmium.SimpleHandler):
    def __init__(self, out):
        super().__init__()
        self.out = out

    def _add(self, tags, lat, lon):
        name = tags.get("name:fr") or tags.get("name")
        if not name:
            return
        cat = category_of(tags)
        if cat is None:
            return
        city = tags.get("addr:city") or ""
        self.out.append((name, cat[0], city, int(round(lat * E6)), int(round(lon * E6)), cat[1]))

    def node(self, n):
        if n.location.valid() and n.tags:
            self._add(n.tags, n.location.lat, n.location.lon)

    def way(self, w):
        if not w.tags or ("name" not in w.tags):
            return
        if category_of(w.tags) is None:
            return
        lats, lons = [], []
        for node in w.nodes:
            if node.location.valid():
                lats.append(node.location.lat)
                lons.append(node.location.lon)
        if lats:
            self._add(w.tags, sum(lats) / len(lats), sum(lons) / len(lons))


def open_ban(path):
    raw = open(path, "rb")
    data = gzip.open(raw) if path.endswith(".gz") else raw
    return io.TextIOWrapper(data, encoding="utf-8", newline="")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pbf", required=True)
    parser.add_argument("--ban", nargs="*", default=[])
    parser.add_argument("--out", required=True)
    parser.add_argument("--region", required=True)
    args = parser.parse_args()

    if os.path.exists(args.out):
        os.remove(args.out)
    db = sqlite3.connect(args.out)
    db.executescript(
        """
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE streets(id INTEGER PRIMARY KEY, name TEXT NOT NULL, postcode TEXT, city TEXT, lat INTEGER, lon INTEGER);
        CREATE TABLE numbers(street_id INTEGER NOT NULL, number TEXT NOT NULL, lat INTEGER NOT NULL, lon INTEGER NOT NULL);
        CREATE TABLE pois(id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT, city TEXT, lat INTEGER, lon INTEGER, rank INTEGER);
        """
    )

    # ---- Adresses (BAN) ----
    street_ids = {}
    numbers = []
    street_rows = []
    total_addresses = 0
    for path in args.ban:
        with open_ban(path) as f:
            reader = csv.DictReader(f, delimiter=";")
            missing = {"numero", "rep", "nom_voie", "code_postal", "nom_commune", "lon", "lat"} - set(reader.fieldnames or [])
            if missing:
                sys.exit(f"Colonnes BAN manquantes dans {path} : {missing}")
            for row in reader:
                try:
                    lat = int(round(float(row["lat"]) * E6))
                    lon = int(round(float(row["lon"]) * E6))
                except (TypeError, ValueError):
                    continue
                key = (row["nom_voie"], row["code_postal"], row["nom_commune"])
                sid = street_ids.get(key)
                if sid is None:
                    sid = len(street_ids) + 1
                    street_ids[key] = sid
                    street_rows.append((sid, key[0], key[1], key[2], lat, lon))
                number = (row["numero"] or "").strip()
                rep = (row["rep"] or "").strip()
                if number and number != "99999":  # 99999 = lieu-dit sans numéro dans la BAN
                    numbers.append((sid, (number + (" " + rep if rep else "")).strip(), lat, lon))
                total_addresses += 1
        print(f"BAN {os.path.basename(path)} lu : {total_addresses} adresses au total", flush=True)

    db.executemany("INSERT INTO streets VALUES (?,?,?,?,?,?)", street_rows)
    db.executemany("INSERT INTO numbers VALUES (?,?,?,?)", numbers)
    print(f"{len(street_rows)} rues, {len(numbers)} numéros", flush=True)
    del numbers, street_rows

    # ---- Lieux OpenStreetMap ----
    pois = []
    PoiHandler(pois).apply_file(args.pbf, locations=True, idx="flex_mem")
    db.executemany("INSERT INTO pois(name, category, city, lat, lon, rank) VALUES (?,?,?,?,?,?)", pois)
    print(f"{len(pois)} lieux OSM", flush=True)

    # ---- Index ----
    db.executescript(
        """
        CREATE INDEX numbers_street ON numbers(street_id);
        CREATE INDEX numbers_pos ON numbers(lat, lon);
        CREATE INDEX streets_pos ON streets(lat, lon);
        CREATE VIRTUAL TABLE streets_fts USING fts4(content="streets", name, city, tokenize=unicode61 "remove_diacritics=1");
        CREATE VIRTUAL TABLE pois_fts USING fts4(content="pois", name, city, tokenize=unicode61 "remove_diacritics=1");
        INSERT INTO streets_fts(docid, name, city) SELECT id, name, city FROM streets;
        INSERT INTO pois_fts(docid, name, city) SELECT id, name, city FROM pois;
        INSERT INTO streets_fts(streets_fts) VALUES('optimize');
        INSERT INTO pois_fts(pois_fts) VALUES('optimize');
        """
    )
    db.executemany(
        "INSERT INTO meta VALUES (?, ?)",
        [("schema", "1"), ("region", args.region), ("addresses", str(total_addresses)), ("pois", str(len(pois)))],
    )
    db.commit()
    db.execute("VACUUM")
    db.close()
    print(f"Index écrit : {args.out} ({os.path.getsize(args.out) / 1e6:.1f} Mo)")


if __name__ == "__main__":
    main()
