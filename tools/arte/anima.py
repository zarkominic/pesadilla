#!/usr/bin/env python3
"""anima.py — dibuja POR CÓDIGO al ÁNIMA (sustituye al alma perdida SKUL de Freedoom).

Un alma en pena de la Santa Compaña: una calavera humana que flota envuelta en llamas amarillas y
anaranjadas que suben, con brasas al fondo de las cuencas y una mandíbula que se descuelga al embestir.

Técnica (mismo motor que el resto de criaturas, tools/arte/sdf.py): la CALAVERA es un modelo 3D de
primitivas SDF (cráneo, arcos de las cejas, pómulos, maxilar, mandíbula con bisagra, dientes) con las
cuencas y la nariz TALLADAS, trazada en los 8 ángulos con rampas exactas de PLAYPAL y contorno de 1 px.
Las LLAMAS se dibujan en 2D alrededor de la silueta ya trazada: la silueta se «arrastra» siguiendo un
campo de flujo (hacia arriba, hacia atrás según hacia dónde mire y, al embestir, en abanico alrededor)
y la longitud de cada lengua sale de un ruido determinista; el calor se cuantiza a una rampa de rojos,
naranjas y amarillos. El fuego va DETRÁS de la calavera (que siempre se lee entera) y la tiñe de naranja
por los bordes, a trozos. Para que no parezca una pegatina sobre el fuego, solo las lenguas largas nacen
amarillas (el resto, anaranjadas), el borde de llama pegado a la silueta se rompe con ruido y no pasa del
naranja, y donde la llama es viva parte del contorno oscuro se vuelve brasa roja.

Fotogramas (info.c, SPR_SKUL; A-I a pleno brillo):
    A-B  vuelo (las llamas cambian)                       8 ángulos
    C-D  embestida: mandíbula abierta, llamas hacia atrás 8 ángulos
    E    dolor                                            8 ángulos
    F-I  muerte: se agrieta, revienta en llamas y huesos  de frente
    J-K  humo y brasas que se apagan (no brillan)         de frente

Apoyo: vuela. Los offsets se escriben explícitos en arte/sprites/offsets_anima_coco.json (el centro de la
calavera siempre a SC_Y px sobre el origen, como el alma perdida de Freedoom).

Uso (determinista, regenera los 46 PNG SKUL*):
    ~/.venvs/pesadilla/bin/python tools/arte/anima.py --salida arte/sprites
    … --solo SKULA1,SKULF0      solo esos lumps
    … --hoja hoja.png           además, hoja de contactos ampliada x3 con etiquetas
"""
import math
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdf  # noqa: E402
from sdf import (V, nrm, rot_x, rot_y, rot_z, rad, Frame, _len, Prim,  # noqa: E402
                 Sphere, Ellipsoid, RoundCone, Group, vnoise, SS,
                 Render, finish, apply_shine, cli, sprite_rows)
from coco import save_offsets, fbm2  # noqa: E402

# ----------------------------------------------------------------------------- materiales
(BONE, TEETH, SOCKET, EYE, BONEL, CRACK, SMOKE, CHAR, CHARL) = range(9)
RAMPS = {
    BONE: [2, 151, 149, 147, 145, 144, 129, 128],      # hueso marfil sucio
    TEETH: [2, 150, 148, 146, 144, 130, 129],          # dientes
    SOCKET: [0],
    EYE: [183, 216, 161, 225],                         # brasa al fondo de la cuenca (borde → núcleo)
    BONEL: [2, 236, 73, 69, 66, 216, 214, 212],        # hueso a la luz del fuego (bordes): anaranjado
    CRACK: [0, 1],
    SMOKE: [0],
    CHAR: [0, 1, 2, 239, 238, 237, 236],               # hueso carbonizado
    CHARL: [0, 188, 185, 235, 233],                    # brasas en los bordes del hueso que se apaga
}
EMISSIVE = (EYE,)
OUTLINE = 2
EMBER_EDGE = 235                     # (135,35,0): brasa oscura para el contorno que toca la llama viva
FIRE = [186, 235, 233, 221, 217, 215, 214, 162, 161, 160, 227, 225]   # fuego: de la punta al corazón
SMOKE_RAMP = [5, 111, 109, 107, 105, 103, 101, 99]                     # humo (J-K, no brillan)
EMBER = [186, 183, 235, 233, 221, 217]

# ----------------------------------------------------------------------------- apoyo (vuela)
Y0S = 8                                  # origen a 8 px del borde de abajo del lienzo del trazado
Y0 = Y0S / math.cos(sdf.TILT)
SC_Y = 16.0                              # centro de la calavera sobre el origen
SCALE = 1.25                             # la calavera se piensa en px y se agranda al dibujar
OFFSETS = {}
PADX, PADT, PADB = 16, 28, 6             # margen del lienzo para las llamas


