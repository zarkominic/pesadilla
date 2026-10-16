#!/usr/bin/env python3
"""toro.py — dibuja POR CÓDIGO al TORO NEGRO (sustituye al demonio SARG de Freedoom; el espectro usa
los mismos sprites y el motor lo pinta como sombra borrosa).

Toro bravo de pesadilla a cuatro patas: pelaje negro con brillos grises, morrillo enorme, cuernos
enormes de hueso claro, ojos rojos que brillan, hocico húmedo con babas colgando y tres banderillas
clavadas en el lomo con cintas raídas (rojo y amarillo) y regueros de sangre.

Mismo motor y estilo que el Penitente (tools/arte/sdf.py): modelo 3D de primitivas SDF con poses
paramétricas, trazado ortográfico a 4 submuestras, rampas exactas de PLAYPAL y contorno de 1 px.

Fotogramas (info.c, SPR_SARG):
    A-D  andar / embestir (A y B también en reposo) ... 8 ángulos
    E    escarbar y bajar la cabeza (preparar)          8 ángulos
    F    arrancada con los cuernos por delante          8 ángulos
    G    derrote: cabeceo hacia arriba (aquí hace daño) 8 ángulos
    H    dolor                                          8 ángulos
    I-N  muerte: se desploma de lado (N = cadáver)      de frente (ángulo 0)

Apoyo en el suelo: construir_pwad.py copia el punto de apoyo del sprite de Freedoom con el mismo nombre
(o pies 4 px bajo el origen si no existe, p. ej. SARGA2 frente al SARGA2A8 reflejado de Freedoom).
Como Freedoom no es regular (3-7 px según el sprite), cada PNG se recorta o rellena por abajo para que
el suelo del modelo caiga SIEMPRE en el mismo sitio respecto al origen: así las pezuñas no saltan
entre fotogramas ni entre ángulos (ver fit_bottom). El eje del cuerpo queda en el centro del ancho.

Uso (determinista, regenera los 70 PNG SARG*):
    ~/.venvs/pesadilla/bin/python tools/arte/toro.py --salida arte/sprites
    … --solo SARGA1,SARGE3      solo esos lumps
    … --hoja hoja.png           además, hoja de contactos ampliada x3 con etiquetas
"""
import math
import os
import struct
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdf  # noqa: E402
from sdf import (V, nrm, rot_x, rot_y, rot_z, rad, basis, Frame, _len,  # noqa: E402
                 Sphere, Ellipsoid, RoundCone, CappedCone, Group, vnoise,
                 Render, finish, trim, ik, apply_shine, cli, sprite_rows)
from doomgfx import read_wad  # noqa: E402

# ----------------------------------------------------------------------------- materiales
(FUR, HORN, HOOF, EYE, SOCKET, MOUTH, NOSE, BABA, BLOOD, WOUND, STICK, RIB_R, RIB_Y, MUD,
 DEADEYE, LEG, PAPER) = range(17)
RAMPS = {
    FUR: [7, 6, 5, 111, 110, 108, 105, 102],      # negro con brillos grises
    LEG: [7, 6, 5, 111, 110, 108, 105, 102],      # igual, en las patas (para el barro)
    HORN: [141, 138, 135, 132, 130, 128, 86],     # hueso claro
    HOOF: [0, 7, 6, 5, 110, 107],                 # pezuña negra
    EYE: [180, 176, 173],                         # rojo que brilla (borde, iris, núcleo)
    SOCKET: [0],
    DEADEYE: [0, 7],
    MOUTH: [46, 44, 42, 40, 37, 34],              # boca: rojo oscuro
    NOSE: [7, 6, 5, 110, 108, 105, 101, 96],      # hocico húmedo
    BABA: [101, 97, 93, 89, 85, 82],              # babas
    BLOOD: [191, 189, 187, 185, 182, 179],
    WOUND: [45, 40, 35, 30, 26],
    STICK: [150, 148, 146, 144],                  # palo de la banderilla
    RIB_R: [45, 42, 39, 36, 33, 30],              # papel rojo desteñido
    RIB_Y: [167, 166, 165, 164, 163, 162],        # papel amarillo sucio
    PAPER: [97, 93, 90, 87, 84],                  # papel blanco sucio del palo
    MUD: [7, 2, 239, 238, 237, 236],              # barro en las patas
}
EMISSIVE = (EYE,)
OUTLINE = 2      # (23,15,7): casi negro cálido

