#!/bin/bash
# construir.sh — regenera todo el arte propio (dibujado por código) y el PWAD que carga el juego.
#   tools/arte/construir.sh            → arte/sprites/*.png, build/pesadilla.wad y motor/src/pesadilla.wad
# Ejecuta EN PARALELO cada tools/arte/*.py que sea un programa (tiene "__main__" y --salida); los
# módulos comunes (sdf.py, arma1p.py) se saltan. Cada pieza escribe solo sus PNG y su
# offsets_<pieza>.json, así que no se pisan. Necesita el venv con numpy y Pillow (tools/wad/README.md).
set -e
cd "$(dirname "$0")/../.."
PY=~/.venvs/pesadilla/bin/python
mkdir -p build/logs
programas=()
for f in tools/arte/*.py; do
  grep -q "^if __name__ == '__main__'" "$f" && grep -q -- "--salida" "$f" && programas+=("$f")
done
echo "${#programas[@]} piezas: ${programas[*]##*/}"
printf '%s\n' "${programas[@]}" | xargs -P "$(sysctl -n hw.ncpu 2>/dev/null || nproc)" -I{} \
  sh -c 'n=$(basename {} .py); if '"$PY"' {} --salida arte/sprites > build/logs/$n.log 2>&1; then echo "  ok  $n"; else echo "  FALLO $n (build/logs/$n.log)"; exit 255; fi'
$PY tools/wad/construir_pwad.py --iwad wads/freedoom-0.13.0/freedoom1.wad --arte arte/sprites --salida build/pesadilla.wad | tail -1
cp build/pesadilla.wad motor/src/pesadilla.wad
echo "listo: motor/src/pesadilla.wad"
