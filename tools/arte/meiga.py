#!/usr/bin/env python3
"""meiga.py — dibuja POR CÓDIGO a la MEIGA (sustituye al imp TROO de Freedoom) y su bola de fuego (BAL1).

Bruja gallega encorvada y flaca: melena blanca enmarañada, cara afilada pálido-verdosa con ojos que
brillan amarillos y nariz ganchuda, harapos pardos y negros con un chal raído, brazos largos con
garras y descalza. Al atacar enciende en la mano una llama verde-amarilla y la lanza.

Técnica (la misma que el Penitente, ver sdf.py): modelo 3D de primitivas SDF con poses
paramétricas, trazado ortográfico, rampas exactas de PLAYPAL, reducción por mayoría con prioridad a
lo cercano y a lo que brilla, y contorno oscuro de 1 px. La bola de fuego y su explosión (BAL1, que
no rotan) se dibujan en 2D con ruido determinista.
- El modelo se piensa a 1 unidad = 1 px y se agranda SCALE (1,12) al dibujar: ~57 px de alto, como el imp.
- La melena cae con la gravedad del mundo y se aparta del cuerpo (push): por delante enmarca la cara y
  por detrás cae por encima del chal y la joroba.
- La llama de la mano (E, F) es más caliente en el centro visto desde la cámara y tiñe de verde la mano,
  la cara y el pelo cercanos.
- Los cadáveres y restos (L, M, R-U) se dibujan con la cámara algo más alta (hasta 26°) para que se lean
  en el suelo; luego se bajan a la última fila del lienzo (mismo apoyo que el resto).

Fotogramas (info.c): A-D andar, E-G ataque (E enciende la llama, F la levanta, G la lanza; también es
el zarpazo cuerpo a cuerpo), H dolor: los 8 ángulos, cada uno en su PNG (Freedoom los tiene en parejas
reflejadas, TROOA2A8…; -merge las sustituye ángulo a ángulo). I-M muerte, N-U despedazada: de frente.
BAL1 A-B en vuelo (a pleno brillo) y C-E explosión, de frente.

Uso (determinista, regenera los 77 PNG TROO* y los 5 BAL1*):
    ~/.venvs/pesadilla/bin/python tools/arte/meiga.py --salida arte/sprites
    … --solo TROOA1,BAL1A0      solo esos lumps
    … --hoja hoja.png           además, hoja de contactos ampliada x3 con etiquetas
"""
import math
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdf import (V, nrm, rot_x, rot_y, rot_z, rad, basis, Frame, _len,  # noqa: E402
                 Sphere, Ellipsoid, RoundCone, EllCone, Ring, Group, vnoise, SS,
                 Render, finish, trim, ik, apply_shine, cli, sprite_rows, rot_axis, TILT)
from penitente import hem_cut, fall_root, _ballistic  # noqa: E402

# ----------------------------------------------------------------------------- materiales
(SKIN, HAIR, RAG, RAGB, SHAWL, NAIL, EYE, SOCKET, MOUTH, FLAME, SPARK, BLOOD, BONE, FLESH, MUD,
 SKINL, HAIRL) = range(17)
RAMPS = {
    SKIN: [157, 155, 153, 152, 93],               # piel pálido-verdosa
    HAIR: [105, 101, 97, 93, 89, 85, 82],         # melena blanca sucia
    RAG: [2, 239, 238, 237, 236, 141],            # harapos pardos
    RAGB: [7, 6, 5, 110, 108, 105],               # harapos negros
    SHAWL: [1, 79, 77, 75, 73, 71],               # chal ocre desvaído
    NAIL: [2, 79, 77, 75, 151, 148],              # uñas de cuerno
    EYE: [163, 229],                              # brillo amarillo
    SOCKET: [0],
    MOUTH: [0, 47],
    FLAME: [121, 118, 115, 112, 160, 229, 226],   # llama verde-amarilla (de fuera a dentro)
    SPARK: [160],
    BLOOD: [191, 188, 185, 182, 179, 176],
    BONE: [109, 104, 98, 92, 87, 83],
    FLESH: [45, 40, 35, 30, 26],
    MUD: [7, 2, 239, 238, 237],
    SKINL: [125, 122, 119, 116, 114],             # piel iluminada por la llama
    HAIRL: [156, 154, 152, 118, 116, 114],        # pelo iluminado por la llama
}
EMISSIVE = (EYE, SPARK, FLAME)
OUTLINE = 2


def materiales(P, mat, inten, nz, nr, spec, lvl_extra, extras):
    """Ajustes propios de la Meiga: pliegues, remiendos, barro, mechones, ojos, boca, luz de la llama."""
    ax = extras.get('axis', (0, 0))
    ang_body = np.arctan2(P[:, 0] - ax[0], P[:, 2] - ax[1])
    m = np.isin(mat, (RAG, RAGB))
    inten[m] *= 1 + 0.22 * np.sin(8 * ang_body[m] + 2.5 * nz[m])          # pliegues
    # Barro en el bajo.
    mud = np.isin(mat, (RAG, RAGB)) & (P[:, 1] < 8.0 + 4.0 * vnoise(P, 0.6, 5)) & (vnoise(P, 1.7, 6) > 0.42)
    mat[mud] = MUD
    # Mechones: vetas alargadas en vertical.
    m = mat == HAIR
    st = vnoise(P * np.array([1.0, 0.2, 1.0]), 1.9, 7) * 0.7 + vnoise(P * np.array([1.0, 0.3, 1.0]), 3.7, 8) * 0.3
    inten[m] *= 0.5 + 0.8 * st[m]
    m = mat == SHAWL
    inten[m] *= 0.85 + 0.25 * (np.sin(P[m, 0] * 2.1 + P[m, 1] * 2.1) > 0.3)      # trama del chal
    apply_shine(mat, inten, spec, ((SKIN, 0.22, 6), (NAIL, 0.6, 8), (BLOOD, 0.6, 12), (BONE, 0.3, 8),
                                   (HAIR, 0.2, 4)))
    # Ojos hundidos con brillo amarillo.
    for ec in extras.get('eyes', []):
        de = _len(P - ec)
        m = (mat == SKIN) & (de < 1.2)
        mat[m] = SOCKET
        m = (mat == SOCKET) & (de < 0.62)
        mat[m] = EYE
        lvl_extra[m] = (de[m] < 0.4)
    # Boca: raja oscura (abierta en el dolor y la muerte).
    mo = extras.get('mouth')
    if mo is not None:
        c, r = mo
        m = (mat == SKIN) & (_len((P - c) * np.array([1.0, 1.0 / max(r[1] / r[0], 1e-3), 1.0])) < r[0])
        mat[m] = MOUTH
    # Llama: más caliente (amarilla) en el centro visto desde la cámara y abajo; verde en los bordes.
    fc = extras.get('flame_core')
    m = mat == FLAME
    if fc is not None and m.any():
        c, size = fc
        D = extras['view']
        rel = P[m] - c
        along = rel @ D
        perp = _len(rel - np.outer(along, D))
        hgt = np.maximum(rel[:, 1], 0)
        heat = 1.3 - perp / (size * 1.45) - hgt / (size * 5.0) + 0.3 * (nz[m] - 0.5)
        nf = len(RAMPS[FLAME])
        lvl_extra[m] = np.clip(np.floor(heat * nf), 0, nf - 1)
    # Luz verde de la llama sobre la mano, la cara y el pelo.
    gl = extras.get('green_light')
    if gl is not None:
        lp, lr = gl
        rel = lp - P
        dl = np.maximum(_len(rel), 1e-6)
        ndl = np.clip(np.einsum('ij,ij->i', nr, rel / dl[:, None]), 0, 1)
        amt = np.clip(1 - dl / lr, 0, 1) * (0.25 + 0.75 * ndl)
        for src, dst in ((SKIN, SKINL), (NAIL, SKINL), (HAIR, HAIRL)):
            m = (mat == src) & (amt > 0.28)
            mat[m] = dst
        m = np.isin(mat, (SKINL, HAIRL, RAG, RAGB, SHAWL))
        inten[m] += amt[m] * 0.9
    # Manchas de sangre sobre la ropa y la piel.
    for sc, sr in extras.get('stains', []):
        ds = _len(P - sc)
        m = np.isin(mat, (RAG, RAGB, SHAWL, SKIN, HAIR)) & (ds < sr * (0.75 + 0.5 * nz))
        mat[m] = BLOOD


