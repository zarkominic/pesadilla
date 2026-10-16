#!/usr/bin/env python3
"""saco.py — dibuja POR CÓDIGO al HOMBRE DEL SACO (sustituye al barón del infierno BOSS de Freedoom)
y su bola de fuego verde (BAL7).

Gigantón viejo y deforme, encorvado, con la cabeza calva llena de verrugas hundida entre los hombros,
ojillos que brillan verdes bajo una frente que cuelga, narizota colorada, barba sucia y larga, abrigo
largo de paño pardo con remiendos (abierto por delante de cintura abajo), cuerda de esparto a la
cintura, botas, manazas y un SACO enorme de arpillera a la espalda que sujeta por el cuello por encima
del hombro izquierdo; dentro algo lucha (los bultos cambian de un fotograma a otro).
Ataque: se saca del pecho una brasa VERDE, la levanta como una bola de fuego y la lanza (el mismo
manotazo vale de zarpazo cuerpo a cuerpo).

Técnica: la misma que el resto de criaturas (tools/arte/sdf.py): modelo 3D de primitivas SDF con poses
paramétricas, trazado ortográfico a 4 submuestras, rampas EXACTAS de PLAYPAL, reducción con prioridad a
lo cercano y a lo que brilla, contorno de 1 px. 1 unidad ≈ 1 px; algo más alto y ancho que el barón de
Freedoom (~72 px con el saco).

Fotogramas (info.c, SPR_BOSS):
    A-D  andar (A y B también en reposo) ............. 8 ángulos
    E    se saca la brasa del pecho (A_FaceTarget) .... 8 ángulos
    F    la levanta: bola de fuego verde .............. 8 ángulos
    G    la lanza / zarpazo (A_BruisAttack) ........... 8 ángulos
    H    dolor ........................................ 8 ángulos
    I-O  muerte: cae de rodillas, suelta el saco, que se abre y derrama algo oscuro; O = cadáver
         (de frente, ángulo 0; también hacia atrás en la resurrección).
BAL7 (no es del barón sino suyo: MT_BRUISERSHOT): A-B en vuelo con estela, 8 ángulos reales (Freedoom
los tiene en parejas reflejadas, BAL7A1A5…); C-E explosión, de frente. Se dibuja en 2D (como BAL1 de la
Meiga) con un verde esmeralda más oscuro, núcleo blanco-menta y sin amarillo: no se confunde con la de
la Meiga, y es más grande.

Apoyo: los offsets van EXPLÍCITOS en arte/sprites/offsets_saco.json (este script lo escribe/actualiza):
el eje del cuerpo en el centro del ancho y el suelo del modelo SINK px por debajo del origen en TODOS los
fotogramas y ángulos (los pies no bailan; no depende de los apoyos irregulares de Freedoom). La bola: el
centro a BALL_Z px por encima del origen (como Freedoom), también en la explosión.

Uso (determinista; regenera los 71 PNG BOSS*, los 19 BAL7* y offsets_saco.json; ~2 min con 3 procesos):
    ~/.venvs/pesadilla/bin/python tools/arte/saco.py --salida arte/sprites
    … --solo BOSSA1,BAL7A3      solo esos lumps (offsets_saco.json se actualiza, no se pisa)
    … --hoja hoja.png           además, hoja de contactos ampliada x3 con etiquetas
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdf import (V, nrm, rot_x, rot_y, rot_z, rad, rot_axis, basis, Frame, _len,  # noqa: E402
                 Sphere, Ellipsoid, RoundCone, CappedCone, EllCone, Ring, Group, vnoise, SS,
                 Render, finish, trim, ik, apply_shine, cli, sprite_rows, TILT)
from penitente import hem_cut  # noqa: E402

# ----------------------------------------------------------------------------- materiales
(COAT, LINING, PATCH1, PATCH2, STITCH, MUD, SKIN, SKINL, NOSE, WART, BEARD, BEARDL, EYE, SOCKET,
 MOUTH, TEETH, NAIL, ROPE, PANTS, BOOT, SACK, SACKD, OOZE, FIRE, SPARK, BLOOD, BONE) = range(27)
RAMPS = {
    COAT: [2, 239, 238, 15, 14, 13, 142, 140],    # paño pardo
    LINING: [0, 2, 239, 238],                      # el abrigo por dentro
    PATCH1: [11, 10, 9, 159, 158, 157, 156],       # remiendo de lana verdosa
    PATCH2: [1, 79, 78, 77, 75, 73, 71],           # remiendo ocre
    STITCH: [0, 1, 2],                             # costuras gruesas
    MUD: [7, 2, 239, 238, 237],                    # barro en el bajo
    SKIN: [1, 78, 76, 74, 72, 70, 68, 66, 64],     # piel vieja, curtida y colorada
    SKINL: [1, 158, 156, 154, 152, 117, 115],      # piel iluminada por el fuego verde
    NOSE: [2, 44, 41, 38, 35, 31, 27],             # narizota colorada
    WART: [1, 79, 77, 75, 73, 71],                 # verrugas y manchas
    BEARD: [6, 109, 107, 104, 101, 98, 95, 92],    # barba gris sucia
    BEARDL: [6, 157, 155, 153, 152, 116, 114],     # barba iluminada por el fuego
    EYE: [118, 114, 112],                          # ojillos verdes que brillan
    SOCKET: [0],
    MOUTH: [0, 46],
    TEETH: [149, 147, 145, 144],                   # dientes amarillos
    NAIL: [2, 79, 77, 75, 151, 148],               # uñas negras de cuerno
    ROPE: [151, 150, 148, 146, 144, 128],          # esparto
    PANTS: [8, 7, 6, 5, 111, 109, 107, 105],       # calzón de lana oscura
    BOOT: [8, 2, 239, 238, 237, 236],              # botas
    SACK: [2, 151, 150, 149, 148, 147, 146, 145, 144],   # arpillera
    SACKD: [0, 1, 2, 239, 47, 238],                # lo que rezuma del saco (mojado, oscuro)
    OOZE: [0, 0, 8, 7, 6, 5, 110, 107],             # lo oscuro que se derrama (negro, brillante)
    FIRE: [125, 123, 121, 118, 116, 114, 113, 112, 80],  # fuego verde (de fuera a dentro)
    SPARK: [112],
    BLOOD: [191, 188, 185, 182, 179, 176],
    BONE: [109, 104, 98, 92, 87, 83],
}
EMISSIVE = (EYE, FIRE, SPARK)
OUTLINE = 2
CLOTH = (COAT, PATCH1, PATCH2, STITCH, MUD, LINING)


def materiales(P, mat, inten, nz, nr, spec, lvl_extra, extras):
    """Ajustes propios del Hombre del Saco: pliegues y forro del abrigo, remiendos, barro, arpillera,
    manchas de la piel, barba, ojos, boca, fuego verde y su luz, sangre."""
    ax = extras.get('axis', (0, 0))
    ang = np.arctan2(P[:, 0] - ax[0], P[:, 2] - ax[1])
    # Abrigo: pliegues verticales (más marcados en los faldones) y el forro oscuro por dentro.
    m = mat == COAT
    wy = extras.get('waist_y', 1e9)
    low = P[:, 1] < wy
    inten[m] *= 1 + np.where(low[m], 0.22, 0.12) * np.sin(9 * ang[m] + 2.2 * nz[m])
    if extras.get('lining', True):
        rh = np.column_stack([P[:, 0] - ax[0], P[:, 2] - ax[1]])
        rh /= np.maximum(np.sqrt((rh ** 2).sum(1)), 1e-6)[:, None]
        inward = (nr[:, 0] * rh[:, 0] + nr[:, 2] * rh[:, 1]) < -0.15
        mat[m & low & inward] = LINING
    # Remiendos (en el marco de la parte del cuerpo donde van): zona + costura alrededor.
    for o, R, c, half, pm in extras.get('patches', []):
        q = (P - o) @ R - c
        inside = (np.abs(q[:, 0]) < half[0]) & (np.abs(q[:, 1]) < half[1]) & (np.abs(q[:, 2]) < half[2])
        mm = (mat == COAT) & inside
        edge = np.maximum(np.abs(q[:, 0]) - half[0], np.abs(q[:, 1]) - half[1]) > -0.55
        mat[mm & ~edge] = pm
        mat[mm & edge] = STITCH
    # Barro en el bajo del abrigo y en las botas.
    hy = extras.get('hem_y', -1e9)
    mud = np.isin(mat, (COAT, LINING)) & (P[:, 1] < hy + 2.5 + 3.0 * vnoise(P, 0.6, 5)) & (vnoise(P, 1.7, 6) > 0.45)
    mat[mud] = MUD
    # Arpillera: grano grueso, arrugas que salen del cuello y lo que rezuma por abajo.
    m = mat == SACK
    if m.any():
        inten[m] *= 0.8 + 0.3 * vnoise(P[m], 2.4, 31)
        sn = extras.get('sack_neck')
        if sn is not None:
            c, axv, rfold = sn
            rel = P[m] - c
            al = rel @ axv
            perp = rel - np.outer(al, axv)
            e1 = nrm(np.cross(axv, (0.3, 0.1, 1.0)))
            e2 = np.cross(axv, e1)
            phi = np.arctan2(perp @ e2, perp @ e1)
            fade = np.clip(1 - np.sqrt((perp ** 2).sum(1)) / rfold, 0, 1)
            inten[m] *= 1 + 0.35 * np.sin(7 * phi + 1.5 * nz[m]) * fade
        sb = extras.get('sack_base')
        if sb is not None:
            o, R, hgt = sb
            q = (P - o) @ R
            wet = (mat == SACK) & (q[:, 1] < hgt * (0.55 + 0.9 * vnoise(P, 0.5, 33))) & (vnoise(P, 1.2, 34) > 0.42)
            mat[wet] = SACKD
    # Piel vieja: manchas y rojeces; la calva brilla.
    m = mat == SKIN
    inten[m] *= 0.88 + 0.22 * vnoise(P[m], 1.1, 41)
    spots = m & (vnoise(P, 1.9, 42) > 0.74)
    mat[spots] = WART
    # Barba: mechones en vertical.
    m = mat == BEARD
    st = vnoise(P * np.array([1.0, 0.25, 1.0]), 2.0, 7) * 0.7 + vnoise(P * np.array([1.0, 0.35, 1.0]), 3.9, 8) * 0.3
    inten[m] *= 0.55 + 0.8 * st[m]
    apply_shine(mat, inten, spec, ((SKIN, 0.4, 7), (NOSE, 0.5, 6), (WART, 0.2, 6), (BOOT, 0.35, 8),
                                   (NAIL, 0.5, 8), (OOZE, 0.9, 10), (SACKD, 0.5, 10), (BLOOD, 0.6, 12),
                                   (BONE, 0.3, 8), (TEETH, 0.3, 6)))
    # Ojillos hundidos que brillan.
    for ec in extras.get('eyes', []):
        de = _len(P - ec)
        mm = np.isin(mat, (SKIN, WART, SKINL)) & (de < 1.15)
        mat[mm] = SOCKET
        mm = (mat == SOCKET) & (de < 0.68)
        mat[mm] = EYE
        lvl_extra[mm] = np.where(de[mm] < 0.38, 2, 1)
    # Boca: raja oscura bajo el bigote (abierta: con dientes amarillos arriba).
    mo = extras.get('mouth')
    if mo is not None:
        c, (rx, ry), Rh = mo
        q = (P - c) @ Rh
        e = (q[:, 0] / rx) ** 2 + (q[:, 1] / ry) ** 2 + (q[:, 2] / 2.2) ** 2
        mm = np.isin(mat, (SKIN, BEARD, WART, SKINL, BEARDL)) & (e < 1)
        mat[mm] = MOUTH
        if ry > 0.8:
            tt = mm & (q[:, 1] > ry * 0.35) & (np.mod(q[:, 0] + 0.45, 0.9) > 0.25)
            mat[tt] = TEETH
    # Fuego verde: más caliente en el centro visto desde la cámara.
    fc = extras.get('fire_core')
    m = mat == FIRE
    if fc is not None and m.any():
        c, size = fc
        D = extras['view']
        rel = P[m] - c
        along = rel @ D
        perp = _len(rel - np.outer(along, D))
        hgt = np.maximum(rel[:, 1], 0)
        heat = 1.3 - perp / (size * 1.45) - hgt / (size * 5.0) + 0.3 * (nz[m] - 0.5)
        nf = len(RAMPS[FIRE])
        lvl_extra[m] = np.clip(np.floor(heat * nf), 0, nf - 1)
    # Luz verde del fuego sobre la mano, la cara, la barba y el abrigo.
    gl = extras.get('green_light')
    if gl is not None:
        lp, lr = gl
        rel = lp - P
        dl = np.maximum(_len(rel), 1e-6)
        ndl = np.clip(np.einsum('ij,ij->i', nr, rel / dl[:, None]), 0, 1)
        amt = np.clip(1 - dl / lr, 0, 1) * (0.25 + 0.75 * ndl)
        for src, dst in ((SKIN, SKINL), (WART, SKINL), (NOSE, SKINL), (BEARD, BEARDL)):
            mm = (mat == src) & (amt > 0.5)
            mat[mm] = dst
        mm = np.isin(mat, (SKINL, BEARDL, COAT, PATCH1, PATCH2, SACK, NAIL))
        inten[mm] += amt[mm] * 0.9
    # Manchas de sangre.
    for sc, sr in extras.get('stains', []):
        ds = _len(P - sc)
        mm = np.isin(mat, CLOTH + (SKIN, BEARD, WART)) & (ds < sr * (0.75 + 0.5 * nz))
        mat[mm] = BLOOD


RENDERS = {}


def render(tilt=TILT):
    key = round(tilt, 5)
    if key not in RENDERS:
        RENDERS[key] = Render(RAMPS, hook=materiales, level_mats=(EYE, FIRE), emissive=EMISSIVE,
                              no_light=(FIRE, SPARK, EYE, SOCKET, MOUTH), tilt=tilt)
    return RENDERS[key]


# ----------------------------------------------------------------------------- modelo
HIP_Y = 28.0
LEG_X = 5.6
THIGH, SHIN, ANKLE = 14.0, 13.0, 2.9
UPPER_ARM, FOREARM = 14.5, 13.5
CHEST_AT = 13.0                    # pecho respecto a la cintura (marco «up»)
SHOULDER = (13.0, 9.0, -1.0)       # hombro izquierdo en el marco del pecho (x+ = izquierda del personaje)
NECK = (0.0, 14.0, 6.5)
HS = 1.22                          # escala de la cabeza (grande: se lee de lejos)
HEM_Y = 10.0
WAIST_R = (10.6, 9.2)
L_PX = 5                           # el modelo se traza L_PX px más alto: nada se corta por abajo
SINK = 2                           # el suelo del modelo queda SINK px por debajo del origen (pies asentados)


def paw(T, along, palm, curl=0.6, spread=1.0, thumb=1.0, mat=SKIN):
    """Manaza: palma, cuatro dedos gordos con uñas negras y pulgar.
    along: hacia los dedos; palm: normal de la palma; thumb: lado del pulgar (+1/-1 respecto a s)."""
    a = nrm(along)
    n = V(palm) - a * (V(palm) @ a)
    n = nrm(n) if np.linalg.norm(n) > 1e-6 else nrm(np.cross(a, (1, 0, 0)))
    s = nrm(np.cross(a, n))
    parts = [Ellipsoid(T + a * 0.8, (2.7, 1.6, 2.8), basis(a, n), mat)]
    nails = []
    for k, off in enumerate((-1.5, -0.5, 0.5, 1.5)):
        ln = (0.8, 1.0, 0.95, 0.75)[k]
        base = T + a * 2.9 + s * off * 1.05
        d1 = nrm(a + s * off * 0.18 * spread + n * curl * 0.45)
        j1 = base + d1 * 2.1 * ln
        d2 = nrm(d1 + n * curl * 0.9)
        j2 = j1 + d2 * 1.8 * ln
        d3 = nrm(d2 + n * curl * 0.6)
        parts += [RoundCone(base, j1, 0.85, 0.75, mat), RoundCone(j1, j2, 0.75, 0.62, mat)]
        nails.append(RoundCone(j2, j2 + d3 * 0.9, 0.55, 0.3, NAIL))
    tb = T + a * 0.5 + s * thumb * 2.1
    dth = nrm(a * 0.7 + s * thumb * 0.5 + n * (0.3 + curl * 0.4))
    parts.append(RoundCone(tb, tb + dth * 2.6, 0.95, 0.75, mat))
    nails.append(RoundCone(tb + dth * 2.6, tb + dth * 3.3, 0.5, 0.3, NAIL))
    return parts, nails


def fire_parts(core, size, seed):
    """Bola de fuego verde en la mano: núcleo, lenguas hacia arriba y chispas sueltas."""
    rng = np.random.default_rng(seed)
    parts = [Sphere(core, size, FIRE)]
    for k in range(6):
        a = 2 * math.pi * k / 6 + rng.uniform(-0.4, 0.4)
        off = V(math.cos(a), 0, math.sin(a)) * size * 0.45
        h = size * rng.uniform(1.4, 2.3)
        b0 = core + off + V(0, size * 0.45, 0)
        tip = core + off * 1.6 + V(0, h, 0) + V(rng.uniform(-0.6, 0.6), 0, rng.uniform(-0.6, 0.6)) * size * 0.45
        parts.append(RoundCone(b0, tip, size * 0.48, 0.25, FIRE))
    sparks = []                               # por encima de las lenguas: delante de la bola harían contorno
    for k in range(4):
        a = 2 * math.pi * (k + rng.uniform(-0.3, 0.3)) / 4
        rr = size * rng.uniform(0.5, 1.4)
        sparks.append(Sphere(core + V(math.cos(a) * rr, rng.uniform(2.6, 3.6) * size, math.sin(a) * rr), 0.55, SPARK))
    return parts, sparks


# Bultos del saco (algo que lucha dentro): (ángulo alrededor del eje en grados — 0 = hacia su espalda,
# 180 = hacia fuera, 90 = a su izquierda —, altura relativa 0-1, tamaño, tipo).
BULGES = {
    'A': [(205, 0.55, 3.4, 'blob'), (115, 0.70, 2.7, 'hand')],
    'B': [(188, 0.62, 3.8, 'blob'), (250, 0.35, 2.5, 'blob')],
    'C': [(165, 0.50, 3.4, 'blob'), (100, 0.58, 2.8, 'hand')],
    'D': [(222, 0.70, 3.1, 'hand'), (140, 0.32, 2.7, 'blob')],
    'E': [(182, 0.52, 3.0, 'blob'), (240, 0.66, 2.6, 'hand')],
    'F': [(232, 0.60, 3.6, 'hand'), (130, 0.40, 2.8, 'blob')],
    'G': [(150, 0.46, 3.3, 'blob'), (205, 0.75, 2.5, 'blob')],
    'H': [(198, 0.62, 4.2, 'hand'), (118, 0.40, 3.4, 'blob'), (255, 0.70, 2.6, 'blob')],
    'I': [(180, 0.55, 4.0, 'hand'), (110, 0.45, 3.2, 'blob')],
    'J': [(160, 0.50, 3.6, 'blob'), (230, 0.65, 3.0, 'hand')],
    'K': [(200, 0.55, 3.0, 'blob')],
    'L': [],
}
SACK_LO = ((0.0, 10.0, 0.0), (11.0, 10.2, 9.0))      # cuerpo del saco (centro, radios) en su marco
SACK_HI = ((0.5, 20.0, 1.0), (9.0, 8.0, 7.5))


def sack_body(F, bulges, deflate=0.0):
    """Saco de arpillera en su marco F (origen en el fondo, y' hacia la boca, z' hacia la espalda del
    que lo carga). deflate (0-1): vacío y aplastado (z' local hacia el suelo cuando está tirado)."""
    M = F.M()
    sq = V(1.0 + 0.12 * deflate, 1.0 - 0.1 * deflate, 1.0 - 0.6 * deflate)
    parts = [Ellipsoid(F.p(SACK_LO[0]), V(SACK_LO[1]) * sq, M, SACK),
             Ellipsoid(F.p(SACK_HI[0]), V(SACK_HI[1]) * sq, M, SACK),
             RoundCone(F.p((1.0, 26.5, 2.0)), F.p((1.5, 30.0, 3.0)), 5.0, 3.2 * (1 - 0.3 * deflate), SACK)]
    c0, r0 = V(SACK_LO[0]), V(SACK_LO[1]) * sq
    for th, h, size, kind in bulges:
        u = V(math.sin(rad(th)), (h - 0.5) * 1.6, math.cos(rad(th)))
        u = nrm(u)
        s = c0 + u * r0
        nn = nrm(u / r0)
        size *= 1.15
        if kind == 'blob':                                        # una rodilla, una cabeza…
            parts.append(Sphere(F.p(s + nn * size * 0.05), size, SACK))
        else:                                                     # una mano que empuja desde dentro
            t1 = nrm(np.cross(nn, (0, 1, 0)))
            t2 = np.cross(nn, t1)
            parts.append(Ellipsoid(F.p(s + nn * size * 0.1), (size * 0.9, size * 1.0, size * 0.65),
                                   M @ basis(nn, t2), SACK))
            for k in range(4):
                fp = s + t2 * size * 1.15 + t1 * (k - 1.5) * size * 0.45 + nn * size * 0.25
                parts.append(Sphere(F.p(fp), size * 0.38, SACK))
    return parts


def sack_ground(F, deflate=0.0, opening=0.0, bulges=()):
    """Saco tirado en el suelo, en su marco F (x' del fondo a la boca, y' arriba, suelo en y' = 0):
    barriga aplastada por el peso, cuello atado y caído (opening = 0) o boca abierta con lo de dentro
    asomando; deflate (0-1): se vacía. bulges: [(x', z', radio)] bultos que aún se mueven arriba.
    → (cuerpo, cuello, cuerda, interior)."""
    M = F.M()
    k = 1 - 0.55 * deflate
    body = [Ellipsoid(F.p((8.0, 7.4 * k, 0.0)), (9.8, 7.4 * k, 9.2 + 1.5 * deflate), M, SACK),
            Ellipsoid(F.p((15.5, 6.0 * k, 0.8)), (7.2, 6.0 * k, 7.4 + 1.2 * deflate), M, SACK),
            Ellipsoid(F.p((2.5, 5.6 * k, -1.8)), (5.8, 5.6 * k, 6.8), M, SACK)]
    for x, z, r in bulges:
        body.append(Sphere(F.p((x, 2 * 7.0 * k - 0.6 * r, z)), r, SACK))
    a = F.p((20.5, 4.4 * k + 0.6, 1.0))
    rope, inside = [], []
    if opening <= 0:
        b, c = F.p((26.0, 2.6, 2.2)), F.p((29.0, 2.5, 2.8))
        neck = [RoundCone(a, b, 3.8, 2.2, SACK), RoundCone(b, c, 2.0, 3.0, SACK),
                Sphere(c + F.d((0.6, 0.6, 0.4)), 1.4, SACK), Sphere(c + F.d((0.5, -0.4, -1.0)), 1.3, SACK)]
        rope = [Ring(Frame(b, M @ rot_z(rad(90))), 2.3, 2.3, 0.7, ROPE),
                RoundCone(b + F.d((0, -1.5, 1.8)), F.p((24.0, 0.6, 7.0)), 0.6, 0.55, ROPE)]
    else:
        r1 = 3.6 + 2.6 * opening
        mc = F.p((24.5 + opening, 0.4 + r1 * 0.85, 1.5))
        neck = [CappedCone(a, mc, 4.2, r1, SACK),
                Ring(Frame(mc, M @ rot_z(rad(90))), r1, r1 * 0.85, 0.75, SACK)]
        inside = [Ellipsoid(mc - F.d((0.4, 0, 0)), (0.9, r1 * 0.78, r1 * 0.68), M, OOZE)]
        rope = [RoundCone(F.p((27.0, 0.6, -3.0)), F.p((31.0, 0.6, -6.5)), 0.6, 0.55, ROPE),
                RoundCone(F.p((27.0, 0.6, -3.0)), F.p((29.5, 0.6, 2.5)), 0.6, 0.55, ROPE)]
    return body, neck, rope, inside


DEFAULT = dict(
    root=None, bob=0.0, lean=12.0, hunch=18.0, twist=0.0, side=0.0,
    head_pitch=-6.0, head_yaw=0.0, head_roll=0.0, jaw=0.0,
    foot_r=(-6.5, 0, 1.0), foot_l=(6.5, 0, -1.0), lift_r=0.0, lift_l=0.0, kneel=None,
    hem=(0.0, 0.0), hem_r=(14.5, 12.5),
    hand_r=('root', (-16.0, 24.0, 5.5)), dir_r=None, palm_r=None, curl_r=0.8, pole_r=None, spread_r=1.0,
    hand_l='sack', dir_l=None, palm_l=None, curl_l=1.25, pole_l=None, spread_l=1.0,
    grip=(10.5, 13.0, 8.5),
    sack='back', sack_at=(4.0, 1.5, -12.0), sack_swing=(0.0, 0.0, 0.0), sack_tilt=8.0, sack_roll=0.0,
    sack_frame=None, sack_open=0.0, deflate=0.0, bulges='A',
    fire=None, sparks_g=False, beard_wind=(0.0, 0.0, 0.0),
    stains=(), spray=(), extra=(), flatten=None, tilt=10.0, lift_px=L_PX,
    eyes=True, lining=True,
)


def build(pose):
    p = dict(DEFAULT)
    p.update(pose)
    tilt = rad(p['tilt'])
    base = Frame((0, p['lift_px'] / math.cos(tilt), 0))          # suelo del mundo (subido)
    root = base * (p['root'] or Frame())
    groups = []
    extras = {'eyes': [], 'stains': [], 'patches': [], 'lining': p['lining']}

    up = root * Frame((0, HIP_Y + p['bob'], 0),
                      rot_y(rad(p['twist'])) @ rot_x(rad(p['lean'])) @ rot_z(rad(p['side'])))
    chest = up * Frame((0, CHEST_AT, 0), rot_x(rad(p['hunch'])))
    head = chest * Frame(NECK, rot_x(rad(-(p['lean'] + p['hunch']) * 0.8 + p['head_pitch']))
                         @ rot_y(rad(p['head_yaw'])) @ rot_z(rad(p['head_roll'])))

    def where(fr, pt):
        return {'up': up.p, 'chest': chest.p, 'root': root.p, 'head': head.p, 'world': base.p}.get(fr, V)(pt)

    # --- piernas: calzón y botas (de rodillas: espinillas en el suelo y puntas hacia atrás)
    upv = root.d((0, 1, 0))
    for sx, foot, lift, ki in ((-1, p['foot_r'], p['lift_r'], 0), (1, p['foot_l'], p['lift_l'], 1)):
        legs, boots = [], []                   # un grupo por pierna y por bota (mejor descarte de rayos)
        hipj = up.p((LEG_X * sx, -2.0, 0.0))
        if p['kneel'] is not None:
            kz = p['kneel'][ki]
            knee = root.p((LEG_X * sx * 1.1, 3.2, kz))
            ank = root.p((LEG_X * sx * 1.15, 3.0, kz - SHIN + 0.5))
            back = root.d((0, 0, -1))
            legs += [RoundCone(hipj, knee, 4.4, 3.5, PANTS), RoundCone(knee, ank, 3.4, 2.7, PANTS)]
            boots += [RoundCone(ank + back * -4.5, ank, 3.1, 2.8, BOOT),
                      RoundCone(ank - back * 0.8, ank + back * 5.0 - upv * 1.4, 2.4, 1.8, BOOT)]
            groups.append(Group(legs, k=1.0, name='legs'))
            groups.append(Group(boots, k=0.6, name='boots'))
            continue
        ank = root.p(V(foot) + (0, ANKLE + lift, 0))
        knee = ik(hipj, ank, THIGH, SHIN, root.d((0, 0.2, 1)))
        sd = nrm(ank - knee)
        fwd = root.d(nrm((0.12 * sx, -0.05 if lift == 0 else -0.35, 1)))
        legs += [RoundCone(hipj, knee, 4.4, 3.5, PANTS), RoundCone(knee, ank, 3.4, 2.7, PANTS)]
        boots += [RoundCone(ank - sd * 6.0, ank, 3.1, 2.85, BOOT),
                  CappedCone(ank - sd * 6.6, ank - sd * 5.2, 3.6, 3.2, BOOT),             # vuelta de la caña
                  RoundCone(ank - fwd * 1.6 - upv * 0.6, ank + fwd * 5.6 - upv * 1.0, 2.4, 2.0, BOOT)]
        groups.append(Group(legs, k=1.0, name='legs'))
        groups.append(Group(boots, k=0.6, name='boots'))

    # --- faldones del abrigo: casca abierta por delante, bajo raído
    hk = (HIP_Y + p['bob']) / HIP_Y
    hemO = root.p((p['hem'][0], HEM_Y * hk, p['hem'][1]))
    waist = up.p((0, 1.5, 0.5))
    axis = waist - hemO
    L = float(np.linalg.norm(axis))
    ya = axis / L
    xa = nrm(np.cross(ya, root.d((0, 0, 1))))
    Fsk = Frame(hemO, np.column_stack([xa, ya, np.cross(xa, ya)]))
    hr = V(p['hem_r'])
    outer = EllCone(Fsk, L, hr, WAIST_R, COAT)
    inner = EllCone(Fsk, L + 2.0, hr - 1.5, V(WAIST_R) - 1.5, COAT)
    hcut = hem_cut(Fsk, base=1.2, rag=1.3)

    def skirt_cut(P, Fsk=Fsk, L=L, inner=inner, hcut=hcut):
        q = Fsk.to_local(P)
        t = np.clip(q[:, 1] / L, 0, 1)
        w = 0.4 + 4.0 * (1 - t) ** 1.3
        d_open = np.maximum(np.abs(q[:, 0]) - w, -q[:, 2])
        return np.maximum(np.maximum(hcut(P), -inner.sdf(P)), -d_open)
    groups.append(Group([outer], cut=skirt_cut, name='skirt'))
    extras['waist_y'] = waist[1] - 1.0
    extras['hem_y'] = hemO[1]
    extras['patches'].append((Fsk.o, Fsk.R, V(-12.5, 7.0, 2.5), (2.2, 3.2, 3.0), PATCH2))   # faldón derecho
    extras['patches'].append((Fsk.o, Fsk.R, V(5.0, 6.0, -11.5), (2.6, 2.6, 2.2), PATCH1))   # faldón, atrás

    # --- torso: barriga, pecho enorme, joroba, hombros y cuello del abrigo subido
    torso = [Ellipsoid(up.p((0, 4.5, 1.0)), (11.0, 8.5, 9.5), up.M(), COAT),
             Ellipsoid(chest.p((0, 4.5, 0.5)), (13.5, 10.0, 10.5), chest.M(), COAT),
             Ellipsoid(chest.p((0, 8.0, -5.5)), (10.5, 7.5, 7.0), chest.M(), COAT),
             Ellipsoid(chest.p((0, 12.3, 3.2)), (8.0, 3.2, 7.4), chest.M(rot_x(rad(-15))), COAT)]
    for sx in (-1, 1):
        torso.append(Sphere(chest.p((SHOULDER[0] * sx, SHOULDER[1], SHOULDER[2])), 4.8, COAT))
    groups.append(Group(torso, k=3.0, name='torso'))
    extras['patches'].append((chest.o, chest.R, V(-6.5, 3.5, 9.5), (2.8, 2.6, 2.6), PATCH1))   # pecho derecho
    extras['patches'].append((chest.o, chest.R, V(7.5, -0.5, 8.0), (2.4, 3.0, 3.0), PATCH2))   # pecho izquierdo
    extras['patches'].append((chest.o, chest.R, V(-4.0, 7.0, -10.5), (3.0, 3.0, 2.6), PATCH2))  # espalda

    # --- cuerda de esparto a la cintura, con nudo y cabos
    belt = [Ring(Frame(up.p((0, 0.8, 0.8)), up.M()), WAIST_R[0] - 0.2, WAIST_R[1] - 0.1, 1.05, ROPE)]
    knot = up.p((-4.5, 0.6, 9.4))
    belt += [Sphere(knot, 1.4, ROPE),
             RoundCone(knot, root.p((-5.6, HIP_Y + p['bob'] - 8.5, 0)) + up.d((0, 0, 10.5)), 0.9, 0.7, ROPE),
             RoundCone(knot, root.p((-3.6, HIP_Y + p['bob'] - 7.0, 0)) + up.d((0, 0, 10.6)), 0.85, 0.7, ROPE)]
    groups.append(Group(belt, k=0.4, name='belt'))

    # --- cabeza calva con verrugas, frente que cuelga, ojillos, narizota, orejas
    def hp(q):
        return head.p(V(q) * HS)
    H = head.M()
    jaw = p['jaw']
    hd = [Ellipsoid(hp((0, 5.0, -0.8)), V(5.3, 5.6, 5.8) * HS, H, SKIN),
          Ellipsoid(hp((0, 2.0, 1.8)), V(5.0, 4.4, 4.6) * HS, H, SKIN),
          Ellipsoid(hp((0, 4.6, 4.3)), V(4.4, 1.3, 1.7) * HS, H, SKIN),
          Sphere(hp((0, 2.2, 6.4)), 1.75 * HS, NOSE),
          RoundCone(hp((0, 4.3, 5.6)), hp((0, 2.6, 6.5)), 0.95 * HS, 1.35 * HS, NOSE)]
    for sx in (-1, 1):
        hd.append(Ellipsoid(hp((5.3 * sx, 3.0, 0.0)), V(1.0, 2.3, 1.6) * HS, H @ rot_z(rad(-12 * sx)), SKIN))
    hg = Group(hd, k=0.7, name='head')

    def surf(g, a, dirv, hi=9.0):
        lo = 0.0
        for _ in range(30):
            mid = (lo + hi) / 2
            if g.eval((a + dirv * mid)[None])[0][0] < 0:
                lo = mid
            else:
                hi = mid
        return a + dirv * lo
    warts = []
    for d, r in (((0.35, 0.9, 0.3), 0.85), ((-0.5, 0.75, -0.35), 0.75), ((0.7, 0.45, 0.2), 0.65),
                 ((-0.15, 0.55, 0.8), 0.6), ((0.1, 0.95, -0.6), 0.7), ((-0.75, 0.3, 0.55), 0.6)):
        c = hp((0, 4.0, -0.3))
        s = surf(hg, c, head.d(nrm(d)))
        warts.append(Sphere(s, r * HS, WART))
    warts.append(Sphere(surf(hg, hp((0, 2.4, 5.0)), head.d(nrm((0.6, 0.2, 0.75)))), 0.55, WART))   # en la nariz
    groups.append(Group(hd + warts, k=0.7, name='head'))
    hg = groups[-1]
    if p['eyes']:
        for sx in (-1, 1):
            extras['eyes'].append(surf(hg, hp((1.85 * sx, 3.7, 2.5)), head.d(nrm((0.12 * sx, 0.05, 1)))))

    # --- barba sucia y larga (cae con la gravedad, por delante del pecho), bigote y greñas
    body = [g for g in groups if g.name == 'torso']

    def push(q, clear=1.4):
        q = V(q)
        f = lambda x: min(g.eval(x[None])[0][0] for g in body)  # noqa: E731
        for _ in range(10):
            d = f(q)
            if d >= clear:
                break
            gr = V([f(q + e) - f(q - e) for e in np.eye(3) * 0.05])
            q = q + nrm(gr) * (clear - d + 0.15)
        return q
    J = head * Frame(V(0, 1.2, 2.0) * HS, rot_x(rad(jaw * 14)))

    def jp(q):
        return J.p(V(q) * HS)
    W = V(p['beard_wind'])
    beard = [Ellipsoid(jp((0, -1.0, 1.2)), V(4.7, 3.1, 3.4) * HS, J.M(), BEARD),
             Ellipsoid(hp((0, 1.0, 5.6)), V(3.0, 0.95, 1.1) * HS, H @ rot_x(rad(8)), BEARD)]
    for sx in (-1, 1):
        beard.append(RoundCone(hp((2.4 * sx, 1.0, 5.4)), hp((3.2 * sx, -1.2, 5.0)), 0.8 * HS, 0.45 * HS, BEARD))   # puntas del bigote
    for dx, ln, r in ((-2.8, 7.0, 1.4), (-1.1, 10.0, 1.8), (0.9, 11.5, 1.8), (2.6, 8.0, 1.5), (0.0, 6.5, 2.3)):
        a = jp((dx, -2.2, 2.4))
        m = push(a + V(dx * 0.15, -ln * 0.55, 0.9) + W * 0.4)
        t = push(m + V(dx * 0.12, -ln * 0.45, -0.1) + W)
        beard += [RoundCone(a, m, r, r * 0.8, BEARD), RoundCone(m, t, r * 0.8, 0.4, BEARD)]
    for sx in (-1, 1):                                          # greñas ralas encima de las orejas
        a = hp((4.6 * sx, 6.0, -2.5))
        m = push(a + V(1.0 * sx, -4.5, -0.8) + W * 0.3)
        t = push(m + V(0.4 * sx, -4.0, 0.3) + W * 0.6)
        beard += [RoundCone(a, m, 0.95, 0.7, BEARD), RoundCone(m, t, 0.7, 0.35, BEARD)]
    groups.append(Group(beard, k=0.8, name='beard'))
    extras['mouth'] = (hp((0, 0.15 - 0.55 * jaw, 5.2)), ((1.7 + 0.35 * jaw) * HS, (0.3 + 1.1 * jaw) * HS), H)

    # --- saco: a la espalda sujeto por el cuello por encima del hombro izquierdo ('back'), suelto y
    #     resbalando ('loose') o tirado en el suelo (dict con el marco y cuánto se ha abierto y vaciado)
    grip_pt = None
    bl = BULGES.get(p['bulges'], []) if isinstance(p['bulges'], str) else p['bulges']
    if p['sack'] in ('back', 'loose'):
        sw = V(p['sack_swing'])
        sackF = Frame(up.p(p['sack_at']) + sw,
                      root.R @ rot_y(rad(p['twist'])) @ rot_x(rad(p['sack_tilt'])) @ rot_z(rad(p['sack_roll'])))
        groups.append(Group(sack_body(sackF, bl, p['deflate']), k=2.6, name='sack'))
        extras['sack_base'] = (sackF.o, sackF.R, 9.0)
        n0 = sackF.p((1.4, 29.0, 3.0))
        n1 = chest.p((11.5, 14.8, -2.0))
        if p['sack'] == 'back':
            grip_pt = chest.p(p['grip'])
            n2 = grip_pt
            n3 = n2 + nrm(n2 - n1) * 3.2 + V(0, -1.6, 0)
            neck = [RoundCone(n0, n1, 3.2, 2.5, SACK), RoundCone(n1, n2, 2.5, 2.0, SACK),
                    RoundCone(n2, n3, 1.8, 2.7, SACK)]
        else:                                                       # el cuello cuelga suelto del hombro
            n2 = n1 + V(0.8, -5.5, 2.5)
            n3 = n2 + V(0.3, -2.5, 0.8)
            neck = [RoundCone(n0, n1, 3.2, 2.5, SACK), RoundCone(n1, n2, 2.5, 2.1, SACK),
                    RoundCone(n2, n3, 2.0, 2.8, SACK)]
        nax = nrm(n1 - n0)
        groups.append(Group(neck, k=1.0, name='sack_neck'))
        tie = n0 + nax * 0.6
        groups.append(Group([Ring(Frame(tie, basis(nax, (0, 0, 1)) @ rot_x(rad(90))), 3.0, 3.0, 0.8, ROPE)],
                            name='sack_rope'))
        extras['sack_neck'] = (n0 - nax * 2.0, nax, 13.0)
    elif isinstance(p['sack'], dict):
        sg = p['sack']
        F = base * sg['frame']
        body, neck, rope, inside = sack_ground(F, sg.get('deflate', 0.0), sg.get('open', 0.0), bl)
        groups.append(Group(body, k=2.2, name='sack'))
        groups.append(Group(neck, k=1.0, name='sack_neck'))
        if rope:
            groups.append(Group(rope, k=0.3, name='sack_rope'))
        if inside:
            groups.append(Group(inside, k=0.5, name='sack_in'))
        extras['sack_base'] = (F.o, F.R @ rot_z(rad(-90)), 8.0)       # «fondo» del saco: x' pequeño
        extras['sack_neck'] = (F.p((21.0, 4.0, 1.0)), F.d((1, 0, 0)), 11.0)

    # --- brazos: mangas del abrigo con el puño vuelto; manazas
    for sx, sfx in ((-1, 'r'), (1, 'l')):
        sleeves, skin, nails = [], [], []      # un grupo por brazo: se descartan mejor los rayos lejanos
        S = chest.p((SHOULDER[0] * sx, SHOULDER[1], SHOULDER[2]))
        spec = p['hand_' + sfx]
        if spec == 'sack':
            if grip_pt is None:
                continue
            T = grip_pt + chest.d((0.6, 0.6, -0.4))
            along = p['dir_' + sfx] or chest.d(nrm((-0.55, 0.35, 0.75)))
            palm = p['palm_' + sfx] or chest.d((-1, -0.4, -0.3))
        else:
            T = where(*spec)
            along = None
            palm = None
        pole = p['pole_' + sfx]
        pole = up.d((0.6 * sx, -0.7, -0.5)) if pole is None else nrm(V(pole))
        E = ik(S, T, UPPER_ARM, FOREARM, pole)
        fa = nrm(T - E)
        if along is None:
            along = fa if p['dir_' + sfx] is None else nrm(V(p['dir_' + sfx]))
        if palm is None:
            palm = V(-sx, 0, -0.4) if p['palm_' + sfx] is None else V(p['palm_' + sfx])
        cuff = T - fa * 3.2
        sleeves += [RoundCone(S, E, 5.0, 4.0, COAT), RoundCone(E, cuff, 4.3, 3.6, COAT),
                    CappedCone(cuff - fa * 0.8, cuff + fa * 1.0, 3.7, 4.3, COAT)]
        skin.append(RoundCone(cuff, T, 2.7, 2.4, SKIN))
        hp_, hn = paw(T, along, palm, p['curl_' + sfx], p['spread_' + sfx], thumb=-sx)
        skin += hp_
        nails += hn
        if sfx == 'r':
            if p['fire']:
                size, seed = p['fire']
                core = T + nrm(along) * 1.0 + nrm(palm) * (1.4 + size * 0.9)
                fparts, sparks = fire_parts(core, size, seed)
                groups.append(Group(fparts, k=0.5, name='fire'))
                groups.append(Group(sparks, name='sparks'))
                extras['fire_core'] = (core, size)
                extras['green_light'] = (core, size * 4.0 + 7.0)
            if p['sparks_g']:
                rng = np.random.default_rng(23)
                fwd = nrm(along)
                sp = [Sphere(T + fwd * rng.uniform(4, 11) + V(rng.uniform(-2.5, 2.5), rng.uniform(-1.5, 3.0),
                                                                rng.uniform(-1.5, 1.5)), 0.6, SPARK) for _ in range(6)]
                groups.append(Group(sp, name='sparks'))
                extras['green_light'] = (T + fwd * 3.0, 14.0)
        groups.append(Group(sleeves, k=1.0, name='sleeves'))
        groups.append(Group(skin, k=0.5, name='hands'))
        groups.append(Group(nails, name='nails'))

    # --- sangre, charcos y añadidos
    extras['stains'] = [(where(fr, pt), r) for fr, pt, r in p['stains']]
    if p['spray']:
        groups.append(Group([Sphere(where(fr, pt), r, BLOOD) for fr, pt, r in p['spray']], name='spray'))
    for g in p['extra']:
        groups.append(g(base) if callable(g) else g)
    if p['flatten'] is not None:
        A, t, ds = p['flatten']
        fy = base.o[1]
        for g in groups:
            if g.name not in ('extra', 'pool', 'spray', 'sack', 'sack_neck', 'sack_rope', 'sack_in'):
                g.xf = (A, V(t) + V(0, fy, 0) - A @ V(0, fy, 0), ds)
        extras['eyes'] = []
        extras.pop('mouth', None)
    ax = root.p((0, 0, 0))
    extras['axis'] = (ax[0], ax[2])
    return groups, extras


# ----------------------------------------------------------------------------- poses
def walk(i):
    """Andar pesado de gigantón: balanceo, el brazo derecho cuelga y oscila, el saco bota."""
    a = i * math.pi / 2
    c, s = math.cos(a), math.sin(a)
    return dict(
        bob=0.3 - 1.4 * abs(c), twist=-5 * c, side=2.2 * s, lean=12 + 1.5 * abs(c),
        head_pitch=-6 + 2 * abs(c), head_roll=-2.5 * s, head_yaw=3 * c,
        foot_r=(-6.5, 0, 1.0 + 6.0 * c), lift_r=3.0 * max(0, -s),
        foot_l=(6.5, 0, 1.0 - 6.0 * c), lift_l=3.0 * max(0, s),
        hem=(1.0 * s, 0.6 * c), hem_r=(14.5 + 0.5 * abs(c), 12.5 + 0.8 * abs(c)),
        hand_r=('root', (-16.0, 23.5 + 1.0 * abs(c), 5.5 - 6.5 * c)),
        sack_swing=(0.6 * s, 0.9 * abs(c) - 0.5, -0.3 * abs(c)), sack_roll=-2.5 * s,
        beard_wind=(-0.5 * s, 0.0, -0.4 * abs(c)), bulges='ABCD'[i],
    )


# E: se saca la brasa verde del pecho; F: la levanta (bola de fuego); G: la lanza (y zarpazo).
ATK_E = dict(lean=14, hunch=20, twist=12, head_pitch=-10, head_yaw=-6, bob=-0.4, jaw=0.3,
             foot_r=(-6.8, 0, -1.5), foot_l=(6.5, 0, 3.0),
             hand_r=('chest', (-9.0, 2.5, 12.5)), dir_r=(0.6, 0.1, 0.8), palm_r=(0.3, 1.0, 0.3), curl_r=0.9,
             pole_r=(-1.0, -0.5, -0.3), fire=(2.5, 5), bulges='E')
ATK_F = dict(lean=4, hunch=14, twist=-22, side=3, head_pitch=4, head_yaw=10, bob=0.4, jaw=0.7,
             foot_r=(-7.0, 0, -3.5), foot_l=(6.5, 0, 4.0), hem_r=(15.0, 13.0), hem=(0, -0.6),
             hand_r=('root', (-14.0, 66.0, -6.0)), dir_r=(0.0, 1.0, 0.3), palm_r=(0.2, 0.3, 1.0), curl_r=0.45,
             pole_r=(-1.0, -0.6, 0.2), fire=(4.0, 9), sack_swing=(0.5, 0.8, 0.5), bulges='F',
             beard_wind=(0.3, 0.0, -0.8))
ATK_G = dict(lean=24, hunch=22, twist=24, side=-2, head_pitch=2, head_yaw=-12, bob=-1.0, jaw=1.0,
             foot_r=(-6.5, 0, 6.0), foot_l=(6.8, 0, -5.0), lift_l=0.8, hem_r=(15.0, 13.0), hem=(0, 1.0),
             hand_r=('root', (-4.0, 44.0, 26.0)), dir_r=(0.05, 0.05, 1.0), palm_r=(0.2, -1.0, 0.25), curl_r=0.15,
             spread_r=1.6, pole_r=(-1.0, -0.6, -0.3), sparks_g=True, sack_swing=(-0.6, -0.5, 1.2),
             bulges='G', beard_wind=(-0.4, 0.3, -1.6))
PAIN = dict(lean=-4, hunch=12, twist=10, side=-4, head_pitch=-24, head_roll=8, jaw=1.4, bob=0.5,
            foot_r=(-6.8, 0, -1.5), foot_l=(6.5, 0, 1.6), hem_r=(15.0, 12.8), hem=(0, -0.8),
            hand_r=('root', (-19.0, 50.0, 3.0)), dir_r=(-0.6, 0.7, 0.3), palm_r=(0.2, 0, 1), curl_r=0.35,
            spread_r=1.5, pole_r=(-0.4, -1.0, -0.4), sack_swing=(1.2, 2.0, -1.0), sack_roll=-5,
            bulges='H', beard_wind=(0.5, 0.6, -1.8))


# ----------------------------------------------------------------------------- muerte (I-O)
# I: el golpe le echa atrás y suelta el saco; J: se le doblan las rodillas y el saco le resbala del hombro;
# K: de rodillas, el saco cae al suelo a su lado (aún se mueve); L: se tambalea y el saco se desata;
# M-N: se desploma de lado hacia su derecha (izquierda de la pantalla), de cara a quien mira, y del saco
# abierto se derrama algo oscuro; O: cadáver con el charco negro y huesecillos.
CHEST_ST = [('chest', (-1.0, 4.5, 10.8), 2.8), ('chest', (2.5, 1.5, 10.6), 2.0), ('chest', (-3.5, 0.0, 10.4), 1.6)]
SACK_GROUND = Frame((15.0, 0.0, -9.0), rot_y(rad(-28)))     # tirado a su izquierda, la boca hacia delante-derecha


def topple(alpha, roll=0.0, t=(0.0, 0.0, 0.0)):
    """Marco raíz de un cuerpo volcado alpha grados hacia su derecha (giro alrededor de z, la cara sigue
    hacia la cámara) tras girar roll grados sobre su eje (roll > 0: queda algo boca arriba)."""
    return Frame(V(t), rot_z(rad(alpha)) @ rot_y(rad(roll)))


def ooze_pool(spec):
    """Charco de lo oscuro que sale del saco (marco del suelo): elipses planas y grumos."""
    def make(base, spec=spec):
        return Group([Ellipsoid(base.p(c), rr, rot_y(rad(ang)), OOZE) for c, rr, ang in spec], k=0.8, name='pool')
    return make


def blood_pool(c, rr, ang):
    def make(base):
        return Group([Ellipsoid(base.p(c), rr, rot_y(rad(ang)), BLOOD)], name='pool')
    return make


def bones(spec):
    def make(base):
        parts = []
        for a, b, r in spec:
            pa, pb = base.p(a), base.p(b)
            parts += [RoundCone(pa, pb, r, r * 0.85, BONE), Sphere(pa, r * 1.35, BONE), Sphere(pb, r * 1.3, BONE)]
        return Group(parts, k=0.3, name='extra')
    return make


def ground_sack(open_=0.0, deflate=0.0, bulges=()):
    return dict(frame=SACK_GROUND, open=open_, deflate=deflate), list(bulges)


def deaths():
    I = dict(lean=-6, hunch=8, twist=-8, side=4, head_pitch=-30, head_roll=-10, jaw=1.6, bob=0.6,
             foot_r=(-6.8, 0, 1.5), foot_l=(6.5, 0, -1.5), hem_r=(15.0, 13.0), hem=(0, -1.0),
             hand_r=('root', (-20.0, 47.0, 2.0)), dir_r=(-0.5, 0.8, 0.2), palm_r=(0.2, 0, 1), curl_r=0.3, spread_r=1.6,
             pole_r=(-0.5, -1.0, -0.3),
             hand_l=('root', (19.0, 50.0, 4.0)), dir_l=(0.5, 0.8, 0.2), palm_l=(-0.2, 0, 1), curl_l=0.3, spread_l=1.6,
             pole_l=(0.5, -1.0, -0.3),
             sack='loose', sack_swing=(1.5, 1.0, -2.0), sack_roll=-10, bulges='I', stains=CHEST_ST,
             spray=[('chest', (-0.5, 6.0, 13.5), 1.6), ('chest', (1.5, 8.5, 16.5), 1.2), ('chest', (-2.0, 9.5, 19.0), 0.9),
                    ('chest', (2.5, 11.5, 20.5), 0.7), ('chest', (0.0, 4.0, 16.0), 0.9)],
             beard_wind=(0.4, 0.8, -1.5))
    J = dict(lean=26, hunch=26, twist=6, side=-5, head_pitch=14, head_roll=10, jaw=1.1, bob=-5.0,
             foot_r=(-7.0, 0, 2.5), foot_l=(7.0, 0, 0.5), hem_r=(15.5, 13.5), hem=(0, 0.8),
             hand_r=('root', (-14.0, 17.0, 10.0)), hand_l=('root', (14.0, 19.0, 9.0)), curl_r=0.9, curl_l=0.9,
             sack='loose', sack_swing=(13.0, -12.0, 4.0), sack_roll=-38, sack_tilt=-4, bulges='J', stains=CHEST_ST)
    gs, gb = ground_sack(0.0, 0.0, [(9.0, 2.0, 3.4), (14.5, -2.5, 2.6)])
    K = dict(kneel=(4.0, 2.5), bob=-11.5, lean=6, hunch=22, side=-3, head_pitch=18, head_roll=12, jaw=1.3,
             hem_r=(16.0, 14.0), hem=(0, -1.0),
             hand_r=('root', (-14.5, 6.0, 7.0)), hand_l=('root', (14.0, 7.0, 6.0)), curl_r=0.8, curl_l=0.8,
             sack=gs, bulges=gb, stains=CHEST_ST)
    gs, gb = ground_sack(0.35, 0.1, [(7.0, 3.0, 2.6)])
    L = dict(kneel=(4.0, 2.5), root=topple(14, 0, (2.0, 0.0, 0.0)), bob=-12.0, lean=24, hunch=26, side=-6,
             head_pitch=26, head_roll=16, jaw=1.2, hem_r=(16.5, 14.5), hem=(0, 1.0),
             hand_r=('root', (-14.0, 2.6, 14.0)), dir_r=(-0.1, -0.3, 1), palm_r=(0, -1, 0), curl_r=0.4,
             hand_l=('root', (12.0, 12.0, 12.0)), curl_l=0.8,
             sack=gs, bulges=gb, stains=CHEST_ST, lining=False,
             extra=[ooze_pool([((36.0, 0.2, 2.0), (4.0, 0.5, 3.0), 20)])])
    lying = dict(lean=8, hunch=16, side=0, head_pitch=-8, head_roll=-6, jaw=1.4, bob=-3.0,
                 foot_r=(-6.0, 0, 6.0), foot_l=(6.5, 0, 3.0), hem_r=(16.0, 14.0), hem=(0, 2.0),
                 hand_r=('root', (-12.0, 50.0, 14.0)), dir_r=(0, 1, 0.3), palm_r=(1, 0, 0), curl_r=0.6,
                 hand_l=('root', (6.0, 30.0, 16.0)), dir_l=(-0.6, -0.3, 0.5), palm_l=(0, 0, 1), curl_l=0.7,
                 stains=CHEST_ST, lining=False)
    gs, gb = ground_sack(0.8, 0.35)
    M = dict(lying, root=topple(55, 15, (8.0, 2.0, 0.0)), sack=gs, bulges=gb,
             extra=[ooze_pool([((37.0, 0.2, 4.0), (6.5, 0.5, 4.5), 25), ((42.0, 0.2, 8.0), (3.0, 0.5, 2.2), 60)])],
             tilt=14.0, lift_px=8)
    gs, gb = ground_sack(1.0, 0.65)
    N = dict(lying, root=topple(86, 45, (16.0, 12.0, 0.0)), sack=gs, bulges=gb, eyes=False,
             extra=[ooze_pool([((38.0, 0.2, 5.0), (9.5, 0.5, 6.5), 25), ((45.0, 0.2, 11.0), (5.0, 0.5, 3.5), 55),
                               ((32.0, 0.2, 10.0), (4.0, 0.5, 3.0), 0)]),
                    blood_pool((-14.0, 0.12, 8.0), (12.0, 0.4, 6.0), -10)],
             tilt=20.0, lift_px=9)
    gs, gb = ground_sack(1.0, 0.95)
    O = dict(N, root=topple(90, 52, (16.0, 11.0, 0.0)), sack=gs, bulges=gb, jaw=1.6,
             flatten=(np.diag([1.0, 0.8, 1.0]), (0, 0, 0), 0.8),
             extra=[ooze_pool([((39.0, 0.2, 6.0), (13.0, 0.5, 8.0), 25), ((48.0, 0.2, 13.0), (6.0, 0.5, 4.0), 55),
                               ((31.0, 0.2, 12.0), (5.5, 0.5, 3.5), 0), ((35.0, 0.7, 7.0), (2.0, 1.1, 1.6), 0),
                               ((43.0, 0.7, 4.0), (1.6, 1.0, 1.4), 0)]),
                    blood_pool((-16.0, 0.12, 9.0), (16.0, 0.4, 7.0), -10),
                    bones([((37.0, 1.0, 10.0), (41.5, 1.0, 12.0), 0.55), ((44.0, 1.0, 7.0), (46.5, 1.0, 4.5), 0.5)])],
             tilt=24.0, lift_px=10)
    return [I, J, K, L, M, N, O]


# ----------------------------------------------------------------------------- bola de fuego (BAL7)
# Gira (A/B con 8 ángulos: estela hacia atrás) y el juego la pinta a pleno brillo: 2D, sin contorno, con un
# campo de «calor» (ruido determinista) cuantizado a una rampa de verdes esmeralda de PLAYPAL (sin amarillo:
# no se confunde con la de la Meiga) y núcleo blanco-menta. BALL_Z: el centro de la bola sobre el origen.
BAL_RAMP = [126, 124, 122, 120, 118, 116, 114, 113, 112, 112, 80]
BALL_R = 7.2
BALL_Z = 9


def fbm2(x, y, scale, seed):
    P = np.column_stack([x.ravel(), y.ravel(), np.full(x.size, 0.37 + seed)])
    n = vnoise(P, scale, seed) * 0.6 + vnoise(P, scale * 2.1, seed + 1) * 0.3 + vnoise(P, scale * 4.3, seed + 2) * 0.1
    return n.reshape(x.shape)


def ball_heat(x, y, frame, angle):
    """Calor de la bola en vuelo: bola (con borde de llamas) + estela hacia atrás según el ángulo."""
    seed = 3 if frame == 'A' else 8
    rot = 0.0 if frame == 'A' else 1.7
    r = np.hypot(x, y)
    th = np.arctan2(y, x)
    nang = fbm2(np.cos(th + rot) * 2.3, np.sin(th + rot) * 2.3, 1.0, seed)
    R = BALL_R * (0.78 + 0.45 * nang)
    h = 1.1 - r / R + 0.32 * (fbm2(x, y, 0.55, seed + 5) - 0.5) + 0.12 * np.exp(-((x + 1.2) ** 2 + (y - 1.2) ** 2) / 1.5)
    phi = (angle - 1) * math.pi / 4
    tx, tz = math.sin(phi), math.cos(phi)          # dirección de la estela en pantalla (x) y hacia la cámara (z)
    if abs(tx) > 0.05:
        sgn = 1.0 if tx > 0 else -1.0
        u = x * sgn                                   # a lo largo de la estela
        Lt = 30.0 * abs(tx)
        w = BALL_R * 0.95 * np.clip(1 - u / (Lt + 1e-6), 0, 1) ** 0.8
        flick = fbm2(u * 0.35 - (2.0 if frame == 'B' else 0.0), y * 0.6, 1.0, seed + 11)
        tail = (0.95 - np.abs(y + 0.04 * u) / np.maximum(w, 0.3)) * np.clip(1 - u / (Lt + 1e-6), 0, 1)
        tail = tail * (0.55 + 0.7 * flick) - 0.25 * (fbm2(u * 0.5, y, 0.9, seed + 13) > 0.62)
        tail = np.where(u > 0, tail, -1)
        if tz < -0.05:                                # se aleja: la estela queda delante de la bola
            h = np.maximum(h * (1 - 0.35 * np.clip(tail, 0, 1)), tail * 0.85)
        else:
            h = np.maximum(h, tail * 0.85)
        # bocanadas sueltas detrás de la estela
        for k, (du, rr) in enumerate(((0.62, 3.0), (0.86, 2.3))):
            cx = Lt * du + (1.5 if frame == 'B' else 0.0) * (k + 1) * 0.6
            cy = (fbm2(np.array([k * 1.7]), np.array([seed * 0.3]), 1.0, seed + 20)[0] - 0.5) * 3.0
            d = np.hypot(u - cx, (y - cy) * 1.3)
            h = np.maximum(h, (0.6 - 0.12 * k) * np.clip(1.3 - d / (rr * abs(tx) ** 0.3 + 0.6), 0, 1))
    elif tz < -0.05:                                  # de espaldas: la estela tapa la bola y sale en jirones
        jag = fbm2(np.cos(th) * 3.0, np.sin(th) * 3.0, 1.0, seed + 17)
        h = np.maximum(h * 0.92, (1.0 - r / (BALL_R * (0.9 + 0.7 * jag))) * 0.7)
    return h


def ball_sparks(frame, angle):
    rng = np.random.default_rng(40 + (frame == 'B') + 2 * angle)
    phi = (angle - 1) * math.pi / 4
    tx = math.sin(phi)
    out = []
    for _ in range(4):
        if abs(tx) > 0.05:
            u = rng.uniform(8, 32 * abs(tx) + 4)
            out.append((u * (1 if tx > 0 else -1), rng.uniform(-4, 4), 5))
        else:
            a = rng.uniform(0, 2 * math.pi)
            rr = rng.uniform(BALL_R + 1.5, BALL_R + 4)
            out.append((math.cos(a) * rr, math.sin(a) * rr, 5))
    return out


def expl_heat(x, y, frame):
    """Explosión C-E: estallido con lenguas de fuego, anillo que se abre y humo verde oscuro."""
    r = np.hypot(x, y)
    th = np.arctan2(y, x)
    rc, w, peak, fill, holes, seed = {'C': (6.5, 4.5, 0.95, 0.85, 0.12, 51),
                                       'D': (10.0, 4.2, 0.85, 0.35, 0.3, 52),
                                       'E': (13.0, 3.6, 0.55, 0.0, 0.55, 53)}[frame]
    tongues = fbm2(np.cos(th) * 4.0, np.sin(th) * 4.0, 1.0, seed)
    rr = rc * (0.6 + 0.8 * tongues)
    h = peak * np.exp(-((r - rr) / w) ** 2)
    h = np.maximum(h, fill * peak * np.clip(1 - r / (rr + 2.0), 0, 1) * 1.15)
    h *= 0.45 + 1.0 * fbm2(x, y, 0.45, seed + 3)
    h -= holes * (fbm2(x, y, 0.24, seed + 7) > 0.56)
    return h


def expl_sparks(frame):
    n, r0, r1, lvl, seed = {'C': (10, 9.0, 14.0, 7, 61), 'D': (12, 12.0, 17.0, 5, 62), 'E': (9, 15.0, 18.5, 3, 63)}[frame]
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(r0, r1)
        out.append((math.cos(a) * r, math.sin(a) * r * 0.92, lvl))
    return out


def raster_heat(heat_fn, sparks, W, H, cx, cy):
    jj, ii = np.meshgrid(np.arange(W * SS), np.arange(H * SS))
    x = (jj + 0.5) / SS - cx
    y = cy - (ii + 0.5) / SS
    h = heat_fn(x, y)
    on = h > 0.05
    cnt = on.reshape(H, SS, W, SS).sum(axis=(1, 3))
    hs = np.where(on, h, 0).reshape(H, SS, W, SS).sum(axis=(1, 3))
    hm = hs / np.maximum(cnt, 1)
    n = len(BAL_RAMP)
    lv = np.clip(np.floor(hm * n), 0, n - 1).astype(int)
    vis = cnt >= 6
    for sx, sy, sl in sparks:
        px, py = int(math.floor(cx + sx)), int(math.floor(cy - sy))
        if 0 <= px < W and 0 <= py < H:
            lv[py, px] = max(lv[py, px], sl) if vis[py, px] else sl
            vis[py, px] = True
    pal = render().palarr
    img = np.zeros((H, W, 4), np.uint8)
    img[vis, :3] = pal[np.array(BAL_RAMP)[lv[vis]]].astype(np.uint8)
    img[vis, 3] = 255
    return img


def crop_with_origin(img, ox, oy):
    """Recorta lo transparente y devuelve (imagen, [izq, sup]) con el origen (ox, oy) del lienzo."""
    vis = img[:, :, 3] >= 128
    rows = np.nonzero(vis.any(1))[0]
    cols = np.nonzero(vis.any(0))[0]
    r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
    return Image.fromarray(img[r0:r1, c0:c1].copy(), 'RGBA'), [int(round(ox - c0)), int(round(oy - r0))]


def draw_ball(frame, angle):
    """→ (imagen, offsets). El lienzo se centra en la bola; el origen queda BALL_Z px por debajo."""
    if frame in 'AB':
        W, H = 84, 30
        cx, cy = W / 2, H / 2
        img = raster_heat(lambda x, y: ball_heat(x, y, frame, angle), ball_sparks(frame, angle), W, H, cx, cy)
    else:
        W, H = 48, 48
        cx, cy = W / 2, H / 2
        img = raster_heat(lambda x, y: expl_heat(x, y, frame), expl_sparks(frame), W, H, cx, cy)
    return crop_with_origin(img, cx, cy + BALL_Z)


# ----------------------------------------------------------------------------- salida
OFFSETS = {}


def view_dir(angle, tilt=TILT):
    th = (angle - 1) * math.pi / 4 if angle else 0.0
    return V(0, -math.sin(tilt), -math.cos(tilt)) @ rot_y(-th)


def draw_creature(pose, angle):
    """→ (imagen recortada, offsets): eje del cuerpo en el centro, suelo del modelo SINK px bajo el origen."""
    groups, extras = build(pose)
    tilt = rad(pose.get('tilt', 10.0))
    extras['view'] = view_dir(angle, tilt)
    R = render(tilt)
    out, depth = R.render(groups, extras, angle)
    img = finish(out, depth, R.palarr, OUTLINE)
    H = out.shape[0]
    floor_row = (H - 1) - pose.get('lift_px', L_PX)          # borde superior de esta fila = suelo en el eje
    a = np.array(img)
    r0 = int(np.nonzero((a[:, :, 3] >= 128).any(1))[0].min())
    t = trim(img)
    return t, [t.width // 2, floor_row - SINK - r0]


def lumps():
    out = {}
    for fi, fr in enumerate('ABCD'):
        for a in range(1, 9):
            out[f'BOSS{fr}{a}'] = ((f'BOSS{fr}{a}', walk(fi)), a)
    for fr, pose in (('E', ATK_E), ('F', ATK_F), ('G', ATK_G), ('H', PAIN)):
        for a in range(1, 9):
            out[f'BOSS{fr}{a}'] = ((f'BOSS{fr}{a}', pose), a)
    for fr, pose in zip('IJKLMNO', deaths()):
        out[f'BOSS{fr}0'] = ((f'BOSS{fr}0', pose), 1)
    for fr in 'AB':
        for a in range(1, 9):
            out[f'BAL7{fr}{a}'] = ((f'BAL7{fr}{a}', ('ball', fr)), a)
    for fr in 'CDE':
        out[f'BAL7{fr}0'] = ((f'BAL7{fr}0', ('ball', fr)), 0)
    return out


def draw(item, angle):
    name, pose = item
    if isinstance(pose, tuple) and pose[0] == 'ball':
        img, off = draw_ball(pose[1], angle)
    else:
        img, off = draw_creature(pose, angle)
    OFFSETS[name] = off
    return img


def guardar_offsets(salida):
    """Actualiza arte/sprites/offsets_saco.json con los lumps dibujados (sin perder los demás)."""
    path = os.path.join(salida, 'offsets_saco.json')
    data = {}
    if os.path.exists(path):
        data = json.load(open(path))
    data.update(OFFSETS)
    with open(path, 'w') as f:
        f.write('{\n' + ',\n'.join(f'  "{k}": [{v[0]}, {v[1]}]' for k, v in sorted(data.items())) + '\n}\n')


# Render en paralelo: unos pocos procesos llenan una caché y luego sdf.cli guarda los PNG y la hoja como
# siempre. El resultado es idéntico al secuencial (cada sprite es independiente y sus semillas son fijas).
PROCS = 3
CACHE = {}


def _work(name):
    item, ang = lumps()[name]
    img = draw(item, ang)
    return name, np.array(img), OFFSETS[name]


def draw_cached(item, angle):
    name = item[0]
    if name not in CACHE:
        return draw(item, angle)
    img, off = CACHE[name]
    OFFSETS[name] = off
    return img


if __name__ == '__main__':
    from concurrent.futures import ProcessPoolExecutor
    ap = argparse.ArgumentParser()
    ap.add_argument('--salida', required=True)
    ap.add_argument('--solo', default='')
    args, _ = ap.parse_known_args()
    todos = lumps()
    names = [n.strip().upper() for n in args.solo.split(',') if n.strip()] or list(todos)
    pesados = sorted(names, key=lambda n: (n[:4] != 'BOSS', n[4] < 'I'))        # muertes primero: reparto parejo
    if len(names) > 3:
        with ProcessPoolExecutor(max_workers=min(PROCS, os.cpu_count() or 1)) as ex:
            for name, arr, off in ex.map(_work, pesados):
                CACHE[name] = (Image.fromarray(arr, 'RGBA'), off)
    rows = sprite_rows('BOSS', 'ABCDEFGH', 'IJKLMNO') + [[f'BAL7A{a}' for a in range(1, 9)],
                                                         [f'BAL7B{a}' for a in range(1, 9)],
                                                         [f'BAL7{f}0' for f in 'CDE']]
    cli(lumps, draw_cached, rows)
    guardar_offsets(args.salida)
