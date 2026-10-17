#!/usr/bin/env python3
"""decoracion.py — LA DECORACIÓN Y LOS EFECTOS de PESADILLA (sustituyen a los de Freedoom), dibujados
por código con el motor de criaturas (sdf.py). Folk horror de pueblo español, de noche.

Mismos estados de info.c (no rotan: lumps X?0); tamaños y apoyo parecidos a los de Freedoom.
Los marcados con * van a PLENO BRILLO en el juego (no se oscurecen con la luz del sector): sus partes
que no dan luz se pintan oscuras para que no «brillen».

Luces y fuegos
- COLUA0*   lámpara de pie → farola: poste de hierro con pie de campana y un farol de cuatro cristales
            con una vela dentro (el cristal da la luz).
- CANDA0*   vela → vela de sebo con chorreones en un plato de barro.
- CBRAA0*   candelabro → candelabro de pie de hierro forjado: trípode de volutas, nudos y cinco velas.
- TBLU/TGRN/TREDA0-D0*  antorchas altas → hachones: vara de hierro retorcido sobre trípode con una
            jaula (cresta) de hierro arriba y un fuego fatuo del color (azul, verde, rojo) que se mueve.
- SMBT/SMGT/SMRTA0-D0*  antorchas bajas → braseros pequeños de trípode con fuego fatuo del color.
- FCANA0-C0*  barril ardiendo → brasero grande de duelas de hierro, lleno de brasas y leña ardiendo.
Piedra y madera
- COL1A0    columna alta verde → columna de piedra comida por la hiedra.
- COL2A0    columna corta verde → fuste de columna roto, con verdín y un trozo caído.
- COL3A0    columna alta roja → pilar de ladrillo de tejar con basa y remate de piedra.
- COL4A0    columna corta roja → pilar de ladrillo desmochado (se le han caído ladrillos).
- COL5A0-B0 columna con corazón → columna corta con un nido de cuervo y, dentro, un huevo de carne
            que late (B: hinchado), con plumas negras.
- COL6A0    columna roja con calavera → pilar corto de ladrillo con una calavera encima.
- ELECA0    columna técnica → la picota (rollo) del pueblo: fuste de granito sobre gradas, argollas de
            hierro con cadena y un remate de bola.
- SMITA0    estalagmita → menhir con cazoletas talladas y piedras al pie.
- SMT2A0    (sin uso en el juego) → mojón de piedra.
- TRE1A0    árbol quemado → olivo muerto retorcido.
- TRE2A0    árbol grande → alcornoque seco, con la corteza de corcho y el tronco descorchado.
- CEYEA0-C0*  ojo maligno → el ojo de la meiga en un tarro de cristal sobre un pie de madera torneada:
            mira a un lado, al frente y al otro (pupila de cabra).
- FSKUA0-C0*  calaveras flotantes → tres calaveras ardiendo sobre una peña.
Colgados del techo (sin gore excesivo)
- GOR1A0-C0 → ahorcado con un saco en la cabeza que patalea y gira.
- GOR2A0    → saco de arpillera colgado con un bulto humano dentro y una mano que asoma.
- GOR3A0    → pelele de paja ahorcado (el muñeco de Goya), con cara pintada.
- GOR4A0    → el cerdo de la matanza colgado del camal.
- GOR5A0    → jaula de hierro colgada de una cadena con un esqueleto acurrucado.
Picas y espantapájaros
- POL1A0    → espantapájaros con sombrero de paja y cara de saco cosida.
- POL6A0-B0 → espantapájaros de trapos con calavera de cabra que gira la cabeza.
- POL2A0    → pica con calaveras ensartadas y trapos.
- POL4A0    → calavera en una pica, con pelo y un trapo.
- POL3A0-B0* → montón de huesos y calaveras del osario con velas encendidas (titilan).
- POL5A0    → charco de sangre con unos huesos y un jirón.
Efectos
- PUFFA0-D0 → impacto de bala: chispa de pólvora (A*) y polvo que se abre y se deshace.
- BLUDA0-C0 → salpicadura de sangre (C, B, A).
- TFOGA0-J0* → niebla de teletransporte: llamarada, humo y chispas verdes de brujería.
- IFOGA0-E0* → aparición de objetos: destello blanco-azul con chispas.

Técnica: modelos 3D de primitivas SDF (sdf.py: Render con gancho de materiales, rampas EXACTAS de
PLAYPAL, contorno oscuro de 1 px, luz desde arriba-izquierda-delante; 1 unidad ≈ 1 px) más dos
primitivas propias (Torno: sólidos de revolución; Calavera), y efectos 2D a pleno brillo (fuego con
ruido periódico para que las animaciones cierren el ciclo, chispas, humo).

Uso (determinista; escribe los PNG y <salida>/offsets_decoracion.json):
    ~/.venvs/pesadilla/bin/python tools/arte/decoracion.py --salida arte/sprites [--solo COLUA0,...] [--hoja h.png]
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdf  # noqa: E402
from sdf import (IWAD, V, Box, CappedCone, Ellipsoid, Frame, Group, Prim, Render, Ring,  # noqa: E402
                 RoundCone, Sphere, _len, apply_shine, basis, finish, nrm, rad, rot_axis, rot_x, rot_y,
                 rot_z, vnoise)
from doomgfx import decode_patch, read_palette, read_wad  # noqa: E402

PAL = read_palette(IWAD)
PALARR = np.array(PAL, float)
OUTLINE = 2

# ============================================================================= materiales
_NOMBRES = []
RAMPS = {}


def _mat(nombre, rampa):
    i = len(_NOMBRES)
    _NOMBRES.append(nombre)
    RAMPS[i] = rampa
    return i


HIERRO = _mat('hierro', [5, 110, 108, 106, 104, 102, 100, 97, 94])           # hierro viejo (sin brillo propio)
HIERRO_FB = _mat('hierro_fb', [7, 6, 5, 111, 110, 109, 108, 107, 105, 103])  # hierro de lo que va a pleno brillo
HIERRO_LUZ = _mat('hierro_luz', [6, 239, 238, 237, 236, 76, 74, 72, 70])     # hierro a la luz del fuego
HIERRO_AZUL = _mat('hierro_azul', [7, 246, 245, 244, 243, 242, 241, 206, 205])
HIERRO_VERDE = _mat('hierro_verde', [7, 127, 126, 159, 158, 157, 156, 155])
HIERRO_ROJO = _mat('hierro_rojo', [7, 191, 190, 189, 188, 47, 46, 45])
OXIDO = _mat('oxido', [2, 239, 238, 237, 236, 13, 76, 74])                     # herrumbre
MADERA = _mat('madera', [2, 239, 238, 237, 143, 141, 139, 137, 135])           # madera vieja gris-parda
MADERA_FB = _mat('madera_fb', [2, 239, 238, 237, 236, 79, 78, 77, 76])
TORNEADO = _mat('torneado', [2, 239, 79, 77, 75, 73, 71, 69, 67])              # madera torneada (nogal)
PIEDRA = _mat('piedra', [8, 110, 108, 106, 104, 102, 100, 98, 96, 94, 92])     # granito
CALIZA = _mat('caliza', [2, 239, 143, 141, 139, 137, 135, 133, 131, 129])      # caliza / arenisca parda
MUSGO = _mat('musgo', [127, 159, 158, 157, 156, 155, 154, 153, 152])           # verdín
HIEDRA = _mat('hiedra', [127, 126, 125, 124, 123, 122, 121, 120, 119])
LIQUEN = _mat('liquen', [158, 156, 154, 152, 163])
LADRILLO = _mat('ladrillo', [191, 46, 44, 42, 40, 38, 36, 34, 32, 30])
MORTERO = _mat('mortero', [2, 239, 143, 141, 139, 137, 135])
HUESO = _mat('hueso', [2, 151, 149, 147, 145, 144, 129, 128])
HUESO_FB = _mat('hueso_fb', [2, 239, 151, 150, 149, 148, 147, 146, 145])
HUESO_LUZ = _mat('hueso_luz', [2, 236, 73, 69, 66, 216, 214, 212])
CUENCA = _mat('cuenca', [0])
CERA = _mat('cera', [150, 148, 146, 144, 129, 128, 51, 49])                    # sebo
CERA_FB = _mat('cera_fb', [151, 149, 147, 145, 144, 130, 128])
BARRO = _mat('barro', [239, 77, 75, 73, 71, 69, 67, 65, 64])                   # barro cocido
BARRO_FB = _mat('barro_fb', [2, 239, 238, 78, 76, 74, 72, 70])
CUERDA = _mat('cuerda', [1, 2, 151, 150, 149, 148, 147, 146])                  # esparto
ARPILLERA = _mat('arpillera', [2, 239, 238, 151, 150, 149, 148, 147, 146, 145])
LIENZO = _mat('lienzo', [5, 110, 108, 106, 104, 102, 100, 98, 96])             # camisa de lienzo sucia
PANO = _mat('pano', [0, 2, 239, 238, 237, 15, 14, 13])                        # paño pardo oscuro
PANO_NEGRO = _mat('pano_negro', [0, 8, 7, 6, 5, 111, 110, 109])
PIEL = _mat('piel', [237, 143, 141, 139, 136, 133, 130, 128])                 # piel de muerto
CERDO = _mat('cerdo', [41, 38, 35, 32, 29, 26, 23, 21, 19])
PAJA = _mat('paja', [2, 167, 166, 165, 164, 163, 162, 161])
SANGRE = _mat('sangre', [0, 191, 190, 189, 188, 187, 186, 185, 184])
CARNE = _mat('carne', [46, 43, 40, 37, 34, 31, 28, 25, 22, 20])
PLUMA = _mat('pluma', [0, 8, 7, 6, 5, 111, 110, 245])
RAMITA = _mat('ramita', [2, 239, 238, 237, 236, 141, 139, 137])
CORTEZA = _mat('corteza', [7, 5, 110, 108, 106, 104, 102, 100, 98])           # corteza de olivo (gris)
CORCHO = _mat('corcho', [2, 239, 238, 237, 236, 105, 103, 101, 99, 97])
DESCORCHE = _mat('descorche', [2, 239, 79, 78, 76, 74, 72, 70, 68])               # tronco descorchado (rojizo)
ROCA_FB = _mat('roca_fb', [8, 7, 6, 5, 111, 110, 109, 108, 107])
LIQUIDO = _mat('liquido', [127, 126, 125, 124, 123, 122, 121, 120, 119, 118, 117])   # nivel
CRISTAL = _mat('cristal', [0, 7, 6, 5, 111, 110])                               # cristal vacío
OJO = _mat('ojo', [237, 143, 140, 137, 134, 131, 129, 128, 50])
IRIS = _mat('iris', [235, 233, 221, 218, 215, 162, 161, 160])                  # nivel
PUPILA = _mat('pupila', [0])
VENA = _mat('vena', [47, 46, 45, 44, 43])
BRASA = _mat('brasa', [188, 186, 184, 182, 180, 178, 176, 216, 215, 213])      # nivel
BREA = _mat('brea', [0, 8, 7, 6, 5])
FAROL = _mat('farol', [233, 221, 219, 217, 215, 213, 211, 229, 227, 225, 4])   # cristal encendido (nivel)
GLOW_AZUL = _mat('glow_azul', [246, 244, 206, 204, 202, 200, 198, 196, 194, 192])   # nivel
GLOW_VERDE = _mat('glow_verde', [127, 125, 123, 121, 119, 117, 115, 113, 112])      # nivel
GLOW_ROJO = _mat('glow_rojo', [191, 189, 187, 185, 183, 181, 179, 177, 176, 174])   # nivel
MECHA = _mat('mecha', [0, 8, 2])
TRAPO = _mat('trapo', [0, 2, 191, 190, 189, 47, 45, 43])                        # trapo rojo sucio
TRAPO_GRIS = _mat('trapo_gris', [0, 8, 5, 110, 108, 106, 104, 102])
PELO = _mat('pelo', [0, 8, 7, 2, 239, 238])
CUERNO = _mat('cuerno', [2, 239, 238, 237, 236, 141, 139])
BOTON = _mat('boton', [0, 8, 5, 109])
HUESO_OSARIO = _mat('hueso_osario', [2, 239, 151, 149, 147, 145, 144, 131, 129])   # a pleno brillo, a la luz de las velas
PANO_VERDE = _mat('pano_verde', [0, 8, 127, 126, 125, 124, 123, 122])
TELA = _mat('tela', [237, 143, 141, 139, 137, 135, 133, 131, 129])                  # trapo claro (cara del pelele)

LEVEL = (LIQUIDO, IRIS, BRASA, FAROL, GLOW_AZUL, GLOW_VERDE, GLOW_ROJO)
EMISSIVE = (FAROL, BRASA, GLOW_AZUL, GLOW_VERDE, GLOW_ROJO, IRIS, PUPILA, CUENCA)

# Fuego (2D, pleno brillo), de lo más caliente a lo más frío. Índices exactos de PLAYPAL.
FUEGO_NAT = [4, 225, 227, 229, 249, 211, 213, 215, 216, 218, 219, 221, 232, 235]
FUEGO_AZUL = [4, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205]
FUEGO_VERDE = [4, 226, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123]
FUEGO_ROJO = [4, 225, 228, 249, 215, 176, 177, 178, 179, 180, 181, 182, 183, 184, 186]
COLORES = {
    'azul': dict(fuego=FUEGO_AZUL, glow=GLOW_AZUL, hierro=HIERRO_AZUL, chispa=[4, 192, 194, 196, 198, 200, 202]),
    'verde': dict(fuego=FUEGO_VERDE, glow=GLOW_VERDE, hierro=HIERRO_VERDE, chispa=[4, 226, 112, 114, 116, 118, 120]),
    'rojo': dict(fuego=FUEGO_ROJO, glow=GLOW_ROJO, hierro=HIERRO_ROJO, chispa=[4, 225, 229, 215, 176, 179, 182]),
    'nat': dict(fuego=FUEGO_NAT, glow=BRASA, hierro=HIERRO_LUZ, chispa=[4, 225, 229, 249, 215, 218, 221]),
}


# ============================================================================= primitivas propias
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


class Fn(Prim):
    """Primitiva a partir de una función de distancia f(P) y una esfera envolvente."""

    def __init__(self, f, c, r, mat):
        self.f, self.mat, self.bc, self.br = f, mat, V(c), r

    def sdf(self, P):
        return self.f(P)


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def _ell(q, c, r):
    p = (q - V(c)) / V(r)
    k0 = _len(p)
    k1 = _len(p / V(r))
    return k0 * (k0 - 1) / np.maximum(k1, 1e-9)


class Calavera(Prim):
    """Calavera humana con las cuencas y la nariz talladas. F: y' arriba, z' hacia donde mira;
    s: escala (s = 1 → unos 10 px de alto, de la barbilla a la coronilla)."""

    def __init__(self, F, s, mat, mandibula=True):
        self.F, self.s, self.mat, self.mand = F, s, mat, mandibula
        self.bc = F.p((0, 5.2 * s, 0.3 * s))
        self.br = 6.4 * s

    def sdf(self, P):
        q = self.F.to_local(P) / self.s
        d = _ell(q, (0, 6.0, -0.5), (4.0, 3.9, 4.5))
        d = smin(d, _ell(q, (0, 3.0, 1.5), (3.0, 2.6, 2.6)), 1.0)
        for sx in (-1, 1):
            d = smin(d, _len(q - V(sx * 2.4, 3.7, 1.9)) - 1.3, 0.6)
        if self.mand:
            d = smin(d, _ell(q, (0, 1.1, 1.7), (2.3, 1.1, 2.1)), 0.7)
        for sx in (-1, 1):
            d = np.maximum(d, -(_len(q - V(sx * 1.85, 4.3, 3.7)) - 1.0))
        d = np.maximum(d, -(_ell(q, (0, 2.75, 4.0), (0.5, 0.75, 0.9))))
        return d * self.s


def calavera_cuencas(F, s, Q):
    """Máscara (puntos del modelo Q) de las cuencas y la nariz de una Calavera (para pintarlas)."""
    q = F.to_local(Q) / s
    m = np.zeros(len(Q), bool)
    for sx in (-1, 1):
        m |= _len(q - V(sx * 1.85, 4.3, 3.7)) < 1.18
    m |= _ell(q, (0, 2.75, 4.0), (0.6, 0.85, 1.1)) < 0
    dientes = (np.abs(q[:, 1] - 1.95) < 0.35) & (q[:, 2] > 2.6) & (np.abs(q[:, 0]) < 1.9)
    return m, dientes


def cil(a, b, r, mat, r2=None):
    return CappedCone(V(a), V(b), r, r if r2 is None else r2, mat)


def cadena_pts(pts, r0, r1, mat):
    """Tubo por una polilínea (radio de r0 a r1)."""
    n = len(pts) - 1
    out = []
    for i in range(n):
        ra = r0 + (r1 - r0) * i / n
        rb = r0 + (r1 - r0) * (i + 1) / n
        out.append(RoundCone(V(pts[i]), V(pts[i + 1]), ra, rb, mat))
    return out


def bezier(p0, p1, p2, n=6):
    p0, p1, p2 = V(p0), V(p1), V(p2)
    return [(1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t * t * p2 for t in np.linspace(0, 1, n + 1)]


# ============================================================================= render
_RENDERS = {}


def render_para(tilt):
    if tilt not in _RENDERS:
        _RENDERS[tilt] = Render(RAMPS, hook=materiales, level_mats=LEVEL, emissive=EMISSIVE, tilt=rad(tilt))
    return _RENDERS[tilt]


class Lienzo:
    """Imagen RGBA (numpy) con la proyección del modelo: px(p) → (x, y) continuos en la imagen."""

    def __init__(self, img, hw, top, Uc, T):
        self.img, self.hw, self.top, self.Uc, self.T = img, hw, top, Uc, T

    def px(self, p):
        q = V(p) + self.T
        return self.hw + q[0], self.top - q @ self.Uc

    def margen(self, arriba=0, lados=0, abajo=0):
        H, W = self.img.shape[:2]
        out = np.zeros((H + arriba + abajo, W + 2 * lados, 4), np.uint8)
        out[arriba:arriba + H, lados:lados + W] = self.img
        self.img = out
        self.hw += lados
        self.top += arriba
        return self


def trazar(groups, extras, tilt):
    """Traza el modelo (suelo en y = 0) con contorno → Lienzo."""
    t = rad(tilt)
    Uc = V(0, math.cos(t), -math.sin(t))
    low = min(g.model_bound()[0] @ Uc - g.model_bound()[1] for g in groups)
    lift = max(0.0, (2.0 - low) / math.cos(t))
    T = V(0, lift, 0)
    for g in groups:
        g.xf = (np.eye(3), T, 1.0)
    ex = dict(extras, t=T, tilt=t, Uc=Uc, Dc=V(0, -math.sin(t), -math.cos(t)))
    R = render_para(tilt)
    out, depth = R.render(groups, ex, 1)
    if ex.get('lineas'):
        out = lineas_interiores(out, depth, R.palarr, ex['lineas'])
    img = np.array(finish(out, depth, R.palarr, OUTLINE))
    img[img[..., 3] < 128] = 0
    xs, ys = [], []
    for g in groups:
        c, r = g.model_bound()
        xs += [c[0] - r, c[0] + r]
        ys += [c @ Uc - r, c @ Uc + r]
    hw = int(math.ceil(max(-min(xs), max(xs)))) + 2
    top = int(math.ceil(max(ys))) + 2
    return Lienzo(img, hw, top, Uc, T)


def lineas_interiores(out, depth, palarr, umbral, oscuro=2):
    H, W = out.shape
    res = out.copy()
    op = out >= 0
    for y, x in zip(*np.nonzero(op)):
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            yy, xx = y + dy, x + dx
            if 0 <= yy < H and 0 <= xx < W and op[yy, xx] and depth[yy, xx] < depth[y, x] - umbral:
                if palarr[out[y, x]].sum() > 3 * 40:
                    res[y, x] = oscuro
                break
    return res


def recortar(L, apoyo='suelo', sup=None):
    """Recorta lo transparente → (Image, [izq, sup]). apoyo 'suelo': sup = fila del suelo bajo el
    centro del objeto; 'techo': sup dado (lo de arriba toca el techo); 'centro': sup dado respecto al
    punto (0, 0, 0) del modelo."""
    a = L.img
    vis = a[..., 3] > 0
    ys, xs = np.nonzero(vis)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    out = a[y0:y1, x0:x1].copy()
    ax, ay = L.px((0, 0, 0))
    izq = int(round(ax - x0))
    if apoyo == 'suelo':
        s = int(round(ay - y0))
        s = max(out.shape[0] - 4, min(out.shape[0] + 2, s))
    elif apoyo == 'techo':
        s = sup
    else:   # centro: sup = altura del punto (0,0,0) sobre el origen del objeto
        s = int(round(ay - y0)) + sup
    return Image.fromarray(out, 'RGBA'), [izq, s]


# ============================================================================= efectos 2D
SS2 = 4


def malla(W, H, cx, cy):
    """Coordenadas de las submuestras (x a la derecha, y hacia ARRIBA) respecto a (cx, cy)."""
    jj, ii = np.meshgrid(np.arange(W * SS2), np.arange(H * SS2))
    return (jj + 0.5) / SS2 - cx, cy - (ii + 0.5) / SS2


def fbm(x, y, z, esc, sem):
    P = np.column_stack([x.ravel(), y.ravel(), np.broadcast_to(z, x.shape).ravel()])
    n = (vnoise(P, esc, sem) * 0.55 + vnoise(P, esc * 2.07, sem + 1) * 0.3
         + vnoise(P, esc * 4.3, sem + 2) * 0.15)
    return n.reshape(x.shape)


def reducir(campo, umbral, W, H, minimo=6):
    on = campo > umbral
    cnt = on.reshape(H, SS2, W, SS2).sum(axis=(1, 3))
    suma = np.where(on, campo, 0).reshape(H, SS2, W, SS2).sum(axis=(1, 3))
    return cnt >= minimo, suma / np.maximum(cnt, 1)


def pintar_calor(img, calor, rampa, detras=False, gamma=1.0, umbral=0.04, minimo=6):
    """Calor (submuestras; 1 = lo más caliente) → píxeles de la rampa (índices PLAYPAL)."""
    H, W = img.shape[:2]
    vis, hm = reducir(calor, umbral, W, H, minimo)
    if detras:
        vis &= img[..., 3] == 0
    n = len(rampa)
    idx = np.clip(((1.0 - np.clip(hm, 0, 1)) ** gamma) * (n - 1) + 0.35, 0, n - 1).astype(int)
    col = PALARR[np.array(rampa)].astype(np.uint8)
    img[vis, :3] = col[idx[vis]]
    img[vis, 3] = 255
    return vis


def calor_llama(x, y, alto, ancho, fase, sem, lengua=1.0, vaiven=1.0, base=0.0):
    """Campo de calor de una llama con la base en (0, 0) (y hacia arriba): alto y ancho en px.
    fase en [0, 1): el ruido recorre un círculo, así que fase 0 y 1 dan lo mismo (ciclos cerrados)."""
    a = 2 * math.pi * fase
    t = y / alto
    tc = np.clip(t, 0, 1.2)
    centro = vaiven * ancho * 0.22 * (math.sin(a) * tc ** 1.6 + 0.5 * math.sin(2 * a + 1.3) * tc ** 3)
    w = 0.5 * ancho * np.clip(tc + 0.12, 0, None) ** 0.38 * np.clip(1.05 - tc, 0, None) ** 0.9
    w = np.maximum(w, 0.3)
    d = np.abs(x - centro) / w
    zc, zs = math.cos(a) * 1.3, math.sin(a) * 1.3
    n = fbm(x * 0.33 + zs, y * 0.2 - zc * 1.5, zc + 7.0, 1.0, sem)
    calor = (1 - d) * (1.05 - 0.75 * tc) - (n - 0.45) * lengua * (0.35 + 1.1 * tc)
    calor = np.where(y < base, calor - (base - y) * 0.9, calor)
    calor = calor - np.clip(t - 0.92, 0, None) * 2.2          # nada de jirones sueltos muy por encima
    return calor


def llama(img, cx, cy, alto, ancho, fase, rampa, sem, detras=False, lengua=1.0, vaiven=1.0, gamma=1.0):
    H, W = img.shape[:2]
    x, y = malla(W, H, cx, cy)
    c = calor_llama(x, y, alto, ancho, fase, sem, lengua, vaiven)
    return pintar_calor(img, c, rampa, detras=detras, gamma=gamma)


def punto(img, x, y, idx, encima=True):
    H, W = img.shape[:2]
    xi, yi = int(math.floor(x)), int(math.floor(y))
    if 0 <= xi < W and 0 <= yi < H and (encima or img[yi, xi, 3] == 0):
        img[yi, xi, :3] = PAL[idx]
        img[yi, xi, 3] = 255


def chispas(img, cx, cy, n, sem, rampa, alto=12.0, ancho=6.0, fase=0.0, largo=(1, 2), sube=1.0):
    """Pavesas que suben de (cx, cy): cada una sube con la fase (ciclo cerrado) y se apaga."""
    rng = np.random.default_rng(sem)
    for _ in range(n):
        x0 = rng.uniform(-ancho, ancho)
        f0 = rng.uniform(0, 1)
        f = (f0 + fase) % 1.0
        h = f * alto * sube
        x = cx + x0 * (0.5 + f) + math.sin(f * 6.0 + x0) * 1.2
        y = cy - h
        k = min(int(f * len(rampa)), len(rampa) - 1)
        L = int(rng.integers(largo[0], largo[1] + 1))
        for j in range(L):
            punto(img, x, y + j, rampa[min(k + j, len(rampa) - 1)])


def anclas(img):
    H, W = img.shape[:2]
    for x in (0, W - 1):
        if img[H - 1, x, 3] == 0:
            img[H - 1, x] = (0, 0, 0, 1)
    return img


# ============================================================================= gancho de materiales
def materiales(P, mat, inten, nz, nr, spec, lvl, ex):
    Q = P - ex['t']
    fn = GANCHOS.get(ex.get('obj'))
    if fn is not None:
        fn(Q, mat, inten, nz, nr, spec, lvl, ex)
    # luz de una llama sobre lo que tiene cerca (tiñe el hierro del color del fuego)
    for (c, r, color) in ex.get('luces', ()):
        dist = _len(Q - V(c))
        cerca = dist < r
        k = np.clip(1 - dist / r, 0, 1)
        tinte = COLORES[color]['hierro']
        for base in (HIERRO_FB, HIERRO, OXIDO):
            m = cerca & (mat == base) & (k > 0.25)
            mat[m] = tinte
            inten[m] = np.clip(inten[m] * (0.7 + 0.8 * k[m]) + 0.25 * k[m], 0, 1.2)
        for base, luz in ((HUESO_FB, HUESO_LUZ), (HUESO_OSARIO, HUESO_LUZ), (CERA_FB, CERA_FB)):
            m = cerca & (mat == base) & (k > 0.3)
            mat[m] = luz
            inten[m] = np.clip(inten[m] + 0.3 * k[m], 0, 1.2)


GANCHOS = {}


def gancho(nombre):
    def deco(fn):
        GANCHOS[nombre] = fn
        return fn
    return deco


def nivel(lvl, m, val, mat_id):
    n = len(RAMPS[mat_id])
    lvl[m] = np.clip(val * (n - 1), 0, n - 1)


def retorcido(Q, mat, inten, mats, paso=3.0, fuerza=0.25):
    """Rayas en espiral del hierro retorcido (forja) en los materiales dados (eje vertical)."""
    m = np.isin(mat, mats)
    th = np.arctan2(Q[m, 0], Q[m, 2])
    s = np.sin(th * 2 + Q[m, 1] * 2 * math.pi / paso)
    inten[m] *= 1 - fuerza * (s > 0.35)


# ============================================================================= COLU: farola
def farola():
    F = Frame((0, 0, 0))
    a, h, yc = 4.3, 4.9, 35.5                     # medio lado y media altura del cristal; centro del farol
    pie = Torno(F, [(0, 5.6), (1.0, 5.6), (1.7, 4.6), (2.6, 3.4), (3.6, 2.5), (5.0, 1.8), (6.0, 1.6)], HIERRO_FB)
    poste = cil((0, 5, 0), (0, yc - h - 2.4, 0), 1.6, HIERRO_FB, 1.35)
    nudos = [Ring(Frame((0, 11, 0)), 2.0, 2.0, 0.6, HIERRO_FB), Ring(Frame((0, 21, 0)), 1.8, 1.8, 0.55, HIERRO_FB),
             Sphere((0, yc - h - 2.2, 0), 2.0, HIERRO_FB)]
    R45 = rot_y(rad(32))
    caja = []
    # farol: plato, cuatro montantes, cristales, tejadillo, remate y anilla
    caja.append(Torno(F * Frame((0, yc - h - 1.4, 0)), [(0, 1.4), (0.7, 3.0), (1.4, a + 0.9), (1.9, a + 0.9)],
                      HIERRO_FB))
    cristal = Box((0, yc, 0), (a, h, a), R45, 0.1, FAROL)
    for sx in (-1, 1):
        for sz in (-1, 1):
            c = V(0, yc, 0) + R45 @ V(sx * (a + 0.15), 0, sz * (a + 0.15))
            caja.append(Box(c, (0.6, h + 0.1, 0.6), R45, 0.1, HIERRO_FB))
    caja.append(Box((0, yc - h - 0.4, 0), (a + 0.7, 0.5, a + 0.7), R45, 0.15, HIERRO_FB))
    caja.append(Box((0, yc + h + 0.4, 0), (a + 0.8, 0.5, a + 0.8), R45, 0.15, HIERRO_FB))
    techo = [Fn(lambda P: _piramide(P, V(0, yc + h + 0.8, 0), 4.8, a + 1.5, R45), (0, yc + h + 3.2, 0), 8.0,
                HIERRO_FB),
             Sphere((0, yc + h + 5.8, 0), 1.1, HIERRO_FB),
             Ring(Frame((0, yc + h + 7.5, 0), rot_x(rad(90))), 1.3, 1.3, 0.42, HIERRO_FB)]
    g = [Group([pie, poste] + nudos[:2], k=0.6), Group([nudos[2]] + caja), Group([cristal]), Group(techo, k=0.3)]
    return g, {'obj': 'COLU', 'R45': R45, 'yc': yc, 'a': a, 'h': h, 'luces': [((0, yc, 0), 9.5, 'nat')]}


def _piramide(P, base, alto, medio, R):
    """Pirámide de base cuadrada (medio lado «medio») con la base en «base» y punta a «alto»."""
    q = (P - base) @ R
    y = q[:, 1]
    t = np.clip(y / alto, 0, 1)
    h = medio * (1 - t)
    d = np.maximum(np.abs(q[:, 0]), np.abs(q[:, 2])) - h
    d = d * math.cos(math.atan2(medio, alto))
    return np.maximum(d, np.maximum(-y, y - alto))


@gancho('COLU')
def g_farola(Q, mat, inten, nz, nr, spec, lvl, ex):
    m = mat == FAROL
    R45 = ex['R45']
    q = (Q[m] - V(0, ex['yc'], 0)) @ R45
    # en cada cristal: brillo de la vela en el centro, más oscuro hacia el marco; el montante del medio
    u = np.where(np.abs(q[:, 0]) > np.abs(q[:, 2]), q[:, 2], q[:, 0])
    v = q[:, 1]
    r = np.hypot(u / (ex['a'] - 0.2), (v + 0.6) / ex['h'])
    val = 1.05 - 0.75 * r + 0.1 * (nz[m] - 0.5)
    val = np.where(np.abs(u) < 0.35, val - 0.45, val)            # junquillo central
    nivel(lvl, m, val, FAROL)
    retorcido(Q, mat, inten, (HIERRO_FB,), paso=2.5, fuerza=0.18)
    apply_shine(mat, inten, spec, ((HIERRO_FB, 0.5, 10), (HIERRO_LUZ, 0.6, 8)))


# ============================================================================= CAND: vela de sebo
def vela():
    F = Frame((0, 0, 0))
    plato = Torno(F, [(0, 3.6), (0.4, 5.3), (0.9, 6.1), (1.5, 6.5), (1.9, 6.4), (2.05, 5.9)], BARRO_FB)
    charco = Ellipsoid((0.6, 1.9, 0.6), (3.4, 0.5, 3.0), None, CERA_FB)
    cuerpo = Torno(F * Frame((0, 1.6, 0)), [(0, 2.1), (6.0, 1.95), (6.6, 1.75), (6.9, 1.2), (7.0, 0.0)], CERA_FB)
    chorros = [Ellipsoid((-1.5, 5.5, 1.1), (0.55, 1.8, 0.55), None, CERA_FB),
               Ellipsoid((0.9, 4.3, 1.75), (0.6, 2.6, 0.5), None, CERA_FB),
               Sphere((1.2, 2.2, 1.9), 0.7, CERA_FB)]
    mecha = cil((0, 8.4, 0), (0.2, 9.5, 0), 0.32, MECHA)
    g = [Group([plato]), Group([charco, cuerpo] + chorros, k=0.5), Group([mecha])]
    return g, {'obj': 'CAND', 'luces': [((0, 10.5, 0), 6.0, 'nat')]}


@gancho('CAND')
def g_vela(Q, mat, inten, nz, nr, spec, lvl, ex):
    m = mat == CERA_FB
    # la parte de arriba de la vela, traslúcida, encendida por la llama
    k = np.clip((Q[m, 1] - 5.5) / 3.0, 0, 1)
    inten[m] = inten[m] * (1 - 0.4 * k) + 0.55 * k
    apply_shine(mat, inten, spec, ((CERA_FB, 0.35, 6), (BARRO_FB, 0.2, 6)))


# ============================================================================= CBRA: candelabro
CBRA_VELAS = [((-11.0, 44.5, 0.0), 5.5), ((11.0, 44.5, 0.0), 5.5), ((0.0, 50.0, 0.0), 6.5),
              ((-5.6, 47.0, -5.0), 5.0), ((5.6, 47.0, 5.0), 5.0)]


def candelabro():
    F = Frame((0, 0, 0))
    pz = []
    # trípode de volutas
    for k in range(3):
        a = rad(90 + 120 * k + 15)
        d = V(math.sin(a), 0, math.cos(a))
        pts = bezier(V(0, 9.5, 0), d * 6.5 + V(0, 5.5, 0), d * 9.5 + V(0, 0.9, 0), 5)
        pz += cadena_pts(pts, 1.05, 0.75, HIERRO_FB)
        pz.append(Ring(Frame(d * 10.2 + V(0, 1.6, 0), basis(np.cross(d, V(0, 1, 0)))), 1.2, 1.2, 0.5, HIERRO_FB))
    pz.append(Torno(F, [(8.0, 1.0), (9.3, 2.2), (10.5, 1.2)], HIERRO_FB))
    fuste = [cil((0, 9, 0), (0, 42, 0), 0.95, HIERRO_FB, 0.85),
             Ellipsoid((0, 15, 0), (1.9, 1.4, 1.9), None, HIERRO_FB),
             Ellipsoid((0, 27, 0), (2.2, 1.7, 2.2), None, HIERRO_FB),
             Ellipsoid((0, 40.5, 0), (1.8, 1.3, 1.8), None, HIERRO_FB)]
    brazos = []
    for (c, h) in CBRA_VELAS:
        c = V(c)
        if abs(c[0]) < 1 and abs(c[2]) < 1:
            brazos.append(cil((0, 41, 0), (0, c[1] - 1.0, 0), 0.9, HIERRO_FB))
        else:
            d = nrm(V(c[0], 0, c[2]))
            r = math.hypot(c[0], c[2])
            pts = bezier(V(0, 40.0, 0), d * (r * 0.55) + V(0, 35.0, 0), d * r + V(0, c[1] - 1.2, 0), 6)
            brazos += cadena_pts(pts, 0.8, 0.7, HIERRO_FB)
            # voluta bajo el brazo
            brazos.append(Ring(Frame(d * (r * 0.42) + V(0, 37.4, 0), basis(np.cross(d, V(0, 1, 0)))), 1.25, 1.25,
                               0.45, HIERRO_FB))
        brazos.append(Torno(Frame(c + V(0, -1.6, 0)), [(0, 0.7), (0.6, 1.9), (1.1, 2.3), (1.4, 2.2)], HIERRO_FB))
    velas = []
    for i, (c, h) in enumerate(CBRA_VELAS):
        c = V(c)
        velas.append(Torno(Frame(c + V(0, -0.6, 0)), [(0, 1.05), (h - 0.6, 0.95), (h, 0.55), (h + 0.15, 0)], CERA_FB))
        velas.append(Ellipsoid(c + V(0.7 if i % 2 else -0.7, h * 0.45, 0.6), (0.4, h * 0.3, 0.4), None, CERA_FB))
    g = [Group(pz, k=0.4), Group(fuste, k=0.5), Group(brazos, k=0.3), Group(velas, k=0.25)]
    luces = [(V(c) + V(0, h + 1.5, 0), 5.0, 'nat') for c, h in CBRA_VELAS]
    return g, {'obj': 'CBRA', 'luces': luces}


@gancho('CBRA')
def g_candelabro(Q, mat, inten, nz, nr, spec, lvl, ex):
    retorcido(Q, mat, inten, (HIERRO_FB,), paso=2.2, fuerza=0.15)
    apply_shine(mat, inten, spec, ((HIERRO_FB, 0.45, 10), (CERA_FB, 0.3, 6), (HIERRO_LUZ, 0.6, 8)))


# ============================================================================= hachones y braseros de color
def hachon(alto, color):
    """Antorcha alta: trípode, vara de hierro retorcido y jaula de hierro arriba con la brea."""
    F = Frame((0, 0, 0))
    hc = alto - 30.0                       # base de la jaula
    pz = []
    for k in range(3):
        a = rad(100 + 120 * k)
        d = V(math.sin(a), 0, math.cos(a))
        pts = bezier(V(0, 10.0, 0), d * 4.0 + V(0, 4.0, 0), d * 7.5 + V(0, 0.8, 0), 4)
        pz += cadena_pts(pts, 0.9, 0.7, HIERRO_FB)
        pz.append(Sphere(d * 7.8 + V(0, 0.9, 0), 1.0, HIERRO_FB))
    pz += [cil((0, 1, 0), (0, hc + 1, 0), 1.45, HIERRO_FB, 1.2),
           Ellipsoid((0, 10.3, 0), (1.9, 1.5, 1.9), None, HIERRO_FB),
           Ellipsoid((0, hc * 0.55, 0), (1.7, 1.3, 1.7), None, HIERRO_FB)]
    jaula = [Torno(F * Frame((0, hc, 0)), [(0, 1.2), (1.2, 2.6), (2.6, 3.6), (3.2, 3.7)], HIERRO_FB)]
    for k in range(6):
        a = rad(k * 60 + 15)
        d = V(math.sin(a), 0, math.cos(a))
        pts = bezier(d * 3.2 + V(0, hc + 2.6, 0), d * 5.4 + V(0, hc + 6.5, 0), d * 5.0 + V(0, hc + 11.5, 0), 4)
        jaula += cadena_pts(pts, 0.55, 0.5, HIERRO_FB)
        jaula.append(Sphere(d * 5.6 + V(0, hc + 12.0, 0), 0.75, HIERRO_FB))
    jaula.append(Ring(Frame((0, hc + 8.6, 0)), 5.5, 5.5, 0.45, HIERRO_FB))
    brea = [Ellipsoid((0, hc + 6.6, 0), (4.0, 3.4, 4.0), None, BREA)]
    g = [Group(pz, k=0.45), Group(jaula, k=0.25), Group(brea)]
    return g, {'obj': 'HACHON', 'color': color, 'hc': hc,
               'luces': [((0, hc + 10.0, 0), 9.0, color)]}


def brasero_peq(alto, color):
    """Brasero pequeño de trípode: patas de volutas, aro, cuenco de hierro con brasas del color."""
    F = Frame((0, 0, 0))
    hb = alto - 36.0                       # boca del cuenco
    pz = []
    for k in range(3):
        a = rad(100 + 120 * k)
        d = V(math.sin(a), 0, math.cos(a))
        pts = bezier(d * 3.6 + V(0, hb - 6.0, 0), d * 3.0 + V(0, hb * 0.45, 0), d * 8.0 + V(0, 0.9, 0), 6)
        pz += cadena_pts(pts, 0.85, 0.75, HIERRO_FB)
        pz.append(Ring(Frame(d * 8.6 + V(0, 1.4, 0), basis(np.cross(d, V(0, 1, 0)))), 1.1, 1.1, 0.45, HIERRO_FB))
    pz.append(Ring(Frame((0, hb * 0.42, 0)), 3.6, 3.6, 0.45, HIERRO_FB))
    cuenco = [Torno(F * Frame((0, hb - 7.5, 0)), [(0, 1.5), (1.5, 4.2), (3.5, 6.6), (5.8, 8.2), (7.5, 8.8)], HIERRO_FB),
              Ring(Frame((0, hb - 0.2, 0)), 8.6, 8.6, 0.7, HIERRO_FB)]
    for k in range(6):
        a = rad(k * 60)
        cuenco.append(Sphere(V(math.sin(a) * 6.9, hb - 3.4, math.cos(a) * 6.9), 0.6, HIERRO_FB))
    brasas = [Ellipsoid((0, hb - 0.6, 0), (7.2, 2.4, 7.2), None, BREA)]
    rng = np.random.default_rng(11)
    for _ in range(9):
        a, r = rng.uniform(0, 2 * math.pi), rng.uniform(0, 5.0)
        brasas.append(Ellipsoid((math.sin(a) * r, hb + 0.6 + rng.uniform(0, 0.8), math.cos(a) * r),
                                (rng.uniform(1.2, 2.0), rng.uniform(0.8, 1.3), rng.uniform(1.2, 2.0)), None, BREA))
    g = [Group(pz, k=0.35), Group(cuenco, k=0.3), Group(brasas, k=0.5)]
    return g, {'obj': 'BRASERO', 'color': color, 'hb': hb,
               'luces': [((0, hb + 4.0, 0), 11.0, color)]}


@gancho('HACHON')
def g_hachon(Q, mat, inten, nz, nr, spec, lvl, ex):
    glow = COLORES[ex['color']]['glow']
    m = mat == BREA
    # brea encendida: grietas que brillan del color, más arriba más vivas
    hc = ex['hc']
    n2 = vnoise(Q[m], 1.4, 21)
    k = np.clip((Q[m, 1] - (hc + 4.5)) / 4.5, 0, 1)
    viva = (n2 > 0.55 - 0.35 * k)
    idx = np.nonzero(m)[0]
    mat[idx[viva]] = glow
    nivel(lvl, idx[viva], 0.35 + 0.6 * k[viva] + 0.3 * (n2[viva] - 0.5), glow)
    retorcido(Q, mat, inten, (HIERRO_FB,) + tuple(COLORES[c]['hierro'] for c in COLORES), paso=2.6, fuerza=0.2)
    apply_shine(mat, inten, spec, ((HIERRO_FB, 0.5, 10),))


@gancho('BRASERO')
def g_brasero(Q, mat, inten, nz, nr, spec, lvl, ex):
    glow = COLORES[ex['color']]['glow']
    m = mat == BREA
    n2 = vnoise(Q[m], 1.1, 23)
    k = np.clip((Q[m, 1] - (ex['hb'] - 1.0)) / 3.0, 0, 1)
    viva = n2 > 0.62 - 0.4 * k
    idx = np.nonzero(m)[0]
    mat[idx[viva]] = glow
    nivel(lvl, idx[viva], 0.3 + 0.55 * k[viva] + 0.4 * (n2[viva] - 0.5), glow)
    apply_shine(mat, inten, spec, ((HIERRO_FB, 0.5, 10),))


# ============================================================================= FCAN: brasero grande
def r_fcan(y):
    return 9.6 + 1.6 * math.sin(math.pi * np.clip((y - 6.0) / 25.0, 0, 1))


def brasero_grande():
    F = Frame((0, 0, 0))
    pz = []
    n = 12
    for k in range(n):
        a = 2 * math.pi * k / n
        Rk = rot_y(a)
        for y0, y1 in ((6.0, 12.5), (12.5, 19.0), (19.0, 25.5), (25.5, 31.0)):
            ym = (y0 + y1) / 2
            r = float(r_fcan(ym))
            pz.append(Box(Rk @ V(0, ym, r), (1.35, (y1 - y0) / 2 + 0.2, 0.55), Rk @ rot_x(-0.12 * math.cos(math.pi * (ym - 6) / 25)), 0.2, HIERRO_FB))
    aros = [Ring(Frame((0, y, 0)), float(r_fcan(y)) + 0.5, float(r_fcan(y)) + 0.5, 0.7, HIERRO_FB)
            for y in (6.6, 18.5, 30.4)]
    patas = []
    for k in range(3):
        a = rad(30 + 120 * k)
        d = V(math.sin(a), 0, math.cos(a))
        patas += cadena_pts(bezier(d * 8.5 + V(0, 7.0, 0), d * 10.5 + V(0, 3.0, 0), d * 11.5 + V(0, 0.8, 0), 3),
                            1.1, 0.9, HIERRO_FB)
    dentro = [cil((0, 6.5, 0), (0, 29.5, 0), 9.4, BRASA, 10.0)]
    lena = []
    for (a, b, r) in (((-3, 26, 2), (-9.5, 37, -3), 1.9), ((2.5, 26, -1), (8.5, 38.5, 2.5), 2.0),
                      ((0.5, 26, 3), (-1.5, 39, 7.5), 1.7), ((-2, 27, -3), (4.5, 35.0, -7.5), 1.6)):
        lena.append(RoundCone(V(a), V(b), r, r * 0.85, MADERA_FB))
    g = [Group(pz + aros, k=0.0), Group(patas, k=0.4), Group(dentro), Group(lena, k=0.3)]
    return g, {'obj': 'FCAN', 'luces': [((0, 34.0, 0), 16.0, 'nat')], 'lineas': 2.5}


@gancho('FCAN')
def g_fcan(Q, mat, inten, nz, nr, spec, lvl, ex):
    m = mat == BRASA
    n2 = vnoise(Q[m], 0.9, 31)
    k = np.clip((Q[m, 1] - 6) / 24, 0, 1)
    nivel(lvl, m, 0.25 + 0.55 * k + 0.6 * (n2 - 0.5), BRASA)
    m = mat == MADERA_FB
    # extremos de la leña carbonizados y encendidos
    idx = np.nonzero(m)[0]
    q = Q[idx]
    alto = q[:, 1] > 33.5
    n3 = vnoise(q, 1.3, 32)
    brasa = alto & (n3 > 0.45)
    mat[idx[brasa]] = BRASA
    nivel(lvl, idx[brasa], 0.55 + 0.4 * (n3[brasa] - 0.45) * 3, BRASA)
    inten[idx[alto & ~brasa]] *= 0.55
    apply_shine(mat, inten, spec, ((HIERRO_FB, 0.45, 10), (HIERRO_LUZ, 0.6, 8)))


# ============================================================================= composición de luces
def dibujar_llamas(lump):
    """COLU, CAND, CBRA, hachones, braseros y FCAN: modelo + fuego 2D → (Image, offsets)."""
    pre, fr = lump[:4], lump[4]
    f = 'ABCD'.index(fr) / 4.0
    if pre == 'COLU':
        g, ex = farola()
        L = trazar(g, ex, 8)
        return recortar(L)
    if pre == 'CAND':
        g, ex = vela()
        L = trazar(g, ex, 22).margen(arriba=9, lados=3)
        x, y = L.px((0.1, 9.0, 0))
        llamita(L.img, x, y + 0.5, 7.5, 3.8, 0, 3)
        return recortar(L)
    if pre == 'CBRA':
        g, ex = candelabro()
        L = trazar(g, ex, 10).margen(arriba=9, lados=2)
        for i, (c, h) in enumerate(CBRA_VELAS):
            x, y = L.px(V(c) + V(0, h + 0.2, 0))
            llamita(L.img, x, y + 0.5, 6.0 if i != 2 else 7.0, 3.2, i % 2, 40 + i)
        return recortar(L)
    if pre in ('TBLU', 'TGRN', 'TRED'):
        color, alto = {'TBLU': ('azul', 94), 'TGRN': ('verde', 99), 'TRED': ('rojo', 90)}[pre]
        g, ex = hachon(alto - 4, color)
        L = trazar(g, ex, 6).margen(arriba=30, lados=6)
        x, y = L.px((0, ex['hc'] + 7.5, 0))
        sem = {'azul': 51, 'verde': 52, 'rojo': 53}[color]
        llama(L.img, x, y + 2.0, 31.0, 19.0, f, COLORES[color]['fuego'], sem, lengua=1.25)
        chispas(L.img, x, y - 18, 4, sem, COLORES[color]['chispa'], alto=12, ancho=4, fase=f)
        return recortar(L)
    if pre in ('SMBT', 'SMGT', 'SMRT'):
        color, alto = {'SMBT': ('azul', 70), 'SMGT': ('verde', 75), 'SMRT': ('rojo', 66)}[pre]
        g, ex = brasero_peq(alto, color)
        L = trazar(g, ex, 8).margen(arriba=32, lados=4)
        x, y = L.px((0, ex['hb'] + 1.0, 0))
        sem = {'azul': 61, 'verde': 62, 'rojo': 63}[color]
        llama(L.img, x, y + 1.0, 31.0, 20.0, f, COLORES[color]['fuego'], sem, lengua=1.2)
        chispas(L.img, x, y - 18, 4, sem, COLORES[color]['chispa'], alto=14, ancho=5, fase=f)
        return recortar(L)
    if pre == 'FCAN':
        f = 'ABC'.index(fr) / 3.0
        g, ex = brasero_grande()
        L = trazar(g, ex, 10).margen(arriba=30, lados=4)
        x, y = L.px((0, 29.0, 0))
        llama(L.img, x, y, 33.0, 23.0, f, FUEGO_NAT, 71, lengua=1.2)
        chispas(L.img, x, y - 20, 5, 72, COLORES['nat']['chispa'], alto=14, ancho=6, fase=f)
        return recortar(L)
    raise KeyError(lump)


# ============================================================================= utilidades de piedra
def h2(a, b, sem=0):
    """Hash entero → [0, 1) (vectorizado) para variar ladrillos y sillares."""
    n = (np.asarray(a, np.int64) * 73856093) ^ (np.asarray(b, np.int64) * 19349663) ^ (sem * 83492791)
    n = (n ^ (n >> 13)) * 1274126177
    n = n ^ (n >> 16)
    return (n & 0xffff) / 65536.0


def ladrillos(Q, mat, inten, m, c, R, half, alto=4.2, largo=8.4, sem=0, mortero=MORTERO):
    """Aparejo de ladrillo en las caras de una caja (centro c, giro R, semilados half): las juntas
    pasan a «mortero» y cada ladrillo tiene su tono."""
    idx = np.nonzero(m)[0]
    q = (Q[idx] - V(c)) @ R
    ex = np.abs(q[:, 0]) / half[0] > np.abs(q[:, 2]) / half[2]
    u = np.where(ex, q[:, 2] + 0.5 * np.sign(q[:, 0]) * half[2], q[:, 0] + 0.5 * np.sign(q[:, 2]) * half[0])
    y = Q[idx, 1]
    fila = np.floor(y / alto)
    uu = u + (fila % 2) * largo * 0.5
    col = np.floor(uu / largo)
    fy = y / alto - fila
    fu = uu / largo - col
    junta = (fy < 0.22) | (fu < 0.11)
    mat[idx[junta]] = mortero
    inten[idx[junta]] *= 0.8
    var = h2(fila, col + np.where(ex, 1000, 0), sem)
    ok = ~junta
    inten[idx[ok]] *= 0.78 + 0.4 * var[ok]
    # algún ladrillo más oscuro (requemado)
    inten[idx[ok & (var > 0.86)]] *= 0.7


def sillares(Q, mat, inten, m, alto=9.0, sem=0, fuerza=0.45):
    """Juntas horizontales de los tambores de una columna (y algo de variación por tambor)."""
    idx = np.nonzero(m)[0]
    y = Q[idx, 1]
    f = np.floor(y / alto)
    fy = y / alto - f
    inten[idx] *= 0.85 + 0.25 * h2(f, 7, sem)
    j = fy < 0.09
    inten[idx[j]] *= 1 - fuerza


def verdin(Q, mat, inten, m, nivel_y, sem=0, cantidad=0.5, escala=0.35, nuevo=None):
    """Manchas de verdín/musgo: más abajo y en lo alto (donde se acumula el agua)."""
    idx = np.nonzero(m)[0]
    n = vnoise(Q[idx], escala, sem) * 0.7 + vnoise(Q[idx], escala * 2.6, sem + 1) * 0.3
    y = Q[idx, 1]
    k = np.clip(1 - y / nivel_y, 0, 1) * 0.35
    v = n + k > 1 - cantidad
    mat[idx[v]] = MUSGO if nuevo is None else nuevo


def hojas_hiedra(pts, n_por, sem, r=1.7, fuera=1.6):
    """Hojas (elipsoides aplastados) a lo largo de una polilínea de tallo."""
    rng = np.random.default_rng(sem)
    out = []
    for i in range(len(pts) - 1):
        a, b = V(pts[i]), V(pts[i + 1])
        for _ in range(n_por):
            t = rng.uniform(0, 1)
            p = a + (b - a) * t
            rad_dir = nrm(V(p[0], 0, p[2]) + rng.normal(0, 0.4, 3) * V(1, 0, 1) + V(0, 1e-3, 0))
            c = p + rad_dir * fuera * rng.uniform(0.4, 1.0) + V(0, rng.uniform(-1, 1), 0)
            M = basis(rad_dir + V(0, rng.uniform(-0.3, 0.6), 0))
            rr = r * rng.uniform(0.75, 1.15)
            out.append(Ellipsoid(c, (rr, rr * 0.85, 0.55), M, HIEDRA))
    return out


def hiedra_espiral(radio, y0, y1, vueltas, a0, sem, n_por=3, ruido=0.8, r_hoja=1.7):
    rng = np.random.default_rng(sem)
    pts = []
    n = 14
    for i in range(n + 1):
        t = i / n
        a = a0 + vueltas * 2 * math.pi * t + rng.normal(0, 0.15)
        rr = radio + rng.uniform(0, ruido)
        pts.append(V(math.sin(a) * rr, y0 + (y1 - y0) * t, math.cos(a) * rr))
    tallo = cadena_pts(pts, 0.5, 0.35, RAMITA)
    return tallo, hojas_hiedra(pts, n_por, sem + 1, r=r_hoja)


# ============================================================================= COL1-COL6: columnas
def basa_capitel(F, y0, r):
    """Basa ática sencilla (plinto + toro) en y0 para un fuste de radio r."""
    return [Box(F.p((0, y0 + 2.2, 0)), (r + 3.2, 2.2, r + 3.2), rot_y(rad(20)), 0.6, CALIZA),
            Ring(Frame(F.p((0, y0 + 5.2, 0))), r + 1.2, r + 1.2, 1.3, CALIZA)]


def col_piedra(alto=53, roto=False):
    """COL1 (alta, comida por la hiedra) y COL2 (fuste roto con verdín)."""
    F = Frame((0, 0, 0))
    r = 9.0
    base = basa_capitel(F, 0, r)
    if not roto:
        fuste = [Torno(F * Frame((0, 5.5, 0)), [(0, r + 0.2), (alto * 0.35, r), (alto - 15.5, r - 1.0)], CALIZA)]
        cap = [Ring(Frame((0, alto - 9.6, 0)), r - 0.3, r - 0.3, 1.1, CALIZA),
               Torno(F * Frame((0, alto - 9.2, 0)), [(0, r - 0.4), (2.5, r + 1.0), (4.2, r + 2.4)], CALIZA),
               Box((0, alto - 2.6, 0), (r + 3.6, 2.5, r + 3.6), rot_y(rad(20)), 0.5, CALIZA)]
        tallo, hojas = [], []
        for k, (a0, y1, sem) in enumerate(((0.3, alto - 6, 81), (2.6, alto - 22, 82), (4.4, alto - 12, 83))):
            t, h = hiedra_espiral(r + 0.5, 4.0, y1, 0.55, a0, sem, n_por=4 if k == 0 else 3)
            tallo += t
            hojas += h
        # mata de hiedra que cuelga del capitel
        for i in range(10):
            a = 0.2 + i * 0.33
            hojas.append(Ellipsoid((math.sin(a) * (r + 3.4), alto - 6.5 - (i % 3) * 1.6, math.cos(a) * (r + 3.4)),
                                   (1.8, 1.5, 0.6), basis(V(math.sin(a), 0.2, math.cos(a))), HIEDRA))
        g = [Group(base + fuste + cap, k=0.3), Group(tallo), Group(hojas)]
        return g, {'obj': 'COLPIEDRA', 'alto': alto}
    # fuste roto: el corte es un plano inclinado y dentado; un trozo caído al pie
    corte_n = nrm(V(0.35, 1.0, 0.25))

    def cut(P, h=alto - 8.0):
        n = vnoise(P, 0.45, 91) - 0.5
        return (P - V(0, h, 0)) @ corte_n - n * 4.0

    fuste = Torno(F * Frame((0, 5.5, 0)), [(0, r + 0.2), (alto, r)], CALIZA)
    fuste.cut = cut
    trozo = CappedCone(V(-12.0, 3.4, 5.0), V(-3.0, 3.4, 9.0), 3.6, 3.4, CALIZA)
    piedras = [Ellipsoid((9.5, 1.2, 6.0), (2.2, 1.5, 1.8), rot_y(0.5), CALIZA),
               Ellipsoid((12.0, 1.0, 1.5), (1.4, 1.0, 1.3), None, CALIZA)]
    tallo, hojas = hiedra_espiral(r + 0.4, 4.0, alto - 18, 0.35, 1.0, 85, n_por=3)
    g = [Group(base + [fuste], k=0.3), Group([trozo] + piedras, k=0.2), Group(tallo), Group(hojas)]
    return g, {'obj': 'COLPIEDRA', 'alto': alto, 'roto': True}


@gancho('COLPIEDRA')
def g_colpiedra(Q, mat, inten, nz, nr, spec, lvl, ex):
    m = mat == CALIZA
    sillares(Q, mat, inten, m & (Q[:, 1] > 5.5), alto=10.5, sem=3)
    verdin(Q, mat, inten, m, ex['alto'], sem=5, cantidad=0.42 if ex.get('roto') else 0.3)
    # lo de arriba del fuste roto, más claro (piedra recién partida)
    if ex.get('roto'):
        arriba = (mat == CALIZA) & (nr[:, 1] > 0.6) & (Q[:, 1] > 20)
        inten[arriba] *= 1.15
    h = mat == HIEDRA
    inten[h] *= 0.8 + 0.4 * vnoise(Q[h], 1.3, 7)
    apply_shine(mat, inten, spec, ((HIEDRA, 0.35, 6),))


def col_ladrillo(alto, desmochado=False, calavera=False):
    """COL3 (pilar alto de ladrillo con basa y remate), COL4 (desmochado), COL6 (con calavera)."""
    R = rot_y(rad(28))
    hw = 8.5
    base = [Box((0, 2.4, 0), (hw + 2.6, 2.4, hw + 2.6), R, 0.5, CALIZA),
            Box((0, 5.6, 0), (hw + 1.4, 1.0, hw + 1.4), R, 0.4, CALIZA)]
    tope = alto - (5.5 if not desmochado else 0)
    cuerpo = Box((0, (6.5 + tope) / 2, 0), (hw, (tope - 6.5) / 2, hw), R, 0.3, LADRILLO)
    extra = []
    if desmochado:
        def cut(P):
            q = P @ R
            ci = np.floor(q[:, 0] / 4.2)
            cj = np.floor(q[:, 2] / 4.2)
            hh = tope - 2.0 - 9.0 * h2(ci, cj, 17) ** 1.6 - 3.5 * (q[:, 0] > 1.5)
            return P[:, 1] - hh
        cuerpo.cut = cut
        rng = np.random.default_rng(19)
        for k in range(4):
            a = rng.uniform(0, 2 * math.pi)
            p = V(math.sin(a) * (hw + 6), 1.2, math.cos(a) * (hw + 5))
            extra.append(Box(p, (2.1, 1.1, 1.0), rot_y(rng.uniform(0, 3)), 0.25, LADRILLO))
        extra.append(Box((hw + 4.5, 3.4, 3.0), (2.0, 1.0, 1.1), rot_z(0.5) @ rot_y(0.4), 0.25, LADRILLO))
    else:
        extra += [Box((0, tope + 1.2, 0), (hw + 1.6, 1.2, hw + 1.6), R, 0.4, CALIZA),
                  Box((0, tope + 3.6, 0), (hw + 2.6, 1.6, hw + 2.6), R, 0.5, CALIZA)]
    g = [Group(base + extra, k=0.0), Group([cuerpo])]
    ex = {'obj': 'COLLADRILLO', 'R': R, 'hw': hw, 'tope': tope, 'lineas': 2.0}
    if calavera:
        Fc = Frame((0.5, tope + 5.0, 1.0), rot_y(rad(-12)) @ rot_x(rad(-6)))
        cal = Calavera(Fc, 1.35, HUESO)
        g.append(Group([cal]))
        ex['calavera'] = (Fc, 1.35)
        # chorretones oscuros por el remate
    return g, ex


@gancho('COLLADRILLO')
def g_colladrillo(Q, mat, inten, nz, nr, spec, lvl, ex):
    hw = ex['hw']
    m = mat == LADRILLO
    ladrillos(Q, mat, inten, m, (0, 0, 0), ex['R'], (hw, 1, hw), sem=4)
    # cal vieja en el mortero y salitre abajo
    s = (mat == LADRILLO) & (Q[:, 1] < 16)
    n = vnoise(Q[s], 0.5, 9)
    idx = np.nonzero(s)[0]
    sal = n > 0.62 + Q[s, 1] / 40
    mat[idx[sal]] = MORTERO
    verdin(Q, mat, inten, mat == CALIZA, 6, sem=11, cantidad=0.2)
    if 'calavera' in ex:
        Fc, s = ex['calavera']
        cu, di = calavera_cuencas(Fc, s, Q)
        mh = mat == HUESO
        mat[mh & cu] = CUENCA
        inten[mh & di] *= 0.55
        apply_shine(mat, inten, spec, ((HUESO, 0.4, 8),))


# ----------------------------------------------------------------------------- COL5: nido que late
def col_nido(fr):
    F = Frame((0, 0, 0))
    r = 8.5
    alto = 30.0
    base = basa_capitel(F, 0, r)
    fuste = [Torno(F * Frame((0, 5.5, 0)), [(0, r + 0.2), (alto - 9, r - 0.4)], CALIZA),
             Torno(F * Frame((0, alto - 4.0, 0)), [(0, r - 0.4), (2.0, r + 1.0), (3.2, r + 2.2)], CALIZA),
             Box((0, alto + 0.6, 0), (r + 3.0, 1.8, r + 3.0), rot_y(rad(20)), 0.4, CALIZA)]
    # nido: corona de ramitas y barro
    rng = np.random.default_rng(23)
    ramas = []
    yn = alto + 2.6
    for k in range(34):
        a = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(6.5, 10.0)
        y = yn + rng.uniform(0.5, 5.0)
        d = V(math.cos(a), 0, math.sin(a))
        t = nrm(np.cross(d, V(0, 1, 0)) + V(0, rng.uniform(-0.5, 0.5), 0))
        c = d * rr + V(0, y, 0)
        L = rng.uniform(4, 8)
        ramas.append(RoundCone(c - t * L / 2, c + t * L / 2 + V(0, rng.uniform(-1, 1.5), 0), 0.55, 0.4, RAMITA))
    cuenco = [Torno(F * Frame((0, yn, 0)), [(0, 4.0), (1.5, 7.0), (3.5, 9.2), (5.0, 9.6)], RAMITA)]
    # huevo de carne que late (B: hinchado)
    s = 1.0 if fr == 'A' else 1.16
    huevo = [Ellipsoid((0.5, yn + 6.0 * s, 0.8), (5.2 * s, 6.6 * s, 5.0 * s), rot_z(0.15), CARNE),
             Ellipsoid((-2.5, yn + 4.0, 3.0), (2.4 * s, 2.0 * s, 2.0 * s), None, CARNE)]
    plumas = []
    for k in range(7):
        a = rad(-60 + k * 50 + rng.uniform(-10, 10))
        d = V(math.cos(a), 0, math.sin(a))
        c = d * rng.uniform(7.5, 9.0) + V(0, yn + 4.5, 0)
        tip = c + d * rng.uniform(3, 5) + V(0, rng.uniform(3.5, 6), 0)
        plumas.append(Ellipsoid((c + tip) / 2, (0.6, np.linalg.norm(tip - c) / 2, 1.5), basis(V(0, 0, 1), tip - c),
                                PLUMA))
    g = [Group(base + fuste, k=0.3), Group(cuenco + ramas, k=0.6), Group(huevo, k=1.4), Group(plumas)]
    return g, {'obj': 'COL5', 'yn': yn, 'fr': fr, 'alto': alto}


@gancho('COL5')
def g_col5(Q, mat, inten, nz, nr, spec, lvl, ex):
    m = mat == CALIZA
    sillares(Q, mat, inten, m & (Q[:, 1] > 5.5), alto=8.0, sem=13)
    verdin(Q, mat, inten, m, ex['alto'], sem=15, cantidad=0.35)
    c = mat == CARNE
    idx = np.nonzero(c)[0]
    # venas oscuras que serpentean por el huevo
    n = vnoise(Q[idx] * V(1, 0.4, 1), 0.3, 33)
    n2 = vnoise(Q[idx] * V(1, 0.4, 1), 0.55, 34)
    vena = (np.abs(n - 0.5) < 0.03) | (np.abs(n2 - 0.5) < 0.022)
    mat[idx[vena]] = VENA
    inten[idx] = inten[idx] * 0.75 + 0.18 + 0.1 * (nz[idx] - 0.5) * -1
    if ex['fr'] == 'B':
        inten[idx] = inten[idx] * 1.1 + 0.08
    r = mat == RAMITA
    inten[r] *= 0.75 + 0.5 * vnoise(Q[r], 1.6, 35)
    apply_shine(mat, inten, spec, ((CARNE, 0.75, 10), (PLUMA, 0.5, 6)))


# ----------------------------------------------------------------------------- ELEC: la picota
def picota():
    F = Frame((0, 0, 0))
    gradas = [Torno(F, [(0, 12.6), (4.0, 12.6)], PIEDRA), Torno(F * Frame((0, 4.0, 0)), [(0, 9.8), (4.0, 9.8)], PIEDRA),
              Torno(F * Frame((0, 8.0, 0)), [(0, 7.2), (3.6, 7.2)], PIEDRA)]
    # gradas octogonales: cajas giradas encima de los cilindros recortan el perfil (aspecto tallado)
    fuste = [Torno(F * Frame((0, 11.6, 0)), [(0, 5.4), (2.0, 4.6), (4.0, 4.3), (82.0, 3.7)], PIEDRA)]
    cap = [Torno(F * Frame((0, 93.0, 0)), [(0, 3.8), (2.0, 5.2), (4.0, 6.4), (5.0, 6.4)], PIEDRA),
           Box((0, 99.4, 0), (6.6, 1.5, 6.6), rot_y(rad(15)), 0.4, PIEDRA),
           Torno(F * Frame((0, 100.8, 0)), [(0, 4.6), (7.0, 4.0), (8.0, 5.2), (9.5, 5.2)], PIEDRA),
           Sphere((0, 114.0, 0), 4.4, PIEDRA),
           Torno(F * Frame((0, 117.4, 0)), [(0, 2.4), (3.0, 1.6), (8.0, 0.6), (9.5, 0.0)], PIEDRA)]
    hierro = []
    # cuatro ménsulas de piedra con ganchos de hierro (de ellos se colgaba al reo)
    for k in range(4):
        a = rad(45 + 90 * k + 15)
        d = V(math.sin(a), 0, math.cos(a))
        R = rot_y(a)
        cap.append(Box(d * 6.8 + V(0, 104.5, 0), (1.5, 1.6, 3.4), R, 0.5, PIEDRA))
        cap.append(Box(d * 9.4 + V(0, 103.6, 0), (1.3, 2.2, 1.0), R, 0.5, PIEDRA))
        pts = bezier(d * 9.6 + V(0, 101.6, 0), d * 10.2 + V(0, 97.0, 0), d * 8.6 + V(0, 96.0, 0), 4)
        hierro += cadena_pts(pts, 0.6, 0.5, HIERRO)
    # collar de hierro a media altura con dos argollas y un trozo de cadena con grillete
    hierro.append(Ring(Frame((0, 61.0, 0)), 4.6, 4.6, 0.75, HIERRO))
    for k, a in enumerate((rad(25), rad(150))):
        d = V(math.sin(a), 0, math.cos(a))
        hierro.append(Ring(Frame(d * 5.6 + V(0, 58.4, 0), basis(np.cross(d, V(0, 1, 0)))), 2.4, 2.4, 0.55, HIERRO))
    d = V(math.sin(rad(25)), 0, math.cos(rad(25)))
    y = 55.4
    for i in range(5):
        R = rot_y(rad(25)) if i % 2 else rot_y(rad(25)) @ rot_y(rad(90))
        hierro.append(Ring(Frame(d * 6.0 + V(0, y, 0), R @ rot_x(rad(90)) @ rot_z(rad(90))), 0.9, 1.4, 0.4, HIERRO))
        y -= 2.2
    hierro.append(Ring(Frame(d * 6.0 + V(0, y - 1.0, 0), basis(np.cross(d, V(0, 1, 0)))), 1.8, 1.4, 0.55, HIERRO))
    g = [Group(gradas, k=0.0), Group(fuste + cap, k=0.4), Group(hierro)]
    return g, {'obj': 'PICOTA', 'lineas': 2.0}


@gancho('PICOTA')
def g_picota(Q, mat, inten, nz, nr, spec, lvl, ex):
    m = mat == PIEDRA
    idx = np.nonzero(m)[0]
    # granito moteado; las gradas con juntas verticales
    n = vnoise(Q[idx], 1.7, 41)
    inten[idx] *= 0.85 + 0.3 * n
    y = Q[idx, 1]
    grada = y < 12
    a = np.arctan2(Q[idx, 0], Q[idx, 2])
    junta = grada & ((np.abs(np.sin(a * 4 + 0.4)) < 0.08) | (np.abs((y % 4.0)) < 0.35))
    inten[idx[junta]] *= 0.6
    verdin(Q, mat, inten, m & (Q[:, 1] < 13), 13, sem=43, cantidad=0.25, nuevo=LIQUEN)
    verdin(Q, mat, inten, (mat == PIEDRA) & (Q[:, 1] > 13), 120, sem=44, cantidad=0.06, nuevo=LIQUEN)
    o = mat == HIERRO
    n2 = vnoise(Q[o], 1.5, 45)
    io = np.nonzero(o)[0]
    mat[io[n2 > 0.6]] = OXIDO
    apply_shine(mat, inten, spec, ((HIERRO, 0.45, 10),))


# ----------------------------------------------------------------------------- SMIT: menhir · SMT2: mojón
class Pena(Prim):
    """Elipsoide deformado con ruido (roca): c, radios, giro M, amplitud y escala del ruido."""

    def __init__(self, c, radios, M, amp, esc, sem, mat):
        self.e = Ellipsoid(c, radios, M, mat)
        self.amp, self.esc, self.sem, self.mat = amp, esc, sem, mat
        self.bc, self.br = V(c), float(max(radios)) + amp

    def sdf(self, P):
        d = self.e.sdf(P)
        n = vnoise(P, self.esc, self.sem) * 0.65 + vnoise(P, self.esc * 2.3, self.sem + 1) * 0.35
        return d * 0.8 + (n - 0.5) * self.amp


def menhir():
    M = rot_z(rad(-5)) @ rot_x(rad(-4))
    cuerpo = Pena((0, 31.0, 0), (10.0, 33.0, 7.5), M, 4.0, 0.22, 51, PIEDRA)
    cuerpo.cut = lambda P: -(P[:, 1] + 0.5)
    piedras = []
    rng = np.random.default_rng(52)
    for k in range(6):
        a = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(13, 22)
        s = rng.uniform(2.2, 4.5)
        piedras.append(Pena((math.cos(a) * rr, s * 0.45, math.sin(a) * rr * 0.6), (s * 1.3, s * 0.8, s), rot_y(a), 1.2,
                            0.6, 53 + k, PIEDRA))
    g = [Group([cuerpo]), Group(piedras)]
    return g, {'obj': 'MENHIR', 'M': M, 'lineas': 2.0}


@gancho('MENHIR')
def g_menhir(Q, mat, inten, nz, nr, spec, lvl, ex):
    m = mat == PIEDRA
    idx = np.nonzero(m)[0]
    n = vnoise(Q[idx], 1.3, 55)
    inten[idx] *= 0.82 + 0.35 * n
    # cazoletas y una espiral grabadas en la cara de delante del menhir
    q = Q[idx]
    alto = q[:, 1] > 4
    cz = [(-2.5, 44, 1.6), (3.0, 40, 1.3), (-0.5, 35, 1.1), (2.6, 49, 1.0), (-3.5, 30, 1.2)]
    for (x, y, r) in cz:
        d = np.hypot(q[:, 0] - x, q[:, 1] - y)
        inten[idx[alto & (q[:, 2] > 2) & (d < r)]] *= 0.45
        inten[idx[alto & (q[:, 2] > 2) & (np.abs(d - r) < 0.35)]] *= 1.25
    dx, dy = q[:, 0] - 0.5, q[:, 1] - 20.0
    rr = np.hypot(dx, dy)
    th = np.arctan2(dy, dx)
    esp = (rr < 6.5) & (np.abs(((rr - th * 1.6 / math.pi) % 3.2) - 1.6) < 0.45) & (q[:, 2] > 2)
    inten[idx[esp]] *= 0.55
    verdin(Q, mat, inten, mat == PIEDRA, 30, sem=57, cantidad=0.17, nuevo=LIQUEN)


def mojon():
    cuerpo = Pena((0, 14.0, 0), (6.5, 16.0, 5.0), rot_z(rad(4)), 1.6, 0.35, 61, PIEDRA)
    cuerpo.cut = lambda P: -(P[:, 1] + 0.5)
    piedra = Pena((-9.0, 2.0, 2.0), (3.5, 2.5, 3.0), None, 1.0, 0.5, 62, PIEDRA)
    return [Group([cuerpo]), Group([piedra])], {'obj': 'MENHIR', 'lineas': 2.0}


# ----------------------------------------------------------------------------- TRE1: olivo · TRE2: alcornoque
def rama(p0, d0, largo, r0, r1, curva, sem, n=6, mat=CORTEZA):
    """Rama retorcida: polilínea que gira con ruido → (prims, puntos)."""
    rng = np.random.default_rng(sem)
    pts = [V(p0)]
    d = nrm(d0)
    paso = largo / n
    for i in range(n):
        d = nrm(d + rng.normal(0, curva, 3) + V(0, 0.08, 0))
        pts.append(pts[-1] + d * paso)
    return cadena_pts(pts, r0, r1, mat), pts


def ramificar(p0, d, L, r0, nivel, rng, mat, out, curva=0.25, sube=0.12, abre=(25, 50), hijos=(2, 3), fin=0.35):
    """Rama recursiva: polilínea retorcida de radio r0 → r0·0.62 y, si quedan niveles, 2-3 hijas que
    salen de su mitad alta (abiertas «abre» grados) más la que sigue la punta."""
    n = max(2, int(L / 5))
    pts = [V(p0)]
    dd = nrm(d)
    for i in range(n):
        dd = nrm(dd + rng.normal(0, curva, 3) + V(0, sube, 0))
        pts.append(pts[-1] + dd * (L / n))
    r1 = max(r0 * 0.62, fin)
    out += cadena_pts(pts, r0, r1, mat)
    if nivel <= 0:
        return
    nh = int(rng.integers(hijos[0], hijos[1] + 1))
    for h in range(nh):
        t = rng.uniform(0.45, 0.95) if h < nh - 1 else 1.0
        k = min(int(t * n), n)
        q = pts[k]
        rq = r0 + (r1 - r0) * k / n
        eje = nrm(np.cross(dd, rng.normal(0, 1, 3)))
        ang = rad(rng.uniform(*abre)) * (0.5 if h == nh - 1 else 1.0)
        dh = rot_axis(eje, ang) @ dd
        ramificar(q, dh, L * rng.uniform(0.58, 0.75), max(rq * 0.72, fin), nivel - 1, rng, mat, out, curva, sube,
                  abre, hijos, fin)


def olivo():
    """TRE1: olivo viejo muerto: tronco corto y gordo, retorcido y hueco, ramas abiertas sin hojas."""
    prims = []
    rng = np.random.default_rng(71)
    # tronco: tres fustes que se enroscan (el olivo viejo se abre en «patas»)
    for k, (a, r0) in enumerate(((0.0, 5.2), (2.1, 4.6), (4.2, 4.2))):
        pts = []
        for i in range(8):
            t = i / 7
            ang = a + t * 2.4
            rr = 4.2 * (1 - t) + 2.0
            pts.append(V(math.sin(ang) * rr + 2.0 * t, t * 28.0, math.cos(ang) * rr * 0.8))
        prims += cadena_pts(pts, r0, 2.8, CORTEZA)
    for k in range(6):                                  # raíces que asoman
        a = rad(15 + k * 60)
        d = V(math.sin(a), 0, math.cos(a))
        prims += cadena_pts(bezier(V(0, 6, 0) + d * 3, d * 9 + V(0, 2.5, 0), d * 15 + V(0, 0.3, 0), 3), 3.2, 1.0,
                            CORTEZA)
    ramas = []
    for k, (d, L) in enumerate(((V(-1.0, 0.8, 0.2), 20), (V(1.0, 0.75, -0.2), 22), (V(0.1, 1.0, 0.5), 18),
                                (V(-0.3, 1.0, -0.7), 16))):
        ramificar(V(2.0 + d[0] * 2, 27.0, d[2] * 2), d, L, 2.8, 2, rng, CORTEZA, ramas, curva=0.3, sube=0.06,
                  abre=(25, 55), fin=0.4)
    g = [Group(prims, k=1.8), Group(ramas, k=0.4)]
    return g, {'obj': 'ARBOL', 'lineas': 2.5}


def alcornoque():
    """TRE2: alcornoque seco: tronco gordo de corcho (descorchado abajo), copa ancha de ramas muertas."""
    rng = np.random.default_rng(83)
    tronco = cadena_pts([V(0, -1, 0), V(1.0, 12, 0.5), V(-0.5, 24, 0), V(1.0, 34, -0.5), V(0.5, 40, 0)], 9.0, 7.0,
                        CORCHO)
    for k in range(6):                                  # raíces
        a = rad(10 + k * 60)
        d = V(math.sin(a), 0, math.cos(a))
        tronco += cadena_pts(bezier(V(0, 9, 0) + d * 4, d * 11 + V(0, 3, 0), d * 17 + V(0, 0.5, 0), 3), 4.5, 1.4,
                             CORCHO)
    ramas = []
    for k, (d, L) in enumerate(((V(-1.0, 0.55, 0.15), 41), (V(1.0, 0.5, -0.15), 42), (V(-0.25, 1.0, 0.35), 31),
                                (V(0.4, 0.9, -0.45), 31), (V(0.55, 0.55, 0.9), 27), (V(-0.6, 0.6, -0.8), 27))):
        ramificar(V(0.5, 38.0, 0) + nrm(d) * 3, d, L, 5.2 if k < 2 else 4.2, 3, rng, CORCHO, ramas, curva=0.18,
                  sube=0.1, abre=(28, 50), hijos=(2, 3), fin=0.45)
    g = [Group(tronco, k=2.0), Group(ramas, k=0.6)]
    return g, {'obj': 'ALCORNOQUE', 'lineas': 2.5}


@gancho('ARBOL')
def g_arbol(Q, mat, inten, nz, nr, spec, lvl, ex):
    m = mat == CORTEZA
    idx = np.nonzero(m)[0]
    # corteza del olivo: vetas retorcidas y agujeros
    n = vnoise(Q[idx] * V(1.6, 0.35, 1.6), 1.0, 75)
    inten[idx] *= 0.7 + 0.55 * n
    hueco = vnoise(Q[idx], 0.5, 76) > 0.78
    inten[idx[hueco]] *= 0.4


@gancho('ALCORNOQUE')
def g_alcornoque(Q, mat, inten, nz, nr, spec, lvl, ex):
    m = mat == CORCHO
    idx = np.nonzero(m)[0]
    q = Q[idx]
    # corcho: grietas profundas; el pie del tronco, descorchado (rojizo) en una faja
    n = vnoise(q * V(1.0, 0.4, 1.0), 0.9, 85)
    inten[idx] *= 0.65 + 0.6 * n
    grieta = np.abs(vnoise(q * V(1.3, 0.25, 1.3), 0.8, 86) - 0.5) < 0.05
    inten[idx[grieta]] *= 0.45
    desc = (q[:, 1] > 4) & (q[:, 1] < 24 + 3 * np.sin(np.arctan2(q[:, 0], q[:, 2]) * 2)) & \
        (np.hypot(q[:, 0], q[:, 2]) < 11.5)
    mat[idx[desc]] = DESCORCHE
    inten[idx[desc]] = inten[idx[desc]] * 0.9 + 0.1


# ============================================================================= colgados (GOR1-GOR5)
class Xf:
    """Transformación rígida para posar un cuerpo: mundo = piv + R·(p - piv)."""

    def __init__(self, piv, R):
        self.piv, self.R = V(piv), R

    def p(self, q):
        return self.piv + self.R @ (V(q) - self.piv)

    def M(self, Ml=None):
        return self.R if Ml is None else self.R @ Ml


def cap(X, a, b, r1, r2, mat):
    return RoundCone(X.p(a), X.p(b), r1, r2, mat)


def ell(X, c, radios, mat, Ml=None):
    return Ellipsoid(X.p(c), radios, X.M(Ml), mat)


def cuerda(top, bottom, r=0.55, mat=CUERDA, n=4, sem=0):
    rng = np.random.default_rng(sem)
    pts = [V(top) + (V(bottom) - V(top)) * t + V(rng.normal(0, 0.15), 0, rng.normal(0, 0.15)) * (0 < t < 1)
           for t in np.linspace(0, 1, n + 1)]
    return cadena_pts(pts, r, r, mat)


def ahorcado(fr):
    """GOR1: ahorcado con un saco en la cabeza, manos atadas a la espalda; patalea (A, B, C)."""
    top = 67.0
    yaw = {'A': 0.0, 'B': 18.0, 'C': -16.0}[fr]
    sw = {'A': 0.0, 'B': 4.0, 'C': -5.0}[fr]
    X = Xf((0, top, 0), rot_z(rad(sw)) @ rot_y(rad(yaw)))
    cuerpo, ropa, piel, saco, soga = [], [], [], [], []
    yc = 51.0                                   # centro de la cabeza
    saco.append(ell(X, (0, yc, 0.3), (4.4, 5.4, 4.2), ARPILLERA))
    saco.append(ell(X, (0, yc - 4.5, 0.2), (3.0, 1.6, 3.0), ARPILLERA))
    soga.append(Ring(Frame(X.p((0, yc - 5.3, 0.2)), X.M(rot_x(rad(8)))), 2.6, 2.6, 0.6, CUERDA))
    soga += cuerda(X.p((0, top, -0.5)), X.p((0.6, yc + 1.0, -3.6)), sem=1)
    soga.append(cap(X, (0.6, yc + 1.0, -3.6), (0.4, yc - 4.6, -2.4), 0.6, 0.6, CUERDA))
    # torso con la camisa, hombros caídos
    ropa.append(cap(X, (0, 44.0, 0), (0, 31.0, 0.3), 4.6, 4.0, LIENZO))
    ropa.append(ell(X, (0, 41.5, 0), (6.4, 2.6, 3.4), LIENZO))
    ropa.append(ell(X, (0, 32.0, 0.2), (4.6, 3.0, 3.2), PANO))
    # brazos atados atrás
    for s in (-1, 1):
        ropa.append(cap(X, (s * 5.6, 41.2, -0.4), (s * 6.3, 34.0, -2.2), 1.7, 1.5, LIENZO))
        ropa.append(cap(X, (s * 6.3, 34.0, -2.2), (s * 1.6, 30.0, -4.4), 1.5, 1.3, LIENZO))
    soga.append(Ring(Frame(X.p((0, 30.0, -4.4)), X.M(rot_y(rad(90)))), 1.6, 1.6, 0.45, CUERDA))
    # piernas: según el fotograma
    piernas = {
        'A': [((-2.2, 30, 0), (-2.0, 16.5, 0.6), (-1.8, 3.5, 0.0)), ((2.2, 30, 0), (2.0, 16.5, 0.4), (1.7, 3.5, -0.3))],
        'B': [((-2.2, 30, 0), (-3.0, 21.5, 7.5), (-2.6, 10.5, 3.5)), ((2.2, 30, 0), (3.0, 17.0, -1.0), (3.4, 4.0, -2.6))],
        'C': [((-2.2, 30, 0), (-6.0, 18.0, 1.0), (-9.0, 6.5, -1.5)), ((2.2, 30, 0), (4.5, 17.5, -2.5), (4.0, 5.5, 4.5))],
    }[fr]
    for (h, k, t) in piernas:
        ropa.append(cap(X, h, k, 2.2, 1.9, PANO))
        ropa.append(cap(X, k, t, 1.9, 1.5, PANO))
        # pie descalzo, colgando de puntas
        d = nrm(V(t) - V(k))
        pie_fin = V(t) + d * 2.2 + V(0, -1.4, 1.4)
        piel.append(cap(X, t, pie_fin, 1.3, 1.0, PIEL))
    g = [Group(soga, k=0.2), Group(saco, k=0.8), Group(ropa, k=0.9), Group(piel, k=0.4)]
    return g, {'obj': 'AHORCADO', 'lineas': 2.0}


@gancho('AHORCADO')
def g_ahorcado(Q, mat, inten, nz, nr, spec, lvl, ex):
    a = mat == ARPILLERA
    idx = np.nonzero(a)[0]
    trama = (np.sin(Q[idx, 0] * 2.6) * np.sin(Q[idx, 1] * 2.6) > 0.35)
    inten[idx[trama]] *= 0.85
    li = mat == LIENZO
    i2 = np.nonzero(li)[0]
    n = vnoise(Q[i2], 0.6, 101)
    inten[i2] *= 0.8 + 0.35 * n
    mancha = vnoise(Q[i2], 0.35, 102) > 0.68
    mat[i2[mancha]] = PANO
    c = mat == CUERDA
    retorcido(Q, mat, inten, (CUERDA,), paso=1.6, fuerza=0.25)
    apply_shine(mat, inten, spec, ((PIEL, 0.25, 6),))


def saco_colgado():
    """GOR2: saco de arpillera colgado, con un bulto humano dentro y una mano que asoma."""
    top = 81.0
    soga = cuerda((0, top, 0), (0, 68.5, 0), sem=3)
    soga.append(Ring(Frame((0, 66.4, 0)), 1.8, 1.8, 0.65, CUERDA))
    soga.append(Ring(Frame((0, 65.0, 0)), 2.1, 2.1, 0.6, CUERDA))
    saco = [Torno(Frame((0, 60.0, 0)), [(0, 4.5), (3.0, 2.2), (6.5, 1.6), (8.0, 2.4)], ARPILLERA),
            Ellipsoid((0.4, 57.0, 0.4), (5.6, 5.0, 5.2), None, ARPILLERA),          # cabeza
            Ellipsoid((0, 46.0, 0), (8.2, 10.0, 6.8), rot_z(rad(4)), ARPILLERA),     # espalda y hombros
            Ellipsoid((-0.8, 35.0, 1.5), (8.0, 6.5, 7.6), None, ARPILLERA),          # rodillas encogidas
            Ellipsoid((2.5, 37.5, 5.8), (3.6, 3.6, 2.5), None, ARPILLERA),
            Ellipsoid((-3.0, 31.0, 0.0), (5.0, 3.6, 5.0), None, ARPILLERA)]
    for k, (x, y, z) in enumerate(((-6.0, 50, 4), (5.5, 43, 4.5), (-4.0, 39, 6.0))):
        saco.append(Ellipsoid((x, y, z), (2.2, 2.0, 1.4), None, ARPILLERA))
    I = Xf((0, 0, 0), np.eye(3))
    mano = [cap(I, (-6.8, 37.5, 3.6), (-11.0, 32.0, 6.4), 1.55, 1.3, PIEL),
            ell(I, (-11.4, 31.0, 6.8), (1.6, 1.4, 1.1), PIEL)]
    for k, (dx, dz) in enumerate(((-1.2, 0.3), (-0.4, 0.8), (0.4, 0.9), (1.1, 0.5))):
        a = V(-11.4 + dx, 30.2, 6.8 + dz * 0.4)
        mano.append(RoundCone(a, a + V(dx * 0.5, -2.6 + abs(dx) * 0.5, 0.4), 0.5, 0.4, PIEL))
    mano.append(RoundCone(V(-10.2, 31.2, 7.4), V(-9.4, 29.6, 8.2), 0.5, 0.4, PIEL))
    saco.append(Ring(Frame((-6.9, 37.4, 3.7), basis(V(-0.6, -0.55, 0.45))), 1.9, 1.9, 0.5, ARPILLERA))
    g = [Group(soga, k=0.2), Group(saco, k=2.0), Group(mano, k=0.35)]
    return g, {'obj': 'SACO', 'lineas': 2.0}


@gancho('SACO')
def g_saco(Q, mat, inten, nz, nr, spec, lvl, ex):
    a = mat == ARPILLERA
    idx = np.nonzero(a)[0]
    q = Q[idx]
    trama = (np.sin(q[:, 0] * 2.4 + q[:, 2] * 2.4) * np.sin(q[:, 1] * 2.4) > 0.4)
    inten[idx[trama]] *= 0.85
    # costura vertical y una mancha oscura que empapa el fondo del saco
    cost = (np.abs(q[:, 0] - 1.0) < 0.35) & (q[:, 2] > 3) & (q[:, 1] < 60)
    inten[idx[cost]] *= 0.6
    n = vnoise(q, 0.45, 111)
    m = (q[:, 1] < 33 + 6 * n) & (n > 0.35)
    mat[idx[m]] = SANGRE
    inten[idx[m]] *= 0.55
    retorcido(Q, mat, inten, (CUERDA,), paso=1.6, fuerza=0.25)


def pelele():
    """GOR3: pelele de paja ahorcado (el muñeco de las fiestas): cara de trapo pintada."""
    top = 83.0
    soga = cuerda((0, top, -0.4), (0.3, 72.0, -2.5), sem=5)
    soga.append(Ring(Frame((0, 67.4, 0.2), rot_x(rad(10))), 2.0, 2.0, 0.55, CUERDA))
    X = Xf((0, top, 0), rot_z(rad(-6)) @ rot_y(rad(8)))
    cara = [ell(X, (0, 71.0, 0), (4.4, 4.8, 4.0), TELA)]
    paja, ropa = [], []
    rng = np.random.default_rng(121)
    for k in range(13):                                      # melena de paja que cae por los lados y atrás
        a = rad(-150 + k * 25)
        if abs(math.degrees(a)) < 40:
            continue
        c = V(math.sin(a) * 3.6, 74.0, math.cos(a) * 3.2 - 0.4)
        fin = c + V(math.sin(a) * 1.6, -rng.uniform(4.5, 7.5), math.cos(a) * 0.8 - 0.6)
        paja.append(cap(X, c, fin, 0.65, 0.35, PAJA))
    paja.append(ell(X, (0, 74.6, -0.6), (4.4, 1.8, 4.0), PAJA))
    for k in range(5):                                       # flequillo
        x = -2.4 + k * 1.2
        paja.append(cap(X, (x, 75.4, 2.2), (x * 1.1, 73.6, 3.6), 0.5, 0.3, PAJA))
    ropa.append(ell(X, (0, 66.0, 0.2), (2.0, 1.4, 1.8), TELA))
    ropa.append(cap(X, (0, 64.0, 0), (0, 52.5, 0.4), 4.4, 3.8, PANO))            # chaquetilla parda
    ropa.append(ell(X, (0, 62.6, 0), (6.0, 2.4, 3.2), PANO))
    ropa.append(Ring(Frame(X.p((0, 54.6, 0.3)), X.M()), 4.0, 3.4, 0.9, TRAPO))   # faja roja
    ropa.append(ell(X, (0, 52.0, 0.4), (4.2, 2.0, 3.2), PANO_VERDE))           # calzón
    for s in (-1, 1):                                                        # brazos flojos
        ropa.append(cap(X, (s * 5.2, 62.5, 0), (s * 7.6, 55.0, 1.5), 1.6, 1.4, PANO))
        ropa.append(cap(X, (s * 7.6, 55.0, 1.5), (s * 8.4, 48.5, 2.8), 1.4, 1.2, LIENZO))
        for j in range(3):
            paja.append(cap(X, (s * 8.4, 48.8, 2.8), (s * (8.6 + 0.8 * j - 0.8), 45.6 - j * 0.3, 3.0 + j * 0.4), 0.45,
                            0.3, PAJA))
    piernas = (((-2.0, 51, 0.4), (-3.0, 42.0, 2.0), (-2.6, 35.0, 0.5)), ((2.0, 51, 0.4), (2.6, 42.5, 0.6), (3.8, 35.4, 1.6)))
    for (h, k, t) in piernas:
        ropa.append(cap(X, h, k, 2.0, 1.8, PANO_VERDE))
        ropa.append(cap(X, k, t, 1.6, 1.4, LIENZO))                        # medias blancas
        for j in range(3):
            paja.append(cap(X, t, V(t) + V(0.8 * j - 0.8, -2.6, 0.6), 0.45, 0.3, PAJA))
    g = [Group(soga, k=0.2), Group(cara, k=0.3), Group(ropa, k=0.7), Group(paja)]
    return g, {'obj': 'PELELE', 'X': X, 'lineas': 2.0}


@gancho('PELELE')
def g_pelele(Q, mat, inten, nz, nr, spec, lvl, ex):
    X = ex['X']
    m = mat == TELA
    idx = np.nonzero(m)[0]
    q = (Q[idx] - X.piv) @ X.R + X.piv          # al marco del muñeco
    cara = (q[:, 1] > 67) & (q[:, 2] > 1.5)
    x, y = q[:, 0], q[:, 1]
    ojos = cara & ((np.hypot(x + 1.6, y - 72.0) < 0.75) | (np.hypot(x - 1.6, y - 72.0) < 0.75))
    boca = cara & (np.abs(y - 68.7 - 0.15 * x * x) < 0.4) & (np.abs(x) < 2.0)
    mofl = cara & ((np.hypot(x + 2.6, y - 69.9) < 0.95) | (np.hypot(x - 2.6, y - 69.9) < 0.95))
    mat[idx[ojos | boca]] = BOTON
    mat[idx[mofl & ~ojos & ~boca]] = TRAPO
    inten[idx] = inten[idx] * 0.9 + 0.12
    p = mat == PAJA
    inten[p] *= 0.75 + 0.5 * vnoise(Q[p], 2.0, 123)
    t = np.isin(mat, (PANO_VERDE, PANO, TRAPO))
    inten[t] *= 0.8 + 0.35 * vnoise(Q[t], 0.8, 124)
    retorcido(Q, mat, inten, (CUERDA,), paso=1.6, fuerza=0.25)


def cerdo():
    """GOR4: el cerdo de la matanza colgado del camal (cabeza abajo)."""
    top = 67.0
    soga = cuerda((0, top, 0), (-9.5, 60.5, 0), n=3, sem=7) + cuerda((0, top, 0), (9.5, 60.5, 0), n=3, sem=8)
    camal = [cil((-15.0, 59.8, 0.3), (15.0, 59.8, -0.3), 1.25, MADERA)]
    X = Xf((0, 0, 0), np.eye(3))
    piel = []
    for s in (-1, 1):                                # patas traseras atadas al camal
        piel.append(cap(X, (s * 5.5, 60.5, 0.4), (s * 5.4, 53.0, 0.4), 1.4, 1.9, CERDO))
        piel.append(cap(X, (s * 5.4, 53.0, 0.4), (s * 4.6, 45.0, 0.4), 2.6, 4.4, CERDO))
        piel.append(ell(X, (s * 5.6, 61.6, 0.4), (1.4, 0.9, 1.1), BREA))
    piel.append(ell(X, (0, 38.0, 0.4), (9.0, 12.0, 7.6), CERDO))                 # cuerpo
    piel.append(ell(X, (0, 28.5, 0.6), (7.4, 6.0, 6.4), CERDO))                  # pecho
    cabeza = [ell(X, (0, 21.0, 1.8), (5.0, 5.6, 4.8), CERDO),
              cap(X, (0, 18.0, 3.8), (0, 13.6, 5.0), 2.8, 2.4, CERDO),             # jeta
              Ellipsoid(X.p((0, 13.2, 5.1)), (2.5, 0.6, 2.2), None, CERDO)]       # morro
    for s in (-1, 1):
        cabeza.append(Ellipsoid(X.p((s * 4.0, 18.6, 1.0)), (1.8, 3.0, 0.6), rot_z(rad(s * 20)), CERDO))  # orejas
        cabeza.append(cap(X, (s * 6.6, 29.0, 1.2), (s * 8.6, 21.5, 2.4), 2.0, 1.4, CERDO))  # manos colgando
        cabeza.append(cap(X, (s * 8.6, 21.5, 2.4), (s * 9.0, 16.4, 2.8), 1.3, 1.1, CERDO))
        cabeza.append(ell(X, (s * 9.0, 15.6, 2.8), (1.2, 0.9, 1.1), BREA))
    g = [Group(soga, k=0.2), Group(camal), Group(piel, k=1.6), Group(cabeza, k=0.7)]
    return g, {'obj': 'CERDO', 'lineas': 2.0}


@gancho('CERDO')
def g_cerdo(Q, mat, inten, nz, nr, spec, lvl, ex):
    m = mat == CERDO
    idx = np.nonzero(m)[0]
    q = Q[idx]
    # la canal: el vientre abierto en una raja oscura (sin vísceras)
    raja = (np.abs(q[:, 0] - 0.4 * np.sin(q[:, 1] * 0.3)) < 0.7 + 0.5 * np.clip((q[:, 1] - 30) / 15, 0, 1)) & \
        (q[:, 2] > 4.0) & (q[:, 1] > 29) & (q[:, 1] < 48)
    mat[idx[raja]] = SANGRE
    inten[idx[raja]] *= 0.5
    # ojo cerrado y hocico
    ojo = (np.abs(q[:, 1] - 20.6) < 0.45) & (np.abs(np.abs(q[:, 0]) - 2.3) < 1.0) & (q[:, 2] > 4.0)
    inten[idx[ojo]] *= 0.4
    hoc = (q[:, 1] < 13.9) & (np.abs(np.abs(q[:, 0]) - 0.9) < 0.45) & (np.abs(q[:, 2] - 5.4) < 0.9)
    mat[idx[hoc]] = BREA
    gota = (q[:, 1] < 13.2) & (np.abs(q[:, 0]) < 0.5)
    mat[idx[gota]] = SANGRE
    # piel escaldada: manchas
    inten[idx] *= 0.85 + 0.25 * vnoise(q, 0.7, 131)
    apply_shine(mat, inten, spec, ((CERDO, 0.35, 8),))


def jaula():
    """GOR5: jaula de hierro colgada de una cadena con un esqueleto acurrucado dentro."""
    top = 51.0
    hierro = []
    y = top - 1.2
    for i in range(5):                                       # cadena
        R = rot_y(rad(90)) if i % 2 else np.eye(3)
        hierro.append(Ring(Frame((0, y, 0), R @ rot_x(rad(90))), 0.9, 1.5, 0.42, HIERRO))
        y -= 2.5
    hierro.append(Ring(Frame((0, y - 0.4, 0), rot_x(rad(90))), 1.5, 1.5, 0.5, HIERRO))
    ya = y - 2.2                                             # arriba de la jaula
    hierro.append(Torno(Frame((0, ya - 4.0, 0)), [(0, 9.0), (1.5, 7.6), (3.0, 4.6), (4.0, 1.2)], HIERRO))
    yb = ya - 51.0                                           # abajo de la jaula
    perfil = lambda t: 9.0 + 4.6 * math.sin(math.pi * t) ** 0.8
    for y0 in (ya - 4.0, ya - 26.0, yb + 2.0):
        r = perfil((ya - 4.0 - y0) / (ya - 4.0 - yb - 2.0))
        hierro.append(Ring(Frame((0, y0, 0)), r, r, 0.65, HIERRO))
    for k in range(10):
        a = 2 * math.pi * k / 10 + 0.15
        pts = []
        for t in np.linspace(0, 1, 7):
            r = perfil(t)
            yy = (ya - 4.0) + (yb + 2.0 - (ya - 4.0)) * t
            pts.append(V(math.sin(a) * r, yy, math.cos(a) * r))
        hierro += cadena_pts(pts, 0.55, 0.55, HIERRO)
    hierro.append(Torno(Frame((0, yb - 1.0, 0)), [(0, 1.0), (1.2, 7.0), (3.0, 9.4)], HIERRO))
    hierro.append(cil((0, yb - 1.2, 0), (0, yb - 4.5, 0), 0.6, HIERRO))
    hierro.append(Sphere((0, yb - 5.0, 0), 1.1, HIERRO))
    # esqueleto acurrucado: sentado en el fondo, rodillas al pecho, cabeza caída
    hb = []
    yf = yb + 3.0
    Fc = Frame((-1.0, yf + 24.0, 2.2), rot_x(rad(35)) @ rot_z(rad(18)))
    cal = Calavera(Fc, 1.15, HUESO)
    # columna y costillas
    hb += cadena_pts([V(0.5, yf + 3.5, -3.0), V(0.2, yf + 11, -3.8), V(-0.5, yf + 18.0, -2.4), V(-0.8, yf + 21.5, 0.2)],
                     0.9, 0.8, HUESO)
    for i in range(5):
        yy = yf + 18.0 - i * 2.1
        for s in (-1, 1):
            hb += cadena_pts(bezier(V(s * 0.6, yy, -3.0), V(s * 5.2, yy - 0.8, -1.6), V(s * 2.0, yy - 1.8, 2.2), 4),
                             0.45, 0.4, HUESO)
    hb.append(Ellipsoid((0.4, yf + 4.0, -1.5), (4.4, 2.4, 2.8), None, HUESO))          # pelvis
    for s in (-1, 1):
        # piernas dobladas: fémur hacia arriba-delante, tibia hacia abajo
        rod = V(s * 3.2, yf + 14.0, 6.0)
        hb.append(RoundCone(V(s * 2.6, yf + 3.6, 0.0), rod, 0.95, 0.85, HUESO))
        hb.append(Sphere(rod, 1.2, HUESO))
        hb.append(RoundCone(rod, V(s * 3.0, yf + 1.2, 6.2), 0.8, 0.7, HUESO))
        hb.append(Ellipsoid(V(s * 3.0, yf + 0.8, 7.6), (1.0, 0.6, 1.8), None, HUESO))
        # brazos abrazando las rodillas
        hom = V(s * 4.4, yf + 19.0, -1.5)
        cod = V(s * 6.2, yf + 11.5, 2.6)
        hb.append(RoundCone(hom, cod, 0.8, 0.7, HUESO))
        hb.append(RoundCone(cod, V(s * 1.4, yf + 13.6, 7.6), 0.7, 0.6, HUESO))
    g = [Group(hierro, k=0.0), Group([cal]), Group(hb, k=0.25)]
    return g, {'obj': 'JAULA', 'cal': (Fc, 1.15), 'lineas': 2.0}


@gancho('JAULA')
def g_jaula(Q, mat, inten, nz, nr, spec, lvl, ex):
    Fc, s = ex['cal']
    cu, di = calavera_cuencas(Fc, s, Q)
    mh = mat == HUESO
    mat[mh & cu] = CUENCA
    inten[mh & di] *= 0.55
    o = mat == HIERRO
    n2 = vnoise(Q[o], 1.0, 141)
    io = np.nonzero(o)[0]
    mat[io[n2 > 0.58]] = OXIDO
    inten[mh] *= 0.85 + 0.25 * vnoise(Q[mh], 1.2, 142)
    apply_shine(mat, inten, spec, ((HIERRO, 0.45, 10), (HUESO, 0.3, 8)))


# ============================================================================= picas y espantapájaros
def calavera_cabra(F, s, mat=HUESO):
    """Cráneo de macho cabrío (cara larga hacia +z', cuernos hacia atrás) en el marco F."""
    pz = [Ellipsoid(F.p((0, 0, 0)), V(3.6, 3.4, 3.8) * s, F.M(), mat),
          RoundCone(F.p((0, -0.6 * s, 1.5 * s)), F.p((0, -3.6 * s, 7.4 * s)), 2.7 * s, 1.5 * s, mat)]
    for sx in (-1, 1):
        pz.append(Ellipsoid(F.p((sx * 2.4 * s, 0.4 * s, 1.6 * s)), V(1.3, 1.3, 1.4) * s, F.M(), mat))
    cuernos = []
    for sx in (-1, 1):
        pts = [F.p(V(sx * 1.8, 2.6, 0.8) * s), F.p(V(sx * 3.6, 6.0, -1.6) * s), F.p(V(sx * 6.2, 6.6, -5.2) * s),
               F.p(V(sx * 8.0, 3.6, -6.4) * s), F.p(V(sx * 8.6, 1.0, -4.6) * s)]
        cuernos += cadena_pts(pts, 1.3 * s, 0.45 * s, CUERNO)
    return pz, cuernos


def cabra_cuencas(F, s, Q):
    q = F.to_local(Q) / s
    m = np.zeros(len(Q), bool)
    for sx in (-1, 1):
        m |= _len(q - V(sx * 2.5, 0.6, 2.4)) < 1.25
    m |= _ell(q, (0, -3.0, 7.5), (0.9, 0.6, 0.9)) < 0
    return m


def espantapajaros(fr='A', cabra=False):
    """POL1 (sombrero de paja y cara de saco cosida) y POL6 (trapos y calavera de cabra que gira)."""
    poste = [cil((0, -0.5, 0), (0, 58.0, -0.6), 1.5, MADERA, 1.3)]
    brazo_y = 45.5
    ancho = 17.0 if not cabra else 11.5
    travesano = [cil((-ancho, brazo_y, -1.0), (ancho, brazo_y + 0.6, -1.0), 1.1, MADERA)]
    ropa, paja, cabeza, extra = [], [], [], []
    X = Xf((0, 0, 0), np.eye(3))
    rng = np.random.default_rng(151 if not cabra else 161)
    if not cabra:
        # chaquetón de paño: cuerpo y mangas sobre el travesaño, faldones rotos
        ropa.append(Torno(Frame((0, 26.0, 0)), [(0, 6.6), (8.0, 5.6), (16.0, 6.0), (19.0, 7.2), (21.0, 3.0)], PANO))
        for s in (-1, 1):
            ropa.append(RoundCone(V(s * 5.0, brazo_y + 0.2, -0.6), V(s * (ancho - 2.0), brazo_y - 1.2, -0.6), 3.2, 2.5,
                                  PANO))
            ropa.append(Ellipsoid(V(s * (ancho - 1.5), brazo_y - 3.6, -0.6), (2.4, 2.6, 2.4), None, PANO))
            for j in range(4):
                a = rng.uniform(-0.6, 0.6)
                c = V(s * (ancho - 0.5), brazo_y - 4.0, -0.6 + rng.uniform(-1, 1))
                paja.append(RoundCone(c, c + V(s * rng.uniform(0.5, 2.5), -rng.uniform(3, 6), a), 0.5, 0.3, PAJA))
        for j in range(12):
            a = rng.uniform(0, 2 * math.pi)
            c = V(math.sin(a) * 5.6, 26.6, math.cos(a) * 5.0)
            paja.append(RoundCone(c, c + V(math.sin(a) * 1.5, -rng.uniform(3, 7), math.cos(a) * 1.5), 0.55, 0.3, PAJA))
        ropa.append(cil((0, 25.0, 0), (0, 27.0, 0), 4.0, PANO))
        extra.append(Ring(Frame((0, 34.0, 0)), 5.8, 5.0, 0.55, CUERDA))
        cabeza.append(Ellipsoid((0, 53.0, 0.4), (4.8, 5.4, 4.4), None, ARPILLERA))
        cabeza.append(Ring(Frame((0, 48.6, 0.2)), 2.4, 2.4, 0.5, CUERDA))
        sombrero = [Torno(Frame((0, 56.6, 0), rot_z(rad(-8))), [(0, 9.6), (0.6, 9.2), (1.0, 4.4), (4.4, 3.8),
                                                                (5.4, 2.6), (5.8, 0.0)], PAJA)]
        g = [Group(poste + travesano, k=0.3), Group(ropa, k=1.0), Group(paja), Group(cabeza + extra, k=0.4),
             Group(sombrero)]
        return g, {'obj': 'ESPANTA', 'lineas': 2.0}
    # POL6: trapos grises y rojos colgando del travesaño, calavera de cabra que gira la cabeza
    ropa.append(Torno(Frame((0, 22.0, 0)), [(0, 4.6), (12.0, 4.4), (22.0, 5.0), (25.0, 2.0)], TRAPO_GRIS))
    for k in range(14):
        x = rng.uniform(-ancho + 1, ancho - 1)
        largo = rng.uniform(8, 20) * (1.0 if abs(x) > 4 else 0.6)
        c = V(x, brazo_y - 0.5, rng.uniform(-1.6, 0.6))
        mat = TRAPO if k % 5 == 2 else TRAPO_GRIS
        ropa.append(Box(c + V(0, -largo / 2, 0), (rng.uniform(1.0, 1.8), largo / 2, 0.45),
                        rot_z(rng.uniform(-0.12, 0.12)) @ rot_y(rng.uniform(-0.5, 0.5)), 0.3, mat))
    for k in range(10):
        c = V(rng.uniform(-3.5, 3.5), rng.uniform(14, 24), rng.uniform(0.5, 3.0))
        ropa.append(Box(c + V(0, -4, 0), (rng.uniform(0.9, 1.6), 5.0, 0.45), rot_z(rng.uniform(-0.2, 0.2)), 0.3,
                        TRAPO_GRIS))
    extra.append(Ring(Frame((0, brazo_y, -1.0), rot_z(rad(90))), 1.8, 1.8, 0.55, CUERDA))
    yaw, roll = (0.0, 0.0) if fr == 'A' else (38.0, -12.0)
    Fc = Frame((0, 53.5, 0.6), rot_y(rad(yaw)) @ rot_z(rad(roll)) @ rot_x(rad(30)))
    pz, cuernos = calavera_cabra(Fc, 1.0)
    g = [Group(poste + travesano, k=0.3), Group(ropa, k=0.0), Group(extra), Group(pz, k=0.9), Group(cuernos, k=0.4)]
    return g, {'obj': 'ESPANTA', 'cabra': (Fc, 1.0), 'lineas': 2.0}


@gancho('ESPANTA')
def g_espanta(Q, mat, inten, nz, nr, spec, lvl, ex):
    a = mat == ARPILLERA
    idx = np.nonzero(a)[0]
    q = Q[idx]
    cara = q[:, 2] > 2.0
    x, y = q[:, 0], q[:, 1]
    # cara cosida: ojos en cruz de aspa, boca cosida con puntadas
    ojo = np.zeros(len(idx), bool)
    for cx in (-1.9, 1.9):
        u, v = x - cx, y - 54.2
        ojo |= (np.abs(np.abs(u) - np.abs(v)) < 0.45) & (np.abs(u) < 1.1)
    boca = (np.abs(y - 50.6 - 0.1 * x * x) < 0.35) & (np.abs(x) < 2.8)
    punt = (np.abs(y - 50.6) < 1.1) & (np.abs(((x + 3) % 1.4) - 0.7) < 0.25) & (np.abs(x) < 2.8)
    mat[idx[cara & (ojo | boca | punt)]] = BOTON
    trama = (np.sin(q[:, 0] * 2.6) * np.sin(q[:, 1] * 2.6) > 0.35)
    inten[idx[trama]] *= 0.85
    p = mat == PAJA
    inten[p] *= 0.75 + 0.5 * vnoise(Q[p], 2.0, 153)
    t = np.isin(mat, (TRAPO, TRAPO_GRIS, PANO))
    inten[t] *= 0.75 + 0.45 * vnoise(Q[t], 0.8, 154)
    if 'cabra' in ex:
        Fc, s = ex['cabra']
        h = mat == HUESO
        cu = cabra_cuencas(Fc, s, Q)
        mat[h & cu] = CUENCA
        cn = mat == CUERNO
        q2 = Fc.to_local(Q[cn])
        anillos = np.sin(_len(q2) * 3.2) > 0.6
        ic = np.nonzero(cn)[0]
        inten[ic[anillos]] *= 0.7
        apply_shine(mat, inten, spec, ((HUESO, 0.35, 8), (CUERNO, 0.3, 6)))
    retorcido(Q, mat, inten, (CUERDA,), paso=1.6, fuerza=0.25)


def pica(calaveras, pelo=False):
    """POL2 (pica con calaveras ensartadas y trapos) y POL4 (una calavera con pelo en una pica)."""
    alto = 62.0 if not pelo else 50.0
    palo = [RoundCone(V(0, -0.5, 0), V(0.4, alto - 4, 0), 1.25, 0.9, MADERA),
            RoundCone(V(0.4, alto - 4, 0), V(0.5, alto + 1.5, 0), 0.9, 0.25, MADERA)]
    rng = np.random.default_rng(171 if not pelo else 181)
    piedras = []
    for k in range(5):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(2.5, 6.0)
        s = rng.uniform(1.6, 2.8)
        piedras.append(Pena((math.cos(a) * r, s * 0.4, math.sin(a) * r * 0.7), (s * 1.2, s * 0.8, s), None, 0.6, 0.8,
                            172 + k, PIEDRA))
    cals, cuen = [], []
    for k, (y, yaw, pitch, s) in enumerate(calaveras):
        F = Frame((0.3, y, 0.2), rot_y(rad(yaw)) @ rot_x(rad(pitch)))
        cals.append(Calavera(F, s, HUESO))
        cuen.append((F, s))
    trapos = []
    pelos = []
    if not pelo:
        for k, (y, L, m) in enumerate(((alto - 21, 10, TRAPO), (alto - 34.5, 14, TRAPO_GRIS), (alto - 35, 8, TRAPO))):
            trapos.append(Ring(Frame((0.3, y, 0)), 1.6, 1.6, 0.5, m))
            for j in range(2):
                d = V(rng.uniform(-1, 1), 0, rng.uniform(0.3, 1))
                trapos.append(Box(V(0.3, y, 0) + d * 1.4 + V(d[0] * 2, -L / 2, 0), (1.1, L / 2, 0.35),
                                  rot_z(-d[0] * 0.35) @ rot_y(math.atan2(d[0], d[2])), 0.3, m))
    else:
        F, s = cuen[0]
        for k in range(16):
            a = rad(-140 + k * 280 / 15)
            c = F.p(V(math.sin(a) * 3.6, 7.6, math.cos(a) * 3.6 - 1.2) * s)
            fin = c + V(math.sin(a) * 2.0, -rng.uniform(10, 17), math.cos(a) * 1.2 - 1.0)
            mid = (c + fin) / 2 + V(math.sin(a) * 1.5, 0, -0.5)
            pelos += cadena_pts([c, mid, fin], 0.75, 0.35, PELO)
        pelos.append(Ellipsoid(F.p(V(0, 7.0, -0.8) * s), V(4.2, 2.2, 4.4) * s, F.M(), PELO))
        trapos.append(Ring(Frame((0.4, alto - 14.0, 0)), 1.5, 1.5, 0.5, TRAPO))
        trapos.append(Box(V(1.5, alto - 19.5, 0.8), (1.0, 5.5, 0.35), rot_z(-0.2), 0.3, TRAPO))
    g = [Group(palo, k=0.3), Group(piedras), Group(cals), Group(trapos)] + ([Group(pelos, k=0.4)] if pelos else [])
    return g, {'obj': 'PICA', 'cuen': cuen, 'lineas': 2.0}


@gancho('PICA')
def g_pica(Q, mat, inten, nz, nr, spec, lvl, ex):
    mh = mat == HUESO
    for F, s in ex['cuen']:
        cu, di = calavera_cuencas(F, s, Q)
        mat[mh & cu] = CUENCA
        inten[mh & di] *= 0.55
    inten[mh] *= 0.85 + 0.25 * vnoise(Q[mh], 1.0, 175)
    md = mat == MADERA
    inten[md] *= 0.8 + 0.3 * vnoise(Q[md] * V(2, 0.3, 2), 1.0, 176)
    # chorretón oscuro bajo las calaveras, por el palo
    p = mat == PELO
    inten[p] *= 0.75 + 0.5 * (np.sin(Q[p, 0] * 3.0 + Q[p, 2] * 3.0) > 0)
    apply_shine(mat, inten, spec, ((HUESO, 0.4, 8),))


# ----------------------------------------------------------------------------- POL3: osario con velas
POL3_VELAS = [((-8.0, 15.5, 2.5), 6.0), ((2.0, 21.0, 0.0), 7.0), ((9.5, 13.0, 3.0), 5.0), ((-2.0, 12.0, 7.5), 4.5)]


def osario():
    rng = np.random.default_rng(191)
    huesos, cals, cuen = [], [], []
    # montón: huesos largos apilados en un túmulo
    for k in range(46):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0, 1) ** 0.6 * 15.0
        y = (1 - (r / 16.0) ** 1.6) * 15.0 * rng.uniform(0.6, 1.0) + 1.0
        c = V(math.cos(a) * r, y, math.sin(a) * r * 0.75)
        d = nrm(V(rng.normal(), rng.normal() * 0.35, rng.normal()))
        L = rng.uniform(5, 9)
        p0, p1 = c - d * L / 2, c + d * L / 2
        huesos.append(RoundCone(p0, p1, 0.75, 0.7, HUESO_OSARIO))
        huesos.append(Sphere(p0, 1.15, HUESO_OSARIO))
        huesos.append(Sphere(p1, 1.15, HUESO_OSARIO))
    for k, (x, y, z, yaw, pitch, s) in enumerate(((-4.5, 11.5, 5.0, 15, -5, 1.15), (5.0, 9.5, 6.5, -20, 5, 1.1),
                                                  (0.5, 16.0, 2.0, 5, -10, 1.2), (-11.0, 4.0, 4.0, 40, 10, 1.0),
                                                  (12.0, 3.5, 3.0, -35, -5, 1.05), (7.0, 15.0, -2.0, -10, 0, 1.0),
                                                  (-7.0, 1.5, 9.0, 10, 20, 0.95))):
        F = Frame((x, y - 4.5 * s, z), rot_y(rad(yaw)) @ rot_x(rad(pitch)))
        cals.append(Calavera(F, s, HUESO_OSARIO))
        cuen.append((F, s))
    base = [Ellipsoid((0, 0.5, 0), (16.5, 5.0, 12.0), None, HUESO_OSARIO)]
    velas = []
    for (c, h) in POL3_VELAS:
        c = V(c)
        velas.append(Torno(Frame(c + V(0, -1.0, 0)), [(0, 1.2), (h - 0.6, 1.05), (h, 0.6), (h + 0.15, 0)], CERA_FB))
        velas.append(Ellipsoid(c + V(0.6, h * 0.4, 0.8), (0.45, h * 0.3, 0.45), None, CERA_FB))
        velas.append(cil(c + V(0, h - 0.2, 0), c + V(0.1, h + 0.9, 0), 0.3, MECHA))
    luces = [(V(c) + V(0, h + 2.0, 0), 7.5, 'nat') for c, h in POL3_VELAS]
    g = [Group(base + huesos, k=0.25), Group(cals), Group(velas, k=0.3)]
    return g, {'obj': 'OSARIO', 'cuen': cuen, 'luces': luces, 'lineas': 2.0}


