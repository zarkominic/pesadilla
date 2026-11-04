#!/bin/bash
# empaquetar.sh — versión web para publicar → build/web/
#   motor compilado SIN datos de depuración (wasm ~2 MB), Freedoom comprimido (28 → ~10 MB),
#   pesadilla.wad (arte propio), index.html con COMPRIMIDOS activado, y licencias/créditos.
# Compila en una copia temporal del motor (fuera de iCloud) para no tocar la build de desarrollo.
# Antes: tools/arte/construir.sh (genera build/pesadilla.wad).
set -e
cd "$(dirname "$0")/../.."
[ -f build/pesadilla.wad ] || { echo "falta build/pesadilla.wad: ejecuta tools/arte/construir.sh"; exit 1; }
TMP="${TMPDIR:-/tmp}/pesadilla-web"
rm -rf "$TMP"; mkdir -p "$TMP"
rsync -a --exclude '*.o' --exclude '*.a' --exclude '.deps' --exclude 'src/*.wad' \
      --exclude 'src/pesadilla.*' --exclude '* [0-9]*' motor/ "$TMP/motor/"
echo "compilando el motor (release)…"
if ! (cd "$TMP/motor" && ./scripts/clean.sh > /dev/null 2>&1; PESADILLA_RELEASE=1 ./scripts/build.sh > "$TMP/build.log" 2>&1); then
  tail -30 "$TMP/build.log"; exit 1
fi
OUT=build/web
rm -rf "$OUT"; mkdir -p "$OUT"
cp "$TMP/motor/src/pesadilla.js" "$TMP/motor/src/pesadilla.wasm" "$OUT/"
cp motor/src/default.cfg "$OUT/"
gzip -9 -n -c wads/freedoom-0.13.0/freedoom1.wad > "$OUT/doom1.wad.gz"
gzip -9 -n -c build/pesadilla.wad > "$OUT/pesadilla.wad.gz"
sed 's/var EMPAQUETADOS = {};/var EMPAQUETADOS = {"doom1.wad": "doom1.wad.gz", "pesadilla.wad": "pesadilla.wad.gz"};/' motor/src/index.html > "$OUT/index.html"
grep -q '"pesadilla.wad": "pesadilla.wad.gz"' "$OUT/index.html" || { echo "no se pudo activar EMPAQUETADOS en index.html"; exit 1; }
# Para el Artifact (solo sirve tipos web): WADs comprimidos y en base64 dentro de .txt.
mkdir -p "$OUT/artefacto"
base64 -i "$OUT/doom1.wad.gz" -o "$OUT/artefacto/doom1.wad.gz.b64.txt"
base64 -i "$OUT/pesadilla.wad.gz" -o "$OUT/artefacto/pesadilla.wad.gz.b64.txt"
# artefacto.html: la misma página para publicarla como Artifact de claude.ai (la plataforma pone su
# propio esqueleto <!doctype><html><head><body>, el charset y el viewport).
python3 - "$OUT/index.html" "$OUT/artefacto.html" <<'PY'
import sys, re
s = open(sys.argv[1]).read()
s, n = re.subn(r'var EMPAQUETADOS = \{[^}]*\};',
               'var EMPAQUETADOS = {"doom1.wad": "doom1.wad.gz.b64.txt", "pesadilla.wad": "pesadilla.wad.gz.b64.txt"};', s)
assert n == 1
for pat in (r'<!DOCTYPE html>\s*', r'<html[^>]*>\s*', r'</html>\s*', r'<head>\s*', r'</head>\s*', r'<body>\s*',
            r'</body>\s*', r'<meta charset="utf-8" />\s*', r'<meta name="viewport"[^>]*/>\s*', r'<link rel="icon"[^>]*/>\s*'):
    s, n = re.subn(pat, '', s, flags=re.I)
    assert n == 1, pat
open(sys.argv[2], 'w').write(s.lstrip())
PY
# Licencias: el motor es GPL-2.0 (hay que ofrecer su código) y Freedoom es BSD (atribución).
cp motor/COPYING.md "$OUT/LICENCIA-MOTOR-GPL2.txt"
cp wads/freedoom-0.13.0/COPYING.txt "$OUT/LICENCIA-FREEDOOM.txt"
cp wads/freedoom-0.13.0/CREDITS.txt "$OUT/CREDITOS-FREEDOOM.txt"
ls -la "$OUT"
du -sh "$OUT"