RENDERS = {}


def render(tilt=TILT):
    """Trazador (uno por inclinación de cámara: los cadáveres se ven algo más desde arriba)."""
    key = round(tilt, 5)
    if key not in RENDERS:
        RENDERS[key] = Render(RAMPS, hook=materiales, level_mats=(EYE, FLAME), emissive=EMISSIVE,
                              no_light=(FLAME, SPARK, EYE, SOCKET, MOUTH), tilt=tilt)
    return RENDERS[key]


# ----------------------------------------------------------------------------- modelo
HIP_Y = 28.0
SHOULDER = (5.0, 9.0, 0.3)          # hombro izquierdo en el marco del pecho (x+ = izquierda del personaje)
UPPER_ARM, FOREARM = 12.0, 12.0
THIGH, SHIN = 13.9, 13.9
HEM_Y = 7.5
HS = 1.15                           # escala de la cabeza (más grande: se lee mejor de lejos)
SCALE = 1.12                        # escala global: el modelo se piensa a 1 unidad = 1 px y se agranda al
                                    # dibujar para quedar del alto del imp de Freedoom (~56 px)


def shawl_cut(F):
    """Borde raído del chal: corto por delante y en pico por la espalda (marco del pecho)."""
    def cut(P):
        q = F.to_local(P)
        ph = np.arctan2(q[:, 0], q[:, 2])
        back = np.maximum(0, -np.cos(ph))
        hy = (5.2 - 7.5 * back ** 1.3 + 0.8 * np.sin(9 * ph + 1.3) + 0.55 * np.sin(17 * ph + 0.4)
              + 1.6 * np.maximum(0, np.sin(5 * ph + 2.0)) ** 10)
        return hy - q[:, 1]
    return cut


def claw(T, along, palm, curl=0.7, spread=1.0, mat=SKIN):
    """Mano huesuda de dedos largos con uñas de cuerno. along: hacia los dedos; palm: normal de la palma."""
    a = nrm(along)
    n = V(palm) - a * (V(palm) @ a)
    n = nrm(n) if np.linalg.norm(n) > 1e-6 else nrm(np.cross(a, (1, 0, 0)))
    s = nrm(np.cross(a, n))
    parts = [Ellipsoid(T + a * 0.5, (1.25, 0.8, 1.5), basis(a, n), mat)]
    nails = []
    for off, ln in ((-1.0, 0.85), (-0.1, 1.0), (0.9, 0.9)):
        base = T + a * 1.6 + s * off * 0.75
        d1 = nrm(a + s * off * 0.32 * spread + n * curl * 0.35)
        j1 = base + d1 * 1.9 * ln
        d2 = nrm(d1 + n * curl * 0.8)
        j2 = j1 + d2 * 1.7 * ln
        d3 = nrm(d2 + n * curl * 0.7)
        parts += [RoundCone(base, j1, 0.55, 0.45, mat), RoundCone(j1, j2, 0.45, 0.4, mat)]
        nails.append(RoundCone(j2, j2 + d3 * 3.0 * ln, 0.45, 0.12, NAIL))
    th = T + a * 0.4 - s * 1.2
    dth = nrm(a * 0.6 - s * 0.6 + n * curl * 0.5)
    parts.append(RoundCone(th, th + dth * 2.0, 0.5, 0.4, mat))
    nails.append(RoundCone(th + dth * 2.0, th + dth * 3.4 + n * 0.4, 0.38, 0.12, NAIL))
    return parts, nails


def flame_parts(core, size, seed):
    """Llama verde-amarilla sobre la palma: núcleo, lenguas hacia arriba y chispas sueltas."""
    rng = np.random.default_rng(seed)
    up = V(0, 1, 0)
    parts = [Sphere(core, size, FLAME)]
    for k in range(5):
        ang = 2 * math.pi * k / 5 + rng.uniform(-0.5, 0.5)
        off = V(math.cos(ang), 0, math.sin(ang)) * size * 0.55
        h = size * rng.uniform(1.5, 2.5)
        tip = core + off * 1.6 + up * h + V(rng.uniform(-0.7, 0.7), 0, rng.uniform(-0.7, 0.7)) * size * 0.5
        parts.append(RoundCone(core + off, tip, size * 0.5, 0.2, FLAME))
    sparks = []
    for _ in range(4):
        sparks.append(Sphere(core + V(rng.uniform(-1, 1) * size * 1.6, rng.uniform(0.8, 3.0) * size,
                                      rng.uniform(-1, 1) * size * 1.4), 0.5, SPARK))
    return parts, sparks