@gancho('OSARIO')
def g_osario(Q, mat, inten, nz, nr, spec, lvl, ex):
    mh = mat == HUESO_OSARIO
    for F, s in ex['cuen']:
        cu, di = calavera_cuencas(F, s, Q)
        mat[mh & cu] = CUENCA
        inten[mh & di] *= 0.5
    inten[mh] *= 0.8 + 0.3 * vnoise(Q[mh], 1.3, 195)
    # lo de abajo del montón, en sombra (va a pleno brillo: lo oscurecemos)
    inten[mh] *= np.clip(0.5 + Q[mh, 1] / 20.0, 0.5, 1.05)
    apply_shine(mat, inten, spec, ((HUESO_OSARIO, 0.35, 8), (CERA_FB, 0.3, 6)))


# ----------------------------------------------------------------------------- CEYE: el ojo de la meiga
def ojo_tarro(fr):
    F = Frame((0, 0, 0))
    pie = [Torno(F, [(0, 8.0), (1.4, 8.0), (2.2, 6.4), (3.0, 3.4), (4.5, 2.5), (6.0, 3.8), (7.4, 2.6), (9.6, 2.4),
                     (11.0, 5.2), (12.2, 8.6), (13.0, 8.8)], TORNEADO)]
    y0 = 13.0                                          # fondo del tarro
    yt = y0 + 26.0                                     # boca
    R = 11.5
    # cristal: lo de detrás del tarro es líquido (verdoso, a pleno brillo); delante, solo los reflejos
    liquido = Torno(F * Frame((0, y0 + 0.8, 0)), [(0, R - 0.9), (2.0, R - 0.3), (21.5, R - 0.3), (22.5, R - 1.4)],
                    LIQUIDO)
    liquido.cut = lambda P: P[:, 2] - 0.0
    borde = [Ring(Frame((0, y0 + 0.9, 0)), R - 0.2, R - 0.2, 0.8, CRISTAL),
             Ring(Frame((0, yt - 2.2, 0)), R - 0.5, R - 0.5, 0.75, CRISTAL),
             Torno(F * Frame((0, yt - 1.6, 0)), [(0, R - 2.2), (0.5, R - 1.0), (3.2, R - 0.9), (3.8, R - 1.8)],
                   MADERA_FB),                                         # tapón de corcho
             Ring(Frame((0, yt - 0.2, 0)), R - 1.4, R - 1.4, 0.55, CUERDA)]
    ojo_c = V(0, y0 + 12.0, 0.5)
    gaze = {'A': -42.0, 'B': 0.0, 'C': 42.0}[fr]
    Fo = Frame(ojo_c, rot_y(rad(gaze)) @ rot_x(rad(-6)))
    ojo = [Sphere(ojo_c, 6.6, OJO)]
    # nervio que cuelga del ojo
    nervio = cadena_pts([Fo.p((0, 0, -5.5)), ojo_c + V(1.5, -6.5, -4.0), ojo_c + V(-0.5, -9.5, -2.0)], 1.3, 0.6, VENA)
    g = [Group(pie, k=0.3), Group([liquido]), Group(borde), Group(ojo), Group(nervio, k=0.4)]
    return g, {'obj': 'OJO', 'Fo': Fo, 'r': 6.6, 'y0': y0, 'yt': yt, 'R': R}


