#!/usr/bin/env python3
"""salud.py — SALUD Y ARMADURA de PESADILLA (objetos que se recogen), dibujados por código.

Sustituyen a los de Freedoom con los mismos estados de info.c (los objetos no rotan: lumps X?0):

- STIMA0  botiquín pequeño → tarro de ungüento de botica: loza blanca con franjas rojas pintadas,
          tapa de corcho atada con bramante y sello de lacre rojo.
- MEDIA0  botiquín grande → maletín de médico del curandero, de boca en arco y asa alta, forrado de
          lienzo blanco con el culo, las cantoneras, las dos correas y el asa de cuero rojo, cierre y
          hebillas de latón y una hoja verde grande pintada delante (el distintivo del herbolario: nada
          de cruces). Blanco y rojo como el tarro, para que no se confunda con las cajas de munición.
- BON1A0-D0 (+1 salud; el juego hace A-B-C-D-C-B) → frasquito de cristal con elixir rojizo que se
          enciende y burbujea: de rojo oscuro (A) a naranja encendido (D), con las burbujas en otro
          sitio en cada fotograma.
- SOULA0-D0 (+100 salud; pleno brillo, flota 14 px como la de Freedoom) → la bola de cristal de la
          meiga: esfera de vidrio oscuro con un remolino de luz roja-anaranjada que gira dentro, una
          media luna de reflejo clara arriba a la izquierda y un reflejo pequeño abajo a la derecha.
- ARM1A0-B0 (armadura verde; B a pleno brillo, parpadea) → coleto de ante verde tirado en el suelo,
          con brahones de cuero en los hombros, cuello alzado, cinto y dos correas con hebillas de
          latón, faldones abiertos y tachuelas (B: igual, con un destello en las hebillas).
- ARM2A0-B0 (armadura azul; B a pleno brillo) → peto de hierro de tercio pavonado (azules de PLAYPAL),
          con la arista del tapul, bordes vueltos, remaches, faldar de dos launas y las correas de los
          hombros sueltas con su hebilla (B: igual, con destellos en remaches y hebillas).
- BON2A0-D0 (+1 armadura, A-B-C-D-C-B) → herradura de hierro pavonado (como el peto), de pie con
          la abertura arriba, de hierro grueso y azul claro en la cara iluminada (para que aguante la
          oscuridad), con un brillo que la recorre de un callo al otro y vuelve.

Técnica: el motor común de criaturas (sdf.py: primitivas SDF, Render con gancho de materiales,
rampas EXACTAS de PLAYPAL, contorno oscuro de 1 px) con la cámara algo más desde arriba (como se
ven los objetos del suelo desde los ojos), más dos primitivas propias: Torno (sólidos de revolución:
tarro, frascos) y Perfil (láminas con una silueta 2D, grosor y abombado: maletín, coleto, peto,
herradura).
Luz desde arriba-izquierda-delante. 1 unidad ≈ 1 px del sprite.

Uso (determinista; escribe los PNG y <salida>/offsets_salud.json):
    ~/.venvs/pesadilla/bin/python tools/arte/salud.py --salida arte/sprites [--solo STIMA0,...] [--hoja h.png]
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdf import (IWAD, V, Box, Ellipsoid, Frame, Group, Prim, Render, Ring, RoundCone,  # noqa: E402
                 Sphere, apply_shine, finish, rad, rot_x, rot_y, rot_z, vnoise)
from doomgfx import decode_patch, read_palette, read_wad  # noqa: E402

# ----------------------------------------------------------------------------- materiales
(CERAMICA, BANDA, CORCHO, CUERDA, LIENZO, CUERO_ROJO, LATON, VIDRIO, ELIXIR, BOLA, COLETO,
 COSTURA, AZUL, BORDE_AZUL, REMACHE, CORREA, AGUJERO, BRILLO, HOJA, HOJA_OSC, SELLO, HERRADURA,
 VIDRIO_OSC, REFLEJO) = range(24)

RAMPS = {
    CERAMICA: [107, 104, 100, 96, 92, 87, 83, 49],          # loza blanca (gris → blanco cálido)
    BANDA: [46, 42, 185, 182, 179, 177],                    # rojo vivo (la franja de la etiqueta)
    CORCHO: [77, 75, 72, 69, 66, 64],                       # corcho
    CUERDA: [150, 148, 146, 144, 128],                      # bramante / esparto
    LIENZO: [107, 104, 101, 98, 95, 92, 89, 86, 83, 81],    # lienzo blanco del maletín (algo sucio)
    CUERO_ROJO: [47, 45, 42, 187, 185, 183, 181, 179, 177],  # cuero rojo: asa, correas, culo, cantoneras
    LATON: [167, 166, 165, 164, 163, 162, 161],             # latón
    VIDRIO: [108, 105, 101, 97, 93, 88],                    # canto del cristal
    ELIXIR: [46, 42, 185, 182, 179, 176, 215, 213, 211, 209],   # elixir: nivel de brillo
    BOLA: [8, 2, 47, 45, 189, 186, 235, 233, 221, 217, 215, 214, 162, 161, 160, 227, 225],  # nivel
    COLETO: [12, 127, 126, 125, 124, 123, 122, 121, 120],   # ante verde oscuro
    COSTURA: [127, 12, 126],                                # costuras y abertura del coleto
    AZUL: [246, 244, 242, 240, 206, 205, 204, 202, 200, 198, 196],   # hierro pavonado azul
    BORDE_AZUL: [242, 206, 204, 202, 200, 198, 197, 195, 193],  # bordes vueltos (más claros)
    REMACHE: [104, 100, 95, 90, 85, 81],                    # remaches de hierro claro
    CORREA: [2, 239, 238, 237, 236, 13, 74],                # correas de cuero
    AGUJERO: [0],
    BRILLO: [195, 193, 192, 4],                             # destellos (nivel)
    HOJA: [125, 123, 121, 119, 117, 115, 114],              # hoja verde
    HOJA_OSC: [12, 127, 126],                               # borde de la hoja pintada
    SELLO: [46, 42, 185, 182, 179],                         # lacre
    HERRADURA: [244, 242, 240, 206, 204, 202, 200, 198, 197, 196],  # hierro pavonado (herradura)
    VIDRIO_OSC: [8, 5, 110, 108, 106],                      # cristal vacío (cuello del frasco)
    REFLEJO: [98, 94, 90, 86, 83, 81, 80],                  # reflejo de la ventana en la bola
}
LEVEL = (ELIXIR, BOLA, BRILLO)
EMISSIVE = (ELIXIR, BRILLO, SELLO, HOJA, HOJA_OSC, REMACHE, BOLA, LATON, REFLEJO)
OUTLINE = 2


# ----------------------------------------------------------------------------- figuras 2D
def caja2(x, y, cx, cy, hx, hy, r=0.0):
    qx = np.abs(x - cx) - hx + r
    qy = np.abs(y - cy) - hy + r
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def elipse2(x, y, cx, cy, rx, ry):
    return (np.hypot((x - cx) / rx, (y - cy) / ry) - 1) * min(rx, ry)


def poligono2(x, y, pts):
    """Distancia con signo a un polígono (iq)."""
    pts = np.asarray(pts, float)
    d = (x - pts[0, 0]) ** 2 + (y - pts[0, 1]) ** 2
    s = np.ones_like(x)
    j = len(pts) - 1
    for i in range(len(pts)):
        ex, ey = pts[j] - pts[i]
        wx, wy = x - pts[i, 0], y - pts[i, 1]
        t = np.clip((wx * ex + wy * ey) / (ex * ex + ey * ey), 0, 1)
        bx, by = wx - ex * t, wy - ey * t
        d = np.minimum(d, bx * bx + by * by)
        c1 = y >= pts[i, 1]
        c2 = y < pts[j, 1]
        c3 = ex * wy > ey * wx
        s = np.where((c1 & c2 & c3) | (~c1 & ~c2 & ~c3), -s, s)
        j = i
    return s * np.sqrt(d)


def espejo(pts):
    """Mitad derecha (x ≥ 0, de abajo arriba) → polígono completo simétrico."""
    return list(pts) + [(-x, y) for x, y in reversed(pts) if x != 0]


# ----------------------------------------------------------------------------- primitivas propias
class Torno(Prim):
    """Sólido de revolución alrededor del eje y' de F: perfil = [(y, radio), ...] de abajo arriba."""

    def __init__(self, F, perfil, mat):
        ys, rs = zip(*perfil)
        self.F, self.mat = F, mat
        self.ys, self.rs = np.array(ys, float), np.array(rs, float)
        self.sl = np.gradient(self.rs, self.ys)
        self.bc = F.p((0, (ys[0] + ys[-1]) / 2, 0))
        self.br = math.hypot((ys[-1] - ys[0]) / 2, max(rs)) + 0.5

    def sdf(self, P):
        q = self.F.to_local(P)
        rho = np.hypot(q[:, 0], q[:, 2])
        y = q[:, 1]
        r = np.interp(y, self.ys, self.rs)
        s = np.interp(y, self.ys, self.sl)
        dr = (rho - r) / np.sqrt(1 + s * s)
        dc = np.maximum(self.ys[0] - y, y - self.ys[-1])
        return np.hypot(np.maximum(dr, 0), np.maximum(dc, 0)) + np.minimum(np.maximum(dr, dc), 0)


