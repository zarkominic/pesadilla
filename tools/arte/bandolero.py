#!/usr/bin/env python3
"""bandolero.py — dibuja POR CÓDIGO al BANDOLERO (sustituye al sargento de escopeta SPOS de Freedoom).

Bandolero de Sierra Morena no muerto: sombrero calañés negro de ala ancha vuelta, cara de calavera
con jirones de piel seca, patillas y ojos que brillan como brasas, pañuelo al cuello, chaquetilla
corta abierta sobre la camisa, faja roja con los cabos colgando, manta zamorana a rayas terciada
del hombro izquierdo a la cadera derecha (anudada a la espalda), calzón oscuro, polainas de cuero
y botos. Lleva una escopeta larga de dos cañones (nogal y hierro, con perrillos).

Mismo motor y estilo que el Penitente (tools/arte/sdf.py): modelo 3D de primitivas SDF con poses
paramétricas, rampas exactas de PLAYPAL, reducción con prioridad a lo cercano y contorno de 1 px.
Algo más corpulento que el Penitente y a la misma escala (1 unidad ≈ 1 px); a distancia se le
distingue por la silueta plana y ancha del sombrero, las piernas a la vista y la faja roja.

Fotogramas (info.c, S_SPOS_*): A-D andar, E apuntar (escopeta al hombro), F disparo de los dos
cañones (a pleno brillo), G dolor (8 ángulos cada uno); H-L muerte (el sombrero sale volando y
queda junto al cadáver) y M-U despedazado (de frente, ángulo 0).

Pies: el sargento de Freedoom no tiene el punto de apoyo a la misma altura en todos sus fotogramas
(5, 4, 3, 2 o 0 filas por debajo del suelo; y SPOSA2 no existe, solo SPOSA2A8, así que se usa 4) y
construir_pwad.py lo copia. ground() añade o quita filas transparentes abajo según el lump para que
el suelo quede siempre en el mismo sitio: los pies no saltan entre fotogramas ni entre ángulos (sin
tocar offsets.json). El modelo se traza LIFT px más alto para no cortar las puntas de las botas.

Uso (determinista, regenera los 70 PNG SPOS*):
    ~/.venvs/pesadilla/bin/python tools/arte/bandolero.py --salida arte/sprites
    … --solo SPOSA1,SPOSE3      solo esos lumps
    … --hoja hoja.png           además, hoja de contactos ampliada x3 con etiquetas
"""
import copy
import math
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdf import (V, nrm, rot_x, rot_y, rot_z, rad, basis, Frame, _len, Prim,  # noqa: E402
                 Sphere, Ellipsoid, RoundCone, CappedCone, Box, EllCone, Ring, Group, vnoise,
                 Render, finish, trim, ik, apply_shine, cli, sprite_rows, IWAD)
from penitente import hand, fall_root, _ballistic  # noqa: E402
from doomgfx import read_wad  # noqa: E402  (sdf.py ya añade tools/wad al path)
from construir_pwad import iwad_patch_geometry, default_offsets  # noqa: E402

# ----------------------------------------------------------------------------- materiales
(HAT, SKULL, DRYSKIN, HAIR, SOCKET, EYE, TEETH, SCARF, JACKET, SHIRT, SASH, MANTA, MANTA_E,
 MDARK, MRED, BREECH, GAITER, STRAP, BOOT, WOOD, IRON, HOLE, FLASH, BLOOD, FLESH, HANDS, BONE) = range(27)
# Rampas de índices de PLAYPAL, de oscuro a claro (colores exactos de la paleta).
RAMPS = {
    HAT: [6, 5, 111, 109, 107, 105, 102, 99],     # fieltro negro (con brillo gris: no se pierde en lo oscuro)
    SKULL: [140, 136, 132, 129, 128, 86],          # hueso
    DRYSKIN: [79, 78, 76, 74, 72, 70],             # piel seca, apergaminada
    HAIR: [8, 2, 239, 238],                        # patillas negras
    SOCKET: [0],
    EYE: [216, 228],                               # brasas
    TEETH: [132, 129, 128, 84],
    SCARF: [159, 157, 155, 153, 152],              # pañuelo verde oliva
    JACKET: [2, 238, 77, 76, 75, 74, 73],          # chaquetilla parda
    SHIRT: [106, 103, 100, 97, 94, 91],            # camisa sucia
    SASH: [44, 41, 38, 35, 32, 29],                # faja roja
    MANTA: [148, 147, 146, 145, 144, 128],         # manta zamorana: fondo crudo
    MANTA_E: [148, 147, 146, 145, 144, 128],       # (extremos y jirones: rayas horizontales)
    MDARK: [2, 239, 238, 237],                     # raya oscura
    MRED: [43, 40, 37, 34, 31],                    # raya roja
    BREECH: [8, 7, 6, 5, 111, 109, 107],           # calzón negro
    GAITER: [151, 150, 149, 148, 147, 146, 145],   # polainas de cuero
    STRAP: [2, 239, 238, 237],                     # correas de las polainas
    BOOT: [8, 2, 239, 238, 237, 236],              # botos
    WOOD: [2, 239, 238, 15, 13, 73],               # nogal
    IRON: [7, 5, 110, 107, 104, 101, 97, 93],      # hierro pavonado
    HOLE: [0],
    FLASH: [221, 215, 213, 229, 226, 225],         # fogonazo
    BLOOD: [191, 188, 185, 182, 179, 176],
    FLESH: [45, 40, 35, 30, 26],
    HANDS: [140, 136, 132, 129, 128, 86],          # manos de hueso
    BONE: [140, 136, 132, 129, 128, 86],
}
EMISSIVE = (EYE, FLASH)
OUTLINE = 2      # (23,15,7): casi negro cálido
CLOTH = (JACKET, SHIRT, SASH, MANTA, MDARK, MRED, BREECH, SCARF)