@gancho('OJO')
def g_ojo(Q, mat, inten, nz, nr, spec, lvl, ex):
    Fo, r = ex['Fo'], ex['r']
    m = mat == OJO
    idx = np.nonzero(m)[0]
    q = Fo.to_local(Q[idx]) / r                        # esfera unidad; z' = hacia donde mira
    ang = np.degrees(np.arccos(np.clip(q[:, 2], -1, 1)))
    iris = ang < 33
    mat[idx[iris]] = IRIS
    # iris: anillo claro por fuera, rayos, más oscuro cerca de la pupila
    rr = ang[iris] / 33
    rad_ = np.arctan2(q[iris, 1], q[iris, 0])
    val = 0.35 + 0.55 * rr + 0.12 * np.sin(rad_ * 11)
    val = np.where(rr > 0.88, 0.25, val)
    nivel(lvl, idx[iris], val, IRIS)
    # pupila de cabra: rectángulo horizontal
    pup = iris & (np.abs(q[:, 1]) < 0.12) & (np.abs(q[:, 0]) < 0.38)
    mat[idx[pup]] = PUPILA
    # venillas rojas en el blanco
    blanco = ~iris
    n = vnoise(Q[idx], 1.2, 201)
    v = blanco & (np.abs(n - 0.5) < 0.018 + 0.03 * (ang > 80))
    mat[idx[v]] = VENA
    inten[idx[blanco]] = np.clip(inten[idx[blanco]] * (0.75 + 0.3 * (q[blanco, 2] + 1) / 2), 0, 1)
    # líquido: verdoso, más claro por arriba y en el centro
    l = mat == LIQUIDO
    il = np.nonzero(l)[0]
    ql = Q[il]
    yrel = (ql[:, 1] - ex['y0']) / (ex['yt'] - ex['y0'])
    cen = 1 - np.abs(ql[:, 0]) / ex['R']
    nivel(lvl, il, 0.15 + 0.35 * cen + 0.25 * (1 - yrel) + 0.15 * (vnoise(ql, 0.6, 203) - 0.5), LIQUIDO)
    apply_shine(mat, inten, spec, ((OJO, 0.6, 12), (CRISTAL, 0.8, 6), (TORNEADO, 0.3, 8)))


