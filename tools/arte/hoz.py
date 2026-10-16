#!/usr/bin/env python3
"""hoz.py — LA HOZ (sustituye a la motosierra de Freedoom), dibujada por código.

Uso:
    ~/.venvs/pesadilla/bin/python tools/arte/hoz.py --salida arte/sprites
    (opcional: --vista <png> guarda además las pantallas simuladas de cada estado;
     --solo SAWGA0,CSAWA0 rehace solo esos lumps)

Escribe SAWGA0-D0 (la hoz en primera persona) y CSAWA0 (la hoz tirada en el suelo para recogerla)
y sus desplazamientos en <salida>/offsets_hoz.json.

En el juego (info.c) la motosierra va: en reposo C, D, C, D… (4 tics cada uno; C también al subir
y bajar el arma) y al atacar A, B, A, B… (A_Saw en cada uno, golpe continuo cuerpo a cuerpo). Aquí:
C y D = la hoz en guardia abajo a la derecha, con la hoja alzada y curvada hacia el centro, con un
leve temblor amenazante (la hoja gira unos grados y el brillo del filo cambia); A y B = dos tajos
de siega rápidos que cruzan el centro de la pantalla (A: la hoja entra por arriba a la derecha;
B: sale abajo a la izquierda), con estelas de movimiento detrás de la punta y del lomo.

Modelo SDF en centímetros con el motor común arma1p.py (misma proyección, luz, paleta y contorno
que el pistolón, la escopeta y el puño): hoja de hierro en espiral (más ancha cerca del mango y
afilada hasta la punta), filo claro en el lado de dentro, manchas de óxido y de sangre seca, espiga
y virola de hierro, mango de nogal con pomo; y la mano derecha con el guante de cuero (pespuntes,
manopla con ribete claro) y la manga de paño granate oscuro con pliegues.
"""
import argparse
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from arma1p import (CONTORNO, RAMPAS, Agarre, Arma, _hx, caja, capsula, costuras, desplazar,  # noqa: E402
                    dibujar, elipsoide, filo, guante, guardar, guardar_offsets, mano_agarre,
                    pantalla_a_camara, pliegues_pano, proyectar, rot_x, rot_z, smin, tubo_z, unit,
                    v3, veta)
from sdf import vnoise  # noqa: E402

MATS = ['hoja', 'filo', 'oxido', 'sangre', 'hierro', 'nogal', 'cuero', 'ribete', 'manga']
RAMPAS_HOZ = dict(
    RAMPAS,
    # hoja: hierro de forja gastado, grises medios (5, 109, 107, 104, 102, 99, 96, 92, 87)
    hoja=_hx(0x1b1b1b, 0x2f2f2f, 0x3b3b3b, 0x4f4f4f, 0x5b5b5b, 0x6f6f6f, 0x838383, 0x9f9f9f, 0xbfbfbf),
    # filo: acero amolado, claro y frío (102, 97, 92, 87, 84, 80, 4)
    filo=_hx(0x5b5b5b, 0x7f7f7f, 0x9f9f9f, 0xbfbfbf, 0xd3d3d3, 0xefefef, 0xffffff),
    # óxido: pardo rojizo (239, 238, 237, 236, 74, 72)
    oxido=_hx(0x2f1b0b, 0x372313, 0x432f1b, 0x4f3b27, 0x5f4323, 0x774f2b),
    # sangre seca: los mismos rojos de las criaturas (191, 189, 187, 185, 182)
    sangre=_hx(0x430000, 0x5b0000, 0x730000, 0x8b0000, 0xb30000),
    # virola y espiga: hierro oscuro como la báscula de la escopeta
    hierro=_hx(0x1b1b1b, 0x232323, 0x2f2f2f, 0x3b3b3b, 0x4f4f4f, 0x5b5b5b, 0x6f6f6f, 0x838383),
    manga=RAMPAS['pano'],
)
BRILLO = {'hoja': (0.35, 18), 'filo': (0.9, 14), 'oxido': (0.05, 6), 'sangre': (0.3, 20), 'hierro': (0.4, 24),
          'nogal': (0.15, 12), 'cuero': (0.12, 10), 'ribete': (0.1, 10), 'manga': (0.0, 1)}
GANANCIA = {'hoja': 0.78, 'filo': 0.95, 'oxido': 0.9, 'sangre': 0.95, 'hierro': 0.75, 'nogal': 0.9,
            'cuero': 1.0, 'ribete': 0.7, 'manga': 0.8}

