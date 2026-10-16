#!/usr/bin/env python3
"""coco.py — dibuja POR CÓDIGO al COCO (sustituye al cacodemonio HEAD de Freedoom) y su escupitajo de
fuego (BAL2).

El coco de las nanas: una cabeza enorme y deforme que flota, sin cuerpo. Piel parda-cetrina con manchas
oliváceas, venas y verrugas; cráneo bajo con bultos desiguales (también en la nuca), frente corta y cejas
pesadas sobre unos ojos pequeños y hundidos que brillan, nariz de patata colorada, orejas desiguales (una
grande y caída, otra pequeña y arrugada), un mechón de pelo negro y, sobre todo, una BOCA gigantesca a media
cabeza, de comisura a comisura, con dientes irregulares (torcidos, rotos, alguno que falta y dos colmillos),
y debajo una papada que cuelga como un saco. Al atacar abre la boca y escupe una bola de fuego fatuo
rojo-anaranjado.

Mismo motor y estilo que el resto de criaturas (tools/arte/sdf.py): modelo 3D de primitivas SDF con
poses paramétricas, trazado ortográfico a 4 submuestras, rampas EXACTAS de PLAYPAL, reducción por
mayoría con prioridad a lo cercano y a lo que brilla, y contorno oscuro de 1 px.
- La boca, las cuencas y la abolladura de la muerte se TALLAN en la cabeza (recorte SDF); el interior de
  la boca se oscurece hacia el fondo para que se lea como un agujero.
- Los dientes se plantan sobre la línea de los labios, que se busca en la superficie de la cara.
- Manchas y arrugas se calculan en el marco de la cabeza: no «nadan» al moverse.

Fotogramas (info.c, SPR_HEAD): A flotar; B-C abre la boca; D escupe (a pleno brillo: fuego en la boca);
E-F dolor: los 8 ángulos, cada uno en su PNG. G-L muerte (se desinfla, cae y queda un amasijo): de frente.
BAL2 A-B en vuelo (a pleno brillo) y C-E explosión, de frente, dibujados en 2D.

Apoyo: el Coco vuela, así que su origen (la z del objeto) no es el suelo. Los offsets se escriben
explícitos en arte/sprites/offsets_anima_coco.json (eje de la cabeza centrado; origen siempre a la misma
altura respecto a la cabeza). La cabeza va de ~z+10 a ~z+64 (caja de 56 de alto). El juego lanza la bola a
z+32 y su centro queda a z+36,5: por eso la boca está a media cabeza (labio de arriba a ~z+39, fuego del
fotograma D de z+21 a z+41) y los ojos van por encima (~z+46..50): la bola brota de la boca y nunca tapa un
ojo. Al morir baja poco a poco (G-J) y el amasijo (K-L) se apoya en el suelo (fila de abajo 1 px bajo el
origen).
Los dos scripts (anima.py y coco.py) escriben el mismo JSON con cerrojo (fcntl), cada uno sus claves.

Uso (determinista, regenera los 54 PNG HEAD* y los 5 BAL2*):
    ~/.venvs/pesadilla/bin/python tools/arte/coco.py --salida arte/sprites
    … --solo HEADA1,BAL2A0      solo esos lumps
    … --hoja hoja.png           además, hoja de contactos ampliada x3 con etiquetas
"""
import fcntl
import json
import math
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdf  # noqa: E402
from sdf import (V, nrm, rot_x, rot_y, rot_z, rad, basis, Frame, _len, Prim,  # noqa: E402
                 Sphere, Ellipsoid, RoundCone, Group, vnoise, SS,
                 Render, finish, trim, apply_shine, cli, sprite_rows)

# ----------------------------------------------------------------------------- materiales
(SKIN, SPOT, WART, LIP, MOUTH, TONGUE, TEETH, EYE, SOCKET, HAIR, EAR_IN, BLOOD, FIRE, TEETHL,
 MOUTHL, SKINL, DEADEYE, GORE, NOSE) = range(19)
RAMPS = {
    SKIN: [1, 151, 150, 149, 148, 147, 146, 145, 144],   # pardo-cetrino
    SPOT: [1, 12, 159, 158, 157, 156, 155, 154],          # cetrino: ojeras y papada oliváceas
    WART: [1, 2, 79, 78, 77, 76, 75, 74],                 # lunares y verrugas pardo oscuro
    LIP: [0, 2, 239, 238, 237, 15, 14, 13],               # labios gruesos, oscuros
    MOUTH: [0, 47, 46, 44, 42, 40, 38],                   # boca: negro rojizo
    TONGUE: [0, 46, 42, 38, 35, 32, 29, 26],              # lengua
    TEETH: [2, 150, 148, 146, 144, 130, 129, 128],       # dientes sucios: raíz parda, punta marfil
    EYE: [164, 161, 160, 225],                            # brillo (borde, iris, núcleo)
    SOCKET: [0, 1],
    DEADEYE: [0, 1, 79],
    HAIR: [0, 7, 6, 5, 110, 108, 106],                    # pelo negro
    EAR_IN: [0, 2, 79, 77, 75, 73],                       # dentro de la oreja
    BLOOD: [191, 189, 187, 185, 182, 179],
    GORE: [47, 45, 42, 39, 36, 33],
    FIRE: [186, 182, 178, 176, 216, 215, 214, 212, 211, 210],   # fuego fatuo rojo-anaranjado
    TEETHL: [2, 232, 221, 218, 215, 213, 211],            # dientes a la luz del fuego
    MOUTHL: [0, 47, 189, 186, 183, 232, 221],             # boca a la luz del fuego
    SKINL: [1, 151, 233, 232, 221, 218, 215],             # piel a la luz del fuego
    NOSE: [1, 239, 77, 75, 73, 71, 69, 67],               # nariz de patata, colorada de vino
}
EMISSIVE = (EYE, FIRE)
OUTLINE = 2      # (23,15,7): casi negro cálido
SKINS = (SKIN, SPOT, WART, NOSE)
NOSE_C = V(1.8, -3.6, 24.6)             # centro de la nariz (marco de la cabeza)

# ----------------------------------------------------------------------------- apoyo (vuela)
Y0S = 8                                  # el origen (z del objeto) queda 8 px por encima del borde del lienzo
Y0 = Y0S / math.cos(sdf.TILT)            # … en unidades del modelo (eje de la cabeza)
HC_Y = 50.0                              # centro de la cabeza sobre el origen. El juego lanza la bola (BAL2)
                                         # a z+32 (su centro queda a z+36,5): la boca va a z+39 y los ojos a
                                         # ~z+49, así la bola brota de la boca y nunca tapa un ojo
TOP_Y = 9.0                              # coronilla (marco de la cabeza): el cráneo es bajo (tope ~z+63)
FIRE_UP = 9.0                            # altura de las lenguas de fuego que salen de la boca (fotograma D)
SCALE = 1.04                             # el modelo se piensa a 1 unidad = 1 px y se agranda al dibujar
OFFSETS = {}