def dibujar_ojo(lump):
    fr = lump[4]
    g, ex = ojo_tarro(fr)
    L = trazar(g, ex, 6)
    img = L.img
    # cristal: dos reflejos verticales delante y el contorno del tarro, claros
    for (xm, a, b, c) in ((-0.66, 0.25, 0.72, 84), (-0.55, 0.78, 0.86, 88), (0.62, 0.55, 0.68, 90)):
        x, y1 = L.px((xm * ex['R'], ex['y0'] + (ex['yt'] - ex['y0']) * a, ex['R']))
        _, y2 = L.px((xm * ex['R'], ex['y0'] + (ex['yt'] - ex['y0']) * b, ex['R']))
        for yy in range(int(round(y2)), int(round(y1))):
            punto(img, x, yy, c)
    # burbujas
    for (bx, by) in ((0.35, 0.86), (0.48, 0.8), (-0.3, 0.9)):
        x, y = L.px((bx * ex['R'], ex['y0'] + (ex['yt'] - ex['y0']) * by, 0))
        punto(img, x, y, 113)
    return recortar(L)


# ----------------------------------------------------------------------------- FSKU: calaveras en la peña
def calaveras_pena():
    pena = [Pena((0, 3.6, 0), (15.0, 6.0, 9.5), None, 2.0, 0.4, 211, ROCA_FB)]
    pena[0].cut = lambda P: -(P[:, 1] + 0.3)
    cals, cuen = [], []
    for (x, y, z, yaw, s) in ((-8.0, 6.6, 0.5, 28, 1.25), (8.0, 7.0, 0.0, -28, 1.25), (0.0, 8.4, 3.5, 0, 1.5)):
        F = Frame((x, y, z), rot_y(rad(yaw)) @ rot_x(rad(-8)))
        cals.append(Calavera(F, s, HUESO_FB))
        cuen.append((F, s))
    luces = [((x, y + 14, z - 3), 11.0, 'nat') for (x, y, z) in ((-8.0, 6.6, 0.5), (8.0, 7.0, 0.0), (0, 8.4, 3.5))]
    return [Group(pena), Group(cals)], {'obj': 'FSKU', 'cuen': cuen, 'luces': luces, 'lineas': 2.0}


