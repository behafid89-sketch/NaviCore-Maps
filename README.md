# NaviCore Maps

Données de cartes hors connexion pour l'application **NaviCore GPS**.

Chaque région publiée (onglet **Releases**) contient :

| Fichier | Contenu | Outil |
|---|---|---|
| `<région>.pmtiles` | Carte à afficher (tuiles vectorielles, schéma OpenMapTiles) | [Planetiler](https://github.com/onthegomap/planetiler) |
| `<région>-routing.tar` | Réseau routier pour le calcul d'itinéraire sur le téléphone | [Valhalla](https://github.com/valhalla/valhalla) |
| `<région>-search.db.gz` | Index de recherche d'adresses et de lieux (SQLite) | `scripts/build_search.py` |
| `stylepack.zip` | Style de carte, icônes et polices pour l'affichage sans Internet | `scripts/build_stylepack.py` |

`catalog.json` liste les régions disponibles ; l'appli le lit pour proposer les téléchargements.

## Fabriquer une région

Onglet **Actions** → **Fabriquer une région** → **Run workflow**, avec l'identifiant défini dans `regions.json`.

## Licences et attribution

- Données cartographiques et routières © [contributeurs OpenStreetMap](https://www.openstreetmap.org/copyright), licence **ODbL**. Les fichiers de ce dépôt sont des bases de données dérivées, diffusées sous la même licence.
- Adresses françaises : **Base Adresse Nationale**, Licence Ouverte Etalab 2.0.
- Style « Liberty » : © OpenFreeMap / MapTiler, licence BSD.
- Polices Noto : SIL Open Font License.
