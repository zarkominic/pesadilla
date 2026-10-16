#!/usr/bin/env python3
"""penitente.py — dibuja POR CÓDIGO al PENITENTE (sustituye al zombi POSS de Freedoom).

Nazareno de procesión convertido en aparición: capirote altísimo granate casi negro con la punta
torcida, antifaz con dos agujeros de ojos que brillan, túnica negra raída, cordón de esparto,
manos y pies huesudos y un trabuco (culata de nogal, cañón de latón con boca acampanada).

Técnica: modelo 3D de primitivas SDF (esferas, conos, cápsulas, cajas…) con poses paramétricas,
trazado con numpy (raymarching ortográfico, cámara 10° desde arriba). Se renderiza a 4x, se
sombrea con pocas tonalidades por material (rampas exactas de PLAYPAL), se reduce a 1x por
mayoría dando prioridad a lo que está más cerca (el trabuco no desaparece delante de la túnica)
y se añade un contorno oscuro de 1 px. Así los 8 ángulos son coherentes de verdad.

Los PNG salen con el eje del cuerpo en el centro exacto del ancho y la fila inferior en el suelo
(3 px por debajo del apoyo, como Freedoom). Para que construir_pwad.py (que recorta lo
transparente y centra) no desplace el sprite, se dejan dos píxeles invisibles (alfa 1, no se
dibujan: el umbral es 128) en las esquinas inferiores: el recorte siempre conserva el lienzo.

Uso (determinista, regenera los 70 PNG POSS*):
    ~/.venvs/pesadilla/bin/python tools/arte/penitente.py --salida arte/sprites
    … --solo POSSA1,POSSE3      solo esos lumps
    … --hoja hoja.png           además, hoja de contactos ampliada x3 con etiquetas
"""
import argparse
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RAIZ, 'tools', 'wad'))
from doomgfx import PaletteMapper, read_palette  # noqa: E402

IWAD = os.path.join(RAIZ, 'wads', 'freedoom-0.13.0', 'freedoom1.wad')
SS = 4                      # submuestras por píxel y eje
TILT = math.radians(10)     # cámara ligeramente desde arriba
CULL = 3.0                  # más lejos que esto de la esfera envolvente: basta la cota


# ----------------------------------------------------------------------------- vectores
def V(*a):
    return np.array(a[0] if len(a) == 1 else a, dtype=float)


def nrm(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], float)


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], float)


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], float)


def rad(d):
    return math.radians(d)