class Bent(Prim):
    """Elipsoide doblado (comisuras hacia arriba): q.y -= bend·(q.x/rx)²; marco F."""

    def __init__(self, F, radii, bend, mat=MOUTH):
        self.F, self.rr, self.bend, self.mat = F, V(radii), bend, mat
        self.bc, self.br = F.o, float(max(radii)) + abs(bend)

    def sdf(self, P):
        q = self.F.to_local(P)
        q[:, 1] -= self.bend * (q[:, 0] / self.rr[0]) ** 2
        k0 = _len(q / self.rr)
        k1 = _len(q / (self.rr * self.rr))
        return k0 * (k0 - 1) / np.maximum(k1, 1e-9) * 0.8


class FastGroup(Group):
    """Como sdf.Group (unión suave de primitivas), pero más rápido con muchas primitivas: las cotas de todas
    se calculan de una vez y cada primitiva solo se mezcla donde puede cambiar el resultado
    (d < mejor + k; más lejos, la unión suave no varía)."""

    def __init__(self, prims, cut_bound=None, **kw):
        super().__init__(prims, **kw)
        self.cut_bound = cut_bound          # (centro, radio): fuera de esa esfera el recorte no talla nada
        self._c = np.array([p.bc for p in prims])
        self._r = np.array([p.br for p in prims])
        self._c2 = (self._c ** 2).sum(1)

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
        near = np.nonzero(gb < sdf.CULL)[0]
        if len(near):
            Qn = Q[near]
            D2 = (Qn ** 2).sum(1)[:, None] + self._c2[None, :] - 2 * Qn @ self._c.T
            BD = np.sqrt(np.maximum(D2, 0)) - self._r[None, :]
            m = len(near)
            best = np.full(m, 1e9)
            raw = np.full(m, 1e9)
            mn = np.full(m, self.prims[0].mat, int)
            kk = self.k
            for j, pr in enumerate(self.prims):
                bd = BD[:, j]
                sel = np.nonzero(bd < best + max(kk, 1e-6))[0]
                if not len(sel):
                    continue
                dp = bd[sel].copy()
                ins = dp < sdf.CULL
                if ins.any():
                    dp[ins] = pr(Qn[sel[ins]])
                b = best[sel]
                if kk > 0:
                    h = np.clip(0.5 + 0.5 * (b - dp) / kk, 0, 1)
                    best[sel] = b * (1 - h) + dp * h - kk * h * (1 - h)
                else:
                    best[sel] = np.minimum(b, dp)
                r0 = raw[sel]
                closer = dp < r0
                mn[sel[closer]] = pr.mat
                raw[sel] = np.minimum(r0, dp)
            if self.cut is not None:
                if self.cut_bound is None:
                    best = np.maximum(best, self.cut(Qn))
                else:
                    cc, cr = self.cut_bound
                    i = np.nonzero(_len(Qn - cc) < cr)[0]
                    if len(i):
                        best[i] = np.maximum(best[i], self.cut(Qn[i]))
            d[near] = best
            mat[near] = mn
        return d * ds, mat


class Wrinkled(FastGroup):
    """Grupo con pliegues de pellejo vacío: surcos casi horizontales, ondulados por ruido (marco local F)."""

    def __init__(self, prims, amp, F, period=5.5, seed=0, **kw):
        super().__init__(prims, **kw)
        self.amp, self.F, self.period, self.seed = amp, F, period, seed
        self.br += amp

    def eval(self, P):
        d, m = super().eval(P)
        near = np.nonzero(d < 3.0)[0]
        if self.amp > 0 and len(near):
            Q = P[near]
            if self.xf is not None:
                A, t, _ = self.xf
                Q = (Q - t) @ np.linalg.inv(A).T
            q = self.F.to_local(Q)
            ph = q[:, 1] + 0.18 * q[:, 0] + 5.0 * (vnoise(q, 0.09, self.seed) - 0.5) + 2.0 * (vnoise(q, 0.21, self.seed + 1) - 0.5)
            fold = np.abs(np.sin(ph * math.pi / self.period))          # surcos en |sin| = 0
            d[near] = d[near] + self.amp * (0.6 - fold) * (0.6 + 0.8 * vnoise(q, 0.15, self.seed + 2))
        return d, m