class Perfil(Prim):
    """Lámina con silueta 2D f2(x, y) (< 0 dentro) en el plano x'-y' de F, de medio grosor g(x, y),
    abombada b(x, y) hacia z' (la normal de la lámina). ext = (x0, x1, y0, y1) de la silueta."""

    def __init__(self, F, f2, g, b, ext, mat, redondeo=0.35):
        self.F, self.f2, self.g, self.b, self.mat, self.rr = F, f2, g, b, mat, redondeo
        x0, x1, y0, y1 = ext
        self.bc = F.p(((x0 + x1) / 2, (y0 + y1) / 2, 2.0))
        self.br = math.hypot(x1 - x0, y1 - y0) / 2 + 7.0

    def sdf(self, P):
        q = self.F.to_local(P)
        x, y, z = q[:, 0], q[:, 1], q[:, 2]
        g = self.g(x, y) if callable(self.g) else self.g
        d2 = self.f2(x, y) + self.rr
        dz = np.abs(z - self.b(x, y)) - g + self.rr
        return (np.hypot(np.maximum(d2, 0), np.maximum(dz, 0)) + np.minimum(np.maximum(d2, dz), 0)
                - self.rr) * 0.85


def lamina(o, cabeceo):
    """Frame de una lámina tumbada: x' a la derecha, y' sube por la prenda echada hacia atrás
    «cabeceo» grados desde la vertical, z' = normal (hacia la cámara y arriba)."""
    b = rad(cabeceo)
    R = np.column_stack([(1, 0, 0), (0, math.cos(b), -math.sin(b)), (0, math.sin(b), math.cos(b))])
    return Frame(o, R)


# ----------------------------------------------------------------------------- render
_RENDERS = {}


def render_para(tilt):
    if tilt not in _RENDERS:
        _RENDERS[tilt] = Render(RAMPS, hook=materiales, level_mats=LEVEL, emissive=EMISSIVE, tilt=rad(tilt))
    return _RENDERS[tilt]


def vista(tilt):
    """(eje x de pantalla, eje y de pantalla, dirección de la mirada) en el espacio del modelo."""
    t = rad(tilt)
    return V(1, 0, 0), V(0, math.cos(t), -math.sin(t)), V(0, -math.sin(t), -math.cos(t))