@gancho('FSKU')
def g_fsku(Q, mat, inten, nz, nr, spec, lvl, ex):
    mh = mat == HUESO_FB
    for F, s in ex['cuen']:
        cu, di = calavera_cuencas(F, s, Q)
        mat[mh & cu] = CUENCA
        inten[mh & di] *= 0.5
    r = mat == ROCA_FB
    inten[r] *= 0.75 + 0.35 * vnoise(Q[r], 1.1, 213)
    apply_shine(mat, inten, spec, ((HUESO_FB, 0.3, 8),))


def dibujar_fsku(lump):
    fr = lump[4]
    f = 'ABC'.index(fr) / 3.0
    g, ex = calaveras_pena()
    L = trazar(g, ex, 8).margen(arriba=30, lados=3)
    # una hoguera detrás de las tres calaveras y lenguas que les salen por encima
    x, y = L.px((0, 9.0, -2.0))
    llama(L.img, x, y + 2.0, 38.0, 32.0, f, FUEGO_NAT, 220, detras=True, lengua=1.2)
    for k, (F, s) in enumerate(ex['cuen']):
        x, y = L.px(F.p((0, 8.0 * s, -0.5)))
        llama(L.img, x, y + 1.5, 13.0 + 4 * (k == 2), 8.0, (f + 0.37 * k) % 1.0, FUEGO_NAT, 224 + k, detras=True,
              lengua=1.0)
    x, y = L.px((0, 30.0, 0))
    chispas(L.img, x, y, 3, 230, COLORES['nat']['chispa'], alto=7, ancho=5, fase=f)
    for F, s in ex['cuen']:
        for sx in (-1, 1):
            x, y = L.px(F.p(V(sx * 1.45, 4.2, 4.6) * s))
            punto(L.img, x, y, 231 if (int(f * 3) + sx) % 2 else 215)
    return recortar(L)


