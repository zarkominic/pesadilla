#!/usr/bin/env python3
"""cohetes.py — EL LANZACOHETES DE FERIA y SU COHETE (sustituyen al lanzacohetes de Freedoom),
dibujados por código.

Uso:
    ~/.venvs/pesadilla/bin/python tools/arte/cohetes.py --salida arte/sprites
    … --solo MISGA0,MISLA1        solo esos lumps
    … --vista <png>               además, pantallas simuladas del arma (con barra y sin ella)
    … --hoja <png>                además, hoja de contactos ampliada del cohete, la explosión y LAUN

Escribe:
- MISGA0 (reposo; también al subir y bajar) y MISGB0 (disparo: retroceso, humo en la boca y en el
  oído de la mecha). En el juego (info.c): MISG B dura 8 + 12 tics y encima van los fogonazos.
- MISFA0-MISFD0: fogonazo y chispas de pólvora a la salida del cohete (a pleno brillo).
- LAUNA0: el lanzacohetes tirado en el suelo, para recogerlo.
- MISLA1-MISLA8: el cohete en vuelo (rota: 8 ángulos reales, a pleno brillo) y MISLB0-MISLD0, la
  explosión de traca (también la usa el cohete del Gran Cabrón).
Y los desplazamientos de todos en <salida>/offsets_cohetes.json (arma1p.guardar_offsets).

El ARMA (motor común arma1p.py: misma proyección, luz, paleta y contorno que el pistolón y la
escopeta): un tubo gordo de cartón pintado en espiral con franjas de feria (rojo, amarillo y verde,
gastadas y con roña: a trozos asoma el cartón; la boca, tiznada), atado con aros de latón a una
canal de madera; boca con brocal de latón y la punta del cohete dentro (en el fotograma de reposo);
mecha lenta que sale del oído y se riza con la brasa encendida; el tubo va apoyado en el hombro
derecho (entra por la esquina de abajo a la derecha, apunta al centro) y la mano izquierda
enguantada (manga de paño granate, como las otras armas) lo sujeta por un asa de nogal que sale del
costado izquierdo, con el dorso a la vista.

El COHETE (motor de criaturas sdf.py: trazado ortográfico, rampas exactas de PLAYPAL, contorno de
1 px): cono de papel rojo, cuerpo de cartón a franjas (rojo, amarillo, verde), varilla de caña
detrás y un chorro de chispas doradas que sale de la tobera (dibujado encima, sin contorno).
La explosión de traca es 2D (como la bola de la Meiga): fuego naranja, chispas de colores con
estela y humo, del tamaño de la de Freedoom. Todo determinista (ruido con semilla fija).
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from arma1p import (FUEGO, RAMPAS, Agarre, Arma, bocanada, caja, capsula, costuras,  # noqa: E402
                    dibujar, elipsoide, filo, guante, guardar, guardar_offsets, mano_agarre,
                    matriz_canon, mover_pose, pliegues_pano, proyectar, rot_x, rot_y, rot_z, smin,
                    tubo, tubo_z, unit, v3, veta)
import sdf  # noqa: E402

# ---------------------------------------------------------------------------------------------
# Paleta del arma: rampas de colores EXACTOS de PLAYPAL (índice 0 = línea de profundidad)
# ---------------------------------------------------------------------------------------------


def _pp(*idx):
    pal = sdf.read_palette(sdf.IWAD)
    return [tuple(pal[i]) for i in idx]


RAMPAS_COH = dict(
    RAMPAS,
    # pintura de feria gastada: rojo ladrillo, amarillo mostaza sucio, verde botella
    rojo=_pp(2, 47, 45, 43, 40, 38, 36, 34, 31),
    amarillo=_pp(1, 79, 151, 149, 147, 166, 165, 164, 163),
    verde=_pp(12, 127, 126, 125, 124, 123, 122, 121, 120),
    # cartón pelado (donde se ha ido la pintura) y bordes del tubo
    carton=_pp(239, 238, 237, 236, 141, 139, 137, 135),
    manga=RAMPAS['pano'],
    # mecha de cáñamo y su brasa
    mecha=_pp(7, 239, 238, 237, 236, 141, 139),
    brasa=_pp(186, 183, 179, 176, 215, 213, 211),
)
MATS = ['rojo', 'amarillo', 'verde', 'carton', 'laton', 'nogal', 'cuero', 'ribete', 'manga',
        'mecha', 'brasa', 'hueco']
BRILLO = {'rojo': (0.12, 8), 'amarillo': (0.12, 8), 'verde': (0.12, 8), 'carton': (0.04, 4),
          'laton': (0.6, 22), 'nogal': (0.15, 12), 'cuero': (0.12, 10), 'ribete': (0.1, 10),
          'manga': (0.0, 1), 'mecha': (0.0, 1), 'brasa': (0.0, 1), 'hueco': (0.0, 1)}
GANANCIA = {'rojo': 0.82, 'amarillo': 0.82, 'verde': 0.82, 'carton': 0.85, 'laton': 0.9, 'nogal': 0.86,
            'cuero': 1.0, 'ribete': 0.62, 'manga': 0.8, 'mecha': 0.8, 'brasa': 1.0, 'hueco': 0.5}

# ---------------------------------------------------------------------------------------------
# El modelo (espacio del arma: eje del tubo en z, de atrás hacia la boca; y arriba; x derecha)
# ---------------------------------------------------------------------------------------------

LARGO = 60.0                 # de z = 0 (punto de referencia de la pose) a la boca (cm)
Z0 = -26.0                   # culo del tubo (queda detrás del hombro, fuera de la pantalla)
RT = 3.5                     # radio del tubo de cartón
RI = 2.8                     # radio interior (por la boca)
PASO = 13.0                  # paso de la espiral de franjas (cm por vuelta)
ANILLOS = (6.0, 25.0, 43.0)   # aros de latón (centro en z)
ANCHO_ARO = 0.9              # medio ancho de cada aro
ZC = (-24.0, 47.0)           # canal de madera bajo el tubo
YC = -RT - 0.8               # centro de la canal (y)
ZG = 33.0                    # asa de nogal (delantera, al costado izquierdo)
ZM = 17.0                    # oído de la mecha
PINTURA = ('rojo', 'amarillo', 'verde')

# asa delantera: un mango de nogal que sale del costado izquierdo del tubo, hacia abajo y afuera;
# la mano izquierda lo agarra con el dorso hacia arriba (a la vista) y los dedos por delante
EJE_PUNO = unit(v3(-0.8, -0.6, -0.1))
BASE_PUNO = v3(0.0, 0.0, ZG) + RT * unit(v3(-0.8, -0.6, 0.0))
_GF = unit(v3(0.0, 0.0, 1.0) - EJE_PUNO[2] * EJE_PUNO)
MANO_I = Agarre(G0=BASE_PUNO + 2.2 * EJE_PUNO, GE=EJE_PUNO, GF=_GF, GX=np.cross(EJE_PUNO, _GF), r=1.65)
PLIEGUES = (8.0, 14.5, 21.0)

# mecha lenta: sale del oído, sube y se riza hacia la izquierda; la brasa en la punta
MECHA = [v3(0.0, RT + 0.9, ZM), v3(-0.1, RT + 2.3, ZM - 0.4), v3(-0.9, RT + 3.4, ZM - 0.3),
         v3(-2.2, RT + 3.8, ZM + 0.3), v3(-3.3, RT + 3.4, ZM + 0.9)]
BRASA = MECHA[-1] + v3(-0.45, -0.2, 0.2)


def _theta(P):
    """Ángulo alrededor del eje del tubo (0 arriba, creciendo hacia la derecha)."""
    return np.arctan2(P[:, 0], P[:, 1])


def franja(P):
    """Índice de la franja de pintura (0 rojo, 1 amarillo, 2 verde) en la espiral."""
    s = P[:, 2] / PASO + _theta(P) / (2 * math.pi)
    return np.floor(s * 3).astype(int) % 3


def gastado(P, semilla=4):
    """Trozos donde se ha ido la pintura (asoma el cartón): ruido determinista en la superficie."""
    q = np.column_stack([P[:, 0], P[:, 1], P[:, 2] * 0.55])
    n = sdf.vnoise(q, 0.8, semilla) * 0.6 + sdf.vnoise(q, 2.2, semilla + 1) * 0.4
    return n > 0.7


def pintar(P, dt, d, mats=PINTURA, cerca=0.5, gastar=True):
    """Reparte la superficie dt entre las franjas de pintura y el cartón pelado (solo los puntos
    cerca de la superficie: el ruido es caro; los lejanos van a la primera franja)."""
    sel = np.abs(dt) < cerca
    d[mats[0]] = np.where(~sel, np.minimum(d[mats[0]], dt), d[mats[0]])
    idx = np.nonzero(sel)[0]
    if not len(idx):
        return
    Q = P[idx]
    k = franja(Q)
    g = gastado(Q) if gastar else np.zeros(len(Q), bool)
    for i, m in enumerate(mats):
        dd = np.where((k == i) & ~g, dt[idx], 1e9)
        d[m][idx] = np.minimum(d[m][idx], dd)
    d['carton'][idx] = np.minimum(d['carton'][idx], np.where(g, dt[idx], 1e9))


def cono_cohete(P, d, z_base):
    """La punta del cohete que asoma por la boca: cono de papel rojo con una franja amarilla."""
    zb, zt = z_base, z_base + 11.0
    cono = capsula(P, v3(0, 0, zb), v3(0, 0, zt), 2.65, 0.3)
    cono = np.maximum(cono, zb - P[:, 2])
    banda = (P[:, 2] > zb + 3.4) & (P[:, 2] < zb + 5.2)
    d['amarillo'] = np.minimum(d['amarillo'], np.where(banda, cono, 1e9))
    d['rojo'] = np.minimum(d['rojo'], np.where(banda, 1e9, cono))


def modelo(P, pose):
    d = {m: np.full(len(P), 1e9) for m in MATS}
    z = P[:, 2]
    # tubo de cartón, hueco por la boca
    alma = tubo_z(P, LARGO - 26.0, LARGO + 4.0, RI, RI)
    dt = np.maximum(tubo_z(P, Z0, LARGO - 2.2, RT, RT), -alma)
    pintar(P, dt, d, gastar=pose.get('gastado', True))
    d['hueco'] = np.minimum(d['hueco'], np.maximum(np.abs(alma) - 0.02, np.maximum(LARGO - 22.0 - z, z - LARGO)))
    # aros de latón (alrededor del tubo y de la canal) y brocal de la boca
    laton = None
    for z0 in ANILLOS:
        a = np.minimum(tubo_z(P, z0 - ANCHO_ARO, z0 + ANCHO_ARO, RT + 0.42, RT + 0.42),
                       caja(P, (0.0, YC - 0.2, z0), (2.05, 1.65, ANCHO_ARO), 0.45))
        laton = a if laton is None else np.minimum(laton, a)
    brocal = np.maximum(np.minimum(tubo_z(P, LARGO - 2.6, LARGO, RT + 0.62, RT + 0.62),
                                   tubo_z(P, LARGO - 3.4, LARGO - 2.4, RT + 0.3, RT + 0.3)), -alma)
    laton = np.minimum(laton, brocal)
    # oído de la mecha: un pezón de latón encima
    oido = tubo(P, v3(0.0, RT - 0.5, ZM), v3(0.0, RT + 0.95, ZM), 0.75, 0.6)
    laton = np.minimum(laton, oido)
    d['laton'] = laton
    # canal de madera bajo el tubo y puño delantero de nogal
    canal = caja(P, (0.0, YC, (ZC[0] + ZC[1]) / 2), (1.7, 1.25, (ZC[1] - ZC[0]) / 2), 0.6)
    canal = smin(canal, elipsoide(P, (0.0, YC - 0.2, ZC[1] - 0.4), (1.7, 1.2, 2.2)), 0.5)
    asa = capsula(P, BASE_PUNO - 1.5 * EJE_PUNO, BASE_PUNO + 11.0 * EJE_PUNO, 1.55, 1.75)
    pomo = elipsoide(P, BASE_PUNO + 11.6 * EJE_PUNO, (2.2, 2.2, 2.2))
    d['nogal'] = np.minimum(np.minimum(canal, asa), pomo)
    d['laton'] = np.minimum(d['laton'], tubo(P, BASE_PUNO - 0.6 * EJE_PUNO, BASE_PUNO + 1.3 * EJE_PUNO, 2.05, 1.95))
    # mecha lenta con su brasa (no en LAUNA0: tumbado, la mecha vertical con su rizo parecía una cruz)
    if pose.get('mecha', True):
        m = None
        for a, b in zip(MECHA[:-1], MECHA[1:]):
            c = capsula(P, a, b, 0.44, 0.4)
            m = c if m is None else np.minimum(m, c)
        d['mecha'] = m
        d['brasa'] = elipsoide(P, BRASA, (0.62, 0.62, 0.62))
    # la punta del cohete en la boca (cargado)
    if pose.get('cohete', True):
        cono_cohete(P, d, LARGO - 2.6)
    # mano izquierda en el puño delantero
    if pose.get('manos', True):
        mi, w0 = mano_agarre(P, MANO_I, pose['brazo_i'])
        dm = {'cuero': mi}
        guante(dm, P, w0, pose['brazo_i'], largo_manga=46.0)
        for k in ('cuero', 'ribete', 'manga'):
            d[k] = np.minimum(d[k], dm[k])
    D = np.stack([d[k] for k in MATS], 1)
    return D.min(1), D.argmin(1)


def detalle(arma, r, I):
    """Veta del nogal, papel del tubo, pliegues y filo de la manga, pespuntes del guante, brasa."""
    veta(arma, r, I)
    pose = r.get('pose') or {}
    pl = r['pl']
    # textura de papel y mugre: la pintura no es lisa; más sucia junto a los aros
    for m in PINTURA + ('carton',):
        sel = r['mat'] == arma.idx(m)
        if not sel.any():
            continue
        q = pl[sel]
        n = sdf.vnoise(q * np.array([1.0, 1.0, 0.35]), 1.6, 9)
        I[sel] += 0.12 * (n - 0.5)
        I[sel] -= 0.2 * (sdf.vnoise(q * np.array([0.6, 0.6, 0.2]), 0.9, 12) > 0.62)   # roña
        cerca_aro = np.min(np.abs(q[:, 2][:, None] - np.array(ANILLOS + (LARGO - 2.6,))[None, :]), 1)
        I[sel] -= 0.16 * (cerca_aro < 1.7)
    if 'brazo_i' in pose:
        pliegues_pano(arma, r, I, pose['w0_i'], pose['brazo_i'], PLIEGUES)
    filo(arma, r, I)
    costuras(arma, r, I, MANO_I)
    # tollina: la boca está tiznada por el escape de los cohetes
    for m in PINTURA + ('carton', 'laton'):
        sel = r['mat'] == arma.idx(m)
        I[sel] -= 0.5 * np.clip((pl[sel][:, 2] - (LARGO - 13.0)) / 12.0, 0, 1) ** 1.5
    # mecha retorcida (bandas oblicuas) y brasa que brilla (más en la punta)
    sel = r['mat'] == arma.idx('mecha')
    I[sel] += 0.18 * np.sign(np.sin((pl[sel] @ np.array([2.2, 3.1, 2.6]))))
    sel = r['mat'] == arma.idx('brasa')
    dd = np.linalg.norm(pl[sel] - (BRASA + v3(-0.4, 0.1, 0.2)), axis=1)
    I[sel] = 0.45 + 0.7 * np.clip(1.0 - dd / 0.9, 0, 1) + pose.get('aviva', 0.0)


ARMA = Arma(MATS, modelo, BRILLO, GANANCIA, detalle, rampas=RAMPAS_COH)

# ---------------------------------------------------------------------------------------------
# Poses y fotogramas del arma
# ---------------------------------------------------------------------------------------------

LIENZO = (96, 56, 256, 154)      # x0, y0, ancho, alto: hasta x = 352 e y = 210 (balanceo)
CODO_I = v3(-6.0, -38.0, 32.0)   # codo izquierdo en espacio de cámara (cm)
POSE_A = {'recamara': (278.0, 178.0, 30.0), 'boca': (186.0, 111.0), 'alabeo': 12.0, 'cohete': True}
HOMBRO = v3(0.0, -2.0, -22.0)    # pivote del retroceso (espacio del arma)


def pose_de(base, **cambios):
    p = dict(base)
    p.update(cambios)
    return p


POSES = {
    'MISGA0': POSE_A,
    # disparo: sin cohete, el tubo retrocede hacia el hombro y la boca da un cabezazo hacia arriba
    'MISGB0': pose_de(POSE_A, cohete=False, giro=(-4.5, 0.4, -2.0), empuje=(0.3, -1.0, -3.5), aviva=0.4),
}


def preparar(pose):
    """Pose → (R, T) y la dirección del antebrazo izquierdo en espacio del arma."""
    p = dict(pose)
    R, T = matriz_canon(p['recamara'], p['boca'], LARGO, p['alabeo'])
    if 'giro' in p:      # cabeceo, guiñada y alabeo extra (grados) alrededor del hombro
        gx, gy, gz = (math.radians(a) for a in p['giro'])
        Rr = rot_y(gy) @ rot_x(gx) @ rot_z(gz)
        R, T = mover_pose(R, T, Rr, HOMBRO, p.get('empuje', (0, 0, 0)))
    p['R'], p['T'] = R, T
    _, w0 = mano_agarre(np.zeros((1, 3)), MANO_I, v3(0, 0, -1))
    codo = R.T @ (CODO_I - T)
    p['brazo_i'] = unit(codo - w0)
    p['w0_i'] = w0
    return p


def render_fotograma(nombre, S=4):
    pose = preparar(POSES[nombre])
    img = dibujar(ARMA, pose, pose['R'], pose['T'], LIENZO, S, previo=True, t0=8.0, tmax=170.0, pasos=240)
    if nombre == 'MISGB0':
        x0, y0 = LIENZO[:2]
        bx, by = proyectar(v3(0.0, 0.0, LARGO + 3.0), pose['R'], pose['T'])
        bocanada(img, bx - x0, by - y0 - 3, [(0, 0, 4.2), (-4, -3, 3.4), (4, -4, 3.2), (0, -7, 3.0), (-3, -10, 2.2)],
                 semilla=21, nivel_max=6)
        ox, oy = proyectar(MECHA[0] + v3(0, 1.0, 0), pose['R'], pose['T'])
        bocanada(img, ox - x0, oy - y0 - 3, [(0, 0, 2.0), (1, -3, 1.6), (-1, -5, 1.3)], semilla=23, nivel_max=5)
    return img


def boca_disparo():
    """Dónde se ve la boca del tubo en el fotograma de disparo (centro de los fogonazos)."""
    pose = preparar(POSES['MISGB0'])
    return proyectar(v3(0.0, 0.0, LARGO + 1.5), pose['R'], pose['T'])


# ---------------------------------------------------------------------------------------------
# Efectos 2D a pleno brillo: fuego, chispas de colores y humo (deterministas)
# ---------------------------------------------------------------------------------------------

SS2 = 4                                                  # submuestras por píxel y eje
COL_FUEGO = np.array(FUEGO, np.uint8)                    # blanco → amarillo → naranja → rojo oscuro
# chispas: de la cabeza (clara) a la cola (oscura), colores exactos de PLAYPAL
CHISPAS = {
    'oro': _pp(225, 229, 249, 248, 215, 220, 234),
    'rojo': _pp(170, 173, 176, 179, 182, 186),
    'verde': _pp(112, 113, 115, 117, 120, 123),
    'azul': _pp(192, 194, 196, 198, 201, 204),
    'blanco': _pp(4, 81, 86, 92, 98, 104),
}
HUMO = _pp(110, 109, 107, 105, 103, 101, 99)             # humo gris (de la sombra a la luz)
HUMO_CALIDO = _pp(239, 238, 237, 236, 141)               # humo con el resplandor del fuego debajo


def fbm2(x, y, escala, semilla):
    P = np.column_stack([x.ravel(), y.ravel(), np.full(x.size, 0.37 + semilla)])
    n = (sdf.vnoise(P, escala, semilla) * 0.6 + sdf.vnoise(P, escala * 2.1, semilla + 1) * 0.3
         + sdf.vnoise(P, escala * 4.3, semilla + 2) * 0.1)
    return n.reshape(x.shape)


def malla(W, H, cx, cy):
    """Coordenadas de las submuestras (x a la derecha, y hacia ARRIBA) respecto a (cx, cy)."""
    jj, ii = np.meshgrid(np.arange(W * SS2), np.arange(H * SS2))
    return (jj + 0.5) / SS2 - cx, cy - (ii + 0.5) / SS2


def reducir2(campo, umbral, W, H, minimo=6):
    """Submuestras → píxel: cobertura (cuántas pasan el umbral) y media del campo donde pasa."""
    on = campo > umbral
    cnt = on.reshape(H, SS2, W, SS2).sum(axis=(1, 3))
    suma = np.where(on, campo, 0).reshape(H, SS2, W, SS2).sum(axis=(1, 3))
    return cnt >= minimo, suma / np.maximum(cnt, 1)


def pintar_fuego(img, calor, W, H):
    """Calor (submuestras, 0..1+) → píxeles de la rampa FUEGO (1 = blanco, 0 = rojo oscuro)."""
    vis, hm = reducir2(calor, 0.04, W, H)
    n = len(COL_FUEGO)
    idx = np.clip(((1.0 - np.clip(hm, 0, 1)) ** 1.15) * (n - 1) + 0.3, 0, n - 1).astype(int)
    img[vis, :3] = COL_FUEGO[idx[vis]]
    img[vis, 3] = 255
    return vis


def pintar_humo(img, densidad, luz, W, H, calido=None):
    """Humo donde aún no hay nada: densidad (submuestras) y luz (0..1, por submuestra)."""
    vis, _ = reducir2(densidad, 0.5, W, H)
    lm = luz.reshape(H, SS2, W, SS2).mean(axis=(1, 3))
    vis &= img[..., 3] == 0
    ramp = np.array(HUMO, np.uint8)
    idx = np.clip(np.round(lm * (len(ramp) - 1)), 0, len(ramp) - 1).astype(int)
    img[vis, :3] = ramp[idx[vis]]
    if calido is not None:
        cm = calido.reshape(H, SS2, W, SS2).mean(axis=(1, 3))
        rc = np.array(HUMO_CALIDO, np.uint8)
        sel = vis & (cm > 0.5)
        img[sel, :3] = rc[np.clip(idx[sel] * len(rc) // len(ramp), 0, len(rc) - 1)]
    img[vis, 3] = 255


def chispa(img, x, y, dx, dy, largo, rampa, nivel=0, encima=True):
    """Una chispa con estela: cabeza en (x, y) (píxeles, y hacia abajo), estela hacia (-dx, -dy)
    de 'largo' píxeles, del color claro de la rampa al oscuro. nivel: empieza más oscura."""
    H, W = img.shape[:2]
    col = CHISPAS[rampa]
    n = max(int(round(largo)), 1)
    L = math.hypot(dx, dy) or 1.0
    ux, uy = dx / L, dy / L
    vistos = set()
    for k in range(n + 1):
        px, py = int(math.floor(x - ux * k)), int(math.floor(y - uy * k))
        if (px, py) in vistos or not (0 <= px < W and 0 <= py < H):
            continue
        vistos.add((px, py))
        c = min(nivel + (k * (len(col) - 1)) // max(n, 1), len(col) - 1)
        if img[py, px, 3] and not encima:
            continue
        img[py, px, :3] = col[c]
        img[py, px, 3] = 255


def lluvia_chispas(img, cx, cy, n, r0, r1, largo, semilla, colores, nivel=0, caida=0.0, aplasta=1.0,
                   dir_=None, abre=math.pi, encima=True):
    """n chispas alrededor de (cx, cy) (píxeles, y hacia abajo), entre los radios r0 y r1, con estela
    radial de 'largo' (min, max). caida: cuánto se doblan hacia abajo (gravedad). dir_: ángulo central
    (radianes, pantalla) y abre: medio ángulo del abanico (por defecto, todo alrededor)."""
    rng = np.random.default_rng(semilla)
    for _ in range(n):
        a = rng.uniform(-abre, abre) + (dir_ if dir_ is not None else 0.0)
        r = rng.uniform(r0, r1)
        hx, hy = cx + math.cos(a) * r, cy + math.sin(a) * r * aplasta
        dx, dy = math.cos(a), math.sin(a) * aplasta + caida * r / max(r1, 1)
        chispa(img, hx, hy, dx, dy, rng.uniform(*largo), colores[rng.integers(len(colores))],
               nivel + int(rng.integers(0, 2)), encima)


def anclas(img):
    """Píxeles invisibles en las esquinas de abajo: construir_pwad no recorta (ni mueve) el lienzo."""
    H, W = img.shape[:2]
    for x in (0, W - 1):
        if img[H - 1, x, 3] == 0:
            img[H - 1, x] = (0, 0, 0, 1)
    return img


# ---------------------------------------------------------------------------------------------
# MISF: fogonazo de la salida del cohete (sobre la boca del fotograma de disparo)
# ---------------------------------------------------------------------------------------------

def fogonazo_cohete(fr):
    """→ (img, x0, y0): lienzo de pantalla completa con la boca del tubo (fotograma B) dentro.
    Es la salida del cohete: un estallido en la boca (A blanco, B naranja que se abre, C lenguas
    rojas que se apagan) y un chorro de chispas de pólvora que sale disparado hacia el centro de la
    pantalla (por donde se va el cohete) y en corona, y luego cae; las mismas chispas en los cuatro
    fotogramas, cada vez más lejos, más caídas y más apagadas (D: las últimas pavesas)."""
    bx, by = boca_disparo()
    W, H = 88, 74
    x0, y0 = int(round(bx - W * 0.6)), int(round(by - H * 0.42))
    cx, cy = bx - x0, by - y0                       # boca en el lienzo (y hacia abajo)
    fx, fy = 160.0 - bx, 100.0 - by                 # hacia el punto de fuga (por donde va el cohete)
    nf = math.hypot(fx, fy)
    fx, fy = fx / nf, fy / nf
    t = {'A': 1.0, 'B': 2.0, 'C': 3.0, 'D': 4.1}[fr]
    img = np.zeros((H, W, 4), np.uint8)
    # estallido de la boca (un poco adelantado hacia el centro)
    llama = {'A': (7.5, 2.0, 1.3, 0.25), 'B': (11.5, 5.0, 1.05, 0.4), 'C': (9.5, 8.0, 0.6, 0.55)}
    if fr in llama:
        R0, adel, pico, rug = llama[fr]
        ex, ey = cx + fx * adel, cy + fy * adel
        x, y = malla(W, H, ex, ey)                  # y hacia arriba
        r = np.hypot(x, y * 1.1)
        th = np.arctan2(y, x)
        sem = {'A': 41, 'B': 42, 'C': 43}[fr]
        lob = fbm2(np.cos(th) * 2.5, np.sin(th) * 2.5, 1.0, sem)
        R = R0 * (0.68 + 0.6 * lob)
        calor = pico - r / R + rug * (fbm2(x, y, 0.35, sem + 5) - 0.5)
        if fr == 'C':
            calor -= 0.55 * (fbm2(x, y, 0.3, sem + 7) > 0.55)
        pintar_fuego(img, calor, W, H)
    # chispas (en 3D, espacio de cámara, cm): las mismas en todos los fotogramas (misma semilla),
    # cada una con su retraso; las que van hacia delante se alejan hacia el punto de fuga y las de
    # la corona se abren alrededor de la boca y caen
    pose = preparar(POSES['MISGB0'])
    R, T = pose['R'], pose['T']
    boca = R @ v3(0.0, 0.0, LARGO + 1.5) + T
    eje = R @ v3(0.0, 0.0, 1.0)
    lado = unit(np.cross(eje, v3(0.0, 1.0, 0.0)))
    arriba = np.cross(lado, eje)

    def pant(q):
        return 160 + 170.0 * q[0] / q[2] - x0, 100 - 170.0 / 1.2 * q[1] / q[2] - y0

    rng = np.random.default_rng(77)
    gr = v3(0.0, -2.0, 0.0)                         # gravedad (cm por t²)
    for i in range(54):
        delante = i < 34
        if delante:
            vel = eje * rng.uniform(22.0, 60.0) + lado * rng.normal(0, 7.0) + arriba * rng.normal(0, 7.0)
            col = ['oro', 'oro', 'oro', 'blanco'][rng.integers(4)]
        else:
            u = unit(rng.normal(0, 1, 3))
            vel = u * rng.uniform(7.0, 14.0) + eje * 4.0
            col = ['oro', 'rojo', 'verde', 'azul', 'oro'][rng.integers(5)]
        retraso = rng.uniform(0.0, 0.7)
        tt = t - retraso
        if tt <= 0.15:
            continue
        q1 = boca + vel * tt + gr * tt * tt
        q0 = boca + vel * max(tt - 0.35, 0.0) + gr * max(tt - 0.35, 0.0) ** 2
        (ax, ay), (bx_, by_) = pant(q1), pant(q0)
        largo = min(max(math.hypot(ax - bx_, ay - by_), 1.0), 6.0)
        nivel = int(max(0.0, tt - 1.4) * 1.6)
        if nivel >= len(CHISPAS[col]) - 1:
            continue
        chispa(img, ax, ay, ax - bx_, ay - by_, largo, col, nivel, encima=False)
    return img, x0, y0


# ---------------------------------------------------------------------------------------------
# MISL A: el cohete en vuelo (sdf.py, 8 ángulos, a pleno brillo)
# ---------------------------------------------------------------------------------------------

(PAPEL_R, PAPEL_Y, PAPEL_G, CANA, BARRO, LLAMA, CUERDA) = range(7)
RAMPAS_COHETE = {
    PAPEL_R: [190, 187, 184, 181, 178, 174],          # papel rojo
    PAPEL_Y: [166, 165, 164, 163, 162, 161],          # papel amarillo
    PAPEL_G: [126, 124, 122, 120, 118, 116],          # papel verde
    CANA: [238, 149, 147, 145, 144, 131],             # varilla de caña
    BARRO: [8, 6, 109, 106, 103],                     # tapón de barro de la tobera
    LLAMA: [235, 221, 215, 248, 229, 225],            # llama de la tobera (por distancia, de fuera a dentro)
    CUERDA: [239, 237, 141, 139],                     # atadura de la varilla
}
Z_NARIZ, Z_CUERPO, Z_COLA, Z_VARILLA = 10.5, 5.5, -5.5, -13.5   # (px a lo largo del cohete)
R_COHETE = 2.9
ALTO = 8.0                       # el modelo se sube: sdf.Render solo dibuja por encima de y = -1
TOBERA = sdf.V(0, ALTO, Z_COLA - 0.6)
CENTRO_COHETE = sdf.V(0, ALTO - 0.4, 0.5)              # punto que va en el origen del objeto
_RENDER_COH = None


def render_cohete():
    global _RENDER_COH
    if _RENDER_COH is None:
        _RENDER_COH = sdf.Render(RAMPAS_COHETE, gancho_cohete, level_mats=(LLAMA,), emissive=(LLAMA,))
    return _RENDER_COH


def gancho_cohete(P, mat, inten, nz, nr, spec, lvl_extra, extras):
    # franjas del cuerpo (en z): verde, amarillo, rojo, amarillo
    cuerpo = mat == PAPEL_R
    z = P[:, 2]
    bandas = np.digitize(z, [Z_COLA + 2.6, Z_COLA + 5.4, Z_COLA + 8.6])
    tabla = np.array([PAPEL_G, PAPEL_Y, PAPEL_R, PAPEL_Y])
    ok = cuerpo & (z < Z_CUERPO)
    mat[ok] = tabla[bandas[ok]]
    # la llama: más clara cerca de la tobera
    sel = mat == LLAMA
    d = sdf._len(P[sel] - TOBERA)
    lvl_extra[sel] = np.clip((1.0 - d / 3.6) * 6, 0, 5)
    sdf.apply_shine(mat, inten, spec, ((PAPEL_R, 0.25, 6), (PAPEL_Y, 0.25, 6), (PAPEL_G, 0.25, 6)))


def grupos_cohete():
    V = sdf.V
    A = ALTO
    nariz = sdf.CappedCone(V(0, A, Z_CUERPO - 0.2), V(0, A, Z_NARIZ), R_COHETE + 0.15, 0.35, PAPEL_R)
    cuerpo = sdf.CappedCone(V(0, A, Z_COLA), V(0, A, Z_CUERPO), R_COHETE, R_COHETE, PAPEL_R)
    tapon = sdf.CappedCone(V(0, A, Z_COLA - 0.8), V(0, A, Z_COLA + 0.2), R_COHETE - 0.6, R_COHETE - 0.3, BARRO)
    yv = A - R_COHETE - 0.55
    varilla = sdf.RoundCone(V(0, yv, Z_CUERPO - 3.0), V(0, yv - 0.4, Z_VARILLA), 0.8, 0.7, CANA)
    ata1 = sdf.Ring(sdf.Frame((0, A - 0.7, Z_COLA + 1.3), sdf.rot_x(math.pi / 2)), R_COHETE + 0.25, R_COHETE + 1.0, 0.45, CUERDA)
    ata2 = sdf.Ring(sdf.Frame((0, A - 0.7, Z_CUERPO - 1.6), sdf.rot_x(math.pi / 2)), R_COHETE + 0.25, R_COHETE + 1.0, 0.45, CUERDA)
    llama = sdf.RoundCone(V(0, A, Z_COLA - 0.6), V(0, A, Z_COLA - 3.4), 1.7, 0.8, LLAMA)
    return [sdf.Group([nariz, cuerpo, tapon]), sdf.Group([varilla, ata1, ata2]), sdf.Group([llama])]


def marco_render(grupos, angulo, tilt=sdf.TILT):
    """La misma cámara que sdf.Render.render: → (R, Uc, Dc, hw, top) para proyectar puntos."""
    th = (angulo - 1) * math.pi / 4 if angulo else 0.0
    R = sdf.rot_y(-th)
    Uc = sdf.V(0, math.cos(tilt), -math.sin(tilt))
    Dc = sdf.V(0, -math.sin(tilt), -math.cos(tilt))
    xs, ys = [], []
    for g in grupos:
        c, r = g.model_bound()
        cc = R @ c
        xs += [cc[0] - r, cc[0] + r]
        ys += [cc @ Uc - r, cc @ Uc + r]
    hw = int(math.ceil(max(-min(xs), max(xs)))) + 2
    top = int(math.ceil(max(ys))) + 2
    return R, Uc, Dc, hw, top


def a_pixel(p, marco):
    R, Uc, Dc, hw, top = marco
    cc = R @ p
    return cc[0] + hw, top - cc @ Uc, cc @ Dc + 400.0      # (x, y) en el lienzo y profundidad


def cohete(angulo):
    """→ (img RGBA, (izq, sup)): el cohete en vuelo visto desde 'angulo' (1..8) con su chorro de
    chispas doradas (2D, encima o detrás del cuerpo según la profundidad)."""
    R_ = render_cohete()
    grupos = grupos_cohete()
    marco = marco_render(grupos, angulo)
    out, depth = R_.render(grupos, {}, angulo)
    base = np.array(sdf.finish(out, depth, R_.palarr, 2))
    base[base[..., 3] < 128] = 0
    # lienzo más grande para las chispas (margen de M píxeles)
    M = 12
    H0, W0 = base.shape[:2]
    img = np.zeros((H0 + 2 * M, W0 + 2 * M, 4), np.uint8)
    img[M:M + H0, M:M + W0] = base
    prof = np.full(img.shape[:2], np.inf)
    prof[M:M + H0, M:M + W0] = np.where(base[..., 3] > 0, np.minimum(depth, 1e6), np.inf)
    rng = np.random.default_rng(50 + angulo)
    ramp = CHISPAS['oro']
    # dirección del chorro en pantalla (hacia atrás del cohete), para las estelas de las chispas
    x0_, y0_, _ = a_pixel(TOBERA, marco)
    x1_, y1_, _ = a_pixel(TOBERA - sdf.V(0, 0, 6.0), marco)
    ex, ey = (x1_ - x0_) / 6.0, (y1_ - y0_) / 6.0          # px por unidad (0 si se ve de frente)
    for k in range(46):
        u = rng.uniform(0.0, 1.0) ** 1.3                      # 0 = en la tobera, 1 = al final
        L = 2.5 + 11.0 * u
        ab = 0.35 + 2.4 * u                                     # el chorro se abre
        p = TOBERA + sdf.V(rng.normal(0, ab), rng.normal(0, ab) - 0.4 * u, -L)
        x, y, t = a_pixel(p, marco)
        c = min(int(u * (len(ramp) - 1) + rng.integers(0, 2)), len(ramp) - 1)
        largo = 1 if u > 0.45 or rng.uniform() < 0.5 else 2      # las de cerca, con estela
        for j in range(largo):
            px, py = int(math.floor(x + ex * j * 1.4)) + M, int(math.floor(y + ey * j * 1.4)) + M
            if not (0 <= px < img.shape[1] and 0 <= py < img.shape[0]):
                continue
            if t > prof[py, px] - 0.5:
                continue                                        # tapada por el cohete
            img[py, px, :3] = ramp[min(c + j, len(ramp) - 1)]
            img[py, px, 3] = 255
    # recorte y desplazamientos: el centro del cohete en el origen, 4-5 px por encima del suelo
    ys, xs = np.nonzero(img[..., 3] > 0)
    cx, cy, _ = a_pixel(CENTRO_COHETE, marco)
    cx, cy = cx + M, cy + M
    # recorte simétrico en x respecto al centro (el origen cae en medio del cohete)
    mitad = int(math.ceil(max(cx - xs.min(), xs.max() + 1 - cx)))
    xa = int(math.floor(cx)) - mitad
    img = img[ys.min():ys.max() + 1, max(xa, 0):int(math.floor(cx)) + mitad + 1]
    izq = int(math.floor(cx)) - max(xa, 0)
    sup = int(round(cy - ys.min() + 4.5))
    return anclas(img), (izq, sup)


# ---------------------------------------------------------------------------------------------
# MISL B-D: explosión de traca (2D, a pleno brillo, centrada como la de Freedoom)
# ---------------------------------------------------------------------------------------------

LIENZO_EXPLOSION = {'B': (74, 62, 13), 'C': (80, 66, 14), 'D': (90, 72, 13)}   # ancho, alto, centro sobre el origen


def explosion(fr):
    W, H, alto = LIENZO_EXPLOSION[fr]
    cx, cy = W / 2, H / 2
    img = np.zeros((H, W, 4), np.uint8)
    x, y = malla(W, H, cx, cy)
    r = np.hypot(x, y * 1.08)
    th = np.arctan2(y, x)
    semilla = {'B': 61, 'C': 62, 'D': 63}[fr]
    lob = fbm2(np.cos(th) * 3.0, np.sin(th) * 3.0, 1.0, semilla)
    ruido = fbm2(x, y, 0.22, semilla + 3)
    if fr == 'B':
        # bola de fuego grumosa: centro blanco, cuerpo naranja, borde rojo en lenguas
        R = 21.0 * (0.66 + 0.6 * lob)
        calor = 1.18 - r / R + 0.45 * (ruido - 0.5)
        pintar_fuego(img, calor, W, H)
        # humo que empieza a salir por arriba
        dens = (fbm2(x, y, 0.16, semilla + 8) > 0.45) & (y > 6) & (r < R + 7)
        pintar_humo(img, dens.astype(float), np.clip(0.3 + y / 40.0, 0, 1), W, H, calido=(y < 16).astype(float))
        lluvia_chispas(img, cx, cy, 30, 20, 34, (3, 7), semilla, ['oro', 'rojo', 'verde', 'azul', 'blanco', 'oro'],
                       caida=0.8, aplasta=0.92, encima=False)
    elif fr == 'C':
        # la bola se rompe en grumos de fuego que se enfrían (más rojos), con humo entre ellos;
        # las chispas de colores, más lejos y cayendo
        R = 27.0 * (0.72 + 0.5 * lob)
        base = np.clip(1.0 - r / R, 0, 1)
        n = fbm2(x, y, 0.15, semilla + 4)
        calor = base * 2.1 * (n - 0.33) + 0.3 * np.clip(1 - r / 9.0, 0, 1)
        calor += 0.25 * (fbm2(x, y, 0.4, semilla + 9) - 0.5) * (base > 0.12)
        calor = np.where(base > 0.02, calor, -1.0)
        pintar_fuego(img, calor, W, H)
        dens = ((base > 0.05) & (fbm2(x, y, 0.1, semilla + 8) > 0.42)).astype(float)
        luz = np.clip(0.3 + (y + 10) / 50.0 + 0.3 * (fbm2(x, y, 0.3, semilla + 2) - 0.5), 0, 1)
        pintar_humo(img, dens, luz, W, H, calido=(base > 0.45).astype(float))
        lluvia_chispas(img, cx, cy, 30, 27, 40, (4, 9), semilla, ['oro', 'rojo', 'verde', 'azul', 'oro', 'blanco'],
                       caida=2.0, aplasta=0.9, nivel=1, encima=False)
    else:
        # nube de humo que se deshace, con pavesas rojas dentro; las últimas chispas cayendo
        R = 33.0 * (0.75 + 0.45 * lob)
        base = np.clip(1.0 - r / R, 0, 1)
        dens = ((fbm2(x, y, 0.085, semilla) + 0.45 * base) > 0.72).astype(float)
        luz = np.clip(0.15 + (y + 14) / 60.0 + 0.35 * (fbm2(x, y, 0.25, semilla + 2) - 0.5), 0, 1)
        brasas = 0.2 * dens * (fbm2(x, y, 0.45, semilla + 6) > 0.72) * (base > 0.25)
        pintar_fuego(img, brasas, W, H)
        pintar_humo(img, dens, luz, W, H)
        lluvia_chispas(img, cx, cy, 20, 32, 45, (2, 6), semilla, ['oro', 'rojo', 'verde', 'oro'],
                       caida=3.0, aplasta=0.88, nivel=2, encima=False)
    return anclas(img), (int(round(cx)), int(round(cy + alto)))


# ---------------------------------------------------------------------------------------------
# LAUN: el lanzacohetes en el suelo (vista de lado, cámara lejana)
# ---------------------------------------------------------------------------------------------

def recoger(salida):
    """LAUNA0: tumbado en el suelo con el asa hacia quien lo mira, visto de lado y un poco desde
    arriba; grosor exagerado como los objetos de Doom. → offsets (centro, apoyo)."""
    pose = {'manos': False, 'cohete': True, 'gastado': False, 'mecha': False}
    Rl = np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]], float)       # boca a la izquierda
    R = rot_x(math.radians(-30)) @ Rl @ rot_z(math.radians(-31))
    dist = 285.0
    c = v3(0.0, -1.5, (Z0 + LARGO) / 2 + 3.0)
    T = v3(0.0, 0.0, dist) - R @ c
    k = np.array([1 / 1.9, 1 / 1.9, 1.0])
    claro = dict(GANANCIA, rojo=0.95, amarillo=0.95, verde=0.95, laton=1.0, nogal=1.0)
    gordo = Arma(MATS, lambda P, pz: modelo(P * k, pz), BRILLO, claro, detalle, rampas=RAMPAS_COH)
    img = dibujar(gordo, pose, R, T, (120, 75, 80, 50), 4, bordes=False, t0=dist - 90, tmax=dist + 90, pasos=300)
    a = img[..., 3] > 0
    ys, xs = np.nonzero(a)
    img = img[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    Image.fromarray(img, 'RGBA').save(os.path.join(salida, 'LAUNA0.png'))
    h, w = img.shape[:2]
    return [w // 2, h]


def hoja(carpeta, ruta):
    """Hoja de contactos ampliada: el cohete en 8 ángulos, la explosión, los fogonazos y LAUN
    (la raya roja marca el origen del objeto)."""
    off = {}
    off.update(leer_mios(carpeta))
    filas = [[f'MISLA{a}' for a in range(1, 9)], ['MISLB0', 'MISLC0', 'MISLD0', 'LAUNA0'],
             ['MISFA0', 'MISFB0', 'MISFC0', 'MISFD0']]
    ims = {n: Image.open(os.path.join(carpeta, n + '.png')).convert('RGBA') for f in filas for n in f
           if os.path.exists(os.path.join(carpeta, n + '.png'))}
    escalas = [7, 4, 4]
    anchos = [max(ims[n].width for n in f if n in ims) * e + 16 for f, e in zip(filas, escalas)]
    altos = [max(ims[n].height for n in f if n in ims) * e + 40 for f, e in zip(filas, escalas)]
    S = Image.new('RGBA', (max(a * len(f) for a, f in zip(anchos, filas)), sum(altos)), (70, 70, 78, 255))
    d = ImageDraw.Draw(S)
    y = 0
    for f, hf, cw, escala in zip(filas, altos, anchos, escalas):
        for c, n in enumerate(f):
            if n not in ims:
                continue
            im = ims[n]
            big = im.resize((im.width * escala, im.height * escala), Image.NEAREST)
            x = c * cw + 8
            S.alpha_composite(big, (x, y + 20))
            d.text((x, y + 4), f'{n} {im.width}x{im.height} {off.get(n)}', fill=(240, 240, 240))
            if n in off and off[n][0] >= 0:
                ox, oy = x + off[n][0] * escala, y + 20 + off[n][1] * escala
                d.line([(ox - 6, oy), (ox + 6, oy)], fill=(255, 40, 40))
                d.line([(ox, oy - 6), (ox, oy + 6)], fill=(255, 40, 40))
        y += hf
    S.save(ruta)


# ---------------------------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------------------------


def leer_mios(carpeta):
    ruta = os.path.join(carpeta, 'offsets_cohetes.json')
    if os.path.exists(ruta):
        with open(ruta) as fh:
            return json.load(fh)
    return {}


def vista(carpeta, salida):
    from arma1p import simular_pantalla
    estados = [['MISGA0'], ['MISGB0'], ['MISGB0', 'MISFA0'], ['MISGB0', 'MISFB0'], ['MISGB0', 'MISFC0'],
               ['MISGB0', 'MISFD0']]
    W = Image.new('RGBA', (330 * len(estados), 210 * 2 + 20), (20, 20, 20, 255))
    for c, capas in enumerate(estados):
        for r, barra in enumerate((True, False)):
            W.paste(simular_pantalla(carpeta, capas, barra), (330 * c, 210 * r + 20))
        ImageDraw.Draw(W).text((330 * c + 4, 4), '+'.join(capas), fill=(230, 230, 230, 255))
    W = W.resize((W.width * 2, int(W.height * 1.2) * 2), Image.NEAREST)
    W.save(salida)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--salida', required=True, help='carpeta de PNG (arte/sprites)')
    ap.add_argument('--muestreo', type=int, default=4, help='rayos por lado de píxel del arma (4 = 16)')
    ap.add_argument('--solo', default=None, help='solo estos lumps (separados por comas)')
    ap.add_argument('--vista', default=None, help='PNG con las pantallas simuladas del arma')
    ap.add_argument('--hoja', default=None, help='PNG con la hoja de contactos del cohete')
    args = ap.parse_args()
    os.makedirs(args.salida, exist_ok=True)
    solo = [s.strip().upper() for s in args.solo.split(',')] if args.solo else None
    x0, y0, _, _ = LIENZO
    offsets = leer_mios(args.salida)
    for nombre in POSES:
        if solo and nombre not in solo:
            continue
        img = render_fotograma(nombre, args.muestreo)
        offsets[nombre], g = guardar(img, x0, y0, os.path.join(args.salida, nombre + '.png'))
        print(f'{nombre}: {g[2]}x{g[3]} en pantalla ({g[0]}, {g[1]}) offsets {offsets[nombre]}', flush=True)
    for fr in 'ABCD':
        nombre = f'MISF{fr}0'
        if solo and nombre not in solo:
            continue
        img, fx, fy = fogonazo_cohete(fr)
        offsets[nombre], g = guardar(img, fx, fy, os.path.join(args.salida, nombre + '.png'))
        print(f'{nombre}: {g[2]}x{g[3]} en pantalla ({g[0]}, {g[1]}) offsets {offsets[nombre]}', flush=True)
    for a in range(1, 9):
        nombre = f'MISLA{a}'
        if solo and nombre not in solo:
            continue
        img, offsets[nombre] = cohete(a)
        Image.fromarray(img, 'RGBA').save(os.path.join(args.salida, nombre + '.png'))
        print(f'{nombre}: {img.shape[1]}x{img.shape[0]} offsets {offsets[nombre]}', flush=True)
    for fr in 'BCD':
        nombre = f'MISL{fr}0'
        if solo and nombre not in solo:
            continue
        img, offsets[nombre] = explosion(fr)
        Image.fromarray(img, 'RGBA').save(os.path.join(args.salida, nombre + '.png'))
        print(f'{nombre}: {img.shape[1]}x{img.shape[0]} offsets {offsets[nombre]}', flush=True)
    if not solo or 'LAUNA0' in solo:
        offsets['LAUNA0'] = recoger(args.salida)
        print(f'LAUNA0: offsets {offsets["LAUNA0"]}', flush=True)
    guardar_offsets(args.salida, offsets, 'cohetes')
    if args.vista:
        vista(args.salida, args.vista)
    if args.hoja:
        hoja(args.salida, args.hoja)


if __name__ == '__main__':
    main()