def rot_axis(axis, a):
    x, y, z = nrm(axis)
    c, s, t = math.cos(a), math.sin(a), 1 - math.cos(a)
    return np.array([[t * x * x + c, t * x * y - s * z, t * x * z + s * y],
                     [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
                     [t * x * z - s * y, t * y * z + s * x, t * z * z + c]])


def basis(f, up=(0, 1, 0)):
    """Matriz (columnas x', y', z') con z' = f y y' lo más parecido posible a «up»."""
    f = nrm(f)
    r = np.cross(f, nrm(up))
    if np.linalg.norm(r) < 1e-6:
        r = np.cross(f, (0, 0, 1))
    r = nrm(r)
    u = np.cross(r, f)
    return np.column_stack([r, u, f])


class Frame:
    """Sistema de referencia rígido: local → padre como o + R·q."""

    def __init__(self, o=(0, 0, 0), R=None):
        self.o = V(o)
        self.R = np.eye(3) if R is None else np.asarray(R, float)

    def p(self, q):
        return self.o + self.R @ V(q)

    def d(self, v):
        return self.R @ V(v)

    def M(self, Ml=None):
        return self.R if Ml is None else self.R @ Ml

    def __mul__(self, other):  # self ∘ other
        return Frame(self.p(other.o), self.R @ other.R)

    def to_local(self, P):
        return (P - self.o) @ self.R


def _len(v):
    return np.sqrt(np.einsum('ij,ij->i', v, v))


# ----------------------------------------------------------------------------- materiales
ROBE, HOOD, BELT, SKIN, WOOD, BRASS, HOLE, EYE, SOCKET, FLASH, BLOOD, BONE, FLESH, RAG, MUD = range(15)
# Rampas de índices de PLAYPAL, de oscuro a claro (colores exactos de la paleta).
RAMPS = {
    ROBE: [7, 6, 5, 110, 108, 105, 103],          # negro sucio (11…87 gris)
    HOOD: [7, 6, 47, 45, 43, 40, 37],             # granate casi negro
    BELT: [150, 148, 146, 144, 128],              # esparto
    SKIN: [140, 136, 132, 129, 86],               # hueso pálido
    WOOD: [2, 239, 238, 15, 13, 73],              # nogal oscuro
    BRASS: [167, 166, 165, 164, 163, 162, 161],   # latón
    HOLE: [0],
    SOCKET: [0],
    EYE: [216, 213],                              # brillo rojo-anaranjado
    FLASH: [221, 215, 213, 229, 226, 225],        # fogonazo
    BLOOD: [191, 188, 185, 182, 179, 176],
    BONE: [109, 104, 98, 92, 87, 83],
    FLESH: [45, 40, 35, 30, 26],
    RAG: [7, 6, 5, 110, 108, 105],               # jirones de túnica
    MUD: [7, 2, 239, 238, 237, 236],             # barro en el bajo
}
EMISSIVE = (EYE, FLASH)
OUTLINE = 2      # (23,15,7): casi negro cálido


# ----------------------------------------------------------------------------- primitivas SDF
class Prim:
    cut = None
    warp = None

    def __call__(self, P):
        Q = P if self.warp is None else self.warp(P)
        d = self.sdf(Q)
        if self.cut is not None:
            d = np.maximum(d, self.cut(P))
        return d


class Sphere(Prim):
    def __init__(self, c, r, mat):
        self.c, self.r, self.mat = V(c), r, mat
        self.bc, self.br = self.c, r

    def sdf(self, P):
        return _len(P - self.c) - self.r


class Ellipsoid(Prim):
    def __init__(self, c, radii, M=None, mat=0):
        self.c, self.rr, self.mat = V(c), V(radii), mat
        self.M = np.eye(3) if M is None else M
        self.bc, self.br = self.c, float(max(radii))

    def sdf(self, P):
        q = (P - self.c) @ self.M
        k0 = _len(q / self.rr)
        k1 = _len(q / (self.rr * self.rr))
        return k0 * (k0 - 1) / np.maximum(k1, 1e-9)


class RoundCone(Prim):
    """Cápsula de radio variable (iq)."""

    def __init__(self, a, b, r1, r2, mat):
        self.a, self.b, self.r1, self.r2, self.mat = V(a), V(b), r1, r2, mat
        self.bc = (self.a + self.b) / 2
        self.br = np.linalg.norm(self.b - self.a) / 2 + max(r1, r2)

    def sdf(self, P):
        ba = self.b - self.a
        l2 = ba @ ba
        rr = self.r1 - self.r2
        a2 = l2 - rr * rr
        il2 = 1.0 / l2
        pa = P - self.a
        y = pa @ ba
        z = y - l2
        xv = pa * l2 - np.outer(y, ba)
        x2 = np.einsum('ij,ij->i', xv, xv)
        y2 = y * y * l2
        z2 = z * z * l2
        k = np.sign(rr) * rr * rr * x2
        d3 = (np.sqrt(np.maximum(x2 * a2 * il2, 0)) + y * rr) * il2 - self.r1
        d1 = np.sqrt(x2 + z2) * il2 - self.r2
        d2 = np.sqrt(x2 + y2) * il2 - self.r1
        return np.where(np.sign(z) * a2 * z2 > k, d1, np.where(np.sign(y) * a2 * y2 < k, d2, d3))


class CappedCone(Prim):
    """Tronco de cono exacto entre a (radio ra) y b (radio rb) (iq)."""

    def __init__(self, a, b, ra, rb, mat):
        self.a, self.b, self.ra, self.rb, self.mat = V(a), V(b), ra, rb, mat
        self.bc = (self.a + self.b) / 2
        self.br = np.linalg.norm(self.b - self.a) / 2 + max(ra, rb)

    def sdf(self, P):
        ba = self.b - self.a
        baba = ba @ ba
        rba = self.rb - self.ra
        pa = P - self.a
        papa = np.einsum('ij,ij->i', pa, pa)
        paba = (pa @ ba) / baba
        x = np.sqrt(np.maximum(papa - paba * paba * baba, 0))
        cax = np.maximum(0, x - np.where(paba < 0.5, self.ra, self.rb))
        cay = np.abs(paba - 0.5) - 0.5
        k = rba * rba + baba
        f = np.clip((rba * (x - self.ra) + paba * baba) / k, 0, 1)
        cbx = x - self.ra - f * rba
        cby = paba - f
        s = np.where((cbx < 0) & (cay < 0), -1.0, 1.0)
        return s * np.sqrt(np.minimum(cax * cax + cay * cay * baba, cbx * cbx + cby * cby * baba))


class Box(Prim):
    def __init__(self, c, half, M=None, rnd=0.0, mat=0):
        self.c, self.h, self.rnd, self.mat = V(c), V(half), rnd, mat
        self.M = np.eye(3) if M is None else M
        self.bc, self.br = self.c, float(np.linalg.norm(self.h)) + rnd

    def sdf(self, P):
        q = np.abs((P - self.c) @ self.M) - (self.h - self.rnd)
        out = _len(np.maximum(q, 0))
        return out + np.minimum(q.max(axis=1), 0) - self.rnd


class EllCone(Prim):
    """Tronco de cono de sección elíptica: base en o (radios rx0, rz0), tapa a altura h (rx1, rz1).
    F: Frame cuyo eje y' es el eje del cono. Distancia aproximada (vale para el trazado amortiguado)."""

    def __init__(self, F, h, r0, r1, mat):
        self.F, self.hh, self.r0, self.r1, self.mat = F, h, V(r0), V(r1), mat
        self.bc = F.p((0, h / 2, 0))
        self.br = math.hypot(h / 2, max(*r0, *r1))

    def sdf(self, P):
        q = self.F.to_local(P)
        t = np.clip(q[:, 1] / self.hh, 0, 1)
        rx = self.r0[0] + (self.r1[0] - self.r0[0]) * t
        rz = self.r0[1] + (self.r1[1] - self.r0[1]) * t
        e = np.sqrt((q[:, 0] / rx) ** 2 + (q[:, 2] / rz) ** 2)
        drad = (e - 1) * np.minimum(rx, rz) * 0.9
        dcap = np.maximum(-q[:, 1], q[:, 1] - self.hh)
        return np.maximum(drad, dcap)


class Ring(Prim):
    """Anillo elíptico (cordón ceñido a la cintura)."""

    def __init__(self, F, rx, rz, tube, mat):
        self.F, self.rx, self.rz, self.tube, self.mat = F, rx, rz, tube, mat
        self.bc, self.br = F.o, max(rx, rz) + tube

    def sdf(self, P):
        q = self.F.to_local(P)
        e = np.sqrt((q[:, 0] / self.rx) ** 2 + (q[:, 2] / self.rz) ** 2)
        dr = (e - 1) * min(self.rx, self.rz)
        return np.sqrt(dr * dr + q[:, 1] ** 2) - self.tube


class Group:
    """Unión (suave si k>0) de primitivas, con recorte opcional y transformación afín opcional
    (para aplastar el cadáver): local = (P - t) @ Ainv.T, distancia × dscale."""

    def __init__(self, prims, k=0.0, cut=None, xf=None, name=''):
        self.prims, self.k, self.cut, self.name = prims, k, cut, name
        self.xf = xf
        cs = np.array([p.bc for p in prims])
        lo = (cs - [[p.br] for p in prims]).min(0)
        hi = (cs + [[p.br] for p in prims]).max(0)
        self.bc = (lo + hi) / 2
        self.br = float(max(np.linalg.norm(c - self.bc) + p.br for c, p in zip(cs, prims)))

    def model_bound(self):
        if self.xf is None:
            return self.bc, self.br
        A, t, _ = self.xf
        return A @ self.bc + t, self.br * float(np.abs(np.linalg.eigvals(A @ A.T)).max() ** 0.5)

    def eval(self, P):
        n = len(P)
        if self.xf is not None:
            A, t, ds = self.xf
            Q = (P - t) @ np.linalg.inv(A).T
        else:
            Q, ds = P, 1.0
        gb = _len(Q - self.bc) - self.br
        d = gb.copy()
        mat = np.full(n, self.prims[0].mat, int)
        near = np.nonzero(gb < CULL)[0]
        if len(near):
            Qn = Q[near]
            best = np.full(len(near), 1e9)
            raw = np.full(len(near), 1e9)
            mn = np.full(len(near), self.prims[0].mat, int)
            for pr in self.prims:
                bd = _len(Qn - pr.bc) - pr.br
                dp = bd.copy()
                sel = bd < CULL
                if sel.any():
                    dp[sel] = pr(Qn[sel])
                if self.k > 0:
                    h = np.clip(0.5 + 0.5 * (best - dp) / self.k, 0, 1)
                    best = best * (1 - h) + dp * h - self.k * h * (1 - h)
                else:
                    best = np.minimum(best, dp)
                closer = dp < raw
                mn[closer] = pr.mat
                raw = np.minimum(raw, dp)
            if self.cut is not None:
                best = np.maximum(best, self.cut(Qn))
            d[near] = best
            mat[near] = mn
        return d * ds, mat


def scene_eval(groups, P):
    d = np.full(len(P), 1e9)
    m = np.zeros(len(P), int)
    for g in groups:
        dg, mg = g.eval(P)
        c = dg < d
        d = np.where(c, dg, d)
        m = np.where(c, mg, m)
    return d, m


# ----------------------------------------------------------------------------- ruido determinista
def vnoise(P, scale, seed=0):
    Q = P * scale + seed * 17.13
    i = np.floor(Q).astype(np.int64)
    f = Q - i
    u = f * f * (3 - 2 * f)

    def h(dx, dy, dz):
        n = ((i[:, 0] + dx) * 73856093) ^ ((i[:, 1] + dy) * 19349663) ^ ((i[:, 2] + dz) * 83492791)
        n = (n ^ (n >> 13)) * 1274126177
        n = n ^ (n >> 16)
        return (n & 0xffff) / 65535.0

    out = 0
    for dx in (0, 1):
        wx = u[:, 0] if dx else 1 - u[:, 0]
        for dy in (0, 1):
            wy = u[:, 1] if dy else 1 - u[:, 1]
            for dz in (0, 1):
                wz = u[:, 2] if dz else 1 - u[:, 2]
                out = out + wx * wy * wz * h(dx, dy, dz)
    return out


# ----------------------------------------------------------------------------- render
class Render:
    def __init__(self):
        self.pal = read_palette(IWAD)
        self.palarr = np.array(self.pal, float)
        self.mapper = PaletteMapper(self.pal)

    def nearest(self, rgb):
        return self.mapper.index(tuple(int(round(c)) for c in np.clip(rgb, 0, 255)))

    def render(self, groups, extras, angle):
        th = (angle - 1) * math.pi / 4 if angle else 0.0
        R = rot_y(-th)                         # modelo → cámara
        Xc = V(1, 0, 0)
        Uc = V(0, math.cos(TILT), -math.sin(TILT))
        Dc = V(0, -math.sin(TILT), -math.cos(TILT))
        # Límites en pantalla a partir de las esferas envolventes.
        xs, ys = [], []
        cen = []
        for g in groups:
            c, r = g.model_bound()
            cc = R @ c
            xs += [cc[0] - r, cc[0] + r]
            ys += [cc @ Uc - r, cc @ Uc + r]
            cen.append((c, r))
        hw = int(math.ceil(max(-min(xs), max(xs)))) + 2
        top = int(math.ceil(max(ys))) + 2
        W, H = 2 * hw, top + 1                 # fila H-1 = sy en [-1, 0)
        jj, ii = np.meshgrid(np.arange(W * SS), np.arange(H * SS))
        sx = -hw + (jj + 0.5) / SS
        sy = top - (ii + 0.5) / SS
        Oc = sx.reshape(-1, 1) * Xc + sy.reshape(-1, 1) * Uc - 400 * Dc
        O = Oc @ R
        D = Dc @ R
        # Esfera envolvente global → rango de t.
        lo = np.min([c - r for c, r in cen], axis=0)
        hi = np.max([c + r for c, r in cen], axis=0)
        C = (lo + hi) / 2
        Rb = max(np.linalg.norm(c - C) + r for c, r in cen)
        oc = O - C
        b = oc @ D
        cterm = np.einsum('ij,ij->i', oc, oc) - Rb * Rb
        disc = b * b - cterm
        ok = disc > 0
        sq = np.sqrt(np.maximum(disc, 0))
        t0 = np.where(ok, -b - sq, np.inf)
        t1 = np.where(ok, -b + sq, -np.inf)
        N = len(O)
        t = np.maximum(t0, 0)
        hit = np.zeros(N, bool)
        idx = np.nonzero(ok)[0]
        for _ in range(220):
            if len(idx) == 0:
                break
            P = O[idx] + D * t[idx, None]
            d, _m = scene_eval(groups, P)
            h = d < 0.01
            hit[idx[h]] = True
            t[idx] += np.where(h, 0, np.maximum(d * 0.8, 0.004))
            cont = (~h) & (t[idx] < t1[idx])
            idx = idx[cont]
        hidx = np.nonzero(hit)[0]
        P = O[hidx] + D * t[hidx, None]
        _, mat = scene_eval(groups, P)
        # Normales por diferencias centrales.
        e = 0.04
        nr = np.zeros_like(P)
        for k in range(3):
            dv = np.zeros(3)
            dv[k] = e
            nr[:, k] = scene_eval(groups, P + dv)[0] - scene_eval(groups, P - dv)[0]
        nr /= np.maximum(_len(nr), 1e-9)[:, None]
        # Oclusión ambiental barata.
        occ = np.zeros(len(P))
        for hgt, w in ((0.7, 1.0), (1.6, 0.7), (3.0, 0.45)):
            dd = scene_eval(groups, P + nr * hgt)[0]
            occ += w * np.clip((hgt - dd) / hgt, 0, 1)
        ao = np.clip(1 - 0.42 * occ, 0.3, 1)
        L = nrm((-0.5, 0.75, 0.55)) @ R
        Vv = -D
        diff = np.clip(nr @ L, 0, 1)
        inten = (0.24 + 0.86 * diff) * ao
        nz = vnoise(P, 0.9, 1) * 0.6 + vnoise(P, 2.3, 2) * 0.4
        inten *= 0.82 + 0.36 * nz
        refl = 2 * (nr @ L)[:, None] * nr - L
        spec = np.clip(refl @ Vv, 0, 1)
        lvl_extra = np.zeros(len(P))

        # Ajustes por material.
        ang_body = np.arctan2(P[:, 0] - extras.get('axis', (0, 0))[0], P[:, 2] - extras.get('axis', (0, 0))[1])
        m = mat == ROBE
        inten[m] *= 1 + 0.2 * np.sin(9 * ang_body[m] + 2.2 * nz[m])            # pliegues
        m = mat == HOOD
        inten[m] *= 0.92 + 0.1 * np.sin(14 * ang_body[m] + 3 * nz[m])
        # Barro en el bajo de la túnica.
        mud = (mat == ROBE) & (P[:, 1] < 3.5 + 4.0 * vnoise(P, 0.6, 5)) & (vnoise(P, 1.7, 6) > 0.35)
        mat[mud] = MUD
        m = mat == BELT
        inten[m] *= 0.78 + 0.42 * (np.sin(ang_body[m] * 26 + P[m, 1] * 5) > -0.2)  # trenzado
        for mm, sp, pw in ((BRASS, 0.9, 10), (SKIN, 0.25, 6), (BLOOD, 0.6, 12), (BONE, 0.3, 8)):
            m = mat == mm
            inten[m] += sp * spec[m] ** pw
        # Ojos: agujeros en el antifaz con brillo dentro.
        for ec in extras.get('eyes', []):
            de = _len(P - ec)
            m = (mat == HOOD) & (de < 1.3)
            mat[m] = SOCKET
            m = (mat == SOCKET) & (de < 0.8)
            mat[m] = EYE
            lvl_extra[m] = (de[m] < 0.45)
        # Boca del trabuco: el interior es negro.
        mz = extras.get('muzzle')
        if mz is not None:
            c0, f, rr = mz
            rel = P - c0
            along = rel @ f
            radial = _len(rel - np.outer(along, f))
            m = (mat == BRASS) & (radial < rr) & (along > -2.2)
            mat[m] = HOLE
        # Manchas de sangre sobre la tela.
        for sc, sr in extras.get('stains', []):
            ds = _len(P - sc)
            m = np.isin(mat, (ROBE, HOOD, RAG)) & (ds < sr * (0.75 + 0.5 * nz))
            mat[m] = BLOOD
        # Índice de paleta por submuestra.
        idxs = np.zeros(len(P), int)
        for mm, ramp in RAMPS.items():
            m = mat == mm
            if not m.any():
                continue
            n = len(ramp)
            if mm == FLASH:
                fc, frad = extras['flash_core']
                lv = np.clip((1 - _len(P[m] - fc) / frad) * n * 1.15, 0, n - 1)
            elif mm == EYE:
                lv = lvl_extra[m]
            else:
                lv = np.clip(np.floor(inten[m] * n), 0, n - 1)
            idxs[m] = np.array(ramp)[lv.astype(int)]
        # Luz del fogonazo sobre el cuerpo (fotograma F, que el juego pinta a pleno brillo).
        fl = extras.get('flash_light')
        if fl is not None:
            lp, lr = fl
            rel = lp - P
            dl = _len(rel)
            ndl = np.clip(np.einsum('ij,ij->i', nr, rel / dl[:, None]), 0, 1)
            amt = np.clip(1 - dl / lr, 0, 1) ** 1.3 * (0.35 + 0.65 * ndl)
            m = (amt > 0.08) & ~np.isin(mat, (FLASH, EYE, HOLE, SOCKET))
            cache = {}
            for k in np.nonzero(m)[0]:
                key = (idxs[k], int(amt[k] * 8))
                if key not in cache:
                    base = self.palarr[idxs[k]]
                    a = key[1] / 8
                    cache[key] = self.nearest(base * (1 + 0.5 * a) + a * np.array([230, 140, 40]))
                idxs[k] = cache[key]
        # Rejilla de submuestras.
        IDX = np.full(N, -1, int)
        IDX[hidx] = idxs
        MAT = np.full(N, -1, int)
        MAT[hidx] = mat
        DEP = np.full(N, np.inf)
        DEP[hidx] = t[hidx]
        return self.downsample(IDX.reshape(H * SS, W * SS), MAT.reshape(H * SS, W * SS),
                               DEP.reshape(H * SS, W * SS), W, H)

    def downsample(self, IDX, MAT, DEP, W, H):
        I = IDX.reshape(H, SS, W, SS).transpose(0, 2, 1, 3).reshape(H, W, SS * SS)
        M = MAT.reshape(H, SS, W, SS).transpose(0, 2, 1, 3).reshape(H, W, SS * SS)
        Dp = DEP.reshape(H, SS, W, SS).transpose(0, 2, 1, 3).reshape(H, W, SS * SS)
        out = np.full((H, W), -1, int)
        depth = np.full((H, W), np.inf)
        cov = (I >= 0).sum(2)
        for y, x in zip(*np.nonzero(cov >= 6)):
            ii, mm, dd = I[y, x], M[y, x], Dp[y, x]
            sel = ii >= 0
            ii, mm, dd = ii[sel], mm[sel], dd[sel]
            mats, counts = np.unique(mm, return_counts=True)
            choice = None
            for em in EMISSIVE:
                if em in mats and counts[list(mats).index(em)] >= 2:
                    choice = em
            if choice is None:
                cand = [(dd[mm == q].mean(), q) for q, c in zip(mats, counts) if c >= 4 or c == counts.max()]
                choice = min(cand)[1]
            pick = ii[mm == choice]
            vals, vc = np.unique(pick, return_counts=True)
            # Moda; en empate, el más claro (lo pequeño se lee mejor).
            best = vals[vc == vc.max()]
            out[y, x] = int(best[np.argmax(self.palarr[best].sum(1))])
            depth[y, x] = dd[mm == choice].min()
        return out, depth


def finish(out, depth, palarr):
    """Contorno de 1 px (fuera) y líneas por discontinuidad de profundidad (dentro) → RGBA."""
    H, W = out.shape
    op = out >= 0
    res = out.copy()
    # Línea interior: el píxel de detrás junto a algo mucho más cercano se oscurece.
    for y, x in zip(*np.nonzero(op)):
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            yy, xx = y + dy, x + dx
            if 0 <= yy < H and 0 <= xx < W and op[yy, xx] and depth[yy, xx] < depth[y, x] - 3.0:
                if palarr[out[y, x]].sum() > 3 * 40:
                    res[y, x] = OUTLINE
                break
    # Contorno exterior (4 vecinos), sin salir por debajo del lienzo.
    pad = np.pad(op, 1)
    ring = (pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:]) & ~op
    res[ring] = OUTLINE
    img = np.zeros((H, W, 4), np.uint8)
    vis = res >= 0
    img[vis, :3] = palarr[res[vis]].astype(np.uint8)
    img[vis, 3] = 255
    # Píxeles invisibles de anclaje (alfa 1): el recorte de construir_pwad conserva el lienzo.
    for x in (0, W - 1):
        if img[H - 1, x, 3] == 0:
            img[H - 1, x] = (0, 0, 0, 1)
    return Image.fromarray(img, 'RGBA')


