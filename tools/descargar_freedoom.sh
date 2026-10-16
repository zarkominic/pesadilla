#!/bin/bash
# descargar_freedoom.sh — baja Freedoom 0.13.0 (BSD) a wads/ y comprueba su SHA-256.
set -e
cd "$(dirname "$0")/.."
mkdir -p wads && cd wads
V=0.13.0
curl -sL -o freedoom-$V.zip https://github.com/freedoom/freedoom/releases/download/v$V/freedoom-$V.zip
echo "3f9b264f3e3ce503b4fb7f6bdcb1f419d93c7b546f4df3e874dd878db9688f59  freedoom-$V.zip" | shasum -a 256 -c -
unzip -oq freedoom-$V.zip && rm -f freedoom-$V.zip
echo "OK: wads/freedoom-$V/"
