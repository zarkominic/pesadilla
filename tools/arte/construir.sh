#!/bin/bash
# construir.sh — regenera todo el arte propio (dibujado por código) y el PWAD que carga el juego.
#   tools/arte/construir.sh            → arte/sprites/*.png, build/pesadilla.wad y motor/src/pesadilla.wad
# Necesita el venv con numpy y Pillow (ver tools/wad/README.md).
set -e
cd "$(dirname "$0")/../.."
PY=~/.venvs/pesadilla/bin/python
$PY tools/arte/penitente.py --salida arte/sprites
$PY tools/arte/pistolon.py --salida arte/sprites
$PY tools/wad/construir_pwad.py --iwad wads/freedoom-0.13.0/freedoom1.wad --arte arte/sprites --salida build/pesadilla.wad
cp build/pesadilla.wad motor/src/pesadilla.wad
echo "listo: motor/src/pesadilla.wad"
