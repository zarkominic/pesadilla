#!/usr/bin/env python3
"""organo.py — EL ÓRGANO DE FUEGO (sustituye a la ametralladora de Freedoom), dibujado por código.

Uso:
    ~/.venvs/pesadilla/bin/python tools/arte/organo.py --salida arte/sprites
    (opcional: --vista <png> guarda además las pantallas simuladas de cada estado;
     --solo CHGGA0,MGUNA0 rehace solo esos lumps)

Escribe CHGGA0-B0 (el arma en primera persona), CHGFA0-B0 (los fogonazos, a pleno brillo) y MGUNA0
(el arma tirada en el suelo para recogerla) y sus desplazamientos en <salida>/offsets_organo.json.

En el juego (info.c) la ametralladora va: A en reposo (y al subir y bajar); al disparar A (con el
fogonazo CHGFA0 encima), B (con CHGFB0), y vuelta a A mientras se mantenga el gatillo. Aquí el
órgano dispara por andanadas alternas: en A los cañones impares (1, 3, 5, 7) y en B los pares
(2, 4, 6); en B además el arma ha retrocedido (más cerca, la boca algo levantada) y humean las bocas
de la andanada anterior, así al alternar A y B el arma tiembla y escupe fuego de un lado a otro.

Modelo SDF en centímetros con el motor común arma1p.py (misma proyección, luz, paleta y contorno
que el pistolón, la escopeta y el puño): un cajón de nogal grueso y oscuro (sale por abajo de la
pantalla) con siete cañones cortos de hierro embutidos en fila, de largo escalonado como los tubos
de un órgano (el del centro el más largo), forjados a mano (algo desiguales, con abolladuras,
manchas de óxido y hollín en las bocas); frontal y dos flejes de hierro remachados, canal de cebo y
cantoneras de latón viejo (apagado); y dos asas laterales de nogal con soportes de hierro, como las
de un arcón, agarradas por las dos manos con el guante de cuero (dorso con pespuntes, manopla con
ribete claro) y las mangas de paño granate oscuro, que salen por las esquinas de abajo.
"""
import argparse
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from arma1p import (RAMPAS, Agarre, Arma, _hx, bocanada, caja, capsula, costuras, dibujar,  # noqa: E402
                    elipsoide, filo, guante, guardar, guardar_offsets, llamarada, mano_agarre,
                    matriz_canon, pliegues_pano, proyectar, retroceso, rot_x, rot_y, rot_z, tubo,
                    unit, v3)
from sdf import vnoise  # noqa: E402

MATS = ['hierro', 'oxido', 'hollin', 'herraje', 'laton', 'nogal', 'hueco', 'cuero', 'ribete', 'manga']
RAMPAS_ORG = dict(
    RAMPAS,
    # cañones: hierro colado oscuro y sucio (6, 5, 111, 109, 107, 104, 102, 99, 96, 92); los grises
    # claros solo en el brillo fino de arriba
    hierro=_hx(0x131313, 0x1b1b1b, 0x232323, 0x2f2f2f, 0x3b3b3b, 0x4f4f4f, 0x5b5b5b, 0x6f6f6f, 0x838383,
               0x9f9f9f),
    # óxido: pardo rojizo (2, 239, 238, 237, 167, 166)
    oxido=_hx(0x170f07, 0x2f1b0b, 0x372313, 0x432f1b, 0x5f4323, 0x732b00),
    # hollín de la pólvora (casi negro: 0, 247, 7, 6, 5)
    hollin=_hx(0x000000, 0x070707, 0x0b0b0b, 0x131313, 0x1b1b1b, 0x232323),
    # frontal, flejes y soportes: hierro negro de fragua (7, 6, 5, 111, 109, 107, 104, 102)
    herraje=_hx(0x0b0b0b, 0x131313, 0x1b1b1b, 0x232323, 0x2f2f2f, 0x3b3b3b, 0x4f4f4f, 0x5b5b5b),
    # latón viejo, sin pulir: la parte oscura de la rampa dorada del pistolón (79, 238, 166, 165,
    # 164, 163); sin los amarillos claros
    laton=_hx(0x2b230f, 0x372313, 0x732b00, 0x874307, 0x9b5b13, 0xaf7b1f, 0xc39b2f),
    manga=RAMPAS['pano'],
)
BRILLO = {'hierro': (0.35, 26), 'oxido': (0.04, 6), 'hollin': (0.05, 8), 'herraje': (0.3, 20), 'laton': (0.25, 16),
          'nogal': (0.12, 12), 'hueco': (0.0, 1), 'cuero': (0.12, 10), 'ribete': (0.1, 10), 'manga': (0.0, 1)}