# ----------------------------------------------------------------------------- apoyo en el suelo
LIFT_PX = 6                                      # el modelo se sube 6 px para que nada se corte por abajo
LIFT = LIFT_PX / math.cos(sdf.TILT)
FLOOR_ROWS = LIFT_PX + 1                         # filas por debajo de la línea del suelo en el render
SINK = -1                                        # suelo del modelo respecto al origen (px; <0 = por encima)
_GEO = None


def feet_below(name):
    """Filas por debajo del origen que dará construir_pwad.py a este lump (mismo cálculo)."""
    global _GEO
    if _GEO is None:
        _GEO = {}
        inside = False
        for n, d in read_wad(sdf.IWAD)[1]:
            if n in ('S_START', 'SS_START'):
                inside = True
            elif n in ('S_END', 'SS_END'):
                inside = False
            elif inside and len(d) >= 8:
                _GEO[n] = struct.unpack('<hhhh', d[:8])
    if name in _GEO:
        _, ih, _, it = _GEO[name]
        return ih - it
    return 4


def fit_bottom(img, name):
    """Recorta o rellena por abajo para que el suelo quede a SINK px del origen en todos los lumps."""
    a = np.array(img)
    a[a[:, :, 3] < 128] = 0
    h, w = a.shape[:2]
    want = feet_below(name) - SINK
    if want < FLOOR_ROWS:
        cut = a[h - (FLOOR_ROWS - want):]
        if (cut[:, :, 3] >= 128).any():
            print(f'AVISO {name}: se recortan píxeles bajo el suelo', file=sys.stderr)
        a = a[:h - (FLOOR_ROWS - want)]
    elif want > FLOOR_ROWS:
        a = np.concatenate([a, np.zeros((want - FLOOR_ROWS, w, 4), np.uint8)])
    h = a.shape[0]
    for x in (0, w - 1):
        if a[h - 1, x, 3] == 0:
            a[h - 1, x] = (0, 0, 0, 1)
    return Image.fromarray(a, 'RGBA')


# ----------------------------------------------------------------------------- materiales por punto
def materiales(P, mat, inten, nz, nr, spec, lvl_extra, extras):
    """Pelo con vetas, brillo gris en lo alto, barro, babas brillantes, ojos, ollares y sangre."""
    m = np.isin(mat, (FUR, LEG))
    hair = vnoise(P * np.array([2.2, 0.9, 0.55]), 1.0, 11)          # vetas alargadas (pelo)
    inten[m] *= 0.76 + 0.30 * hair[m]
    top = np.clip(nr[:, 1] - 0.3, 0, 1)                                # brillo gris en lomo y morrillo
    inten[m] += 0.28 * top[m]
    # Rizos del testuz: manchas más claras.
    tc = extras.get('testuz')
    if tc is not None:
        c, r = tc
        dt = _len(P - c)
        mm = m & (dt < r)
        inten[mm] *= 0.8 + 0.6 * (vnoise(P[mm], 1.9, 21) > 0.5)
    # Barro en las patas.
    mud = (mat == LEG) & (P[:, 1] - extras.get('floor', 0.0) < 4.5 + 3.0 * vnoise(P, 0.7, 5)) \
        & (vnoise(P, 1.6, 6) > 0.42)
    mat[mud] = MUD
    mat[mat == LEG] = FUR
    m = mat == HORN
    # Cuernos: anillos de crecimiento y suciedad cerca de la base.
    for c, ax in extras.get('horn_rings', []):
        mm = m & (_len(P - c) < 9.0)
        along = (P[mm] - c) @ ax
        inten[mm] *= 0.82 + 0.18 * np.clip(along / 6.0, 0, 1) + 0.06 * np.sin(along * 3.1)
    apply_shine(mat, inten, spec, ((FUR, 0.45, 6), (HORN, 0.35, 6), (NOSE, 1.0, 9), (BABA, 1.0, 6),
                                   (BLOOD, 0.6, 12), (HOOF, 0.4, 7), (MOUTH, 0.5, 8)))
    # Ollares: dos agujeros en el hocico.
    for c in extras.get('nostrils', []):
        mm = (mat == NOSE) & (_len(P - c) < 0.85)
        mat[mm] = SOCKET
    # Ojos: núcleo más claro.
    for c, r in extras.get('eyes', []):
        de = _len(P - c)
        mm = (mat == EYE) & (de < r * 1.6)
        lvl_extra[mm] = np.where(de[mm] < r * 0.62, 2, 1)
        rim = (mat == EYE) & (de >= r * 1.6)
        lvl_extra[rim] = 0
    # Regueros de sangre sobre el pelo.
    for sc, sr in extras.get('stains', []):
        ds = _len(P - sc)
        mm = np.isin(mat, (FUR, MUD)) & (ds < sr * (0.75 + 0.5 * nz))
        mat[mm] = BLOOD


