#!/usr/bin/env python3
"""construir_pwad.py — junta los PNG de arte/ en un PWAD que sustituye recursos de Freedoom.

Uso:
    ~/.venvs/pesadilla/bin/python tools/wad/construir_pwad.py \
        --iwad wads/freedoom-0.13.0/freedoom1.wad --arte arte/sprites --salida build/pesadilla.wad

- Cada PNG se llama como el lump que sustituye (POSSA1.png, PISGA0.png…), con fondo transparente.
- Desplazamientos (dónde «se apoya» el sprite), por orden de preferencia:
  1. arte/sprites/offsets.json u offsets_<pieza>.json: {"POSSA1": [izq, sup], ...}
  2. Si el lump existe en el IWAD: se conserva su punto de apoyo
     (monstruos: centro de los pies; armas: centro del borde inferior en pantalla).
  3. Si no: centro horizontal y pies 4 px por debajo del origen.
- El PWAD se carga con -merge (Chocolate Doom fusiona los sprites como deutex).

Texturas (opcional):
- --parches <carpeta>: PNG con el nombre de un PARCHE de pared del IWAD (los que usa TEXTURE1 vía
  PNAMES). Mismo tamaño exacto que el original; se conservan sus offsets. Si el original es opaco,
  el PNG también debe serlo (si no, el motor deja «agujeros» en la pared); si tiene huecos (rejas,
  telarañas), el PNG decide los suyos con el alfa. Van como lumps sueltos: el motor busca los parches
  por nombre y encuentra antes los del PWAD.
- --suelos <carpeta>: PNG de 64x64 con el nombre de un SUELO/TECHO (flat) del IWAD. Van entre
  F_START/F_END en el orden del IWAD. Ojo: al fusionar (-merge), el motor quita del IWAD los suelos
  sustituidos y pone los del PWAD al final, así que una animación (agua, lava, limo…) solo funciona si
  se sustituyen TODOS sus fotogramas: se comprueba aquí. F_SKY1 (marca del cielo) no se toca.
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


# Animaciones de suelos del motor (p_spec.c, animdefs): primero y último fotograma.
FLAT_ANIMS = [('NUKAGE1', 'NUKAGE3'), ('FWATER1', 'FWATER4'), ('SWATER1', 'SWATER4'), ('LAVA1', 'LAVA4'),
              ('BLOOD1', 'BLOOD3'), ('RROCK05', 'RROCK08'), ('SLIME01', 'SLIME04'), ('SLIME05', 'SLIME08'),
              ('SLIME09', 'SLIME12')]


def iwad_section(lumps, starts, ends):
    out, ins = [], False
    for name, data in lumps:
        if name in starts:
            ins = True
        elif name in ends:
            ins = False
        elif ins and data:
            out.append((name, data))
    return out


def construir_parches(carpeta, iwad_lumps, mapper):
    from doomgfx import decode_patch, read_palette  # noqa: F401
    originales = dict(iwad_section(iwad_lumps, ('P_START', 'PP_START'), ('P_END', 'PP_END')))
    salida = []
    for fn in sorted(os.listdir(carpeta)):
        if not fn.lower().endswith('.png'):
            continue
        name = os.path.splitext(fn)[0].upper()
        if name not in originales:
            sys.exit(f'parche {name}: no existe en el IWAD')
        w, h, il, it = struct.unpack('<hhhh', originales[name][:8])
        img = Image.open(os.path.join(carpeta, fn)).convert('RGBA')
        if img.size != (w, h):
            sys.exit(f'parche {name}: mide {img.size}, el original {w}x{h} (las texturas dependen del tamaño)')
        salida.append((name, encode_patch(img, (il, it), mapper)))
    return salida


def construir_suelos(carpeta, iwad_lumps, mapper):
    orden = [n for n, _ in iwad_section(iwad_lumps, ('F_START', 'FF_START'), ('F_END', 'FF_END'))]
    pngs = {os.path.splitext(fn)[0].upper(): fn for fn in os.listdir(carpeta) if fn.lower().endswith('.png')}
    for name in pngs:
        if name not in orden:
            sys.exit(f'suelo {name}: no existe en el IWAD')
        if name == 'F_SKY1':
            sys.exit('F_SKY1 es la marca del cielo: no se sustituye')
    for a, b in FLAT_ANIMS:
        if a in orden and b in orden:
            grupo = orden[orden.index(a):orden.index(b) + 1]
            dentro = [g for g in grupo if g in pngs]
            if dentro and len(dentro) != len(grupo):
                sys.exit(f'animación {a}-{b}: hay que sustituir todos sus fotogramas {grupo} (faltan {sorted(set(grupo) - set(dentro))})')
    salida = []
    for name in orden:
        if name not in pngs:
            continue
        img = Image.open(os.path.join(carpeta, pngs[name])).convert('RGB')
        if img.size != (64, 64):
            sys.exit(f'suelo {name}: debe medir 64x64')
        px = img.load()
        salida.append((name, bytes(mapper.index(px[x, y]) for y in range(64) for x in range(64))))
    return salida


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--iwad', required=True)
    ap.add_argument('--arte', required=True, help='carpeta con PNG de sprites')
    ap.add_argument('--salida', required=True)
    ap.add_argument('--parches', help='carpeta con PNG de parches de pared (opcional)')
    ap.add_argument('--suelos', help='carpeta con PNG de suelos y techos 64x64 (opcional)')
    args = ap.parse_args()

    _, iwad_lumps = read_wad(args.iwad)
    geo = iwad_patch_geometry(iwad_lumps)
    mapper = PaletteMapper(read_palette(args.iwad))

    # offsets.json y offsets_<pieza>.json (cada script de arma escribe el suyo).
    explicit = {}
    for fn in sorted(os.listdir(args.arte)):
        if fn == 'offsets.json' or (fn.startswith('offsets_') and fn.endswith('.json')):
            explicit.update(json.load(open(os.path.join(args.arte, fn))))

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
    parches = construir_parches(args.parches, iwad_lumps, mapper) if args.parches and os.path.isdir(args.parches) else []
    suelos = construir_suelos(args.suelos, iwad_lumps, mapper) if args.suelos and os.path.isdir(args.suelos) else []
    lumps += parches
    if suelos:
        lumps += [('F_START', b'')] + suelos + [('F_END', b'')]
    os.makedirs(os.path.dirname(os.path.abspath(args.salida)), exist_ok=True)
    write_wad(args.salida, lumps)
    print(f'→ {args.salida}: {len(sprites)} sprites, {len(parches)} parches de pared, {len(suelos)} suelos')


if __name__ == '__main__':
    main()
