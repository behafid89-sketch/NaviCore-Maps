#!/usr/bin/env python3
"""
Pack de style hors connexion : style « Liberty » d'OpenFreeMap (licence BSD), ses icônes (sprites)
et ses polices (glyphes). L'appli réécrit les adresses pour lire ces fichiers sur le téléphone.
"""
import json
import os
import sys
import urllib.error
import urllib.request
import zipfile

STYLE_URL = "https://tiles.openfreemap.org/styles/liberty"
UA = {"User-Agent": "NaviCore-Maps-builder/1.0 (github.com/behafid89-sketch/NaviCore-Maps)"}


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def collect_fonts(value, out):
    """text-font peut être une liste simple ou une expression : on récupère toutes les listes de noms."""
    if isinstance(value, list):
        if value and all(isinstance(v, str) for v in value) and not value[0] in ("literal", "step", "match", "case", "get", "coalesce"):
            out.add(",".join(value))
        else:
            for v in value:
                collect_fonts(v, out)


def main(out_zip):
    style = json.loads(fetch(STYLE_URL))
    sprite = style.get("sprite")
    glyphs = style["glyphs"]

    fontstacks = set()
    for layer in style.get("layers", []):
        tf = layer.get("layout", {}).get("text-font")
        if tf is not None:
            collect_fonts(tf, fontstacks)
    # MapLibre demande chaque police séparément quand une pile en contient plusieurs.
    fonts = sorted({f.strip() for stack in fontstacks for f in stack.split(",")})
    print("Polices :", fonts)

    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("style.json", json.dumps(style, ensure_ascii=False))

        sprite_urls = []
        if isinstance(sprite, str):
            sprite_urls = [("sprite", sprite)]
        elif isinstance(sprite, list):
            sprite_urls = [(s["id"], s["url"]) for s in sprite]
        for sid, base in sprite_urls:
            for suffix in (".json", ".png", "@2x.json", "@2x.png"):
                try:
                    z.writestr(f"sprites/{sid}{suffix}", fetch(base + suffix))
                except urllib.error.HTTPError as e:
                    print(f"Sprite absent {base}{suffix} ({e.code})")

        count = 0
        for font in fonts:
            for start in range(0, 65536, 256):
                rng = f"{start}-{start + 255}"
                url = glyphs.replace("{fontstack}", urllib.request.quote(font)).replace("{range}", rng)
                try:
                    data = fetch(url)
                except urllib.error.HTTPError:
                    continue
                if not data:
                    continue
                z.writestr(f"fonts/{font}/{rng}.pbf", data)
                count += 1
        print(f"{count} fichiers de glyphes")

        z.writestr(
            "stylepack.json",
            json.dumps({"schema": 1, "source": STYLE_URL, "sprites": [s for s, _ in sprite_urls], "fonts": fonts}),
        )
    print(f"Pack écrit : {out_zip} ({os.path.getsize(out_zip) / 1e6:.1f} Mo)")


if __name__ == "__main__":
    main(sys.argv[1])