def dibujar(groups, extras, tilt):
    """Traza el objeto, le pone contorno y lo recorta. → (imagen RGBA, columna del eje, fila del suelo).
    Se eleva todo lo necesario para que nada caiga por debajo del lienzo del trazador."""
    _, Uc, _ = vista(tilt)
    low = min(g.model_bound()[0] @ Uc - g.model_bound()[1] for g in groups)
    lift = max(0.0, (3.0 - low) / math.cos(rad(tilt)))
    t = V(0, lift, 0)
    for g in groups:
        g.xf = (np.eye(3), t, 1.0)
    extras = dict(extras, t=t, tilt=tilt)
    R = render_para(tilt)
    out, depth = R.render(groups, extras, 1)
    a = np.array(finish(out, depth, R.palarr, OUTLINE))
    a[a[:, :, 3] < 128] = 0
    H, W = a.shape[:2]
    hw = W // 2
    top = H - 1                                     # fila del lienzo con sy en [-1, 0)
    suelo = top - lift * math.cos(rad(tilt))        # fila (continua) donde cae el origen del modelo
    vis = a[:, :, 3] >= 128
    cols = np.nonzero(vis.any(0))[0]
    rows = np.nonzero(vis.any(1))[0]
    b = a[rows.min():rows.max() + 1, cols.min():cols.max() + 1].copy()
    return b, hw - cols.min(), suelo - rows.min()


# ----------------------------------------------------------------------------- gancho de materiales
def materiales(P, mat, inten, nz, nr, spec, lvl_extra, extras):
    Q = P - extras['t']                     # coordenadas del modelo (sin la elevación)
    Xc, Uc, Dc = vista(extras['tilt'])
    obj = extras['obj']
    fres = 1 - np.abs(nr @ Dc)               # 0 de cara, 1 en la silueta
    if obj == 'STIM':
        gancho_tarro(Q, mat, inten, nz, nr, spec, extras)
    elif obj == 'MEDI':
        gancho_maletin(Q, mat, inten, nz, nr, spec, fres, extras)
    elif obj == 'BON1':
        gancho_frasco(Q, mat, inten, nz, nr, spec, lvl_extra, fres, Xc, Uc, extras)
    elif obj == 'SOUL':
        gancho_bola(Q, mat, inten, nr, spec, lvl_extra, fres, Xc, Uc, extras)
    elif obj in ('ARM1',):
        gancho_coleto(Q, mat, inten, nz, spec, lvl_extra, extras)
    elif obj in ('ARM2',):
        gancho_peto(Q, mat, inten, nz, nr, spec, lvl_extra, extras)
    elif obj == 'BON2':
        gancho_herradura(Q, mat, inten, nz, spec, lvl_extra, extras)


# ============================================================================= STIM: tarro de ungüento
TARRO = [(0.0, 5.6), (0.5, 6.5), (1.2, 7.1), (4.6, 7.2), (5.8, 6.7), (6.6, 5.4), (7.0, 4.4), (7.6, 4.3)]
TAPA = [(7.0, 4.5), (7.3, 4.8), (9.5, 4.8), (9.8, 4.5), (9.95, 3.2), (10.0, 0.0)]
SELLO_P = [(9.6, 2.5), (10.3, 2.5), (10.5, 1.8), (10.55, 0.0)]


def tarro():
    F = Frame((0, 0, 0))
    g = [Group([Torno(F, TARRO, CERAMICA)]),
         Group([Torno(F, TAPA, CORCHO), Torno(F, SELLO_P, SELLO),
                Ring(Frame((0, 7.6, 0)), 4.85, 4.85, 0.45, CUERDA)], k=0.2)]
    return g, {'obj': 'STIM'}


def gancho_tarro(Q, mat, inten, nz, nr, spec, extras):
    phi = np.arctan2(Q[:, 0], Q[:, 2])                  # 0 = de cara a la cámara
    y = Q[:, 1]
    m = mat == CERAMICA
    # franja roja pintada alrededor de la panza (como la loza de botica)
    mat[m & (np.abs(y - 4.1) < 0.9)] = BANDA
    mat[m & (np.abs(y - 1.9) < 0.35)] = BANDA
    # loza: vidriado brillante, algo sucio abajo
    m = mat == CERAMICA
    inten[m] *= 0.92 + 0.14 * nz[m]
    inten[m & (y < 1.0)] *= 0.8
    apply_shine(mat, inten, spec, ((CERAMICA, 0.8, 12), (SELLO, 0.7, 8), (BANDA, 0.4, 8)))
    m = mat == CORCHO
    inten[m] *= 0.8 + 0.4 * vnoise(Q[m], 2.2, 3)


# ============================================================================= MEDI: maletín del curandero
# Maletín de médico de los de boca en arco (bolsa Gladstone) forrado de lienzo blanco, con el culo,
# las cantoneras, las dos correas y el asa de cuero rojo, el cierre de latón en lo alto y una hoja
# verde grande pintada en la cara de delante (el distintivo del herbolario: nada de cruces).
# Blanco y rojo, como el tarro: la familia de la salud; y de silueta de bolsa, no de caja.
MAL_PTS = espejo([(0.0, 0.0), (11.6, 0.0), (12.5, 0.7), (12.9, 2.3), (12.7, 7.4), (12.1, 9.5),
                  (10.6, 11.0), (7.6, 12.0), (3.6, 12.5), (0.0, 12.6)])
MAL_TOP = 12.6                       # alto del maletín en el centro (la boca en arco)
CORREAS_MAL = (-7.0, 7.0)            # x de las dos correas que lo abrazan
HOJA_C = (0.0, 6.2)                  # centro de la hoja pintada


def f_maletin(x, y):
    return poligono2(x, y, MAL_PTS)


def g_maletin(x, y):
    """Medio fondo: panzudo abajo y estrecho arriba, donde se juntan las dos mitades del armazón."""
    t = np.clip(y / (MAL_TOP + 0.6), 0, 1)
    return (1.7 + 4.0 * np.sqrt(np.clip(1 - t ** 2.2, 0, 1))) * (1 - 0.12 * (x / 12.9) ** 4)


def vesica(u, v, w, L):
    """Hoja puntiaguda (vesica) de medio ancho w y medio largo L a lo largo de v: < 0 dentro."""
    R = (L * L + w * w) / (2 * w)
    return np.maximum(np.hypot(u - (R - w), v), np.hypot(u + (R - w), v)) - R


def frente_maletin(x, y):
    """z de la cara de delante del maletín."""
    return g_maletin(np.asarray([x], float), np.asarray([y], float))[0]


