#!/usr/bin/env python3
"""pistolon.py — EL PISTOLÓN DE CHISPA (sustituye a la pistola de Freedoom), dibujado por código.

Uso:
    ~/.venvs/pesadilla/bin/python tools/arte/pistolon.py --salida arte/sprites

Escribe PISGA0.png (reposo), PISGB0.png (disparo), PISGC0.png (vuelta), PISFA0.png (fogonazo) y
añade sus desplazamientos a <salida>/offsets_<script>.json (conserva las claves de otros lumps).

Cómo se dibuja (determinista, sin IA ni azar no sembrado), con el motor común arma1p.py:
- Modelo 3D hecho con primitivas SDF (cápsulas, conos, cajas redondeadas, elipsoides) en
  centímetros: cañón de hierro con boca de latón, caja de nogal con culata curvada, llave de
  chispa (pie de gato, batería, cazoleta) y mano derecha con guante de cuero y manga.
- Se traza con raymarching vectorizado (numpy) desde el ojo del jugador, con la proyección de los
  «psprites» de Doom: pantalla 320x200 cuyos píxeles se ven 1,2 veces más altos que anchos.
- Se renderiza a 4x, se reduce por mayoría de alfa, se sombrea con rampas de la paleta PLAYPAL
  (luz desde arriba-izquierda-delante), se oscurecen los bordes de profundidad y se añade un
  contorno oscuro de 1 px.
- Los tres fotogramas comparten sistema de coordenadas de pantalla: los desplazamientos salen de
  la posición real en pantalla (x_izq = 1 - izq, y_sup = 32 - sup, vista completa 320x200), así
  no hay saltos entre fotogramas y el fogonazo cae en la boca del cañón del fotograma B.
"""
import argparse
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from arma1p import (RAMPAS, Arma, bocanada, capsula, caja, dibujar, elipsoide,  # noqa: E402,F401
                    elipsoide_ejes, fogonazo, girar, guardar, guardar_offsets, matriz_canon,
                    retroceso, rot_x, smin, tubo_z, v3, veta)
from arma1p import proyectar as proyectar_rt  # noqa: E402

MATS = ['hierro', 'laton', 'nogal', 'cuero', 'ribete', 'manga', 'pedernal']

# ---------------------------------------------------------------------------------------------
# El modelo (espacio del arma: origen en la recámara, z hacia la boca, y arriba, x a la derecha)
# ---------------------------------------------------------------------------------------------

LARGO = 23.0                 # cañón (cm)
PIVOTE_GATO = v3(2.2, -1.0, -4.4)       # eje del pie de gato (en la platina)
PIVOTE_BATERIA = v3(2.2, 0.15, 1.9)     # eje de la batería (delante de la cazoleta)

# Culata: línea central de la empuñadura, que baja hacia atrás desde la garganta
G0 = v3(0.0, -1.5, -7.0)                 # arriba de la empuñadura (donde se apoya la membrana)
GE = v3(0.0, -0.75, -0.66) / np.linalg.norm([0.0, -0.75, -0.66])   # eje de la empuñadura
GF = v3(0.0, -0.66, 0.75) / np.linalg.norm([0.0, -0.66, 0.75])     # «delante» de la empuñadura
GX = v3(1.0, 0.0, 0.0)
ANTEBRAZO = v3(0.5, -0.6, -0.62) / np.linalg.norm([0.5, -0.6, -0.62])


def en_mano(s, x, f):
    """Punto de la mano: s cm bajando por la empuñadura, x a la derecha, f hacia delante."""
    return G0 + s * GE + x * GX + f * GF