RENDER = None


def render():
    global RENDER
    if RENDER is None:
        RENDER = Render(RAMPS, hook=materiales, level_mats=(EYE,), emissive=EMISSIVE,
                        no_light=(EYE, SOCKET))
    return RENDER


# ----------------------------------------------------------------------------- modelo
BODY_Y = 27.0                       # centro del cuerpo sobre el suelo
NECK_PIVOT = (0.0, 6.0, 15.0)       # giro de la cabeza (en el marco del cuerpo)
POLL = (0.0, 3.5, 7.0)              # testuz respecto al giro
FRONT_Z, HIND_Z, LEG_X = 11.0, -12.0, 5.8
HOOF_Y = 1.15                       # centro de la pezuña sobre el suelo

# Cuerno izquierdo (x+) en el marco de la cabeza: puntos y radios.
HORN_PTS = [(3.6, -0.2, 0.2), (7.9, 0.5, 0.5), (11.6, 2.6, 0.7), (13.9, 6.2, 1.2),
            (14.6, 10.2, 2.2), (13.6, 13.8, 3.6), (11.6, 16.4, 5.0)]
HORN_R = [2.4, 2.05, 1.7, 1.35, 1.0, 0.7, 0.32]

# Banderillas: (punto de partida dentro del morrillo, dirección de salida, color, lado del reguero).
BANDERILLAS = [
    ((2.4, 12.0, 9.0), (0.62, 0.62, -0.48), RIB_R, 1),
    ((-2.6, 12.0, 12.0), (-0.70, 0.60, -0.38), RIB_Y, -1),
    ((1.0, 11.0, 4.0), (0.36, 0.62, -0.70), RIB_Y, 1),
]
BAND_LEN = 10.5

DEFAULT = dict(
    root=None, shift=(0.0, 0.0), bob=0.0, surge=0.0, pitch=0.0, roll=0.0, yaw=0.0,
    hpitch=14.0, hyaw=0.0, hroll=0.0, jaw=3.0,
    LF=('ground', (LEG_X, FRONT_Z), 0.0), RF=('ground', (-LEG_X, FRONT_Z), 0.0),
    LH=('ground', (LEG_X, HIND_Z), 0.0), RH=('ground', (-LEG_X, HIND_Z), 0.0),
    tail_up=0.0, tail_sway=0.0, sway=0.0, drool=((0.0, -8.0, -0.6), (0.0, -6.5, -0.4)),
    eyes='on', eye_r=1.05, stains=(), spray=(), pool=None, extra=(),
)


def _project(group, q, iters=5):
    """Lleva el punto q a la superficie del grupo (unos pasos de Newton sobre la distancia)."""
    q = V(q)
    for _ in range(iters):
        d = group.eval(q[None])[0][0]
        g = np.zeros(3)
        for k in range(3):
            e = np.zeros(3)
            e[k] = 0.05
            g[k] = group.eval((q + e)[None])[0][0] - group.eval((q - e)[None])[0][0]
        g = nrm(g) if np.linalg.norm(g) > 1e-9 else V(0, 1, 0)
        q = q - g * d
    return q


def _surface_exit(group, a, dirv, hi=20.0):
    """Primer punto de salida desde a (dentro) en la dirección dirv."""
    lo = 0.0
    for _ in range(30):
        mid = (lo + hi) / 2
        if group.eval((a + dirv * mid)[None])[0][0] < 0:
            lo = mid
        else:
            hi = mid
    return a + dirv * lo