GANANCIA = {'hierro': 0.46, 'oxido': 0.85, 'hollin': 0.7, 'herraje': 0.75, 'laton': 0.52, 'nogal': 0.37,
            'hueco': 0.5, 'cuero': 1.0, 'ribete': 0.66, 'manga': 0.8}

# ---------------------------------------------------------------------------------------------
# El modelo (espacio del arma: origen en el eje del cañón central, en la cara del cajón de la que
# salen los cañones; z hacia las bocas, y arriba, x a la derecha)
# ---------------------------------------------------------------------------------------------

N = 7
PASO = 3.2                        # entre ejes de cañones (en la cara del cajón)
RC, RB, RALMA = 1.38, 1.24, 0.64   # radio del cañón en el cajón, en la boca, y del ánima
ABRE = 4.6                        # grados que se abre cada cañón respecto al de al lado (en abanico)
LARGOS = [23.0 - 2.2 * abs(i - (N - 1) / 2) for i in range(N)]   # hasta dónde llegan: 16,4 … 23 … 16,4
XS = [(i - (N - 1) / 2) * PASO for i in range(N)]
# forjados a mano: cada cañón algo más alto o más bajo y con la boca algo torcida (cm)
DY = [0.10, -0.12, 0.06, 0.0, -0.08, 0.14, -0.05]
TUERCE = [(-0.2, 0.15), (0.15, -0.1), (-0.1, 0.22), (0.0, 0.1), (0.12, -0.15), (-0.08, 0.12), (0.25, -0.05)]
Z_RECAMARA = -6.0                 # culo de los cañones (dentro del cajón)
# el cajón: en planta, un trapecio ancho delante (los cañones) que se estrecha hacia el jugador como
# una culata; alto, y por abajo sale de la pantalla
W_F = XS[-1] + RC + 1.6
W_R = W_F - 1.2                   # medio ancho delante y detrás
Z_ATRAS = -13.0
PEND = (W_F - W_R) / -Z_ATRAS     # cuánto se estrecha por cm hacia atrás
Y_TAPA, Y_SUELO = 1.9, -20.0      # arriba (tapa los cañones) y abajo
FLEJES = (-9.0,)                  # fleje de hierro que abraza el cajón
Z_CEBO = -5.3                     # canal de cebo (latón) sobre las recámaras
Z_ABRAZ = 7.5                     # abrazadera de hierro que ata los cañones
LARGO = LARGOS[N // 2]
IMPARES = [0, 2, 4, 6]            # andanada de A (cañones 1, 3, 5, 7)
PARES = [1, 3, 5]                 # andanada de B

# asas: una vara de nogal a cada costado, paralela al costado, con dos soportes de hierro (como las
# de un arcón); las manos las agarran desde arriba, con el dorso hacia arriba y afuera
ASA_OFF, ASA_Y = 2.7, -1.6
ASA_Z = (2.2, -10.5)              # puntas del asa (soportes)
ASA_R = 1.4
N_LADO = unit(v3(1.0, 0.0, -PEND))   # normal del costado derecho (en planta)


def costado(z, y=0.0, lado=1):
    """Punto del costado del cajón a la altura z (lado +1 derecho, -1 izquierdo)."""
    return v3(lado * (W_F + PEND * z), y, z)


def punto_asa(z, lado=1):
    return costado(z, ASA_Y, lado) + ASA_OFF * N_LADO * v3(lado, 1, 1)


def _eje(i):
    """Eje del cañón i: (recámara, boca, dirección); pasa por (XS[i], DY[i], 0) en la cara del cajón."""
    g = math.radians((i - (N - 1) / 2) * ABRE)
    tx, ty = TUERCE[i]
    u = unit(v3(math.tan(g) + tx * 0.012, ty * 0.012, 1.0))
    p0 = v3(XS[i], DY[i], 0.0)
    a = p0 + u * (Z_RECAMARA / u[2])
    b = p0 + u * (LARGOS[i] / u[2])
    return a, b, u


EJES = [_eje(i) for i in range(N)]


def en_z(i, z):
    """Punto del eje del cañón i a la altura z."""
    a, b, u = EJES[i]
    return a + u * ((z - a[2]) / u[2])


def _abolladuras():
    """Dos abolladuras por cañón, en la parte de arriba (la que se ve), deterministas."""
    rng = np.random.default_rng(41)
    out = []
    for i in range(N):
        a, b, u = EJES[i]
        for _ in range(2):
            z = rng.uniform(1.5, LARGOS[i] - 2.5)
            ang = rng.uniform(-1.1, 1.1)                       # desde arriba, hacia un lado u otro
            t = (z - a[2]) / (b[2] - a[2])
            c = a + t * (b - a)
            r = RC + t * (RB - RC)
            dirn = v3(math.sin(ang), math.cos(ang), 0.0)
            out.append((c + dirn * (r + 0.28), rng.uniform(0.42, 0.55)))
    return out


ABOLL = _abolladuras()


def _marco_mano(lado):
    """Agarre de la mano de un lado (+1 derecha, -1 izquierda) en su asa: el índice delante, el
    meñique hacia atrás; el dorso mira arriba y afuera, los dedos rodean el asa por fuera y abajo."""
    GE = unit(punto_asa(-1.0) - punto_asa(0.0))
    g = unit(0.5 * N_LADO + 0.86 * v3(0, 1, 0))
    g = unit(g - (g @ GE) * GE)
    GF = np.cross(GE, g)
    G0 = punto_asa(-2.2)
    if lado < 0:                       # la izquierda, en espejo
        M = v3(-1, 1, 1)
        g, GF, GE, G0 = g * M, GF * M, GE * M, G0 * M
    return Agarre(G0=G0, GE=GE, GF=GF, GX=g, r=ASA_R)


MANOS = {1: _marco_mano(1), -1: _marco_mano(-1)}
PLIEGUES = (8.0, 15.0, 22.0)


def canones(P, d):
    hierro = np.full(len(P), 1e9)
    hueco = np.full(len(P), 1e9)
    for i in range(N):
        a, b, u = EJES[i]
        c = tubo(P, a, b, RC, RB)
        # brocal: la boca se ensancha como la de un cañón de artillería, con su labio
        boca = np.minimum(tubo(P, b - 2.4 * u, b - 0.5 * u, RB + 0.05, RB + 0.36), tubo(P, b - 0.55 * u, b, RB + 0.42))
        anillo = tubo(P, en_z(i, 0.7), en_z(i, 1.7), RC + 0.22)          # moldura a la salida
        medio = tubo(P, en_z(i, LARGOS[i] * 0.48), en_z(i, LARGOS[i] * 0.48 + 0.7), RC + 0.12)  # astrágalo
        c = np.minimum(np.minimum(c, boca), np.minimum(anillo, medio))
        # la boca hueca: el hierro se vacía y un forro negro hace de fondo del ánima
        c = np.maximum(c, -tubo(P, b - 1.6 * u, b + 1.0 * u, RALMA))
        h = np.maximum(tubo(P, b - 1.7 * u, b + 0.01 * u, RALMA + 0.02), c - 0.05)
        hierro = np.minimum(hierro, c)
        hueco = np.minimum(hueco, h)
    for q, r in ABOLL:                                                   # abolladuras
        hierro = np.maximum(hierro, -(np.linalg.norm(P - q, axis=1) - r))
    return hierro, hueco


def bloque(P, y0, y1, z0, z1, crece=0.0, rr=0.0):
    """Trozo del cajón en planta de trapecio: de y0 a y1 y de z0 a z1, con los costados del cajón
    desplazados 'crece' cm hacia fuera; aristas redondeadas rr."""
    lado = (np.abs(P[:, 0]) - (W_F + crece * math.sqrt(1 + PEND ** 2) + PEND * P[:, 2])) / math.sqrt(1 + PEND ** 2)
    ly = np.abs(P[:, 1] - (y0 + y1) / 2) - (y1 - y0) / 2
    lz = np.abs(P[:, 2] - (z0 + z1) / 2) - (z1 - z0) / 2
    q = np.stack([lado, ly, lz], 1) + rr
    return np.sqrt((np.maximum(q, 0) ** 2).sum(1)) + np.minimum(q.max(1), 0) - rr


def cajon(P, d, y_suelo=Y_SUELO):
    """Cajón de nogal, frontal y flejes de hierro, latón y asas (y_suelo: hasta dónde baja)."""
    nogal = bloque(P, y_suelo, Y_TAPA, Z_ATRAS, 0.0, rr=0.8)
    # hierro: frontal por donde salen los cañones (con un collar por cañón), dos flejes que dan la
    # vuelta al cajón y la abrazadera que ata los cañones en batería, a media caña
    herraje = bloque(P, y_suelo, Y_TAPA + 0.2, -0.4, 0.45, crece=0.2, rr=0.2)
    for i in range(N):
        herraje = np.minimum(herraje, tubo(P, en_z(i, -0.4), en_z(i, 0.55), RC + 0.3))
    for zf in FLEJES:
        herraje = np.minimum(herraje, bloque(P, y_suelo, Y_TAPA + 0.18, zf - 0.55, zf + 0.55, crece=0.18, rr=0.12))
    ab = caja(P, (0.0, -0.15, Z_ABRAZ), (en_z(N - 1, Z_ABRAZ)[0], 0.55, 0.5), 0.2)
    for i in range(N):
        c_ = en_z(i, Z_ABRAZ)
        u_ = EJES[i][2]
        ab = np.minimum(ab, tubo(P, c_ - 0.55 * u_, c_ + 0.55 * u_, RC + 0.22))
    herraje = np.minimum(herraje, ab)
    # asas: vara de nogal con cinchos de hierro en las puntas y dos soportes hasta el costado
    for sx in (-1, 1):
        a, b = punto_asa(ASA_Z[0], sx), punto_asa(ASA_Z[1], sx)
        e = unit(b - a)
        d['nogal'] = np.minimum(d['nogal'], capsula(P, a - 0.6 * e, b + 0.6 * e, ASA_R))
        for z, base in ((ASA_Z[0], 0.3), (ASA_Z[1], ASA_Z[1] + 1.0)):
            p = punto_asa(z, sx)
            herraje = np.minimum(herraje, capsula(P, costado(base, ASA_Y, sx) - 0.3 * N_LADO * v3(sx, 1, 1), p, 0.8))
            herraje = np.minimum(herraje, tubo(P, p - 0.75 * e, p + 0.75 * e, ASA_R + 0.3))
    d['herraje'] = np.minimum(d['herraje'], herraje)
    # latón viejo: canal de cebo sobre las recámaras, cantoneras de las esquinas de atrás y clavos
    xc = en_z(N - 1, Z_CEBO)[0]
    laton = caja(P, (0.0, Y_TAPA + 0.08, Z_CEBO), (xc + 0.7, 0.26, 0.62), 0.16)
    for sx in (-1, 1):
        for z in (-2.2, -6.2, -11.6):                                    # clavos en los costados
            laton = np.minimum(laton, elipsoide(P, costado(z, Y_TAPA - 1.7, sx), (0.45, 0.5, 0.5)))
        for zf in FLEJES:                                                # remaches de los flejes
            laton = np.minimum(laton, elipsoide(P, costado(zf, Y_TAPA + 0.22, sx) - v3(sx * 0.8, 0, 0),
                                                (0.4, 0.32, 0.4)))
    d['nogal'] = np.minimum(d['nogal'], nogal)
    # oídos (agujeros de cebo) sobre cada recámara: se vacía el latón y el fondo del agujero es negro
    oidos = None
    for i in range(N):
        x = en_z(i, Z_CEBO)[0]
        o = elipsoide(P, (x, Y_TAPA + 0.34, Z_CEBO), (0.3, 0.2, 0.3))
        oidos = o if oidos is None else np.minimum(oidos, o)
    d['laton'] = np.minimum(d['laton'], np.maximum(laton, -oidos))
    return np.maximum(laton + 0.08, oidos)


def manchas(P, hierro, herraje):
    """Hollín en las bocas y óxido, solo para los puntos pegados a la superficie (barato)."""
    hollin = np.zeros(len(P), bool)
    oxido = np.zeros(len(P), bool)
    cerca = (hierro < 0.12) | (herraje < 0.12)
    if not cerca.any():
        return hollin, oxido
    Q = P[cerca]
    # cañón más cercano (en abanico: se compara con su eje a la altura de cada punto)
    i = np.argmin(np.stack([np.abs(Q[:, 0] - (XS[k] + EJES[k][2][0] / EJES[k][2][2] * Q[:, 2])) for k in range(N)], 1), 1)
    L = np.asarray(LARGOS)[i]
    n1 = vnoise(Q, 1.3, seed=7)
    # el hollín sube desde la boca 2-4,5 cm, con lenguas irregulares, y más por arriba (el humo)
    arriba = np.clip(Q[:, 1] - np.asarray(DY)[i], 0, None)
    # (el labio de la boca queda limpio: un aro de hierro que se lee como boca, no como una bola negra)
    ho = (Q[:, 2] > L - 0.9 - 3.2 * n1 * n1 - 0.9 * arriba * n1) & (Q[:, 2] < L - 0.6) & (hierro[cerca] < 0.12)
    n2 = vnoise(Q, 0.75, seed=3) * 0.6 + vnoise(Q, 2.3, seed=4) * 0.4
    ox = (n2 > 0.7) & ~ho
    hollin[cerca] = ho
    oxido[cerca] = ox
    return hollin, oxido


# cajas que envuelven cada grupo de piezas: fuera de ellas (más allá de MARGEN) solo se calcula la
# distancia a la caja, que nunca es mayor que la real; así los rayos que no tocan nada salen baratos
MARGEN = 1.5
_EXT = np.array([p for e in EJES for p in e[:2]])
COTA_CAN = ((_EXT.min(0) + _EXT.max(0)) / 2, (_EXT.max(0) - _EXT.min(0)) / 2 + RB + 0.9)
_XC = W_F + ASA_OFF * 1.1 + ASA_R + 1.2
COTA_CAJ = (v3(0.0, (Y_SUELO + Y_TAPA) / 2 + 0.3, (Z_ATRAS + ASA_Z[0]) / 2),
            v3(_XC, (Y_TAPA - Y_SUELO) / 2 + 1.0, (ASA_Z[0] - Z_ATRAS) / 2 + 1.8))


def _parcial(P, cota, fn):
    """Evalúa fn(P_sub, d_sub) solo donde la cota es pequeña → (d, sel, resultado de fn)."""
    sel = cota < MARGEN
    d = {m: np.full(len(P), 1e9) for m in MATS}
    sub = {m: np.full(int(sel.sum()), 1e9) for m in MATS}
    res = fn(P[sel], sub) if sel.any() else None
    for m in MATS:
        d[m][sel] = sub[m]
    return d, sel, res


def modelo(P, pose):
    n = len(P)
    d = {m: np.full(n, 1e9) for m in MATS}
    # cañones
    cota = caja(P, *COTA_CAN)
    dc, sel, res = _parcial(P, cota, lambda Q, sub: canones(Q, sub))
    hierro = cota.copy()
    hueco = np.full(n, 1e9)
    if res is not None:
        hierro[sel], hueco[sel] = res
    # cajón, herrajes, latón y asas
    cota = caja(P, *COTA_CAJ)
    dk, sel, oid = _parcial(P, cota, lambda Q, sub: cajon(Q, sub, pose.get('y_suelo', Y_SUELO)))
    for m in ('nogal', 'herraje', 'laton'):
        d[m] = dk[m]
    d['nogal'] = np.where(sel, d['nogal'], cota)
    if oid is not None:
        hueco[sel] = np.minimum(hueco[sel], oid)
    d['hueco'] = hueco
    hollin, oxido = manchas(P, hierro, d['herraje'])
    d['hollin'] = np.where(hollin, hierro, 1e9)
    d['oxido'] = np.where(oxido, np.minimum(hierro, d['herraje']), 1e9)
    d['hierro'] = np.where(hollin | oxido, 1e9, hierro)
    d['herraje'] = np.where(oxido, 1e9, d['herraje'])
    if pose.get('manos', True):
        for lado in (1, -1):
            A = MANOS[lado]
            br = pose['brazo'][lado]
            w0 = pose['w0'][lado]
            cota = np.minimum(np.linalg.norm(P - (A.G0 + 3.6 * A.GE), axis=1) - 8.0,
                              capsula(P, w0, w0 + 40.0 * br, 6.2))

            def mano(Q, sub, A=A, br=br):
                m, w = mano_agarre(Q, A, br)
                dm = {'cuero': m}
                guante(dm, Q, w, br, largo_manga=40.0)
                for k in ('cuero', 'ribete', 'manga'):
                    sub[k] = dm[k]
            dm, sel, _ = _parcial(P, cota, mano)
            dm['cuero'] = np.where(sel, dm['cuero'], cota)
            for m in ('cuero', 'ribete', 'manga'):
                d[m] = np.minimum(d[m], dm[m])
    D = np.stack([d[m] for m in MATS], 1)
    return D.min(1), D.argmin(1)


def vetas(arma, r, I, fuerza=0.12):
    """Veta del nogal del cajón: fibras a lo largo (z), onduladas, con algún nudo oscuro."""
    sel = r['mat'] == arma.idx('nogal')
    if not sel.any():
        return
    q = r['pl'][sel]
    w = q[:, 0] * 2.6 + 0.5 * np.sin(q[:, 2] * 0.35 + q[:, 0] * 0.4) + 0.5 * np.sin(q[:, 1] * 1.3) + 2.0 * vnoise(q * v3(1, 1, 0.15), 0.9, seed=17)
    v = 0.5 * np.sin(w) + 0.5 * (np.sin(w * 2.3 + 1.3) > 0.6)
    I[sel] += fuerza * v - 0.12 * (vnoise(q, 0.8, seed=13) > 0.68)
    # chamuscado alrededor del canal de cebo (la pólvora del cebo quema la tapa)
    cerca = np.exp(-((q[:, 2] - Z_CEBO) / 1.8) ** 2) * (q[:, 1] > Y_TAPA - 0.3)
    I[sel] -= 0.55 * cerca * vnoise(q, 1.4, seed=19)


def detalle(arma, r, I):
    """Veta y desgaste del nogal, brillo fino a lo largo de los cañones, martillado del hierro,
    pespuntes de los guantes, pliegues y filo de las mangas."""
    # veta del nogal: fibras a lo largo del cajón (hacia los cañones), algo onduladas
    vetas(arma, r, I)
    pose = r.get('pose') or {}
    pl = r['pl']
    # nogal: mugre en manchas y el canto iluminado algo más claro (la silueta del cajón se lee a oscuras)
    filo(arma, r, I, mat='nogal', fuerza=0.3, umbral=0.75)
    sel = r['mat'] == arma.idx('hierro')
    if sel.any() and 'R' in pose:
        # brillo fino a lo largo de cada cañón donde la normal mira a la luz (mirando casi a lo
        # largo de los cañones el especular normal no sale)
        nb = r['n'][sel] @ pose['R']
        Lb = arma.luz @ pose['R']
        Lp = Lb * np.array([1.0, 1.0, 0.0])
        Lp /= np.linalg.norm(Lp)
        c = nb @ Lp
        lado = np.abs(nb[:, 2]) < 0.5
        I[sel] += lado * (0.16 * (c > 0.93) + 0.16 * (c > 0.985))
        # martillado: el hierro forjado no es liso
        I[sel] += 0.12 * (vnoise(pl[sel], 2.6, seed=21) - 0.5)
    for m, k in (('oxido', 0.2), ('herraje', 0.12), ('hollin', 0.25)):
        s = r['mat'] == arma.idx(m)
        if s.any():
            I[s] += k * (vnoise(pl[s], 3.1, seed=23) - 0.5)
    if pose.get('manos', True) and 'brazo' in pose:
        selm = r['mat'] == arma.idx('manga')
        q = pl[selm]
        dist = []
        for lado in (1, -1):
            o, e = pose['w0'][lado], pose['brazo'][lado]
            t = np.maximum((q - o) @ e, 0.0)
            dist.append(np.linalg.norm(q - o - np.outer(t, e), axis=1))
        k = np.argmin(np.stack(dist, 1), 1) if len(q) else np.zeros(0, int)
        for i, lado in enumerate((1, -1)):
            m = np.zeros(selm.shape, bool)
            m[selm] = k == i
            pliegues_pano(arma, r, I, pose['w0'][lado], pose['brazo'][lado], PLIEGUES, sel=m)
            A = MANOS[lado]
            cerca = np.linalg.norm(pl - A.G0, axis=-1) < 9.0
            Ic = I.copy()
            costuras(arma, r, Ic, A)
            I[cerca] = Ic[cerca]
        filo(arma, r, I)


ARMA = Arma(MATS, modelo, BRILLO, GANANCIA, detalle, rampas=RAMPAS_ORG)

# ---------------------------------------------------------------------------------------------
# Poses y fotogramas
# ---------------------------------------------------------------------------------------------

LIENZO = (0, 60, 320, 162)       # x0, y0, ancho, alto (pantalla completa; abajo sale por el borde)
CODOS = {1: v3(40.0, -38.0, 10.0), -1: v3(-40.0, -38.0, 10.0)}   # codos en espacio de cámara (cm)
PIVOTE = v3(0.0, -3.0, -9.0)     # el retroceso gira alrededor de las manos

POSE_A = {'recamara': (160.0, 150.0, 46.0), 'boca': (160.0, 106.0), 'alabeo': 0.0}
POSES = {
    'CHGGA0': POSE_A,
    # retroceso: el arma se viene hacia el jugador y la boca sube un poco
    'CHGGB0': dict(POSE_A, giro=2.5, empuje=(0.0, -0.6, -2.6), humo=IMPARES),
}


def preparar(pose):
    p = dict(pose)
    R, T = matriz_canon(p['recamara'], p['boca'], LARGO, p['alabeo'])
    if 'giro' in p or 'empuje' in p:
        R, T = retroceso(R, T, p.get('giro', 0.0), p.get('empuje', (0, 0, 0)), PIVOTE)
    p['R'], p['T'] = R, T
    p['brazo'], p['w0'] = {}, {}
    for lado in (1, -1):
        _, w0 = mano_agarre(np.zeros((1, 3)), MANOS[lado], v3(0, 0, -1))
        codo = R.T @ (CODOS[lado] - T)
        p['brazo'][lado] = unit(codo - w0)
        p['w0'][lado] = w0
    return p


def bocas(pose, cuales):
    """Posiciones en pantalla (x, y) de las bocas de los cañones 'cuales'."""
    return [proyectar(EJES[i][1] + 0.6 * EJES[i][2], pose['R'], pose['T']) for i in cuales]


def render_fotograma(nombre, S=4):
    pose = preparar(POSES[nombre])
    img = dibujar(ARMA, pose, pose['R'], pose['T'], LIENZO, S, previo=True, t0=8.0, tmax=100.0, pasos=220)
    if pose.get('humo'):
        x0, y0 = LIENZO[:2]
        for j, (bx, by) in enumerate(bocas(pose, pose['humo'])):
            bocanada(img, bx - x0, by - y0 - 3, [(0, 0, 2.2), (1.5, -2.5, 1.8), (-0.5, -4.5, 1.4)],
                     semilla=20 + j, nivel_max=5)
    return img


def fogonazos():
    """CHGFA0 (andanada impar) y CHGFB0 (andanada par), una llama por boca de su fotograma, más un
    resplandor común. → [(lump, img, x0, y0)] en pantalla."""
    out = []
    for lump, nombre, cuales, sem in (('CHGFA0', 'CHGGA0', IMPARES, 31), ('CHGFB0', 'CHGGB0', PARES, 32)):
        pose = preparar(POSES[nombre])
        bs = bocas(pose, cuales)
        xs = [b[0] for b in bs]
        ys = [b[1] for b in bs]
        x0 = int(math.floor(min(xs) - 18))
        y0 = int(math.floor(min(ys) - 32))
        w = int(math.ceil(max(xs) + 18)) - x0
        h = int(math.ceil(max(ys) + 10)) - y0
        focos = [(bx - x0, by - y0 - 5.0, 8.0, 1.35, 0.7 * j) for j, (bx, by) in enumerate(bs)]
        cx = sum(xs) / len(xs) - x0
        cy = sum(ys) / len(ys) - y0
        focos.append((cx, cy - 11.0, 11.0, 0.85, 2.0))
        img = llamarada(w, h, focos, semilla=sem, lenguas=6, chispas=18, potencia=0.9)
        out.append((lump, img, x0, y0))
    return out


def recoger(salida, S=4):
    """MGUNA0: el órgano tirado en el suelo, visto desde arriba y de tres cuartos por delante: el
    cajón de nogal (aquí más bajo: en primera persona baja hasta salir de la pantalla) y los siete
    cañones con las bocas escalonadas como los tubos de un órgano (cámara lejana; tamaño exagerado
    como los objetos de Doom)."""
    pose = {'manos': False, 'y_suelo': -7.5}
    R = rot_x(math.radians(-38)) @ rot_y(math.radians(-128)) @ rot_z(math.radians(0))
    dist = 300.0
    E = 1.85
    c = v3(0.0, -4.0, 0.0) * E
    T = v3(0.0, 0.0, dist) - R @ c
    k = 1.0 / E
    claro = dict(GANANCIA, hierro=0.78, herraje=0.95, nogal=0.8, laton=0.9)
    gordo = Arma(MATS, lambda P, pz: modelo(P * k, pz), BRILLO, claro, detalle, rampas=RAMPAS_ORG)
    img = dibujar(gordo, pose, R, T, (80, 40, 160, 120), S, bordes=False, t0=dist - 100, tmax=dist + 100, pasos=300)
    a = img[..., 3] > 0
    ys, xs = np.nonzero(a)
    img = img[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    from PIL import Image
    Image.fromarray(img, 'RGBA').save(os.path.join(salida, 'MGUNA0.png'))
    h, w = img.shape[:2]
    return [w // 2, h]


def vista(carpeta, salida):
    from PIL import Image, ImageDraw
    from arma1p import simular_pantalla
    estados = [['CHGGA0'], ['CHGGA0', 'CHGFA0'], ['CHGGB0', 'CHGFB0'], ['CHGGB0']]
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
    ruta_off = os.path.join(args.salida, 'offsets_organo.json')
    if solo and os.path.exists(ruta_off):          # con --solo se conservan los demás lumps
        with open(ruta_off) as fh:
            offsets.update(json.load(fh))
    for nombre in POSES:
        if solo and nombre not in solo:
            continue
        img = render_fotograma(nombre, args.muestreo)
        offsets[nombre], g = guardar(img, x0, y0, os.path.join(args.salida, nombre + '.png'))
        print(f'{nombre}: {g[2]}x{g[3]} en pantalla ({g[0]}, {g[1]}) offsets {offsets[nombre]}')
    for nombre, img, fx, fy in fogonazos():
        if solo and nombre not in solo:
            continue
        offsets[nombre], g = guardar(img, fx, fy, os.path.join(args.salida, nombre + '.png'))
        print(f'{nombre}: {g[2]}x{g[3]} en pantalla ({g[0]}, {g[1]}) offsets {offsets[nombre]}')
    if not solo or 'MGUNA0' in solo:
        offsets['MGUNA0'] = recoger(args.salida, args.muestreo)
        print(f'MGUNA0: offsets {offsets["MGUNA0"]}')
    guardar_offsets(args.salida, offsets, pieza='organo')
    if args.vista:
        vista(args.salida, args.vista)


if __name__ == '__main__':
    main()