def modelo(P, pose):
    """Devuelve (distancia, material) por punto. material = índice en MATS."""
    d = {}

    # --- hierro: cañón (ochavado atrás, redondo delante), llave, pie de gato, batería ---
    canon = np.minimum(tubo_z(P, -0.4, 8.0, 1.66, 1.52, octo=True),
                       tubo_z(P, 7.5, LARGO - 0.9, 1.47, 1.28))
    anillo = tubo_z(P, 7.6, 8.4, 1.72, 1.72, octo=True)               # moldura
    cola = capsula(P, (0, 1.05, -0.3), (0, 0.4, -6.2), 0.42, 0.3)     # cola de la recámara
    platina = caja(P, (1.78, -1.1, -2.9), (0.26, 1.15, 4.7), 0.4)     # platina de la llave
    hierro = np.minimum(np.minimum(canon, anillo), np.minimum(cola, platina))

    # pie de gato: gira alrededor de su eje; pose['gato'] en grados (0 = montado, + = caído)
    Pg = girar(P, PIVOTE_GATO, rot_x(math.radians(pose['gato'])))
    o = PIVOTE_GATO
    k = 1.2  # tamaño de la llave (exagerado para que se lea)
    cuello = np.minimum(capsula(Pg, o + k * v3(0, -0.2, 0.3), o + k * v3(0, 1.3, -1.25), 0.6, 0.5),
                        capsula(Pg, o + k * v3(0, 1.3, -1.25), o + k * v3(0, 2.75, -0.75), 0.5, 0.45))
    talon = capsula(Pg, o + k * v3(0, -0.2, 0.3), o + k * v3(0, -0.55, 1.3), 0.46, 0.34)
    mandibula = caja(Pg, o + k * v3(0, 2.95, -0.25), (0.46, 0.48, 0.92), 0.16)
    mand_sup = caja(Pg, o + k * v3(0, 3.75, -0.3), (0.42, 0.24, 0.88), 0.14)
    tornillo = np.minimum(capsula(Pg, o + k * v3(0, 3.55, -0.55), o + k * v3(0, 4.65, -0.55), 0.28),
                          capsula(Pg, o + k * v3(-0.32, 4.65, -0.55), o + k * v3(0.32, 4.65, -0.55), 0.24))
    gato = np.minimum(np.minimum(np.minimum(cuello, talon), mandibula), np.minimum(mand_sup, tornillo))
    pedernal = caja(Pg, o + k * v3(0, 3.35, 0.75), (0.42, 0.3, 0.6), 0.08)

    # batería (rastrillo): placa vertical que tapa la cazoleta; pose['bateria'] en grados (- = abierta)
    Pb = girar(P, PIVOTE_BATERIA, rot_x(math.radians(pose['bateria'])))
    ob = PIVOTE_BATERIA
    bateria = np.minimum(caja(Pb, ob + k * v3(0, 1.45, -0.7), (0.5, 1.75, 0.2), 0.1),
                         caja(Pb, ob + k * v3(0, 0.12, -1.0), (0.52, 0.16, 0.84), 0.08))
    muelle = capsula(P, ob + k * v3(0, -0.75, 0.2), ob + k * v3(0, -0.85, 2.4), 0.26, 0.14)
    hierro = np.minimum(np.minimum(hierro, gato), np.minimum(bateria, muelle))
    d['hierro'] = hierro
    d['pedernal'] = pedernal

    # --- latón: boca del cañón (con labio), punto de mira, cazoleta, punta de la caja, pomo ---
    boca = np.minimum(tubo_z(P, LARGO - 1.6, LARGO - 0.3, 1.55, 1.7), tubo_z(P, LARGO - 0.5, LARGO, 1.85, 1.85))
    mira = caja(P, (0, 1.5, LARGO - 2.5), (0.18, 0.4, 0.55), 0.08)
    cazoleta = caja(P, (2.15, -0.05, 0.85), (0.6, 0.26, 0.9), 0.1)
    punta_caja = tubo_z(P, 16.6, 17.5, 1.32, 1.32, cy=-1.4)
    pomo = elipsoide(P, en_mano(10.6, 0, -0.6), (2.0, 1.9, 2.0))
    laton = np.minimum(np.minimum(boca, mira), np.minimum(cazoleta, np.minimum(punta_caja, pomo)))
    d['laton'] = laton

    # --- nogal: caja bajo el cañón, cuerpo de la llave, garganta y culata curvada ---
    caja_del = caja(P, (0, -1.5, 7.6), (1.42, 1.15, 9.4), 0.85)
    cuerpo = caja(P, (0.1, -1.35, -2.9), (1.72, 1.42, 5.0), 0.95)
    culata = np.minimum(capsula(P, (0, -1.0, -6.0), G0 + 0.0 * GE, 1.3, 1.35),
                        capsula(P, G0, en_mano(9.5, 0, -0.4), 1.35, 1.95))
    nogal = smin(np.minimum(caja_del, cuerpo), culata, 0.9)
    d['nogal'] = nogal

    # --- mano derecha con guante: dorso a la derecha, pulgar a la izquierda, dedos por delante ---
    dorso = elipsoide_ejes(P, en_mano(4.3, 1.75, -0.45), (GX, GE, GF), (1.4, 4.1, 2.8))
    palma = elipsoide_ejes(P, en_mano(4.6, 0.3, -1.3), (GX, GE, GF), (1.7, 3.9, 1.9))
    tenar = elipsoide_ejes(P, en_mano(2.4, -1.15, -1.25), (GX, GE, GF), (1.05, 2.1, 1.6))
    membrana = capsula(P, en_mano(0.9, 1.2, -0.5), en_mano(0.9, -0.9, -1.3), 0.95, 0.9)
    pulgar = np.minimum(capsula(P, en_mano(1.6, -1.35, -1.0), (-1.7, -0.75, -5.4), 0.95, 0.82),
                        capsula(P, (-1.7, -0.75, -5.4), (-1.75, -0.3, -3.3), 0.82, 0.72))
    mano = smin(smin(dorso, palma, 1.0), smin(smin(tenar, membrana, 0.8), pulgar, 0.6), 0.8)
    dedos = None
    for i, s in enumerate((0.9, 2.95, 4.9, 6.75)):
        r = 0.9 - 0.05 * i
        delante = 0.7 if i == 0 else 0.0                      # el índice va al gatillo, más adelante
        k = en_mano(s, 1.65, 1.3 + delante)                   # nudillo
        a = en_mano(s, 0.35, 2.35 + delante)                  # delante de la empuñadura
        b = en_mano(s + 0.2, -1.45, 1.35 + delante * 0.5)     # esquina izquierda
        c = en_mano(s + 0.3, -1.85, -0.15)                    # punta, en el lado izquierdo
        f = np.minimum(np.minimum(capsula(P, k, a, r, r * 0.95), capsula(P, a, b, r * 0.95, r * 0.9)),
                       capsula(P, b, c, r * 0.9, r * 0.82))
        dedos = f if dedos is None else np.minimum(dedos, f)
    mano = smin(mano, dedos, 0.45)
    w0 = en_mano(7.0, 0.9, -2.0)
    muneca = capsula(P, w0, w0 + 3.0 * ANTEBRAZO, 2.25, 2.3)
    mano = smin(mano, muneca, 1.2)
    d['cuero'] = mano

    # manopla acampanada del guante (mismo cuero), con un ribete claro en el borde, y manga
    ea, eb = w0 + 1.6 * ANTEBRAZO, w0 + 4.6 * ANTEBRAZO
    vuelta = capsula(P, ea, eb, 2.5, 3.5)
    hueco = capsula(P, eb - 0.1 * (eb - ea), eb + 0.6 * (eb - ea), 3.05)
    vuelta = np.maximum(vuelta, -hueco)
    d['cuero'] = smin(d['cuero'], vuelta, 0.6)
    t = (P - ea) @ ANTEBRAZO
    d['ribete'] = np.maximum(vuelta - 0.06, 3.7 - t)  # el último medio centímetro de la manopla
    d['manga'] = capsula(P, w0 + 4.0 * ANTEBRAZO, w0 + 30 * ANTEBRAZO, 3.0, 4.6)

    D = np.stack([d[m] for m in MATS], 1)
    mat = D.argmin(1)
    return D.min(1), mat


