#!/bin/bash
# publicar.sh — sube build/web a la rama gh-pages: https://zarkominic.github.io/pesadilla/
# Antes: tools/arte/construir.sh (si cambió el arte) y tools/web/empaquetar.sh.
set -e
cd "$(dirname "$0")/../.."
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
cd build/web
cp index.html default.cfg doom1.wad.gz pesadilla.js pesadilla.wad pesadilla.wasm \
   LICENCIA-MOTOR-GPL2.txt LICENCIA-FREEDOOM.txt CREDITOS-FREEDOOM.txt "$T"/
cd "$T"
touch .nojekyll
git init -q -b gh-pages
git config user.name zarkominic
git config user.email 811108+zarkominic@users.noreply.github.com
git add -A
git commit -q -m "web: versión publicada de PESADILLA"
git push -q -f https://github.com/zarkominic/pesadilla.git gh-pages
echo "subido: https://zarkominic.github.io/pesadilla/ (tarda 1-2 min en actualizarse)"