class FlatRing(Prim):
    """Banda plana elíptica (manta doblada y terciada): eje = y' de F, ancho 2w a lo largo del
    eje, grosor 2t en dirección radial, cantos redondeados."""

    def __init__(self, F, rx, rz, w, t, mat, rnd=0.45):
        self.F, self.rx, self.rz, self.w, self.t, self.mat, self.rnd = F, rx, rz, w, t, mat, rnd
        self.bc, self.br = F.o, max(rx, rz) + t + w

    def sdf(self, P):
        q = self.F.to_local(P)
        k0 = np.sqrt((q[:, 0] / self.rx) ** 2 + (q[:, 2] / self.rz) ** 2)
        k1 = np.sqrt((q[:, 0] / self.rx ** 2) ** 2 + (q[:, 2] / self.rz ** 2) ** 2)
        dr = k0 * (k0 - 1) / np.maximum(k1, 1e-9)
        ax = np.abs(dr) - (self.t - self.rnd)
        ay = np.abs(q[:, 1]) - (self.w - self.rnd)
        out = np.sqrt(np.maximum(ax, 0) ** 2 + np.maximum(ay, 0) ** 2)
        return out + np.minimum(np.maximum(ax, ay), 0) - self.rnd


def stripes(s, mat_base):
    """Rayas de la manta a lo largo de la coordenada s: fondo, raya oscura y raya roja."""
    band = np.mod(s, 6.5)
    out = np.full(len(s), mat_base)
    out[band < 1.1] = MDARK
    out[(band > 3.2) & (band < 4.4)] = MRED
    return out


def materiales(P, mat, inten, nz, nr, spec, lvl_extra, extras):
    """Ajustes propios del Bandolero: camisa en la abertura, rayas de la manta, pliegues de la
    faja, piel seca y boca de la calavera, ojos, correas, bocas de los cañones, manchas, brillos."""
    to, tR = extras['torso']
    q = (P - to) @ tR
    # Chaquetilla abierta: la camisa asoma por delante (más abierta arriba).
    m = ((mat == JACKET) & (q[:, 2] > 2.0) & (q[:, 1] > 1.2) & (q[:, 1] < 15.0)
         & (np.abs(q[:, 0]) < 0.55 + 0.17 * (q[:, 1] - 1.2)))
    mat[m] = SHIRT
    m = mat == JACKET
    inten[m] *= 0.9 + 0.18 * vnoise(q[m], 0.9, 3)
    m = mat == SASH                                                   # vueltas de la faja
    inten[m] *= 0.8 + 0.32 * (np.sin(q[m, 1] * 2.4 + 0.9 * nz[m]) > -0.35)
    # Manta: rayas transversales a lo largo de la banda; en los extremos, horizontales.
    mf = extras.get('manta')
    m = mat == MANTA
    if mf is not None and m.any():
        F, rx, rz = mf
        ql = F.to_local(P[m])
        mat[m] = stripes(np.arctan2(ql[:, 2] / rz, ql[:, 0] / rx) * (rx + rz) / 2, MANTA)
    m = mat == MANTA_E
    if m.any():
        mat[m] = stripes(P[m, 1] * 0.9 + 0.7, MANTA_E)
    # Calavera: jirones de piel seca (en coordenadas de la cabeza, no bailan entre fotogramas).
    hd = extras.get('head')
    if hd is not None:
        ho, hR = hd
        hq = (P - ho) @ hR
        near = _len(P - (ho + hR @ V(0, 4.0, 0.5))) < 7.0
        front = (hq[:, 2] > 1.2) & (np.abs(hq[:, 0]) < 2.0) & (hq[:, 1] < 5.0)  # la cara queda en hueso
        m = (mat == SKULL) & near & ~front & (vnoise(hq, 0.75, 21) > 0.48)
        mat[m] = DRYSKIN
        face = np.isin(mat, (SKULL, DRYSKIN)) & near & (hq[:, 2] > 1.3) & (np.abs(hq[:, 0]) < 1.6)
        teeth = face & (hq[:, 1] > 0.75) & (hq[:, 1] < 2.05)                     # dentadura
        mat[teeth] = TEETH
        gap = teeth & (np.mod(hq[:, 0] + 0.55, 1.1) < 0.4) & (hq[:, 1] < 1.75)
        mat[gap] = HOLE
    for ec in extras.get('eyes', []):
        de = _len((P - ec) * V(1.0, 1.45, 1.0)) if hd is None else _len(((P - ec) @ hR) * V(1.0, 1.45, 1.0))
        m = np.isin(mat, (SKULL, DRYSKIN, HAIR)) & (de < 1.2)
        mat[m] = SOCKET
        m = (mat == SOCKET) & (de < 0.6)
        mat[m] = EYE
        lvl_extra[m] = de[m] < 0.3
    nose = extras.get('nose')
    if nose is not None:
        m = np.isin(mat, (SKULL, DRYSKIN)) & (_len(P - nose) < 0.55)
        mat[m] = SOCKET
    # Correas de las polainas (bajo la rodilla y en el tobillo).
    for K, sd in extras.get('shins', []):
        s = (P - K) @ sd
        m = (mat == GAITER) & (((s > 1.4) & (s < 2.2)) | ((s > 7.6) & (s < 8.3)))
        mat[m] = STRAP
    # Bocas de los cañones: el interior es negro.
    for c0, f, rr in extras.get('muzzles', []):
        rel = P - c0
        along = rel @ f
        radial = _len(rel - np.outer(along, f))
        m = (mat == IRON) & (radial < rr) & (along > -1.6)
        mat[m] = HOLE
    # Manchas de sangre sobre la ropa.
    for sc, sr in extras.get('stains', []):
        ds = _len(P - sc)
        m = np.isin(mat, CLOTH) & (ds < sr * (0.75 + 0.5 * nz))
        mat[m] = BLOOD
    apply_shine(mat, inten, spec, ((IRON, 0.9, 10), (SKULL, 0.25, 6), (HANDS, 0.25, 6), (BONE, 0.3, 8),
                                   (BLOOD, 0.6, 12), (HAT, 0.35, 8), (BOOT, 0.3, 8), (GAITER, 0.2, 6)))