def maletin():
    F = Frame((0, 0, 0))
    cuerpo = Perfil(F, f_maletin, g_maletin, lambda x, y: 0 * x, (-13, 13, 0, MAL_TOP), LIENZO, redondeo=1.0)
    # el asa de cuero, de pie sobre la boca (algo echada hacia atrás), con sus anillas de latón
    asa = Ring(Frame((0, MAL_TOP - 0.6, 0), rot_x(rad(84))), 3.9, 5.2, 0.95, CUERO_ROJO)
    asa.cut = lambda P: (MAL_TOP - 0.2) - P[:, 1]
    herrajes = [Sphere((-4.0, MAL_TOP - 0.2, 0), 1.0, LATON), Sphere((4.0, MAL_TOP - 0.2, 0), 1.0, LATON),
                # el cierre de la boca, delante, bajo el asa
                Box((0, MAL_TOP - 1.9, frente_maletin(0, MAL_TOP - 1.9) - 0.1), (1.2, 0.9, 0.45),
                    rot_x(rad(-38)), 0.3, LATON)]
    # hebillas de las correas, en la cara de delante
    for cx in CORREAS_MAL:
        y = 9.0
        herrajes.append(Box((cx, y, frente_maletin(cx, y) - 0.15), (1.25, 0.85, 0.4), rot_x(rad(-30)),
                            0.25, LATON))
    return [Group([cuerpo]), Group([asa]), Group(herrajes)], {'obj': 'MEDI'}


def gancho_maletin(Q, mat, inten, nz, nr, spec, fres, extras):
    x, y, z = Q[:, 0], Q[:, 1], Q[:, 2]
    m = mat == LIENZO
    d = f_maletin(x, y)
    # culo y cantoneras de cuero rojo, y las dos correas que lo abrazan
    culo = m & (y < 2.1)
    canton = m & ((12.9 - np.abs(x)) + 0.75 * y < 4.6)
    correa = m & np.any([np.abs(x - cx) < 1.05 for cx in CORREAS_MAL], axis=0)
    mat[culo | canton | correa] = CUERO_ROJO
    # el hueco de las hebillas deja ver la correa
    for cx in CORREAS_MAL:
        h = (mat == LATON) & (np.abs(x - cx) < 0.5) & (np.abs(y - 9.0) < 0.35)
        mat[h] = CUERO_ROJO
    # el armazón de la boca: un junquillo de latón por la cresta
    m = mat == LIENZO
    mat[m & (np.abs(z) < 0.75) & (d > -1.3) & (np.abs(x) < 11.0)] = LATON
    # la hoja verde pintada en la cara de delante (lanceolada, inclinada, con su nervio y su rabo)
    m = (mat == LIENZO) & (z > 1.0)
    xx, yy = x - HOJA_C[0], y - HOJA_C[1]
    c, s = math.cos(0.5), math.sin(0.5)
    u, v = xx * c - yy * s, xx * s + yy * c
    mat[m & (vesica(u, v, 2.75, 4.9) < 0)] = HOJA_OSC
    mat[m & (vesica(u, v, 2.05, 4.1) < 0)] = HOJA
    rabo = m & (np.abs(u) < 0.42) & (v < -3.6) & (v > -5.9)
    mat[rabo] = HOJA_OSC
    h = mat == HOJA
    inten[h] = 0.55 + 0.35 * np.clip((-u[h] + v[h]) / 4.0, -1, 1)
    inten[h & (np.abs(u) < 0.35) & (v > -2.6) & (v < 2.4)] = 1.0       # el nervio, claro
    inten[mat == HOJA_OSC] = 0.3
    # lienzo: trama, polvo abajo, y los pespuntes del canto de la cara
    m = mat == LIENZO
    inten[m] *= 0.88 + 0.2 * vnoise(Q[m] * V(1.0, 0.6, 1.0), 1.1, 7)
    inten[m & (y < 4.0)] *= 0.9
    inten[m & (d > -1.1) & (z > 0.5) & (np.abs(nr[:, 2]) > 0.35)] *= 0.82
    m = mat == CUERO_ROJO
    inten[m] *= 0.9 + 0.2 * vnoise(Q[m], 1.4, 8)
    apply_shine(mat, inten, spec, ((LATON, 1.0, 10), (CUERO_ROJO, 0.45, 10), (LIENZO, 0.12, 4)))


# ============================================================================= BON1: frasquito de elixir
FRASCO_R = 4.55
BON1_FR = {   # (brillo del elixir, [(x, y, radio) de las burbujas en el plano de la pantalla])
    'A': (-0.16, [(-1.2, 1.9, 0.7), (1.4, 4.4, 0.55)]),
    'B': (0.06, [(0.9, 2.4, 0.7), (-1.6, 5.0, 0.55), (0.2, 6.6, 0.45)]),
    'C': (0.28, [(-0.5, 3.0, 0.8), (1.7, 5.6, 0.55), (-1.4, 6.8, 0.45)]),
    'D': (0.50, [(0.6, 3.6, 0.85), (-1.5, 4.6, 0.6), (1.1, 7.3, 0.55), (-0.2, 1.6, 0.45)]),
}


def frasco(fr):
    F = Frame((0, 0, 0))
    R = FRASCO_R
    g = [Group([Sphere((0, R, 0), R, ELIXIR),
                Torno(F, [(R + 2.6, 1.75), (R + 3.4, 1.45), (R + 6.2, 1.4), (R + 6.7, 1.9), (R + 7.3, 1.9),
                          (R + 7.5, 1.5)], VIDRIO_OSC)], k=0.9),
         Group([Torno(F, [(R + 7.1, 1.25), (R + 9.2, 1.4), (R + 9.5, 1.0), (R + 9.6, 0.0)], CORCHO)])]
    brillo, burb = BON1_FR[fr]
    return g, {'obj': 'BON1', 'brillo': brillo, 'burbujas': burb}