def leg(B, root, side, front, spec, upper, lower):
    """Una pata. spec: ('ground', (x, z), alzada[, flexión]) con la pezuña en el suelo del modelo,
    ('body', (x, y, z)) con la pezuña en el marco del cuerpo, o ('kneel', (x, z)) rodilla en el suelo."""
    fwd_r = root.d((0, 0, 1))
    up_r = root.d((0, 1, 0))
    if front:
        S = B.p((side * LEG_X, -3.0, 10.5))
    else:
        S = B.p((side * LEG_X, 1.0, -13.0))
    kind = spec[0]
    if kind == 'kneel':
        x, z = spec[1]
        K = root.p((x, 1.6, z))
        F = root.p((x, 1.5, z - 7.5))
        T = root.p((x, 1.3, z - 9.8))
        hoof_f, hoof_u = nrm(root.d((0, -0.5, -1))), up_r
        mid = K
    else:
        if kind == 'ground':
            x, z = spec[1]
            lift = spec[2]
            flex = spec[3] if len(spec) > 3 else (55.0 if front else 35.0) * min(1.0, lift / 3.0)
            T = root.p((x, HOOF_Y + lift, z))
            frame_up, frame_fwd = up_r, fwd_r
        else:  # 'body'
            T = B.p(spec[1])
            flex = spec[2] if len(spec) > 2 else 20.0
            frame_up, frame_fwd = B.d((0, 1, 0)), B.d((0, 0, 1))
        side_ax = np.cross(frame_up, frame_fwd)
        Rf = sdf.rot_axis(side_ax, rad(flex))
        hoof_f, hoof_u = Rf @ frame_fwd, Rf @ frame_up
        F = T + hoof_u * 2.5 - hoof_f * 0.35
        if front:
            mid = ik(S, F, 11.0, 9.6, frame_fwd)
        else:
            Hk = F + (Rf @ (frame_up * 8.6 - frame_fwd * 1.6))
            mid = ik(S, Hk, 10.6, 9.0, frame_fwd)
    hoof = [Ellipsoid(T + hoof_f * 0.75, (2.1, 1.15, 2.45), basis(hoof_f, hoof_u), HOOF)]
    if front:
        upper += [RoundCone(S, mid, 4.3, 2.5, FUR)]
        lower += [Sphere(mid, 2.15, LEG), RoundCone(mid, F, 2.0, 1.55, LEG), Sphere(F, 1.8, LEG),
                  RoundCone(F, T + hoof_u * 0.5, 1.55, 1.5, LEG)] + hoof
    else:
        if kind == 'kneel':
            Hk = mid
        upper += [RoundCone(S, mid, 5.4, 3.4, FUR)]
        lower += [RoundCone(mid, Hk, 3.3, 1.9, LEG), Sphere(Hk, 2.0, LEG), RoundCone(Hk, F, 1.8, 1.5, LEG),
                  Sphere(F, 1.75, LEG), RoundCone(F, T + hoof_u * 0.5, 1.5, 1.45, LEG)] + hoof