RENDER = None


def render():
    global RENDER
    if RENDER is None:
        RENDER = Render(RAMPS, hook=materiales, flash_mats=(FLASH,), level_mats=(EYE,), emissive=EMISSIVE,
                        no_light=(FLASH, EYE, HOLE, SOCKET))
    return RENDER


# ----------------------------------------------------------------------------- modelo
HIP_Y = 26.5
SHOULDER = (7.3, 11.6, -0.3)       # hombro izquierdo en el marco del torso (x+ = izquierda del personaje)
NECK = (0.0, 16.9, 0.5)
UPPER_ARM, FOREARM = 9.3, 9.0
THIGH, SHIN = 13.0, 12.6
ANKLE = 2.2
MANTA_R = (10.0, 5.9)


def hat_parts(F):
    """Sombrero calañés en su marco (origen en el ala, y' arriba): ala ancha vuelta y copa
    troncocónica baja."""
    p, M = F.p, F.M()
    return [
        Ellipsoid(p((0, 0, 0)), (8.4, 0.55, 8.1), M, HAT),                  # ala
        Ring(Frame(p((0, 0.6, 0)), M), 7.9, 7.6, 0.75, HAT),                 # borde vuelto hacia arriba
        CappedCone(p((0, -0.4, 0)), p((0, 4.4, 0)), 4.2, 3.3, HAT),          # copa
        Ellipsoid(p((0, 4.25, 0)), (3.3, 0.45, 3.3), M, HAT),                # tapa algo abombada
    ]


def escopeta(GF):
    """Escopeta de dos cañones en su marco: z' a lo largo de los cañones, y' arriba, origen en la
    garganta de la culata (donde la empuña la mano derecha)."""
    p, M = GF.p, GF.M()
    parts = [
        Box(p((0, -1.5, -6.6)), (0.85, 1.95, 2.5), M @ rot_x(rad(-9)), 0.45, WOOD),      # culata
        RoundCone(p((0, -0.7, -4.2)), p((0, 0.15, -0.3)), 0.95, 0.75, WOOD),              # garganta
        Box(p((0, 0.45, 0.9)), (1.15, 0.85, 1.5), M, 0.3, IRON),                          # báscula
        RoundCone(p((0, -0.3, 2.4)), p((0, 0.05, 9.5)), 0.95, 0.8, WOOD),                 # guardamanos
        RoundCone(p((0.62, 0.85, 1.0)), p((0.62, 0.85, 18.0)), 0.72, 0.62, IRON),          # cañones
        RoundCone(p((-0.62, 0.85, 1.0)), p((-0.62, 0.85, 18.0)), 0.72, 0.62, IRON),
        RoundCone(p((0.55, 1.3, -0.5)), p((0.6, 2.35, -0.1)), 0.4, 0.32, IRON),            # perrillos
        RoundCone(p((-0.55, 1.3, -0.5)), p((-0.6, 2.35, -0.1)), 0.4, 0.32, IRON),
        Ring(Frame(p((0, -0.5, 0.5)), M @ rot_z(rad(90))), 0.85, 0.85, 0.22, IRON),        # guardamonte
    ]
    muzzles = [(p((sx * 0.62, 0.85, 18.0)), GF.d((0, 0, 1)), 0.4) for sx in (-1, 1)]
    return parts, muzzles


DEFAULT = dict(
    bob=0.0, lean=5.0, twist=0.0, side=0.0, head_pitch=3.0, head_roll=0.0, head_yaw=0.0,
    foot_r=(-3.4, 0.0, 0.6), foot_l=(3.4, 0.0, -0.4), lift_r=0.0, lift_l=0.0,
    gun=dict(frame='upper', grip=(-4.8, 2.2, 6.0), f=(0.6, 0.26, 0.75), up=(0, 1, 0)),
    hand_r='gun', hand_l='gun', grip_r=(0, -0.5, -1.3), grip_l=(0, -0.95, 6.2),
    flash=False, root=None, flatten=None, tails=0.0, hat='head', hat_tilt=(-5.0, 4.0),
    stains=(), spray=(), extra=(), no_torso=False, no_head=False, no_arms=False, no_gun=False,
    eyes=True, legs=True, stump=False, knee_pole=(0, 0, 1),
)