def gancho_frasco(Q, mat, inten, nz, nr, spec, lvl, fres, Xc, Uc, extras):
    R = FRASCO_R
    cen = V(0, R, 0)
    sx = (Q - cen) @ Xc
    sy = (Q - cen) @ Uc
    body = mat == ELIXIR
    # nivel del líquido: el cuello y el borde superior del vientre son cristal vacío
    vacio = body & (Q[:, 1] > 2 * R - 1.1)
    mat[vacio] = VIDRIO_OSC
    # canto del cristal (silueta): claro y frío
    canto = (mat == ELIXIR) & (fres > 0.78)
    mat[canto] = VIDRIO
    inten[canto] = 0.15 + 0.6 * np.clip((-sx[canto] + sy[canto]) / (1.4 * R), 0, 1) + 0.4 * max(extras['brillo'], 0)
    m = mat == ELIXIR
    rho = np.hypot(sx[m] + 0.4, sy[m] + 0.6) / R
    b = extras['brillo']
    n = len(RAMPS[ELIXIR])
    lv = (0.95 - 0.75 * rho) * (n - 3) + b * 6 + 1.0 * (vnoise(Q[m], 1.1, 9) - 0.5)
    for (bx, by, br) in extras['burbujas']:
        d = np.hypot(sx[m] - bx, sy[m] - (by - R))
        lv = np.where(d < br, n - 1.0, np.where(d < br + 0.55, np.maximum(lv - 2, 1), lv))
    lvl[m] = np.clip(lv, 0, n - 1)
    # brillo del cristal arriba a la izquierda
    hl = np.isin(mat, (ELIXIR, VIDRIO, VIDRIO_OSC)) & (spec > 0.975)
    mat[hl] = BRILLO
    lvl[hl] = 3
    apply_shine(mat, inten, spec, ((VIDRIO_OSC, 0.9, 10), (CORCHO, 0.1, 4)))
    m = mat == CORCHO
    inten[m] *= 0.8 + 0.4 * vnoise(Q[m], 2.4, 4)


# ============================================================================= SOUL: bola de cristal
BOLA_R = 11.6
SOUL_FR = {'A': (0.0, 1.0), 'B': (0.42, 1.06), 'C': (0.84, 1.12), 'D': (1.26, 1.18)}   # (giro, pulso)


def bola(fr):
    g = [Group([Sphere((0, BOLA_R, 0), BOLA_R, BOLA)])]
    giro, pulso = SOUL_FR[fr]
    return g, {'obj': 'SOUL', 'giro': giro, 'pulso': pulso}


def gancho_bola(Q, mat, inten, nr, spec, lvl, fres, Xc, Uc, extras):
    cen = V(0, BOLA_R, 0)
    u = ((Q - cen) @ Xc) / BOLA_R
    v = ((Q - cen) @ Uc) / BOLA_R
    rho = np.clip(np.hypot(u, v), 0, 1)
    th = np.arctan2(v, u)
    g, p = extras['giro'], extras['pulso']
    n = len(RAMPS[BOLA])
    # remolino de dos brazos que se enrosca hacia el centro, lenguas finas entre medias y un
    # corazón que late
    brazo = np.clip(np.cos(2 * (th + g) + 7.0 * rho), 0, 1) ** 2 * np.clip(1.05 - rho, 0, 1) * 1.35
    lengua = np.clip(np.cos(3 * (th - 0.5 * g) - 5.0 * rho + 1.0), 0, 1) ** 4 * np.clip(0.85 - rho, 0, 1)
    corazon = p * np.exp(-(rho / 0.27) ** 2) * 1.2
    calor = np.maximum.reduce([brazo, lengua * 0.95, corazon]) + 0.3 * (1 - rho) ** 0.7
    lv = 1.5 + calor * (n - 2.5)
    # cristal: el borde es oscuro, salvo abajo a la derecha, donde lo tiñe la luz de dentro
    borde = rho > 0.84
    tinte = np.clip((u - v) / 1.2, 0, 1) * np.clip((rho - 0.84) / 0.1, 0, 1)
    lv = np.where(borde, np.minimum(lv, 1 + 6 * tinte), lv)
    # reflejo de la ventana: una media luna clara en el borde de arriba a la izquierda…
    ca = np.cos(th - 2.3)
    luna = (rho > 0.70) & (rho < 0.94) & (ca > 0.77)
    # … un punto de brillo dentro, separado del corazón, y un reflejo pequeño abajo a la derecha
    punto = np.hypot(u + 0.36, v - 0.4) < 0.12
    contra = (rho > 0.74) & (rho < 0.87) & (np.cos(th + 0.85) > 0.975)
    lvl[:] = np.clip(np.where(punto, n - 1, lv), 0, n - 1)
    mat[:] = BOLA
    mat[(luna | contra) & ~punto] = REFLEJO
    # la media luna, más clara en el centro (de grosor y de ángulo)
    centro = np.clip(1 - np.abs(rho - 0.815) / 0.14, 0, 1)
    inten[luna] = 0.35 + 0.75 * centro[luna] * np.clip((ca[luna] - 0.77) / 0.18, 0, 1) ** 0.5
    inten[contra] = 0.25


# ============================================================================= ARM1: coleto de ante
COLETO_PTS = espejo([(0.0, -0.2), (6.0, -0.6), (12.6, 0.0), (9.4, 6.4), (8.6, 8.4), (10.2, 12.0),
                     (11.2, 15.6), (11.0, 18.4), (12.0, 20.4), (11.8, 23.0), (9.6, 24.8), (5.2, 25.4),
                     (0.0, 25.4)])
TACHUELAS = ([(x, 2.0) for x in (-10.0, -7.4, -3.4, 3.4, 7.4, 10.0)]
             + [(s * x, y) for s in (-1, 1) for x, y in ((9.7, 11.6), (10.6, 15.4), (10.4, 18.6))])
CINTO = (6.3, 8.7)                       # el cinto de cuero (y de abajo y de arriba)
CORREAS_ARM1 = (12.6, 16.6)              # correas del pecho
HEBILLAS_ARM1 = ((0.0, 7.5, 1.9, 1.5), (2.3, 12.6, 1.2, 1.0), (-2.3, 16.6, 1.2, 1.0))   # x, y, medio ancho, medio alto