class Cut(Prim):
    """Recorte por un plano dentado: lo que queda del lado n·(q-c) < ruido (marco del cráneo)."""

    def __init__(self, F, c, n, jag=1.2, seed=0):
        self.F, self.c, self.n, self.jag, self.seed = F, V(c), nrm(n), jag, seed
        self.mat = BONE
        self.bc, self.br = self.F.o, 1e3

    def sdf(self, P):
        q = self.F.to_local(P)
        return (q - self.c) @ self.n - self.jag * (vnoise(q, 0.45, self.seed) - 0.5) * 2


def materiales(P, mat, inten, nz, nr, spec, lvl_extra, extras):
    """Grietas, dientes separados, cuencas negras, brasas y el borde teñido por el fuego."""
    Q = extras['pre'](P)
    loc = extras['S'].to_local(Q)
    bone = mat == BONE
    # Grietas finas y manchas de hueso viejo.
    for a, b, w in CRACKS[:2 + int(extras.get('crack', 0.0) * (len(CRACKS) - 2))]:
        ab = b - a
        tt = np.clip(((loc - a) @ ab) / (ab @ ab), 0, 1)
        dd = _len(loc - (a + np.outer(tt, ab)))
        m = bone & (dd < w)
        mat[m] = CRACK
    inten[bone] *= 0.86 + 0.24 * vnoise(loc[bone], 0.8, 12)
    # Dientes: rayas oscuras entre diente y diente.
    m = mat == TEETH
    if m.any():
        g = np.abs(np.sin(loc[m, 0] * 2.9 + 0.3))
        inten[m] *= np.where(g < 0.3, 0.2, 1.0)
    apply_shine(mat, inten, spec, ((BONE, 0.35, 6), (TEETH, 0.4, 6)))
    # Cuencas y nariz talladas: negras.
    for c, r in extras.get('holes', []):
        m = np.isin(mat, (BONE, CRACK)) & (_len(Q - c) < r + 0.45)
        mat[m] = SOCKET
    # Brasas al fondo de las cuencas.
    for c, r, hot in extras.get('eyes', []):
        de = _len(Q - c)
        m = (mat == EYE) & (de < r + 0.6)
        lvl_extra[m] = np.where(de[m] < r * 0.5 + 0.2, 2 + hot, 1 + hot)
    # Borde de la silueta teñido por el fuego que la envuelve (más por arriba y por detrás).
    Dv = extras['view']
    rim = 1 - np.abs(nr @ Dv)
    up = np.clip(nr[:, 1] + 0.3, 0, 1)
    amt = rim ** 2 * (0.25 + 0.85 * up) * (0.75 + 0.5 * vnoise(loc, 0.6, 14)) * extras.get('glow', 1.0)
    amt = amt * np.clip(0.3 + 1.1 * vnoise(loc, 0.32, 15), 0, 1.2)      # a trozos: no es un anillo continuo
    ch = extras.get('char', 0.0)
    if ch > 0:
        m = np.isin(mat, (BONE, TEETH, CRACK)) & (vnoise(loc, 0.5, 13) < 0.35 + 0.7 * ch)
        mat[m] = CHAR
        inten[m] *= 1.1 - 0.4 * ch
        m = (mat == CHAR) & (amt > 0.5 + 0.3 * ch)
        mat[m] = CHARL
    m = (mat == BONE) & (amt > 0.5)
    mat[m] = BONEL
    inten[m] = np.maximum(inten[m], 0.35) + amt[m] * 0.4


RENDER = None


def render():
    global RENDER
    if RENDER is None:
        RENDER = Render(RAMPS, hook=materiales, level_mats=(EYE,), emissive=EMISSIVE,
                        no_light=(EYE, SOCKET))
    return RENDER


# ----------------------------------------------------------------------------- calavera
HINGE = (0.0, -4.2, -1.2)
EYE_C = (3.75, 0.9, 7.0)                 # centro de la cuenca izquierda (x+)
EYE_R = 2.75