def materiales(P, mat, inten, nz, nr, spec, lvl_extra, extras):
    """Tez cetrina, lunares, arrugas, surcos, labios, boca honda, ojos, orejas, sangre y luz del fuego."""
    Q = extras['pre'](P)                           # puntos en el modelo sin escalar
    loc = extras['H'].to_local(Q)                  # … y en el marco de la cabeza (no «nadan»)
    sk = np.isin(mat, SKINS)
    # Tez cetrina: ojeras, papada y sien oliváceas (zonas concretas, borde roto por ruido).
    sal = np.zeros(len(P))
    for c, r in SALLOW:
        sal = np.maximum(sal, 1 - _len((loc - c) / r))
    m = sk & (sal + 0.35 * (vnoise(loc, 0.35, 41) - 0.5) > 0.12)
    mat[m] = SPOT
    # Lunares pardos: pequeños, más en el cráneo.
    sp = vnoise(loc, 0.3, 43) * 0.8 + vnoise(loc, 0.9, 44) * 0.2
    m = sk & (sp > 0.79 - 0.04 * (loc[:, 1] > 3))
    mat[m] = WART
    # Nariz colorada (de vino) con el borde roto por ruido.
    m = sk & (mat != WART) & (_len(loc - NOSE_C) + 1.2 * (vnoise(loc, 0.6, 46) - 0.5) < 5.6)
    mat[m] = NOSE
    # Arrugas de la frente (sobre las cejas).
    fr = sk & (loc[:, 1] > 5.5) & (loc[:, 1] < 12) & (loc[:, 2] > 8)
    inten[fr] *= 0.78 + 0.32 * (np.sin(loc[fr, 1] * 1.35 + 2.0 * vnoise(loc[fr], 0.3, 44)) > 0.2)
    inten[sk] *= 0.9 + 0.2 * vnoise(loc[sk], 0.9, 45)
    apply_shine(mat, inten, spec, ((SKIN, 0.32, 5), (SPOT, 0.2, 5), (NOSE, 0.45, 6), (TEETH, 0.5, 6), (LIP, 0.5, 6),
                                   (HAIR, 0.55, 5), (TONGUE, 0.6, 7), (BLOOD, 0.6, 12), (EAR_IN, 0.2, 5)))
    # Surcos (nariz-comisuras, entrecejo): oscuros; orificios de la nariz: negros.
    cf = extras.get('crease_fn')
    if cf is not None:
        dc = cf(Q)
        m = np.isin(mat, SKINS) & (dc < 0.5)
        inten[m] *= 0.45
        for c in extras.get('nostrils', []):
            m = np.isin(mat, SKINS) & (_len(Q - c) < 1.6)
            mat[m] = SOCKET
    # Boca: la pared tallada es MOUTH, más oscura hacia el fondo; alrededor, el labio.
    mf = extras.get('mouth_fn')
    if mf is not None:
        dm = mf(Q)
        wall = np.isin(mat, SKINS + (LIP,)) & (dm > -0.6) & (dm < 0.15)
        if cf is not None:
            wall &= dc > 0.6
        mat[wall] = MOUTH
        zf, zb = extras['mouth_depth']
        lip = np.isin(mat, SKINS) & (dm >= 0.15) & (dm < extras.get('lip_w', 2.2)) & (loc[:, 2] > zf - 6.0)
        mat[lip] = LIP
        m = np.isin(mat, (MOUTH, TONGUE))
        depth = np.clip((loc[:, 2] - zb) / (zf - zb), 0, 1)
        inten[m] = inten[m] * (0.25 + 0.75 * depth[m] ** 1.5)
    # Cuencas: la pared tallada es oscura; el ojo brilla al fondo.
    for c, rs in extras.get('sockets', []):
        ds = _len(Q - c)
        m = np.isin(mat, SKINS + (LIP,)) & (ds < rs + 0.5)
        mat[m] = SOCKET
        inten[m] = 0.1
    for c, r, kind in extras.get('eyes', []):
        de = _len(Q - c)
        m = (mat == EYE) & (de < r + 0.6)
        if kind == 'dead':
            mat[m] = DEADEYE
        else:
            lo, hi = {'on': (1, 2), 'hot': (2, 3), 'dim': (0, 1)}[kind]
            lvl_extra[m] = np.where(de[m] < r * 0.55 + 0.25, hi, lo)
    # Orejas: el hueco interior.
    for c, ax, r in extras.get('ear_holes', []):
        q = Q - c
        m = sk & (_len(q) < r) & ((q @ ax) > -0.3)
        mat[m] = EAR_IN
    # Sangre: manchas y regueros.
    for sc, sr in extras.get('stains', []):
        ds = _len(Q - sc)
        m = np.isin(mat, SKINS + (LIP, TEETH)) & (ds < sr * (0.7 + 0.6 * nz))
        mat[m] = BLOOD
    # Fuego en la boca: núcleo caliente visto desde la cámara; tiñe dientes, boca y piel cercanas.
    fc = extras.get('fire_core')
    m = mat == FIRE
    if fc is not None and m.any():
        c, size = fc
        Dv = extras['view']
        rel = Q[m] - c
        along = rel @ Dv
        perp = _len(rel - np.outer(along, Dv))
        heat = 1.15 - perp / (size * 1.25) + 0.35 * (nz[m] - 0.5)
        for b0, b1 in extras.get('fire_tongues', []):            # lenguas: calientes en la base, rojas en la punta
            ab = b1 - b0
            tt = np.clip(((Q[m] - b0) @ ab) / (ab @ ab), 0, 1)
            near = _len(Q[m] - (b0 + np.outer(tt, ab))) < 2.8
            heat = np.where(near, np.maximum(heat, 0.95 - 0.75 * tt + 0.25 * (nz[m] - 0.5)), heat)
        nf = len(RAMPS[FIRE])
        lvl_extra[m] = np.clip(np.floor(heat * nf), 0, nf - 1)
    fl = extras.get('fire_light')
    if fl is not None:
        lp, lr = fl
        rel = lp - Q
        dl = np.maximum(_len(rel), 1e-6)
        ndl = np.clip(np.einsum('ij,ij->i', nr, rel / dl[:, None]), 0, 1)
        amt = np.clip(1 - dl / lr, 0, 1) * (0.3 + 0.7 * ndl)
        for src, dst, th in ((TEETH, TEETHL, 0.2), (MOUTH, MOUTHL, 0.12), (TONGUE, MOUTHL, 0.12),
                             (LIP, SKINL, 0.35), (SKIN, SKINL, 0.45), (SPOT, SKINL, 0.45)):
            mm = (mat == src) & (amt > th)
            mat[mm] = dst
            inten[mm] = np.maximum(inten[mm], 0.25) + amt[mm] * 0.9


RENDERS = {}


def render(tilt=sdf.TILT):
    """Trazador (uno por inclinación de cámara: el amasijo del suelo se ve algo más desde arriba)."""
    key = round(tilt, 5)
    if key not in RENDERS:
        RENDERS[key] = Render(RAMPS, hook=materiales, level_mats=(EYE, FIRE), emissive=EMISSIVE,
                              no_light=(EYE, SOCKET, FIRE, DEADEYE), tilt=tilt)
    return RENDERS[key]


# ----------------------------------------------------------------------------- modelo
# Proporciones: cráneo bajo y abollado con frente corta; ojos pequeños bajo el ceño; nariz de patata; una
# boca enorme a media cabeza y, debajo, quijada, barbilla y una papada que cuelga como un saco.
HINGE = (0.0, -3.0, -8.0)            # bisagra de la mandíbula (marco de la cabeza), bien atrás: abre mucho
UL = (0.0, -8.6, 0.0)                # altura de la línea del labio de arriba (x, y; z se busca)
MOUTH_RX = 21.0                      # media anchura de la boca
BEND = 5.2                           # comisuras hacia arriba
EYE_L = (7.6, 0.9, 3.7, 1.6)        # ojo izquierdo (x+): x, y, radio de la cuenca, radio del ojo
EYE_R = (-7.0, -0.5, 3.2, 1.4)      # ojo derecho: más bajo y más pequeño
JZ = -HINGE[2] - 5.0                 # la mandíbula se pensó con la bisagra en z=-5: corrección de z

# Dientes de arriba y de abajo: (x en la boca de -1 a 1, largo, ancho, inclinación). Irregulares: torcidos,
# alguno roto, dos huecos y dos colmillos.
_rng = np.random.default_rng(1957)
TEETH_UP = []
for k, u in enumerate(np.linspace(-0.88, 0.88, 11)):
    if k in (3, 8):                                   # huecos: dientes que faltan
        continue
    ln = _rng.uniform(1.8, 3.6)
    w = _rng.uniform(1.25, 1.75)
    if k in (2, 9):                                   # colmillos torcidos
        ln, w = (5.6, 1.7) if k == 2 else (4.8, 1.6)
    if k == 6:                                        # roto
        ln = 1.2
    TEETH_UP.append((u + _rng.uniform(-0.03, 0.03), ln, w, _rng.uniform(-18, 18)))
TEETH_LO = []
for k, u in enumerate(np.linspace(-0.8, 0.8, 9)):
    if k == 5:
        continue
    ln = _rng.uniform(1.6, 3.0)
    w = _rng.uniform(1.2, 1.6)
    if k == 1:
        ln = 4.2
    TEETH_LO.append((u + _rng.uniform(-0.04, 0.04), ln, w, _rng.uniform(-20, 20)))

DEFAULT = dict(
    bob=0.0, pitch=0.0, yaw=0.0, roll=0.0, hc=HC_Y,
    jaw=10.0, drop=0.5, twist=3.0,  # mandíbula: grados de apertura, descuelgue y torsión (boca torcida)
    eyes='on', squint=0.0, puff=0.0,
    fire=None, deflate=0.0, sag=0.0, wrinkle=0.0, dent=0.0,
    stains=(), spray=(), squash=1.0, floor=False, pool=0.0, tongue_out=0.0, tilt=10.0,
)


SALLOW = [(V(7.5, -2.6, 17.0), V(6.0, 3.6, 5.0)), (V(-7.0, -4.0, 17.0), V(5.5, 3.6, 5.0)),   # ojeras
          (V(16.5, -21.0, 6.0), V(8.0, 9.0, 9.0)), (V(-16.0, -22.0, 6.0), V(8.0, 9.0, 9.0)),  # papada
          (V(-17.0, 0.0, -6.0), V(5.0, 5.0, 5.0)), (V(4.0, -8.0, -21.0), V(7.0, 6.0, 5.0))]   # sien, nuca


