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
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdf import (V, nrm, rot_x, rot_y, rot_z, rad, rot_axis, basis, Frame, _len,  # noqa: E402,F401
                 Sphere, Ellipsoid, RoundCone, CappedCone, Box, EllCone, Ring, Group, vnoise,
                 Render, finish, trim, ik, apply_shine, cli, sprite_rows)

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



def materiales(P, mat, inten, nz, nr, spec, lvl_extra, extras):
    """Ajustes propios del Penitente: pliegues, barro, trenzado, brillos, ojos, boca del trabuco, manchas."""
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
    apply_shine(mat, inten, spec, ((BRASS, 0.9, 10), (SKIN, 0.25, 6), (BLOOD, 0.6, 12), (BONE, 0.3, 8)))
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


RENDER = None


def render():
    global RENDER
    if RENDER is None:
        RENDER = Render(RAMPS, hook=materiales, flash_mats=(FLASH,), level_mats=(EYE,), emissive=EMISSIVE,
                        no_light=(FLASH, EYE, HOLE, SOCKET))
    return RENDER


# ----------------------------------------------------------------------------- modelo
HIP_Y = 27.0
SHOULDER = (6.0, 11.5, -0.2)       # hombro izquierdo en el marco del torso (x+ = izquierda del personaje)
NECK = (0.0, 15.0, 0.3)
UPPER_ARM, FOREARM = 8.5, 9.0


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


def draw(pose, angle):
    if isinstance(pose, tuple) and pose[0] == 'gib':
        groups, extras = gib(pose[1])
    else:
        groups, extras = build(pose)
    R = render()
    out, depth = R.render(groups, extras, angle)
    return trim(finish(out, depth, R.palarr, OUTLINE))


if __name__ == '__main__':
    cli(lumps, draw, sprite_rows('POSS', 'ABCDEFG', 'HIJKLMNOPQRSTU'))
