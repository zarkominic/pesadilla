#!/usr/bin/env python3
"""puno.py — EL PUÑO (sustituye al puño de Freedoom), dibujado por código.

Uso:
    ~/.venvs/pesadilla/bin/python tools/arte/puno.py --salida arte/sprites
    (opcional: --vista <carpeta> guarda además una hoja de contactos y simulaciones de pantalla)

Escribe PUNGA0.png (reposo) y PUNGB0-D0.png (el puñetazo; en el juego: A reposo y B, C, D, C, B
al golpear, con el golpe en C) y añade sus desplazamientos a <salida>/offsets_<script>.json.

Es la misma mano derecha del pistolón (guante de cuero con pespuntes, manopla con ribete claro,
manga granate) cerrada en puño, con el motor común arma1p.py: modelo SDF en centímetros, trazado
desde el ojo del jugador con la proyección de los psprites, rampas de PLAYPAL y contorno oscuro.
Cada fotograma coloca el puño en pantalla (centro, profundidad, giro) y el brazo sale hacia el
hombro derecho, por debajo de la cámara; todos comparten el lienzo de pantalla, así que los
desplazamientos son exactos y no hay saltos.
"""
import argparse
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from arma1p import (RAMPAS, Arma, capsula, detalle_puno, dibujar, filo, guante, guardar,  # noqa: E402
                    guardar_offsets, marco_mira, pantalla_a_camara, pliegues_pano, puno, unit, v3)

MATS = ['cuero', 'ribete', 'manga']
BRILLO = {'cuero': (0.14, 10), 'ribete': (0.1, 10), 'manga': (0.0, 1)}   # el paño no brilla
GANANCIA = {'cuero': 1.0, 'ribete': 0.78, 'manga': 0.8}
RAMPAS_PUNO = dict(RAMPAS, manga=RAMPAS['pano'])   # la manga: paño granate oscuro (como el capirote)
PLIEGUES = (7.5, 14.5, 22.0)        # surcos del paño a lo largo del antebrazo (cm desde la muñeca)

ESCALA = 1.2                         # guante algo exagerado, como las piezas del pistolón
CENTRO_PUNO = v3(0.0, -0.6, 6.0) * ESCALA   # punto de la mano que se coloca en pantalla
HOMBRO = v3(19.0, -30.0, -4.0)      # hombro derecho en espacio de cámara (cm)


def preparar(pose):
    """Pose de pantalla → pose con (R, T) y el brazo en espacio de la mano."""
    sx, sy, z = pose['centro']
    C = pantalla_a_camara(sx, sy, z)
    codo = np.asarray(pose['codo'], float)
    # el puño apunta desde el codo hacia el centro del puño (más un retoque de giro/cabeceo)
    a = unit(C - codo)
    yaw, pitch = math.radians(pose.get('guiñada', 0.0)), math.radians(pose.get('cabeceo', 0.0))
    a = unit(a + v3(math.sin(yaw), math.sin(pitch), 0.0))
    # 'dorso': hacia dónde mira el dorso de la mano (espacio de cámara), girado 'alabeo' grados
    R = marco_mira(a, pose.get('dorso', (0.0, 1.0, 0.0)), pose.get('alabeo', 0.0))
    T = C - R @ CENTRO_PUNO
    p = dict(pose)
    p['R'], p['T'] = R, T
    codo_h = R.T @ (codo - T)
    hombro_h = R.T @ (HOMBRO - T)
    w0 = v3(0.0, -0.3, -0.5) * ESCALA
    p['w0'] = w0
    p['antebrazo'] = unit(codo_h - w0)
    p['largo'] = float(np.linalg.norm(codo_h - w0))
    p['codo_h'], p['hombro_h'] = codo_h, hombro_h
    return p


def modelo(P, pose):
    d = {}
    mano, w0 = puno(P, escala=ESCALA)
    d['cuero'] = mano
    guante(d, P, w0, pose['antebrazo'], largo_manga=pose['largo'], escala=ESCALA)
    # brazo: codo y brazo hasta el hombro (manga)
    d['manga'] = np.minimum(d['manga'], capsula(P, pose['codo_h'], pose['hombro_h'], 4.7, 5.6))
    D = np.stack([d[m] for m in MATS], 1)
    return D.min(1), D.argmin(1)