DEFAULT = dict(
    bob=0.0, lean=12.0, hunch=24.0, twist=0.0, side=0.0,
    head_pitch=-4.0, head_roll=0.0, head_yaw=0.0, jaw=0.0,
    foot_r=(-3.2, 0.0, 0.6), foot_l=(3.2, 0.0, -0.6), lift_r=0.0, lift_l=0.0,
    hem=(0.0, 0.0), hem_r=(7.0, 6.2), rag=2.2,
    hand_r=('root', (-7.0, 22.0, 5.5)), hand_l=('root', (7.0, 22.0, 5.0)),
    dir_r=None, dir_l=None, palm_r=None, palm_l=None, pole_r=None, pole_l=None,
    curl_r=0.75, curl_l=0.75, spread_r=1.0, spread_l=1.0,
    flame=None, wind=(0.0, 0.0, 0.0), hair_fan=0.0, tilt=10.0,
    root=None, flatten=None, crush=0.0,
    stains=(), spray=(), extra=(),
    no_head=False, no_torso=False, no_arms=False, no_skirt=False, legs=True, eyes=True,
)


def hair_parts(head, wind, seed=3, fan=0.0, push=None):
    """Melena blanca enmarañada: casquete + mechones que caen (gravedad del mundo) + greñas de punta.
    push(p): saca un punto fuera del cuerpo (el pelo cae POR ENCIMA del chal y la joroba, no los atraviesa)."""
    rng = np.random.default_rng(seed)
    push = push or (lambda q: q)
    capc = head.p(V(0, 1.7, -1.7) * HS)
    parts = [Ellipsoid(capc, V(4.1, 4.0, 4.1) * HS, head.M(), HAIR)]
    down = V(0, -1, 0)
    W = V(wind)
    locks = []
    for yaw in (85, 115, 145, 170, 190, 215, 245, 275):            # melena larga: lados y nuca
        locks.append((yaw, 8, rng.uniform(12, 17), 1.5))
    for yaw in (95, 140, 180, 220, 265):                           # capa de arriba
        locks.append((yaw, 42, rng.uniform(8, 11), 1.4))
    for yaw in (128, 151, 172, 203, 232):                          # greñas de punta, hacia atrás y fuera
        locks.append((yaw, rng.uniform(22, 42), rng.uniform(2.4, 4.0), -1.0))
    for yaw, elev in ((28, 74), (167, 66), (243, 70)):              # greñas tiesas en la coronilla (asimétricas)
        locks.append((yaw, elev, rng.uniform(2.0, 3.0), -1.0))
    for yaw in (150, 178, 207):                                    # mechones que caen por la joroba
        locks.append((yaw, 18, rng.uniform(13, 16), -2.0))
    for yaw, elev, ln, rr in locks:
        yaw += rng.uniform(-12, 12)
        d = V(math.sin(rad(yaw)) * math.cos(rad(elev)), math.sin(rad(elev)), math.cos(rad(yaw)) * math.cos(rad(elev)))
        n = head.d(d)
        r0 = capc + head.d(d * V(3.8, 3.6, 3.9) * HS)
        jit = V(rng.uniform(-1, 1), rng.uniform(-0.5, 0.5), rng.uniform(-1, 1))
        if rr < -1.5:                                              # por encima de la joroba y espalda abajo
            back = head.d((0, 0, -1)) * V(1, 0, 1)
            back = nrm(back) if np.linalg.norm(back) > 1e-3 else V(0, 0, -1)
            nh = V(n[0], 0, n[2])
            nh = nh / max(np.linalg.norm(nh), 1e-6) * fan
            m = push(r0 + back * 4.5 + V(0, 1.2, 0) + jit * 0.8 + W * 0.3 + nh * 0.5)
            q = push(m + back * 3.0 + down * ln * 0.3 + jit * 0.8 + W * 0.5 + nh * 0.5)
            t = push(q + back * 1.0 + down * ln * 0.45 + jit * 1.2 + W * 0.8 + nh * 0.5)
            t[1] = max(t[1], 0.6)
            parts += [RoundCone(r0, m, 1.4, 1.3, HAIR), RoundCone(m, q, 1.3, 1.0, HAIR), RoundCone(q, t, 1.0, 0.4, HAIR)]
            continue
        if rr < 0:                                                 # greña de punta
            m = r0 + n * ln * 0.6 + jit * 0.6 + W * 0.3
            t = m + nrm(n + V(0, -0.2, 0) + jit * 0.6) * ln * 0.6 + W * 0.6
            parts += [RoundCone(r0, m, 1.0, 0.7, HAIR), RoundCone(m, t, 0.7, 0.3, HAIR)]
            continue
        nh = V(n[0], 0, n[2])
        nh = nh / max(np.linalg.norm(nh), 1e-6) * fan               # melena desparramada por el suelo
        m = push(r0 + n * (2.0 if elev < 30 else 0.9) + down * ln * 0.45 + jit * 1.2 + W * 0.4 + nh * 0.5)
        t = push(m + down * ln * 0.55 + n * 1.6 + jit * 1.6 + W * 1.0 + nh)
        t[1] = max(t[1], 0.6)
        m[1] = max(m[1], 0.9)
        parts += [RoundCone(r0, m, rr, rr * 0.75, HAIR), RoundCone(m, t, rr * 0.75, 0.35, HAIR)]
    return parts