def skull_parts(S, J):
    """Cráneo y cara en el marco S; mandíbula en el marco J (bisagra en su origen)."""
    p = S.p
    M = S.M()
    cran = [
        Ellipsoid(p((0, 3.2, -1.8)), (8.8, 9.0, 10.4), M, BONE),                 # bóveda
        Ellipsoid(p((0, 3.8, 3.6)), (7.8, 7.4, 6.4), M, BONE),                   # frente
        Ellipsoid(p((0, 2.7, 6.9)), (7.4, 1.7, 2.1), M, BONE),                   # arco de las cejas
        Ellipsoid(p((6.3, -2.6, 4.8)), (2.4, 2.1, 3.3), M, BONE),                # pómulo izquierdo
        Ellipsoid(p((-6.3, -2.6, 4.8)), (2.4, 2.1, 3.3), M, BONE),               # pómulo derecho
        RoundCone(p((6.6, -2.6, 3.0)), p((7.6, -2.2, -2.4)), 1.2, 1.0, BONE),    # arcos cigomáticos
        RoundCone(p((-6.6, -2.6, 3.0)), p((-7.6, -2.2, -2.4)), 1.2, 1.0, BONE),
        Ellipsoid(p((0, -5.0, 4.6)), (5.0, 3.4, 4.4), M, BONE),                  # maxilar
    ]
    teeth_up = [Ellipsoid(p((0, -7.6, 5.4)), (4.3, 1.5, 3.7), M, TEETH)]
    q = J.p
    MJ = J.M()
    jaw = [
        Ellipsoid(q((0, -6.6, 6.0)), (4.6, 2.0, 3.6), MJ, BONE),                 # mentón
        RoundCone(q((4.6, -6.0, 4.0)), q((5.6, -1.5, -0.6)), 1.4, 1.2, BONE),    # ramas
        RoundCone(q((-4.6, -6.0, 4.0)), q((-5.6, -1.5, -0.6)), 1.4, 1.2, BONE),
        Ellipsoid(q((0, -5.8, 3.0)), (5.0, 1.6, 3.4), MJ, BONE),
    ]
    teeth_lo = [Ellipsoid(q((0, -4.3, 5.6)), (4.0, 1.4, 3.2), MJ, TEETH)]
    return cran, teeth_up, jaw, teeth_lo


# Grietas (segmentos en el marco del cráneo, sobre la bóveda): las dos primeras siempre; más al morir.
CRACKS = [(V(1.5, 12.2, 2.0), V(4.0, 10.0, 6.5), 0.32), (V(4.0, 10.0, 6.5), V(3.0, 7.5, 9.0), 0.3),
          (V(-2.0, 12.0, -3.0), V(-6.5, 8.5, -6.0), 0.32), (V(1.5, 12.2, 2.0), V(-2.0, 12.0, -3.0), 0.32),
          (V(-4.5, 9.5, 6.5), V(-1.5, 6.5, 9.5), 0.34), (V(6.0, 8.0, -6.0), V(8.4, 3.0, -3.0), 0.34),
          (V(-6.5, 8.5, -6.0), V(-8.5, 2.0, -4.0), 0.34)]

DEFAULT = dict(pitch=0.0, yaw=0.0, roll=0.0, bob=0.0, jaw=4.0, hot=0, glow=1.0, crack=0.0,
               t=None, eyes=True, char=0.0)

# Muerte: la calavera revienta en trozos que salen despedidos y giran (marco del cráneo, unidades/t).
# (nombre, región: y por encima/debajo de la línea de rotura y lado, velocidad, eje de giro, grados por t)
PIECES = [('capL', (1, 1), V(17.0, 17.0, 2.0), V(0, 0, 1), -110.0),
          ('capR', (1, -1), V(-18.0, 14.0, 1.0), V(0.2, 0, 1), 120.0),
          ('faceL', (-1, 1), V(9.0, -1.0, 6.0), V(0.3, 0.4, 1), -80.0),
          ('faceR', (-1, -1), V(-10.0, -3.0, 6.0), V(0.3, -0.3, 1), 90.0),
          ('jaw', None, V(-2.0, -13.0, 5.0), V(1, 0, 0.3), -150.0)]
GRAV = -22.0
SPLIT_Y = 2.6


def shards(S, t, seed=77):
    """Esquirlas de hueso y dientes sueltos: [(prim, centro, velocidad, eje, giro)]."""
    rng = np.random.default_rng(seed)
    out = []
    for k in range(9):
        a = rng.uniform(0, 2 * math.pi)
        sp = rng.uniform(16, 26)
        v = V(math.cos(a) * sp, math.sin(a) * sp * 0.8 + 6, rng.uniform(-3, 6))
        c = V(rng.uniform(-5, 5), rng.uniform(-6, 8), rng.uniform(-2, 6))
        if k < 6:
            pr = Ellipsoid(S.p(c), (rng.uniform(1.0, 1.8), rng.uniform(0.5, 0.8), rng.uniform(0.8, 1.4)),
                           S.M(rot_z(rng.uniform(0, 3))), BONE)
        else:
            pr = RoundCone(S.p(c), S.p(c + V(0, -1.6, 0.3)), 0.75, 0.45, TEETH)
        out.append((pr, c, v, nrm(rng.normal(size=3)), rng.uniform(-200, 200)))
    return out