def trim(img):
    """Recorta el lienzo de forma simétrica respecto al eje (y las filas vacías de arriba)."""
    a = np.array(img)
    H, W = a.shape[:2]
    vis = a[:, :, 3] >= 128
    cols = np.nonzero(vis.any(0))[0]
    rows = np.nonzero(vis.any(1))[0]
    half = W // 2
    need = max(half - cols.min(), cols.max() + 1 - half) if len(cols) else 1
    x0 = half - need
    a = a[rows.min():, x0:W - x0].copy()
    a[:, :, :][a[:, :, 3] < 128] = 0
    h, w = a.shape[:2]
    for x in (0, w - 1):
        if a[h - 1, x, 3] == 0:
            a[h - 1, x] = (0, 0, 0, 1)
    return Image.fromarray(a, 'RGBA')


# ----------------------------------------------------------------------------- modelo
HIP_Y = 27.0
SHOULDER = (6.0, 11.5, -0.2)       # hombro izquierdo en el marco del torso (x+ = izquierda del personaje)
NECK = (0.0, 15.0, 0.3)
UPPER_ARM, FOREARM = 8.5, 9.0


def ik(S, T, l1, l2, pole):
    d = T - S
    L = np.linalg.norm(d)
    if L > l1 + l2 - 0.05:
        s = L / (l1 + l2 - 0.05)
        l1, l2 = l1 * s, l2 * s
    a = (l1 * l1 - l2 * l2 + L * L) / (2 * L)
    h = math.sqrt(max(l1 * l1 - a * a, 0))
    u = d / L
    pp = pole - u * (pole @ u)
    pp = nrm(pp) if np.linalg.norm(pp) > 1e-6 else nrm(np.cross(u, (0, 0, 1)))
    return S + u * a + pp * h