def build(pose):
    p = dict(DEFAULT)
    p.update(pose)
    root = Frame((p['shift'][0], LIFT, p['shift'][1]), rot_y(rad(p['yaw']))) * (p['root'] or Frame())
    extras = {'eyes': [], 'stains': [], 'nostrils': [], 'horn_rings': [], 'floor': LIFT}
    B = root * Frame((0, BODY_Y + p['bob'], p['surge']), rot_x(rad(p['pitch'])) @ rot_z(rad(p['roll'])))
    N = B * Frame(NECK_PIVOT, rot_y(rad(p['hyaw'])) @ rot_x(rad(p['hpitch'])) @ rot_z(rad(p['hroll'])))
    Hd = N * Frame(POLL)
    groups = []

    # --- cuerpo: pecho, barril, grupa, morrillo, papada, cuello, cabeza (unión suave)
    M = B.M()
    body = [
        Ellipsoid(B.p((0, 0.5, 8.0)), (9.0, 10.5, 10.0), M, FUR),                 # pecho
        Ellipsoid(B.p((0, -0.5, -3.0)), (8.6, 9.0, 14.5), M, FUR),                # barril
        Ellipsoid(B.p((0, 2.2, -14.0)), (8.0, 8.4, 8.0), M, FUR),                 # grupa
        Ellipsoid(B.p((0, 10.5, 10.0)), (7.8, 8.2, 9.8), M @ rot_x(rad(-12)), FUR),  # morrillo
        Ellipsoid(B.p((0, -8.0, 15.5)), (2.6, 5.5, 4.5), M, FUR),                 # papada
        RoundCone(B.p((0, 4.5, 13.0)), Hd.p((0, -4.0, -1.5)), 7.6, 5.2, FUR),     # cuello
    ]
    H = Hd.M()
    head = [
        Ellipsoid(Hd.p((0, -2.2, 1.0)), (5.0, 4.0, 4.0), H, FUR),                 # cráneo
        RoundCone(Hd.p((0, -2.8, 1.8)), Hd.p((0, -10.4, 6.2)), 4.5, 3.5, FUR),    # cara
        Ellipsoid(Hd.p((0, -11.5, 6.9)), (3.9, 2.6, 2.9), H @ rot_x(rad(-30)), NOSE),  # hocico
        Ellipsoid(Hd.p((0, -0.8, 2.6)), (3.8, 2.6, 1.8), H @ rot_x(rad(25)), FUR),  # testuz rizado
    ]
    for sx in (-1, 1):
        head += [Ellipsoid(Hd.p((5.8 * sx, -2.4, -0.8)), (2.7, 1.1, 1.6), H @ rot_z(rad(-25 * sx)), FUR),  # oreja
                 Ellipsoid(Hd.p((4.1 * sx, -3.3, 2.7)), (1.7, 0.9, 1.5), H @ rot_z(rad(18 * sx)), FUR)]   # ceja
    # Mandíbula (gira en la bisagra) y boca por dentro.
    J = Hd * Frame((0, -6.0, 0.6), rot_x(rad(p['jaw'])))
    head += [RoundCone(J.p((0, 0, 0)), J.p((0, -6.4, 4.4)), 2.7, 2.1, FUR)]
    if p['jaw'] > 6:
        Jm = Hd * Frame((0, -6.0, 0.6), rot_x(rad(p['jaw'] * 0.5)))
        head += [Ellipsoid(Jm.p((0, -4.2, 3.3)), (2.3, 0.9 + 0.035 * p['jaw'], 3.4), Jm.M() @ rot_x(rad(-35)), MOUTH)]
    extras['testuz'] = (Hd.p((0, -0.8, 2.8)), 3.4)
    for sx in (-1, 1):
        extras['nostrils'].append(Hd.p((1.55 * sx, -12.4, 9.2)))

    # --- patas (lo alto, grueso, va con el cuerpo para que se funda; lo bajo, aparte)
    upper, lower = [], []
    for key, side, front in (('LF', 1, True), ('RF', -1, True), ('LH', 1, False), ('RH', -1, False)):
        leg(B, root, side, front, p[key], upper, lower)
    groups.append(Group(body + head + upper, k=2.2, name='body'))
    bodyg = groups[-1]
    groups.append(Group(lower, k=0.9, name='legs'))

    # --- cuernos
    horns = []
    for sx in (-1, 1):
        pts = [Hd.p((x * sx, y, z)) for x, y, z in HORN_PTS]
        for i in range(len(pts) - 1):
            horns.append(RoundCone(pts[i], pts[i + 1], HORN_R[i], HORN_R[i + 1], HORN))
        extras['horn_rings'].append((pts[0], nrm(pts[2] - pts[0])))
    groups.append(Group(horns, k=0.5, name='horns'))

    # --- ojos (brillan) en la superficie de la cara
    if p['eyes'] != 'none':
        eyes = []
        for sx in (-1, 1):
            a = Hd.p((2.0 * sx, -4.4, 2.0))
            dv = Hd.d(nrm((0.85 * sx, 0.05, 0.55)))
            c = _surface_exit(bodyg, a, dv)
            r = p['eye_r']
            if p['eyes'] == 'dead':
                eyes.append(Sphere(c - dv * 0.3, r * 0.9, DEADEYE))
            else:
                eyes += [Sphere(c - dv * 0.2, r * 1.25, SOCKET), Sphere(c + dv * 0.1, r, EYE)]
                extras['eyes'].append((c + dv * 0.1, r))
        groups.append(Group(eyes, name='eyes'))

    # --- babas colgando de las comisuras (caen en vertical del mundo)
    drool = []
    for sx, dv in zip((-1, 1), p['drool']):
        if dv is None:
            continue
        s0 = Hd.p((2.7 * sx, -11.6, 5.4))
        e = s0 + V(dv)
        mid = (s0 + e) / 2 + V(0.25 * sx, 0.6, 0)
        drool += [RoundCone(s0, mid, 0.62, 0.52, BABA), RoundCone(mid, e, 0.52, 0.45, BABA), Sphere(e, 0.8, BABA)]
    if drool:
        groups.append(Group(drool, k=0.3, name='drool'))

    # --- banderillas con cintas y regueros de sangre
    band = []
    sw = p['sway']
    for start, dirv, col, rside in BANDERILLAS:
        a = B.p(start)
        d = B.d(nrm(dirv))
        entry = _surface_exit(bodyg, a, d)
        top = entry + d * BAND_LEN
        other = RIB_Y if col == RIB_R else RIB_R
        seg = 5                                                     # palo forrado: blanco con anillas de color
        for i in range(seg):
            p0 = entry - d * 1.0 + d * ((BAND_LEN + 1.0) * i / seg)
            p1 = entry - d * 1.0 + d * ((BAND_LEN + 1.0) * (i + 1) / seg)
            band.append(RoundCone(p0, p1, 0.55, 0.55, PAPER if i % 2 == 0 else col))
        band.append(CappedCone(top - d * 0.4, top + d * 1.0, 0.5, 1.4, col))            # rosetón de papel
        for k, (ox, mat) in enumerate(((0.7, col), (-0.7, other))):
            q0 = top + B.d((ox, 0, 0))
            q1 = q0 + V(0.6 * sw + 0.6 * ox, -2.6, -1.3)
            q2 = q1 + V(0.9 * sw + 0.4 * ox, -2.6, -0.7 - 0.4 * k)
            q3 = q2 + V(1.1 * sw, -2.2, -0.2)
            band += [RoundCone(q0, q1, 0.48, 0.45, mat), RoundCone(q1, q2, 0.45, 0.42, mat),
                     RoundCone(q2, q3, 0.42, 0.32, mat)]
        # Reguero: de la herida hacia abajo por el costado.
        ex = B.d((rside * 4.5, -9.0, -1.0))
        n = 6
        for i in range(n):
            t = i / (n - 1)
            q = _project(bodyg, entry + ex * t + B.d((0, 0, 0.4 * math.sin(5 * t))))
            extras['stains'].append((q, 1.15 - 0.55 * t))
        extras['stains'].append((entry, 1.5))
    groups.append(Group(band, k=0.15, name='banderillas'))

    # --- rabo
    tb = B.p((0, 8.0, -21.0))
    tu = p['tail_up']
    ts = p['tail_sway']
    t1 = tb + B.d((0, 1.2 + 1.5 * tu, -2.2))
    hang = V(0.8 * ts, -6.5, -1.2)
    lift = B.d((0.5 * ts, 1.5, -6.5))
    t2 = t1 + hang * (1 - tu) + lift * tu
    t3 = t2 + V(1.3 * ts, -6.0 * (1 - tu) - 1.5 * tu, 0.3 - 5.0 * tu)
    t4 = t3 + V(1.5 * ts, -4.5 * (1 - tu) - 3.5 * tu, 0.4 - 2.5 * tu)
    tail = [RoundCone(tb, t1, 1.8, 1.2, FUR), RoundCone(t1, t2, 1.15, 0.9, FUR), RoundCone(t2, t3, 0.9, 0.75, FUR),
            RoundCone(t3, t4, 0.75, 0.7, FUR), Ellipsoid(t4 + nrm(t4 - t3) * 1.6, (1.5, 1.5, 1.5), None, FUR),
            Ellipsoid(t4 + nrm(t4 - t3) * 2.6, (1.2, 1.2, 1.2), None, FUR)]
    groups.append(Group(tail, k=0.9, name='tail'))

    # --- sangre extra (manchas, gotas, charco)
    def where(fr, pt):
        return B.p(pt) if fr == 'body' else Hd.p(pt) if fr == 'head' else root.p(pt)

    extras['stains'] += [(where(fr, pt), r) for fr, pt, r in p['stains']]
    if p['spray']:
        groups.append(Group([Sphere(where(fr, pt), r, BLOOD) for fr, pt, r in p['spray']], name='spray'))
    if p['pool'] is not None:
        c, rr, ang = p['pool']
        groups.append(Group([Ellipsoid(root.p(c), rr, rot_y(rad(ang)), BLOOD)], name='pool'))
    for g in p['extra']:
        groups.append(g)
    floor = root.p((0, 0, 0))[1]
    for g in groups:                       # nada atraviesa el suelo (un cuerno queda «clavado»)
        g.cut = lambda P, fy=floor: fy - P[:, 1]
    ax = root.p((0, 0, 0))
    extras['axis'] = (ax[0], ax[2])
    return groups, extras


