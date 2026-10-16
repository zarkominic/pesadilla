#!/usr/bin/env python3
"""construir_pwad.py — junta los PNG de arte/ en un PWAD que sustituye recursos de Freedoom.

Uso:
    ~/.venvs/pesadilla/bin/python tools/wad/construir_pwad.py \
        --iwad wads/freedoom-0.13.0/freedoom1.wad --arte arte/sprites --salida build/pesadilla.wad

- Cada PNG se llama como el lump que sustituye (POSSA1.png, PISGA0.png…), con fondo transparente.
- Desplazamientos (dónde «se apoya» el sprite), por orden de preferencia:
  1. arte/sprites/offsets.json: {"POSSA1": [izq, sup], ...}
  2. Si el lump existe en el IWAD: se conserva su punto de apoyo
     (monstruos: centro de los pies; armas: centro del borde inferior en pantalla).
  3. Si no: centro horizontal y pies 4 px por debajo del origen.
- El PWAD se carga con -merge (Chocolate Doom fusiona los sprites como deutex).
"""
import argparse
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
from doomgfx import PaletteMapper, encode_patch, read_palette, read_wad, write_wad  # noqa: E402
from PIL import Image  # noqa: E402


def iwad_patch_geometry(lumps):
    geo = {}
    in_sprites = False
    for name, data in lumps:
        if name in ('S_START', 'SS_START'):
            in_sprites = True
        elif name in ('S_END', 'SS_END'):
            in_sprites = False
        elif in_sprites and len(data) >= 8:
            geo[name] = struct.unpack('<hhhh', data[:8])
    return geo


def default_offsets(name, w, h, geo):
    if name in geo:
        iw, ih, il, it = geo[name]
        if il < 0:  # arma en primera persona: offsets negativos = posición en pantalla
            center_x = -il + iw / 2
            bottom = -it + ih
            return (-round(center_x - w / 2), -round(bottom - h))
        feet_below = ih - it  # píxeles del sprite por debajo del suelo
        return (round(w / 2), h - feet_below)
    return (w // 2, h - 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--iwad', required=True)
    ap.add_argument('--arte', required=True, help='carpeta con PNG de sprites')
    ap.add_argument('--salida', required=True)
    args = ap.parse_args()

    _, iwad_lumps = read_wad(args.iwad)
    geo = iwad_patch_geometry(iwad_lumps)
    mapper = PaletteMapper(read_palette(args.iwad))

    offsets_path = os.path.join(args.arte, 'offsets.json')
    explicit = json.load(open(offsets_path)) if os.path.exists(offsets_path) else {}

    sprites = []
    for fn in sorted(os.listdir(args.arte)):
        if not fn.lower().endswith('.png'):
            continue
        name = os.path.splitext(fn)[0].upper()
        if len(name) > 8:
            sys.exit(f'nombre de lump demasiado largo: {name}')
        img = Image.open(os.path.join(args.arte, fn)).convert('RGBA')
        bbox = img.getbbox()
        if bbox is None:
            sys.exit(f'{fn} está vacío')
        if name not in explicit:
            img = img.crop(bbox)  # recorta lo transparente; el apoyo se calcula sobre lo visible
        off = tuple(explicit.get(name) or default_offsets(name, img.width, img.height, geo))
        sprites.append((name, encode_patch(img, off, mapper)))
        print(f'{name:8s} {img.width:3d}x{img.height:<3d} offsets {off}')

    lumps = [('S_START', b'')] + sprites + [('S_END', b'')]
    os.makedirs(os.path.dirname(os.path.abspath(args.salida)), exist_ok=True)
    write_wad(args.salida, lumps)
    print(f'→ {args.salida}: {len(sprites)} sprites')


if __name__ == '__main__':
    main()
