#!/usr/bin/env python3
"""farol.py — EL FAROL DE FUEGOS FATUOS (sustituye al rifle de plasma de Freedoom), dibujado por código.

Uso:
    ~/.venvs/pesadilla/bin/python tools/arte/farol.py --salida arte/sprites
    … --solo PLSGA0,PLSSA0        solo esos lumps
    … --vista <png>               además, pantallas simuladas del arma (con barra y sin ella)
    … --hoja <png>                además, hoja de contactos ampliada (bola, salpicadura, PLAS, fogonazos)

Escribe:
- PLSGA0 (reposo; también al subir y bajar, y mientras se dispara) y PLSGB0 (los 20 tics de después
  del último disparo: el farol ha dado un respingo y el fuego fatuo se aviva, y por la boca sale un
  hilo de humo). En el juego (info.c) se dispara en PLSG A (3 tics) y encima va PLSF A o PLSF B al azar.
- PLSFA0 y PLSFB0: el resplandor azul a pleno brillo: el fuego fatuo encendido de golpe dentro del
  cristal y una llamarada azul en la boca de latón (se dibujan encima de PLSGA0, alineados con él).
- PLASA0: el farol tirado en el suelo, para recogerlo.
- PLSSA0-PLSSB0: la bola de fuego fatuo en vuelo (no rota; a pleno brillo) y PLSEA0-PLSEE0, la
  salpicadura que se deshace en chispas azules.
Y los desplazamientos de todos en <salida>/offsets_farol.json (arma1p.guardar_offsets).

El ARMA (motor común arma1p.py: misma proyección, luz, paleta y contorno que las demás): un farol
de sereno de hierro forjado negro, de planta cuadrada, con cuatro cristales sucios (hollín arriba,
mugre a manchas, una raja) protegidos por varillas verticales; tejadillo de pirámide con alero y
la chimenea de latón doblada hacia delante en una boca acampanada (por ahí salen las bolas). Dentro,
atrapado, el fuego fatuo azul (se ve a través del cristal: el cristal se colorea con lo que hay detrás,
llama y resplandor). Lo sostiene un asta corta de nogal que baja del pie del farol como una
empuñadura: la mano derecha enguantada la agarra por debajo y la izquierda sujeta un asa de nogal
del costado izquierdo, con el dorso a la vista (guante de cuero y manga de paño granate, como las
otras armas).

Todo determinista (ruido con semilla fija, sin azar).
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from arma1p import (RAMPAS, Agarre, Arma, _hx, bocanada, caja, capsula, colorear, costuras,  # noqa: E402
                    elipsoide, filo, guante, guardar, guardar_offsets, mano_agarre, mover_pose,
                    pantalla_a_camara, pliegues_pano, proyectar, reducir, rot_x, rot_y, rot_z,
                    smin, trazar, tubo, tubo_z, unit, v3, veta, desplazar)
import sdf  # noqa: E402

PAL = sdf.read_palette(sdf.IWAD)


def _pp(*idx):
    return [tuple(PAL[i]) for i in idx]


# ---------------------------------------------------------------------------------------------
# Paleta del arma: rampas de colores EXACTOS de PLAYPAL (de oscuro a claro)
# ---------------------------------------------------------------------------------------------

# el cristal se pinta con lo que se ve a través: del negro al azul del resplandor y, donde está
# el fuego fatuo, al azul claro y al blanco del núcleo (una sola rampa larga)
VIDRIO = (0, 246, 245, 244, 243, 242, 241, 240, 206, 205, 204, 203, 202, 201, 200, 199, 198, 197,
          196, 195, 194, 193, 192, 4)
N_V = len(VIDRIO)
L_GLOW = 12.6             # el resplandor llega hasta aquí (azul 201)…
L_LLAMA = 17.0            # … y la llama empieza aquí (azul claro 197): el borde de la llama se lee neto
RAMPAS_FAROL = dict(
    RAMPAS,
    # hierro forjado negro (7, 6, 5, 111, 109, 107, 104, 102, 99, 96)
    hierro=_hx(0x0b0b0b, 0x131313, 0x1b1b1b, 0x232323, 0x2f2f2f, 0x3b3b3b, 0x4f4f4f, 0x5b5b5b, 0x6f6f6f,
               0x838383),
    # óxido: pardo rojizo (2, 239, 238, 237, 167, 166)
    oxido=_hx(0x170f07, 0x2f1b0b, 0x372313, 0x432f1b, 0x5f4323, 0x732b00),
    vidrio=_pp(*VIDRIO),
    # reflejo de la luz del cuarto en el cristal (grises claros)
    reflejo=_hx(0x434343, 0x5b5b5b, 0x777777, 0x979797, 0xb7b7b7),
    manga=RAMPAS['pano'],
)
MATS = ['hierro', 'oxido', 'laton', 'nogal', 'vidrio', 'reflejo', 'hueco', 'cuero', 'ribete', 'manga']
BRILLO = {'hierro': (0.3, 20), 'oxido': (0.04, 6), 'laton': (0.6, 22), 'nogal': (0.15, 12),
          'vidrio': (0.0, 1), 'reflejo': (0.0, 1), 'hueco': (0.0, 1), 'cuero': (0.12, 10), 'ribete': (0.1, 10), 'manga': (0.0, 1)}
GANANCIA = {'hierro': 0.62, 'oxido': 0.85, 'laton': 0.85, 'nogal': 0.8, 'vidrio': 1.0, 'reflejo': 1.0, 'hueco': 0.5,
            'cuero': 1.0, 'ribete': 0.66, 'manga': 0.8}

# ---------------------------------------------------------------------------------------------
# El modelo (espacio del arma: origen en el centro del pie de los cristales; y arriba, z hacia
# delante (hacia donde salen las bolas), x a la derecha). Centímetros.
# ---------------------------------------------------------------------------------------------

HW = 6.6                 # medio ancho de los cristales (planta cuadrada)
HG = 11.5                # alto de los cristales
Y_PIE = -2.4             # el pie de hierro baja hasta aquí
Y_TECHO = HG + 0.5       # arranque del tejadillo
Y_CUMBRE = HG + 5.0      # arriba del tejadillo
R_TUBO = 1.15            # radio de la chimenea de latón
Y_CODO = Y_CUMBRE + 0.8  # donde empieza el codo de la chimenea
R_CODO = 2.0             # radio del codo
INCL = 18.0              # el farol se lleva echado hacia atrás estos grados: la chimenea solo se
                         # dobla 90 - INCL y la boca apunta al frente (al centro de la pantalla)
PHI = math.radians(90.0 - INCL)
C_CODO = v3(0.0, Y_CODO, R_CODO)
FIN_CODO = C_CODO + R_CODO * v3(0.0, math.sin(PHI), -math.cos(PHI))
EJE_BOCA = v3(0.0, math.cos(PHI), math.sin(PHI))   # hacia dónde mira la boca (espacio del arma)
L_CUELLO, L_CAMPANA = 1.0, 4.6                     # tramo recto y campana, a lo largo de EJE_BOCA
R_BOCA = 3.0             # radio de la boca
BOCA = FIN_CODO + (L_CUELLO + L_CAMPANA) * EJE_BOCA   # centro de la boca (por ahí salen las bolas)
VARILLAS = (-3.4, 3.4)   # varillas de protección de cada cristal (posición a lo ancho)
# asa del costado izquierdo: un mango corto de nogal que sale hacia la izquierda (y algo hacia
# abajo y atrás), con casquillo de hierro; la mano izquierda lo agarra con el dorso arriba
ASA_DIR = unit(v3(-0.88, -0.3, -0.36))
ASA_0 = v3(-HW - 0.6, 3.8, -0.6)
ASA_L = 9.0
ASA_R = 1.35
# asta: sale del costado derecho (como el brazo de hierro de un farol de carro) hacia atrás y a la
# derecha; la mano derecha la agarra por la empuñadura
ASTA_DIR = unit(v3(0.72, -0.05, -0.69))
ASTA_0 = v3(HW + 0.7, 4.4, -1.4)
ASTA_L = 24.0
ASTA_R = 1.35
ASTA_MANO = 9.5                      # la mano derecha agarra el asta a esta distancia del farol
LLAMA_C = v3(0.0, 4.6, 0.0)          # centro del fuego fatuo


def asta(t):
    return ASTA_0 + ASTA_DIR * t


def marco_izq():
    """Agarre de la mano izquierda en el asa: el índice junto al farol, el dorso arriba y los
    dedos rodeando el mango por delante (como la mano del asa del lanzacohetes)."""
    GE = ASA_DIR
    f = v3(0.0, 0.0, 1.0)
    GF = unit(f - (f @ GE) * GE)
    return Agarre(G0=ASA_0 + 2.4 * GE, GE=GE, GF=GF, GX=np.cross(GE, GF), r=ASA_R + 0.1)


def marco_der():
    """Agarre de la mano derecha en la empuñadura del asta (como la garganta de una culata): el
    dorso arriba y afuera, los dedos rodean el asta por debajo."""
    GE = ASTA_DIR
    g = unit(v3(0.55, 0.83, 0.0))
    GX = unit(g - (g @ GE) * GE)
    GF = np.cross(GE, GX)                      # derecha: GX × GE = -GF
    return Agarre(G0=asta(ASTA_MANO), GE=GE, GF=GF, GX=GX, r=1.75)


MANOS = {-1: marco_izq(), 1: marco_der()}


def piramide(P, y0, y1, a0, a1, rr=0.0):
    """Tronco de pirámide de planta cuadrada: de y0 (medio lado a0) a y1 (medio lado a1)."""
    k = (a1 - a0) / (y1 - y0)
    s = math.sqrt(1 + k * k)
    a = a0 + k * (P[:, 1] - y0)
    dx = (np.abs(P[:, 0]) - a) / s
    dz = (np.abs(P[:, 2]) - a) / s
    dy = np.maximum(y0 - P[:, 1], P[:, 1] - y1)
    return np.maximum(np.maximum(dx, dz), dy) - rr


def codo(P, c, rc, r, phimax=math.pi / 2):
    """Codo de tubo en el plano y-z alrededor de c: sale de (c - rc·z) subiendo y gira phimax
    (un cuarto de vuelta: acaba en c + rc·y, mirando al frente)."""
    q = P - c
    phi = np.clip(np.arctan2(q[:, 1], -q[:, 2]), 0.0, phimax)
    cl = np.stack([np.zeros(len(P)), rc * np.sin(phi), -rc * np.cos(phi)], 1)
    return np.linalg.norm(q - cl, axis=1) - r


def campana(P, o, w, largo, r0, r1, grueso=0.22):
    """Campana de latón hueca de o a o + largo·w (w unitario), de radio r0 a r1 (perfil cóncavo)."""
    q = P - o
    zz = q @ w
    rho = np.linalg.norm(q - np.outer(zz, w), axis=1)
    t = np.clip(zz / largo, 0, 1)
    r = r0 + (r1 - r0) * t ** 2
    pend = 2 * (r1 - r0) / largo
    capa = (np.abs(rho - r) - grueso) / math.sqrt(1 + pend * pend)
    dz = np.maximum(-zz, zz - largo)
    shell = np.maximum(capa, dz)
    labio = np.sqrt((rho - r1) ** 2 + (zz - largo) ** 2) - 0.36
    return np.minimum(shell, labio)


def reflejo(P):
    """Brillo de la luz del cuarto en el cristal de atrás: dos rayas oblicuas (una ancha y una fina)
    pegadas al cristal, arriba a la izquierda."""
    capa = np.abs(P[:, 2] + HW + 0.05) - 0.04
    s = P[:, 0] + 0.6 * P[:, 1]
    banda = np.minimum(np.abs(s - 1.0) - 0.5, np.abs(s - 2.5) - 0.18)
    lim = np.maximum(np.maximum(P[:, 0] + 2.4, -HW + 0.7 - P[:, 0]), np.abs(P[:, 1] - 8.6) - 2.9)
    return np.maximum(np.maximum(capa, banda * 0.85), lim)


def modelo(P, pose):
    d = {m: np.full(len(P), 1e9) for m in MATS}
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    # cristales: una caja maciza (se pinta con lo que se vería detrás)
    d['vidrio'] = caja(P, (0.0, HG / 2, 0.0), (HW, HG / 2 - 0.2, HW), 0.05)
    d['reflejo'] = reflejo(P)
    # armazón: pie, marco de abajo y de arriba, cuatro postes en las esquinas y varillas
    pie = caja(P, (0.0, Y_PIE / 2 - 0.1, 0.0), (HW + 1.0, -Y_PIE / 2 + 0.1, HW + 1.0), 0.35)
    pie = smin(pie, caja(P, (0.0, Y_PIE - 0.35, 0.0), (HW - 0.6, 0.5, HW - 0.6), 0.3), 0.3)
    marco_b = caja(P, (0.0, 0.25, 0.0), (HW + 0.55, 0.5, HW + 0.55), 0.15)
    marco_a = caja(P, (0.0, HG - 0.15, 0.0), (HW + 0.55, 0.55, HW + 0.55), 0.15)
    hierro = np.minimum(np.minimum(pie, marco_b), marco_a)
    for sx in (-1, 1):
        for sz in (-1, 1):
            hierro = np.minimum(hierro, caja(P, (sx * HW, HG / 2, sz * HW), (0.55, HG / 2 + 0.3, 0.55), 0.12))
    for v in VARILLAS:
        for s in (-1, 1):
            hierro = np.minimum(hierro, capsula(P, v3(v, 0.6, s * (HW + 0.45)), v3(v, HG - 0.6, s * (HW + 0.45)), 0.3))
            hierro = np.minimum(hierro, capsula(P, v3(s * (HW + 0.45), 0.6, v), v3(s * (HW + 0.45), HG - 0.6, v), 0.3))
    # tejadillo: alero y pirámide, con un collar arriba
    techo = piramide(P, Y_TECHO, Y_CUMBRE, HW + 1.7, 2.1, 0.1)
    alero = caja(P, (0.0, Y_TECHO + 0.1, 0.0), (HW + 1.75, 0.3, HW + 1.75), 0.12)
    collar = tubo_z(np.stack([x, z, y], 1), Y_CUMBRE - 0.4, Y_CUMBRE + 0.9, 2.0, 1.8)
    hierro = np.minimum(hierro, np.minimum(np.minimum(techo, alero), collar))
    # anilla de colgar detrás del tejadillo
    q = P - v3(0.0, Y_CUMBRE - 0.8, -3.2)
    anilla = np.sqrt((np.sqrt(q[:, 1] ** 2 + q[:, 2] ** 2) - 1.3) ** 2 + q[:, 0] ** 2) - 0.32
    hierro = np.minimum(hierro, anilla)
    # chimenea de latón: sube, se dobla hacia delante y se abre en la campana de la boca
    sube = tubo(P, v3(0.0, Y_CUMBRE, 0.0), v3(0.0, Y_CODO, 0.0), R_TUBO + 0.1, R_TUBO)
    cd = codo(P, C_CODO, R_CODO, R_TUBO, PHI)
    c0 = FIN_CODO + L_CUELLO * EJE_BOCA                  # arranque de la campana
    recto = tubo(P, FIN_CODO, c0 + 0.2 * EJE_BOCA, R_TUBO)
    camp = campana(P, c0, EJE_BOCA, L_CAMPANA, R_TUBO, R_BOCA)
    aro = tubo(P, c0 - 0.4 * EJE_BOCA, c0 + 0.5 * EJE_BOCA, R_TUBO + 0.35)
    d['laton'] = np.minimum(np.minimum(np.minimum(sube, cd), np.minimum(recto, camp)), aro)
    d['hueco'] = tubo(P, c0 + 0.6 * EJE_BOCA, c0 + 1.0 * EJE_BOCA, R_TUBO + 0.3)
    # asa izquierda: mango de nogal con casquillo y pletina de hierro, y un pomo en la punta
    nogal = capsula(P, ASA_0 + 0.8 * ASA_DIR, ASA_0 + ASA_L * ASA_DIR, ASA_R, ASA_R + 0.2)
    nogal = np.minimum(nogal, elipsoide(P, ASA_0 + (ASA_L + 0.6) * ASA_DIR, (1.85, 1.85, 1.85)))
    hierro = np.minimum(hierro, tubo(P, ASA_0 - 0.4 * ASA_DIR, ASA_0 + 1.7 * ASA_DIR, ASA_R + 0.5, ASA_R + 0.3))
    hierro = np.minimum(hierro, caja(P, (-HW - 0.75, 3.8, -0.6), (0.3, 1.9, 1.5), 0.15))
    # asta de nogal: brazo de hierro (dos pletinas desde los postes de la derecha hasta el
    # casquillo), anillo de latón, empuñadura torneada y pomo
    for zz in (HW, -HW):
        hierro = np.minimum(hierro, capsula(P, v3(HW + 0.3, 4.4 + 0.25 * np.sign(zz), zz * 0.75), asta(1.2), 0.5))
    casq = tubo(P, asta(-0.4), asta(3.4), ASTA_R + 0.5, ASTA_R + 0.32)
    hierro = np.minimum(hierro, casq)
    t = np.clip((P - ASTA_0) @ ASTA_DIR, 0, ASTA_L)
    torneado = 0.22 * (np.abs(np.sin((t - 7.5) * 1.25)) < 0.4) * (t > 7.5) * (t < 19.0)
    palo = capsula(P, asta(3.0), asta(ASTA_L), ASTA_R, ASTA_R + 0.25) - torneado
    pomo = elipsoide(P, asta(ASTA_L + 0.5), (2.0, 2.0, 2.0))
    nogal = np.minimum(nogal, np.minimum(palo, pomo))
    d['laton'] = np.minimum(d['laton'], tubo(P, asta(5.6), asta(6.6), ASTA_R + 0.3))
    d['nogal'] = nogal
    # óxido a manchas en el hierro (solo para los puntos pegados a la superficie: el ruido es caro)
    cerca = hierro < 0.12
    if cerca.any():
        Q = P[cerca]
        n2 = sdf.vnoise(Q, 0.8, 3) * 0.6 + sdf.vnoise(Q, 2.3, 4) * 0.4
        ox = n2 > 0.735
        d['oxido'][cerca] = np.where(ox, hierro[cerca], 1e9)
        hierro = hierro.copy()
        hierro[np.nonzero(cerca)[0][ox]] = 1e9
    d['hierro'] = hierro
    if pose.get('manos', True):
        for lado in (-1, 1):
            A = MANOS[lado]
            br = pose['brazo'][lado]
            mi, w0 = mano_agarre(P, A, br)
            dm = {'cuero': mi}
            guante(dm, P, w0, br, largo_manga=40.0)
            for k in ('cuero', 'ribete', 'manga'):
                d[k] = np.minimum(d[k], dm[k])
    D = np.stack([d[k] for k in MATS], 1)
    return D.min(1), D.argmin(1)


# ---------------------------------------------------------------------------------------------
# El fuego fatuo visto a través del cristal
# ---------------------------------------------------------------------------------------------


def fbm2(x, y, escala, semilla):
    """Ruido fractal 2D determinista (como el de las bolas de fuego)."""
    P = np.column_stack([np.ravel(x), np.ravel(y), np.full(np.size(x), 0.37 + semilla)])
    n = (sdf.vnoise(P, escala, semilla) * 0.6 + sdf.vnoise(P, escala * 2.1, semilla + 1) * 0.3
         + sdf.vnoise(P, escala * 4.3, semilla + 2) * 0.1)
    return n.reshape(np.shape(x))


def fuego2d(u, v, fr):
    """Calor del fuego fatuo en el plano de la llama (u a la derecha, v arriba, cm desde su centro):
    > 0 dentro (1 = núcleo blanco). Bola abajo y lenguas que suben, se tuercen y se parten.
    → (calor, distancia normalizada para el resplandor)."""
    tam = fr.get('tam', 1.0)
    fase = fr.get('fase', 0.0)
    sem = fr.get('semilla', 5)
    u = u / tam
    v = v / tam - fr.get('sube', 0.0)
    arriba = np.clip(v, 0, None)
    # las lenguas se mecen (más cuanto más arriba)
    uu = u - (0.5 * np.sin(v * 0.8 + fase) + 0.6 * (fbm2(v * 0.4 - fase, 0.0 * v, 1.0, sem + 3) - 0.5)) * arriba / 3.0
    # distancia anisótropa: la llama es redonda abajo y se alarga hacia arriba
    dist = np.sqrt(uu ** 2 + np.where(v < 0, v * 1.15, v * 0.38) ** 2) / 2.35
    # ruido estirado en vertical: corta la parte de arriba en lenguas (solo resta)
    n = fbm2(uu * 1.5, v * 0.42 - fase * 1.4, 1.0, sem)
    calor = 1.0 - dist - 1.6 * np.clip(n - 0.38, 0, None) * (0.25 + arriba / 2.6)
    # el núcleo blanco solo abajo, en la bola: arriba las lenguas son azul claro
    calor = np.where(calor > 0, calor * (1.0 - 0.45 * np.clip(arriba / 5.0, 0, 1)), calor)
    return calor, dist


def niveles_llama(calor, dist, fr):
    """Calor → nivel (continuo) de la rampa VIDRIO: la llama del azul claro (197) al blanco, con un
    salto neto en el borde; fuera, el resplandor (del negro al azul 201) que cae con la distancia."""
    brillo = fr.get('brillo', 1.0)
    lv_llama = L_LLAMA + np.clip(calor / 0.8, 0, 1) ** 0.8 * (N_V - 0.6 - L_LLAMA)
    glow = brillo * np.exp(-np.maximum(dist - 0.8, 0) * 2.35 / (2.4 * fr.get('alcance', 1.0)))
    lv_glow = 2.0 + np.clip(glow, 0, 1.15) * (L_GLOW - 2.0)
    return np.where(calor > 0, lv_llama, lv_glow)


RAJA = [(1.4, 2.0), (2.6, 3.3), (2.2, 4.4), (3.6, 5.6), (4.1, 7.4)]   # raja del cristal de atrás (x, y)


def ver_cristal(arma, r, I):
    """Pinta los sub-píxeles del cristal con lo que hay detrás: el fuego fatuo (dibujado en el plano
    de la llama, mirando a la cámara: núcleo blanco, lenguas azul claro, borde azul), su resplandor
    (más claro cerca de la llama), el hollín de arriba, la mugre a manchas y una raja."""
    sel = r['mat'] == arma.idx('vidrio')
    if not sel.any():
        return
    pose = r['pose']
    fr = pose.get('llama', {})
    P = r['pl'][sel]
    D = r['dir'][sel] @ pose['R']              # dirección del rayo en espacio del arma
    C = LLAMA_C
    n = unit(C - pose['cam'])
    t = ((C - P) @ n) / (D @ n)
    Q = P + D * t[:, None] - C
    arriba = pose['arriba']
    ey = unit(arriba - (arriba @ n) * n)
    ex = np.cross(ey, n)
    calor, dist = fuego2d(Q @ ex, Q @ ey, fr)
    llama = calor > 0
    lv = niveles_llama(calor, dist, fr)
    # mugre y hollín (en la superficie del cristal): oscurecen el resplandor; la llama, menos
    yrel = P[:, 1] / HG
    hollin = np.clip((yrel - 0.6) / 0.3, 0, 1) * (0.6 + 0.8 * sdf.vnoise(P * v3(1.0, 0.4, 1.0), 1.1, 31))
    mugre = sdf.vnoise(P, 0.75, 33) * 0.65 + sdf.vnoise(P, 2.0, 34) * 0.35
    manchas = np.clip((mugre - 0.5) / 0.2, 0, 1)
    lv = lv - np.where(llama, 2.0, 6.0) * hollin - np.where(llama, 1.0, 4.0) * manchas
    # raja en el cristal de atrás: línea oscura con el canto claro al lado
    atras = P[:, 2] < -HW + 0.3
    dr = np.full(len(P), 1e9)
    for (ax, ay), (bx, by) in zip(RAJA[:-1], RAJA[1:]):
        a, b = np.array([ax, ay]), np.array([bx, by])
        q = P[:, :2] - a
        h = np.clip(q @ (b - a) / ((b - a) @ (b - a)), 0, 1)
        dr = np.minimum(dr, np.linalg.norm(q - h[:, None] * (b - a), axis=1))
    lv = np.where(atras & (dr < 0.13), 1.0, lv)
    lv = np.where(atras & (dr >= 0.13) & (dr < 0.3) & ~llama, lv + 3.0, lv)
    I[sel] = (np.clip(lv, 1, N_V - 1) - 0.35 + 0.01) / (N_V - 1)


def detalle(arma, r, I):
    pose = r.get('pose') or {}
    pl = r['pl']
    veta(arma, r, I)
    sel = r['mat'] == arma.idx('hierro')
    if sel.any():
        I[sel] += 0.14 * (sdf.vnoise(pl[sel], 2.4, 21) - 0.5)
    filo(arma, r, I, mat='hierro', fuerza=0.25, umbral=0.75)
    filo(arma, r, I, mat='nogal', fuerza=0.2, umbral=0.75)
    if pose.get('manos', True) and 'brazo' in pose:
        selm = r['mat'] == arma.idx('manga')
        q = pl[selm]
        dist = []
        for lado in (-1, 1):
            o, e = pose['w0'][lado], pose['brazo'][lado]
            t = np.maximum((q - o) @ e, 0.0)
            dist.append(np.linalg.norm(q - o - np.outer(t, e), axis=1))
        k = np.argmin(np.stack(dist, 1), 1) if len(q) else np.zeros(0, int)
        for i, lado in enumerate((-1, 1)):
            m = np.zeros(selm.shape, bool)
            m[selm] = k == i
            pliegues_pano(arma, r, I, pose['w0'][lado], pose['brazo'][lado], (8.0, 15.0, 22.0), sel=m)
            A = MANOS[lado]
            cerca = np.linalg.norm(pl - A.G0, axis=-1) < 9.0
            Ic = I.copy()
            costuras(arma, r, Ic, A)
            I[cerca] = Ic[cerca]
        filo(arma, r, I)
    ver_cristal(arma, r, I)
    sel = r['mat'] == arma.idx('reflejo')
    I[sel] = 0.62 + 0.25 * (sdf.vnoise(pl[sel], 1.5, 41) - 0.5)


ARMA = Arma(MATS, modelo, BRILLO, GANANCIA, detalle, rampas=RAMPAS_FAROL)

# ---------------------------------------------------------------------------------------------
# Poses y fotogramas
# ---------------------------------------------------------------------------------------------

LIENZO = (-22, 70, 364, 152)     # x0, y0, ancho, alto: sobra por los lados y por abajo (balanceo de ±16 px)
CODOS = {1: v3(40.0, -36.0, 6.0), -1: v3(-42.0, -32.0, 14.0)}   # codos en espacio de cámara (cm)
POSE_A = {'pie': (162.0, 182.0, 40.0), 'cabeceo': INCL, 'guinada': 0.0, 'alabeo': -2.0,
          'llama': {'tam': 1.0, 'semilla': 5, 'fase': 0.0, 'brillo': 1.0}}
POSES = {
    'PLSGA0': POSE_A,
    'PLSGB0': dict(POSE_A, pie=(162.0, 184.0, 38.5), cabeceo=INCL + 3.0,
                   llama={'tam': 1.22, 'semilla': 9, 'fase': 1.7, 'brillo': 1.15, 'alcance': 1.3, 'sube': 0.6}),
}


def preparar(pose):
    p = dict(pose)
    R = rot_z(math.radians(p['alabeo'])) @ rot_y(math.radians(p['guinada'])) @ rot_x(math.radians(p['cabeceo']))
    x, y, Z = p['pie']
    T = pantalla_a_camara(x, y, Z)
    p['R'], p['T'] = R, T
    p['cam'] = -R.T @ T                         # la cámara en espacio del arma
    p['arriba'] = R.T @ v3(0.0, 1.0, 0.0)       # «arriba» del mundo en espacio del arma (la llama sube)
    p['brazo'], p['w0'] = {}, {}
    for lado in (-1, 1):
        _, w0 = mano_agarre(np.zeros((1, 3)), MANOS[lado], v3(0, 0, -1))
        codo_ = R.T @ (CODOS[lado] - T)
        p['brazo'][lado] = unit(codo_ - w0)
        p['w0'][lado] = w0
    return p


def dibujar_mat(arma, pose, lienzo, S=4, previo=True, bordes=True, **kw):
    """Como arma1p.dibujar, pero devuelve también el material de cada píxel (-1 = vacío)."""
    R, T = pose['R'], pose['T']
    x0, y0, w, h = lienzo
    if previo:
        r0 = trazar(arma, pose, R, T, x0, y0, w, h, 2, **kw)
        m = r0['hit'].reshape(h, 2, w, 2).any(axis=(1, 3))
        for _ in range(2):
            m = m | desplazar(m, 1, 0, False) | desplazar(m, -1, 0, False) | desplazar(m, 0, 1, False) | desplazar(m, 0, -1, False)
        kw['mascara'] = m
    r = trazar(arma, pose, R, T, x0, y0, w, h, S, **kw)
    alfa, m, I, z = reducir(arma, r, S)
    return colorear(arma, alfa, m, I, z, bordes=bordes), m


# fuego fatuo de cada fotograma (PLSF: encendido de golpe, llena el cristal de luz)
LLAMA_FLASH = {'A': {'tam': 1.5, 'semilla': 12, 'fase': 3.1, 'brillo': 1.6, 'alcance': 2.4, 'sube': 0.2},
               'B': {'tam': 1.42, 'semilla': 17, 'fase': 4.6, 'brillo': 1.5, 'alcance': 2.2, 'sube': 0.35}}
LIENZO_CRISTAL = (112, 112, 104, 80)      # el trozo de pantalla donde cae el cristal (para PLSF)


def render_fotograma(nombre, S=4):
    pose = preparar(POSES[nombre])
    img, _ = dibujar_mat(ARMA, pose, LIENZO, S, t0=8.0, tmax=120.0, pasos=220)
    if nombre == 'PLSGB0':
        # un hilo de humo sale por la boca tras el último disparo
        x0, y0 = LIENZO[:2]
        bx, by = proyectar(BOCA + 0.8 * EJE_BOCA, pose['R'], pose['T'])
        bocanada(img, bx - x0, by - y0 - 3, [(0, 0, 3.9), (2.6, -4.2, 3.3), (1.0, -8.2, 2.9), (3.6, -11.4, 2.3),
                                              (2.2, -14.4, 1.7)], semilla=27, nivel_max=5)
    return img


def boca_pantalla(pose_base=None):
    pose = preparar(pose_base or POSE_A)
    return proyectar(BOCA + 0.5 * EJE_BOCA, pose['R'], pose['T'])


# ---------------------------------------------------------------------------------------------
# Efectos 2D a pleno brillo: fuego azul y chispas (deterministas)
# ---------------------------------------------------------------------------------------------

SS2 = 4                                                                    # submuestras por píxel y eje
# fuego fatuo: del blanco al azul oscuro (colores exactos de PLAYPAL)
AZUL = np.array(_pp(4, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206), np.uint8)
CHISPA = np.array(_pp(4, 192, 194, 196, 198, 200, 202, 204, 206, 241), np.uint8)   # cabeza → cola


def malla(W, H, cx, cy):
    """Coordenadas de las submuestras (x a la derecha, y hacia ARRIBA) respecto a (cx, cy)."""
    jj, ii = np.meshgrid(np.arange(W * SS2), np.arange(H * SS2))
    return (jj + 0.5) / SS2 - cx, cy - (ii + 0.5) / SS2


def pintar_azul(img, calor, potencia=1.0, minimo=6, solo_vacio=False):
    """Calor (submuestras, 0..1+) → píxeles de la rampa AZUL (1 = blanco; 0 = azul oscuro)."""
    H, W = img.shape[:2]
    on = calor > 0.0
    cnt = on.reshape(H, SS2, W, SS2).sum(axis=(1, 3))
    suma = np.where(on, calor, 0).reshape(H, SS2, W, SS2).sum(axis=(1, 3))
    hm = suma / np.maximum(cnt, 1)
    vis = cnt >= minimo
    if solo_vacio:
        vis &= img[..., 3] == 0
    n = len(AZUL)
    idx = np.clip(((1.0 - np.clip(hm, 0, 1)) ** potencia) * (n - 1) + 0.3, 0, n - 1).astype(int)
    img[vis, :3] = AZUL[idx[vis]]
    img[vis, 3] = 255
    return vis


def chispa(img, x, y, dx, dy, largo, nivel=0, encima=False):
    """Chispa azul con estela: cabeza en (x, y) (píxeles, y hacia abajo), estela hacia (-dx, -dy)."""
    H, W = img.shape[:2]
    n = max(int(round(largo)), 1)
    L = math.hypot(dx, dy) or 1.0
    ux, uy = dx / L, dy / L
    vistos = set()
    for k in range(n + 1):
        px, py = int(math.floor(x - ux * k)), int(math.floor(y - uy * k))
        if (px, py) in vistos or not (0 <= px < W and 0 <= py < H):
            continue
        vistos.add((px, py))
        c = min(nivel + (k * (len(CHISPA) - 2)) // max(n, 1), len(CHISPA) - 1)
        if img[py, px, 3] and not encima:
            continue
        img[py, px, :3] = CHISPA[c]
        img[py, px, 3] = 255


def chispas(img, cx, cy, n, r0, r1, largo, semilla, nivel=0, sube=0.0, abre=math.pi, dir_=-math.pi / 2, aplasta=1.0):
    """n chispas alrededor de (cx, cy) (y hacia abajo) entre los radios r0 y r1, con estela radial;
    sube: cuánto se tuercen hacia arriba (el fuego fatuo flota)."""
    rng = np.random.default_rng(semilla)
    for _ in range(n):
        a = dir_ + rng.uniform(-abre, abre)
        r = rng.uniform(r0, r1)
        hx, hy = cx + math.cos(a) * r, cy + math.sin(a) * r * aplasta
        dx, dy = math.cos(a), math.sin(a) * aplasta - sube * r / max(r1, 1)
        chispa(img, hx, hy, dx, dy, rng.uniform(*largo), nivel + int(rng.integers(0, 2)))


def anclas(img):
    """Píxeles invisibles en las esquinas de abajo: construir_pwad no recorta (ni mueve) el lienzo."""
    H, W = img.shape[:2]
    for x in (0, W - 1):
        if img[H - 1, x, 3] == 0:
            img[H - 1, x] = (0, 0, 0, 1)
    return img


# ---------------------------------------------------------------------------------------------
# PLSF: el resplandor del disparo (encima de PLSGA0, a pleno brillo)
# ---------------------------------------------------------------------------------------------


def estallido(img, cx, cy, fr):
    """Llamarada azul en la boca de latón: núcleo blanco, lenguas que se abren y chispas que salen
    hacia el centro de la pantalla (por donde se va la bola)."""
    H, W = img.shape[:2]
    R0, sem, rug, ay = {'A': (10.5, 51, 0.5, 1.0), 'B': (11.5, 52, 0.7, 0.92)}[fr]
    ex, ey = cx, cy - 2.5                         # algo adelantada (hacia el centro: arriba)
    x, y = malla(W, H, ex, ey)
    r = np.hypot(x, y / ay)
    th = np.arctan2(y, x)
    lob = fbm2(np.cos(th) * 2.4, np.sin(th) * 2.4, 1.0, sem)
    R = R0 * (0.62 + 0.75 * lob)
    calor = 1.25 - r / R + rug * (fbm2(x, y, 0.38, sem + 5) - 0.5)
    pintar_azul(img, calor, potencia=0.9)
    chispas(img, ex, ey, 16, R0 * 0.9, R0 * 1.7, (2, 5), sem + 9, nivel=1, sube=0.4)


def fogonazo(fr, S=4):
    """→ (img, x0, y0) de PLSF{fr}: el cristal del farol con el fuego fatuo encendido de golpe (solo
    los píxeles del cristal: las varillas y el marco de PLSGA0 se ven por los huecos, a contraluz) y
    la llamarada de la boca."""
    pose = preparar(dict(POSE_A, llama=LLAMA_FLASH[fr]))
    x0, y0, w, h = LIENZO_CRISTAL
    lamp, m = dibujar_mat(ARMA, pose, LIENZO_CRISTAL, S, t0=8.0, tmax=120.0, pasos=220)
    # el lienzo del fogonazo abarca el cristal y la boca
    bx, by = proyectar(BOCA + 0.5 * EJE_BOCA, pose['R'], pose['T'])
    X0, Y0 = min(x0, int(bx) - 28), min(y0, int(by) - 32)
    X1, Y1 = max(x0 + w, int(bx) + 28), max(y0 + h, int(by) + 26)
    img = np.zeros((Y1 - Y0, X1 - X0, 4), np.uint8)
    sel = m == ARMA.idx('vidrio')
    sub = img[y0 - Y0:y0 - Y0 + h, x0 - X0:x0 - X0 + w]
    sub[sel] = lamp[sel]
    estallido(img, bx - X0, by - Y0, fr)
    return img, X0, Y0


# ---------------------------------------------------------------------------------------------
# PLAS: el farol en el suelo (de lado, cámara lejana)
# ---------------------------------------------------------------------------------------------


def recoger(S=4, guinada=-38.0, cabeceo=-22.0, llama=None, dist=188.0):
    """PLASA0: el farol de pie en el suelo, ladeado y apoyado en el extremo del asta, visto de tres
    cuartos y algo desde arriba; un poco más grande que de verdad, como los objetos de Doom.
    → (img, offsets)."""
    # ladeado (sobre z) hasta que el pomo del asta toca el suelo
    fin = asta(ASTA_L + 2.0)
    base = v3(-HW - 1.0, Y_PIE, 0.0)
    g = math.atan2(fin[1] - Y_PIE, fin[0] - base[0])
    Rl = rot_z(-g)
    R = rot_x(math.radians(cabeceo)) @ rot_y(math.radians(guinada)) @ Rl
    c = v3(4.0, 8.0, 0.0)
    T = v3(0.0, 0.0, dist) - R @ c
    pose = {'manos': False, 'R': R, 'T': T, 'cam': -R.T @ T, 'arriba': R.T @ v3(0.0, 1.0, 0.0),
            'llama': llama or {'tam': 1.5, 'semilla': 5, 'fase': 0.6, 'brillo': 1.8, 'alcance': 2.6}}
    claro = dict(GANANCIA, hierro=0.85, nogal=0.95, laton=0.95)
    arma = Arma(MATS, modelo, BRILLO, claro, detalle, rampas=RAMPAS_FAROL)
    img, _ = dibujar_mat(arma, pose, (110, 60, 100, 80), S, bordes=False, t0=dist - 60, tmax=dist + 60, pasos=260)
    a = img[..., 3] > 0
    ys, xs = np.nonzero(a)
    img = img[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = img.shape[:2]
    return img, [w // 2, h]


# ---------------------------------------------------------------------------------------------
# PLSS: la bola de fuego fatuo en vuelo; PLSE: la salpicadura (2D, a pleno brillo, no rotan)
# ---------------------------------------------------------------------------------------------

# lienzo (ancho, alto), centro de la bola (x, y desde arriba) y cuánto queda el centro por encima del
# origen del objeto (como las de Freedoom: la bola en medio de sus 8 unidades de alto; la salpicadura
# sube mientras se deshace)
LIENZO_BOLA = {'A': (22, 25, 11.0, 15.5, 4), 'B': (22, 25, 11.0, 15.5, 4)}
LIENZO_SALP = {'A': (26, 26, 13.0, 13.5, 4), 'B': (32, 32, 16.0, 16.5, 5), 'C': (38, 38, 19.0, 20.0, 8),
               'D': (42, 42, 21.0, 22.0, 11), 'E': (42, 42, 21.0, 22.0, 15)}


def bola(fr):
    """La bola: núcleo blanco, cuerpo azul claro y una cola de lenguas azules que sube y se mece."""
    W, H, cx, cy, alto = LIENZO_BOLA[fr]
    img = np.zeros((H, W, 4), np.uint8)
    x, y = malla(W, H, cx, cy)
    sem, fase = {'A': (61, 0.0), 'B': (62, 2.4)}[fr]
    arriba = np.clip(y, 0, None)
    xx = x - 1.3 * np.sin(y * 0.45 + fase) * arriba / 8.0
    dist = np.sqrt(xx ** 2 + np.where(y < 0, y, y * 0.5) ** 2) / 5.6
    n = fbm2(xx * 0.5, y * 0.28 - fase, 1.0, sem)
    calor = 1.1 - dist - 1.5 * np.clip(n - 0.4, 0, None) * (0.15 + arriba / 7.0)
    calor = np.where(calor > 0, calor * (1.0 - 0.5 * np.clip(arriba / 9.0, 0, 1)), calor)
    pintar_azul(img, calor, potencia=1.1)
    # un halo de chispas sueltas alrededor
    chispas(img, cx, cy, 5, 7.0, 9.0, (1, 2), sem + 3, nivel=2, sube=0.5)
    return anclas(img), (int(round(cx)), int(round(cy + alto)))


def jirones(x, y, n, radios, tam, sube, pico, semilla):
    """n lenguas de fuego fatuo sueltas (en submuestras x, y; y arriba) repartidas alrededor del
    centro entre los radios dados, desplazadas 'sube' hacia arriba: cada una, una lágrima con la
    punta arriba mordida por el ruido. → calor (máximo de todas)."""
    rng = np.random.default_rng(semilla)
    calor = np.full(x.shape, -1.0)
    for k in range(n):
        a = (k + rng.uniform(-0.45, 0.45)) * 2 * math.pi / n
        r = rng.uniform(*radios)
        jx, jy = math.cos(a) * r, math.sin(a) * r * 0.85 + sube
        s_ = tam * rng.uniform(0.75, 1.25)
        dx, dy = x - jx, y - jy
        dx = dx - 0.5 * np.sin(dy * 0.6 + k) * np.clip(dy, 0, None) / s_
        dist = np.sqrt(dx ** 2 + np.where(dy < 0, dy * 1.3, dy * 0.42) ** 2) / s_
        c = pico * (1.0 - dist) - 0.35 * np.clip(fbm2(dx * 0.6, dy * 0.4, 1.0, semilla + k) - 0.45, 0, None)
        calor = np.maximum(calor, c)
    return calor


def salpicadura(fr):
    """A: fogonazo blanco del impacto; B: se abre en lenguas; C: anillo roto con chispas; D: jirones
    y chispas que suben; E: las últimas pavesas azules."""
    W, H, cx, cy, alto = LIENZO_SALP[fr]
    img = np.zeros((H, W, 4), np.uint8)
    x, y = malla(W, H, cx, cy)
    r = np.hypot(x, y)
    th = np.arctan2(y, x)
    sem = {'A': 71, 'B': 72, 'C': 73, 'D': 74, 'E': 75}[fr]
    lob = fbm2(np.cos(th) * 2.8, np.sin(th) * 2.8, 1.0, sem)
    ruido = fbm2(x, y, 0.3, sem + 3)
    if fr == 'A':
        R = 8.0 * (0.72 + 0.55 * lob)
        calor = 1.3 - r / R + 0.35 * (ruido - 0.5)
        pintar_azul(img, calor, potencia=0.8)
        chispas(img, cx, cy, 8, 8.5, 11.0, (2, 3), sem, nivel=0, sube=0.2)
    elif fr == 'B':
        R = 11.0 * (0.66 + 0.6 * lob)
        calor = 1.05 - r / R + 0.55 * (ruido - 0.5)
        pintar_azul(img, calor, potencia=1.05)
        chispas(img, cx, cy, 14, 11.0, 15.0, (2, 4), sem, nivel=1, sube=0.4)
    elif fr == 'C':
        # la llamarada se abre y se rompe en lenguas que suben (nada de un aro limpio)
        rc = 10.5 * (0.6 + 0.8 * lob)
        anillo = np.exp(-((r - rc) / (2.6 + 1.6 * ruido)) ** 2) * (1.0 + 0.3 * np.clip(y / 10.0, -1, 1))
        dentro = 0.45 * np.clip(1.0 - r / rc, 0, 1) * (fbm2(x, y, 0.3, sem + 4) > 0.5)
        calor = 0.95 * np.maximum(anillo * (0.45 + 0.9 * ruido), dentro) - 0.25
        hueco = fbm2(np.cos(th) * 3.2, np.sin(th) * 3.2, 1.0, sem + 11) > 0.6
        calor -= 0.7 * hueco + 0.5 * (fbm2(x, y, 0.2, sem + 7) > 0.62)
        pintar_azul(img, calor, potencia=1.25)
        chispas(img, cx, cy, 18, 13.0, 18.0, (2, 5), sem, nivel=2, sube=0.7)
    elif fr == 'D':
        # la llamarada se deshace en jirones: lenguas sueltas que suben, ya azules, y chispas
        calor = jirones(x, y, 7, (6.0, 15.0), 2.6, 2.0, 0.62, sem)
        pintar_azul(img, calor, potencia=1.5)
        chispas(img, cx, cy - 3, 14, 12.0, 19.0, (2, 4), sem, nivel=3, sube=1.1)
    else:
        # las últimas pavesas: jirones pequeños y oscuros, más arriba
        calor = jirones(x, y, 5, (9.0, 16.0), 1.9, 5.0, 0.4, sem)
        pintar_azul(img, calor, potencia=1.8)
        chispas(img, cx, cy - 6, 10, 10.0, 18.0, (1, 3), sem, nivel=5, sube=1.4, abre=2.2)
    return anclas(img), (int(round(cx)), int(round(cy + alto)))


# ---------------------------------------------------------------------------------------------
# Trabajos, hoja de contactos y vista
# ---------------------------------------------------------------------------------------------

PESADOS = ['PLSGA0', 'PLSGB0', 'PLSFA0', 'PLSFB0', 'PLASA0']


def _trabajo(arg):
    """Un lump pesado (raymarching): → (nombre, img, (x0, y0) del lienzo o None, offsets o None)."""
    nombre, S = arg
    if nombre in POSES:
        return nombre, render_fotograma(nombre, S), LIENZO[:2], None
    if nombre.startswith('PLSF'):
        img, x0, y0 = fogonazo(nombre[4], S)
        return nombre, img, (x0, y0), None
    img, off = recoger(S)
    return nombre, img, None, off


def leer_mios(carpeta):
    ruta = os.path.join(carpeta, 'offsets_farol.json')
    if os.path.exists(ruta):
        with open(ruta) as fh:
            return json.load(fh)
    return {}


def hoja(carpeta, ruta):
    """Hoja de contactos ampliada: bola y salpicadura (x8), PLAS y los fogonazos (x4); la cruz roja
    marca el origen del objeto."""
    off = leer_mios(carpeta)
    filas = [['PLSSA0', 'PLSSB0', 'PLSEA0', 'PLSEB0', 'PLSEC0', 'PLSED0', 'PLSEE0'], ['PLASA0', 'PLSFA0', 'PLSFB0']]
    escalas = [7, 4]
    ims = {n: Image.open(os.path.join(carpeta, n + '.png')).convert('RGBA') for f in filas for n in f
           if os.path.exists(os.path.join(carpeta, n + '.png'))}
    anchos = [max(ims[n].width for n in f if n in ims) * e + 16 for f, e in zip(filas, escalas)]
    altos = [max(ims[n].height for n in f if n in ims) * e + 40 for f, e in zip(filas, escalas)]
    S = Image.new('RGBA', (max(a * len(f) for a, f in zip(anchos, filas)), sum(altos)), (40, 40, 46, 255))
    d = ImageDraw.Draw(S)
    y = 0
    for f, hf, cw, escala in zip(filas, altos, anchos, escalas):
        for c, n in enumerate(f):
            if n not in ims:
                continue
            im = ims[n]
            big = im.resize((im.width * escala, im.height * escala), Image.NEAREST)
            x = c * cw + 8
            S.alpha_composite(big, (x, y + 20))
            d.text((x, y + 4), f'{n} {im.width}x{im.height} {off.get(n)}', fill=(240, 240, 240))
            if n in off and off[n][0] >= 0:
                ox, oy = x + off[n][0] * escala, y + 20 + off[n][1] * escala
                d.line([(ox - 6, oy), (ox + 6, oy)], fill=(255, 40, 40))
                d.line([(ox, oy - 6), (ox, oy + 6)], fill=(255, 40, 40))
        y += hf
    S.save(ruta)


def vista(carpeta, salida, estados=None):
    from arma1p import simular_pantalla
    estados = estados or [['PLSGA0'], ['PLSGA0', 'PLSFA0'], ['PLSGA0', 'PLSFB0'], ['PLSGB0']]
    W = Image.new('RGBA', (330 * len(estados), 210 * 2 + 20), (20, 20, 20, 255))
    for c, capas in enumerate(estados):
        for r, barra in enumerate((True, False)):
            W.paste(simular_pantalla(carpeta, capas, barra), (330 * c, 210 * r + 20))
        ImageDraw.Draw(W).text((330 * c + 4, 4), '+'.join(capas), fill=(230, 230, 230, 255))
    W = W.resize((W.width * 2, int(W.height * 1.2) * 2), Image.NEAREST)
    W.save(salida)


def main():
    from concurrent.futures import ProcessPoolExecutor
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--salida', required=True, help='carpeta de PNG (arte/sprites)')
    ap.add_argument('--muestreo', type=int, default=4, help='rayos por lado de píxel del arma (4 = 16)')
    ap.add_argument('--solo', default=None, help='solo estos lumps (separados por comas)')
    ap.add_argument('--vista', default=None, help='PNG con las pantallas simuladas del arma')
    ap.add_argument('--hoja', default=None, help='PNG con la hoja de contactos')
    args = ap.parse_args()
    os.makedirs(args.salida, exist_ok=True)
    solo = [s.strip().upper() for s in args.solo.split(',')] if args.solo else None
    offsets = leer_mios(args.salida)
    pesados = [n for n in PESADOS if not solo or n in solo]
    trabajos = [(n, args.muestreo) for n in pesados]
    if len(trabajos) > 1:
        with ProcessPoolExecutor(max_workers=min(len(trabajos), os.cpu_count() or 1)) as ex:
            hechos = list(ex.map(_trabajo, trabajos))
    else:
        hechos = [_trabajo(t) for t in trabajos]
    for nombre, img, origen, off in hechos:
        ruta = os.path.join(args.salida, nombre + '.png')
        if origen is not None:
            offsets[nombre], g = guardar(img, origen[0], origen[1], ruta)
            print(f'{nombre}: {g[2]}x{g[3]} en pantalla ({g[0]}, {g[1]}) offsets {offsets[nombre]}', flush=True)
        else:
            Image.fromarray(img, 'RGBA').save(ruta)
            offsets[nombre] = off
            print(f'{nombre}: {img.shape[1]}x{img.shape[0]} offsets {off}', flush=True)
    ligeros = [(f'PLSS{f}0', bola, f) for f in 'AB'] + [(f'PLSE{f}0', salpicadura, f) for f in 'ABCDE']
    for nombre, fn, fr in ligeros:
        if solo and nombre not in solo:
            continue
        img, offsets[nombre] = fn(fr)
        Image.fromarray(img, 'RGBA').save(os.path.join(args.salida, nombre + '.png'))
        print(f'{nombre}: {img.shape[1]}x{img.shape[0]} offsets {offsets[nombre]}', flush=True)
    guardar_offsets(args.salida, offsets, 'farol')
    if args.vista:
        vista(args.salida, args.vista)
    if args.hoja:
        hoja(args.salida, args.hoja)


if __name__ == '__main__':
    main()