def head_parts(H, puff=0.0, deflate=0.0):
    """Cráneo, frente, cejas, mejillas, nariz y papada: todo en el marco H (cabeza). Los 6 primeros son el
    cráneo (sobre él se peina el mechón)."""
    p = H.p
    M = H.M()
    dz = 1 - 0.55 * deflate                     # al desinflarse, el cráneo se hunde

    def sh(r, k=0.3):
        return r * (1 - k * deflate)
    Mc = H.M(rot_z(rad(-7)))                    # cráneo ladeado: más alto por la izquierda
    sk = [
        Ellipsoid(p((1, -6.0 * dz, -4)), (23, 12.0 * dz, 20.5), Mc, SKIN),        # cráneo: bajo y ancho
        Sphere(p((14, -5.5 * dz, -9)), sh(10.0), SKIN),                           # bulto izquierdo
        Sphere(p((-15, -7 * dz, -8)), sh(9.5), SKIN),                             # bulto derecho
        Sphere(p((-5, -0.5 * dz, -4)), sh(5.5, 0.4), SKIN),                       # chichón de la coronilla
        Sphere(p((-9, 4.8 * dz, 11)), sh(4.4, 0.4), SKIN),                        # chichón de la frente
        Ellipsoid(p((1, 3.6 * dz, 9.5)), (15, 5.4 * dz, 9.5), M, SKIN),          # frente corta y abombada
        Ellipsoid(p((8.2, 4.0, 18.6)), (6.8, 3.0, 4.6), M @ rot_z(rad(17)), SKIN),    # ceja izquierda (ceño)
        Ellipsoid(p((-7.4, 2.5, 18.6)), (6.4, 2.9, 4.4), M @ rot_z(rad(-15)), SKIN),  # ceja derecha
        Ellipsoid(p((12, -3.6, 14)), (5.5, 3.8, 5.0), M, SKIN),                   # pómulo izquierdo
        Ellipsoid(p((-11.5, -4.6, 14)), (5.5, 3.8, 5.0), M, SKIN),                # pómulo derecho
        Ellipsoid(p((13, -9, 10)), (8 + puff, 8 + puff, 8 + puff), M, SKIN),      # mejilla izquierda
        Ellipsoid(p((-13, -10, 10)), (8 + puff, 8 + puff, 8 + puff), M, SKIN),    # mejilla derecha
        Ellipsoid(p((0, -5.8, 13.5)), (16, 5.6, 9), M, SKIN),                      # morro sobre la boca
        RoundCone(p((0.4, 3.2, 19.8)), p((1.3, -2.0, 23.6)), 2.3, 3.4, SKIN),     # caballete de la nariz
        Sphere(p(NOSE_C), 5.0, SKIN),                                              # nariz de patata
        Sphere(p((5.6, -5.0, 22.0)), 2.7, SKIN), Sphere(p((-2.2, -5.3, 22.2)), 2.5, SKIN),   # aletas
        Ellipsoid(p((16.5, -20 - 3 * deflate, 8)), (7.5, 11.0, 7.5), M, SKIN),   # papada izquierda (cuelga)
        Ellipsoid(p((-16.0, -21 - 3 * deflate, 8)), (7.5, 11.0, 7.5), M, SKIN),  # papada derecha
        Ellipsoid(p((0, -13 * dz, -11)), (18, 14.5 * dz, 12.5), M, SKIN),         # nuca: cierra la cabeza por detrás
        Sphere(p((8, -5 * dz, -21)), sh(7.0), SKIN),                              # bultos de la nuca
        Sphere(p((-8, -13 * dz, -18.5)), sh(6.5), SKIN),
        Sphere(p((-3, 1.5 * dz, -19)), sh(5.5), SKIN),
        Sphere(p((15, -15 * dz, -13)), sh(5.0), SKIN),
    ]
    return sk


def warts_on(face, H):
    """Lunares y verrugas: se plantan sobre la superficie (rayo desde fuera hacia el eje de la cabeza)."""
    out = []
    for q, r in (((5.9, -1.8, 24.0), 1.2), ((-13.0, -5.5, 17.0), 1.4), ((10.5, 6.5, 13.0), 1.2),
                 ((-18.5, 2.0, 5.0), 1.5), ((15.5, -1.0, 13.5), 1.0), ((-10.0, -2.0, -18.0), 1.4),
                 ((12.0, -10.0, -14.0), 1.2), ((3.0, 6.0, -12.0), 1.3)):
        q = V(q)
        dv = nrm(H.d(q * (1, 0.35, 1)))
        a = H.p((0, q[1], 0)) + dv * 45.0
        s = surf(face, a, -dv, hi=60)
        out.append(Sphere(s - dv * 0.3 * r, r, WART))
    return out


def veins(proj):
    """Venas hinchadas sobre el cráneo (frente, sien y nuca), como polilíneas (rumbo, elevación) sobre él."""
    out = []
    for pts, r0 in ((((28, 52), (36, 38), (30, 26), (40, 18)), 0.95),          # frente (izquierda)
                    (((292, 56), (300, 40), (288, 24), (296, 8)), 0.9),        # sien derecha
                    (((150, 64), (160, 44), (150, 26), (166, 6), (158, -14)), 1.05),   # nuca
                    (((160, 44), (186, 30), (196, 8)), 0.85),
                    (((205, 62), (214, 40), (228, 22), (222, 2)), 0.95),
                    (((120, 40), (112, 22), (124, 4)), 0.8)):
        P = [proj(y, e, 0.15) for y, e in pts]
        n = len(P) - 1
        for i in range(n):
            ra = r0 * (1 - 0.35 * i / n)
            rb = r0 * (1 - 0.35 * (i + 1) / n)
            out.append(RoundCone(P[i], P[i + 1], ra, rb, SPOT))
    return out


def creases(H):
    """Surcos tallados: de la nariz a las comisuras, entrecejo y orificios de la nariz."""
    p = H.p
    return [RoundCone(p((7.0, -2.4, 22.6)), p((16.5, -5.0, 17.5)), 0.95, 0.6, SKIN),
            RoundCone(p((-5.6, -2.9, 22.6)), p((-16.0, -5.5, 17.5)), 0.95, 0.6, SKIN),
            RoundCone(p((0.3, 6.0, 20.5)), p((0.6, 2.6, 21.0)), 0.7, 0.5, SKIN),
            Sphere(p((3.4, -6.8, 28.0)), 1.25, SKIN), Sphere(p((-0.2, -6.9, 27.8)), 1.15, SKIN)]


