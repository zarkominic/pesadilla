#!/usr/bin/env python3
"""sdf.py — motor común para dibujar POR CÓDIGO los sprites de criaturas de PESADILLA.

Modelos 3D hechos con primitivas SDF (esferas, elipsoides, conos, cápsulas, cajas, anillos) y
agrupados con unión suave; se trazan con numpy (raymarching ortográfico, cámara 10° desde arriba)
a 4 submuestras por píxel, se sombrean con rampas EXACTAS de PLAYPAL (pocas tonalidades por
material), se reducen dando prioridad a lo cercano y a lo que brilla, y se les pone un contorno
oscuro de 1 px. Lo usan penitente.py y el resto de criaturas: misma luz, paleta y contorno.

Convenciones del modelo: y arriba, z hacia delante (hacia la cámara en el ángulo 1), x a la
IZQUIERDA del personaje; 1 unidad ≈ 1 píxel; suelo en y = 0. Ángulos de Doom: 1 de frente,
3 mira a la izquierda de la pantalla, 5 de espaldas, 7 a la derecha (0 = siempre de frente).

Para un sprite nuevo: define materiales (ids enteros + rampas), construye Groups de primitivas
para cada pose, y llama a Render(...).render(groups, extras, angle) → finish → trim.
cli(...) da la línea de órdenes estándar (--salida, --solo, --hoja).
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
    """Trazador ortográfico de modelos SDF a sprites de Doom.

    ramps: {material: [índices de PLAYPAL de oscuro a claro]}
    hook(P, mat, inten, nz, nr, spec, lvl_extra, extras): ajustes por material de cada criatura
        (modifica mat/inten/lvl_extra en su sitio; los brillos con apply_shine).
    flash_mats: materiales que se colorean por distancia a extras['flash_core'] (fogonazos).
    level_mats: materiales cuyo tono sale de lvl_extra (p. ej. ojos que brillan).
    emissive: materiales con prioridad al reducir (no desaparecen aunque sean pequeños).
    no_light: materiales que no ilumina extras['flash_light'].
    """

    def __init__(self, ramps, hook=None, flash_mats=(), level_mats=(), emissive=(), no_light=(),
                 tilt=TILT):
        self.ramps, self.hook = ramps, hook
        self.flash_mats, self.level_mats = tuple(flash_mats), tuple(level_mats)
        self.emissive, self.no_light, self.tilt = tuple(emissive), tuple(no_light), tilt
        self.pal = read_palette(IWAD)
        self.palarr = np.array(self.pal, float)
        self.mapper = PaletteMapper(self.pal)

    def nearest(self, rgb):
        return self.mapper.index(tuple(int(round(c)) for c in np.clip(rgb, 0, 255)))

    def render(self, groups, extras, angle):
        th = (angle - 1) * math.pi / 4 if angle else 0.0
        R = rot_y(-th)                         # modelo → cámara
        Xc = V(1, 0, 0)
        Uc = V(0, math.cos(self.tilt), -math.sin(self.tilt))
        Dc = V(0, -math.sin(self.tilt), -math.cos(self.tilt))
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

        # Ajustes propios de cada criatura (pliegues, ojos, bocas de cañón, manchas, brillos…).
        if self.hook is not None:
            self.hook(P, mat, inten, nz, nr, spec, lvl_extra, extras)
        # Índice de paleta por submuestra.
        idxs = np.zeros(len(P), int)
        for mm, ramp in self.ramps.items():
            m = mat == mm
            if not m.any():
                continue
            n = len(ramp)
            if mm in self.flash_mats:
                fc, frad = extras['flash_core']
                lv = np.clip((1 - _len(P[m] - fc) / frad) * n * 1.15, 0, n - 1)
            elif mm in self.level_mats:
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
            m = (amt > 0.08) & ~np.isin(mat, self.no_light)
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
            for em in self.emissive:
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


def finish(out, depth, palarr, outline=2):
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
                    res[y, x] = outline
                break
    # Contorno exterior (4 vecinos), sin salir por debajo del lienzo.
    pad = np.pad(op, 1)
    ring = (pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:]) & ~op
    res[ring] = outline
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


# ----------------------------------------------------------------------------- cinemática
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



def apply_shine(mat, inten, spec, table):
    """Brillo especular por material: table = ((material, fuerza, exponente), ...)."""
    for mm, sp, pw in table:
        m = mat == mm
        inten[m] += sp * spec[m] ** pw


def contact_sheet(images, path, rows, scale=3):
    """Hoja de contactos ampliada con etiquetas: rows = [[lump, ...], ...] (los que falten se omiten)."""
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


def sprite_rows(prefix, rotated, still):
    """Filas de hoja de contactos: fotogramas con 8 ángulos y fotogramas de frente (ángulo 0)."""
    rows = [[f'{prefix}{f}{a}' for a in range(1, 9)] for f in rotated]
    if still:
        rows.append([f'{prefix}{f}0' for f in still])
    return rows


def cli(lumps, draw, rows):
    """Línea de órdenes estándar: lumps() → {lump: (pose, ángulo)}; draw(pose, ángulo) → Image."""
    ap = argparse.ArgumentParser()
    ap.add_argument('--salida', required=True, help='carpeta de PNG (arte/sprites)')
    ap.add_argument('--solo', default='', help='lumps separados por comas')
    ap.add_argument('--hoja', default='', help='ruta de la hoja de contactos (PNG)')
    args = ap.parse_args()
    os.makedirs(args.salida, exist_ok=True)
    todos = lumps()
    names = [n.strip().upper() for n in args.solo.split(',') if n.strip()] or list(todos)
    images = {}
    for n in names:
        pose, ang = todos[n]
        im = draw(pose, ang)
        im.save(os.path.join(args.salida, n + '.png'))
        images[n] = im
        print(f'{n} {im.width}x{im.height}', flush=True)
    if args.hoja and images:
        contact_sheet(images, args.hoja, rows)