# ---------------------------------------------------------------------------------------------
# Cámara, luz y materiales (el trazado, la reducción y el color están en arma1p.py)
# ---------------------------------------------------------------------------------------------


def pose_a_matriz(pose):
    """Pose → (R, T): p_cámara = R · p_arma + T.

    La pose se da en pantalla: 'recamara' = (x, y, Z) posición en pantalla completa y profundidad
    (cm) de la recámara; 'boca' = (x, y) donde debe verse el centro de la boca del cañón;
    'alabeo' = giro (grados) sobre el eje del cañón (positivo: el costado derecho, el de la llave,
    se inclina hacia arriba).
    """
    R, T = matriz_canon(pose['recamara'], pose['boca'], LARGO, pose['alabeo'])
    # retroceso: el arma gira (boca arriba) alrededor de la muñeca y se desplaza (cm, cámara)
    giro = pose.get('retroceso', 0.0)
    if giro or 'empuje' in pose:
        R, T = retroceso(R, T, giro, pose.get('empuje', (0, 0, 0)), en_mano(4.0, 0.0, -1.0))
    return R, T


def proyectar(p_arma, pose):
    """Punto del espacio del arma → (x, y) en la pantalla completa 320x200."""
    R, T = pose_a_matriz(pose)
    return proyectar_rt(p_arma, R, T)


BRILLO = {'hierro': (0.55, 30), 'laton': (0.6, 22), 'nogal': (0.15, 12), 'cuero': (0.12, 10),
          'ribete': (0.1, 10), 'manga': (0.0, 1), 'pedernal': (0.3, 20)}


# cuánto de la rampa usa cada material con luz plena (el hierro queda oscuro salvo en los brillos)
GANANCIA = {'hierro': 0.72, 'laton': 0.9, 'nogal': 0.92, 'cuero': 1.0, 'ribete': 0.9, 'manga': 1.0,
            'pedernal': 0.9}


def detalle(arma, r, I):
    """Costuras del dorso del guante (tres pespuntes entre los dedos) y veta del nogal."""
    pl = r['pl']
    q = pl - G0
    sg, fg, xg = q @ GE, q @ GF, q[..., 0]
    cos = np.zeros(sg.shape, bool)
    for s0 in (1.95, 3.95, 5.85):
        cos |= (np.abs(sg - s0 - 0.25 * fg) < 0.16) & (xg > 1.2) & (fg > -2.6) & (fg < 1.4)
    sel = (r['mat'] == MATS.index('cuero')) & cos
    I[sel] -= 0.3
    veta(arma, r, I)