def f_coleto(x, y):
    d = poligono2(x, y, COLETO_PTS)
    d = np.maximum(d, -elipse2(x, y, 0, 26.6, 5.0, 4.2))           # escote
    for sx in (-5.6, 5.6):                                         # aberturas de los faldones
        d = np.maximum(d, -caja2(x, y, sx, 1.4, 0.4, 3.0))
    d = np.maximum(d, -caja2(x, y, 0, 2.2, 0.55, 4.0))             # se abre por delante abajo
    return d


def b_coleto(x, y):
    return 4.6 * np.clip(1 - (x / 13.5) ** 2, 0, 1) * np.clip(0.45 + y / 16, 0, 1)


def coleto(fr):
    F = lamina((0, 1.6, 9.0), 64)
    sobre = lambda x, y, dz: F.p((x, y, b_coleto(np.array([x]), np.array([y]))[0] + dz))  # noqa: E731
    piezas = [Perfil(F, f_coleto, 1.25, b_coleto, (-13, 13, -1, 26), COLETO)]
    # brahones: rollos de cuero en los hombros
    for s in (-1, 1):
        piezas.append(Ellipsoid(sobre(s * 10.8, 21.8, 1.0), (3.3, 3.6, 2.2), F.R @ rot_z(rad(-s * 20)).T, CORREA))
    # cuello alzado
    piezas.append(Ring(Frame(F.p((0, 25.0, 2.6)), F.R), 4.4, 2.2, 0.9, COLETO))
    hebillas = [Box(sobre(hx, hy, 1.3), (hw, hh, 0.45), F.R, 0.25, LATON) for hx, hy, hw, hh in HEBILLAS_ARM1]
    return [Group(piezas, k=0.8), Group(hebillas)], {'obj': 'ARM1', 'F': F, 'fr': fr}


def gancho_coleto(Q, mat, inten, nz, spec, lvl, extras):
    F = extras['F']
    q = F.to_local(Q)
    x, y = q[:, 0], q[:, 1]
    m = mat == COLETO
    d = f_coleto(x, y)
    # cinto y correas de cuero oscuro
    mat[m & (y > CINTO[0]) & (y < CINTO[1]) & (d < -0.3)] = CORREA
    for yy in CORREAS_ARM1:
        mat[m & (np.abs(y - yy) < 0.8) & (np.abs(x) < 7.6) & (d < -0.4)] = CORREA
    # el hueco de las hebillas
    for hx, hy, hw, hh in HEBILLAS_ARM1:
        h = (mat == LATON) & (np.abs(x - hx) < hw - 0.75) & (np.abs(y - hy) < hh - 0.7)
        mat[h] = CORREA
    # tachuelas
    for tx, ty in TACHUELAS:
        mat[np.isin(mat, (COLETO, CORREA)) & (np.hypot(x - tx, y - ty) < 0.55)] = LATON
    # abertura delantera y pespuntes del borde
    m = mat == COLETO
    mat[m & (np.abs(x) < 0.42) & (y < 24.0) & (d < -0.5)] = COSTURA
    m = mat == COLETO
    inten[m] *= (0.84 + 0.24 * vnoise(q[m], 0.7, 21)) * (1 + 0.1 * np.sin(1.3 * y[m] + 0.8 * np.sin(0.7 * x[m])))
    inten[m & (d > -1.0) & (d < -0.4)] *= 0.72
    m = mat == CORREA
    inten[m] *= 0.85 + 0.3 * vnoise(q[m], 1.3, 22)
    apply_shine(mat, inten, spec, ((LATON, 1.0, 10), (COLETO, 0.15, 6), (CORREA, 0.3, 8)))
    if extras['fr'] == 'B':                       # el fotograma a pleno brillo: un destello en la hebilla
        hb = (mat == LATON) & (spec > 0.8)
        mat[hb] = BRILLO
        lvl[hb] = 3


# ============================================================================= ARM2: peto de tercio
PETO_PTS = espejo([(0.0, 3.6), (3.5, 4.7), (7.6, 6.2), (8.4, 7.6), (11.0, 11.0), (12.4, 14.6),
                   (12.0, 17.4), (9.6, 19.0), (8.0, 20.6), (7.4, 23.0), (5.4, 24.0), (0.0, 24.0)])
FALDAR = espejo([(0.0, -0.2), (6.0, -0.7), (12.2, 0.0), (10.2, 4.2), (8.4, 6.8), (0.0, 6.8)])
REMACHES_PETO = [(s * x, y) for s in (-1, 1) for x, y in ((7.4, 21.6), (11.4, 15.2), (8.0, 7.2))]
REMACHES_ESC = [(s * x, y) for s in (-1, 1) for x, y in ((9.8, 4.2), (11.0, 1.4), (5.0, 1.0))]


def f_peto(x, y):
    d = poligono2(x, y, PETO_PTS)
    return np.maximum(d, -elipse2(x, y, 0, 25.6, 6.0, 4.4))       # escote


def f_borde_peto(x, y):
    """Cordón (borde vuelto) del escote y de las sisas: una franja de 1,1 px por dentro del borde."""
    franja = np.abs(f_peto(x, y) + 0.6) - 0.6
    arriba = (y > 19.0) | ((y > 13.0) & (np.abs(x) > 9.0))
    return np.maximum(franja, np.where(arriba, -1.0, 1.0))


def b_peto(x, y):
    tapul = 1.8 * np.clip(1 - np.abs(x) / 1.9, 0, 1) * np.clip((y - 4.5) / 4, 0, 1)
    pecho = 0.55 + 0.45 * np.sin(np.pi * np.clip((y - 3.0) / 23.0, 0, 1))
    return 6.6 * np.clip(1 - (x / 14.0) ** 2, 0, 1) * pecho + tapul


def f_esc(x, y):
    return poligono2(x, y, FALDAR)


def b_esc(x, y):
    return 3.4 * np.clip(1 - (x / 14.0) ** 2, 0, 1) + 0.4 - 0.25 * y