def build(pose):
    p = dict(DEFAULT)
    p.update(pose)
    root = p['root'] or Frame()
    xf = p['flatten']
    groups = []
    extras = {'eyes': [], 'stains': [], 'muzzles': []}

    up = root * Frame((0, HIP_Y + p['bob'], 0),
                      rot_y(rad(p['twist'])) @ rot_x(rad(p['lean'])) @ rot_z(rad(p['side'])))
    head = up * Frame(NECK, rot_y(rad(p['head_yaw'])) @ rot_x(rad(p['head_pitch'])) @ rot_z(rad(p['head_roll'])))
    extras['torso'] = (up.o, up.R)

    def where(fr, pt):
        return up.p(pt) if fr == 'upper' else root.p(pt) if fr == 'root' else head.p(pt) if fr == 'head' else V(pt)

    # --- piernas: calzón, polainas con correas y botos
    if p['legs']:
        legs, shins = [], []
        for sx, foot, lift in ((-1, p['foot_r'], p['lift_r']), (1, p['foot_l'], p['lift_l'])):
            hipj = root.p((3.3 * sx, HIP_Y - 1.6 + p['bob'], 0))
            ank = root.p(V(foot) + (0, ANKLE + lift, 0))
            knee = ik(hipj, ank, THIGH, SHIN, root.d(p['knee_pole']))
            sd = nrm(ank - knee)
            fwd = root.d((0.1 * sx, -0.05 if lift == 0 else -0.3, 1))
            legs += [RoundCone(hipj, knee, 3.25, 2.55, BREECH),
                     RoundCone(knee - sd * 0.4, ank - sd * 0.4, 2.45, 1.75, GAITER),
                     RoundCone(ank - fwd * 1.2 - root.d((0, 0.5, 0)), ank + fwd * 4.3 - root.d((0, 1.0, 0)), 1.8, 1.3, BOOT),
                     RoundCone(ank - sd * 0.2, ank - root.d((0, 0.6, 0)), 1.95, 1.85, BOOT)]
            shins.append((knee, sd))
        legs.append(Ellipsoid(root.p((0, HIP_Y - 0.4 + p['bob'], 0)), (5.9, 4.3, 4.4), up.M(), BREECH))   # caderas
        groups.append(Group(legs, k=0.6, name='legs'))
        extras['shins'] = shins

    # --- torso: chaquetilla corta, faja, manta terciada y pañuelo
    if not p['no_torso']:
        jacket = [EllCone(up * Frame((0, 0.5, 0)), 11.0, (6.1, 4.5), (7.2, 5.0), JACKET),
                  Ellipsoid(up.p((0, 10.3, -0.3)), (6.9, 4.4, 4.8), up.M(), JACKET)]
        for sx in (-1, 1):
            jacket.append(Sphere(up.p((SHOULDER[0] * sx, SHOULDER[1], SHOULDER[2])), 3.0, JACKET))
        groups.append(Group(jacket, k=2.0, name='torso'))

        tw = p['tails']
        knot = up.p((5.3, -0.2, 3.5))
        e1, e2 = up.p((6.3 + tw, -7.6, 3.9)), up.p((5.0 + 0.6 * tw, -6.4, 4.5))
        sash = [EllCone(up * Frame((0, -2.9, 0)), 6.3, (6.45, 5.05), (6.55, 5.15), SASH),
                Sphere(knot, 1.45, SASH), RoundCone(knot, e1, 1.05, 1.3, SASH), RoundCone(knot, e2, 0.95, 1.15, SASH)]
        groups.append(Group(sash, k=0.6, name='sash'))

        MF = up * Frame((0.3, 7.6, -0.3), rot_z(rad(46)))
        manta = [FlatRing(MF, MANTA_R[0], MANTA_R[1], 2.5, 0.85, MANTA)]
        groups.append(Group(manta, name='manta'))
        extras['manta'] = (MF, MANTA_R[0], MANTA_R[1])
        mk = up.p((-4.6, 0.8, -4.6))                                  # nudo a la espalda, cadera derecha
        ends = [Sphere(mk, 1.7, MANTA_E)]
        for dx, ln, sw in ((-1.0, 7.5, tw * 0.5), (0.9, 6.2, tw * 0.3)):
            a = mk + up.d((dx, -0.6, -0.4))
            b = up.p((-4.6 + dx * 1.6 + sw, 0.8 - ln, -5.2))
            ends.append(RoundCone(a, b, 1.25, 1.45, MANTA_E))
        groups.append(Group(ends, k=0.5, name='manta_ends'))

        sc = [Ring(Frame(up.p((0, 14.4, 0.4)), up.M(rot_x(rad(-14)))), 2.4, 2.5, 0.95, SCARF),
              Sphere(up.p((0.5, 13.6, 3.4)), 1.05, SCARF),
              Ellipsoid(up.p((0.6, 12.0, 4.5)), (1.7, 2.0, 0.7), up.M(rot_x(rad(-12))), SCARF)]
        groups.append(Group(sc, k=0.5, name='scarf'))

    # --- cabeza: calavera con patillas, ojos de brasa
    if not p['no_head']:
        hd = [Ellipsoid(head.p((0, 4.9, -0.2)), (3.5, 3.7, 3.9), head.M(), SKULL),
              Ellipsoid(head.p((0, 3.0, 1.4)), (2.8, 2.6, 2.6), head.M(), SKULL),
              Ellipsoid(head.p((0, 0.9, 1.6)), (2.2, 1.5, 2.05), head.M(), SKULL),
              RoundCone(up.p((0, 13.5, 0.2)), head.p((0, 2.2, -0.4)), 1.35, 1.15, SKULL)]
        for sx in (-1, 1):
            hd.append(Ellipsoid(head.p((3.05 * sx, 3.1, 0.4)), (0.7, 2.0, 1.2), head.M(), HAIR))
        hd.append(Ellipsoid(head.p((0, 4.0, -2.7)), (2.9, 2.2, 1.4), head.M(), HAIR))       # melena bajo el ala
        groups.append(Group(hd, k=0.7, name='head'))
        extras['head'] = (head.o, head.R)
        if p['eyes']:
            hg = groups[-1]

            def surf(a, dirv):
                lo, hi = 0.0, 9.0
                for _ in range(30):
                    mid = (lo + hi) / 2
                    if hg.eval((a + dirv * mid)[None])[0][0] < 0:
                        lo = mid
                    else:
                        hi = mid
                return a + dirv * lo
            for sx in (-1, 1):
                extras['eyes'].append(surf(head.p((1.2 * sx, 3.95, 0.6)), head.d(nrm((0.2 * sx, 0.05, 1)))))
            extras['nose'] = surf(head.p((0, 2.75, 1.0)), head.d((0, 0, 1)))

    # --- sombrero (puesto, o suelto cuando sale volando)
    hat = p['hat']
    HF = None
    if hat == 'head' and not p['no_head']:
        HF = head * Frame((0, 7.3, 0.0), rot_x(rad(p['hat_tilt'][0])) @ rot_z(rad(p['hat_tilt'][1])))
    elif isinstance(hat, tuple) and hat[0] == 'rel':
        HF = head * Frame(hat[1], rot_x(rad(hat[2])) @ rot_z(rad(hat[3])))
    elif isinstance(hat, Frame):
        HF = hat
    if HF is not None:
        groups.append(Group(hat_parts(HF), k=0.5, name='hat'))

    # --- escopeta
    gspec = p['gun']
    GF = None
    if not p['no_gun'] and gspec is not None:
        Mg = basis(gspec['f'], gspec.get('up', (0, 1, 0)))
        GF = up * Frame(gspec['grip'], Mg) if gspec['frame'] == 'upper' else Frame(gspec['grip'], Mg)
        gparts, muzzles = escopeta(GF)
        groups.append(Group(gparts, k=0.2, name='gun'))
        extras['muzzles'] = muzzles
        if p['flash']:
            mc = (muzzles[0][0] + muzzles[1][0]) / 2
            f = muzzles[0][1]
            r_, u_ = GF.d((1, 0, 0)), GF.d((0, 1, 0))
            core = mc + f * 2.6
            fl = [Sphere(core, 3.0, FLASH), RoundCone(mc + f * 0.8, mc + f * 10.5, 2.2, 0.3, FLASH)]
            for dv in (r_, -r_, u_, -u_):
                dd = nrm(f * 0.8 + dv)
                fl.append(RoundCone(mc + f * 1.8, mc + f * 1.8 + dd * 6.5, 1.3, 0.2, FLASH))
            for dv in (r_ + u_, r_ - u_, -r_ + u_, -r_ - u_):
                dd = nrm(f * 1.2 + nrm(dv))
                fl.append(RoundCone(mc + f * 1.8, mc + f * 1.8 + dd * 4.4, 0.9, 0.2, FLASH))
            groups.append(Group(fl, k=0.6, name='flash'))
            extras['flash_core'] = (core, 10.5)
            extras['flash_light'] = (core, 26.0)

    # --- brazos (mangas de la chaquetilla, puños de la camisa) y manos de hueso
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
                T = where(spec[0], spec[1])
                along = None
            pole = up.d((0.8 * sx, -0.6, -0.7))
            E = ik(S, T, UPPER_ARM, FOREARM, pole)
            fa = nrm(T - E)
            cuff = T - fa * 2.0
            sleeves += [RoundCone(S, E, 2.5, 2.1, JACKET), RoundCone(E, cuff, 2.1, 1.9, JACKET),
                        RoundCone(cuff, cuff + fa * 0.7, 1.75, 1.55, SHIRT)]
            hands += hand(T, along if along is not None else fa, HANDS)
        if sleeves:
            groups.append(Group(sleeves, k=0.8, name='sleeves'))
            groups.append(Group(hands, k=0.4, name='hands'))

    # --- muñón (despedazado: solo quedan las piernas)
    if p['stump']:
        st = [Ellipsoid(up.p((0, 1.6, 0)), (5.2, 1.7, 4.0), up.M(), FLESH),
              RoundCone(up.p((0, 1.0, -1.6)), up.p((0.4, 6.0, -1.9)), 0.9, 0.7, BONE),
              Sphere(up.p((1.5, 2.6, 1.2)), 1.3, BLOOD), Sphere(up.p((-2.0, 2.4, 0.6)), 1.1, BLOOD)]
        groups.append(Group(st, k=0.5, name='stump'))
        sash = [EllCone(up * Frame((0, -2.9, 0)), 4.3, (6.45, 5.05), (6.55, 5.15), SASH)]
        groups.append(Group(sash, name='sash'))

    extras['stains'] = [(where(fr, pt), r) for fr, pt, r in p['stains']]
    if p['spray']:
        groups.append(Group([Sphere(where(fr, pt), r, BLOOD) for fr, pt, r in p['spray']], name='spray'))
    for g in p['extra']:
        groups.append(g)
    if xf is not None:
        for g in groups:
            if g.name not in ('gun', 'extra', 'pool', 'spray', 'hat'):
                g.xf = xf
        extras['eyes'] = []
        extras.pop('nose', None)
    return groups, extras