def build(pose):
    p = dict(DEFAULT)
    p.update(pose)
    root = p['root'] or Frame()
    xf = p['flatten']
    groups = []
    extras = {'eyes': [], 'stains': []}

    up = root * Frame((0, HIP_Y + p['bob'], 0),
                      rot_y(rad(p['twist'])) @ rot_x(rad(p['lean'])) @ rot_z(rad(p['side'])))
    chest = up * Frame((0, 8.0, 0), rot_x(rad(p['hunch'])))
    head = chest * Frame((0, 12.0, 4.6), rot_x(rad(-(p['lean'] + p['hunch']) + p['head_pitch']))
                         @ rot_y(rad(p['head_yaw'])) @ rot_z(rad(p['head_roll'])))

    def where(fr, pt):
        return {'upper': up.p, 'chest': chest.p, 'root': root.p, 'head': head.p}.get(fr, V)(pt)

    # --- piernas: espinillas y pies descalzos; muslos bajo la falda
    feet, thighs, legcloth = [], [], []
    for sx, foot, lift in ((-1, p['foot_r'], p['lift_r']), (1, p['foot_l'], p['lift_l'])):
        hipj = root.p((3.0 * sx, HIP_Y - 1 + p['bob'], 0))
        ank = root.p(V(foot) + (0, 1.7 + lift, 0))
        knee = ik(hipj, ank, THIGH, SHIN, root.d((0, 0, 1)))
        fwd = root.d(nrm((0.15 * sx, -0.05 if lift == 0 else -0.35, 1)))
        toe = ank + fwd * 4.6 - root.d((0, 1.1, 0))
        feet += [RoundCone(ank - fwd * 1.0 - root.d((0, 0.5, 0)), toe, 1.3, 0.85, SKIN),
                 RoundCone(ank, knee, 1.0, 1.45, SKIN)]
        side = root.d((sx, 0, 0))
        for k in (-1, 0, 1):
            feet.append(RoundCone(toe - fwd * 0.6 + side * k * 0.6, toe + fwd * 0.9 + side * k * 0.7
                                  - root.d((0, 0.4, 0)), 0.45, 0.35, SKIN))
        thighs.append(RoundCone(hipj, knee, 2.9, 2.4, RAG))
        legcloth.append(RoundCone(knee + (hipj - knee) * 0.3, knee + (ank - knee) * 0.45, 2.7, 2.2, RAGB))

    # --- falda raída (unión suave con los muslos) y cuerpo
    hk = (HIP_Y + p['bob']) / HIP_Y                       # al agacharse, los bajos también bajan
    hemF = root * Frame((p['hem'][0], HEM_Y * hk, p['hem'][1] + 0.3))
    robe = []
    if not p['no_skirt']:
        waist = up.p((0, 1.5, 0.0))
        axis = waist - hemF.o
        ya = nrm(axis)
        xa = nrm(np.cross(ya, root.d((0, 0, 1))))
        Fsk = Frame(hemF.o, np.column_stack([xa, ya, np.cross(xa, ya)]))
        robe.append(EllCone(Fsk, np.linalg.norm(axis), p['hem_r'], (4.4, 3.6), RAGB))
        if p['legs']:
            robe += legcloth
        # Sobrefalda parda, más corta.
        hemO = root * Frame((p['hem'][0] * 0.7, (HEM_Y + 9.0) * hk, p['hem'][1] * 0.7 + 0.5))
        axo = waist - hemO.o
        yo = nrm(axo)
        xo = nrm(np.cross(yo, root.d((0, 0, 1))))
        Fo = Frame(hemO.o, np.column_stack([xo, yo, np.cross(xo, yo)]))
        over = [EllCone(Fo, np.linalg.norm(axo), (p['hem_r'][0] - 0.2, p['hem_r'][1] + 0.1), (4.8, 4.0), RAG)]
        if p['legs']:
            over += thighs
        groups.append(Group(over, k=1.6, cut=hem_cut(hemO, base=0.8, rag=1.3 + p['crush']), name='over'))
    if not p['no_torso']:
        robe += [Ellipsoid(up.p((0, 4.5, 0)), (3.9, 6.0, 3.0), up.M(), RAGB),
                 Ellipsoid(chest.p((0, 4.5, 0.2)), (4.4, 6.2, 3.1), chest.M(), RAG),
                 Sphere(chest.p((0, 6.2, -2.3)), 4.0, RAG)]
        for sx in (-1, 1):
            robe.append(Sphere(chest.p((SHOULDER[0] * sx, SHOULDER[1], SHOULDER[2])), 2.2, RAG))
    if robe:
        groups.append(Group(robe, k=1.6, cut=hem_cut(hemF, base=1.5, rag=p['rag'] + p['crush']), name='robe'))
    if p['legs']:
        groups.append(Group(feet, k=0.6, name='feet'))

    # --- chal raído sobre hombros y joroba, con nudo delante
    if not p['no_torso']:
        sh = [Ellipsoid(chest.p((0, 7.0, -0.7)), (7.6, 5.4, 5.0), chest.M(), SHAWL),
              Ellipsoid(chest.p((0, 3.5, -2.6)), (5.7, 6.4, 3.6), chest.M(), SHAWL)]
        knot = chest.p((0.6, 5.2, 3.9))
        sh.append(Sphere(knot, 1.2, SHAWL))
        groups.append(Group(sh, k=1.2, cut=shawl_cut(chest), name='shawl'))
        ends = [RoundCone(knot, knot + V(0.8, -4.2, 0.6), 0.9, 0.55, SHAWL),
                RoundCone(knot, knot + V(-0.6, -3.4, 0.9), 0.8, 0.5, SHAWL),
                Sphere(knot, 1.2, SHAWL)]
        groups.append(Group(ends, k=0.5, name='shawl_ends'))

    # --- cabeza: cara afilada, nariz ganchuda, barbilla en punta; cuello flaco
    if not p['no_head']:
        jaw = p['jaw']
        def hp(x, y, z):
            return head.p((x * HS, y * HS, z * HS))
        sk = [Ellipsoid(hp(0, 0.6, -0.3), V(3.1, 3.5, 3.5) * HS, head.M(), SKIN),
              Ellipsoid(hp(0, -1.3, 1.3), V(2.5, 3.4, 2.6) * HS, head.M(), SKIN),
              RoundCone(hp(0, -3.0, 1.9), hp(0, -5.8 - jaw, 3.1 - 0.4 * jaw), 1.4 * HS, 0.55 * HS, SKIN),
              Sphere(hp(1.6, -0.3, 2.3), 1.0 * HS, SKIN), Sphere(hp(-1.6, -0.3, 2.3), 1.0 * HS, SKIN),
              RoundCone(hp(0, 0.9, 3.2), hp(0, -0.9, 6.0), 0.8 * HS, 0.55 * HS, SKIN),
              RoundCone(hp(0, -0.9, 6.0), hp(0, -2.2, 5.4), 0.55 * HS, 0.3 * HS, SKIN),
              Sphere(hp(1.2, 1.7, 2.5), 0.85 * HS, SKIN), Sphere(hp(-1.2, 1.7, 2.5), 0.85 * HS, SKIN),
              RoundCone(chest.p((0, 9.5, 0.8)), hp(0, -2.2, -1.2), 1.8, 1.3, SKIN)]
        hg = Group(sk, k=0.7, name='head')
        groups.append(hg)
        extras['mouth'] = (hp(0, -3.2 - 0.5 * jaw, 3.0), (0.9 + 0.3 * jaw, 0.35 + 0.6 * jaw))
        if p['eyes']:
            for sx in (-1, 1):
                a = hp(1.2 * sx, 0.6, 0)
                dirv = head.d(nrm((0.18 * sx, 0, 1)))
                lo, hi = 0.0, 9.0
                for _ in range(30):
                    mid = (lo + hi) / 2
                    if hg.eval((a + dirv * mid)[None])[0][0] < 0:
                        lo = mid
                    else:
                        hi = mid
                extras['eyes'].append(a + dirv * lo)
        body = [g for g in groups if g.name in ('robe', 'over', 'shawl', 'shawl_ends')]

        def push(q, clear=1.0):
            q = V(q)
            if not body:
                return q
            f = lambda x: min(g.eval(x[None])[0][0] for g in body)
            for _ in range(10):
                d = f(q)
                if d >= clear:
                    break
                gr = V([f(q + e) - f(q - e) for e in np.eye(3) * 0.05])
                q = q + nrm(gr) * (clear - d + 0.15)
            return q
        groups.append(Group(hair_parts(head, p['wind'], fan=p['hair_fan'], push=push), k=0.9, name='hair'))

    # --- brazos largos: mangas negras rotas por el codo, antebrazos huesudos, garras
    if not p['no_arms']:
        sleeves, skin, nails = [], [], []
        for sx, sfx in ((-1, 'r'), (1, 'l')):
            S = chest.p((SHOULDER[0] * sx, SHOULDER[1], SHOULDER[2]))
            T = where(*p['hand_' + sfx])
            pole = p['pole_' + sfx]
            pole = up.d((0.55 * sx, -0.1, -1.0)) if pole is None else nrm(V(pole))
            E = ik(S, T, UPPER_ARM, FOREARM, pole)
            fa = nrm(T - E)
            along = fa if p['dir_' + sfx] is None else nrm(V(p['dir_' + sfx]))
            palm = V(-sx, 0, -0.4) if p['palm_' + sfx] is None else V(p['palm_' + sfx])
            cuff = E + (T - E) * 0.12
            sleeves += [RoundCone(S, E, 2.1, 1.8, RAGB), RoundCone(E, cuff, 1.8, 2.25, RAGB)]
            for k, (o1, ln) in enumerate(((0.9, 4.0), (-0.8, 3.0))):
                side = nrm(np.cross(fa, (0, 1, 0))) if abs(fa[1]) < 0.95 else V(1, 0, 0)
                b = cuff + side * o1 * 1.6
                sleeves.append(RoundCone(b, b + V(0, -ln, 0) + fa * 0.8, 0.8, 0.3, RAGB))
            skin.append(RoundCone(E + fa * 0.5, T, 1.2, 0.9, SKIN))
            hp, hn = claw(T, along, palm, p['curl_' + sfx], p['spread_' + sfx])
            skin += hp
            nails += hn
            if sfx == 'r' and p['flame']:
                size, seed = p['flame']
                core = T + along * 1.2 + nrm(palm) * (1.3 + size * 0.9)
                fparts, sparks = flame_parts(core, size, seed)
                groups.append(Group(fparts, k=0.5, name='flame'))
                groups.append(Group(sparks, name='sparks'))
                extras['flame_core'] = (core, size)
                extras['green_light'] = (core, size * 6.0 + 6.0)
            if sfx == 'r' and p.get('sparks_g'):
                rng = np.random.default_rng(21)
                fwd = nrm(along)
                sp = [Sphere(T + fwd * rng.uniform(4, 10) + V(rng.uniform(-2, 2), rng.uniform(-1.5, 2.5),
                                                               rng.uniform(-1, 1)), 0.5, SPARK) for _ in range(5)]
                groups.append(Group(sp, name='sparks'))
        groups.append(Group(sleeves, k=0.9, name='sleeves'))
        groups.append(Group(skin, k=0.45, name='arms'))
        groups.append(Group(nails, name='nails'))

    extras['stains'] = [(where(fr, pt), r) for fr, pt, r in p['stains']]
    if p['spray']:
        groups.append(Group([Sphere(where(fr, pt), r, BLOOD) for fr, pt, r in p['spray']], name='spray'))
    for g in p['extra']:
        groups.append(g)
    if xf is not None:
        for g in groups:
            if g.name not in ('extra', 'pool', 'spray'):
                g.xf = xf
        extras['eyes'] = []
        extras.pop('mouth', None)
    ax = root.p((0, 0, 0))
    extras['axis'] = (ax[0], ax[2])
    return groups, extras