def jaw_parts(J, deflate=0.0):
    """Mandíbula (marco J, con la bisagra en el origen): quijada ancha, barbilla salida y una papada que cuelga
    como un saco. Los 3 primeros forman la cara (para buscar los labios)."""
    p = J.p
    M = J.M()
    s = 1 - 0.25 * deflate
    return [
        Ellipsoid(p((0, -12.5, 10 + JZ)), (20, 10.0, 14.5), M, SKIN),               # quijada
        Ellipsoid(p((1, -16.0, 19.5 + JZ)), (12.5, 7.5, 7.5), M, SKIN),             # barbilla
        Ellipsoid(p((0, -7.5, 18.5 + JZ)), (16.8, 4.2, 6.0), M, SKIN),              # labio de abajo
        Ellipsoid(p((0, -24.0 + 3 * deflate, 12.0 + JZ)), (14.5 * s, 7.0 * s, 9.5 * s), M, SKIN),   # papada (saco)
        Ellipsoid(p((-1, -28.5 + 4 * deflate, 10.0 + JZ)), (9.5 * s, 4.5 * s, 7.0 * s), M, SKIN),   # su fondo
        Sphere(p((5.0, -19.0, 24.0 + JZ)), 1.3, WART),
    ]


def lowest(group, c):
    """Punto más bajo de group (cerca del centro c): sondeos verticales desde abajo en una rejilla."""
    xs, zs = np.meshgrid(np.arange(-20, 21, 4.0), np.arange(-14, 27, 4.0))
    P = np.column_stack([xs.ravel() + c[0], np.full(xs.size, c[1] - 70.0), zs.ravel() + c[2]])
    t = np.zeros(len(P))
    hit = np.zeros(len(P), bool)
    for _ in range(90):
        d = group.eval(P + V(0, 1, 0) * t[:, None])[0]
        hit |= d < 0.05
        t = np.where(hit, t, t + np.maximum(d * 0.8, 0.05))
    if not hit.any():
        return V(c[0], c[1] - 30, c[2])
    i = np.argmin(np.where(hit, t, np.inf))
    return P[i] + V(0, t[i], 0)


def surf(group, a, dirv, hi=30.0):
    """Primer punto de la superficie de group desde a (fuera) hacia dirv."""
    t = 0.0
    for _ in range(80):
        d = group.eval((a + dirv * t)[None])[0][0]
        if d < 0.02:
            break
        t += max(d * 0.7, 0.02)
        if t > hi:
            break
    return a + dirv * t


def ear(H, big):
    """Oreja: grande, de soplillo y caída (izquierda) o pequeña, arrugada y mordida (derecha)."""
    p = H.p
    if big:
        c = p((25.0, -4.5, -3.5))
        R = H.M(rot_z(rad(-28)) @ rot_y(rad(34)))
        parts = [Ellipsoid(c, (2.0, 10.0, 6.8), R, SKIN),
                 Ellipsoid(c + H.d((-0.6, 0.0, -0.8)), (2.6, 8.8, 5.6), R, SKIN),         # borde grueso (se ve por detrás)
                 RoundCone(p((27.0, -11.5, -2.5)), p((28.2, -17.0, -1.0)), 2.7, 2.3, SKIN),  # lóbulo caído
                 Ellipsoid(p((19.5, -5.5, -4.0)), (3.0, 5.0, 3.5), H.M(), SKIN)]               # raíz
        hole = (c + H.d((1.7, 0.6, 1.0)), nrm(H.d((1.0, 0.15, 0.5))), 5.0)
    else:
        c = p((-23.4, -3.0, -2.5))
        R = H.M(rot_z(rad(18)) @ rot_y(rad(-30)))
        parts = [Ellipsoid(c, (1.9, 5.8, 4.5), R, SKIN),
                 Ellipsoid(c + H.d((0.6, 0.0, -0.6)), (2.4, 5.0, 3.6), R, SKIN),
                 Sphere(p((-24.8, 0.8, -2.2)), 1.6, SKIN), Sphere(p((-24.4, -7.0, -1.0)), 1.8, SKIN),
                 Ellipsoid(p((-19.0, -3.5, -3.0)), (3.0, 4.0, 3.0), H.M(), SKIN)]
        hole = (c + H.d((-1.5, 0.0, 0.7)), nrm(H.d((-1.0, 0.0, 0.45))), 3.0)
    return parts, hole


def hair(H, proj, deflate=0.0, seed=7):
    """Mechón: guedejas negras y grasientas peinadas de la coronilla hacia la derecha, que cuelgan por la sien y
    la nuca, y unos pelos tiesos. proj(rumbo, elevación, alzado) da un punto sobre el cráneo (marco H)."""
    rng = np.random.default_rng(seed)
    out = []
    for k, (y0, y1, y2, e0, w) in enumerate(((150, 214, 248, 82, 1.45), (164, 223, 257, 78, 1.35),
                                              (178, 232, 266, 74, 1.2))):
        a = proj(y0, e0, 0.6)
        b = proj(y1, 62 - 4 * k, 1.0)
        c = proj(y2, 30 - 5 * k, 1.2)
        d = proj(y2 + 4, 0 - 6 * k, 1.7 + 0.4 * k)
        e = d + H.d((-0.8 - 0.6 * k, -5.5 - 1.5 * k, 0.6)) + V(0, 0, rng.uniform(-1, 1))
        out += [RoundCone(a, b, w, w * 0.95, HAIR), RoundCone(b, c, w * 0.95, w * 0.85, HAIR),
                RoundCone(c, d, w * 0.85, w * 0.65, HAIR), RoundCone(d, e, w * 0.65, 0.3, HAIR)]
    # Guedeja que cae por la nuca.
    a, b, c = proj(175, 70, 0.7), proj(182, 34, 1.2), proj(176, 2, 1.6)
    e = c + H.d((1.2, -6.5, -1.2))
    out += [RoundCone(a, b, 1.5, 1.4, HAIR), RoundCone(b, c, 1.4, 1.1, HAIR), RoundCone(c, e, 1.1, 0.3, HAIR)]
    for yaw, el, ln in ((95, 72, 3.0), (120, 80, 2.6), (30, 76, 2.6), (300, 70, 3.0), (160, 60, 3.0)):   # pelos tiesos
        a = proj(yaw, el, 0.2)
        n = nrm(a - proj(yaw, el, -1.0))
        t = a + nrm(n + H.d((rng.uniform(-0.5, 0.5), 0.2, rng.uniform(-0.5, 0.5)))) * ln
        m = (a + t) / 2 + H.d((rng.uniform(-1, 1), 0, rng.uniform(-1, 1)))
        out += [RoundCone(a, m, 0.55, 0.45, HAIR), RoundCone(m, t, 0.45, 0.25, HAIR)]
    return out