def build(pose, lift=0.0):
    """lift: el modelo se sube lift px en pantalla (la muerte cae por debajo del origen)."""
    p = dict(DEFAULT)
    p.update(pose)
    Y0e = Y0 + lift / math.cos(sdf.TILT)
    S = Frame((0, Y0e + SC_Y + p['bob'], 0),
              rot_y(rad(p['yaw'])) @ rot_x(rad(p['pitch'])) @ rot_z(rad(p['roll'])))
    J = S * Frame(HINGE, rot_x(rad(p['jaw'])))
    cran, tup, jaw, tlo = skull_parts(S, J)
    holes = [Sphere(S.p((EYE_C[0], EYE_C[1], EYE_C[2])), EYE_R, SOCKET),
             Sphere(S.p((-EYE_C[0], EYE_C[1], EYE_C[2])), EYE_R, SOCKET),
             Ellipsoid(S.p((0, -3.3, 8.0)), (1.1, 1.6, 2.2), S.M(), SOCKET),
             Sphere(S.p((0.7, -3.9, 8.5)), 0.8, SOCKET), Sphere(S.p((-0.7, -3.9, 8.5)), 0.8, SOCKET)]

    def holes_d(Q):
        return np.minimum.reduce([h(Q) for h in holes])
    mouth = Ellipsoid(S.p((0, -8.6, 3.6)), (3.5, 1.3, 3.0), S.M(), SOCKET)    # fondo oscuro de la boca
    eyes = []
    extras = {'holes': [], 'eyes': [], 'S': S, 'glow': p['glow'], 'crack': p['crack'], 'char': p['char']}
    for sx in (1, -1):
        c = S.p((EYE_C[0] * sx, EYE_C[1], EYE_C[2]))
        extras['holes'].append((c, EYE_R))
        ec = S.p((EYE_C[0] * sx * 0.9, EYE_C[1] - 0.2, EYE_C[2] - 2.6))
        eyes.append(Sphere(ec, 1.15, EYE))
        extras['eyes'].append((ec, 1.15, p['hot']))
    extras['holes'].append((S.p((0, -3.5, 8.4)), 1.6))
    k = SCALE
    o = V(0, Y0e, 0)

    if p['t'] is None:
        groups = [Group(cran, k=1.6, cut=lambda Q: -holes_d(Q), name='skull'), Group(tup, name='teeth'),
                  Group(jaw, k=1.0, name='jaw'), Group(tlo, name='teeth'), Group([mouth], name='mouth')]
        if p['eyes']:
            groups.append(Group(eyes, name='eyes'))
        t = (1 - k) * o
        for g in groups:
            g.xf = (np.eye(3) * k, t, k)
        extras['pre'] = lambda P: (P - t) / k
        return groups, extras

    # --- reventada: cada trozo con su movimiento (A = k·R, t = k·(c − R·c + desplazamiento) + (1 − k)·o)
    T = p['t']
    owners = []
    groups = []

    def motion(c_loc, v, ax, deg):
        c = S.p(c_loc)
        R = rot_axis_(S.d(ax), rad(deg * T)) * (1 - 0.4 * p['char'])      # el hueso que se apaga mengua
        disp = S.d(v) * T + V(0, 0.5 * GRAV * T * T, 0)
        A = k * R
        tt = k * (c - R @ c + disp) + (1 - k) * o
        return A, tt

    def jag(Q, seed):
        q = S.to_local(Q)
        return 0.9 * (vnoise(q, 0.5, seed) - 0.5) * 2

    for name, region, v, ax, deg in PIECES:
        if name == 'jaw':
            gs = [Group(jaw, k=1.0, name='jaw'), Group(tlo, name='teeth')]
            c_loc = V(0, -9.0, 3.0)
        else:
            ys, xs = region

            def cut(Q, ys=ys, xs=xs):
                q = S.to_local(Q)
                r = ys * (SPLIT_Y - q[:, 1]) + jag(Q, 3)
                if xs:
                    r = np.maximum(r, -xs * q[:, 0] + jag(Q, 4))
                return np.maximum(r, -holes_d(Q))
            gs = [Group(cran, k=1.6, cut=cut, name=name)]
            if name.startswith('face'):
                half = lambda Q, xs=xs: -xs * S.to_local(Q)[:, 0]
                gs.append(Group(tup, cut=half, name='teeth'))
                if p['eyes']:
                    gs.append(Group([eyes[0] if xs > 0 else eyes[1]], name='eyes'))
                c_loc = V(3.5 * xs, -2.0, 4.0)
            else:
                c_loc = V(4.0 * xs, 8.0, -1.0)
        A, tt = motion(c_loc, v, ax, deg)
        for g in gs:
            g.xf = (A, tt, k * (1 - 0.4 * p['char']))
        groups += gs
        owners.append((gs, np.linalg.inv(A), tt))
    for pr, c_loc, v, ax, deg in shards(S, T):
        A, tt = motion(c_loc, v, ax, deg)
        g = Group([pr], name='shard')
        g.xf = (A, tt, k * (1 - 0.4 * p['char']))
        groups.append(g)
        owners.append(([g], np.linalg.inv(A), tt))

    def pre(P):
        best = np.full(len(P), np.inf)
        Q = np.zeros_like(P)
        for gs, Ai, tt in owners:
            d = np.min([g.eval(P)[0] for g in gs], axis=0)
            m = d < best
            best = np.where(m, d, best)
            Q[m] = (P[m] - tt) @ Ai.T
        return Q
    extras['pre'] = pre
    return groups, extras