# ----------------------------------------------------------------------------- poses
def walk(i):
    a = i * math.pi / 2
    c, s = math.cos(a), math.sin(a)
    return dict(
        bob=0.4 - 1.2 * abs(c), hunch=24 + 2 * abs(c), twist=-6 * c, side=1.8 * s,
        head_pitch=-5 + 3 * abs(c), head_roll=-3 * s, head_yaw=4 * c,
        foot_r=(-3.2, 0, 0.6 + 5.0 * c), lift_r=2.0 * max(0, -s),
        foot_l=(3.2, 0, 0.6 - 5.0 * c), lift_l=2.0 * max(0, s),
        hem=(0.9 * s, 0.4 * c), hem_r=(7.0, 6.2 + 0.8 * abs(c)),
        hand_r=('root', (-8.4, 23.0 + 0.6 * abs(c), 6.0 - 4.5 * c)),
        hand_l=('root', (8.4, 23.0 + 0.6 * abs(c), 6.0 + 4.5 * c)),
        wind=(-0.6 * s, 0.0, -0.8),
    )


# E: enciende la llama en la palma; F: la levanta hacia atrás; G: la lanza (y zarpazo cuerpo a cuerpo).
ATK_E = dict(lean=8, hunch=18, twist=-6, head_pitch=-2, bob=0.3,
             foot_r=(-3.4, 0, -2.0), foot_l=(3.2, 0, 3.0), hem_r=(7.6, 6.8),
             hand_r=('root', (-11.0, 44.0, 8.0)), dir_r=(0.0, 0.25, 1.0), palm_r=(0, 1, 0), curl_r=0.4,
             pole_r=(-1.0, -0.7, -0.2),
             hand_l=('root', (7.5, 31.0, 13.0)), dir_l=(0.1, -0.4, 1.0), palm_l=(0, -1, 0.2), curl_l=0.45,
             spread_l=1.4, flame=(2.3, 5), wind=(0.3, 0, -0.8))
ATK_F = dict(lean=3, hunch=15, twist=-20, side=2, head_pitch=4, head_yaw=14, bob=0.6,
             foot_r=(-3.6, 0, -3.0), foot_l=(3.2, 0, 3.5), hem_r=(7.8, 7.0), hem=(0, -0.4),
             hand_r=('root', (-10.0, 50.0, -2.5)), dir_r=(0.0, 1.0, 0.25), palm_r=(0.1, 0.35, 1.0), curl_r=0.45,
             pole_r=(-1.0, -0.8, 0.1),
             hand_l=('root', (6.5, 40.0, 15.0)), dir_l=(0.0, -0.1, 1.0), palm_l=(0, -1, 0), curl_l=0.35,
             spread_l=1.5, flame=(3.0, 9), wind=(0.6, 0.2, -1.4))
ATK_G = dict(lean=22, hunch=22, twist=20, side=-2, head_pitch=6, head_yaw=-12, bob=-0.8,
             foot_r=(-3.2, 0, 4.5), foot_l=(3.4, 0, -4.0), lift_l=0.6, hem_r=(7.8, 7.2), hem=(0, 0.8),
             hand_r=('root', (-2.5, 41.0, 22.0)), dir_r=(0.05, 0.1, 1.0), palm_r=(0.2, -1, 0.3), curl_r=0.15,
             spread_r=1.7, pole_r=(-1.0, -0.6, -0.3),
             hand_l=('root', (9.0, 27.0, -3.0)), curl_l=0.8, wind=(-0.4, 0.2, -2.0), sparks_g=True)