def dibujar_colgados(lump):
    pre, fr = lump[:4], lump[4]
    if pre == 'GOR1':
        L = trazar(*ahorcado(fr), 2)
        return recortar(L, 'techo', 67)
    if pre == 'GOR2':
        return recortar(trazar(*saco_colgado(), 2), 'techo', 81)
    if pre == 'GOR3':
        return recortar(trazar(*pelele(), 2), 'techo', 83)
    if pre == 'GOR4':
        return recortar(trazar(*cerdo(), 2), 'techo', 67)
    if pre == 'GOR5':
        return recortar(trazar(*jaula(), 2), 'techo', 51)
    if pre == 'POL1':
        return recortar(trazar(*espantapajaros(), 6))
    if pre == 'POL6':
        return recortar(trazar(*espantapajaros(fr, cabra=True), 6))
    if pre == 'POL2':
        return recortar(trazar(*pica([(55.0, -10, 5, 1.2), (43.0, 20, -15, 1.15), (31.0, -5, 10, 1.1)]), 6))
    if pre == 'POL4':
        return recortar(trazar(*pica([(44.0, 8, 4, 1.35)], pelo=True), 6))
    if pre == 'POL3':
        g, ex = osario()
        L = trazar(g, ex, 12).margen(arriba=9, lados=2)
        for i, (c, h) in enumerate(POL3_VELAS):
            x, y = L.px(V(c) + V(0, h + 0.4, 0))
            llamita(L.img, x, y, 6.5 if i != 1 else 7.5, 3.2, ('AB'.index(fr) + i) % 2, 300 + i)
        return recortar(L)
    raise KeyError(lump)