# ----------------------------------------------------------------------------- poses
def walk(i):
    a = i * math.pi / 2
    c, s = math.cos(a), math.sin(a)
    return dict(
        bob=0.5 - 1.3 * abs(c), lean=6.0, twist=-6 * c, side=1.5 * s,
        head_pitch=2 + 2 * abs(c), head_roll=-2 * s,
        foot_r=(-3.4, 0, 0.6 + 5.6 * c), lift_r=2.6 * max(0, -s),
        foot_l=(3.4, 0, 0.6 - 5.6 * c), lift_l=2.6 * max(0, s),
        tails=1.4 * s,
        gun=dict(frame='upper', grip=(-4.8, 2.2 + 0.4 * abs(c), 6.0), f=nrm((0.6, 0.26 + 0.04 * c, 0.75))),
    )


AIM = dict(lean=2.0, twist=-18, head_yaw=14, head_pitch=9, head_roll=8, bob=-0.6,
           foot_r=(-4.0, 0, -2.4), foot_l=(3.4, 0, 3.2), tails=0.5,
           gun=dict(frame='model', grip=(-4.4, 41.0, 7.6), f=nrm((0.1, 0.0, 1.0))),
           grip_r=(0, -0.5, -1.3), grip_l=(0, -0.95, 6.0))