# ---------------------------------------------------------------------------------------------
# El modelo (espacio de la hoz: origen en la boca de la virola, z a lo largo del mango hacia la
# hoja, y hacia donde se curva la hoja (el lado del filo), x = normal al plano de la hoja)
# ---------------------------------------------------------------------------------------------

Z_N = 2.4               # espiga: de la virola al arranque de la curva
R0, A_ESP = 11.0, 1.05  # espiral de la hoja: radio (cm) en el arranque y cuánto se cierra por radián
PHI_FIN = 3.55          # ángulo de la punta (rad): la hoja da algo más de media vuelta
G_LOMO, G_FILO = 0.32, 0.05   # medio grosor en el lomo y en el filo (exagerado para que se lea)
U_FILO = 0.24           # parte de la anchura que es filo amolado
LARGO_MANGO = 12.5
MANO = Agarre(G0=(0.0, 0.0, -1.75), GE=(0.0, 0.0, -1.0), GF=(-0.62, -0.78, 0.0), GX=(0.78, -0.62, 0.0), r=1.55)
CENTRO_MANO = v3(0.0, 0.0, -5.2)   # punto de la hoz que se coloca en pantalla
HOMBRO = v3(19.0, -30.0, -4.0)     # hombro derecho en espacio de cámara (cm)
PLIEGUES = (8.0, 15.0, 22.0)


