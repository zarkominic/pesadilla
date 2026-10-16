#!/bin/bash
# construir.sh — regenera todo el arte propio (dibujado por código) y el PWAD que carga el juego.
#   tools/arte/construir.sh            → arte/sprites/*.png, build/pesadilla.wad y motor/src/pesadilla.wad
# Ejecuta cada tools/arte/*.py que sea un programa (tiene "__main__" y --salida); los módulos
# comunes (sdf.py…) se saltan. Necesita el venv con numpy y Pillow (ver tools/wad/README.md).
set -e
cd "$(dirname "$0")/../.."
PY=~/.venvs/pesadilla/bin/python
for f in tools/arte/*.py; do
  grep -q "^if __name__ == '__main__'" "$f" && grep -q -- "--salida" "$f" || continue
  echo "== $f"
  $PY "$f" --salida arte/sprites > /dev/null
done
$PY tools/wad/construir_pwad.py --iwad wads/freedoom-0.13.0/freedoom1.wad --arte arte/sprites --salida build/pesadilla.wad | tail -1
cp build/pesadilla.wad motor/src/pesadilla.wad
echo "listo: motor/src/pesadilla.wad"