ARMA = Arma(MATS, modelo, BRILLO, GANANCIA, detalle)


# ---------------------------------------------------------------------------------------------
# Fotogramas
# ---------------------------------------------------------------------------------------------

# Lienzo común en coordenadas de pantalla completa (320x200); se recorta al guardar.
LIENZO = (100, 70, 170, 140)  # x0, y0, ancho, alto (abajo llega a y=210: sale por el borde)

POSE_A = {'recamara': (194.0, 136.0, 42.0), 'boca': (162.0, 110.0), 'alabeo': -8.0,
          'gato': 0.0, 'bateria': 0.0}


def pose_de(base, **cambios):
    p = dict(base)
    for k, v in cambios.items():
        if k in ('recamara', 'boca'):
            p[k] = tuple(a + b for a, b in zip(p[k], v))  # desplazamiento relativo
        elif k.startswith('d'):
            p[k[1:]] += v
        else:
            p[k] = v
    return p


POSES = {
    'PISGA0': POSE_A,
    # disparo: la boca salta hacia arriba girando sobre la muñeca y el arma retrocede hacia el
    # jugador; el pie de gato ha caído y la batería está abierta
    'PISGB0': pose_de(POSE_A, retroceso=10.0, empuje=(0.4, 1.2, -3.0), gato=58.0, bateria=-62.0),
    # vuelta: a medio camino
    'PISGC0': pose_de(POSE_A, retroceso=4.5, empuje=(0.2, 0.5, -1.4), gato=58.0, bateria=-62.0),
}


def render_fotograma(nombre, S=4):
    x0, y0, w, h = LIENZO
    pose = POSES[nombre]
    R, T = pose_a_matriz(pose)
    img = dibujar(ARMA, pose, R, T, LIENZO, S)
    # humo
    if nombre == 'PISGB0':
        px, py = proyectar(PIVOTE_BATERIA + (0.3, 0.6, -0.6), pose)
        bocanada(img, px - x0 + 2, py - y0 - 4,
                 [(0, 0, 3.2), (3, -3, 2.6), (-2, -5, 2.2), (2, -8, 1.8)], semilla=3)
    if nombre == 'PISGC0':
        px, py = proyectar(PIVOTE_BATERIA + (0.3, 0.6, -0.6), pose)
        bocanada(img, px - x0 + 4, py - y0 - 10, [(0, 0, 2.2), (2, -3, 1.8), (-1, -5, 1.4)], semilla=5, nivel_max=5)
        mx, my = proyectar((0, 0, LARGO + 2.0), pose)
        bocanada(img, mx - x0, my - y0 - 3, [(0, 0, 3.4), (-3, -2, 2.6), (3, -3, 2.8), (0, -6, 2.4), (-2, -8, 1.6)],
                 semilla=9, nivel_max=6)
    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--salida', required=True, help='carpeta de PNG (arte/sprites)')
    ap.add_argument('--muestreo', type=int, default=4, help='rayos por lado de píxel (4 = 16 por píxel)')
    ap.add_argument('--solo', default=None, help='solo este lump (para pruebas)')
    args = ap.parse_args()
    os.makedirs(args.salida, exist_ok=True)
    x0, y0, _, _ = LIENZO
    offsets = {}
    geometria = {}
    for nombre in POSES:
        if args.solo and nombre != args.solo:
            continue
        img = render_fotograma(nombre, args.muestreo)
        offsets[nombre], geometria[nombre] = guardar(img, x0, y0, os.path.join(args.salida, nombre + '.png'))
        print(f'{nombre}: {geometria[nombre][2]}x{geometria[nombre][3]} en pantalla ({geometria[nombre][0]}, '
              f'{geometria[nombre][1]}) offsets {offsets[nombre]}')
    if not args.solo or args.solo == 'PISFA0':
        # fogonazo: centrado un poco por delante de la boca del cañón del fotograma B
        fx, fy = proyectar((0, 0.2, LARGO + 1.6), POSES['PISGB0'])
        f = fogonazo()
        ruta = os.path.join(args.salida, 'PISFA0.png')
        sx, sy = int(round(fx - f.shape[1] / 2)), int(round(fy - f.shape[0] / 2))
        offsets['PISFA0'], g = guardar(f, sx, sy, ruta)
        print(f'PISFA0: {g[2]}x{g[3]} en pantalla ({g[0]}, {g[1]}) offsets {offsets["PISFA0"]}')
    # offsets_pistolon.json (cada pieza escribe el suyo)
    guardar_offsets(args.salida, offsets)


if __name__ == '__main__':
    main()