def _suave(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def ancho(ph):
    """Anchura de la hoja (cm) según el ángulo: estrecha en la espiga, ancha al primer tercio,
    afilada hasta la punta."""
    base = 1.3 + 2.2 * _suave(ph / 0.95)
    cola = np.clip((PHI_FIN - ph) / (PHI_FIN - 1.15), 0.0, 1.0) ** 0.62
    return base * cola


def hoja(P):
    """Distancia a la hoja en espiral → (distancia, u, φ): u = 0 en el filo (dentro), 1 en el lomo."""
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    dy, dz = y - R0, z - Z_N
    rho = np.sqrt(dy * dy + dz * dz)
    phi = np.arctan2(dz, -dy)
    phi = np.where(phi < -np.pi / 2, phi + 2 * np.pi, phi)
    ph = np.clip(phi, 0.0, PHI_FIN)
    rc = R0 - A_ESP * ph
    w = ancho(ph)
    radial = np.abs(rho - rc) - w / 2
    tapas = np.maximum(-phi, phi - PHI_FIN) * rho
    d2 = np.maximum(radial, tapas)
    u = np.clip((rho - (rc - w / 2)) / np.maximum(w, 1e-3), 0.0, 1.0)
    t = G_FILO + (G_LOMO - G_FILO) * np.sqrt(u)
    dx = np.abs(x) - t
    d = np.sqrt(np.maximum(d2, 0) ** 2 + np.maximum(dx, 0) ** 2) + np.minimum(np.maximum(d2, dx), 0)
    return d * 0.85, u, phi


def manchas(P, u, phi):
    """Máscaras deterministas de óxido (en el lomo) y sangre seca (cerca del filo)."""
    n1 = vnoise(P, 0.55, seed=3) * 0.65 + vnoise(P, 1.6, seed=4) * 0.35
    n2 = vnoise(P, 0.45, seed=9) * 0.6 + vnoise(P, 1.9, seed=11) * 0.4
    oxido = (n1 > 0.6) & (u > 0.4)
    sangre = (n2 > 0.74 - 0.12 * (1 - u)) & (u < 0.75) & (phi > 0.9) & (phi < 3.1)
    return oxido, sangre


def modelo_hoz(P, d):
    """Hoja, espiga, virola y mango (sin la mano)."""
    dh, u, phi = hoja(P)
    espiga = caja(P, (0.0, 0.0, (Z_N - 0.6) / 2), (0.3, 0.62, (Z_N + 0.6) / 2), 0.12)
    hj = smin(dh, espiga, 0.35)
    ox, sg = manchas(P, u, phi)
    es_filo = (u < U_FILO) & (phi > 0.12)
    sg = sg & ~(es_filo & (vnoise(P, 2.2, seed=5) > 0.55))   # el filo amolado asoma entre la sangre
    d['sangre'] = np.where(sg, hj, 1e9)
    d['filo'] = np.where(es_filo & ~sg, hj, 1e9)
    d['oxido'] = np.where(ox & ~sg & ~es_filo, hj, 1e9)
    d['hoja'] = np.where(~sg & ~es_filo & ~ox, hj, 1e9)
    virola = np.minimum(tubo_z(P, -2.0, 0.0, 1.58, 1.52), tubo_z(P, -2.0, -1.6, 1.7, 1.7))
    remache = elipsoide(P, (0.0, 0.0, -1.0), (1.85, 0.32, 0.32))   # pasador que atraviesa la virola
    d['hierro'] = np.minimum(virola, remache)
    mango = capsula(P, (0.0, 0.0, -1.6), (0.0, 0.0, -LARGO_MANGO + 1.2), 1.38, 1.62)
    pomo = elipsoide(P, (0.0, 0.0, -LARGO_MANGO + 0.6), (1.95, 1.95, 1.25))
    d['nogal'] = smin(mango, pomo, 0.5)


def modelo(P, pose):
    d = {m: np.full(len(P), 1e9) for m in MATS}
    modelo_hoz(P, d)
    if pose.get('manos', True):
        mano, w0 = mano_agarre(P, MANO, pose['antebrazo'])
        dm = {'cuero': mano}
        guante(dm, P, w0, pose['antebrazo'], largo_manga=pose['largo'])
        dm['manga'] = np.minimum(dm['manga'], capsula(P, pose['codo_h'], pose['hombro_h'], 4.7, 5.6))
        for m in ('cuero', 'ribete', 'manga'):
            d[m] = np.minimum(d[m], dm[m])
    D = np.stack([d[m] for m in MATS], 1)
    return D.min(1), D.argmin(1)


def detalle(arma, r, I):
    """Veta del mango, rayado y picaduras de la hoja, pespuntes del guante, pliegues de la manga."""
    veta(arma, r, I, fuerza=0.09)
    pose = r.get('pose') or {}
    pl = r['pl']
    hj = np.isin(r['mat'], [arma.idx('hoja'), arma.idx('oxido')])
    if hj.any():
        q = pl[hj]
        rho = np.sqrt((q[:, 1] - R0) ** 2 + (q[:, 2] - Z_N) ** 2)
        v = 0.07 * np.sin(rho * 7.0 + 2.0 * vnoise(q, 0.8, seed=1))        # rayado del amolado
        v -= 0.18 * (vnoise(q, 2.4, seed=2) > 0.72)                         # picaduras
        I[hj] += v
    fl = r['mat'] == arma.idx('filo')
    if fl.any():
        q = pl[fl]
        _, u, _ = hoja(q)
        I[fl] += 0.25 * (u < U_FILO * 0.45)                                 # la arista misma, más clara
    if pose.get('manos', True) and 'antebrazo' in pose:
        costuras(arma, r, I, MANO)
        pliegues_pano(arma, r, I, pose['w0'], pose['antebrazo'], PLIEGUES)
        filo(arma, r, I)


ARMA = Arma(MATS, modelo, BRILLO, GANANCIA, detalle, rampas=RAMPAS_HOZ)

# ---------------------------------------------------------------------------------------------
# Poses: la mano se coloca en pantalla (x, y, profundidad) y la hoz se orienta con la dirección del
# mango (de pomo a hoja) y la dirección hacia la que se curva la hoja (espacio de cámara)
# ---------------------------------------------------------------------------------------------


def marco(pose):
    zh = unit(pose['mango'])
    c = np.asarray(pose['curva'], float)
    yh = unit(c - (c @ zh) * zh)
    xh = np.cross(yh, zh)
    return np.stack([xh, yh, zh], 1)


def preparar(pose):
    p = dict(pose)
    sx, sy, z = p['mano']
    C = pantalla_a_camara(sx, sy, z)
    R = marco(p)
    T = C - R @ CENTRO_MANO
    p['R'], p['T'] = R, T
    if p.get('manos', True):
        codo = np.asarray(p['codo'], float)
        codo_h = R.T @ (codo - T)
        _, w0 = mano_agarre(np.zeros((1, 3)), MANO, v3(0, 0, -1))
        p['w0'] = w0
        p['antebrazo'] = unit(codo_h - w0)
        p['largo'] = float(np.linalg.norm(codo_h - w0))
        p['codo_h'], p['hombro_h'] = codo_h, R.T @ (HOMBRO - T)
    return p


def pose_de(base, **cambios):
    p = dict(base)
    p.update(cambios)
    return p


LIENZO = (0, 30, 356, 182)   # x0, y0, ancho, alto (pantalla completa; margen para el balanceo)

POSE_C = dict(mano=(240, 168, 27.0), mango=(-0.12, 0.82, 0.56), curva=(-1.0, 0.05, -0.25), codo=(20.0, -40.0, 8.0))
POSES = {
    # reposo: hoz en guardia abajo a la derecha, la hoja alzada y curvada hacia el centro
    'SAWGC0': POSE_C,
    # el temblor: la hoja gira unos grados sobre el mango y la mano sube un poco
    'SAWGD0': pose_de(POSE_C, mano=(237, 165, 27.0), mango=(-0.19, 0.82, 0.54), curva=(-1.0, 0.2, 0.02)),
    # tajo 1: el brazo sube y la hoja se alza sobre el centro, el filo mirando abajo
    'SAWGA0': dict(mano=(236, 128, 30.0), mango=(-0.45, 0.75, 0.5), curva=(-0.9, -0.3, -0.2), codo=(22.0, -30.0, 14.0)),
    # tajo 2: la hoja baja cruzando el centro hacia la izquierda
    'SAWGB0': dict(mano=(178, 140, 29.0), mango=(-0.7, 0.35, 0.62), curva=(-0.35, -0.9, -0.15), codo=(16.0, -34.0, 14.0)),
}
# para las estelas: de qué pose viene cada tajo
ESTELA = {'SAWGA0': 'SAWGC0', 'SAWGB0': 'SAWGA0'}


def punto_hoja(phi, lado):
    """Punto de la hoja (espacio de la hoz) a un ángulo phi: lado = -1 filo, 0 centro, 1 lomo."""
    rc = R0 - A_ESP * phi
    r = rc + lado * ancho(np.float64(phi)) / 2
    return v3(0.0, R0 - r * math.cos(phi), Z_N + r * math.sin(phi))


def interpolar(p0, p1, t):
    p = dict(p1)
    for k in ('mano', 'mango', 'curva', 'codo'):
        p[k] = tuple((1 - t) * np.asarray(p0[k], float) + t * np.asarray(p1[k], float))
    return p


GRIS_ESTELA = _hx(0x2f2f2f, 0x3b3b3b, 0x4f4f4f, 0x5b5b5b, 0x6f6f6f, 0x838383, 0x9f9f9f)


def estela(img, nombre, desde=0.6, hasta=0.93, pasos=16):
    """Estela del tajo: la zona por la que ha pasado la hoja desde la pose anterior, rellena con un
    tramado de grises (en la paleta de Doom no hay transparencias: el tramado a 1 px se lee como un
    barrido translúcido), más claro y más denso junto a la hoja. Solo donde no hay nada pintado.
    Corta (el último tercio del movimiento) y rala, para que no ensucie sobre paredes claras."""
    if nombre not in ESTELA:
        return img
    from PIL import Image, ImageDraw
    p0, p1 = POSES[ESTELA[nombre]], POSES[nombre]
    x0, y0, w, h = LIENZO
    fis = np.linspace(0.5, PHI_FIN - 0.02, 14)
    lomo = [punto_hoja(f, 1.0) for f in fis]
    filo_ = [punto_hoja(f, -1.0) for f in fis]
    nivel = np.full((h, w), -1.0)
    contornos = []
    for k in range(pasos + 1):
        t = desde + (hasta - desde) * k / pasos
        pz = preparar(dict(interpolar(p0, p1, t), manos=False))
        contornos.append([proyectar(q, pz['R'], pz['T']) for q in lomo + filo_[::-1]])
    for k in range(pasos):
        s = (k + 0.5) / pasos
        m = Image.new('L', (w, h), 0)
        d = ImageDraw.Draw(m)
        a, b = contornos[k], contornos[k + 1]
        n = len(fis)
        for j in range(n - 1):        # el lomo y el filo de un paso al siguiente: cuadriláteros
            for (ia, ib) in ((j, j + 1), (2 * n - 2 - j, 2 * n - 1 - j)):
                quad = [a[ia], a[ib], b[ib], b[ia]]
                d.polygon([(x - x0, y - y0) for x, y in quad], fill=255)
            d.polygon([(x - x0, y - y0) for x, y in b], fill=255)
        sel = np.asarray(m) > 0
        nivel[sel] = np.maximum(nivel[sel], s)
    out = img.copy()
    Y, X = np.mgrid[0:h, 0:w]
    gx, gy = X + x0, Y + y0
    libre = (out[..., 3] == 0) & (nivel >= 0)
    # densidad del tramado: 1/4 al principio y 1/2 junto a la hoja
    pat4 = ((gx % 2 == 0) & (gy % 2 == 0))
    pat2 = ((gx + gy) % 2 == 0)
    pon = libre & (((nivel < 0.6) & pat4) | ((nivel >= 0.6) & pat2))
    col = np.array(GRIS_ESTELA, np.uint8)
    idx = np.clip((nivel * len(col)).astype(int), 0, len(col) - 1)
    out[pon, :3] = col[idx[pon]]
    out[pon, 3] = 255
    return out


def posproceso(nombre, img, pose):
    return estela(img, nombre)


def render_fotograma(nombre, S=4):
    pose = preparar(POSES[nombre])
    img = dibujar(ARMA, pose, pose['R'], pose['T'], LIENZO, S, previo=True, t0=6.0, tmax=120.0, pasos=200)
    return posproceso(nombre, img, pose)


# ---------------------------------------------------------------------------------------------
# La hoz en el suelo (CSAWA0)
# ---------------------------------------------------------------------------------------------


def recoger(salida, S=4):
    """CSAWA0: la hoz tirada en el suelo, de lado y algo desde arriba (cámara lejana, casi
    ortográfica). El grosor se exagera para que se lea a esta escala, como los objetos de Doom."""
    pose = {'manos': False}
    R = rot_x(math.radians(-50)) @ np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]], float) @ rot_z(math.radians(80))
    dist = 300.0
    E = 2.45                       # escala de los objetos del mundo (como los de Doom, exagerados)
    c = v3(0.0, 9.0, 1.0) * E
    T = v3(0.0, 0.0, dist) - R @ c
    k = np.array([1 / (E * 1.3), 1 / E, 1 / E])     # y el grosor, algo más
    claro = dict(GANANCIA, hoja=0.95, hierro=0.9, nogal=1.0)
    gorda = Arma(MATS, lambda P, pz: modelo(P * k, pz), BRILLO, claro, detalle, rampas=RAMPAS_HOZ)
    img = dibujar(gorda, pose, R, T, (110, 60, 100, 80), S, bordes=False, t0=dist - 90, tmax=dist + 90, pasos=300)
    a = img[..., 3] > 0
    ys, xs = np.nonzero(a)
    img = img[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    from PIL import Image
    Image.fromarray(img, 'RGBA').save(os.path.join(salida, 'CSAWA0.png'))
    h, w = img.shape[:2]
    return [w // 2, h]


def vista(carpeta, salida):
    from PIL import Image, ImageDraw
    from arma1p import simular_pantalla
    estados = [['SAWGC0'], ['SAWGD0'], ['SAWGA0'], ['SAWGB0']]
    W = Image.new('RGBA', (330 * len(estados), 210 * 2 + 20), (20, 20, 20, 255))
    for c, capas in enumerate(estados):
        for r, barra in enumerate((True, False)):
            W.paste(simular_pantalla(carpeta, capas, barra), (330 * c, 210 * r + 20))
        ImageDraw.Draw(W).text((330 * c + 4, 4), '+'.join(capas), fill=(230, 230, 230, 255))
    W = W.resize((W.width * 2, int(W.height * 1.2) * 2), Image.NEAREST)
    W.save(salida)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--salida', required=True, help='carpeta de PNG (arte/sprites)')
    ap.add_argument('--muestreo', type=int, default=4, help='rayos por lado de píxel (4 = 16 por píxel)')
    ap.add_argument('--solo', default=None, help='solo estos lumps (separados por comas)')
    ap.add_argument('--vista', default=None, help='PNG con las pantallas simuladas')
    args = ap.parse_args()
    os.makedirs(args.salida, exist_ok=True)
    solo = [s.strip().upper() for s in args.solo.split(',')] if args.solo else None
    x0, y0, _, _ = LIENZO
    offsets = {}
    ruta_off = os.path.join(args.salida, 'offsets_hoz.json')
    if solo and os.path.exists(ruta_off):          # con --solo se conservan los demás lumps
        with open(ruta_off) as fh:
            offsets.update(json.load(fh))
    for nombre in POSES:
        if solo and nombre not in solo:
            continue
        img = render_fotograma(nombre, args.muestreo)
        offsets[nombre], g = guardar(img, x0, y0, os.path.join(args.salida, nombre + '.png'))
        print(f'{nombre}: {g[2]}x{g[3]} en pantalla ({g[0]}, {g[1]}) offsets {offsets[nombre]}')
    if not solo or 'CSAWA0' in solo:
        offsets['CSAWA0'] = recoger(args.salida, args.muestreo)
        print(f'CSAWA0: offsets {offsets["CSAWA0"]}')
    guardar_offsets(args.salida, offsets, pieza='hoz')
    if args.vista:
        vista(args.salida, args.vista)


if __name__ == '__main__':
    main()