def peto(fr):
    F = lamina((0, 1.2, 9.5), 60)
    sobre = lambda x, y, dz: F.p((x, y, b_peto(np.array([x]), np.array([y]))[0] + dz))  # noqa: E731
    cuerpo = [Perfil(F, f_peto, 1.0, b_peto, (-13, 13, 4, 25), AZUL, redondeo=0.5),
              Perfil(F, f_borde_peto, 1.3, b_peto, (-13, 13, 4, 25), BORDE_AZUL, redondeo=0.5)]
    # faldar: dos launas corridas que se abren un poco por abajo
    esc = [Perfil(F, f_esc, 0.9, b_esc, (-13, 13, -1, 7), AZUL, redondeo=0.4)]
    # correas de los hombros, sueltas y tiradas hacia fuera, con su hebilla
    correas = []
    for s in (-1, 1):
        a = sobre(s * 6.4, 23.2, 0.7)
        bq = F.p((s * 13.6, 22.2, 0.9))
        correas.append(RoundCone(a, bq, 0.95, 0.85, CORREA))
        correas.append(Box(F.p((s * 12.6, 22.4, 1.4)), (1.1, 1.0, 0.45), F.R @ rot_z(rad(s * 8)), 0.25, LATON))
    return ([Group(cuerpo, k=0.3), Group(esc), Group(correas)], {'obj': 'ARM2', 'F': F, 'fr': fr})


LUZ = np.array([-0.5, 0.75, 0.55]) / np.linalg.norm([-0.5, 0.75, 0.55])


def gancho_peto(Q, mat, inten, nz, nr, spec, lvl, extras):
    F = extras['F']
    q = F.to_local(Q)
    x, y = q[:, 0], q[:, 1]
    met = np.isin(mat, (AZUL, BORDE_AZUL))
    # launas de las escarcelas: surcos horizontales; y la junta del faldar con el peto
    inten[met & (y < 6.4) & (np.abs(y - 3.3) < 0.4)] *= 0.45
    inten[met & (np.abs(y - 6.5) < 0.35)] *= 0.4
    # remaches
    for rx, ry in REMACHES_PETO + REMACHES_ESC:
        mat[met & (np.hypot(x - rx, y - ry) < 0.6)] = REMACHE
    # golpes y desgaste del pavonado
    m = np.isin(mat, (AZUL, BORDE_AZUL))
    dif = np.clip(nr[m] @ LUZ, 0, 1)
    oscuro = inten[m] / np.maximum(0.24 + 0.86 * dif, 1e-3)          # oclusión y ruido del motor
    inten[m] = ((0.1 + 0.66 * dif ** 1.5) * np.clip(oscuro, 0.5, 1.2) * (0.86 + 0.24 * vnoise(q[m], 0.8, 31))
                + np.where(mat[m] == BORDE_AZUL, 0.18, 0.0) + 0.75 * spec[m] ** 24)
    # la arista del tapul (en medio del pecho) coge la luz: una línea clara
    tap = (mat == AZUL) & (np.abs(x + 0.35) < 0.5) & (y > 7.0) & (y < 22.0)
    mat[tap] = BORDE_AZUL
    inten[tap] = 0.62 + 0.12 * np.clip((y[tap] - 7.0) / 8.0, 0, 1)
    apply_shine(mat, inten, spec, ((REMACHE, 0.9, 8), (CORREA, 0.25, 8), (LATON, 0.9, 8)))
    # destellos: lo más brillante del pavonado se va al azul lavanda
    hb = np.isin(mat, (AZUL, BORDE_AZUL)) & (spec > 0.985)
    mat[hb] = BRILLO
    lvl[hb] = np.where(spec[hb] > 0.98, 1, 0)
    if extras['fr'] == 'B':
        hb = np.isin(mat, (REMACHE, LATON)) & (spec > 0.8)
        mat[hb] = BRILLO
        lvl[hb] = 3


# ============================================================================= BON2: herradura
HER_C = (0.0, 8.3)
HER_OUT = (6.4, 8.3)
HER_IN = (2.9, 4.8)
CLAVOS = [-1.15, -0.62, -0.1]          # ángulos (desde abajo) de los clavos de cada rama
BON2_FR = {'A': 0.12, 'B': 0.37, 'C': 0.63, 'D': 0.88}   # dónde está el destello (0 = callo izquierdo)


def f_herradura(x, y):
    cx, cy = HER_C
    d = np.maximum(elipse2(x, y, cx, cy, *HER_OUT), -elipse2(x, y, cx, cy, *HER_IN))
    d = np.maximum(d, -caja2(x, y, 0.0, cy + 8.0, 3.1, 4.5))      # abertura entre los callos
    return d


def herradura(fr):
    F = Frame((0, 0.0, 0), rot_y(rad(-20)) @ rot_x(rad(-14)))
    g = [Group([Perfil(F, f_herradura, 1.05, lambda x, y: 0 * x, (-7, 7, -0.2, 17), HERRADURA, redondeo=0.45)])]
    return g, {'obj': 'BON2', 'F': F, 's0': BON2_FR[fr]}


def gancho_herradura(Q, mat, inten, nz, spec, lvl, extras):
    F = extras['F']
    q = F.to_local(Q)
    x, y = q[:, 0] - HER_C[0], q[:, 1] - HER_C[1]
    m = mat == HERRADURA
    # parámetro a lo largo de la U: 0 en el callo izquierdo, 1 en el derecho
    ang = np.arctan2(x, -y)                       # 0 abajo, −π/2 izquierda…
    s = (ang + 2.45) / 4.9
    # clavos: en la línea media de la herradura
    rmid = np.hypot(x / ((HER_OUT[0] + HER_IN[0]) / 2), y / ((HER_OUT[1] + HER_IN[1]) / 2))
    for a in CLAVOS + [-c for c in CLAVOS]:
        px = math.sin(a) * (HER_OUT[0] + HER_IN[0]) / 2
        py = -math.cos(a) * (HER_OUT[1] + HER_IN[1]) / 2
        mat[m & (np.hypot(x - px, y - py) < 0.62)] = AGUJERO
    m = mat == HERRADURA
    # surco de la línea de clavos
    inten[m & (np.abs(rmid - 1) < 0.07)] *= 0.75
    inten[m] *= 0.77 + 0.26 * vnoise(q[m], 1.0, 41)
    apply_shine(mat, inten, spec, ((HERRADURA, 0.6, 12),))
    # el destello que la recorre
    d = np.abs(s - extras['s0'])
    g = m & (d < 0.075) & (q[:, 2] > -0.2)
    mat[g] = BRILLO
    lvl[g] = np.where(d[g] < 0.03, 3, np.where(d[g] < 0.055, 2, 1))