def hem_cut(F, base=2.6, rag=1.0):
    """Bajo raído e irregular de la túnica (en el marco F del bajo)."""
    def cut(P):
        q = F.to_local(P)
        ph = np.arctan2(q[:, 0], q[:, 2])
        hy = (base + rag * (1.1 * np.sin(5 * ph + 0.7) + 0.8 * np.sin(11 * ph + 2.1)
                            + 0.55 * np.sin(19 * ph + 4.0) + 0.4 * np.sin(31 * ph + 1.3))
              + 1.6 * rag * np.maximum(0, np.sin(3 * ph + 0.4)) ** 12
              + 1.2 * rag * np.maximum(0, np.sin(7 * ph + 2.9)) ** 16)
        return np.maximum(hy, 0.5) - q[:, 1]
    return cut


def gun_parts(GF, mat_wood=WOOD, mat_metal=BRASS):
    """Trabuco en su marco: z' a lo largo del cañón, y' arriba, origen en la empuñadura."""
    p, M = GF.p, GF.M()
    parts = [
        Box(p((0, -1.0, -6.3)), (0.8, 1.8, 2.1), M @ rot_x(rad(-10)), 0.4, mat_wood),   # culata
        RoundCone(p((0, -0.6, -4.2)), p((0, 0.1, -0.2)), 1.05, 0.8, mat_wood),            # garganta
        RoundCone(p((0, -0.1, 0.0)), p((0, 0.15, 8.6)), 0.85, 0.7, mat_wood),             # caña
        Box(p((0, 0.5, 0.6)), (0.9, 0.85, 1.3), M, 0.3, mat_metal),                     # llave
        RoundCone(p((0, 1.2, -0.5)), p((0, 2.0, -0.1)), 0.4, 0.3, mat_metal),             # pie de gato
        RoundCone(p((0, 0.7, 0.0)), p((0, 0.7, 12.0)), 0.9, 0.95, mat_metal),             # cañón
        CappedCone(p((0, 0.7, 11.4)), p((0, 0.7, 15.3)), 0.95, 2.15, mat_metal),          # boca acampanada
        Ring(Frame(p((0, 0.7, 5.0)), M @ rot_x(rad(90))), 1.0, 1.0, 0.32, mat_metal),
        Ring(Frame(p((0, 0.7, 9.0)), M @ rot_x(rad(90))), 1.0, 1.0, 0.32, mat_metal),
    ]
    muzzle = (p((0, 0.7, 15.3)), GF.d((0, 0, 1)), 1.45)
    return parts, muzzle