FIRE = dict(AIM, lean=-4.0, head_pitch=5, twist=-15,
            gun=dict(frame='model', grip=(-4.6, 41.6, 6.2), f=nrm((0.1, math.sin(rad(10)), math.cos(rad(10))))),
            flash=True, tails=-0.6)

PAIN = dict(lean=-14, twist=12, side=-4, head_pitch=-18, head_roll=8, bob=0.3, hat_tilt=(14, -9),
            foot_r=(-3.6, 0, 0.8), foot_l=(3.4, 0, -0.8), tails=-1.6,
            gun=dict(frame='upper', grip=(-15.5, 13.5, 4.0), f=nrm((-0.2, 0.9, 0.4))),
            grip_r=(0, -0.5, -1.3), hand_l=('upper', (17.0, 12.5, 3.0)))


def deaths():
    chest = [('upper', (0.8, 8.5, 4.8), 3.6), ('upper', (-2.2, 5.0, 4.9), 2.2)]
    H = dict(lean=-21, twist=8, side=3, head_pitch=-30, head_roll=-8, bob=0.6,
             foot_r=(-3.6, 0, 1.2), foot_l=(3.4, 0, -0.8), tails=-2.0,
             hat=('rel', (1.5, 10.0, -0.5), 34, 22),
             gun=dict(frame='model', grip=(-19.0, 46.0, 4.0), f=nrm((-0.5, 0.85, 0.15))),
             hand_r=('upper', (-15.5, 17.0, 3.0)), hand_l=('upper', (15.0, 18.0, 2.0)),
             stains=chest,
             spray=[('upper', (1.0, 9.0, 7.4), 1.5), ('upper', (2.4, 11.5, 10.2), 1.1),
                    ('upper', (-0.5, 12.5, 12.4), 0.8), ('upper', (3.6, 13.8, 12.9), 0.7)])
    I = dict(lean=38, twist=14, side=7, head_pitch=26, head_roll=10, bob=-7.5,
             foot_r=(-3.8, 0, 0.0), foot_l=(3.8, 0, -1.4), tails=1.0,
             hat=Frame((9.0, 51.0, -6.0), rot_z(rad(-40)) @ rot_x(rad(-12))),
             hand_r=('model', (-7.5, 10.0, 9.0)), hand_l=('model', (7.0, 9.0, 8.0)),
             gun=dict(frame='model', grip=(-11.0, 3.6, 8.0), f=nrm((0.55, -0.3, 0.75))),
             stains=chest)
    J = dict(root=fall_root(40, 25, 8, 0.0), lean=-12, head_pitch=-20, bob=-2.0, side=-5,
             foot_r=(-3.8, 0, 3.0), foot_l=(3.8, 0, 1.0),
             hat=Frame((15.0, 22.0, -6.0), rot_z(rad(-75)) @ rot_x(rad(-14))),
             hand_r=('root', (-14.0, 30.0, 5.0)), hand_l=('root', (13.0, 33.0, 3.0)),
             gun=dict(frame='model', grip=(-15.0, 1.7, 9.0), f=nrm((0.9, 0, 0.35)), up=(0, 0, 1)),
             stains=chest)
    K = dict(root=fall_root(74, 45, 18, 3.5), lean=-8, head_pitch=-15, bob=-2.0, side=-4,
             foot_r=(-3.8, 0, 3.0), foot_l=(3.8, 0, 1.5),
             hat=Frame((18.0, 1.0, -3.0), rot_z(rad(5)) @ rot_x(rad(6))),
             hand_r=('root', (-15.0, 28.0, 3.0)), hand_l=('root', (14.0, 31.0, 1.0)),
             gun=dict(frame='model', grip=(-18.0, 1.7, 10.0), f=nrm((0.95, 0, 0.3)), up=(0, 0, 1)),
             stains=chest)
    L = dict(root=fall_root(88, 55, 30, 4.6), lean=-4, head_pitch=-12, bob=-2.0, side=-3,
             foot_r=(-4.0, 0, 2.0), foot_l=(4.0, 0, 3.5),
             hat=Frame((18.0, 1.0, -3.0), rot_z(rad(5)) @ rot_x(rad(6))),
             hand_r=('root', (-14.0, 26.0, 2.0)), hand_l=('root', (14.0, 29.0, 1.0)),
             gun=dict(frame='model', grip=(-21.0, 1.7, 11.0), f=nrm((0.95, 0, 0.3)), up=(0, 0, 1)),
             stains=chest, flatten=(np.diag([1, 0.6, 1.0]), V(0, 0, 0), 0.6),
             extra=[Group([Ellipsoid((3.0, 0.15, -3.0), (17.0, 0.5, 6.0), rot_y(rad(-37)), BLOOD)], name='pool')])
    return [H, I, J, K, L]