PAIN = dict(lean=-3, hunch=12, twist=8, side=-4, head_pitch=-26, head_roll=10, jaw=1.3, bob=0.5,
            foot_r=(-3.4, 0, -1.5), foot_l=(3.2, 0, 1.6), hem_r=(7.8, 6.8), hem=(0, -0.6),
            hand_r=('root', (-14.5, 39.0, 4.0)), dir_r=(-0.6, 0.6, 0.4), palm_r=(0.2, 0, 1), curl_r=0.3, spread_r=1.5,
            pole_r=(-0.3, -1.0, -0.4),
            hand_l=('root', (13.5, 43.0, 2.0)), dir_l=(0.6, 0.7, 0.3), palm_l=(-0.2, 0, 1), curl_l=0.3, spread_l=1.5,
            pole_l=(0.3, -1.0, -0.4), wind=(0.5, 0.6, -2.4))


# ----------------------------------------------------------------------------- muerte (I-M)
FALL_DIR = nrm((-0.85, 0.0, 0.45))     # cae hacia su derecha (izquierda de la pantalla) y algo adelante


def fall(alpha, slide, lift=0.0, psi=0.0):
    """Marco raíz de un cuerpo que se vuelca alpha grados hacia FALL_DIR, desplazado para seguir centrado."""
    d = FALL_DIR
    R = rot_axis(np.cross((0, 1, 0), d), rad(alpha)) @ rot_y(rad(psi))
    return Frame(-d * slide + V(0, lift, 0), R)


CHEST_STAINS = [('chest', (0.4, 4.0, 3.4), 3.2), ('chest', (-2.0, 1.6, 3.4), 2.2)]


def deaths():
    I = dict(lean=-9, hunch=4, twist=-10, side=5, head_pitch=-36, head_roll=-12, jaw=1.8, bob=1.2,
             foot_r=(-3.4, 0, 0.6), foot_l=(3.4, 0, -1.2), hem_r=(7.8, 7.0), hem=(0, -0.8),
             hand_r=('root', (-12.5, 51.0, 3.0)), dir_r=(-0.3, 1.0, 0.2), palm_r=(0.3, 0, 1), curl_r=0.25, spread_r=1.7,
             pole_r=(-0.6, -1.0, -0.3),
             hand_l=('root', (12.0, 49.0, 1.0)), dir_l=(0.3, 1.0, 0.1), palm_l=(-0.3, 0, 1), curl_l=0.25, spread_l=1.7,
             pole_l=(0.6, -1.0, -0.3), wind=(0.3, 0.8, -2.6), stains=CHEST_STAINS,
             spray=[('chest', (0.3, 5.0, 6.2), 1.5), ('chest', (2.2, 7.0, 9.0), 1.1), ('chest', (-1.6, 8.0, 11.0), 0.9),
                    ('chest', (2.8, 9.5, 12.5), 0.7), ('chest', (-0.5, 3.5, 9.5), 0.8)])
    J = dict(lean=30, hunch=34, twist=14, side=-8, head_pitch=24, head_roll=16, jaw=0.9, bob=-6.0,
             foot_r=(-3.8, 0, 1.6), foot_l=(3.8, 0, -0.6), hem_r=(8.4, 7.6), hem=(0, 0.6), rag=2.6,
             hand_r=('root', (-9.5, 15.0, 9.0)), hand_l=('root', (7.5, 17.0, 11.0)), curl_r=0.9, curl_l=0.9,
             wind=(0.0, 0.0, 0.0), stains=CHEST_STAINS)
    K = dict(bob=-12.5, lean=30, hunch=30, side=-14, twist=10, head_pitch=30, head_roll=26, jaw=0.9,
             foot_r=(-3.8, 0, -9.0), foot_l=(3.8, 0, -8.0), hem_r=(9.0, 8.4), rag=2.6,
             hand_r=('root', (-11.0, 3.0, 8.0)), dir_r=(-0.3, -0.5, 1.0), hand_l=('root', (8.0, 6.0, 10.0)),
             curl_r=0.6, curl_l=0.9, stains=CHEST_STAINS)
    L = dict(root=fall(62, 14, 1.5, psi=60), bob=-5.0, lean=10, hunch=18, side=-4, head_pitch=-14, head_roll=-10,
             jaw=1.2, foot_r=(-4.0, 0, 2.0), foot_l=(4.0, 0, 0.0), hem_r=(8.8, 8.0), rag=2.6,
             hand_r=('root', (-15.0, 40.0, 5.0)), hand_l=('root', (14.0, 36.0, 7.0)), curl_r=0.5, curl_l=0.6,
             spread_r=1.4, spread_l=1.4, stains=CHEST_STAINS, wind=tuple(FALL_DIR * 2 + V(0, 1.5, 0)), hair_fan=1.5,
             tilt=18.0)
    M = dict(root=fall(90, 25, 5.0, psi=118), bob=-1.0, lean=0, hunch=12, side=0, head_pitch=-12, head_roll=-14,
             jaw=1.3, foot_r=(-4.5, 0, -3.5), foot_l=(4.5, 0, -4.0), hem=(0, -2.5), hem_r=(9.0, 8.0), rag=2.8,
             crush=0.4,
             hand_r=('root', (-17.0, 36.0, -2.0)), hand_l=('root', (15.0, 31.0, -1.0)), curl_r=0.6, curl_l=0.7,
             spread_r=1.3, spread_l=1.3, stains=CHEST_STAINS, hair_fan=4.5, tilt=26.0,
             flatten=(np.diag([1, 0.85, 1.0]), V(0, 0, 0), 0.85),
             extra=[Group([Ellipsoid((-8.0, 0.15, 3.0), (15.0, 0.5, 7.0), rot_y(rad(-24)), BLOOD)], name='pool')])
    return [I, J, K, L, M]


# ----------------------------------------------------------------------------- despedazada (N-U)
GIB_T = [0.0, 0.17, 0.31, 0.45, 0.58, 0.72, 0.86, 1.0]
GIB_SQUASH = [1.0, 0.92, 0.78, 0.62, 0.48, 0.34, 0.24, 0.17]
GIB_TILT = [10, 10, 10, 12, 16, 20, 24, 26]      # la cámara sube poco a poco: los restos se ven desde arriba