def hand(c, along, mat=SKIN):
    """Mano huesuda: palma + pulgar + nudillos."""
    a = nrm(along)
    side = nrm(np.cross(a, (0, 1, 0))) if abs(a[1]) < 0.95 else V(1, 0, 0)
    return [Ellipsoid(c, (1.15, 1.45, 1.15), basis(a), mat),
            RoundCone(c + a * 0.6, c + a * 1.9 - V(0, 0.5, 0), 0.55, 0.45, mat),
            RoundCone(c + side * 0.9, c + side * 1.3 + a * 1.0, 0.45, 0.4, mat)]


DEFAULT = dict(
    bob=0.0, lean=7.0, twist=0.0, side=0.0, head_pitch=4.0, head_roll=0.0,
    foot_r=(-3.0, 0.0, 0.8), foot_l=(3.0, 0.0, -0.6), lift_r=0.0, lift_l=0.0,
    hem=(0.0, 0.0), hem_r=(9.8, 7.0), skirt=True,
    gun=dict(frame='upper', grip=(-4.2, 1.2, 6.2), f=(0.6, 0.1, 0.79), up=(0, 1, 0)),
    hand_r='gun', hand_l='gun', grip_r=(0, -0.45, -1.4), grip_l=(0, -1.0, 4.6),
    flash=False, root=None, flatten=None, bend=1.0, cords=0.0,
    stains=(), extra=(), hood_lift=0.0, no_hood=False, no_torso=False, no_arms=False, no_gun=False,
    eyes=True, crush=0.0, spray=(), legs=True,
)