# ----------------------------------------------------------------------------- muerte despedazado (M-U)
GIB_T = [0.0, 0.10, 0.22, 0.34, 0.46, 0.58, 0.72, 0.86, 1.0]
# Las piernas se quedan en pie, se doblan y caen de espaldas: (giro de caída, deslizamiento, bajada de cadera, aplastado)
GIB_LEGS = [None, (0, 0, 0, 1.0), (0, 0, -3, 1.0), (10, 2, -7, 1.0), (32, 6, -9, 1.0),
            (60, 11, -9, 1.0), (80, 15, -8, 0.85), (88, 16, -8, 0.72), (88, 16, -8, 0.62)]


def _fragments():
    """Trozos que salen despedidos: (tipo, material, tamaño, posición inicial, velocidad, giro)."""
    rng = np.random.default_rng(1810)
    frs = []

    def add(kind, mat, size, y0, n, vx=(10, 30), vy=(30, 70), z0=0.0):
        for _ in range(n):
            ang = rng.uniform(0, 2 * math.pi)
            sp = rng.uniform(*vx)
            p0 = V(rng.uniform(-4, 4), y0 + rng.uniform(-4, 4), z0 + rng.uniform(-2, 2))
            v = V(math.cos(ang) * sp, rng.uniform(*vy), math.sin(ang) * sp * 0.45)
            frs.append((kind, mat, size * rng.uniform(0.75, 1.25), p0, v, rng.uniform(-6, 6)))

    add('rag', JACKET, 3.0, 36, 5)
    add('rag', MANTA_E, 3.2, 35, 4)
    add('rag', SASH, 2.4, 29, 2, vy=(20, 45))
    add('bone', BONE, 3.3, 38, 5)
    add('blob', FLESH, 1.7, 38, 4)
    add('blob', BLOOD, 1.2, 38, 14, vx=(8, 34), vy=(20, 80))
    frs.append(('skull', SKULL, 3.0, V(0.5, 46, 0.5), V(-15, 60, 3), 3.0))
    return frs


def gib(k):
    t = GIB_T[k]
    if k == 0:
        # M: el impacto revienta el pecho; el cuerpo sigue en pie y el sombrero sale disparado.
        H = dict(deaths()[0])
        H['hat'] = ('rel', (2.5, 13.0, -0.5), 30, 40)
        H['spray'] = list(H['spray']) + [
            ('upper', (-3.0, 8.0, 7.0), 1.7), ('upper', (4.5, 6.0, 6.5), 1.5), ('upper', (0.0, 4.0, 8.0), 1.3),
            ('upper', (-5.5, 11.0, 9.0), 1.0), ('upper', (6.0, 12.0, 9.5), 0.9), ('upper', (1.5, 15.0, 11.0), 0.8)]
        return build(H)

    # N-U: quedan las piernas (con la faja), que se doblan y caen; el resto vuela y cae.
    alpha, slide, drop, s = GIB_LEGS[k]
    base = dict(no_torso=True, no_head=True, no_arms=True, no_gun=True, eyes=False, hat=None, stump=True,
                lean=0.0, bob=drop, root=fall_root(alpha, 40, slide, 0.0) if alpha else None,
                foot_r=(-3.6, 0, 0.6), foot_l=(3.6, 0, -0.4),
                stains=[('upper', (1.0, -1.0, 5.0), 2.5)],
                flatten=(np.diag([1.0, s, 1.0]), V(0, 0, 0), s) if s < 1 else None)
    parts = []
    for kind, mat, size, p0, v, spin in _fragments():
        rest = {'rag': 0.6, 'bone': 0.8, 'blob': size * 0.5, 'skull': size}[kind]
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
            parts += [Sphere(c, size, SKULL), Ellipsoid(c + V(0, -1.6, 1.1), (1.7, 1.2, 1.5), None, SKULL),
                      Sphere(c + V(-1.1, 0.0, size * 0.85), 0.75, HOLE), Sphere(c + V(1.1, 0.0, size * 0.85), 0.75, HOLE)]
    groups, extras = build(base)
    groups.append(Group(parts, k=0.3, name='extra'))
    # El sombrero sube dando vueltas y cae de ala.
    hc, landed = _ballistic(V(0.5, 52.0, 0.0), V(10.0, 75.0, -3.0), t, 0.9)
    Rh = rot_z(rad(4)) @ rot_x(rad(6)) if landed else rot_z(rad(-40 - 50 * t)) @ rot_x(rad(-12))
    groups.append(Group(hat_parts(Frame(hc, Rh)), k=0.5, name='hat'))
    # La escopeta cae girando hasta quedar tendida a un lado.
    g0, g1 = V(-7.0, 34.0, 6.0), V(-20.0, 1.7, 8.0)
    u = min(1.0, t / 0.6)
    gp = g0 + (g1 - g0) * u + V(0, 12.0 * math.sin(math.pi * u) * (1 - u), 0)
    gf = nrm((math.sin(rad(90 * u)) * 0.95, -0.2 * (1 - u), math.cos(rad(90 * u)) * 0.3 + 0.05))
    gparts, _ = escopeta(Frame(gp, basis(gf, (0, 1, 0) if u < 1 else (0, 0, 1))))
    groups.append(Group(gparts, k=0.2, name='gun'))
    if k >= 4:
        rr = 6.0 + 14.0 * (k - 4) / 4
        groups.append(Group([Ellipsoid((1.0, 0.15, -1.0), (rr, 0.5, rr * 0.42), None, BLOOD)], name='pool'))
    return groups, extras