def llamita(img, x, y, alto, ancho, fase, sem):
    """Llama pequeña de vela: gota con el núcleo blanco; fase 0/1 titila (se inclina y se estira)."""
    H, W = img.shape[:2]
    rng = np.random.default_rng(sem * 7 + fase)
    alto = alto * (1.0 if fase == 0 else 0.82)
    lean = (0.6 if fase else -0.4) * rng.uniform(0.6, 1.0)
    for yy in range(int(math.floor(y - alto - 1)), int(math.ceil(y + 1))):
        t = (y - yy - 0.5) / alto                  # 0 abajo, 1 punta
        if t < -0.05 or t > 1.0:
            continue
        w = ancho * 0.5 * (math.sin(math.pi * min(max(t, 0) ** 0.75, 1.0)) ** 0.9) + 0.25
        cx = x + lean * t * t * 2.0
        for xx in range(int(math.floor(cx - w - 1)), int(math.ceil(cx + w + 1))):
            d = abs(xx + 0.5 - cx) / max(w, 0.3)
            if d > 1.0:
                continue
            calor = (1 - d) * 0.9 + (1 - abs(t - 0.32) * 1.6) * 0.6
            if calor > 1.05:
                idx = 4
            elif calor > 0.8:
                idx = 231
            elif calor > 0.55:
                idx = 161
            elif calor > 0.3:
                idx = 216
            else:
                idx = 218
            if t < 0.12 and d < 0.5:
                idx = 194 if calor > 0.6 else 198     # base azulada de la llama
            punto(img, xx, yy, idx)