def build(pose):
    p = dict(DEFAULT)
    p.update(pose)
    root = p['root'] or Frame()
    xf = p['flatten']
    groups = []
    extras = {'eyes': [], 'stains': []}

    up = root * Frame((0, HIP_Y + p['bob'], 0),
                      rot_y(rad(p['twist'])) @ rot_x(rad(p['lean'])) @ rot_z(rad(p['side'])))
    head = up * Frame(NECK, rot_x(rad(p['head_pitch'])) @ rot_z(rad(p['head_roll'])))
    if p['hood_lift']:
        head = Frame(head.o + V(0, p['hood_lift'], 0), head.R)

    # --- piernas y pies (bajo la túnica asoman los pies)
    body, skin = [], []
    legcloth = []
    for sx, foot, lift in ((-1, p['foot_r'], p['lift_r']), (1, p['foot_l'], p['lift_l'])):
        hipj = root.p((3.0 * sx, HIP_Y - 1 + p['bob'], 0))
        ank = root.p(V(foot) + (0, 1.6 + lift, 0))
        knee = ik(hipj, ank, 12.8, 12.8, root.d((0, 0, 1)))
        fwd = root.d((0.12 * sx, -0.05 if lift == 0 else -0.25, 1))
        skin += [RoundCone(ank - fwd * 0.9 - root.d((0, 0.4, 0)), ank + fwd * 3.9 - root.d((0, 0.9, 0)), 1.25, 1.0, SKIN),
                 RoundCone(ank, ank + (knee - ank) * 0.35, 0.85, 1.0, SKIN)]
        legcloth += [RoundCone(hipj, knee, 3.6, 3.2, ROBE), RoundCone(knee, ank + (knee - ank) * 0.12, 3.2, 2.6, ROBE)]

    # --- túnica: falda + tela de las piernas + torso (unión suave, bajo raído)
    hemF = root * Frame((p['hem'][0], 0, p['hem'][1] + 0.3))
    robe = []
    if p['skirt']:
        waist = root.p((0, HIP_Y + 1.5 + p['bob'], 0.2))
        hemc = hemF.o
        axis = waist - hemc
        ya = nrm(axis)                      # marco de la falda: y' = eje cintura-bajo
        xa = nrm(np.cross(ya, root.d((0, 0, 1))))
        Fsk = Frame(hemc, np.column_stack([xa, ya, np.cross(xa, ya)]))
        robe.append(EllCone(Fsk, np.linalg.norm(axis), p['hem_r'], p.get('waist_r', (6.4, 4.9)), ROBE))
        if p['legs']:
            robe += legcloth
    if not p['no_torso']:
        robe += [Ellipsoid(up.p((0, 7.0, -0.2)), (6.0, 8.2, 4.4), up.M(), ROBE),
                 Sphere(up.p((0, 10.5, -1.7)), 4.2, ROBE)]
        for sx in (-1, 1):
            robe.append(Sphere(up.p((SHOULDER[0] * sx, SHOULDER[1], SHOULDER[2])), 2.7, ROBE))
    if robe:
        groups.append(Group(robe, k=2.2, cut=hem_cut(hemF, rag=1.0 + p['crush']), name='robe'))
    if skin and p['legs']:
        groups.append(Group(skin, k=0.6, name='feet'))

    # --- cordón de esparto con nudo y cabos colgando
    if not p['no_torso']:
        bF = up * Frame((0, 1.4, 0.2))
        belt = [Ring(bF, 6.75, 5.15, 0.85, BELT)]
        knot = bF.p((2.4, -0.2, 5.1))
        sw = p['cords']
        e1 = up.p((3.0 + sw, -8.6, 5.9))
        e2 = up.p((1.9 + 0.7 * sw, -10.6, 5.6))
        belt += [Sphere(knot, 1.25, BELT), RoundCone(knot, e1, 0.65, 0.55, BELT), RoundCone(knot, e2, 0.65, 0.55, BELT),
                 Sphere(e1, 0.85, BELT), Sphere(e2, 0.85, BELT)]
        groups.append(Group(belt, k=0.4, name='belt'))

    # --- antifaz + capirote (granate), con la punta torcida
    if not p['no_hood']:
        Fa = head * Frame((0, -8.5, 0.6))
        anti = EllCone(Fa, 14.0, (7.4, 5.9), (4.3, 4.5), HOOD)
        anti.cut = (lambda F: (lambda P: (lambda q: (-0.9 - 0.4 * q[:, 2]) - q[:, 1])(F.to_local(P))))(Fa)
        dome = Ellipsoid(head.p((0, 4.0, 0.2)), (4.4, 3.4, 4.6), head.M(), HOOD)
        cone = CappedCone(head.p((0, 3.5, 0.0)), head.p((0, 25.0, -0.3)), 4.25, 0.3, HOOD)
        bend_dir = head.d(nrm((0.75, 0, -0.65)))
        bend = 2.6 * p['bend']
        cbase = head.p((0, 13.0, 0))
        cax = head.d((0, 1, 0))

        def warp(P, cbase=cbase, cax=cax, bend_dir=bend_dir, bend=bend):
            s = np.clip(((P - cbase) @ cax) / 12.0, 0, None)
            return P - np.outer(bend * s * s, bend_dir)
        cone.warp = warp
        cone.br += abs(bend) + 1
        groups.append(Group([anti, dome, cone], k=1.4, name='hood'))
        if p['eyes']:
            hg = groups[-1]
            for sx in (-1, 1):
                a = head.p((1.75 * sx, 1.9, 0))
                dirv = head.d((0.12 * sx, 0, 1))
                lo, hi = 0.0, 9.0
                for _ in range(30):
                    mid = (lo + hi) / 2
                    if hg.eval((a + dirv * mid)[None])[0][0] < 0:
                        lo = mid
                    else:
                        hi = mid
                extras['eyes'].append(a + dirv * lo)

    # --- trabuco
    gspec = p['gun']
    GF = None
    if not p['no_gun'] and gspec is not None:
        Mg = basis(gspec['f'], gspec.get('up', (0, 1, 0)))
        if gspec['frame'] == 'upper':
            GF = up * Frame(gspec['grip'], Mg)
        else:
            GF = Frame(gspec['grip'], Mg)
        gparts, muzzle = gun_parts(GF)
        groups.append(Group(gparts, k=0.25, name='gun'))
        extras['muzzle'] = muzzle
        if p['flash']:
            mc, f, _ = muzzle
            r_ = GF.d((1, 0, 0))
            u_ = GF.d((0, 1, 0))
            core = mc + f * 2.2
            fl = [Sphere(core, 2.5, FLASH), RoundCone(mc + f * 0.8, mc + f * 8.5, 1.8, 0.25, FLASH)]
            for dv in (r_, -r_, u_, -u_):
                dd = nrm(f * 0.8 + dv)
                fl.append(RoundCone(mc + f * 1.6, mc + f * 1.6 + dd * 5.5, 1.1, 0.2, FLASH))
            for dv in (r_ + u_, r_ - u_, -r_ + u_, -r_ - u_):
                dd = nrm(f * 1.2 + nrm(dv))
                fl.append(RoundCone(mc + f * 1.6, mc + f * 1.6 + dd * 3.6, 0.8, 0.2, FLASH))
            groups.append(Group(fl, k=0.6, name='flash'))
            extras['flash_core'] = (core, 9.0)
            extras['flash_light'] = (core, 22.0)

    # --- brazos (mangas acampanadas) y manos
    if not p['no_arms']:
        sleeves, hands = [], []
        for sx, which, gl in ((-1, 'hand_r', 'grip_r'), (1, 'hand_l', 'grip_l')):
            S = up.p((SHOULDER[0] * sx, SHOULDER[1], SHOULDER[2]))
            spec = p[which]
            if spec == 'gun' and GF is not None:
                T = GF.p(p[gl])
                along = GF.d((0, 0, 1))
            elif spec == 'gun':
                continue
            else:
                frame, pt = spec[0], spec[1]
                T = up.p(pt) if frame == 'upper' else root.p(pt) if frame == 'root' else V(pt)
                along = nrm(T - S)
            pole = up.d((0.8 * sx, -0.6, -0.7))
            E = ik(S, T, UPPER_ARM, FOREARM, pole)
            fa = nrm(T - E)
            cuff = T - fa * 2.7
            sleeves += [RoundCone(S, E, 2.4, 2.1, ROBE), RoundCone(E, cuff, 2.1, 2.7, ROBE)]
            hands += hand(T, along if spec == 'gun' else fa)
        groups.append(Group(sleeves, k=1.0, name='sleeves'))
        groups.append(Group(hands, k=0.4, name='hands'))

    def where(fr, pt):
        return up.p(pt) if fr == 'upper' else root.p(pt) if fr == 'root' else head.p(pt) if fr == 'head' else V(pt)

    extras['stains'] = [(where(fr, pt), r) for fr, pt, r in p['stains']]
    if p['spray']:
        groups.append(Group([Sphere(where(fr, pt), r, BLOOD) for fr, pt, r in p['spray']], name='spray'))
    for g in p['extra']:
        groups.append(g)
    if xf is not None:
        for g in groups:
            if g.name not in ('gun', 'extra', 'pool', 'spray'):
                g.xf = xf
        extras['eyes'] = []
    ax = root.p((0, 0, 0))
    extras['axis'] = (ax[0], ax[2])
    return groups, extras


# ----------------------------------------------------------------------------- poses
def walk(i):
    a = i * math.pi / 2
    c, s = math.cos(a), math.sin(a)
    return dict(
        bob=0.6 - 1.2 * abs(c), lean=7.0, twist=-5 * c, side=1.5 * s,
        head_pitch=3 + 3 * abs(c), head_roll=-2 * s,
        foot_r=(-3.0, 0, 0.8 + 5.2 * c), lift_r=1.7 * max(0, -s),
        foot_l=(3.0, 0, 0.8 - 5.2 * c), lift_l=1.7 * max(0, s),
        hem=(0.9 * s, 0.4 * c), hem_r=(9.8, 7.0 + 0.9 * abs(c)), cords=1.2 * s,
        gun=dict(frame='upper', grip=(-4.4, 1.0 + 0.4 * abs(c), 6.4), f=nrm((0.58, 0.34 + 0.04 * c, 0.74))),
    )


AIM = dict(lean=2.0, twist=-14, head_pitch=9, head_roll=-7, bob=0.0,
           foot_r=(-3.3, 0, -1.6), foot_l=(3.0, 0, 2.6), hem_r=(10.0, 7.6), hem=(0, 0.5),
           gun=dict(frame='model', grip=(-4.3, 38.4, 9.6), f=(0.0, 0.0, 1.0)),
           grip_r=(0, -0.45, -1.4), grip_l=(0, -1.0, 4.2))