def _fragments():
    """Trozos que salen despedidos: (tipo, material, tamaño, posición inicial, velocidad, giro)."""
    rng = np.random.default_rng(1611)
    frs = []

    def add(kind, mat, size, y0, n, vx=(10, 30), vy=(30, 70)):
        for _ in range(n):
            ang = rng.uniform(0, 2 * math.pi)
            sp = rng.uniform(*vx)
            p0 = V(rng.uniform(-6, 6), y0 + rng.uniform(-5, 5), rng.uniform(-3, 3))
            v = V(math.cos(ang) * sp, rng.uniform(*vy), math.sin(ang) * sp * 0.45)
            frs.append((kind, mat, size * rng.uniform(0.75, 1.25), p0, v, rng.uniform(-6, 6)))

    add('rag', RAG, 2.4, 34, 4, vx=(16, 38))
    add('rag', RAGB, 2.4, 36, 4, vx=(16, 38))
    add('rag', SHAWL, 2.8, 42, 3, vx=(12, 34))
    add('tuft', HAIR, 2.6, 46, 5, vx=(12, 40), vy=(40, 85))
    add('bone', BONE, 3.0, 38, 4, vx=(14, 36))
    add('blob', FLESH, 1.6, 38, 4, vx=(14, 36))
    add('blob', BLOOD, 1.2, 38, 14, vx=(8, 40), vy=(20, 80))
    add('blob', BLOOD, 1.7, 40, 10, vx=(14, 46), vy=(30, 95))
    frs.append(('head', BONE, 2.8, V(0.5, 46, 6), V(-16, 66, 3), 3.0))
    frs.append(('hand', SKIN, 1.0, V(-6, 34, 4), V(-24, 48, 2), 5.0))
    frs.append(('hand', SKIN, 1.0, V(6, 34, 4), V(26, 44, -3), -4.0))
    return frs


def gib(k):
    t = GIB_T[k]
    if k == 0:
        # N: el impacto le revienta el pecho; sigue en pie gritando.
        N = dict(deaths()[0])
        N['spray'] = list(N['spray']) + [
            ('chest', (-3.0, 3.0, 6.5), 1.7), ('chest', (3.5, 2.0, 6.0), 1.5), ('chest', (0.0, 0.0, 7.5), 1.3),
            ('chest', (-5.0, 6.0, 8.5), 1.0), ('chest', (5.5, 7.0, 9.0), 0.9), ('chest', (1.0, 10.0, 10.5), 0.8)]
        return build(N)

    # O-U: queda la falda, que se desploma; lo demás sale volando y cae.
    sq = GIB_SQUASH[k]
    base = dict(no_torso=True, no_head=True, no_arms=True, eyes=False, legs=k < 4, lean=0.0, hunch=0.0,
                hem_r=(7.6 + 3.0 * (1 - sq), 6.6 + 2.0 * (1 - sq)), crush=0.6 * (1 - sq),
                stains=[('root', (1.0, 26.0 * sq, 4.0), 3.5), ('root', (-2.5, 20.0 * sq, 4.5), 2.5)],
                flatten=(np.diag([1.0, sq, 1.0]), V(0, 0, 0), sq))
    parts, hair, nails = [], [], []
    for kind, mat, size, p0, v, spin in _fragments():
        rest = {'rag': 0.6, 'tuft': 0.8, 'bone': 0.8, 'blob': size * 0.5, 'head': size, 'hand': 0.9}[kind]
        c, landed = _ballistic(p0, v, t, rest)
        Rm = rot_z(spin * min(t, 0.6)) @ rot_x(0.7 * spin * min(t, 0.6))
        if kind == 'rag':
            f = 0.35 if landed else 0.6
            parts.append(Ellipsoid(c, (size * 1.5, size * f, size), Rm, mat))
        elif kind == 'tuft':
            ax = Rm @ V(1, -0.3, 0.2)
            if landed:
                ax = nrm(V(ax[0], 0, ax[2]))
            hair += [RoundCone(c - ax * size, c + ax * size, 1.1, 0.4, HAIR),
                     RoundCone(c - ax * size * 0.6, c + ax * size * 0.9 + V(0, -0.8, 0.6), 0.9, 0.3, HAIR)]
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
        elif kind == 'head':
            # Calavera con la melena blanca todavía pegada.
            parts += [Sphere(c, size, BONE), Ellipsoid(c + V(-0.6, -1.6, 1.2), (1.5, 1.1, 1.4), None, BONE)]
            hd = nrm(Rm @ V(0.4, 0.6, -0.7))
            hair += [Ellipsoid(c + hd * 1.6, (3.0, 2.6, 3.0), Rm, HAIR),
                     RoundCone(c + hd * 2.0, c + hd * 2.0 + V(2.5, -3.5 if not landed else 0.0, -1.0), 1.3, 0.4, HAIR),
                     RoundCone(c + hd * 2.0, c + hd * 1.0 + V(-3.0, -3.0 if not landed else 0.0, 0.5), 1.2, 0.4, HAIR)]
        elif kind == 'hand':
            a = nrm(Rm @ V(1, -0.3, 0.3))
            if landed:
                a = nrm(V(a[0], 0, a[2]))
            hp, hn = claw(c, a, V(0, 1, 0) if landed else Rm @ V(0, 0, 1), 0.8, 1.2)
            parts += [RoundCone(c - a * 4.0, c, 1.0, 0.9, SKIN)] + hp
            nails += hn
    groups, extras = build(base)
    groups.append(Group(parts, k=0.3, name='extra'))
    groups.append(Group(hair, k=0.6, name='extra'))
    groups.append(Group(nails, name='extra'))
    if k >= 4:
        rr = 6.0 + 14.0 * (k - 4) / 4
        groups.append(Group([Ellipsoid((1.0, 0.15, -1.0), (rr, 0.5, rr * 0.42), None, BLOOD)], name='pool'))
    return groups, extras


# ----------------------------------------------------------------------------- bola de fuego (BAL1)
# No rota (lumps …0) y el juego la pinta a pleno brillo: se dibuja en 2D, sin contorno, con un campo de
# «calor» (ruido determinista) que se cuantiza a una rampa de verdes y amarillos de PLAYPAL.
BAL_RAMP = [123, 120, 117, 114, 112, 229, 160, 226, 225]
# Lienzo de cada fotograma = el de Freedoom (mismo punto de apoyo y el centro en el mismo sitio).
BAL_CANVAS = {'A': (15, 15), 'B': (15, 15), 'C': (34, 33), 'D': (40, 35), 'E': (46, 39)}


def fbm2(x, y, scale, seed):
    P = np.column_stack([x.ravel(), y.ravel(), np.full(x.size, 0.37 + seed)])
    n = vnoise(P, scale, seed) * 0.6 + vnoise(P, scale * 2.1, seed + 1) * 0.3 + vnoise(P, scale * 4.3, seed + 2) * 0.1
    return n.reshape(x.shape)