def build(pose):
    p = dict(DEFAULT)
    p.update(pose)
    dfl = p['deflate']
    H = Frame((0, Y0 + p['hc'] + p['bob'], 0),
              rot_y(rad(p['yaw'])) @ rot_x(rad(p['pitch'])) @ rot_z(rad(p['roll'])))
    J = H * Frame(V(HINGE) + (0, -p['drop'], 0),
                  rot_x(rad(p['jaw'])) @ rot_y(rad(p['twist'])) @ rot_z(rad(p['twist'] * 0.6)))
    groups = []
    extras = {'stains': [], 'eyes': [], 'sockets': [], 'ear_holes': []}

    sk = head_parts(H, p['puff'], dfl)
    jw = jaw_parts(J, dfl)
    earL, holeL = ear(H, True)
    earR, holeR = ear(H, False)
    face = FastGroup(sk + jw[:3], k=3.0)                 # cara sin tallar: para buscar la superficie
    warts = warts_on(face, H)

    # --- línea de los labios: arriba en la cabeza, abajo en la mandíbula (se buscan en la superficie)
    def lip_pt(F, u, y, inset):
        x = u * MOUTH_RX
        yy = y + BEND * u * u
        a = F.p((x, yy, 40.0))
        s = surf(face, a, F.d((0, 0, -1)), hi=60)
        return s + F.d((0, 0, -inset))
    up_c = lip_pt(H, 0.0, UL[1], 0.0)
    lo_y = UL[1] - HINGE[1] - 1.6                         # línea del labio de abajo en el marco de la mandíbula
    lo_c = lip_pt(J, 0.0, lo_y, 0.0)

    # --- boca tallada: elipsoide doblado entre las dos líneas de los labios
    # (marco alineado con la cabeza: la mandíbula torcida no levanta una comisura hasta el ojo)
    mid = (up_c + lo_c) / 2
    gap = max(abs((up_c - lo_c) @ H.d((0, 1, 0))), 0.5)
    zax = H.d((0, 0, 1))
    MF = Frame(mid + zax * -7.5, H.M())
    bent = Bent(MF, (MOUTH_RX + 0.5, gap / 2 + 0.9, 11.0), BEND)
    # Boca de oreja a oreja: desde cada comisura, un tajo que sigue la mejilla hacia la oreja.
    slits = []
    for sx in (1, -1):
        a0 = lip_pt(H, 0.96 * sx, UL[1] - 0.6, 0.6)
        pts = [a0]
        for xx, yy, zz in ((22.5, -4.0, 9.0), (24.5, -3.0, 2.0)):
            o = H.p((40.0 * sx, yy, zz))
            pts.append(surf(face, o, H.d((-sx, 0, 0)), hi=40) + H.d((sx * -0.5, 0, 0)))
        for q0, q1, r0, r1 in ((pts[0], pts[1], 1.8, 1.45), (pts[1], pts[2], 1.45, 0.8)):
            slits.append(RoundCone(q0, q1, r0, r1, MOUTH))

    def mouth(Q):
        return np.minimum.reduce([bent(Q)] + [sl(Q) for sl in slits])
    sockets = []
    eye_list = []
    for (ex, ey, rs, re) in (EYE_L, EYE_R):
        a = H.p((ex, ey - p['squint'] * 0.6, 40.0))
        s = surf(face, a, H.d((0, 0, -1)), hi=60)
        sc = s + H.d((0, 0, -0.6))
        rs_eff = rs * (1 - 0.45 * p['squint'])
        sockets.append(Sphere(sc, rs_eff, SOCKET))
        extras['sockets'].append((sc, rs_eff))
        if p['eyes'] != 'off' and p['squint'] < 0.95:
            ec = sc + H.d((0, 0, -rs_eff + re * 0.9))
            eye_list.append(Sphere(ec, re * (1 - 0.5 * p['squint']), EYE))
            extras['eyes'].append((ec, re * (1 - 0.5 * p['squint']), p['eyes']))
    crs = creases(H)
    dent = None
    if p['dent'] > 0:
        dent = Sphere(H.p((-2, TOP_Y + 17 - 12 * p['dent'], -4)), 15, SKIN)

    def crease_d(Q):
        return np.minimum.reduce([c(Q) for c in crs])

    # Todo lo tallado (boca, cuencas, surcos) cabe en esta esfera; la abolladura de la muerte no.
    cbound = None if dent is not None else (H.p((0, -4.0, 12.0)), 30.0)

    def carve(Q):
        d = np.minimum.reduce([mouth(Q), sockets[0](Q), sockets[1](Q), crease_d(Q)])
        if dent is not None:
            d = np.minimum(d, dent(Q))
        return -d

    allskin = sk + jw
    if p['wrinkle'] > 0:
        groups.append(Wrinkled(allskin, p['wrinkle'], H, seed=5, k=3.0, cut=carve, name='head'))
    else:
        groups.append(FastGroup(allskin, k=3.0, cut=carve, cut_bound=cbound, name='head'))
    groups.append(FastGroup(earL + earR, k=1.2, name='ears'))
    extras['ear_holes'] = [holeL, holeR]
    extras['mouth_fn'] = mouth
    extras['crease_fn'] = crease_d
    extras['nostrils'] = [c.c for c in crs if isinstance(c, Sphere)]
    extras['lip_w'] = 2.3
    # Profundidad de la boca (en z de la cabeza): delante, la línea de los labios; detrás, el fondo.
    zf = H.to_local(up_c[None])[0][2]
    extras['mouth_depth'] = (zf, zf - 16.0)

    # --- dientes
    teeth = []
    for u, ln, w, tilt in TEETH_UP:
        root = lip_pt(H, u, UL[1] + 1.2, 1.6)
        down = nrm(H.d((math.sin(rad(tilt)) * 0.5, -1, 0.15)))
        tip = root + down * (ln + 1.2)
        teeth.append(RoundCone(root, tip, w, 0.4, TEETH))
    for u, ln, w, tilt in TEETH_LO:
        root = lip_pt(J, u, lo_y - 1.2, 1.6)
        upv = nrm(J.d((math.sin(rad(tilt)) * 0.5, 1, 0.1)))
        tip = root + upv * (ln + 1.2)
        teeth.append(RoundCone(root, tip, w, 0.4, TEETH))
    bits = warts + teeth                              # piezas sueltas (unión dura): verrugas, dientes, lengua, ojos
    # Lengua en el suelo de la boca (en el amasijo, fuera y colgando).
    to = p['tongue_out']
    tg = J.p((0.5 + 1.5 * to, lo_y - 3.5 + 1.0 * to, 13.0 + JZ + 10.0 * to))
    bits.append(Ellipsoid(tg, (10.0 - 4.0 * to, 3.2 - 1.0 * to, 8.0 + 2.0 * to), J.M(rot_x(rad(30 * to))), TONGUE))
    if eye_list:
        bits += eye_list
    groups.append(FastGroup(bits, name='bits'))

    # --- mechón: puntos sobre el cráneo (se buscan desde fuera hacia su centro)
    skull = Group(sk[:6] + sk[19:24], k=3.0)
    cc = H.p((0, -5.0, -4))

    def proj(yaw, elev, lift):
        d = H.d((math.sin(rad(yaw)) * math.cos(rad(elev)), math.sin(rad(elev)), math.cos(rad(yaw)) * math.cos(rad(elev))))
        s = surf(skull, cc + d * 40.0, -d, hi=45)
        return s + d * lift
    groups.append(FastGroup(hair(H, proj, dfl), k=0.5, name='hair'))
    groups.append(FastGroup(veins(proj), k=0.6, name='veins'))

    # --- fuego en la boca (D)
    if p['fire']:
        # Fuego en la boca y lenguas que se escapan por encima del labio (el misil del juego nace a z+32, justo
        # encima: parece que la bola sale de esas llamas).
        size, seed = p['fire']
        core = mid + zax * 2.0
        rng = np.random.default_rng(seed)
        fparts = [Sphere(core, size, FIRE)]
        for k in range(6):
            a = 2 * math.pi * k / 6 + rng.uniform(-0.4, 0.4)
            off = V(math.cos(a), math.sin(a) * 0.7, 0.3) * size * 0.9
            fparts.append(Sphere(core + off, size * rng.uniform(0.45, 0.7), FIRE))
        tongues = []
        for xo in (-10.0, -5.0, 4.5, 9.5):
            base = mid + H.d((xo, 1.5, 0)) + zax * 3.0
            m1 = base + H.d((xo * 0.12 + rng.uniform(-1, 1), 4.5, 2.0))
            tip = m1 + H.d((xo * 0.1 + rng.uniform(-1.5, 1.5), FIRE_UP * rng.uniform(0.5, 0.8), 1.5))
            tongues += [RoundCone(base, m1, 2.3, 1.6, FIRE), RoundCone(m1, tip, 1.6, 0.35, FIRE)]
            extras.setdefault('fire_tongues', []).append((base, tip))
        groups.append(Group(fparts + tongues, k=1.2, name='fire'))
        extras['fire_core'] = (core, size * 1.1)
        extras['fire_light'] = (core, size * 4.0 + 12.0)

    extras['stains'] = [(H.p(c), r) for c, r in p['stains']]
    if p['spray']:
        groups.append(Group([Sphere(H.p(c), r, BLOOD) for c, r in p['spray']], name='spray'))

    # --- escala global (alrededor del origen) y aplastado al desinflarse (alrededor del punto más bajo,
    # que no se mueve mientras cae; en el suelo, el amasijo se apoya en el origen): P' = A·P + t
    k = SCALE
    o = V(0, Y0, 0)
    sq = p['squash']
    low = lowest(groups[0], H.o)
    Af = np.diag([1 + 0.5 * (1 - sq), sq, 1 + 0.35 * (1 - sq)])
    tf = low - Af @ low
    if p['floor']:
        tf = tf + V(0, o[1] + 2.0 - low[1], 0)
    A = k * Af
    t = k * tf + (1 - k) * o
    for g in groups:
        g.xf = (A, t, k * min(1.0, sq * 1.15))
    floor_y = (A @ low + t)[1]
    if p['pool'] > 0:
        a = p['pool']
        c = A @ (low + V(-3.0, 0, 11.0)) + t
        groups.append(Group([Ellipsoid(V(c[0], floor_y + 0.25, c[2]), (12 + 16 * a, 0.5, 7 + 7 * a),
                                       rot_y(rad(-12)), GORE)], name='pool'))
    Ainv = np.linalg.inv(A)
    extras['pre'] = lambda P: (P - t) @ Ainv.T     # punto del dibujo → punto del modelo (sin escalar)
    extras['H'] = H
    extras['fwd'] = lambda q: A @ q + t
    return groups, extras