# ----------------------------------------------------------------------------- salida
LIFT = 2        # el modelo se traza 2 px más alto: lo que queda por delante (puntas de las botas) no se corta


def lift_scene(groups, extras, dy):
    """Sube toda la escena dy unidades (grupos y puntos de referencia del gancho de materiales)."""
    L = V(0, dy, 0)
    out = []
    for g in groups:
        g = copy.copy(g)
        g.xf = (np.eye(3), L, 1.0) if g.xf is None else (g.xf[0], V(g.xf[1]) + L, g.xf[2])
        out.append(g)
    ex = dict(extras)
    ex['eyes'] = [e + L for e in extras.get('eyes', [])]
    ex['stains'] = [(c + L, r) for c, r in extras.get('stains', [])]
    ex['muzzles'] = [(c + L, f, r) for c, f, r in extras.get('muzzles', [])]
    ex['shins'] = [(k + L, sd) for k, sd in extras.get('shins', [])]
    for key in ('torso', 'head', 'flash_core', 'flash_light'):
        if key in extras:
            ex[key] = (extras[key][0] + L, extras[key][1])
    if 'nose' in extras:
        ex['nose'] = extras['nose'] + L
    if 'manta' in extras:
        F, rx, rz = extras['manta']
        ex['manta'] = (Frame(F.o + L, F.R), rx, rz)
    return out, ex


_GEO = None


def ground(img, name):
    """Deja los pies a la misma altura en todos los fotogramas y ángulos.

    El PNG sale con el suelo LIFT + 1 filas por encima de su borde inferior (lo que está por delante
    del centro se ve algo más abajo, por la cámara 10° desde arriba).
    construir_pwad.py pone el suelo f filas por encima del borde inferior, con f copiado del sprite de
    Freedoom; en el sargento f cambia de un fotograma a otro (5 andando, 2-4 apuntando y disparando,
    0 en el cadáver y el despedazado; 4 si el lump no existe, p. ej. SPOSA2 frente a SPOSA2A8). Se añaden
    (o se quitan) filas abajo para que siempre queden f filas bajo el suelo: el punto de apoyo queda a la
    misma altura en todos (en el cadáver y el despedazado, f = 0, se recorta lo que cae por debajo)."""
    global _GEO
    if _GEO is None:
        _GEO = iwad_patch_geometry(read_wad(IWAD)[1])
    a = np.array(img)
    h, w = a.shape[:2]
    f = h - default_offsets(name, w, h, _GEO)[1]
    k = f - 1 - LIFT
    if k > 0:
        a = np.concatenate([a, np.zeros((k, w, 4), np.uint8)])
    elif k < 0:
        a = a[:h + k].copy()
    h = a.shape[0]
    for x in (0, w - 1):
        if a[h - 1, x, 3] == 0:
            a[h - 1, x] = (0, 0, 0, 1)        # anclas invisibles: el recorte conserva el lienzo
    return Image.fromarray(a, 'RGBA')


def lumps():
    """{lump: ((lump, pose), ángulo)}; los fotogramas sin ángulo (0) se ven siempre de frente."""
    out = {}
    for fi, fr in enumerate('ABCD'):
        for a in range(1, 9):
            out[f'SPOS{fr}{a}'] = (walk(fi), a)
    for fr, pose in (('E', AIM), ('F', FIRE), ('G', PAIN)):
        for a in range(1, 9):
            out[f'SPOS{fr}{a}'] = (pose, a)
    for fr, pose in zip('HIJKL', deaths()):
        out[f'SPOS{fr}0'] = (pose, 1)
    for k, fr in enumerate('MNOPQRSTU'):
        out[f'SPOS{fr}0'] = (('gib', k), 1)
    return {n: ((n, pose), a) for n, (pose, a) in out.items()}


def draw_pose(pose, angle):
    """Sprite sin ajustar al suelo (para pruebas): pose de build() o ('gib', k)."""
    if isinstance(pose, tuple) and pose[0] == 'gib':
        groups, extras = gib(pose[1])
    else:
        groups, extras = build(pose)
    groups, extras = lift_scene(groups, extras, LIFT)
    R = render()
    out, depth = R.render(groups, extras, angle)
    return trim(finish(out, depth, R.palarr, OUTLINE))


def draw(named, angle):
    name, pose = named
    return ground(draw_pose(pose, angle), name)


if __name__ == '__main__':
    cli(lumps, draw, sprite_rows('SPOS', 'ABCDEFG', 'HIJKLMNOPQRSTU'))