def rot_axis_(axis, a):
    return sdf.rot_axis(axis, a)


# ----------------------------------------------------------------------------- llamas (2D)
def flame_layer(mask, cx, cy, fl, seed):
    """Calor de las llamas en el lienzo (alto, ancho) a partir de la silueta mask (bool).
    cx, cy: centro de la calavera (px; y hacia abajo). fl: parámetros del flujo y las lenguas."""
    Hh, Ww = mask.shape
    sub = 3
    jj, ii = np.meshgrid(np.arange(Ww * sub), np.arange(Hh * sub))
    x = (jj + 0.5) / sub
    y = (ii + 0.5) / sub
    X, Y = x - cx, cy - y                                   # y hacia arriba
    r = np.hypot(X, Y) + 1e-6
    # Flujo: arriba + de lado (hacia atrás) + en abanico (embestida de frente).
    fx = fl['side'] + fl['rad'] * X / r
    fy = fl['up'] + fl['rad'] * Y / r
    fn = np.hypot(fx, fy) + 1e-6
    fx, fy = fx / fn, fy / fn
    # Coordenada a lo ancho del flujo → lenguas de distinta longitud.
    u = X * fy - Y * fx
    nl = fbm2(u * 0.4, np.full_like(u, 0.0) + seed * 0.1, 1.0, seed)
    L = fl['len'] * (0.22 + 1.45 * nl ** 2.0)
    # Calor en la raíz de cada lengua: solo las largas nacen amarillas; las cortas, anaranjadas. Así la
    # llama no forma un anillo amarillo continuo pegado a la calavera.
    h0 = 0.5 + 0.55 * np.clip((nl - 0.2) * 1.5, 0, 1)
    heat = np.zeros_like(x)
    steps = np.arange(0.0, fl['len'] * 1.45, 0.5)
    for s in steps:
        wig = fl['wig'] * math.sin(s * 0.55 + seed * 1.7) * min(1.0, s / 4.0)
        sx = x - fx * s * 1.0 - fy * wig
        sy = y + fy * s * 1.0 - fx * wig                     # en píxeles con y hacia abajo
        ix = np.clip(sx.astype(int), 0, Ww - 1)
        iy = np.clip(sy.astype(int), 0, Hh - 1)
        inside = mask[iy, ix] & (sx >= 0) & (sx < Ww) & (sy >= 0) & (sy < Hh)
        h = np.where(inside, h0 * (1.0 - s / L), 0.0)
        heat = np.maximum(heat, h)
    # Borde de fuego que abraza la silueta por todos lados (también por debajo, más fino).
    rim = np.zeros_like(x)
    # (dx, dy: dónde se mira la silueta; dy > 0 = debajo del punto → el punto está ENCIMA de la calavera)
    for dx, dy, w in ((1, 0, 0.8), (-1, 0, 0.8), (0, 1, 1.0), (0, -1, 0.42), (2, 0, 0.5), (-2, 0, 0.5), (0, 2, 0.8),
                      (1, 1, 0.9), (-1, 1, 0.9), (1, -1, 0.45), (-1, -1, 0.45)):
        ix = np.clip((x + dx).astype(int), 0, Ww - 1)
        iy = np.clip((y + dy).astype(int), 0, Hh - 1)
        rim = np.maximum(rim, np.where(mask[iy, ix], 0.75 * w, 0))
    # El borde se rompe con ruido a lo largo de la silueta y no pasa del naranja.
    th = np.arctan2(Y, X)
    brk = fbm2(np.cos(th) * 3.0, np.sin(th) * 3.0 + seed * 0.37, 1.0, seed + 11)
    rim = rim * np.clip(0.15 + 1.1 * brk, 0, 1)
    heat = np.maximum(heat, np.minimum(rim * fl.get('rim', 1.0), 0.52))
    heat *= 0.5 + 0.5 * np.clip(0.55 + 0.8 * Y / r, 0, 1)         # más vivo por arriba que por debajo
    streak = fbm2(u * 0.7, (X * fx + Y * fy) * 0.12 + seed, 1.0, seed + 5)
    heat = heat * (0.78 + 0.45 * streak)
    base = heat > 0.02
    heat = heat + 0.22 * (fbm2(x * 0.5, y * 0.5 + seed, 0.9, seed + 3) - 0.5)
    heat = np.where(base & (heat > 0.05), heat, 0)
    # Reducción a píxeles: media del calor de las submuestras encendidas.
    on = heat > 0
    cnt = on.reshape(Hh, sub, Ww, sub).sum(axis=(1, 3))
    hs = heat.reshape(Hh, sub, Ww, sub).sum(axis=(1, 3))
    return np.where(cnt >= 4, hs / np.maximum(cnt, 1), 0.0)