def detalle(arma, r, I):
    detalle_puno(arma, r, I, np.ones(r['mat'].shape, bool), escala=ESCALA)
    pose = r['pose']
    # paño: 3 pliegues marcados y el color claro solo en el filo iluminado (sin brillo en medio)
    pliegues_pano(arma, r, I, pose['w0'], pose['antebrazo'], PLIEGUES)
    filo(arma, r, I)


ARMA = Arma(MATS, modelo, BRILLO, GANANCIA, detalle, rampas=RAMPAS_PUNO)

# Lienzo común en coordenadas de pantalla completa (320x200), con margen a la derecha para el
# balanceo del arma al andar (el psprite se desplaza hasta 16 px a cada lado).
LIENZO = (60, 60, 296, 150)   # x0, y0, ancho, alto → x hasta 356, y hasta 210

POSES = {
    # reposo: puño en guardia abajo a la derecha, nudillos arriba, la palma mirando hacia el centro
    'PUNGA0': dict(centro=(226, 158, 26.0), codo=(14.0, -36.0, 22.0), dorso=(0.5, 0.0, 1.0)),
    # arranque: el puño se retrasa y baja (unos 20 px) girando hacia dentro: carga el golpe
    'PUNGB0': dict(centro=(240, 176, 23.0), codo=(18.0, -38.0, 8.0), dorso=(0.8, 0.2, 1.0), alabeo=15.0),
    # golpe (aquí se hace el daño): a medio camino hacia el centro, girando la palma hacia abajo
    'PUNGC0': dict(centro=(194, 140, 36.0), codo=(16.0, -26.0, 12.0), dorso=(0.0, 1.0, 0.4)),
    # brazo estirado: el puño lejos, en el centro, de perfil (se ve el pulgar)
    'PUNGD0': dict(centro=(160, 118, 40.0), codo=(13.0, -17.0, 19.0), dorso=(0.0, 1.0, 0.0), alabeo=-30.0),
}


def render_fotograma(nombre, S=4):
    pose = preparar(POSES[nombre])
    return dibujar(ARMA, pose, pose['R'], pose['T'], LIENZO, S, t0=6.0, tmax=120.0, pasos=200)


def vista(carpeta, salida):
    """Hoja de contactos ampliada y pantallas simuladas (con barra de estado y sin ella)."""
    from PIL import Image, ImageDraw
    from arma1p import simular_pantalla
    nombres = list(POSES)
    filas = []
    for barra in (True, False):
        fila = [simular_pantalla(carpeta, [n], barra) for n in nombres]
        filas.append(fila)
    W = Image.new('RGBA', (330 * len(nombres), 210 * 2 + 20), (20, 20, 20, 255))
    for r, fila in enumerate(filas):
        for c, im in enumerate(fila):
            W.paste(im, (330 * c, 210 * r + 20))
            ImageDraw.Draw(W).text((330 * c + 4, 4), nombres[c], fill=(230, 230, 230, 255))
    W = W.resize((W.width * 2, int(W.height * 1.2) * 2), Image.NEAREST)
    W.save(salida)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--salida', required=True, help='carpeta de PNG (arte/sprites)')
    ap.add_argument('--muestreo', type=int, default=4, help='rayos por lado de píxel (4 = 16 por píxel)')
    ap.add_argument('--solo', default=None, help='solo estos lumps (separados por comas)')
    ap.add_argument('--vista', default=None, help='PNG con la hoja de pantallas simuladas')
    args = ap.parse_args()
    os.makedirs(args.salida, exist_ok=True)
    solo = [s.strip().upper() for s in args.solo.split(',')] if args.solo else None
    x0, y0, _, _ = LIENZO
    offsets = {}
    for nombre in POSES:
        if solo and nombre not in solo:
            continue
        img = render_fotograma(nombre, args.muestreo)
        offsets[nombre], g = guardar(img, x0, y0, os.path.join(args.salida, nombre + '.png'))
        print(f'{nombre}: {g[2]}x{g[3]} en pantalla ({g[0]}, {g[1]}) offsets {offsets[nombre]}')
    guardar_offsets(args.salida, offsets)
    if args.vista:
        vista(args.salida, args.vista)


if __name__ == '__main__':
    main()
