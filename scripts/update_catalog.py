#!/usr/bin/env python3
"""Ajoute ou remplace une entrée dans catalog.json (lu par l'appli pour proposer les téléchargements)."""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone

REPO = "behafid89-sketch/NaviCore-Maps"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def file_entry(kind, path, tag, extra=None):
    entry = {
        "kind": kind,
        "url": f"https://github.com/{REPO}/releases/download/{tag}/{os.path.basename(path)}",
        "size": os.path.getsize(path),
        "sha256": sha256(path),
    }
    if extra:
        entry.update(extra)
    return entry


def load(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"schema": 1, "regions": []}


def save(catalog, path):
    catalog["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", default="catalog.json")
    p.add_argument("--tag", required=True)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("region")
    r.add_argument("--id", required=True)
    r.add_argument("--name", required=True)
    r.add_argument("--country", required=True)
    r.add_argument("--country-code", required=True)
    r.add_argument("--bbox", required=True, help="minLon,minLat,maxLon,maxLat")
    r.add_argument("--map", required=True)
    r.add_argument("--routing", required=True)
    r.add_argument("--search", required=True)
    r.add_argument("--search-uncompressed-size", type=int, required=True)
    r.add_argument("--valhalla-version", required=True)

    s = sub.add_parser("stylepack")
    s.add_argument("--file", required=True)

    a = p.parse_args()
    catalog = load(a.catalog)

    if a.cmd == "region":
        entry = {
            "id": a.id,
            "name": a.name,
            "country": a.country,
            "countryCode": a.country_code,
            "bbox": [float(v) for v in a.bbox.split(",")],
            "version": a.tag,
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "valhalla": a.valhalla_version,
            "files": [
                file_entry("map", a.map, a.tag),
                file_entry("routing", a.routing, a.tag),
                file_entry("search", a.search, a.tag, {"gzip": True, "uncompressedSize": a.search_uncompressed_size}),
            ],
        }
        catalog["regions"] = [x for x in catalog.get("regions", []) if x["id"] != a.id] + [entry]
        catalog["regions"].sort(key=lambda x: (x["country"], x["name"]))
    else:
        catalog["stylepack"] = dict(file_entry("stylepack", a.file, a.tag), version=a.tag)

    save(catalog, a.catalog)


if __name__ == "__main__":
    main()
