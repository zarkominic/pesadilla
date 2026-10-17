#!/usr/bin/env python3
"""cabron.py — dibuja POR CÓDIGO al GRAN CABRÓN (sustituye al ciberdemonio CYBR de Freedoom; jefe final).

Macho cabrío gigantesco del aquelarre (el «Gran Cabrón» de Goya, pero de pie sobre dos patas): cuernos
enormes retorcidos en espiral, barba de chivo larga, ojos amarillos que brillan con la pupila horizontal
de las cabras, orejas caídas, pelaje negro-pardo apelmazado (mechones, cresta erizada en la nuca),
torso humano deforme y velludo (barriga caída, pecho torcido, joroba, costillas), brazos largos con
garras, patas de cabra (corvejón hacia atrás) con pezuñas hendidas, rabo corto levantado con borla y,
en la pata izquierda, un grillete roto con la cadena arrastrando. Bajo el brazo derecho, apoyado en la
cadera, lleva un gran CAÑÓN DE FERIA de duelas de madera con franjas gastadas (rojo, amarillo y verde,
como el lanzacohetes), aros y boca de hierro, asa encima, mecha encendida en la culata y un cohete
asomando por la boca: de ahí salen los cohetes (MISL, que dibuja cohetes.py). La boca está donde el
motor crea el cohete (P_SpawnMissile: en el eje, z+32; el centro del MISL queda a ~37 px del suelo): a
36-40 px sobre los pies y a ~5 px del eje de frente, y el fogonazo de F va en ella. Para apuntar y
disparar (E, F) lo sujeta también con la otra mano. Sin símbolos religiosos.

Luz: pelo negro-pardo con una rampa larga; la base se queda oscura y la luz de borde arriba-izquierda
(como el Toro) y las puntas de los mechones dan las luces altas para que la silueta se lea con poca luz.

Técnica: la misma que el resto de criaturas (tools/arte/sdf.py): modelo 3D de primitivas SDF con poses
paramétricas, trazado ortográfico a 4 submuestras, rampas EXACTAS de PLAYPAL, reducción con prioridad a
lo cercano y a lo que brilla, contorno de 1 px. 1 unidad ≈ 1 px: ~108 px con los cuernos (el ciberdemonio
de Freedoom mide unos 105). El humo, el fuego y las chispas de la muerte son 2D (como en cohetes.py) y se
pintan encima del trazado: el humo solo detrás (donde no hay nada), el fuego y las chispas delante.

Fotogramas (info.c, SPR_CYBR; ninguno a pleno brillo):
    A-D  andar a pisotones (A y B también en reposo; A_Hoof en A, A_Metal en D) ... 8 ángulos
    E    apunta: piernas abiertas, agarra la caña con la otra mano, chisporrotea la mecha 8 ángulos
    F    dispara desde la cadera: fogonazo en la boca y culatazo ................... 8 ángulos
    G    dolor ...................................................................... 8 ángulos
    H-P  muerte larga, de frente (ángulo 0): H le revienta el cañón en la cadera; I berrea con el brazo
         y el costado quemados y el muñón del cañón ardiendo; J se tambalea y lo suelta; K cae de rodillas; L-N se
         desploma de lado; O tendido entre humo; P (para siempre) un montón de pelo y cuernos humeando.

Apoyo: offsets EXPLÍCITOS en arte/sprites/offsets_cabron.json (este script lo escribe/actualiza): el eje
del cuerpo en el centro del ancho y el suelo del modelo SINK px por debajo del origen en TODOS los
fotogramas y ángulos (las pezuñas no bailan).

Uso (determinista; regenera los 65 PNG CYBR* y offsets_cabron.json; varios procesos):
    ~/.venvs/pesadilla/bin/python tools/arte/cabron.py --salida arte/sprites
    … --solo CYBRA1,CYBRH0      solo esos lumps (offsets_cabron.json se actualiza, no se pisa)
    … --hoja hoja.png           además, hoja de contactos ampliada x3 con etiquetas
    … --procesos N              procesos en paralelo (por defecto 5)
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
                 Sphere, Ellipsoid, RoundCone, CappedCone, Box, Ring, Group, vnoise,
                 Render, finish, trim, ik, apply_shine, cli, sprite_rows, TILT)
from cohetes import fbm2, malla, reducir2, pintar_fuego, chispa, HUMO, HUMO_CALIDO, SS2  # noqa: E402

# ----------------------------------------------------------------------------- materiales
(FUR, SKIN, HAND, HORN, HOOF, EYE, SOCKET, MOUTH, TEETH, NOSE, BEARD, CLAW, WOOD, GRIP, PAINT_R,
 PAINT_Y, PAINT_G, IRON, RUST, HOLE, ROCKET, FUSE, EMBER, FLASH, BLOOD, CHAR, BURN, POOL) = range(28)
RAMPS = {
    FUR: [0, 8, 2, 1, 239, 238, 15, 237, 14, 13, 142, 141, 140, 139, 138, 136],  # negro-pardo; brillos pardo claro
    SKIN: [2, 1, 239, 143, 142, 141, 140, 139, 138, 136],    # torso: piel cetrina y sucia
    HAND: [2, 1, 239, 238, 237, 151, 150, 149],            # manos: cuero oscuro
    HORN: [1, 79, 151, 150, 149, 148, 140, 136, 132, 130],  # cuerno: pardo en la base, marfil sucio en la punta
    HOOF: [0, 8, 7, 6, 5, 111, 109],                       # pezuña negra
    EYE: [164, 162, 161, 160],                             # amarillo que brilla (borde → núcleo)
    SOCKET: [0],
    MOUTH: [0, 47, 46, 45, 44],
    TEETH: [79, 151, 149, 148, 140],
    NOSE: [8, 7, 6, 5, 111, 110, 108, 105, 102],           # morro húmedo (los ollares, negros)
    BEARD: [8, 7, 6, 5, 111, 109, 107, 105, 103, 101, 98],  # barba negra entrecana
    CLAW: [0, 8, 7, 5, 110, 108],                          # garras negras
    WOOD: [2, 239, 238, 237, 151, 150, 149, 148],          # duelas del cañón (donde no hay pintura)
    GRIP: [2, 239, 238, 237, 151, 150, 149, 148],          # asa de madera
    PAINT_R: [2, 47, 45, 43, 40, 38, 36, 34],              # pintura de feria gastada (como el lanzacohetes)
    PAINT_Y: [1, 79, 167, 166, 165, 164, 163, 162],
    PAINT_G: [12, 127, 126, 125, 124, 123, 122, 121],
    IRON: [0, 8, 7, 6, 5, 111, 109, 107, 104, 100],        # hierro negro con brillo
    RUST: [2, 1, 239, 238, 237, 77, 76],                   # hierro oxidado (grillete y cadena)
    HOLE: [0],
    ROCKET: [190, 187, 184, 181, 178, 174],                # papel rojo del cohete
    FUSE: [7, 239, 238, 237, 236, 141],                    # mecha de cáñamo
    EMBER: [186, 183, 179, 176, 215, 213, 211],            # brasa de la mecha (por nivel)
    FLASH: [221, 215, 213, 229, 226, 225],                 # fogonazo (por distancia al centro)
    BLOOD: [191, 188, 185, 182, 179, 176],
    CHAR: [0, 8, 7, 6, 5, 2, 1],                           # chamuscado
    BURN: [0, 47, 45, 42, 40, 38, 36],                     # carne quemada
    POOL: [0, 47, 191, 190, 189, 188, 187, 185],           # charco de sangre (oscuro)
}
EMISSIVE = (EYE, EMBER, FLASH)
FUR_BASE, RIM = 0.84, 0.85                                 # tono base del pelo y fuerza de la luz de borde
OUTLINE = 2
NO_LIGHT = (FLASH, EYE, SOCKET, HOLE, EMBER, MOUTH)

# ----------------------------------------------------------------------------- medidas del modelo
HS = 1.25                         # escala de la cabeza
HIP_Y = 46.0                      # articulación de la cadera sobre el suelo
LEG_X = 7.8
THIGH, SHIN, META = 15.5, 19.5, 10.5
HOOF_Y = 1.5
WAIST_AT = 4.0                    # el marco «up» (cintura) va WAIST_AT por encima de las caderas
CHEST_AT = 14.0                   # pecho respecto a la cintura
SHOULDER = (16.0, 8.5, -1.0)      # hombro izquierdo en el marco del pecho (x+ = su izquierda)
UPPER_ARM, FOREARM = 16.0, 15.0
NECK_AT = (0.0, 21.5, 7.0)        # giro de la cabeza en el marco del pecho
HIP_AT = (-12.6, 47.0, 4.0)       # apoyo del cañón en la cadera derecha (marco raíz girado con la cintura)
BORE_R = 3.7
L_PX = 6                          # el modelo se traza L_PX px más alto: nada se corta por abajo
SINK = 3                          # el suelo del modelo queda SINK px por debajo del origen


# ----------------------------------------------------------------------------- materiales por punto
def materiales(P, mat, inten, nz, nr, spec, lvl_extra, extras):
    """Pelo apelmazado, vello del torso y costillas, cuernos anillados, ojos de pupila horizontal, franjas
    del cañón, hierro, óxido, brasa, sangre y quemaduras."""
    # --- pelo: mechones que cuelgan (ruido estirado en vertical) y brillo arriba
    m = mat == FUR
    if m.any():
        q = P[m] * np.array([1.0, 0.33, 1.0])
        cl = vnoise(q, 0.85, 11) * 0.6 + vnoise(q, 2.2, 12) * 0.4
        inten[m] *= 0.45 + 0.85 * cl
        inten[m] += 0.16 * np.clip(nr[m, 1], 0, 1)
        lit = np.clip(nr[m] @ extras['view'][2], 0, 1) if 'view' in extras else 0.5
        inten[m] += 0.3 * np.clip((cl - 0.58) * 4.0, 0, 1) * lit          # brillo en las puntas de los mechones
    m = mat == BEARD
    if m.any():
        q = P[m] * np.array([1.0, 0.25, 1.0])
        inten[m] *= 0.55 + 0.8 * vnoise(q, 2.0, 7)
    # --- torso: piel con vello (más espeso en hombros, costados y pubis), costillas en los costados
    ch = extras.get('chest')
    m = mat == SKIN
    if ch is not None and m.any():
        o, R = ch
        q = (P - o) @ R
        inten[m] *= 0.84 + 0.3 * vnoise(P[m], 0.8, 21)
        side = np.clip((np.abs(q[:, 0]) - 9.0) / 6.0, 0, 1)
        ribs = m & (np.abs(q[:, 0]) > 7.5) & (q[:, 1] > -5.0) & (q[:, 1] < 7.0)
        inten[ribs] *= 1 + 0.32 * np.sin(q[ribs, 1] * 1.7 + 0.5)
        hair = vnoise(P * np.array([1.0, 0.45, 1.0]), 1.25, 23)
        wo, wR = extras['waist']
        qw = (P - wo) @ wR
        low = np.clip((3.0 - qw[:, 1]) / 6.0, 0, 1)
        stripe = np.clip(1 - np.abs(q[:, 0]) / 3.0, 0, 1) * np.clip((q[:, 1] + 2.0) / 6.0, 0, 1)
        thr = 0.8 - 0.36 * side - 0.22 * stripe - 0.5 * low
        mat[m & (hair > thr)] = FUR
        mat[(mat == SKIN) & (qw[:, 1] < 1.5 + 3.0 * vnoise(P, 0.7, 24))] = FUR
        mat[(mat == SKIN) & (q[:, 2] < 1.0 + 4.0 * (vnoise(P, 0.6, 25) - 0.5))] = FUR      # espalda peluda
    # --- cuernos: anillos transversales, base oscura, punta clara
    m = mat == HORN
    if m.any():
        idx = np.nonzero(m)[0]
        best = np.full(len(idx), 1e9)
        along = np.zeros(len(idx))
        tt = np.zeros(len(idx))
        for pts, cum in extras.get('horns', []):
            d = np.linalg.norm(P[idx, None, :] - pts[None], axis=2)
            k = d.argmin(1)
            dd = d[np.arange(len(idx)), k]
            sel = dd < best
            best[sel] = dd[sel]
            along[sel] = cum[k[sel]]
            tt[sel] = cum[k[sel]] / cum[-1]
        inten[idx] *= (0.8 + 0.22 * np.sin(along * 2.3)) * (0.78 + 0.5 * tt)
    # --- ojos amarillos con pupila horizontal (sobre la superficie de la cabeza)
    for c, Rm, rr in extras.get('eyes', []):
        q = (P - c) @ Rm
        e = np.sqrt((q[:, 0] / rr[0]) ** 2 + (q[:, 1] / rr[1]) ** 2 + (q[:, 2] / rr[2]) ** 2)
        near = np.isin(mat, (FUR, SKIN, NOSE)) & (e < 1.45)
        mat[near] = SOCKET
        ey = (mat == SOCKET) & (e < 1.0)
        mat[ey] = EYE
        lvl_extra[ey] = np.where(e[ey] < 0.5, 3, np.where(e[ey] < 0.8, 2, 1))
        pup = ey & (np.abs(q[:, 1]) < rr[1] * 0.3) & (np.abs(q[:, 0]) < rr[0] * 0.66)
        mat[pup] = SOCKET
    for c, r in extras.get('nostrils', []):
        mat[np.isin(mat, (NOSE, FUR)) & (_len(P - c) < r)] = SOCKET
    # --- cañón: franjas de feria en espiral sobre las duelas, gastadas; boca tiznada; ánima negra
    cf = extras.get('cannon')
    if cf is not None:
        o, R, z0, z1 = cf
        sel = np.isin(mat, (WOOD, IRON))
        if sel.any():
            q = (P - o) @ R
            rad_ = np.hypot(q[:, 0], q[:, 1])
            th = np.arctan2(q[:, 0], q[:, 1])
            body = (mat == WOOD) & (q[:, 2] > z0) & (q[:, 2] < z1)
            s = q[:, 2] / 15.0 + th / (2 * math.pi)
            k = np.floor(s * 3).astype(int) % 3
            worn = (vnoise(q * np.array([1, 1, 0.55]), 0.8, 4) * 0.6 + vnoise(q, 2.2, 5) * 0.4) > 0.6
            paint = body & ~worn
            mat[paint] = np.array([PAINT_R, PAINT_Y, PAINT_G])[k[paint]]
            stave = np.isin(mat, (WOOD, PAINT_R, PAINT_Y, PAINT_G)) & (np.mod(th * 14 / (2 * math.pi), 1.0) < 0.14)
            inten[stave] *= 0.62
            soot = np.isin(mat, (WOOD, PAINT_R, PAINT_Y, PAINT_G, IRON)) & (q[:, 2] > z1 - 7.0 + 3.0 * vnoise(P, 0.9, 6))
            inten[soot] *= 0.62
            hole = np.isin(mat, (WOOD, IRON, PAINT_R, PAINT_Y, PAINT_G)) & (rad_ < BORE_R + 0.3) & (q[:, 2] > z1 - 9.0)
            mat[hole] = HOLE
    # --- óxido del grillete y la cadena
    for c, r in extras.get('rust', []):
        mm = (mat == IRON) & (_len(P - c) < r) & (vnoise(P, 1.3, 31) > 0.42)
        mat[mm] = RUST
    # --- pelo: la base sigue negro-parda (la rampa es más larga) y la luz de borde arriba-izquierda (como el
    # Toro) despega hombros, lomo, muslos y brazos del fondo; el tramo claro de la rampa es sobre todo para ella
    m = mat == FUR
    inten[m] *= FUR_BASE
    vw = extras.get('view')
    if vw is not None:
        Lr, Vv, _ = vw
        fres = np.clip(1.0 - np.abs(nr @ Vv), 0, 1) ** 1.6
        rim = fres * np.clip(nr @ Lr + 0.15, 0, 1)
        m = np.isin(mat, (FUR, SKIN, BEARD, HAND))
        inten[m] += RIM * rim[m]
    apply_shine(mat, inten, spec, ((HOOF, 0.4, 7), (CLAW, 0.5, 8), (NOSE, 1.0, 9), (IRON, 0.7, 10),
                                   (HORN, 0.3, 6), (BLOOD, 0.6, 12), (SKIN, 0.22, 6), (PAINT_R, 0.2, 6),
                                   (PAINT_Y, 0.2, 6), (PAINT_G, 0.2, 6), (HAND, 0.25, 6), (BURN, 0.5, 8),
                                   (ROCKET, 0.25, 6)))
    # --- brasa de la mecha
    em = extras.get('ember')
    m = mat == EMBER
    if em is not None and m.any():
        c, r, hot = em
        de = _len(P[m] - c)
        n = len(RAMPS[EMBER])
        lvl_extra[m] = np.clip(np.floor((1.15 - de / r) * n * 0.6 + hot), 0, n - 1)
    # --- quemaduras (muerte): el pelo se chamusca, la piel queda en carne viva
    for c, r in extras.get('burn', []):
        db = _len(P - c) / r + 0.45 * (nz - 0.5)
        mm = db < 1.0
        mat[mm & np.isin(mat, (FUR, BEARD))] = CHAR
        mat[mm & np.isin(mat, (SKIN, HAND))] = BURN
        mat[mm & np.isin(mat, (WOOD, GRIP, PAINT_R, PAINT_Y, PAINT_G, FUSE))] = CHAR
        inten[mm] *= 0.85
    # --- manchas de sangre
    for sc, sr in extras.get('stains', []):
        ds = _len(P - sc)
        mm = np.isin(mat, (FUR, SKIN, HAND, BEARD, CHAR, BURN)) & (ds < sr * (0.75 + 0.5 * nz))
        mat[mm] = BLOOD


RENDERS = {}


def render(tilt=TILT):
    key = round(tilt, 5)
    if key not in RENDERS:
        RENDERS[key] = Render(RAMPS, hook=materiales, flash_mats=(FLASH,), level_mats=(EYE, EMBER),
                              emissive=EMISSIVE, no_light=NO_LIGHT, tilt=tilt)
    return RENDERS[key]


# ----------------------------------------------------------------------------- piezas
def claw_hand(T, along, palm, curl=0.7, spread=1.0, thumb=1.0, mat=HAND):
    """Mano grande de dedos nudosos con garras negras curvas. along: hacia los dedos; palm: normal de la
    palma; thumb: lado del pulgar (+1/-1 respecto a s)."""
    a = nrm(along)
    n = V(palm) - a * (V(palm) @ a)
    n = nrm(n) if np.linalg.norm(n) > 1e-6 else nrm(np.cross(a, (1, 0, 0)))
    s = nrm(np.cross(a, n))
    parts = [Ellipsoid(T + a * 1.0, (3.1, 1.9, 3.3), basis(a, n), mat)]
    claws = []
    for k, off in enumerate((-1.6, -0.55, 0.55, 1.6)):
        ln = (0.85, 1.0, 1.0, 0.8)[k]
        base = T + a * 3.3 + s * off * 1.15
        d1 = nrm(a + s * off * 0.2 * spread + n * curl * 0.45)
        j1 = base + d1 * 2.5 * ln
        d2 = nrm(d1 + n * curl * 0.8)
        j2 = j1 + d2 * 2.1 * ln
        d3 = nrm(d2 + n * (0.5 + curl * 0.6))
        parts += [RoundCone(base, j1, 1.0, 0.85, mat), RoundCone(j1, j2, 0.85, 0.7, mat)]
        claws.append(RoundCone(j2, j2 + d3 * 2.6, 0.62, 0.15, CLAW))
    tb = T + a * 0.6 + s * thumb * 2.4
    dth = nrm(a * 0.7 + s * thumb * 0.5 + n * (0.3 + curl * 0.4))
    parts.append(RoundCone(tb, tb + dth * 2.8, 1.05, 0.8, mat))
    claws.append(RoundCone(tb + dth * 2.8, tb + dth * 2.8 + nrm(dth + n * 0.6) * 2.0, 0.55, 0.15, CLAW))
    return parts, claws


def tuft(a, d, ln, r0, mat=FUR):
    """Mechón de pelo apelmazado: de a en la dirección d, afilándose."""
    d = nrm(d)
    m = a + d * ln * 0.55
    return [RoundCone(a, m, r0, r0 * 0.6, mat), RoundCone(m, a + d * ln, r0 * 0.6, 0.18, mat)]


def horn_poly(sx):
    """Eje del cuerno (en el marco de la cabeza, sin escalar): sube y se va hacia atrás y hacia fuera
    retorciéndose en espiral (como un macho montés). → (puntos, radios)."""
    base = V(2.4 * sx, 6.0, -1.0)
    pts, rs = [], []
    N = 22
    for i in range(N + 1):
        t = i / N
        ax = V(sx * (1.5 * t + 12.5 * t * t), 16.5 * t + 1.0 * t * t, -(8.5 * t + 3.0 * t * t))
        tang = nrm(V(sx * (1.5 + 25.0 * t), 16.5 + 2.0 * t, -(8.5 + 6.0 * t)))
        e1 = nrm(np.cross(tang, V(0, 0, 1)))
        e2 = np.cross(tang, e1)
        phi = sx * 2 * math.pi * 1.8 * t + 0.4
        rh = 2.7 * math.sin(math.pi * min(t * 1.1, 1.0)) ** 0.7
        pts.append(base + ax + rh * (math.cos(phi) * e1 + math.sin(phi) * e2))
        rs.append(3.0 * (1 - t) ** 0.8 + 0.35)
    return pts, rs


def chain_links(path, n, size=1.0):
    """Eslabones alternos a lo largo de una polilínea (Rings de hierro); el último, partido."""
    path = [V(p) for p in path]
    seg = [np.linalg.norm(path[i + 1] - path[i]) for i in range(len(path) - 1)]
    total = sum(seg)
    out = []
    step = 2.7 * size
    for k in range(n):
        s = min(k * step + 1.4 * size, total - 0.5)
        i, acc = 0, 0.0
        while i < len(seg) - 1 and acc + seg[i] < s:
            acc += seg[i]
            i += 1
        t = (s - acc) / max(seg[i], 1e-6)
        c = path[i] + (path[i + 1] - path[i]) * t
        tg = nrm(path[i + 1] - path[i])
        M = basis(tg, (0, 1, 0)) @ rot_x(rad(90))           # y' = tangente; el anillo en x'z'
        M = M @ rot_y(rad(90 * (k % 2)))
        # anillo alargado a lo largo de la tangente: en el marco de basis, z' es la tangente → tras rot_x(90)
        # la tangente es y'. Usamos un marco propio: x' = tangente, z' = normal del plano del eslabón.
        nrmv = nrm(np.cross(tg, (0, 1, 0))) if abs(tg[1]) < 0.95 else V(1, 0, 0)
        if k % 2:
            nrmv = nrm(np.cross(tg, nrmv))
        bx = tg
        bz = nrmv
        by = np.cross(bz, bx)
        Mf = np.column_stack([bx, bz, by])                   # ring en x'z' → plano (tangente, by)
        r = Ring(Frame(c, Mf), 1.75 * size, 1.05 * size, 0.55 * size, IRON)
        out.append(r)
    return out


# ----------------------------------------------------------------------------- pose por defecto
DEFAULT = dict(
    root=None, bob=0.0, lean=10.0, hunch=20.0, twist=0.0, side=0.0,
    head_pitch=0.0, head_yaw=0.0, head_roll=0.0, jaw=0.0,
    foot_r=(-8.5, 0, 1.0), foot_l=(8.5, 0, -1.0), lift_r=0.0, lift_l=0.0, flex_r=None, flex_l=None,
    kneel=None,
    hand_l=('root', (22.0, 40.0, 4.0)), dir_l=None, palm_l=None, curl_l=0.8, pole_l=None, spread_l=1.0,
    hand_r='cannon', dir_r=None, palm_r=None, curl_r=1.2, pole_r=None, spread_r=1.0,
    cannon='hip', aim=-8.0, cannon_yaw=20.0, cannon_roll=0.0, hip_at=HIP_AT, recoil=0.0,
    barrel_at=(4.6, -1.5, 11.0), barrel_dir=(-0.35, -0.55, 0.75), barrel_palm=(-1.0, 0.1, 0.0),
    loaded=True, flash=None, ember=1.0, muzzle_light=0.0,
    tail_sway=0.0, tail_up=0.0, beard_wind=(0.0, 0.0, 0.0),
    stains=(), spray=(), extra=(), burn=(), fx=(), flatten=None, keep_shape=(),
    tilt=10.0, lift_px=L_PX, eyes=True, chain_trail=-1.0,
)


def build(pose):
    p = dict(DEFAULT)
    p.update(pose)
    tilt = rad(p['tilt'])
    base = Frame((0, p['lift_px'] / math.cos(tilt), 0))          # suelo del mundo (subido)
    root = base * (p['root'] or Frame())
    groups = []
    extras = {'eyes': [], 'stains': [], 'horns': [], 'rust': [], 'burn': [], 'fx': []}

    up = root * Frame((0, HIP_Y + WAIST_AT + p['bob'], 0),
                      rot_y(rad(p['twist'])) @ rot_x(rad(p['lean'])) @ rot_z(rad(p['side'])))
    chest = up * Frame((0, CHEST_AT, 0), rot_x(rad(p['hunch'])))
    head = chest * Frame(NECK_AT, rot_x(rad(-(p['lean'] + p['hunch']) * 0.85 + p['head_pitch']))
                         @ rot_y(rad(p['head_yaw'])) @ rot_z(rad(p['head_roll'])))
    extras['chest'] = (chest.o, chest.R)
    extras['waist'] = (up.o, up.R)
    upv = root.d((0, 1, 0))

    frames = {'up': up, 'chest': chest, 'root': root, 'head': head, 'world': base}

    def where(fr, pt):
        return frames[fr].p(pt)

    # --- patas de cabra: muslo, rodilla adelante, corvejón atrás, caña, cuartilla y pezuña hendida
    for sx, foot, lift, flex, ki in ((-1, p['foot_r'], p['lift_r'], p['flex_r'], 0),
                                     (1, p['foot_l'], p['lift_l'], p['flex_l'], 1)):
        upper, lower, hoof = [], [], []
        hipj = up.p((LEG_X * sx, -WAIST_AT, 0.5))
        if p['kneel'] is not None:
            kz = p['kneel'][ki]
            back = root.d((0, 0, -1))
            knee = root.p((LEG_X * sx * 1.15, 3.2, kz))
            K = root.p((LEG_X * sx * 1.2, 3.0, kz - SHIN + 1.0))
            F = K + back * 4.0 + upv * (META - 1.5)
            T = F + back * 2.6 + upv * 1.2
            hf, hu = nrm(back + upv * 1.6), nrm(-back + upv * 0.4)
            fwd = back * -1
        else:
            fwd = root.d(nrm((0.06 * sx, 0, 1)))
            T = root.p(V(foot) + (0, HOOF_Y + lift, 0))
            fl = (32.0 * min(1.0, lift / 5.0)) if flex is None else flex
            sidev = np.cross(upv, fwd)
            Rf = rot_axis(sidev, rad(fl))
            hf, hu = Rf @ fwd, Rf @ upv
            F = T + hu * 3.3 - hf * 1.0
            K = F + Rf @ (upv * META - fwd * 3.0)
            knee = ik(hipj, K, THIGH, SHIN, fwd * 1.0 + upv * 0.2)
        upper += [RoundCone(hipj, knee, 8.0, 4.9, FUR), Sphere(knee, 4.5, FUR)]
        lower += [RoundCone(knee, K, 4.6, 3.0, FUR), Sphere(K, 3.1, FUR), RoundCone(K, F, 2.8, 2.1, FUR),
                  Sphere(F, 2.3, FUR), RoundCone(F, T + hu * 0.9, 2.1, 1.9, FUR)]
        sd = nrm(np.cross(hu, hf))
        for k in (-1, 1):
            hoof.append(Ellipsoid(T + hf * 1.1 + sd * k * 1.05, (1.15, 1.5, 2.5), basis(hf, hu), HOOF))
        # mechones: zahones de pelo largo en el muslo y flecos sobre el corvejón
        th_dir = nrm(knee - hipj)
        outv = nrm(np.cross(th_dir, fwd)) * (-sx if np.cross(th_dir, fwd) @ root.d((1, 0, 0)) > 0 else sx) * -1
        outv = root.d((sx, 0, 0))
        for k, (t, o, b, ln, r0) in enumerate(((0.45, 0.9, -0.5, 10.0, 2.4), (0.6, 0.3, -1.0, 11.5, 2.6),
                                               (0.75, 1.0, 0.3, 8.0, 2.0), (0.55, -0.3, -0.9, 9.0, 2.2))):
            a = hipj + (knee - hipj) * t + outv * (4.6 * o) - fwd * (4.0 * -b)
            upper += tuft(a, V(0.25 * sx * o, -1.0, -0.25 + 0.15 * b), ln, r0)
        for k, (o, b, ln) in enumerate(((0.8, -1.0, 6.0), (-0.6, -1.0, 5.5))):
            a = K + (knee - K) * 0.35 + outv * (1.8 * o) - fwd * 1.5
            lower += tuft(a, V(0.2 * sx * o, -1.0, -0.4), ln, 1.5)
        groups.append(Group(upper, k=1.6, name='thigh'))
        groups.append(Group(lower, k=0.9, name='leg'))
        groups.append(Group(hoof, k=0.3, name='hoof'))
        # grillete roto con la cadena arrastrando (pata izquierda)
        if sx == 1:
            sc = K + (F - K) * 0.72
            ax = nrm(F - K)
            shack = [Ring(Frame(sc, basis(ax, (0, 0, 1)) @ rot_x(rad(90))), 3.0, 3.0, 0.95, IRON)]
            hinge = sc - fwd * 3.3 + upv * 0.2
            shack.append(Sphere(hinge, 1.3, IRON))
            gy = root.p((0, 0.75, 0))[1]
            trail = p['chain_trail']
            g1 = V(hinge[0] + 1.5, gy, hinge[2] - 3.5)
            g2 = g1 + root.d((1.5, 0, -9.0)) * (1.0 if trail < 0 else trail)
            g2[1] = gy
            path = [hinge - fwd * 0.6, (hinge + g1) / 2 + V(0, 0, -1.5), g1, g2]
            if p['kneel'] is not None:
                path = [hinge - fwd * 0.4, hinge + root.d((2.0, -2.0, -3.0)), hinge + root.d((3.5, -3.0, -8.0))]
            nl = max(4, int(sum(np.linalg.norm(V(path[i + 1]) - V(path[i])) for i in range(len(path) - 1)) / 2.7))
            links = chain_links(path, min(nl, 9))
            groups.append(Group(shack + links, k=0.2, name='chain'))
            extras['rust'].append((sc, 4.5))
            extras['rust'].append((g1, 12.0))

    # --- caderas, barriga caída, pecho torcido, joroba, hombros, gorguera y cuello
    torso = [Ellipsoid(up.p((0, -3.5, -0.5)), (12.5, 8.0, 9.5), up.M(), FUR),
             Ellipsoid(up.p((0, 5.0, 2.5)), (12.0, 9.0, 10.0), up.M(), SKIN),
             Ellipsoid(up.p((0.8, 2.5, 6.5)), (8.5, 7.0, 6.5), up.M(), SKIN),
             Ellipsoid(chest.p((0, 3.5, 1.0)), (15.5, 10.5, 10.5), chest.M(), SKIN),
             Ellipsoid(chest.p((6.5, 1.5, 7.0)), (6.8, 5.6, 4.2), chest.M(rot_z(rad(-8))), SKIN),
             Ellipsoid(chest.p((-6.0, 2.6, 6.8)), (6.0, 4.8, 4.0), chest.M(), SKIN),
             Ellipsoid(chest.p((-2.5, 9.0, -6.5)), (13.5, 9.5, 8.5), chest.M(), FUR),
             Ellipsoid(chest.p((0, 13.0, 1.5)), (10.0, 5.0, 9.0), chest.M(), FUR),
             RoundCone(chest.p((0, 11.0, 3.0)), head.p(V(0, -2.0, -1.5) * HS), 6.8, 5.2, FUR)]
    for sx in (-1, 1):
        torso.append(Ellipsoid(up.p((5.5 * sx, -5.0, -5.5)), (6.5, 7.0, 6.0), up.M(), FUR))
        torso.append(Sphere(chest.p((SHOULDER[0] * sx, SHOULDER[1] - (1.8 if sx < 0 else 0), SHOULDER[2])),
                            7.0 + (0.6 if sx < 0 else 0), FUR))
    groups.append(Group(torso, k=3.0, name='torso'))
    torso_g = groups[-1]
    # cresta erizada en la nuca y los hombros
    mane = []
    for k, (x, y, z, dx, ln) in enumerate(((0, 15.5, -1.0, 0.0, 8.0), (-4.5, 15.0, -2.5, -0.35, 7.5),
                                           (4.5, 15.0, -2.5, 0.35, 7.5), (-9.0, 13.5, -3.0, -0.7, 6.5),
                                           (9.0, 13.5, -3.0, 0.7, 6.5), (-2.0, 15.0, -6.0, -0.15, 7.0),
                                           (2.5, 15.5, -5.5, 0.2, 7.0), (-13.0, 12.5, -2.0, -0.9, 5.5),
                                           (13.0, 12.5, -2.0, 0.9, 5.5), (0.0, 12.0, -10.0, 0.0, 6.0))):
        mane += tuft(chest.p((x, y, z)), chest.d((dx, 0.55, -1.0)), ln, 2.3)
    groups.append(Group(mane, k=0.8, name='mane'))

    # --- cabeza de macho cabrío: cráneo, testuz, cara larga, morro, carrillos, orejas caídas, quijada
    def hp(q):
        return head.p(V(q) * HS)
    H = head.M()
    jaw = p['jaw']
    hd = [Ellipsoid(hp((0, 2.5, -1.0)), V(5.0, 5.2, 5.8) * HS, H, FUR),
          Ellipsoid(hp((0, 3.4, 3.0)), V(4.8, 2.0, 2.6) * HS, H, FUR),
          RoundCone(hp((0, 1.0, 2.5)), hp((0, -7.0, 8.5)), 4.2 * HS, 2.6 * HS, FUR),
          Ellipsoid(hp((0, -6.0, 7.6)), V(3.7, 2.7, 2.6) * HS, H @ rot_x(rad(-35)), FUR),       # morro ancho
          Ellipsoid(hp((0, -7.6, 9.2)), V(3.3, 1.9, 1.8) * HS, H @ rot_x(rad(-35)), NOSE)]
    for sx in (-1, 1):
        hd.append(Ellipsoid(hp((3.0 * sx, -0.5, 3.5)), V(2.3, 3.0, 3.0) * HS, H, FUR))
        hd.append(Ellipsoid(hp((6.8 * sx, 1.6, -1.2)), V(4.0, 0.95, 1.9) * HS, H @ rot_z(rad(-24 * sx)), FUR))
    J = head * Frame(V(0, -2.0, 3.0) * HS, rot_x(rad(jaw * 22)))
    hd.append(RoundCone(J.p(V(0, 0, 0)), J.p(V(0, -5.2, 5.0) * HS), 2.6 * HS, 1.7 * HS, FUR))
    groups.append(Group(hd, k=0.9, name='head'))
    hg = groups[-1]
    # boca cerrada: una raja oscura entre el belfo y la quijada (con la boca abierta la tapa 'mouth')
    groups.append(Group([Ellipsoid(hp((0, -8.7, 8.2)), V(3.0, 0.32, 2.2) * HS, H @ rot_x(rad(-30)), MOUTH)],
                        name='lips'))
    if jaw > 0.2:
        Jm = head * Frame(V(0, -2.0, 3.0) * HS, rot_x(rad(jaw * 11)))
        groups.append(Group([Ellipsoid(Jm.p(V(0, -4.0, 4.6) * HS), V(1.8, 0.6 + 0.9 * jaw, 3.2) * HS,
                                       Jm.M() @ rot_x(rad(-40)), MOUTH)], name='mouth'))
    # tupé entre los cuernos
    fl = []
    for dx, ln in ((-1.2, 4.5), (1.0, 5.0), (0.0, 5.5)):
        fl += tuft(hp((dx, 6.5, 1.0)), head.d((dx * 0.15, 0.4, 1.0)), ln * HS, 1.4)
    groups.append(Group(fl, k=0.6, name='forelock'))

    def surf(g, a, dirv, hi=12.0):
        lo = 0.0
        for _ in range(30):
            mid = (lo + hi) / 2
            if g.eval((a + dirv * mid)[None])[0][0] < 0:
                lo = mid
            else:
                hi = mid
        return a + dirv * lo
    for sx in (-1, 1):                                   # ollares: dos agujeros en la nariz, de frente
        dv = head.d(nrm((0.42 * sx, -0.35, 0.84)))
        extras.setdefault('nostrils', []).append((surf(hg, hp((1.1 * sx, -7.4, 8.6)), dv), 1.1 * HS))
    if p['eyes']:
        for sx in (-1, 1):
            dv = head.d(nrm((0.62 * sx, 0.14, 0.78)))
            c = surf(hg, hp((1.0 * sx, 2.2, 2.8)), dv)
            Rm = basis(dv, head.d((0, 1, 0)))
            extras['eyes'].append((c, Rm, V(1.95, 1.5, 1.7) * HS))

    # --- cuernos retorcidos
    horns = []
    for sx in (-1, 1):
        pts, rs = horn_poly(sx)
        wp = [hp(q) for q in pts]
        for i in range(len(wp) - 1):
            c = (wp[i] + wp[i + 1]) / 2
            tg = wp[i + 1] - wp[i]
            ln = np.linalg.norm(tg)
            tg = tg / ln
            e1 = nrm(np.cross(tg, head.d((0, 0, 1))))
            e2 = np.cross(tg, e1)
            ph = sx * 2 * math.pi * 1.8 * (i + 0.5) / (len(wp) - 1)
            a1 = math.cos(ph) * e1 + math.sin(ph) * e2
            a2 = np.cross(tg, a1)
            r = (rs[i] + rs[i + 1]) / 2 * HS
            horns.append(Ellipsoid(c, (r * 1.08, r * 0.62, ln * 0.78), np.column_stack([a1, a2, tg]), HORN))
        arr = np.array(wp)
        cum = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(arr, axis=0), axis=1))])
        extras['horns'].append((arr, cum))
    groups.append(Group(horns, k=0.35, name='horns'))

    # --- barba de chivo (cae por delante del pecho)
    body = [torso_g]

    def push(q, clear=1.2):
        q = V(q)
        f = lambda x: min(g.eval(x[None])[0][0] for g in body)  # noqa: E731
        for _ in range(10):
            d = f(q)
            if d >= clear:
                break
            gr = V([f(q + e) - f(q - e) for e in np.eye(3) * 0.05])
            q = q + nrm(gr) * (clear - d + 0.15)
        return q
    W = V(p['beard_wind'])
    beard = []
    for dx, ln, r in ((0.0, 15.0, 2.0), (-1.3, 11.0, 1.4), (1.3, 11.5, 1.4)):
        a = J.p(V(dx, -4.0, 4.0) * HS)
        m = push(a + V(dx * 0.2, -ln * 0.5, 0.6) + W * 0.4)
        t = push(m + V(dx * 0.1, -ln * 0.5, -0.4) + W)
        beard += [RoundCone(a, m, r * HS, r * 0.75 * HS, BEARD), RoundCone(m, t, r * 0.75 * HS, 0.3, BEARD)]
    beard.append(Ellipsoid(J.p(V(0, -3.6, 3.4) * HS), V(2.2, 1.6, 2.0) * HS, J.M(), BEARD))
    groups.append(Group(beard, k=0.8, name='beard'))

    # --- cañón de feria bajo el brazo derecho, apoyado en la cadera: la boca queda a la altura a la que el
    # motor crea el cohete (z+32; P_SpawnMissile) y cerca del eje de frente
    grip_T = None
    Cf = Frame(root.p(rot_y(rad(p['twist'])) @ V(p['hip_at']) + V(0, p['bob'], 0)),
               root.R @ rot_y(rad(p['twist'] + p['cannon_yaw'])) @ rot_x(rad(-p['aim'])) @ rot_z(rad(p['cannon_roll'])))
    Cf = Frame(Cf.o - Cf.d((0, 0, p['recoil'])), Cf.R)
    frames['cannon'] = Cf
    if p['muzzle_light']:
        extras['flash_light'] = (Cf.p((0, 0, 27.0)), p['muzzle_light'])
    if p['cannon'] == 'hip':
        cannon_parts(Cf, groups, extras, p)
        grip_T = Cf.p((-2.2, 9.6, 1.0))
    elif p['cannon'] == 'burst':
        groups += cannon_burst(Cf, extras)
    elif p['cannon'] == 'stump':
        groups += cannon_stump(Cf, extras)
    elif p['cannon'] is not None:
        groups += p['cannon'](base, where)

    # --- brazos: peludos, largos; manos con garras
    for sx, sfx in ((-1, 'r'), (1, 'l')):
        arm, hand, claws = [], [], []
        S = chest.p((SHOULDER[0] * sx, SHOULDER[1], SHOULDER[2]))
        spec = p['hand_' + sfx]
        if spec == 'cannon':
            if grip_T is None:
                continue
            T = grip_T                                   # agarra el asa de encima por fuera: dedos por encima
            along = Cf.d(nrm((1.0, -0.45, 0.1)))
            palm = Cf.d((0.25, -1.0, 0))
        elif spec == 'barrel':
            T = Cf.p(p['barrel_at'])                    # la otra mano sujeta la caña por delante, por dentro
            along = Cf.d(nrm(V(p['barrel_dir'])))
            palm = Cf.d(V(p['barrel_palm']))
        else:
            T = where(*spec)
            along, palm = None, None
        pole = p['pole_' + sfx]
        pole = up.d((0.55 * sx, -0.75, -0.45)) if pole is None else nrm(V(pole))
        E = ik(S, T, UPPER_ARM, FOREARM, pole)
        extras.setdefault('reach', {})[sfx] = (float(np.linalg.norm(T - S)), UPPER_ARM + FOREARM)
        fa = nrm(T - E)
        if along is None:
            along = fa if p['dir_' + sfx] is None else nrm(V(p['dir_' + sfx]))
        if palm is None:
            palm = V(-sx, 0, -0.3) if p['palm_' + sfx] is None else V(p['palm_' + sfx])
        Wr = T - fa * 2.2
        arm += [RoundCone(S, E, 5.6, 4.3, FUR), Sphere(E, 4.1, FUR), RoundCone(E, Wr, 4.2, 3.0, FUR)]
        arm += tuft(E + fa * 1.0, V(0.15 * sx, -1.0, -0.3), 6.5, 2.0)
        arm += tuft(E + fa * 5.5, V(0.2 * sx, -1.0, -0.1), 5.0, 1.6)
        arm += tuft(S + (E - S) * 0.5 + up.d((2.5 * sx, 0, -1.5)), V(0.25 * sx, -1.0, -0.2), 6.0, 2.0)
        hp_, hc = claw_hand(T, along, palm, p['curl_' + sfx], p['spread_' + sfx], thumb=-sx)
        hand += [RoundCone(Wr, T, 2.9, 2.6, HAND)] + hp_
        claws += hc
        groups.append(Group(arm, k=1.3, name='arm'))
        groups.append(Group(hand, k=0.5, name='hand'))
        groups.append(Group(claws, name='claws'))

    # --- rabo de chivo: corto, sale por encima de las nalgas y se levanta: una paleta de pelo con la borla
    # abierta en abanico en la punta (no un tubo colgando)
    tb = up.p((0, 2.0, -8.0))
    ts, tu = p['tail_sway'], p['tail_up']
    bk = up.d((0, 0, -1))
    t1 = tb + up.d((0.3 * ts, 2.4 + 1.0 * tu, -4.0 + 0.6 * tu))
    tdir = nrm(up.d((0.15 * ts, 1.0 + 0.3 * tu, -0.32 + 0.2 * tu)))
    t2 = t1 + tdir * 7.0
    side = nrm(np.cross(tdir, bk)) if abs(tdir @ bk) < 0.95 else up.d((1, 0, 0))
    tail = [RoundCone(tb, t1, 3.0, 2.6, FUR),
            Ellipsoid((t1 + t2) / 2, (3.4, 1.7, 4.6), basis(tdir, -bk), FUR)]
    for k, (a, ln, r0) in enumerate(((0.0, 6.0, 1.9), (0.75, 5.0, 1.6), (-0.75, 5.0, 1.6), (1.35, 4.0, 1.3),
                                     (-1.35, 4.0, 1.3))):
        tail += tuft(t2 - tdir * 1.6 + side * a * 1.3, tdir + side * a * 0.6 + bk * 0.2, ln, r0)
    groups.append(Group(tail, k=0.9, name='tail'))

    # --- sangre, añadidos, quemaduras, efectos 2D
    extras['stains'] = [(where(fr, pt), r) for fr, pt, r in p['stains']]
    extras['burn'] += [(where(fr, pt), r) for fr, pt, r in p['burn']]
    if p['spray']:
        groups.append(Group([Sphere(where(fr, pt), r, BLOOD) for fr, pt, r in p['spray']], name='spray'))
    for g in p['extra']:
        groups += g(base, where)
    for fx in p['fx']:
        f = dict(fx)
        f['at'] = where(*fx['at'])
        if 'dir' in fx:
            f['dir'] = frames[fx['dir'][0]].d(fx['dir'][1])
        extras['fx'].append(f)
    if p['flatten'] is not None:
        A, t, ds = p['flatten']
        fy = base.o[1]
        for g in groups:
            if g.name not in ('extra', 'pool', 'spray', 'wreck') + tuple(p['keep_shape']):
                g.xf = (A, V(t) + V(0, fy, 0) - A @ V(0, fy, 0), ds)
        extras['eyes'] = []
    ax = root.p((0, 0, 0))
    extras['axis'] = (ax[0], ax[2])
    return groups, extras


def cannon_parts(Cf, groups, extras, p):
    """Cañón de feria en su marco Cf (z' hacia la boca, y' arriba, origen en el apoyo de la cadera):
    duelas de madera pintadas a franjas, aros, culata y boca de hierro, asa, mecha con brasa y la punta
    del cohete asomando (si está cargado)."""
    M = Cf.M()
    Z0, Z1 = -13.0, 16.5
    body = [CappedCone(Cf.p((0, 0, Z0)), Cf.p((0, 0, Z1)), 5.5, 4.9, WOOD),
            Ellipsoid(Cf.p((0, 0, Z0 - 0.5)), (5.8, 5.8, 3.3), M, IRON),                   # culata
            RoundCone(Cf.p((0, 0, Z0 - 3.0)), Cf.p((0, 0, Z0 - 5.0)), 1.6, 1.3, IRON),
            Sphere(Cf.p((0, 0, Z0 - 5.8)), 2.1, IRON),                                       # cascabel
            CappedCone(Cf.p((0, 0, Z1 - 0.5)), Cf.p((0, 0, Z1 + 5.0)), 5.1, 6.7, IRON),     # boca acampanada
            Ring(Frame(Cf.p((0, 0, Z1 + 5.0)), M @ rot_x(rad(90))), 6.4, 6.4, 0.95, IRON)]
    for z, r in ((-9.5, 5.45), (-2.0, 5.3), (5.5, 5.15), (12.5, 5.0)):
        body.append(Ring(Frame(Cf.p((0, 0, z)), M @ rot_x(rad(90))), r, r, 0.8, IRON))
    # muñones a los lados (hierro)
    for sx in (-1, 1):
        body.append(RoundCone(Cf.p((4.5 * sx, 0, 1.5)), Cf.p((7.0 * sx, 0, 1.5)), 1.5, 1.4, IRON))

    def bore_cut(P, Cf=Cf, z=Z1 - 9.0):
        q = Cf.to_local(P)
        d = np.maximum(np.hypot(q[:, 0], q[:, 1]) - BORE_R, z - q[:, 2])
        return -d
    groups.append(Group(body, k=0.35, cut=bore_cut, name='cannon'))
    extras['cannon'] = (Cf.o, Cf.R, Z0 + 0.5, Z1 + 5.5)
    if p['loaded']:
        groups.append(Group([CappedCone(Cf.p((0, 0, Z1 - 4.0)), Cf.p((0, 0, Z1 + 3.2)), 3.2, 0.45, ROCKET)],
                            name='rocket'))
    # asa de hierro encima (por donde lo agarra la mano derecha)
    groups.append(Group([RoundCone(Cf.p((0, 4.8, -3.0)), Cf.p((0, 8.6, -2.2)), 0.9, 0.85, IRON),
                         RoundCone(Cf.p((0, 4.8, 5.0)), Cf.p((0, 8.6, 4.2)), 0.9, 0.85, IRON),
                         RoundCone(Cf.p((0, 8.6, -2.2)), Cf.p((0, 8.6, 4.2)), 1.05, 1.05, IRON)],
                        k=0.3, name='grip'))
    # mecha: sale del oído de la culata, se riza; brasa en la punta
    mk = [Cf.p((0, 5.0, -9.0)), Cf.p((0.4, 7.2, -9.6)), Cf.p((1.6, 8.6, -9.0)), Cf.p((2.8, 8.8, -7.8)),
          Cf.p((3.4, 7.9, -6.6))]
    fuse = [RoundCone(mk[i], mk[i + 1], 0.75, 0.7, FUSE) for i in range(len(mk) - 1)]
    groups.append(Group(fuse, k=0.2, name='fuse'))
    if p['ember'] > 0:
        ec = mk[-1] + Cf.d((0.2, -0.4, 0.5))
        groups.append(Group([Sphere(ec, 0.9 + 0.25 * p['ember'], EMBER)], name='ember'))
        extras['ember'] = (ec, 1.2 + 0.3 * p['ember'], 1.0 + p['ember'])
    if p['flash']:
        size, seed = p['flash']
        rng = np.random.default_rng(seed)
        mz = Cf.p((0, 0, Z1 + 6.0))
        f = Cf.d((0, 0, 1))
        core = mz + f * size * 0.7
        fl = [Sphere(core, size * 0.62, FLASH), RoundCone(mz + f * 0.5, mz + f * size * 2.8, size * 0.55, 0.4, FLASH)]
        for k in range(7):
            a = 2 * math.pi * k / 7 + rng.uniform(-0.3, 0.3)
            dd = nrm(Cf.d((math.cos(a), math.sin(a), rng.uniform(0.2, 0.9))))
            ln = size * rng.uniform(1.1, 1.9)
            fl.append(RoundCone(core, core + dd * ln, size * 0.32, 0.25, FLASH))
        groups.append(Group(fl, k=1.2, name='flash'))
        extras['flash_core'] = (core, size * 2.2)
        extras['flash_light'] = (core, size * 7.0)


# ----------------------------------------------------------------------------- poses
def walk(i):
    """Pisotones pesados: A y C con los dos pies en el suelo (el golpe: el cuerpo baja), B y D con una pata
    en el aire; el brazo libre se balancea, el cañón bota en la cadera, la barba y el rabo se mecen."""
    a = i * math.pi / 2
    c, s = math.cos(a), math.sin(a)
    return dict(
        bob=-2.6 * abs(c) + 0.6 * abs(s), lean=12 + 2.0 * abs(c), hunch=20 + 2.0 * abs(c),
        twist=-6 * c, side=3.0 * s,
        head_pitch=-2 + 3 * abs(c), head_roll=-3 * s, head_yaw=3 * c, jaw=0.1 + 0.15 * abs(c),
        foot_r=(-8.8, 0, 1.0 + 8.5 * c - 2.0 * max(0, -s)), lift_r=11.0 * max(0, -s), flex_r=40.0 * max(0, -s),
        foot_l=(8.8, 0, 1.0 - 8.5 * c - 2.0 * max(0, s)), lift_l=11.0 * max(0, s), flex_l=40.0 * max(0, s),
        hand_l=('root', (22.5, 41.0 - 1.5 * abs(c), 4.0 + 9.0 * c)),
        aim=-8.0 + 2.0 * abs(c), cannon_yaw=20.0 + 3.0 * c, cannon_roll=3.0 * s,
        tail_sway=-2.0 * s, beard_wind=(-0.6 * s, 0.4 * abs(c), -0.6 * abs(c)),
    )


ATK_E = dict(lean=16, hunch=18, twist=-6, bob=-3.5, head_pitch=-6, head_yaw=4, jaw=0.35,
             foot_r=(-10.5, 0, 6.5), foot_l=(10.5, 0, -6.0),
             hand_l='barrel', curl_l=1.1, pole_l=(0.7, -0.6, -0.3),
             aim=-6.0, cannon_yaw=26.0, ember=2.5, tail_up=0.3, tail_sway=1.0, beard_wind=(0.3, 0.0, -0.5),
             fx=[dict(kind='sparks', at=('cannon', (3.6, 7.6, -6.1)), r=(2, 6), n=7, seed=13, fall=0.8, tail=(1, 3),
                      cols=['oro', 'oro', 'rojo', 'blanco'])])
ATK_F = dict(lean=6, hunch=14, twist=-4, bob=-2.5, head_pitch=10, head_yaw=2, jaw=1.1,
             foot_r=(-10.5, 0, 6.5), foot_l=(10.5, 0, -6.0),
             hand_l='barrel', curl_l=1.1, pole_l=(0.7, -0.6, -0.2),
             aim=-3.0, cannon_yaw=25.0, recoil=3.0, loaded=False, ember=0.0, muzzle_light=52.0,
             tail_up=0.6, tail_sway=-1.5, beard_wind=(0.3, 0.5, -1.6),
             fx=[dict(kind='fire', at=('cannon', (0, 0, 23.0)), dir=('cannon', (0, 0, 1)), len=13.0, r=10.0, seed=11),
                 dict(kind='sparks', at=('cannon', (0, 0, 27.0)), r=(9, 22), n=16, seed=12, fall=0.5),
                 dict(kind='smoke', at=('cannon', (3.5, 8.0, -6.5)), h=14, w=(3, 8), seed=5, dens=0.5)])
PAIN = dict(lean=-6, hunch=10, twist=-12, side=-5, bob=0.5, head_pitch=24, head_roll=12, head_yaw=10, jaw=1.4,
            foot_r=(-9.5, 0, -2.0), foot_l=(9.0, 0, 4.0), lift_l=1.5,
            hand_l=('chest', (9.0, 9.0, 17.0)), dir_l=(-0.5, 0.6, 0.3), palm_l=(-0.3, 0, -1), curl_l=1.1,
            pole_l=(0.8, -0.6, 0.1),
            aim=8.0, cannon_roll=-10.0, cannon_yaw=12.0, tail_up=0.8, tail_sway=2.5,
            beard_wind=(0.8, 0.8, -1.8))


# ----------------------------------------------------------------------------- muerte (H-P)
# H: le revienta el cañón en la cadera (fuego, duelas y aros saltando; se aparta con el brazo en alto);
# I: berrea con la cabeza atrás, el brazo y el costado derechos quemados y el muñón del cañón ardiendo;
# J: se tambalea y el cañón destrozado cae a su derecha; K: cae de rodillas; L-N: se desploma de lado hacia
# su izquierda (derecha de la pantalla), de cara a quien mira; O: tendido; P (para siempre): un montón de pelo
# y cuernos, aplastado, que humea, junto a los restos del cañón.
def plank(c, d, ln, wdt, mat, up=(0, 1, 0)):
    d = nrm(d)
    return Box(c, (wdt, 0.55, ln / 2), basis(d, up), 0.25, mat)


def cannon_burst(Cf, extras, seed=7):
    """El cañón revienta: queda la culata, y las duelas pintadas y dos aros salen despedidos (el fuego es 2D)."""
    rng = np.random.default_rng(seed)
    M = Cf.M()
    breech = [Ellipsoid(Cf.p((0, 0, -13.5)), (5.8, 5.8, 3.3), M, IRON), Sphere(Cf.p((0, 0, -18.8)), 2.1, IRON),
              RoundCone(Cf.p((0, 0, -16.0)), Cf.p((0, 0, -18.0)), 1.6, 1.3, IRON)]
    staves = []
    for k in range(9):
        a = 2 * math.pi * k / 9 + rng.uniform(-0.25, 0.25)
        out = Cf.d((math.cos(a), math.sin(a), rng.uniform(-0.2, 0.7)))
        c = Cf.p((0, 0, rng.uniform(-2, 8))) + out * rng.uniform(11, 19)
        d = nrm(out + Cf.d(tuple(rng.uniform(-0.8, 0.8, 3))))
        staves.append(plank(c, d, rng.uniform(6, 10), 1.3, [WOOD, PAINT_R, PAINT_Y, PAINT_G][k % 4],
                            up=nrm(np.cross(d, Cf.d((0, 0, 1))) + V(0, 0.01, 0))))
    hoops = [Ring(Frame(Cf.p((-3.0, 13.0, 4.0)), M @ rot_x(rad(60)) @ rot_z(rad(20))), 5.0, 5.0, 0.75, IRON),
             Ring(Frame(Cf.p((6.0, -6.0, 16.0)), M @ rot_y(rad(50)) @ rot_x(rad(30))), 4.8, 4.8, 0.75, IRON)]
    c = Cf.p((0, 0, 1.0))
    extras['flash_light'] = (c, 48.0)
    extras['burn'].append((Cf.p((0, 0, -12.0)), 7.0))
    return [Group(breech, k=0.5, name='cannon'), Group(staves, k=0.2, name='splinters'),
            Group(hoops, name='splinters')]


def cannon_stump(Cf, extras, seed=9):
    """Lo que queda en la cadera: la culata y el primer aro con las duelas abiertas como una flor, chamuscadas."""
    rng = np.random.default_rng(seed)
    M = Cf.M()
    parts = [Ellipsoid(Cf.p((0, 0, -13.5)), (5.8, 5.8, 3.3), M, IRON), Sphere(Cf.p((0, 0, -18.8)), 2.1, IRON),
             RoundCone(Cf.p((0, 0, -16.0)), Cf.p((0, 0, -18.0)), 1.6, 1.3, IRON),
             Ring(Frame(Cf.p((0, 0, -9.5)), M @ rot_x(rad(90))), 5.45, 5.45, 0.8, IRON)]
    staves = []
    for k in range(10):
        a = 2 * math.pi * k / 10 + rng.uniform(-0.15, 0.15)
        rr = V(math.cos(a), math.sin(a), 0)
        ln = rng.uniform(5, 12)
        splay = rng.uniform(0.25, 0.7)
        d = nrm(Cf.d(rr * splay + V(0, 0, 1)))
        a0 = Cf.p(rr * 5.0 + V(0, 0, -11.0))
        staves.append(plank(a0 + d * ln / 2, d, ln, 1.25, [WOOD, PAINT_R, PAINT_Y, PAINT_G][k % 4],
                            up=Cf.d(rr)))
    extras['burn'].append((Cf.p((0, 0, -6.0)), 14.0))
    return [Group(parts, k=0.4, name='cannon'), Group(staves, k=0.15, name='cannon')]


def wreck_ground(Fl, seed=3):
    """Restos del cañón tirados en el suelo (marco Fl en el suelo del mundo): culata, duelas sueltas y aros."""
    def make(base, where, Fl=Fl, seed=seed):
        rng = np.random.default_rng(seed)
        F = base * Fl
        M = F.M()
        parts = [Ellipsoid(F.p((0, 5.0, 0)), (3.3, 5.6, 5.6), M @ rot_y(rad(90)), IRON),
                 Sphere(F.p((-5.6, 2.6, 0.0)), 2.1, IRON),
                 RoundCone(F.p((-2.8, 3.6, 0)), F.p((-5.0, 2.8, 0)), 1.6, 1.3, IRON),
                 Ring(Frame(F.p((2.6, 5.0, 0)), M @ rot_z(rad(90))), 5.45, 5.45, 0.8, IRON)]
        wood = []
        for k in range(8):
            a = (k - 3.5) * 0.32 + rng.uniform(-0.12, 0.12)
            ln = rng.uniform(10, 17)
            st = F.p((3.0, 1.0 + 4.5 * abs(math.sin(a * 2.0)), 0)) + F.d((0, 0, math.sin(a) * 3.5))
            d = nrm(F.d((math.cos(a), -0.06 - 0.25 * abs(math.sin(a * 2.0)) / max(ln, 1), math.sin(a))))
            c = st + d * ln / 2
            c[1] = max(c[1], F.o[1] + 0.8)
            wood.append(plank(c, d, ln, 1.3, [WOOD, PAINT_R, PAINT_Y, PAINT_G][k % 4]))
        hoops = [Ring(Frame(F.p((21.0, 0.8, 4.0)), M @ rot_x(rad(3))), 5.1, 5.1, 0.75, IRON),
                 Ring(Frame(F.p((14.0, 3.6, -6.0)), M @ rot_z(rad(72)) @ rot_y(rad(20))), 4.9, 4.9, 0.75, IRON)]
        return [Group(parts, k=0.4, name='wreck'), Group(wood, k=0.15, name='wreck'), Group(hoops, name='wreck')]
    return make


def blood_pool(c, rr, ang):
    def make(base, where):
        return [Group([Ellipsoid(base.p(c), rr, rot_y(rad(ang)), POOL)], name='pool')]
    return make


def topple(alpha, roll=0.0, t=(0.0, 0.0, 0.0)):
    """Marco raíz volcado alpha grados hacia su izquierda (giro alrededor de z, la cara sigue hacia la cámara)
    tras girar roll grados sobre su eje vertical."""
    return Frame(V(t), rot_z(rad(-alpha)) @ rot_y(rad(roll)))


WRECK = Frame((-34.0, 0.0, 8.0), rot_y(rad(28)))


def deaths():
    burn_sh = [('up', (-14.0, -2.0, 4.0), 9.5), ('up', (-15.5, 8.0, 1.0), 6.0)]          # cadera y costado derechos
    st = [('up', (-9.0, 6.0, 9.5), 2.4), ('up', (-12.5, 1.0, 8.0), 1.8), ('up', (-6.5, 10.0, 9.0), 1.6)]
    H = dict(lean=-2, hunch=12, twist=-16, side=4, bob=0.2, head_pitch=6, head_yaw=30, head_roll=-10, jaw=1.3,
             foot_r=(-9.5, 0, -1.5), foot_l=(9.5, 0, 3.0),
             hand_l=('chest', (4.0, 18.0, 15.0)), dir_l=(-0.3, 0.8, 0.4), palm_l=(-0.2, 0, 1), curl_l=0.5,
             spread_l=1.6, pole_l=(0.8, -0.5, -0.2),
             cannon='burst', aim=6.0, cannon_yaw=14.0, hand_r=('root', (-33.0, 66.0, 2.0)), dir_r=(-0.6, 0.7, 0.2),
             palm_r=(0.3, 0, 1), curl_r=0.3, spread_r=1.7, pole_r=(-0.6, -0.7, -0.3),
             tail_up=0.9, tail_sway=2.0, beard_wind=(1.2, 0.5, -1.0),
             fx=[dict(kind='fire', at=('cannon', (0.0, 0.0, 2.0)), r=15.0, seed=21),
                 dict(kind='smoke', at=('cannon', (0.0, 13.0, -2.0)), h=18, w=(8, 14), seed=23, dens=0.5),
                 dict(kind='sparks', at=('cannon', (0.0, 0.0, 2.0)), r=(15, 30), n=26, seed=22)])
    I = dict(lean=-9, hunch=6, twist=-6, side=-3, bob=0.8, head_pitch=52, head_yaw=-6, head_roll=8, jaw=1.6,
             foot_r=(-9.0, 0, -3.5), foot_l=(9.5, 0, 2.5), lift_l=1.0,
             hand_l=('up', (-8.0, 4.0, 12.5)), dir_l=(-0.9, -0.2, -0.2), palm_l=(0, -0.3, -1), curl_l=1.0,
             pole_l=(0.7, -0.5, 0.4),
             cannon='stump', aim=-16.0, cannon_yaw=16.0, cannon_roll=-20, hand_r=('root', (-27.0, 40.0, -3.0)), curl_r=0.6,
             pole_r=(-0.5, 0.2, -0.8), burn=burn_sh + [('root', (-26.0, 44.0, -2.0), 6.0)], stains=st,
             spray=[('up', (-18.0, 2.0, 9.0), 1.3), ('up', (-21.0, 4.0, 12.0), 1.0), ('up', (-23.0, 0.0, 13.5), 0.8)],
             tail_up=0.6, tail_sway=-1.5, beard_wind=(0.4, 0.9, -1.4),
             fx=[dict(kind='fire', at=('cannon', (0.0, 1.0, -5.0)), r=6.5, seed=31),
                 dict(kind='smoke', at=('cannon', (0.0, 6.0, -6.0)), h=34, w=(6, 15), seed=32, dens=0.62)])
    J = dict(lean=20, hunch=24, twist=14, side=9, bob=-5.0, head_pitch=-14, head_yaw=12, head_roll=14, jaw=1.0,
             foot_r=(-11.0, 0, -5.0), foot_l=(10.0, 0, 6.0),
             hand_l=('root', (21.0, 32.0, 14.0)), curl_l=0.9,
             cannon=wreck_ground(WRECK), hand_r=('root', (-21.0, 32.0, 6.0)),
             curl_r=0.7, burn=burn_sh, stains=st, tail_sway=2.5,
             fx=[dict(kind='fire', at=('world', (-32.0, 7.0, 8.0)), r=5.0, seed=41),
                 dict(kind='smoke', at=('world', (-32.0, 10.0, 8.0)), h=34, w=(5, 14), seed=42, dens=0.6),
                 dict(kind='smoke', at=('up', (-15.0, 0.0, 3.0)), h=22, w=(3, 8), seed=43, dens=0.55)])
    K = dict(kneel=(5.0, 3.0), bob=-27.5, lean=8, hunch=28, side=3, head_pitch=-22, head_roll=10, jaw=1.2,
             hand_l=('root', (22.0, 5.0, 10.0)), curl_l=0.8, hand_r=('root', (-22.0, 5.5, 9.0)), curl_r=0.8,
             cannon=wreck_ground(WRECK), burn=burn_sh, stains=st, tail_sway=-1.0,
             fx=[dict(kind='smoke', at=('world', (-32.0, 8.0, 8.0)), h=38, w=(5, 15), seed=51, dens=0.58),
                 dict(kind='smoke', at=('up', (-15.0, 0.0, 3.0)), h=20, w=(3, 7), seed=52, dens=0.5)])
    kneel = dict(kneel=(5.0, 3.0), bob=-27.5, lean=12, hunch=28, side=0, head_pitch=-10, head_roll=-10, jaw=1.4,
                 cannon=wreck_ground(WRECK), burn=burn_sh, stains=st, tail_sway=-1.0)
    L = dict(kneel, root=topple(22, 0, (-4.0, 0.0, 0.0)), lean=16, hunch=30, head_pitch=-16,
             hand_l=('world', (30.0, 2.0, 12.0)), dir_l=(0.4, -0.2, 1.0), palm_l=(0, -1, 0), curl_l=0.4,
             hand_r=('world', (-12.0, 18.0, 16.0)), curl_r=0.9,
             fx=[dict(kind='smoke', at=('world', (-32.0, 8.0, 8.0)), h=36, w=(4, 13), seed=61, dens=0.55)])
    M = dict(kneel, root=topple(52, 8, (-12.0, 0.0, 0.0)), lean=10, hunch=22, head_pitch=-4, head_roll=-18,
             hand_l=('world', (34.0, 2.0, 14.0)), dir_l=(0.5, -0.1, 1.0), palm_l=(0, -1, 0), curl_l=0.3,
             hand_r=('world', (-2.0, 30.0, 18.0)), curl_r=0.8, tilt=13.0, lift_px=7,
             fx=[dict(kind='smoke', at=('world', (-32.0, 8.0, 8.0)), h=34, w=(4, 12), seed=71, dens=0.52)])
    lying = dict(kneel, root=topple(84, 18, (-24.0, 0.0, 0.0)), lean=6, hunch=16, head_pitch=4, head_roll=35,
                 head_yaw=-10, jaw=1.6,
                 hand_l=('world', (26.0, 2.0, 18.0)), dir_l=(0.2, -0.1, 1.0), palm_l=(0, -1, 0), curl_l=0.6,
                 hand_r=('world', (8.0, 16.0, 20.0)), dir_r=(0.3, -0.6, 0.6), curl_r=0.8,
                 tilt=18.0, lift_px=8)
    N = dict(lying, fx=[dict(kind='smoke', at=('world', (-32.0, 8.0, 8.0)), h=30, w=(4, 11), seed=81, dens=0.5),
                        dict(kind='smoke', at=('world', (-6.0, 22.0, 6.0)), h=20, w=(3, 8), seed=82, dens=0.5)],
             extra=[blood_pool((-14.0, 0.15, 12.0), (9.0, 0.4, 5.0), -8)])
    O = dict(lying, flatten=(np.diag([1.0, 0.85, 1.0]), (0, 0, 0), 0.85), eyes=False, jaw=1.8,
             fx=[dict(kind='smoke', at=('world', (-32.0, 6.0, 8.0)), h=30, w=(4, 11), seed=91, dens=0.5),
                 dict(kind='smoke', at=('world', (-6.0, 18.0, 6.0)), h=26, w=(3, 9), seed=92, dens=0.55)],
             extra=[blood_pool((-14.0, 0.15, 12.0), (12.0, 0.4, 6.0), -8)], tilt=20.0)
    P = dict(lying, flatten=(np.diag([1.05, 0.62, 1.0]), (0, 0, 0), 0.7), eyes=False, jaw=1.8,
             fx=[dict(kind='smoke', at=('world', (-32.0, 5.0, 8.0)), h=26, w=(3, 9), seed=101, dens=0.48),
                 dict(kind='smoke', at=('world', (-4.0, 12.0, 6.0)), h=30, w=(3, 10), seed=102, dens=0.55),
                 dict(kind='smoke', at=('world', (18.0, 12.0, 4.0)), h=22, w=(2, 7), seed=103, dens=0.5)],
             extra=[blood_pool((-14.0, 0.15, 12.0), (14.0, 0.4, 7.0), -8)], tilt=22.0)
    return [H, I, J, K, L, M, N, O, P]


# ----------------------------------------------------------------------------- efectos 2D
def screen_map(groups, angle, tilt):
    """Misma proyección que sdf.Render.render: punto del modelo → (columna, fila, profundidad) continuas del
    lienzo (la profundidad es la del rayo, comparable con la que devuelve el trazado)."""
    th = (angle - 1) * math.pi / 4 if angle else 0.0
    R = rot_y(-th)
    Uc = V(0, math.cos(tilt), -math.sin(tilt))
    Dc = V(0, -math.sin(tilt), -math.cos(tilt))
    xs, ys = [], []
    for g in groups:
        c, r = g.model_bound()
        cc = R @ c
        xs += [cc[0] - r, cc[0] + r]
        ys += [cc @ Uc - r, cc @ Uc + r]
    hw = int(math.ceil(max(-min(xs), max(xs)))) + 2
    top = int(math.ceil(max(ys))) + 2

    def f(P):
        pc = R @ V(P)
        return pc[0] + hw, top - pc @ Uc, pc @ Dc + 400.0
    return f


FIRE_COL = None


def _fire_cols():
    global FIRE_COL
    if FIRE_COL is None:
        from arma1p import FUEGO
        FIRE_COL = np.array(FUEGO, np.uint8)
    return FIRE_COL


def paint_fx(img, depth, fxs, proj):
    """Pinta humo (detrás: solo donde no hay nada), fuego y chispas (delante de lo que queda detrás de su
    centro: se respeta la profundidad del trazado). Devuelve la imagen (con margen añadido arriba y a los lados
    si hace falta) y cuántas filas se añadieron arriba."""
    H, W = img.shape[:2]
    pt, px = 0, 0
    for f in fxs:
        cx, cy, _ = proj(f['at'])
        if f['kind'] == 'smoke':
            need_up, need_x = f['h'] + f['w'][1] + 2 - cy, f['w'][1] + 6 + max(-cx, cx - W)
        elif f['kind'] == 'fire':
            ext = f['r'] * 1.8 + f.get('len', 0.0)
            need_up, need_x = ext + 2 - cy, ext + 2 + max(-cx, cx - W)
        else:
            need_up, need_x = f['r'][1] + 8 - cy, f['r'][1] + 8 + max(-cx, cx - W)
        pt = max(pt, int(math.ceil(need_up)))
        px = max(px, int(math.ceil(need_x)))
    big = np.zeros((H + pt, W + 2 * px, 4), np.uint8)
    big[pt:, px:px + W] = img
    dep = np.full((H + pt, W + 2 * px), np.inf)
    dep[pt:, px:px + W] = depth
    img, depth = big, dep
    H, W = img.shape[:2]
    empty0 = img[..., 3] == 0

    def at(P):
        cx, cy, cz = proj(P)
        return cx + px, cy + pt, cz
    # 1) humo: solo donde no había nada (queda detrás del cuerpo)
    for f in fxs:
        if f['kind'] != 'smoke':
            continue
        cx, cy, _ = at(f['at'])
        x, y = malla(W, H, cx, cy)                            # y hacia arriba desde la base del penacho
        hgt, (w0, w1), seed = f['h'], f['w'], f['seed']
        t = np.clip(y / hgt, 0, 1)
        sway = 3.0 * np.sin(y * 0.18 + seed) * t
        wid = w0 + (w1 - w0) * t
        env = 1.0 - np.abs(x - sway) / np.maximum(wid, 0.5)
        env = np.where((y > -2) & (y < hgt + w1 * 0.5), env, -1)
        env -= np.clip((y - hgt) / (w1 * 0.6), 0, 1)
        n = fbm2(x * 1.0, y * 0.8 - seed * 3, 0.16, seed)
        dens = env * 0.9 + (n - 0.5) * 1.3 - (1 - f.get('dens', 0.6))
        vis, _ = reducir2(dens, 0.0, W, H)
        vis &= empty0 & (img[..., 3] == 0)
        luz = np.clip(0.35 + 0.3 * (n - 0.5) * 2 + 0.25 * (-(x - sway) / np.maximum(wid, 1)) + 0.25 * t, 0, 1)
        lm = luz.reshape(H, SS2, W, SS2).mean(axis=(1, 3))
        ramp = np.array(HUMO, np.uint8)
        idx = np.clip(np.round(lm * (len(ramp) - 1)), 0, len(ramp) - 1).astype(int)
        img[vis, :3] = ramp[idx[vis]]
        img[vis, 3] = 255
    # 2) fuego: manchas a lo largo de 'dir' (chorro) con lenguas de ruido; tapa lo que queda detrás
    cols = _fire_cols()
    for f in fxs:
        if f['kind'] != 'fire':
            continue
        seed, R0 = f['seed'], f['r']
        P0 = V(f['at'])
        dvec = V(f.get('dir', (0, 0, 0)))
        L = f.get('len', 0.0)
        nb = 1 + int(L / max(R0 * 0.5, 1.0)) if L > 0 else 1
        heat = None
        zc = []
        for k in range(nb):
            u = k / max(nb - 1, 1)
            cx, cy, cz = at(P0 + dvec * L * u)
            zc.append(cz)
            x, y = malla(W, H, cx, cy)
            r = np.hypot(x, y * 0.92)
            th = np.arctan2(y, x)
            lob = fbm2(np.cos(th) * 2.6, np.sin(th) * 2.6, 1.0, seed + 7 * k)
            Rk = R0 * (1.0 - 0.55 * u) * (0.6 + 0.65 * lob)
            hk = 1.15 - r / Rk - 0.25 * u
            heat = hk if heat is None else np.maximum(heat, hk)
        x, y = malla(W, H, *at(P0)[:2])
        heat = heat + 0.42 * (fbm2(x, y, 0.3, seed + 3) - 0.5)
        vis, hm = reducir2(heat, 0.04, W, H)
        front = min(zc) - R0 * 0.5
        vis &= (img[..., 3] == 0) | (depth > front)
        n = len(cols)
        idx = np.clip(((1.0 - np.clip(hm, 0, 1)) ** 1.15) * (n - 1) + 0.3, 0, n - 1).astype(int)
        img[vis, :3] = cols[idx[vis]]
        img[vis, 3] = 255
        depth[vis] = np.minimum(depth[vis], front)
    # 3) chispas (con estela), también tapadas por lo que queda delante
    for f in fxs:
        if f['kind'] != 'sparks':
            continue
        cx, cy, cz = at(f['at'])
        rng = np.random.default_rng(f['seed'])
        r0, r1 = f['r']
        layer = np.zeros_like(img)
        for _ in range(f['n']):
            a = rng.uniform(0, 2 * math.pi)
            rr = rng.uniform(r0, r1)
            hx, hy = cx + math.cos(a) * rr, cy - math.sin(a) * rr * 0.9
            chispa(layer, hx, hy, math.cos(a), -math.sin(a) * 0.9 + f.get('fall', 0.3), rng.uniform(*f.get('tail', (3, 7))),
                   f.get('cols', ['oro', 'rojo', 'oro', 'blanco', 'verde'])[rng.integers(len(f.get('cols', 'abcde')))],
                   int(rng.integers(0, 2)))
        vis = (layer[..., 3] > 0) & ((img[..., 3] == 0) | (depth > cz - 3.0))
        img[vis] = layer[vis]
    return img, pt


# ----------------------------------------------------------------------------- salida
OFFSETS = {}


def draw_creature(pose, angle):
    """→ (imagen recortada, offsets): eje del cuerpo en el centro, suelo del modelo SINK px bajo el origen."""
    groups, extras = build(pose)
    tilt = rad(pose.get('tilt', 10.0))
    R = render(tilt)
    Rv = rot_y(-((angle - 1) * math.pi / 4 if angle else 0.0))       # misma cámara que sdf.Render.render
    extras['view'] = (nrm((-0.8, 0.55, -0.15)) @ Rv,                     # luz de borde (arriba-izquierda, detrás)
                      -(V(0, -math.sin(tilt), -math.cos(tilt)) @ Rv),    # hacia la cámara
                      nrm((-0.5, 0.75, 0.55)) @ Rv)                      # luz principal
    out, depth = R.render(groups, extras, angle)
    img = np.array(finish(out, depth, R.palarr, OUTLINE))
    H = out.shape[0]
    floor_row = (H - 1) - pose.get('lift_px', L_PX)          # borde superior de esta fila = suelo en el eje
    if extras['fx']:
        img, pt = paint_fx(img, depth, extras['fx'], screen_map(groups, angle, tilt))
        floor_row += pt
        h, w = img.shape[:2]
        for x in (0, w - 1):
            if img[h - 1, x, 3] == 0:
                img[h - 1, x] = (0, 0, 0, 1)
    r0 = int(np.nonzero((img[:, :, 3] >= 128).any(1))[0].min())
    t = trim(Image.fromarray(img, 'RGBA'))
    return t, [t.width // 2, floor_row - SINK - r0]


def lumps():
    out = {}
    for fi, fr in enumerate('ABCD'):
        for a in range(1, 9):
            out[f'CYBR{fr}{a}'] = ((f'CYBR{fr}{a}', walk(fi)), a)
    for fr, pose in (('E', ATK_E), ('F', ATK_F), ('G', PAIN)):
        for a in range(1, 9):
            out[f'CYBR{fr}{a}'] = ((f'CYBR{fr}{a}', pose), a)
    for fr, pose in zip('HIJKLMNOP', deaths()):
        out[f'CYBR{fr}0'] = ((f'CYBR{fr}0', pose), 1)
    return out


def draw(item, angle):
    name, pose = item
    img, off = draw_creature(pose, angle)
    OFFSETS[name] = off
    return img


def guardar_offsets(salida):
    """Actualiza arte/sprites/offsets_cabron.json con los lumps dibujados (sin perder los demás)."""
    path = os.path.join(salida, 'offsets_cabron.json')
    data = {}
    if os.path.exists(path):
        data = json.load(open(path))
    data.update(OFFSETS)
    with open(path, 'w') as f:
        f.write('{\n' + ',\n'.join(f'  "{k}": [{v[0]}, {v[1]}]' for k, v in sorted(data.items())) + '\n}\n')


# Render en paralelo: unos procesos llenan una caché y luego sdf.cli guarda los PNG y la hoja como siempre.
# El resultado es idéntico al secuencial (cada sprite es independiente y sus semillas son fijas).
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


ROWS = sprite_rows('CYBR', 'ABCDEFG', 'HIJKLMNOP')

if __name__ == '__main__':
    from concurrent.futures import ProcessPoolExecutor
    ap = argparse.ArgumentParser()
    ap.add_argument('--salida', required=True)
    ap.add_argument('--solo', default='')
    ap.add_argument('--procesos', type=int, default=5)
    args, rest = ap.parse_known_args()
    todos = lumps()
    names = [n.strip().upper() for n in args.solo.split(',') if n.strip()] or list(todos)
    pesados = sorted(names, key=lambda n: (n[4] < 'H', n))          # muertes primero: reparto parejo
    if len(names) > 1 and args.procesos > 1:
        with ProcessPoolExecutor(max_workers=min(args.procesos, os.cpu_count() or 1)) as ex:
            for name, arr, off in ex.map(_work, pesados):
                CACHE[name] = (Image.fromarray(arr, 'RGBA'), off)
    sys.argv = [sys.argv[0], '--salida', args.salida] + (['--solo', args.solo] if args.solo else []) + rest
    cli(lumps, draw_cached, ROWS)
    guardar_offsets(args.salida)