# ============================================================================= efectos
POLVO = [4, 80, 82, 84, 87, 90, 93, 96, 99, 102, 105]            # polvo y humo de pólvora (claro → oscuro)
POLVO_PARDO = [130, 132, 134, 136, 138, 140, 142, 238]
HUMO_VERDE = [113, 152, 153, 154, 155, 156, 157, 158, 159, 127]
FUEGO_BRUJA = [4, 226, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125]
DESTELLO = [4, 4, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204]
SANGRE_FX = [176, 178, 180, 182, 184, 186, 188, 190]             # claro → oscuro


def lienzo(W, H):
    return np.zeros((H, W, 4), np.uint8)


def nube(img, cx, cy, radio, fase, sem, rampa, rotura=0.0, achatar=1.0, sube=0.0, minimo=6, gamma=1.0):
    """Nube de humo/polvo con borde de ruido: densidad = 1 en el centro → 0 en el borde; «rotura»
    (0-1) la deshace en jirones."""
    H, W = img.shape[:2]
    x, y = malla(W, H, cx, cy)
    y = y - sube
    r = np.hypot(x, y / achatar) / radio
    a = 2 * math.pi * fase
    n = fbm(x * 0.35 + math.cos(a), y * 0.35 + math.sin(a), 3.0 + fase, 1.0, sem)
    dens = (1 - r) * 1.2 + (n - 0.5) * (0.9 + 1.4 * rotura) - rotura * 0.75
    return pintar_calor(img, dens, rampa, gamma=gamma, minimo=minimo)


def chispa(img, x, y, rampa, largo=1, dx=0, dy=0):
    for j in range(largo):
        punto(img, x - dx * j, y - dy * j, rampa[min(j, len(rampa) - 1)])


def desde_img(img, ox, oy):
    """Lienzo ya colocado: offsets fijos (los de Freedoom)."""
    return Image.fromarray(anclas(img), 'RGBA'), [ox, oy]


def puff(fr):
    if fr == 'A':                                     # chispa de pólvora (pleno brillo)
        img = lienzo(5, 5)
        for (x, y, c) in ((2, 2, 4), (1, 2, 231), (3, 2, 231), (2, 1, 231), (2, 3, 230), (0, 2, 161), (4, 2, 161),
                          (2, 0, 161), (2, 4, 216), (1, 1, 216), (3, 3, 216)):
            punto(img, x, y, c)
        return desde_img(img, 2, 3)
    W, H, ox, oy = {'B': (12, 11, 6, 8), 'C': (15, 14, 7, 9), 'D': (17, 15, 8, 10)}[fr]
    img = lienzo(W, H)
    k = 'BCD'.index(fr)
    rad_ = (3.8, 5.6, 7.0)[k]
    nube(img, W / 2, H / 2 + 0.5, rad_, 0.2 * k, 401, POLVO[2:] if k == 0 else POLVO[3 + k:], rotura=(0.0, 0.25, 0.6)[k],
         achatar=0.9, gamma=1.3)
    if fr == 'B':                                      # pavesas de pólvora que salen despedidas
        for (x, y, c) in ((1.0, 3.0, 216), (10.5, 2.0, 218), (9.5, 9.5, 216), (2.0, 9.0, 219)):
            punto(img, x, y, c)
    return desde_img(img, ox, oy)


def blud(fr):
    W, H, ox, oy = {'A': (17, 8, 8, 5), 'B': (11, 10, 6, 7), 'C': (6, 7, 3, 5)}[fr]
    img = lienzo(W, H)
    S = SANGRE_FX

    def gota(cx, cy, r, alto=1.0):
        for yy in range(H):
            for xx in range(W):
                dx, dy = (xx + 0.5 - cx) / r, (yy + 0.5 - cy) / (r * alto)
                d = dx * dx + dy * dy
                if d <= 1.0:
                    c = S[int(np.clip(2 + d * 4 + dy * 1.5, 0, len(S) - 1))]
                    if dx < -0.1 and dy < -0.1 and d < 0.35:
                        c = S[0]
                    punto(img, xx, yy, c)

    if fr == 'C':                                      # gota que sale
        gota(3.0, 4.2, 2.1, 1.25)
        punto(img, 3, 0, S[3])
        punto(img, 2, 1, S[2])
        punto(img, 3, 1, S[4])
    elif fr == 'B':                                    # salpicadura
        gota(5.5, 5.2, 3.0, 0.9)
        for (x, y, r) in ((1.5, 2.5, 1.0), (9.5, 2.0, 1.1), (10.0, 7.5, 0.9), (1.2, 8.2, 0.8), (6.0, 1.0, 0.7)):
            gota(x, y, r)
    else:                                              # cae y se esparce
        gota(8.5, 4.5, 3.4, 0.55)
        for (x, y, r) in ((2.0, 4.0, 1.1), (14.8, 4.6, 1.2), (4.6, 6.6, 0.9), (12.6, 6.8, 0.9), (0.8, 6.8, 0.7),
                          (16.2, 7.0, 0.7), (6.0, 1.5, 0.7), (11.0, 1.2, 0.7)):
            gota(x, y, r, 0.8)
    return desde_img(img, ox, oy)


def tfog(fr):
    """Niebla de teletransporte: llamarada verde de brujería (A-C), humo verdoso que sube y se deshace
    (D-J), chispas verdes."""
    W, H, ox, oy = 50, 60, 25, 59
    img = lienzo(W, H)
    k = 'ABCDEFGHIJ'.index(fr)
    cx, suelo = 25.0, 59.0
    # humo (detrás): aparece en C, sube y se deshace
    if k >= 2:
        t = (k - 2) / 7.0                               # 0 → 1
        for j, (dx, r, s) in enumerate(((-6, 9, 0), (6, 9.5, 1), (0, 11, 2))):
            nube(img, cx + dx * (1 + t), suelo - 26 - 18 * t - j * 4, r * (0.8 + 0.6 * t), 0.13 * k + j * 0.3,
                 410 + j, HUMO_VERDE[min(int(t * 3), 3):], rotura=min(0.95, 0.15 + t * 0.95), achatar=1.15)
    # corro de brujas: un anillo de fuego verde en el suelo (A-E)
    if k <= 4:
        x, y = malla(W, H, cx, suelo - 1.5)
        rr = np.hypot(x / 17.0, y / 3.2)
        n = fbm(x * 0.4, y * 0.8, 6.0 + k, 1.0, 425)
        anillo = (1 - np.abs(rr - 1.0) * 3.2) * (1.0 - 0.15 * k) + (n - 0.5) * 0.8
        pintar_calor(img, anillo, FUEGO_BRUJA[2:], minimo=5)
    # llamas: crecen hasta C y se apagan en F
    alto = (46, 52, 56, 42, 28, 16, 0, 0, 0, 0)[k]
    if alto:
        ancho = (32, 35, 36, 28, 22, 16)[k]
        H_ = H * SS2
        x, y = malla(W, H, cx, suelo + 1)
        c = calor_llama(x, y, alto, ancho, 0.17 * k, 421, lengua=1.25)
        # dos lenguas laterales
        c = np.maximum(c, calor_llama(x + 9, y, alto * 0.7, ancho * 0.5, 0.17 * k + 0.4, 422, lengua=1.2))
        c = np.maximum(c, calor_llama(x - 9, y, alto * 0.65, ancho * 0.5, 0.17 * k + 0.7, 423, lengua=1.2))
        if k >= 3:
            c = c - (k - 2) * 0.12
        pintar_calor(img, c, FUEGO_BRUJA, gamma=1.6 if k < 3 else 1.2)
    # chispas: suben y se apagan
    n = (6, 8, 12, 12, 10, 9, 8, 6, 4, 3)[k]
    chispas(img, cx, suelo - 6 - 3 * min(k, 5), n, 430, [4, 226, 112, 114, 116, 118, 120, 122], alto=40, ancho=13,
            fase=0.09 * k, largo=(1, 2), sube=1.0)
    return desde_img(img, ox, oy)


def ifog(fr):
    """Aparición de un objeto: destello blanco-azul con rayos (A, B), anillo de chispas (C) que se
    apaga (D, E)."""
    W, H, ox, oy = 50, 60, 25, 44
    img = lienzo(W, H)
    k = 'ABCDE'.index(fr)
    cx, cy = 25.0, 30.0
    x, y = malla(W, H, cx, cy)
    r = np.hypot(x, y)
    th = np.arctan2(y, x)
    if k <= 1:
        R = (12.0, 15.5)[k]
        rayos = np.clip(np.cos(th * 4 + k * 0.4), 0, 1) ** 8 * 1.0 + np.clip(np.cos(th * 4 + 0.785 + k * 0.4), 0, 1) ** 10 * 0.6
        calor = (1 - r / R) * 1.1 + rayos * np.clip(1 - r / (R * 2.0), 0, 1) * 0.9
        n = fbm(x * 0.4, y * 0.4, 1.0 + k, 1.0, 441)
        calor += (n - 0.5) * 0.35
        pintar_calor(img, calor, DESTELLO, gamma=0.9)
    elif k == 2:
        R = 14.0
        n = fbm(x * 0.5, y * 0.5, 4.0, 1.0, 442)
        calor = np.clip(1 - r / 4.5, 0, 1) * 0.8 + (n - 0.5) * 0.6 * np.clip(1 - r / 6, 0, 1) - 0.05
        pintar_calor(img, calor, DESTELLO[3:], gamma=1.0)
        rng2 = np.random.default_rng(443)
        for i in range(22):                           # anillo de destellos (cruces pequeñas)
            a = 2 * math.pi * i / 22 + rng2.uniform(-0.12, 0.12)
            rr = R * rng2.uniform(0.85, 1.12)
            px_, py_ = cx + math.cos(a) * rr, cy - math.sin(a) * rr * 0.9
            c = DESTELLO[2 + (i % 4)]
            punto(img, px_, py_, c)
            if i % 3 == 0:
                for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    punto(img, px_ + ddx, py_ + ddy, DESTELLO[6 + (i % 3)])
    rng = np.random.default_rng(450)
    n = (10, 14, 18, 14, 8)[k]
    for i in range(n):
        a = rng.uniform(0, 2 * math.pi)
        v = rng.uniform(0.6, 1.0)
        d = (6, 11, 16, 19, 21)[k] * v
        caida = (0, 0, 1.0, 3.0, 6.0)[k] * v
        px_, py_ = cx + math.cos(a) * d, cy - math.sin(a) * d * 0.85 + caida
        largo = 2 if k in (1, 2) else 1
        c0 = (0, 0, 1, 3, 5)[k]
        chispa(img, px_, py_, DESTELLO[c0 + (i % 3):], largo, dx=math.cos(a), dy=-math.sin(a) * 0.85)
    return desde_img(img, ox, oy)


def charco(fr):
    """POL5: charco de sangre en el suelo (visto casi de canto) con unos huesos y un jirón de tela."""
    W, H, ox, oy = 55, 10, 27, 5
    img = lienzo(W, H)
    x, y = malla(W, H, 27.5, 5.0)
    n = fbm(x * 0.16, y * 0.6, 2.0, 1.0, 461)
    d = np.hypot(x / 25.0, y / 3.6)
    dens = (1 - d) * 1.3 + (n - 0.5) * 1.1
    # brillo: más claro donde el charco es fino (borde) y un reflejo en el centro
    SANG = [187, 186, 185, 184, 183, 182, 46, 45, 44]
    vis = pintar_calor(img, dens * 0.9 + 0.1, SANG[::-1], gamma=1.0)
    for (xx, yy) in ((20, 4), (21, 4), (22, 4), (31, 5), (32, 5), (24, 3)):
        punto(img, xx, yy, 180)
    # jirón de tela parda
    for yy in range(3, 7):
        for xx in range(34, 42 - (yy - 3)):
            if (xx + yy) % 5 != 0:
                punto(img, xx, yy, (238, 237, 236, 79)[(xx * 7 + yy * 3) % 4])
    # huesos: un fémur, una costilla y una mandíbula
    HU = [128, 130, 144, 146, 149]
    for t in range(12):
        punto(img, 10 + t, 6 - t * 0.25, HU[2] if t % 3 else HU[1])
        punto(img, 10 + t, 5 - t * 0.25, HU[0] if t < 10 else HU[2])
    for (xx, yy) in ((9, 5), (9, 6), (8, 6), (22, 3), (22, 2), (23, 2)):
        punto(img, xx, yy, HU[3])
    for t in range(7):
        punto(img, 26 + t, 7 - math.sin(t / 6 * math.pi) * 2.0, HU[1])
    for (xx, yy, c) in ((44, 6, HU[2]), (45, 5, HU[1]), (46, 5, HU[1]), (47, 5, HU[2]), (48, 6, HU[3]),
                        (44, 7, HU[3])):
        punto(img, xx, yy, c)
    return desde_img(img, ox, oy)


def dibujar_efecto(lump):
    pre, fr = lump[:4], lump[4]
    return {'PUFF': puff, 'BLUD': blud, 'TFOG': tfog, 'IFOG': ifog, 'POL5': charco}[pre](fr)


def dibujar_piedra(lump):
    pre, fr = lump[:4], lump[4]
    if pre == 'COL1':
        return recortar(trazar(*col_piedra(52), 8))
    if pre == 'COL2':
        return recortar(trazar(*col_piedra(38, roto=True), 8))
    if pre == 'COL3':
        return recortar(trazar(*col_ladrillo(48), 8))
    if pre == 'COL4':
        return recortar(trazar(*col_ladrillo(38, desmochado=True), 8))
    if pre == 'COL6':
        return recortar(trazar(*col_ladrillo(36, calavera=True), 8))
    if pre == 'COL5':
        return recortar(trazar(*col_nido(fr), 10))
    if pre == 'ELEC':
        return recortar(trazar(*picota(), 6))
    if pre == 'SMIT':
        return recortar(trazar(*menhir(), 8))
    if pre == 'SMT2':
        return recortar(trazar(*mojon(), 8))
    if pre == 'TRE1':
        return recortar(trazar(*olivo(), 8))
    if pre == 'TRE2':
        return recortar(trazar(*alcornoque(), 8))
    raise KeyError(lump)


# ============================================================================= lumps
def lumps():
    out = {}
    for n in ('COL1A0', 'COL2A0', 'COL3A0', 'COL4A0', 'COL5A0', 'COL5B0', 'COL6A0', 'ELECA0', 'SMITA0', 'SMT2A0',
              'TRE1A0', 'TRE2A0'):
        out[n] = dibujar_piedra
    for n in ('GOR1A0', 'GOR1B0', 'GOR1C0', 'GOR2A0', 'GOR3A0', 'GOR4A0', 'GOR5A0', 'POL1A0', 'POL2A0', 'POL3A0',
              'POL3B0', 'POL4A0', 'POL6A0', 'POL6B0'):
        out[n] = dibujar_colgados
    for fr in 'ABC':
        out['CEYE' + fr + '0'] = dibujar_ojo
        out['FSKU' + fr + '0'] = dibujar_fsku
        out['BLUD' + fr + '0'] = dibujar_efecto
    for fr in 'ABCD':
        out['PUFF' + fr + '0'] = dibujar_efecto
    for fr in 'ABCDEFGHIJ':
        out['TFOG' + fr + '0'] = dibujar_efecto
    for fr in 'ABCDE':
        out['IFOG' + fr + '0'] = dibujar_efecto
    out['POL5A0'] = dibujar_efecto
    out['COLUA0'] = dibujar_llamas
    out['CANDA0'] = dibujar_llamas
    out['CBRAA0'] = dibujar_llamas
    for p in ('TBLU', 'TGRN', 'TRED', 'SMBT', 'SMGT', 'SMRT'):
        for fr in 'ABCD':
            out[p + fr + '0'] = dibujar_llamas
    for fr in 'ABC':
        out['FCAN' + fr + '0'] = dibujar_llamas
    return out


# ----------------------------------------------------------------------------- hoja de contactos
def freedoom(nombres):
    d = dict(read_wad(IWAD)[1])
    return {n: decode_patch(d[n], PAL) for n in nombres if n in d}


def hoja(images, offs, path, escala=3, por_fila=8):
    """Hoja ampliada: cada lump nuestro (izquierda) junto al de Freedoom (derecha), apoyados en la
    misma línea (en rojo, el origen del objeto: suelo o techo)."""
    nombres = list(images)
    ref = freedoom(nombres)
    filas = [nombres[i:i + por_fila] for i in range(0, len(nombres), por_fila)]
    bloques = []
    for f in filas:
        arriba = max(max(offs[n][1], ref[n][1][1] if n in ref else 0) for n in f)
        abajo = max(max(images[n].height - offs[n][1], (ref[n][0].height - ref[n][1][1]) if n in ref else 0) for n in f)
        ancho = [max(images[n].width, ref[n][0].width if n in ref else 0) for n in f]
        bloques.append((f, arriba, max(abajo, 2), ancho))
    W = max(sum(2 * w * escala + 24 for w in b[3]) for b in bloques)
    H = sum((b[1] + b[2]) * escala + 26 for b in bloques)
    sheet = Image.new('RGB', (W, H), (60, 60, 68))
    dr = ImageDraw.Draw(sheet)
    y0 = 0
    for f, arr, aba, ancho in bloques:
        suelo = y0 + 20 + arr * escala
        x0 = 0
        for n, w in zip(f, ancho):
            dr.text((x0 + 4, y0 + 4), n, fill=(240, 240, 240))
            for k, par in enumerate(((images[n], offs[n]), ref.get(n))):
                if par is None:
                    continue
                im, off = par
                big = im.resize((im.width * escala, im.height * escala), Image.NEAREST)
                cx = x0 + 8 + (w * escala + 8) * k + w * escala // 2
                sheet.paste(big, (int(cx - off[0] * escala), int(suelo - off[1] * escala)), big)
                dr.line([(cx - 3 * escala, suelo), (cx + 3 * escala, suelo)], fill=(220, 60, 60))
            x0 += 2 * w * escala + 24
        y0 += (arr + aba) * escala + 26
    sheet.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--salida', required=True, help='carpeta de PNG (arte/sprites)')
    ap.add_argument('--solo', default='', help='lumps separados por comas (o prefijos: COLU,TBLU)')
    ap.add_argument('--hoja', default='', help='hoja de contactos (PNG) junto a los de Freedoom')
    args = ap.parse_args()
    os.makedirs(args.salida, exist_ok=True)
    todos = lumps()
    pedidos = [n.strip().upper() for n in args.solo.split(',') if n.strip()]
    nombres = [n for n in todos if not pedidos or any(n.startswith(p) for p in pedidos)]
    ruta_off = os.path.join(args.salida, 'offsets_decoracion.json')
    offs = json.load(open(ruta_off)) if os.path.exists(ruta_off) else {}
    images = {}
    for n in nombres:
        im, off = todos[n](n)
        im.save(os.path.join(args.salida, n + '.png'))
        images[n] = im
        offs[n] = [int(off[0]), int(off[1])]
        print(f'{n} {im.width}x{im.height} offsets {off}', flush=True)
    with open(ruta_off, 'w') as f:
        json.dump(dict(sorted(offs.items())), f, indent=1)
    if args.hoja:
        hoja(images, offs, args.hoja)


if __name__ == '__main__':
    main()