# ----------------------------------------------------------------------------- lumps
OBJETOS = {
    'STIMA0': (tarro, None, 24, 'suelo'),
    'MEDIA0': (maletin, None, 24, 'suelo'),
    'BON1A0': (frasco, 'A', 22, 'suelo'), 'BON1B0': (frasco, 'B', 22, 'suelo'),
    'BON1C0': (frasco, 'C', 22, 'suelo'), 'BON1D0': (frasco, 'D', 22, 'suelo'),
    'SOULA0': (bola, 'A', 0, 'flota'), 'SOULB0': (bola, 'B', 0, 'flota'),
    'SOULC0': (bola, 'C', 0, 'flota'), 'SOULD0': (bola, 'D', 0, 'flota'),
    'ARM1A0': (coleto, 'A', 26, 'suelo'), 'ARM1B0': (coleto, 'B', 26, 'suelo'),
    'ARM2A0': (peto, 'A', 26, 'suelo'), 'ARM2B0': (peto, 'B', 26, 'suelo'),
    'BON2A0': (herradura, 'A', 18, 'suelo'), 'BON2B0': (herradura, 'B', 18, 'suelo'),
    'BON2C0': (herradura, 'C', 18, 'suelo'), 'BON2D0': (herradura, 'D', 18, 'suelo'),
}
FLOTA = 14          # la bola flota como la esfera de Freedoom (su borde de abajo, 14 px sobre el suelo)
HUNDE = 1           # los objetos del suelo bajan 1 px por debajo del apoyo (como la armadura de Freedoom)


def lump(nombre):
    fn, fr, tilt, apoyo = OBJETOS[nombre]
    groups, extras = fn() if fr is None else fn(fr)
    img, ax, suelo = dibujar(groups, extras, tilt)
    h, w = img.shape[:2]
    if apoyo == 'flota':
        off = [int(ax), h + FLOTA]
    else:
        off = [int(ax), h - HUNDE]
    return Image.fromarray(img, 'RGBA'), off


# ----------------------------------------------------------------------------- hoja de contactos
FILAS = [['STIMA0', 'MEDIA0', 'ARM1A0', 'ARM1B0', 'ARM2A0', 'ARM2B0'],
         ['BON1A0', 'BON1B0', 'BON1C0', 'BON1D0', 'BON2A0', 'BON2B0', 'BON2C0', 'BON2D0'],
         ['SOULA0', 'SOULB0', 'SOULC0', 'SOULD0']]


def freedoom(nombres):
    pal = read_palette(IWAD)
    d = dict(read_wad(IWAD)[1])
    return {n: decode_patch(d[n], pal) for n in nombres if n in d}


def hoja(images, offs, path, escala=5):
    """Hoja ampliada: cada lump nuestro (izquierda) junto al de Freedoom (derecha), apoyados en la
    misma línea de suelo (en rojo, el origen del objeto)."""
    ref = freedoom([n for r in FILAS for n in r])
    filas = [[n for n in f if n in images] for f in FILAS]
    filas = [f for f in filas if f]
    alto = []
    for f in filas:
        arriba = max(max(offs[n][1], ref[n][1][1] if n in ref else 0) for n in f)
        abajo = max(max(images[n].height - offs[n][1], (ref[n][0].height - ref[n][1][1]) if n in ref else 0) for n in f)
        alto.append((arriba, max(abajo, 3)))
    ancho = [max(max(images[n].width, ref[n][0].width if n in ref else 0) for n in f) for f in filas]
    W = max(len(f) * (2 * w * escala + 3 * 8) for f, w in zip(filas, ancho))
    H = sum((a + b) * escala + 30 for a, b in alto)
    sheet = Image.new('RGB', (W, H), (78, 78, 86))
    dr = ImageDraw.Draw(sheet)
    y0 = 0
    for f, w, (arr, aba) in zip(filas, ancho, alto):
        suelo = y0 + 22 + arr * escala
        cw = 2 * w * escala + 3 * 8
        for c, n in enumerate(f):
            x0 = c * cw
            dr.text((x0 + 4, y0 + 4), n, fill=(240, 240, 240))
            for k, par in enumerate(((images[n], offs[n]), ref.get(n))):
                if par is None:
                    continue
                im, off = par
                big = im.resize((im.width * escala, im.height * escala), Image.NEAREST)
                cx = x0 + 8 + w * escala * k + 8 * k + w * escala // 2
                sheet.paste(big, (int(cx - off[0] * escala), int(suelo - off[1] * escala)), big)
                dr.line([(cx - 3 * escala, suelo), (cx + 3 * escala, suelo)], fill=(220, 60, 60))
        y0 += (arr + aba) * escala + 30
    sheet.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--salida', required=True, help='carpeta de PNG (arte/sprites)')
    ap.add_argument('--solo', default='', help='lumps separados por comas')
    ap.add_argument('--hoja', default='', help='hoja de contactos (PNG) junto a los de Freedoom')
    args = ap.parse_args()
    os.makedirs(args.salida, exist_ok=True)
    nombres = [n.strip().upper() for n in args.solo.split(',') if n.strip()] or list(OBJETOS)
    ruta_off = os.path.join(args.salida, 'offsets_salud.json')
    offs = json.load(open(ruta_off)) if os.path.exists(ruta_off) else {}
    images = {}
    for n in nombres:
        im, off = lump(n)
        im.save(os.path.join(args.salida, n + '.png'))
        images[n] = im
        offs[n] = off
        print(f'{n} {im.width}x{im.height} offsets {off}', flush=True)
    with open(ruta_off, 'w') as f:
        json.dump(dict(sorted(offs.items())), f, indent=1)
    if args.hoja:
        hoja(images, offs, args.hoja)


if __name__ == '__main__':
    main()
