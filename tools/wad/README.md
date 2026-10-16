# tools/wad — del PNG al WAD

Convierte el arte propio (PNG con fondo transparente) al formato de Doom y lo empaqueta en un
PWAD que sustituye los recursos equivalentes de Freedoom.

## Preparación (una vez)

El entorno de Python vive fuera de iCloud para no sincronizar miles de ficheros:

```bash
python3 -m venv ~/.venvs/pesadilla && ~/.venvs/pesadilla/bin/pip install pillow
```

## Construir el PWAD

```bash
~/.venvs/pesadilla/bin/python tools/wad/construir_pwad.py \
  --iwad wads/freedoom-0.13.0/freedoom1.wad --arte arte/sprites --salida build/pesadilla.wad
```

- Cada PNG se llama como el lump que sustituye: `POSSA1.png` (zombi, fotograma A, ángulo 1),
  `PISGA0.png` (pistola, fotograma A)…
- El punto de apoyo se copia del sprite de Freedoom que sustituye (pies del monstruo, posición
  del arma en pantalla). Para forzarlo: `arte/sprites/offsets.json` con `{"POSSA1": [izq, sup]}`.
- Los colores se pasan a la paleta de 256 colores de Freedoom (PLAYPAL) por el más cercano.

## Probar en local

El motor carga el PWAD con `-merge` (fusiona los sprites como deutex):
copia `build/pesadilla.wad` a `motor/src/` y añádelo en `index.html` (preRun + argumentos).

## Ficheros

- `doomgfx.py`: leer/escribir WADs, decodificar y codificar patches, paleta.
- `construir_pwad.py`: PNG → PWAD.