FIRE = dict(AIM, lean=-3.0, head_pitch=4, twist=-12,
            gun=dict(frame='model', grip=(-4.3, 39.0, 8.0), f=nrm((0.0, math.sin(rad(9)), math.cos(rad(9))))),
            flash=True)

PAIN = dict(lean=-13, twist=10, side=-4, head_pitch=-16, head_roll=7, bob=0.4,
            foot_r=(-3.4, 0, 0.8), foot_l=(3.2, 0, -0.6), cords=-1.6, hem=(0, -0.7), hem_r=(10.2, 7.2),
            gun=dict(frame='upper', grip=(-16.0, 13.5, 4.0), f=nrm((-0.2, 0.9, 0.4))),
            grip_r=(0, -0.45, -1.4), hand_l=('upper', (17.0, 13.0, 3.0)))


def fall_root(alpha, psi, slide, lift):
    d = nrm((0.6, 0, -0.8))
    axis = np.cross((0, 1, 0), d)
    R = rot_axis(axis, rad(alpha)) @ rot_y(rad(psi))
    return Frame(-d * slide + V(0, lift, 0), R)


def deaths():
    chest = [('upper', (0.6, 8.5, 4.4), 3.6), ('upper', (-2.2, 5.0, 4.6), 2.2)]
    H = dict(lean=-21, twist=8, side=3, head_pitch=-28, head_roll=-8, bob=0.6,
             foot_r=(-3.4, 0, 1.2), foot_l=(3.2, 0, -0.8), cords=-2.0, hem=(0, -1.0), hem_r=(10.2, 7.4),
             gun=dict(frame='model', grip=(-19.0, 47.0, 4.0), f=nrm((-0.5, 0.85, 0.15))),
             hand_r=('upper', (-15.5, 17.0, 3.0)), hand_l=('upper', (15.0, 18.0, 2.0)),
             stains=chest,
             spray=[('upper', (1.0, 9.0, 7.0), 1.5), ('upper', (2.4, 11.5, 9.8), 1.1),
                    ('upper', (-0.5, 12.5, 12.0), 0.8), ('upper', (3.6, 13.8, 12.5), 0.7)])
    I = dict(lean=50, twist=14, side=7, head_pitch=26, head_roll=10, bob=-5.5,
             foot_r=(-3.6, 0, 1.8), foot_l=(3.6, 0, -0.4), hem_r=(10.8, 8.0), hem=(0, 1.0),
             hand_r=('model', (-6.5, 12.0, 9.0)), hand_l=('model', (6.0, 11.0, 8.0)),
             gun=dict(frame='model', grip=(-10.0, 3.6, 8.0), f=nrm((0.55, -0.35, 0.75))),
             stains=chest, cords=1.0)
    J = dict(root=fall_root(40, 25, 8, 0.0), lean=-12, head_pitch=-20, bob=-2.0, side=-5,
             foot_r=(-3.6, 0, 3.0), foot_l=(3.6, 0, 1.0), hem_r=(10.5, 7.8),
             hand_r=('root', (-14.0, 30.0, 5.0)), hand_l=('root', (13.0, 33.0, 3.0)),
             gun=dict(frame='model', grip=(-14.0, 1.7, 9.0), f=nrm((0.9, 0, 0.35)), up=(0, 0, 1)),
             stains=chest)
    K = dict(root=fall_root(74, 45, 18, 3.5), lean=-8, head_pitch=-15, bob=-2.0, side=-4,
             foot_r=(-3.6, 0, 3.0), foot_l=(3.6, 0, 1.5), hem_r=(11.0, 8.0),
             hand_r=('root', (-15.0, 28.0, 3.0)), hand_l=('root', (14.0, 31.0, 1.0)),
             gun=dict(frame='model', grip=(-17.0, 1.7, 10.0), f=nrm((0.95, 0, 0.3)), up=(0, 0, 1)),
             stains=chest, bend=1.6)
    L = dict(root=fall_root(88, 55, 30, 4.6), lean=-4, head_pitch=-12, bob=-2.0, side=-3,
             foot_r=(-3.8, 0, 2.0), foot_l=(3.8, 0, 3.5), hem_r=(11.5, 8.5),
             hand_r=('root', (-14.0, 26.0, 2.0)), hand_l=('root', (14.0, 29.0, 1.0)),
             gun=dict(frame='model', grip=(-20.0, 1.7, 11.0), f=nrm((0.95, 0, 0.3)), up=(0, 0, 1)),
             stains=chest, bend=3.0, flatten=(np.diag([1, 0.6, 1.0]), V(0, 0, 0), 0.6), crush=0.5,
             extra=[Group([Ellipsoid((3.0, 0.15, -3.0), (17.0, 0.5, 6.0), rot_y(rad(-37)), BLOOD)], name='pool')])
    return [H, I, J, K, L]


# ----------------------------------------------------------------------------- muerte despedazado (M-U)
GRAV = -400.0          # unidades/t² (t va de 0 a 1 a lo largo de los 9 fotogramas): todo aterriza hacia t≈0.75
GIB_T = [0.0, 0.10, 0.22, 0.34, 0.46, 0.58, 0.72, 0.86, 1.0]
GIB_SQUASH = [1.0, 0.95, 0.8, 0.66, 0.52, 0.4, 0.3, 0.22, 0.17]


def _fragments():
    """Trozos que salen despedidos: (tipo, material, tamaño, posición inicial, velocidad, giro)."""
    rng = np.random.default_rng(1936)
    frs = []

    def add(kind, mat, size, y0, n, vx=(10, 30), vy=(30, 70), z0=0.0):
        for _ in range(n):
            ang = rng.uniform(0, 2 * math.pi)
            sp = rng.uniform(*vx)
            p0 = V(rng.uniform(-4, 4), y0 + rng.uniform(-4, 4), z0 + rng.uniform(-2, 2))
            v = V(math.cos(ang) * sp, rng.uniform(*vy), math.sin(ang) * sp * 0.45)
            frs.append((kind, mat, size * rng.uniform(0.75, 1.25), p0, v, rng.uniform(-6, 6)))

    add('rag', RAG, 3.2, 38, 9)
    add('bone', BONE, 3.4, 40, 5)
    add('blob', FLESH, 1.7, 40, 4)
    add('blob', BLOOD, 1.2, 40, 14, vx=(8, 34), vy=(20, 80))
    frs.append(('skull', BONE, 2.7, V(0.5, 48, 0.5), V(-14, 62, 3), 3.0))
    frs.append(('hood', HOOD, 1.0, V(0, 50, 0), V(9, 85, -2), 4.5))
    return frs


def _ballistic(p0, v, t, rest):
    """Posición en el instante t con gravedad; se queda quieta al tocar el suelo (y = rest)."""
    a = 0.5 * GRAV
    b, c = v[1], p0[1] - rest
    tl = (-b - math.sqrt(b * b - 4 * a * c)) / (2 * a)       # instante en que toca el suelo
    tt = min(t, tl)
    p = p0 + v * tt + V(0, a * tt * tt, 0)
    return p, t >= tl