def ball_heat(x, y, frame):
    """Campo de calor de cada fotograma (x, y en píxeles desde el centro, y hacia arriba)."""
    r = np.hypot(x, y)
    th = np.arctan2(y, x)
    if frame in 'AB':
        seed = 3 if frame == 'A' else 8
        rot = 0.0 if frame == 'A' else 1.9
        nang = fbm2(np.cos(th + rot) * 2.2, np.sin(th + rot) * 2.2, 1.0, seed)
        R = 5.0 * (0.72 + 0.6 * nang)
        return 1.12 - r / R + 0.3 * (fbm2(x, y, 0.7, seed + 5) - 0.5)
    rc, w, peak, fill, holes, seed = {'C': (7.0, 4.0, 1.0, 0.9, 0.0, 11),
                                       'D': (10.0, 4.0, 0.9, 0.45, 0.35, 12),
                                       'E': (13.5, 3.4, 0.5, 0.0, 0.6, 13)}[frame]
    nang = fbm2(np.cos(th) * 3.0, np.sin(th) * 3.0, 1.0, seed)
    rr = rc * (0.7 + 0.6 * nang)
    h = peak * np.exp(-((r - rr) / w) ** 2)
    h = np.maximum(h, fill * peak * np.clip(1 - r / rr, 0, 1) * 1.1)
    h *= 0.45 + 1.0 * fbm2(x, y, 0.42, seed + 3)
    h -= holes * (fbm2(x, y, 0.22, seed + 7) > 0.58)
    return h


def ball_sparks(frame):
    """Chispas sueltas: (x, y, nivel de la rampa)."""
    n, r0, r1, lvl, seed = {'A': (3, 5.5, 7.0, 6, 31), 'B': (3, 5.5, 7.0, 6, 32), 'C': (9, 10.0, 15.0, 6, 33),
                            'D': (10, 13.0, 18.0, 5, 34), 'E': (7, 16.0, 20.0, 3, 35)}[frame]
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(r0, r1)
        out.append((math.cos(a) * r, math.sin(a) * r * 0.9, lvl))
    return out


def draw_ball(frame):
    W, H = BAL_CANVAS[frame]
    cx, cy = W / 2, H / 2
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
    for sx, sy, sl in ball_sparks(frame):
        px, py = int(math.floor(cx + sx)), int(math.floor(cy - sy))
        if 0 <= px < W and 0 <= py < H:
            vis[py, px] = True
            lv[py, px] = max(lv[py, px], sl) if vis[py, px] else sl
    pal = render().palarr
    img = np.zeros((H, W, 4), np.uint8)
    img[vis, :3] = pal[np.array(BAL_RAMP)[lv[vis]]].astype(np.uint8)
    img[vis, 3] = 255
    for xx in (0, W - 1):                       # anclas invisibles: construir_pwad conserva el lienzo
        if img[H - 1, xx, 3] == 0:
            img[H - 1, xx] = (0, 0, 0, 1)
    return Image.fromarray(img, 'RGBA')


def lumps():
    out = {}
    for fi, fr in enumerate('ABCD'):
        for a in range(1, 9):
            out[f'TROO{fr}{a}'] = (walk(fi), a)
    for fr, pose in (('E', ATK_E), ('F', ATK_F), ('G', ATK_G), ('H', PAIN)):
        for a in range(1, 9):
            out[f'TROO{fr}{a}'] = (pose, a)
    for fr, pose in zip('IJKLM', deaths()):
        out[f'TROO{fr}0'] = (pose, 1)
    for k, fr in enumerate('NOPQRSTU'):
        out[f'TROO{fr}0'] = (('gib', k), 1)
    for fr in 'ABCDE':
        out[f'BAL1{fr}0'] = (('ball', fr), 0)
    return out


def view_dir(angle, tilt=TILT):
    """Dirección de los rayos de la cámara en coordenadas del modelo (como Render.render)."""
    th = (angle - 1) * math.pi / 4 if angle else 0.0
    return V(0, -math.sin(tilt), -math.cos(tilt)) @ rot_y(-th)


def move_scene(groups, extras, k=1.0, off=(0, 0, 0)):
    """Escala por k y desplaza (P' = k·P + off) toda la escena y los puntos de referencia del gancho."""
    off = V(off)
    for g in groups:
        if g.xf is None:
            g.xf = (np.eye(3) * k, off.copy(), k)
        else:
            A, t, ds = g.xf
            g.xf = (A * k, t * k + off, ds * k)
    extras['eyes'] = [e * k + off for e in extras.get('eyes', [])]
    extras['stains'] = [(c * k + off, r * k) for c, r in extras.get('stains', [])]
    if 'mouth' in extras:
        c, (r0, r1) = extras['mouth']
        extras['mouth'] = (c * k + off, (r0 * k, r1 * k))
    for key in ('flame_core', 'green_light'):
        if key in extras:
            c, r = extras[key]
            extras[key] = (c * k + off, r * k)
    ax = extras.get('axis', (0, 0))
    extras['axis'] = (ax[0] * k + off[0], ax[1] * k + off[2])


def drop_to_bottom(img):
    """Baja el dibujo hasta la última fila del lienzo (cadáveres vistos desde más arriba)."""
    a = np.array(img)
    H = a.shape[0]
    rows = np.nonzero((a[:, :, 3] >= 128).any(1))[0]
    if len(rows) and rows.max() < H - 1:
        sh = H - 1 - rows.max()
        b = np.zeros_like(a)
        b[sh:] = a[:H - sh]
        b[b[:, :, 3] < 128] = 0
        a = b
    for x in (0, a.shape[1] - 1):
        if a[H - 1, x, 3] == 0:
            a[H - 1, x] = (0, 0, 0, 1)
    return Image.fromarray(a, 'RGBA')


def draw(pose, angle):
    if isinstance(pose, tuple) and pose[0] == 'ball':
        return draw_ball(pose[1])
    if isinstance(pose, tuple) and pose[0] == 'gib':
        groups, extras = gib(pose[1])
        tilt = rad(GIB_TILT[pose[1]])
    else:
        groups, extras = build(pose)
        tilt = rad(pose.get('tilt', 10.0))
    move_scene(groups, extras, SCALE)
    if tilt > TILT + 1e-6:
        # Cámara más alta: lo que está en el suelo hacia la cámara bajaría del lienzo; se empuja atrás.
        zf = max(c[2] + r for c, r in (g.model_bound() for g in groups))
        move_scene(groups, extras, 1.0, (0, 0, -max(0.0, zf - 0.8 / math.sin(tilt))))
    extras['view'] = view_dir(angle, tilt)
    R = render(tilt)
    out, depth = R.render(groups, extras, angle)
    img = finish(out, depth, R.palarr, OUTLINE)
    if tilt > TILT + 1e-6:
        img = drop_to_bottom(img)
    return trim(img)


if __name__ == '__main__':
    cli(lumps, draw, sprite_rows('TROO', 'ABCDEFGH', 'IJKLMNOPQRSTU') + [[f'BAL1{f}0' for f in 'ABCDE']])