def sparks(cx, cy, n, r0, r1, up, seed):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(r0, r1)
        out.append((cx + math.cos(a) * r, cy - abs(math.sin(a)) * r * 0.6 - rng.uniform(0, up)))
    return out


def compose(skull_rgba, fl, seed, ramp=FIRE, extra_heat=None, n_sparks=4):
    """Pone la calavera (ya con contorno) sobre su capa de llamas en un lienzo más grande.
    Devuelve (imagen, fila del origen, columna del eje)."""
    a = np.array(skull_rgba)
    H, W = a.shape[:2]
    Hh, Ww = H + PADT + PADB, W + 2 * PADX
    big = np.zeros((Hh, Ww, 4), np.uint8)
    big[PADT:PADT + H, PADX:PADX + W] = a
    mask = big[:, :, 3] >= 128
    oy = PADT + H - 1 - Y0S                                  # fila del origen (borde de arriba)
    ax = PADX + W // 2
    cx = ax
    cy = oy - SC_Y * math.cos(sdf.TILT) + 0.5
    heat = flame_layer(mask, cx, cy, fl, seed) if fl is not None else np.zeros((Hh, Ww))
    if extra_heat is not None:
        heat = np.maximum(heat, extra_heat(Hh, Ww, cx, cy))
    pal = render().palarr
    n = len(ramp)
    lv = np.clip(np.floor(heat * n), 0, n - 1).astype(int)
    fire = (heat > 0.06) & ~mask
    for sx, sy in sparks(cx, cy, n_sparks, 8, 14, 10, seed + 9):
        px, py = int(sx), int(sy)
        if 0 <= px < Ww and 0 <= py < Hh and not mask[py, px]:
            fire[py, px] = True
            lv[py, px] = max(lv[py, px], n // 2)
    out = big.copy()
    out[fire, :3] = pal[np.array(ramp)[lv[fire]]].astype(np.uint8)
    out[fire, 3] = 255
    # Contorno fundido con la llama: donde la llama es viva (y por arriba), algunos píxeles del contorno se
    # vuelven brasa roja oscura: la calavera arde, no parece una pegatina sobre el fuego.
    edge = mask & (np.all(big[:, :, :3] == pal[OUTLINE].astype(np.uint8), axis=2))
    hot = np.zeros_like(mask)
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        hot |= np.roll(np.roll(fire & (heat > 0.45), dy, 0), dx, 1)
    yy, xx = np.nonzero(edge & hot)
    if len(yy):
        nz = fbm2(xx * 0.6, yy * 0.6 + seed, 1.0, seed + 21)
        upper = yy < cy + 2
        sel = upper & (nz > 0.45)
        out[yy[sel], xx[sel], :3] = pal[EMBER_EDGE].astype(np.uint8)
    return out, oy, ax


def place(a, oy, ax, name):
    """Recorta simétrico respecto al eje y filas vacías; apunta los offsets (izq, sup)."""
    vis = a[:, :, 3] >= 128
    a[~vis] = 0
    cols = np.nonzero(vis.any(0))[0]
    rows = np.nonzero(vis.any(1))[0]
    need = max(ax - cols.min(), cols.max() + 1 - ax)
    x0 = ax - need
    b = a[rows.min():rows.max() + 1, x0:ax + need]
    OFFSETS[name] = [need, int(oy - rows.min())]
    return Image.fromarray(b, 'RGBA')


# ----------------------------------------------------------------------------- poses
def facing(angle):
    """(x en pantalla hacia donde mira, hacia la cámara) para el ángulo de Doom."""
    th = (angle - 1) * math.pi / 4
    return -math.sin(th), math.cos(th)


def flow(angle, kind, frame):
    fx, fz = facing(angle)
    if kind == 'fly':
        return dict(up=1.0, side=-0.55 * fx, rad=0.3, len=19.0 + 2.0 * frame, wig=1.4)
    if kind == 'charge':
        return dict(up=0.6, side=-1.4 * fx, rad=0.35 + 0.9 * abs(fz), len=20.0 + 2.5 * frame, wig=1.0)
    if kind == 'pain':
        return dict(up=0.6, side=-0.3 * fx, rad=1.0, len=11.0, wig=2.4)
    raise ValueError(kind)


FLY = [dict(jaw=3.0, pitch=-2.0, bob=0.0), dict(jaw=5.0, pitch=2.0, bob=0.6)]
CHARGE = [dict(jaw=32.0, pitch=8.0, hot=1, bob=-0.4), dict(jaw=40.0, pitch=12.0, hot=1, bob=-0.6)]
PAIN = dict(jaw=26.0, pitch=-20.0, roll=14.0, yaw=-10.0, bob=0.8, glow=0.6)


def draw_rot(name, pose, angle, kind, frame):
    groups, extras = build(pose)
    th = (angle - 1) * math.pi / 4
    extras['view'] = V(0, -math.sin(sdf.TILT), -math.cos(sdf.TILT)) @ rot_y(-th)
    R = render()
    out, depth = R.render(groups, extras, angle)
    img = finish(out, depth, R.palarr, OUTLINE)
    seed = 100 + 7 * frame + {'fly': 0, 'charge': 40, 'pain': 80}[kind] + angle * 3
    a, oy, ax = compose(img, flow(angle, kind, frame), seed)
    return place(a, oy, ax, name)


# ----------------------------------------------------------------------------- muerte (F-K, de frente)
DEATH_LIFT = 40                          # px: los trozos caen por debajo del origen
DEATH = {
    'F': dict(pose=dict(jaw=34.0, pitch=-18.0, roll=6.0, hot=1, glow=1.4, crack=1.0)),
    'G': dict(pose=dict(jaw=34.0, pitch=-18.0, roll=6.0, hot=1, glow=1.4, crack=1.0, t=0.12)),
    'H': dict(pose=dict(jaw=34.0, pitch=-18.0, roll=6.0, hot=0, glow=1.3, crack=1.0, t=0.32)),
    'I': dict(pose=dict(jaw=34.0, pitch=-18.0, roll=6.0, eyes=False, glow=1.2, crack=1.0, t=0.55, char=0.3)),
    'J': dict(pose=dict(jaw=34.0, pitch=-18.0, roll=6.0, eyes=False, glow=1.0, crack=1.0, t=0.78, char=0.75)),
    'K': dict(pose=dict(jaw=34.0, pitch=-18.0, roll=6.0, eyes=False, glow=0.8, crack=1.0, t=1.0, char=1.0)),
}


def ring_heat(X, Y, rc, w, peak, fill, holes, seed):
    r = np.hypot(X, Y)
    th = np.arctan2(Y, X)
    nang = fbm2(np.cos(th) * 3.0, np.sin(th) * 3.0, 1.0, seed)
    rr = rc * (0.72 + 0.56 * nang) * (1 + 0.15 * np.clip(Y / max(rc, 1), 0, 1))
    h = peak * np.exp(-((r - rr) / w) ** 2)
    h = np.maximum(h, fill * peak * np.clip(1 - r / rr, 0, 1) * 1.15)
    h *= 0.5 + 0.95 * fbm2(X, Y, 0.4, seed + 3)
    h -= holes * (fbm2(X, Y, 0.22, seed + 7) > 0.57)
    return h


BURST = {   # (radio, ancho, pico, relleno, agujeros) del fuego; (radio, densidad) del humo
    'F': ((10.0, 6.0, 1.15, 1.0, 0.0), None),
    'G': ((13.0, 7.0, 1.2, 1.0, 0.0), None),
    'H': ((16.0, 6.0, 1.0, 0.55, 0.2), None),
    'I': ((20.0, 5.0, 0.72, 0.15, 0.45), (16.0, 0.35)),
    'J': ((22.0, 3.0, 0.4, 0.0, 0.0), (20.0, 0.7)),
    'K': ((24.0, 2.0, 0.0, 0.0, 1.0), (23.0, 0.5)),
}


def draw_death(name, fr):
    d = DEATH[fr]
    groups, extras = build(d['pose'], lift=DEATH_LIFT)
    extras['view'] = V(0, -math.sin(sdf.TILT), -math.cos(sdf.TILT))
    R = render()
    out, depth = R.render(groups, extras, 1)
    img = np.array(finish(out, depth, R.palarr, OUTLINE))
    H, W = img.shape[:2]
    # Lienzo fijo: eje en ax, origen en oy; el trazado se coloca con su eje y su origen encima.
    Ww, Hh = 96, 112
    ax, oy = Ww // 2, 64
    big = np.zeros((Hh, Ww, 4), np.uint8)
    roy = H - 1 - (Y0S + DEATH_LIFT)
    x0, y0 = ax - W // 2, oy - roy
    sx0, sy0 = max(0, -x0), max(0, -y0)
    ex, ey = min(W, Ww - x0), min(H, Hh - y0)
    big[y0 + sy0:y0 + ey, x0 + sx0:x0 + ex] = img[sy0:ey, sx0:ex]
    mask = big[:, :, 3] >= 128
    cx, cy = ax, oy - SC_Y * math.cos(sdf.TILT) + 0.5
    sub = 3
    jj, ii = np.meshgrid(np.arange(Ww * sub), np.arange(Hh * sub))
    X = (jj + 0.5) / sub - cx
    Y = cy - (ii + 0.5) / sub
    fire_p, smoke_p = BURST[fr]
    seed = 300 + ord(fr)
    heat = ring_heat(X, Y, *fire_p, seed)
    if fr in 'JK':                                    # ya solo quedan brasas sueltas
        heat = np.where(fbm2(X, Y, 0.45, seed + 21) > 0.64, heat, 0)
    if fr == 'F':                                     # la calavera aún entera: llamas que se disparan
        fl = dict(up=0.8, side=0.0, rad=1.0, len=20.0, wig=2.2, rim=1.4)
        fh = flame_layer(mask, cx, cy, fl, seed)
        heat = np.maximum(heat.reshape(Hh, sub, Ww, sub).mean(axis=(1, 3)), fh)
    else:
        on = heat > 0.05
        cnt = on.reshape(Hh, sub, Ww, sub).sum(axis=(1, 3))
        hs = np.where(on, heat, 0).reshape(Hh, sub, Ww, sub).sum(axis=(1, 3))
        heat = np.where(cnt >= 4, hs / np.maximum(cnt, 1), 0.0)
    pal = R.palarr
    res = np.zeros((Hh, Ww, 4), np.uint8)
    if smoke_p is not None:
        rs, dens = smoke_p
        Xp, Yp = X[::sub, ::sub] + 0.5, Y[::sub, ::sub] - 0.5
        r = np.hypot(Xp, Yp * 0.9 - 2.0)
        sm = np.clip(1 - r / rs, 0, 1) ** 0.6 * (fbm2(Xp, Yp, 0.18, seed + 11) * 1.3) - (1 - dens) * 0.6
        sm = np.where(fbm2(Xp, Yp, 0.3, seed + 12) > 0.62 - 0.2 * dens, sm, sm * 0.3)
        n = len(SMOKE_RAMP)
        smk = sm > 0.12
        lv = np.clip(np.floor(sm * n * 1.2), 0, n - 1).astype(int)
        res[smk, :3] = pal[np.array(SMOKE_RAMP)[lv[smk]]].astype(np.uint8)
        res[smk, 3] = 255
    ramp = FIRE if fr in 'FGHI' else EMBER
    n = len(ramp)
    fire = heat > 0.06
    lv = np.clip(np.floor(heat * n), 0, n - 1).astype(int)
    res[fire, :3] = pal[np.array(ramp)[lv[fire]]].astype(np.uint8)
    res[fire, 3] = 255
    res[mask] = big[mask]
    # Chispas y brasas sueltas encima.
    nsp = {'F': 6, 'G': 10, 'H': 12, 'I': 10, 'J': 7, 'K': 4}[fr]
    rr = {'F': (10, 18), 'G': (14, 22), 'H': (18, 26), 'I': (21, 29), 'J': (24, 31), 'K': (26, 33)}[fr]
    rng = np.random.default_rng(seed + 5)
    for _ in range(nsp):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(*rr)
        px, py = int(cx + math.cos(a) * r), int(cy - math.sin(a) * r * 0.9)
        if 0 <= px < Ww and 0 <= py < Hh and not mask[py, px]:
            res[py, px, :3] = pal[ramp[min(n - 1, int(n * (0.75 if fr in 'FGH' else 0.5)))]]
            res[py, px, 3] = 255
    return place(res, oy, ax, name)


def lumps():
    out = {}
    for fi, fr in enumerate('AB'):
        for a in range(1, 9):
            out[f'SKUL{fr}{a}'] = ((f'SKUL{fr}{a}', 'fly', fi), a)
    for fi, fr in enumerate('CD'):
        for a in range(1, 9):
            out[f'SKUL{fr}{a}'] = ((f'SKUL{fr}{a}', 'charge', fi), a)
    for a in range(1, 9):
        out[f'SKULE{a}'] = (('SKULE' + str(a), 'pain', 0), a)
    for fr in 'FGHIJK':
        out[f'SKUL{fr}0'] = ((f'SKUL{fr}0', 'death', fr), 1)
    return out


def draw(item, angle):
    name, kind, fi = item
    if kind == 'fly':
        return draw_rot(name, FLY[fi], angle, kind, fi)
    if kind == 'charge':
        return draw_rot(name, CHARGE[fi], angle, kind, fi)
    if kind == 'pain':
        return draw_rot(name, PAIN, angle, kind, 0)
    if kind == 'death':
        return draw_death(name, fi)
    raise ValueError(kind)


def main():
    rows = sprite_rows('SKUL', 'ABCDE', 'FGHIJK')
    cli(lumps, draw, rows)
    out = sys.argv[sys.argv.index('--salida') + 1]
    save_offsets(out, OFFSETS)


if __name__ == '__main__':
    main()