def gib(k):
    t = GIB_T[k]
    if k == 0:
        # M: el impacto revienta el pecho; el cuerpo sigue en pie.
        H = dict(deaths()[0])
        H['spray'] = list(H['spray']) + [
            ('upper', (-3.0, 8.0, 6.5), 1.7), ('upper', (4.5, 6.0, 6.0), 1.5), ('upper', (0.0, 4.0, 7.5), 1.3),
            ('upper', (-5.5, 11.0, 8.5), 1.0), ('upper', (6.0, 12.0, 9.0), 0.9), ('upper', (1.5, 15.0, 10.5), 0.8)]
        return build(H)

    # N-U: queda la falda, que se desploma; el resto sale volando y cae.
    s = GIB_SQUASH[k]
    base = dict(no_torso=True, no_hood=True, no_arms=True, no_gun=True, eyes=False, legs=k < 4,
                lean=0.0, hem_r=(10.0 + 3.0 * (1 - s), 7.4 + 2.0 * (1 - s)), crush=0.6 * (1 - s),
                stains=[('root', (1.0, 30.0 * s, 4.0), 3.5), ('root', (-2.5, 22.0 * s, 4.5), 2.5)],
                flatten=(np.diag([1.0, s, 1.0]), V(0, 0, 0), s))
    parts = []
    for kind, mat, size, p0, v, spin in _fragments():
        rest = {'rag': 0.6, 'bone': 0.8, 'blob': size * 0.5, 'skull': size, 'hood': 2.2}[kind]
        c, landed = _ballistic(p0, v, t, rest)
        Rm = rot_z(spin * min(t, 0.6)) @ rot_x(0.7 * spin * min(t, 0.6))
        if kind == 'rag':
            sq = 0.35 if landed else 0.6
            parts.append(Ellipsoid(c, (size * 1.5, size * sq, size), Rm, mat))
        elif kind == 'bone':
            ax = Rm @ V(1, 0.2, 0)
            if landed:
                ax = nrm(V(ax[0], 0, ax[2]))
            parts += [RoundCone(c - ax * size, c + ax * size, 0.75, 0.6, mat),
                      Sphere(c - ax * size, 0.95, mat), Sphere(c + ax * size, 0.95, mat)]
        elif kind == 'blob':
            if landed and mat == BLOOD:
                parts.append(Ellipsoid(V(c[0], 0.2, c[2]), (size * 2.2, 0.4, size * 1.6), None, mat))
            else:
                parts.append(Sphere(c, size, mat))
        elif kind == 'skull':
            parts += [Sphere(c, size, BONE), Ellipsoid(c + V(0, -1.6, 1.0), (1.6, 1.1, 1.4), None, BONE)]
        elif kind == 'hood':
            ax = rot_z(-2.4 * t) @ V(0, 1, 0)                   # el capirote da vueltas al caer
            if landed:
                ax = nrm(V(1.0, 0.12, -0.3))
            parts.append(CappedCone(c - ax * 3.0, c + ax * 14.0, 3.9, 0.35, HOOD))
    groups, extras = build(base)
    groups.append(Group(parts, k=0.3, name='extra'))
    # El trabuco cae girando hasta quedar tendido a un lado.
    g0, g1 = V(-6.0, 36.0, 6.0), V(-17.0, 1.7, 8.0)
    u = min(1.0, t / 0.6)
    gp = g0 + (g1 - g0) * u + V(0, 12.0 * math.sin(math.pi * u) * (1 - u), 0)
    gf = nrm((math.sin(rad(90 * u)) * 0.95, -0.2 * (1 - u), math.cos(rad(90 * u)) * 0.3 + 0.05))
    gparts, _ = gun_parts(Frame(gp, basis(gf, (0, 1, 0) if u < 1 else (0, 0, 1))))
    groups.append(Group(gparts, k=0.25, name='gun'))
    if k >= 4:
        rr = 6.0 + 14.0 * (k - 4) / 4
        groups.append(Group([Ellipsoid((1.0, 0.15, -1.0), (rr, 0.5, rr * 0.42), None, BLOOD)], name='pool'))
    return groups, extras


# ----------------------------------------------------------------------------- salida
def lumps():
    """{lump: (pose, ángulo)}; los fotogramas sin ángulo (0) se ven siempre de frente."""
    out = {}
    for fi, fr in enumerate('ABCD'):
        for a in range(1, 9):
            out[f'POSS{fr}{a}'] = (walk(fi), a)
    for fr, pose in (('E', AIM), ('F', FIRE), ('G', PAIN)):
        for a in range(1, 9):
            out[f'POSS{fr}{a}'] = (pose, a)
    for fr, pose in zip('HIJKL', deaths()):
        out[f'POSS{fr}0'] = (pose, 1)
    for k, fr in enumerate('MNOPQRSTU'):
        out[f'POSS{fr}0'] = (('gib', k), 1)
    return out


def draw(R, pose, angle):
    if isinstance(pose, tuple) and pose[0] == 'gib':
        groups, extras = gib(pose[1])
    else:
        groups, extras = build(pose)
    out, depth = R.render(groups, extras, angle)
    return trim(finish(out, depth, R.palarr))


def contact_sheet(images, path, scale=3):
    rows = [[f'POSS{f}{a}' for a in range(1, 9)] for f in 'ABCDEFG']
    rows += [[f'POSS{f}0' for f in 'HIJKL'], [f'POSS{f}0' for f in 'MNOPQRSTU']]
    rows = [[n for n in r if n in images] for r in rows]
    rows = [r for r in rows if r]
    cw = max(im.width for im in images.values()) * scale + 10
    chh = max(im.height for im in images.values()) * scale + 22
    ncol = max(len(r) for r in rows)
    sheet = Image.new('RGB', (cw * ncol, chh * len(rows)), (92, 92, 100))
    dr = ImageDraw.Draw(sheet)
    for r, row in enumerate(rows):
        for c, n in enumerate(row):
            im = images[n]
            big = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
            x = c * cw + cw // 2 - big.width // 2
            y = r * chh + chh - 6 - big.height
            sheet.paste(big, (x, y), big)
            dr.text((c * cw + 4, r * chh + 3), f'{n} {im.width}x{im.height}', fill=(235, 235, 235))
            dr.line([(c * cw + cw // 2, r * chh + chh - 6), (c * cw + cw // 2, r * chh + chh - 2)], fill=(255, 60, 60))
    sheet.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--salida', required=True, help='carpeta de PNG (arte/sprites)')
    ap.add_argument('--solo', default='', help='lumps separados por comas')
    ap.add_argument('--hoja', default='', help='ruta de la hoja de contactos (PNG)')
    args = ap.parse_args()
    os.makedirs(args.salida, exist_ok=True)
    R = Render()
    todos = lumps()
    names = [n.strip().upper() for n in args.solo.split(',') if n.strip()] or list(todos)
    images = {}
    for n in names:
        pose, ang = todos[n]
        im = draw(R, pose, ang)
        im.save(os.path.join(args.salida, n + '.png'))
        images[n] = im
        print(f'{n} {im.width}x{im.height}', flush=True)
    if args.hoja:
        contact_sheet(images, args.hoja)


if __name__ == '__main__':
    main()