# ----------------------------------------------------------------------------- poses
FLOAT = dict(jaw=10.0, drop=0.5)
OPEN1 = dict(jaw=14.0, drop=1.0, pitch=-4, bob=0.0, puff=0.6, eyes='hot')
OPEN2 = dict(jaw=24.0, drop=2.5, pitch=-6, bob=0.0, puff=1.2, eyes='hot')
SPIT = dict(jaw=29.0, drop=3.5, pitch=-3, bob=0.0, puff=0.3, fire=(6.5, 3), eyes='hot')
PAIN1 = dict(jaw=17.0, drop=1.5, twist=9.0, pitch=-9, roll=8, yaw=-6, squint=0.75, bob=0.0)
PAIN2 = dict(jaw=10.0, twist=-5.0, pitch=-5, roll=-6, yaw=4, squint=0.45, bob=0.0)

# Muerte (de frente): G el balazo le revienta la frente y grita; H-J se desinfla como un odre pinchado
# mientras cae; K se estrella contra el suelo; L queda el amasijo de pellejo, dientes y pelo.
WOUNDS = [((-6.0, 7.0, 15.0), 3.2), ((9.0, 6.0, 14.5), 2.0), ((0.0, -26.0, 20.0), 2.6),
          ((-14.0, -6.0, 14.0), 2.2), ((5.0, -14.0, 20.0), 1.8)]
SPRAY_G = [((-6.0, 8.0, 21.0), 1.6), ((-8.0, 11.0, 25.0), 1.2), ((-4.0, 13.0, 28.0), 0.9), ((-10.0, 15.0, 30.0), 0.7),
           ((9.0, 7.0, 20.0), 1.1), ((12.0, 9.0, 24.0), 0.8), ((0.0, -24.0, 27.0), 1.4), ((-3.0, -28.0, 29.0), 1.0),
           ((3.0, -32.0, 28.0), 0.8)]
SPRAY_H = [((-7.0, 9.0, 22.0), 1.2), ((-11.0, 14.0, 27.0), 0.9), ((-14.0, 18.0, 30.0), 0.6), ((0.0, -28.0, 26.0), 1.2),
           ((2.0, -34.0, 28.0), 0.9), ((12.0, 8.0, 22.0), 0.8)]


def deaths():
    G = dict(hc=HC_Y - 2, jaw=30.0, pitch=-18, roll=8, yaw=-4, eyes='dim', puff=0.8, bob=1.0, stains=WOUNDS[:3], spray=SPRAY_G)
    H = dict(hc=HC_Y - 5, jaw=33.0, pitch=-10, roll=-4, eyes='dim', deflate=0.22, wrinkle=0.4, dent=0.25, sag=0.25,
             stains=WOUNDS[:4], spray=SPRAY_H, squash=0.92)
    I = dict(hc=HC_Y - 8, jaw=26.0, pitch=2, roll=-9, twist=-6, eyes='dead', deflate=0.45, wrinkle=0.7, dent=0.55, sag=0.5,
             stains=WOUNDS, squash=0.8)
    J = dict(hc=HC_Y - 10, jaw=20.0, pitch=10, roll=-14, twist=-8, eyes='dead', deflate=0.68, wrinkle=0.9, dent=0.8, sag=0.75,
             stains=WOUNDS, squash=0.66)
    K = dict(jaw=24.0, pitch=-16, roll=-10, twist=-8, eyes='dead', deflate=0.85, wrinkle=0.75, dent=0.95, sag=0.9,
             stains=WOUNDS, squash=0.58, floor=True, tilt=20.0, pool=0.45, tongue_out=0.5)
    L = dict(jaw=26.0, pitch=-30, roll=-12, twist=-10, eyes='dead', deflate=1.0, wrinkle=0.8, dent=1.0, sag=1.0,
             stains=WOUNDS, squash=0.47, floor=True, tilt=30.0, pool=1.0, tongue_out=1.0)
    return [G, H, I, J, K, L]


def view_dir(angle, tilt=sdf.TILT):
    th = (angle - 1) * math.pi / 4 if angle else 0.0
    return V(0, -math.sin(tilt), -math.cos(tilt)) @ rot_y(-th)