# ----------------------------------------------------------------------------- poses
def walk(i):
    """Trote pesado: pares diagonales (LF+RH, RF+LH), cabeza baja con los cuernos por delante."""
    a = i * math.pi / 2
    c, s = math.cos(a), math.sin(a)
    Af, Ah, Lf, Lh = 4.6, 4.2, 3.4, 2.8
    return dict(
        bob=0.4 - 1.1 * abs(c), pitch=1.2 * c, roll=1.4 * s, hpitch=16 + 4 * abs(c), hyaw=3 * s, hroll=-2 * s,
        LF=('ground', (LEG_X, FRONT_Z + Af * c), Lf * max(0, -s)),
        RH=('ground', (-LEG_X, HIND_Z + Ah * c), Lh * max(0, -s)),
        RF=('ground', (-LEG_X, FRONT_Z - Af * c), Lf * max(0, s)),
        LH=('ground', (LEG_X, HIND_Z - Ah * c), Lh * max(0, s)),
        tail_sway=2.2 * s, tail_up=0.15, sway=1.0 * s,
        drool=((-0.9 * s, -8.0, -0.9 - 0.5 * abs(c)), (-0.7 * s, -6.5, -0.7 - 0.4 * abs(c))),
    )


PAW = dict(   # E: escarba con la pata y baja la cabeza
    bob=-0.8, pitch=5, roll=-2, hpitch=34, hyaw=-6, hroll=-4, jaw=4,
    LF=('ground', (LEG_X, FRONT_Z - 4.5), 2.6, 70.0), RF=('ground', (-LEG_X, FRONT_Z + 2.0), 0.0),
    LH=('ground', (LEG_X, HIND_Z - 1.5), 0.0), RH=('ground', (-LEG_X, HIND_Z + 0.5), 0.0),
    tail_up=0.7, tail_sway=1.5, sway=-0.6,
    drool=((0.8, -5.8, -0.4), (0.4, -4.8, -0.2)),
)
CHARGE = dict(  # F: arrancada, cuernos por delante
    bob=-1.8, surge=3.5, pitch=7, hpitch=46, jaw=10,
    LF=('ground', (LEG_X, FRONT_Z + 6.0), 0.0), RF=('ground', (-LEG_X, FRONT_Z + 3.5), 1.4),
    LH=('ground', (LEG_X, HIND_Z - 4.0), 0.0), RH=('ground', (-LEG_X, HIND_Z - 2.0), 0.0),
    tail_up=1.0, tail_sway=-1.0, sway=-1.4,
    drool=((0.0, -2.0, -4.5), (0.0, -1.8, -4.0)),
)
HOOK = dict(  # G: derrote hacia arriba, boca abierta (aquí hace daño)
    bob=0.8, surge=2.0, pitch=-7, roll=3, hpitch=-22, hyaw=18, hroll=24, jaw=32,
    LF=('ground', (LEG_X, FRONT_Z + 5.0), 4.5), RF=('ground', (-LEG_X, FRONT_Z + 3.0), 0.0),
    LH=('ground', (LEG_X, HIND_Z - 1.0), 0.0), RH=('ground', (-LEG_X, HIND_Z - 0.5), 0.0),
    tail_up=0.8, tail_sway=2.0, sway=1.6,
    drool=((-3.5, 1.5, -2.5), (-4.0, 0.5, -1.5)),
)
PAIN = dict(  # H: dolor, respingo con la cabeza arriba
    bob=0.6, surge=-1.5, pitch=-6, roll=-5, hpitch=-18, hyaw=-24, hroll=-14, jaw=26,
    LF=('ground', (LEG_X, FRONT_Z), 0.0), RF=('ground', (-LEG_X, FRONT_Z + 1.0), 1.8),
    LH=('ground', (LEG_X, HIND_Z), 0.0), RH=('ground', (-LEG_X, HIND_Z - 0.5), 0.0),
    tail_up=0.4, tail_sway=-2.0, sway=-1.2, eye_r=1.3,
    drool=((2.5, -3.5, -1.5), (2.0, -3.0, -1.0)),
)