def place(img, name, floor=False):
    """Recorta filas vacías de abajo y apunta los offsets: eje en el centro; origen a Y0S px del borde del
    lienzo (vuela: siempre igual respecto a la cabeza) o, en el suelo, la fila más baja 1 px bajo el origen."""
    a = np.array(img)
    a[a[:, :, 3] < 128] = 0
    H, W = a.shape[:2]
    top = H - 1 - Y0S
    rows = np.nonzero((a[:, :, 3] >= 128).any(1))[0]
    a = a[:rows.max() + 1]
    if floor:
        top = rows.max()
    OFFSETS[name] = [W // 2, int(top)]
    return Image.fromarray(a, 'RGBA')


# ----------------------------------------------------------------------------- escupitajo (BAL2)
# No rota (lumps …0) y el juego lo pinta a pleno brillo: se dibuja en 2D, sin contorno, con un campo de
# «calor» (ruido determinista) cuantizado a una rampa roja-anaranjada (la bola de la Meiga es verde).
BAL_RAMP = [190, 186, 182, 178, 176, 217, 215, 214, 213, 211, 209]
# Lienzo y punto de apoyo de cada fotograma = los de Freedoom (el centro de la bola en el mismo sitio).
BAL_CANVAS = {'A': ((15, 15), (8, 12)), 'B': ((16, 16), (8, 13)), 'C': ((32, 30), (16, 23)),
              'D': ((40, 35), (20, 27)), 'E': ((49, 44), (25, 34))}


def fbm2(x, y, scale, seed):
    P = np.column_stack([x.ravel(), y.ravel(), np.full(x.size, 0.61 + seed)])
    n = vnoise(P, scale, seed) * 0.6 + vnoise(P, scale * 2.1, seed + 1) * 0.3 + vnoise(P, scale * 4.3, seed + 2) * 0.1
    return n.reshape(x.shape)


def ball_heat(x, y, frame):
    """Campo de calor (x, y en píxeles desde el centro, y hacia arriba)."""
    r = np.hypot(x, y)
    th = np.arctan2(y, x)
    if frame in 'AB':
        seed, rot = (21, 0.0) if frame == 'A' else (26, 2.3)
        nang = fbm2(np.cos(th + rot) * 2.0, np.sin(th + rot) * 2.0, 1.0, seed)
        R = 5.3 * (0.7 + 0.6 * nang) * (1 + 0.25 * np.clip(y / 6, 0, 1))     # lenguas hacia arriba
        return 1.15 - r / R + 0.25 * (fbm2(x, y, 0.8, seed + 5) - 0.5)
    rc, w, peak, fill, holes, seed = {'C': (6.5, 4.5, 1.05, 1.0, 0.0, 31),
                                       'D': (10.5, 4.2, 0.85, 0.4, 0.35, 32),
                                       'E': (14.5, 3.6, 0.45, 0.0, 0.62, 33)}[frame]
    nang = fbm2(np.cos(th) * 3.0, np.sin(th) * 3.0, 1.0, seed)
    rr = rc * (0.72 + 0.56 * nang)
    h = peak * np.exp(-((r - rr) / w) ** 2)
    h = np.maximum(h, fill * peak * np.clip(1 - r / rr, 0, 1) * 1.15)
    h *= 0.45 + 1.0 * fbm2(x, y, 0.45, seed + 3)
    h -= holes * (fbm2(x, y, 0.24, seed + 7) > 0.57)
    return h


def ball_drops(frame):
    """Gotas y chispas sueltas: (x, y, nivel de la rampa)."""
    n, r0, r1, lvl, seed = {'A': (3, 5.5, 7.0, 7, 51), 'B': (3, 5.5, 7.5, 7, 52), 'C': (10, 9.0, 14.0, 7, 53),
                            'D': (12, 12.0, 17.5, 5, 54), 'E': (9, 16.0, 21.0, 2, 55)}[frame]
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(r0, r1)
        out.append((math.cos(a) * r, math.sin(a) * r * 0.9, lvl))
    return out


def draw_ball(frame):
    (W, H), (ox, oy) = BAL_CANVAS[frame]
    cx, cy = W / 2, oy - (4.5 if frame in 'AB' else oy - H / 2)       # centro: el de la bola de Freedoom
    if frame not in 'AB':
        cy = H / 2
    jj, ii = np.meshgrid(np.arange(W * SS), np.arange(H * SS))
    x = (jj + 0.5) / SS - cx
    y = cy - (ii + 0.5) / SS
    h = ball_heat(x, y, frame)
    on = h > 0.05
    cnt = on.reshape(H, SS, W, SS).sum(axis=(1, 3))
    hs = np.where(on, h, 0).reshape(H, SS, W, SS).sum(axis=(1, 3))
    hm = hs / np.maximum(cnt, 1)
    n = len(BAL_RAMP)
    lv = np.clip(np.floor(hm * n), 0, n - 1).astype(int)
    vis = cnt >= 6
    for sx, sy, sl in ball_drops(frame):
        px, py = int(math.floor(cx + sx)), int(math.floor(cy - sy))
        if 0 <= px < W and 0 <= py < H:
            lv[py, px] = max(lv[py, px], sl) if vis[py, px] else sl
            vis[py, px] = True
    pal = render().palarr
    img = np.zeros((H, W, 4), np.uint8)
    img[vis, :3] = pal[np.array(BAL_RAMP)[lv[vis]]].astype(np.uint8)
    img[vis, 3] = 255
    return Image.fromarray(img, 'RGBA')


# ----------------------------------------------------------------------------- salida
def lumps():
    out = {}
    for fr, pose in (('A', FLOAT), ('B', OPEN1), ('C', OPEN2), ('D', SPIT), ('E', PAIN1), ('F', PAIN2)):
        for a in range(1, 9):
            out[f'HEAD{fr}{a}'] = ((f'HEAD{fr}{a}', pose), a)
    for fr, pose in zip('GHIJKL', deaths()):
        out[f'HEAD{fr}0'] = ((f'HEAD{fr}0', pose), 1)
    for fr in 'ABCDE':
        out[f'BAL2{fr}0'] = ((f'BAL2{fr}0', ('ball', fr)), 0)
    return out


def draw(item, angle):
    name, pose = item
    if isinstance(pose, tuple):
        fr = pose[1]
        OFFSETS[name] = list(BAL_CANVAS[fr][1])
        return draw_ball(fr)
    groups, extras = build(pose)
    tilt = rad(pose.get('tilt', 10.0))
    extras['view'] = view_dir(angle, tilt)
    R = render(tilt)
    out, depth = R.render(groups, extras, angle)
    return place(trim(finish(out, depth, R.palarr, OUTLINE)), name, pose.get('floor', False))


OFFSETS_JSON = 'offsets_anima_coco.json'


def save_offsets(folder, new):
    """Mezcla new en arte/sprites/offsets_anima_coco.json (con cerrojo: anima.py escribe el mismo)."""
    if not new:
        return
    path = os.path.join(folder, OFFSETS_JSON)
    with open(path, 'a+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        txt = f.read()
        cur = json.loads(txt) if txt.strip() else {}
        cur.update(new)
        f.seek(0)
        f.truncate()
        f.write('{\n' + ',\n'.join(f'  "{k}": [{v[0]}, {v[1]}]' for k, v in sorted(cur.items())) + '\n}\n')
        f.flush()
        fcntl.flock(f, fcntl.LOCK_UN)


def main():
    rows = sprite_rows('HEAD', 'ABCDEF', 'GHIJKL') + [[f'BAL2{f}0' for f in 'ABCDE']]
    cli(lumps, draw, rows)
    out = sys.argv[sys.argv.index('--salida') + 1]
    save_offsets(out, OFFSETS)


if __name__ == '__main__':
    main()