def deaths():
    """I-N: recibe el golpe, dobla las manos, se vence sobre el costado izquierdo y queda tendido
    con la barriga y las patas hacia el que mira y un cuerno al aire."""
    chest = [('body', (1.5, 3.0, 17.0), 3.2), ('body', (-2.0, -1.0, 17.5), 2.4), ('body', (0.5, -5.0, 16.5), 2.0)]
    I = dict(yaw=12, bob=1.0, pitch=-12, roll=-4, hpitch=-36, hyaw=-10, hroll=-12, jaw=38,
             LF=('ground', (LEG_X + 1.5, FRONT_Z + 2.0), 0.0), RF=('ground', (-LEG_X - 1.0, FRONT_Z - 1.5), 0.0),
             LH=('ground', (LEG_X, HIND_Z), 0.0), RH=('ground', (-LEG_X, HIND_Z), 0.0),
             tail_up=0.6, tail_sway=1.0, eye_r=1.3, stains=chest,
             spray=[('body', (1.0, 4.0, 20.5), 1.4), ('body', (2.5, 6.5, 23.0), 1.1), ('body', (-1.0, 8.0, 25.0), 0.9),
                    ('body', (3.5, 9.5, 26.5), 0.7), ('body', (0.0, 2.0, 22.5), 1.0)],
             drool=((1.5, -3.0, -2.0), (1.0, -2.5, -1.5)))
    J = dict(yaw=14, bob=-7.0, pitch=15, roll=-5, hpitch=30, hyaw=-6, hroll=-8, jaw=20,
             LF=('kneel', (LEG_X + 0.5, FRONT_Z + 3.0)), RF=('kneel', (-LEG_X - 0.5, FRONT_Z + 2.0)),
             LH=('ground', (LEG_X + 0.5, HIND_Z - 1.0), 0.0), RH=('ground', (-LEG_X - 0.5, HIND_Z), 0.0),
             tail_sway=-1.5, stains=chest, drool=((0.5, -3.0, 0.0), (0.0, -2.5, 0.0)))
    K = dict(yaw=24, bob=-12.5, pitch=6, roll=-36, hpitch=26, hyaw=8, hroll=-10, jaw=26,
             LF=('body', (LEG_X, -16.0, 5.0), 95.0), RF=('body', (-LEG_X, -15.5, 6.0), 95.0),
             LH=('body', (LEG_X + 1.0, -16.5, -3.0), -80.0), RH=('body', (-LEG_X, -16.0, -4.0), -70.0),
             tail_sway=-2.0, stains=chest, drool=((1.5, -2.5, 0.5), None))
    L = dict(yaw=30, shift=(0.0, -2.0), bob=-15.5, pitch=3, roll=-64, hpitch=18, hyaw=14, hroll=-6, jaw=30,
             LF=('body', (LEG_X + 0.5, -17.5, 12.0), 60.0), RF=('body', (-LEG_X - 1.0, -17.0, 10.0), 50.0),
             LH=('body', (LEG_X + 1.0, -17.5, -10.0), -40.0), RH=('body', (-LEG_X - 1.0, -17.0, -8.0), -30.0),
             tail_sway=-2.5, stains=chest, drool=((1.5, -2.0, 0.5), None))
    M = dict(yaw=34, shift=(0.0, -4.0), bob=-17.6, pitch=1, roll=-84, hpitch=10, hyaw=22, hroll=0, jaw=34,
             LF=('body', (LEG_X + 0.7, -18.0, 19.0), 25.0), RF=('body', (-LEG_X - 3.0, -19.5, 21.0), 0.0),
             LH=('body', (LEG_X + 0.7, -18.0, -18.0), -15.0), RH=('body', (-LEG_X - 3.0, -19.0, -19.0), 0.0),
             tail_sway=-3.0, stains=chest, drool=(None, None))
    N = dict(M, eyes='dead', jaw=40, pool=((-12.0, 0.1, 13.0), (15.0, 0.4, 10.0), 30),
             stains=chest + [('body', (0.0, -8.0, 4.0), 3.0), ('head', (0.0, -11.0, 5.0), 2.0)])
    return [I, J, K, L, M, N]


# ----------------------------------------------------------------------------- salida
def lumps():
    """{lump: ((lump, pose), ángulo)}; los fotogramas sin ángulo (0) se ven siempre de frente."""
    out = {}
    for fi, fr in enumerate('ABCD'):
        for a in range(1, 9):
            out[f'SARG{fr}{a}'] = ((f'SARG{fr}{a}', walk(fi)), a)
    for fr, pose in (('E', PAW), ('F', CHARGE), ('G', HOOK), ('H', PAIN)):
        for a in range(1, 9):
            out[f'SARG{fr}{a}'] = ((f'SARG{fr}{a}', pose), a)
    for fr, pose in zip('IJKLMN', deaths()):
        out[f'SARG{fr}0'] = ((f'SARG{fr}0', pose), 1)
    return out


def draw(item, angle):
    name, pose = item
    groups, extras = build(pose)
    R = render()
    out, depth = R.render(groups, extras, angle)
    return fit_bottom(trim(finish(out, depth, R.palarr, OUTLINE)), name)


if __name__ == '__main__':
    cli(lumps, draw, sprite_rows('SARG', 'ABCDEFGH', 'IJKLMN'))
