#!/usr/bin/env python3
"""escopeta.py — LA ESCOPETA DE CAZA (sustituye a la escopeta de Freedoom), dibujada por código.

Uso:
    ~/.venvs/pesadilla/bin/python tools/arte/escopeta.py --salida arte/sprites
    (opcional: --vista <png> guarda además las pantallas simuladas de cada estado)

Escribe SHTGA0 (reposo, también al disparar), SHTGB0-D0 (recarga), SHTFA0-B0 (fogonazo doble, a
pleno brillo) y SHOTA0 (la escopeta tirada en el suelo para recogerla), y añade sus
desplazamientos a <salida>/offsets.json (conserva las claves de otros lumps).

En el juego (info.c) los estados van: A reposo; al disparar A (con SHTFA0 y luego SHTFB0 encima),
y la recarga B, C, D, C, B, A. Aquí la recarga es la de una escopeta de dos cañones de perrillos:
B = tras el retroceso baja un poco, perrillos caídos, el pulgar empuja la llave y los cañones
empiezan a bascular; C = quebrada: el arma se baja y gira, los cañones caen hacia abajo a la
izquierda y se ven las recámaras con los culotes de latón (vale igual a la ida, vainas vacías, que
a la vuelta, cartuchos nuevos); D = abierta del todo, la mano derecha deja la culata y mete los dos
cartuchos rojos.

Modelo SDF en centímetros con el motor común arma1p.py (misma proyección, luz, paleta y contorno
que el pistolón): dos cañones de hierro pavonado (grises muy oscuros con un brillo fino) con banda
y punto de mira de latón; báscula pequeña, lisa y oscura con perrillos y llave; guardamanos «de
cola de castor» y culata de nogal (se ven el guardamanos delante de la mano izquierda y la
garganta abajo a la derecha); y las manos con el guante del pistolón (la izquierda bajo el
guardamanos, la derecha en la garganta de la culata o, en D, el puño con los cartuchos) y mangas
de paño granate oscuro con pliegues.
"""
import argparse
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from arma1p import (MUNECA_PUNO, RAMPAS, Agarre, Arma, caja, capsula, detalle_puno,  # noqa: E402
                    dibujar, elipsoide, filo, girar, guante, guardar, guardar_offsets, llamarada,
                    mano_agarre, marco_mira, matriz_canon, mover_pose, pliegues_pano, proyectar,
                    puno, rot_x, rot_y, rot_z, smin, tubo_z, unit, v3, veta)

MATS = ['pavonado', 'hierro', 'laton', 'nogal', 'cuero', 'ribete', 'manga', 'carton', 'hueco']
# báscula, perrillos y llave: hierro oscuro (5, 111, 109, 107, 104, 102, 99, 96), algo más claro que
# los cañones para que se separen, pero sin platas
BASCULA = [(27, 27, 27), (35, 35, 35), (47, 47, 47), (59, 59, 59), (79, 79, 79), (91, 91, 91),
           (111, 111, 111), (131, 131, 131)]
RAMPAS_ESC = dict(RAMPAS, manga=RAMPAS['pano'], hierro=BASCULA)
BRILLO = {'pavonado': (0.9, 60), 'hierro': (0.45, 30), 'laton': (0.6, 22), 'nogal': (0.15, 12),
          'cuero': (0.12, 10), 'ribete': (0.1, 10), 'manga': (0.0, 1), 'carton': (0.25, 14),
          'hueco': (0.0, 1)}
GANANCIA = {'pavonado': 0.62, 'hierro': 0.6, 'laton': 0.9, 'nogal': 0.86, 'cuero': 1.0, 'ribete': 0.62,
            'manga': 0.8, 'carton': 0.95, 'hueco': 0.5}

# ---------------------------------------------------------------------------------------------
# El modelo (espacio del arma: origen en la cara de la recámara entre los dos cañones,
# z hacia las bocas, y arriba, x a la derecha)
# ---------------------------------------------------------------------------------------------

LARGO = 54.0                     # cañones (cm; algo cortos y gruesos para que se lean)
BX = 1.3                         # medio entre ejes de los cañones
RB0, RBM, RB1 = 1.45, 1.28, 1.15  # radio exterior en la recámara, a 12 cm y en la boca
RALMA = 0.9                      # ánima
BANDA_Y = (1.7, 1.33)            # altura de la banda de tiro en la recámara y en la boca
BISAGRA = v3(0.0, -2.3, 5.6)     # eje de basculación de los cañones
PIV_PERRILLO = v3(2.0, -0.4, -5.0)   # pivote de los perrillos (x = ±2,0)
PIV_LLAVE = v3(0.0, 1.0, -4.6)   # la llave de apertura gira sobre la tabla superior
GUARDAMANOS = (6.8, 29.0)        # z del guardamanos de nogal (de cola de castor: más ancho que los cañones)

# manos (marcos de agarre en espacio del arma)
PLIEGUES = (8.0, 14.0, 21.0)      # surcos del paño de las mangas (cm desde la muñeca)
ESCALA_CARGA = 1.1                # la mano que carga (puño del guante, algo exagerado)
CENTRO_CARGA = v3(0.0, -0.6, 6.0) * ESCALA_CARGA   # centro del puño en espacio de la mano
MANO_D = Agarre(G0=(0.0, -1.3, -11.5), GE=(0.0, -0.171, -0.985), GF=(0.0, -0.985, 0.171), GX=(1, 0, 0), r=1.75)
# mano izquierda bajo el guardamanos (espacio de los cañones): palma abajo del guardamanos, los
# dedos suben por el costado derecho y el pulgar por el izquierdo; índice delante.
# (z del nudillo, radio) por dedo:
DZ_I = -1.6                      # la mano va algo atrás: delante queda a la vista el nogal
DEDOS_I = tuple((z + DZ_I, r) for z, r in ((17.6, 0.98), (15.65, 0.98), (13.8, 0.93), (12.15, 0.82)))
MUNECA_I = v3(-1.3, -5.3, 10.0 + DZ_I)


def mano_guardamanos(P):
    """Mano izquierda enguantada que sujeta el guardamanos desde abajo → (distancia, partes)."""
    dz = DZ_I
    palma = elipsoide(P, (0.2, -4.25, 14.9 + dz), (2.9, 1.2, 4.1))
    talon = elipsoide(P, (-0.7, -4.7, 12.3 + dz), (2.6, 1.45, 2.7))
    mano = smin(palma, talon, 1.0)
    dedos = []
    for z, r in DEDOS_I:
        k = (2.7, -4.3, z)
        m = (4.1, -2.75, z + 0.15)
        t = (3.85, -0.45, z + 0.3)
        f = np.minimum(capsula(P, k, m, r, r * 0.95), capsula(P, m, t, r * 0.95, r * 0.82))
        f = np.minimum(f, elipsoide(P, t, (r * 0.85, r * 0.95, r * 0.85)))
        dedos.append(f)
    df = dedos[0]
    for f in dedos[1:]:
        df = smin(df, f, 0.2)
    mano = smin(mano, df, 0.6)
    pulgar = np.minimum(capsula(P, (-1.9, -4.0, 12.4 + dz), (-3.65, -2.5, 15.6 + dz), 1.15, 0.95),
                        capsula(P, (-3.65, -2.5, 15.6 + dz), (-3.6, -1.1, 18.4 + dz), 0.95, 0.8))
    mano = smin(mano, pulgar, 0.6)
    muneca = capsula(P, (-0.8, -4.8, 11.8 + dz), MUNECA_I, 2.25, 2.3)
    mano = smin(mano, muneca, 1.0)
    return mano, {'dedos': dedos, 'pulgar': pulgar}


def _banda(P, y_alta, y_baja, ancho):
    """Banda (chapa) entre los cañones: y de y_baja a y_alta(z), a lo largo de todo el cañón."""
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    ya = y_alta[0] + (y_alta[1] - y_alta[0]) * np.clip(z / LARGO, 0, 1)
    return np.maximum(np.maximum(np.abs(x) - ancho, y - ya), np.maximum(y_baja - y, np.abs(z - LARGO / 2) - LARGO / 2))


def cartuchos(P, sale, d, x=(-BX, BX), eje_y=0.0):
    """Dos cartuchos (culote de latón con pestaña y tubo de cartón rojo) en los ejes de las recámaras,
    con el culote 'sale' cm fuera de la cara de la recámara."""
    for cx in x:
        z0 = -sale
        culote = np.minimum(tubo_z(P, z0, z0 + 1.0, 0.86, 0.86, cx=cx, cy=eje_y),
                            tubo_z(P, z0, z0 + 0.14, 1.0, 1.0, cx=cx, cy=eje_y))
        carton = tubo_z(P, z0 + 0.9, z0 + 6.6, 0.84, 0.84, cx=cx, cy=eje_y)
        pist = tubo_z(P, z0 - 0.03, z0 + 0.1, 0.22, 0.22, cx=cx, cy=eje_y)   # pistón (cobre oscuro)
        d['laton'] = np.minimum(d['laton'], np.maximum(culote, -pist))
        d['hueco'] = np.minimum(d['hueco'], pist + 0.03)
        d['carton'] = np.minimum(d['carton'], carton)


def canones(P, pose, d):
    """Cañones, bandas, punto de mira, guardamanos y cartuchos (todo lo que bascula)."""
    canon = None
    alma = None
    for sx in (-1, 1):
        c = np.minimum(tubo_z(P, 0.0, 12.0, RB0, RBM, cx=sx * BX), tubo_z(P, 11.5, LARGO, RBM, RB1, cx=sx * BX))
        a = tubo_z(P, -1.0, LARGO + 1.0, RALMA, RALMA, cx=sx * BX)
        canon = c if canon is None else np.minimum(canon, c)
        alma = a if alma is None else np.minimum(alma, a)
    banda = _banda(P, BANDA_Y, 0.2, 0.45)                     # banda de tiro, encima
    banda_inf = _banda(P, (-0.3, -0.3), -1.25, 0.5)               # entre los cañones, debajo
    ganchos = caja(P, (0.0, -1.75, 3.0), (0.75, 0.8, 2.8), 0.25)  # tetones que entran en la báscula
    hierro_c = np.minimum(np.minimum(canon, banda), np.minimum(banda_inf, ganchos))
    hierro_c = np.maximum(hierro_c, -alma)                        # huecos
    d['pavonado'] = np.minimum(d['pavonado'], hierro_c)
    # el interior de las almas (visto por la recámara abierta) es negro: un forro fino
    forro = np.maximum(np.abs(alma) - 0.02, np.maximum(-P[:, 2] - 0.01, P[:, 2] - 12.0))
    d['hueco'] = np.minimum(d['hueco'], np.maximum(forro, canon))
    ya = BANDA_Y[0] + (BANDA_Y[1] - BANDA_Y[0]) * (LARGO - 1.6) / LARGO
    d['laton'] = np.minimum(d['laton'], elipsoide(P, (0.0, ya + 0.22, LARGO - 1.6), (0.33, 0.3, 0.33)))
    # guardamanos de nogal «de cola de castor»: más ancho que los cañones y abrazando su mitad de
    # abajo, para que la madera se vea por los costados (y delante de la mano izquierda)
    z0, z1 = GUARDAMANOS
    gm = caja(P, (0.0, -1.6, (z0 + z1) / 2), (3.2, 1.4, (z1 - z0) / 2), 1.15)
    gm = smin(gm, elipsoide(P, (0.0, -1.9, z1 - 1.2), (2.9, 1.25, 2.0)), 0.6)     # punta redondeada
    d['nogal'] = np.minimum(d['nogal'], gm)
    # cartuchos en las recámaras
    if pose.get('cartuchos', True):
        cartuchos(P, pose.get('cartucho_fuera', 0.0), d)


def accion(P, pose, d):
    """Báscula, perrillos, llave, guardamonte y culata (lo que no bascula). Báscula pequeña y lisa
    (sin grabado ni remaches) para que mande la silueta de los dos cañones."""
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    mesa = caja(P, (0.0, -2.1, 2.5), (2.55, 0.75, 3.9), 0.5)                # tabla de la báscula
    cuerpo = caja(P, (0.0, -1.05, -3.4), (2.62, 1.85, 3.4), 0.85)            # cara y platinas
    escudos = None
    for sx in (-1, 1):                                                     # «hombros» tras los cañones
        e = np.maximum(elipsoide(P, (sx * BX, 0.0, -0.4), (1.6, 1.55, 1.1)), z - 0.0)
        escudos = e if escudos is None else np.minimum(escudos, e)
    cola = caja(P, (0.0, 0.65, -7.2), (0.6, 0.3, 2.4), 0.22)               # tabla superior
    bascula = smin(smin(mesa, cuerpo, 0.6), np.minimum(escudos, cola), 0.5)
    # guardamonte y gatillos (debajo: casi nunca se ven)
    guard = np.minimum(np.minimum(capsula(P, (0, -2.8, -1.4), (0, -4.0, -3.4), 0.26),
                                  capsula(P, (0, -4.0, -3.4), (0, -3.8, -6.4), 0.26)),
                       capsula(P, (0, -3.8, -6.4), (0, -2.7, -7.8), 0.26))
    gatillos = np.minimum(capsula(P, (0.0, -2.8, -3.0), (0.0, -3.5, -3.5), 0.2),
                          capsula(P, (0.0, -2.8, -4.4), (0.0, -3.4, -5.0), 0.2))
    hierro_a = np.minimum(bascula, np.minimum(guard, gatillos))
    # perrillos, pequeños (pose['perrillos'] en grados: -40 = montados, 0 = caídos sobre las agujas)
    for sx in (-1, 1):
        pv = PIV_PERRILLO * v3(sx, 1, 1)
        Pp = girar(P, pv, rot_x(math.radians(pose.get('perrillos', -40.0))))
        o = pv
        cuello = capsula(Pp, o, o + v3(-sx * 0.3, 1.6, 2.0), 0.45, 0.38)
        cabeza = capsula(Pp, o + v3(-sx * 0.3, 1.6, 2.0), o + v3(-sx * 0.7, 1.5, 3.9), 0.4, 0.32)
        espuela = capsula(Pp, o + v3(-sx * 0.3, 1.6, 2.0), o + v3(-sx * 0.2, 2.3, 1.2), 0.32, 0.26)
        hierro_a = np.minimum(hierro_a, np.minimum(np.minimum(cuello, cabeza), espuela))
    # llave de apertura sobre la tabla superior (pose['llave'] en grados: + = hacia la derecha)
    Pl = girar(P, PIV_LLAVE, rot_y(math.radians(pose.get('llave', 0.0))))
    llave = capsula(Pl, PIV_LLAVE, PIV_LLAVE + v3(0.25, 0.1, -3.0), 0.4, 0.42)
    hierro_a = np.minimum(hierro_a, llave)
    d['hierro'] = np.minimum(d['hierro'], hierro_a)
    # culata: garganta y culata recta (a la inglesa)
    garganta = capsula(P, (0.0, -0.9, -6.2), (0.0, -2.7, -19.0), 1.65, 1.9)
    culata = capsula(P, (0.0, -2.7, -19.0), (0.0, -6.0, -43.0), 1.9, 3.5)
    madera = smin(smin(garganta, culata, 1.0), cuerpo + 0.3, 0.8)
    d['nogal'] = np.minimum(d['nogal'], np.maximum(madera, -(cuerpo - 0.05)))


def mano_carga(P, pose, d):
    """Fotograma D: la mano derecha (puño enguantado, como el del puño) mete los dos cartuchos
    nuevos en las recámaras; espacio de los cañones."""
    R, o = pose['carga_R'], pose['carga_o']             # marco de la mano en espacio de los cañones
    Ph = (P - o) @ R                                    # → espacio de la mano
    mano, w0 = puno(Ph, escala=ESCALA_CARGA)
    dm = {'cuero': mano}
    guante(dm, Ph, w0, pose['carga_brazo'], largo_manga=40.0, escala=ESCALA_CARGA)
    for m in ('cuero', 'ribete', 'manga'):
        d[m] = np.minimum(d[m], dm[m])


def modelo(P, pose):
    d = {m: np.full(len(P), 1e9) for m in MATS}
    # lo que bascula: girado 'abre' grados alrededor de la bisagra (bocas abajo)
    Pc = girar(P, BISAGRA, rot_x(math.radians(pose.get('abre', 0.0))))
    canones(Pc, pose, d)
    accion(P, pose, d)
    if pose.get('manos', True):
        # mano izquierda bajo el guardamanos (bascula con él)
        mi, _ = mano_guardamanos(Pc)
        dm = {'cuero': mi}
        guante(dm, Pc, MUNECA_I, pose['brazo_i'], largo_manga=40.0)
        for m in ('cuero', 'ribete', 'manga'):
            d[m] = np.minimum(d[m], dm[m])
        # mano derecha en la garganta de la culata (en D se va a meter los cartuchos)
        if pose.get('mano_d', True):
            md, w0d = mano_agarre(P, MANO_D, pose['brazo_d'])
            dd = {'cuero': md}
            guante(dd, P, w0d, pose['brazo_d'], largo_manga=40.0)
            for m in ('cuero', 'ribete', 'manga'):
                d[m] = np.minimum(d[m], dd[m])
        if 'carga_R' in pose:
            mano_carga(Pc, pose, d)
    D = np.stack([d[m] for m in MATS], 1)
    return D.min(1), D.argmin(1)


def mangas(arma, r, I, pose):
    """Pliegues del paño de cada manga, a lo largo de su antebrazo (cada sub-píxel de manga va con
    el antebrazo más cercano)."""
    sel = r['mat'] == arma.idx('manga')
    if not sel.any():
        return
    Rx = rot_x(math.radians(pose.get('abre', 0.0)))      # cañones → arma: Rx (p - B) + B
    ejes = [(Rx @ (MUNECA_I - BISAGRA) + BISAGRA, Rx @ pose['brazo_i'])]
    if pose.get('mano_d', True):
        ejes.append((pose['w0_d'], pose['brazo_d']))
    if 'carga_R' in pose:
        M, o = pose['carga_R'], pose['carga_o']
        ejes.append((Rx @ (o + M @ (MUNECA_PUNO * ESCALA_CARGA) - BISAGRA) + BISAGRA,
                     Rx @ (M @ pose['carga_brazo'])))
    q = r['pl'][sel]
    dist = []
    for o, e in ejes:
        t = np.maximum((q - o) @ e, 0.0)
        dist.append(np.linalg.norm(q - o - np.outer(t, e), axis=1))
    k = np.argmin(np.stack(dist, 1), 1)
    for i, (o, e) in enumerate(ejes):
        m = np.zeros(sel.shape, bool)
        m[sel] = k == i
        pliegues_pano(arma, r, I, o, e, PLIEGUES, sel=m)


def detalle(arma, r, I):
    """Veta del nogal, pliegues y filo de las mangas, surcos de la banda y de los dedos."""
    veta(arma, r, I)
    pose = r.get('pose') or {}
    pl = r['pl']
    mangas(arma, r, I, pose)
    filo(arma, r, I)
    # en espacio de los cañones (basculan): surcos de la banda y de los dedos de la mano izquierda
    pc = girar(pl.reshape(-1, 3), BISAGRA, rot_x(math.radians(pose.get('abre', 0.0)))).reshape(pl.shape)
    sel = r['mat'] == arma.idx('pavonado')
    ax = np.abs(pc[..., 0])
    I[sel & (ax > 0.42) & (ax < 0.62) & (pc[..., 1] > 0.6)] -= 0.35       # valle entre banda y cañón
    if sel.any() and 'R' in pose:
        # brillo fino a lo largo de cada cañón, donde la normal mira a la luz (el especular normal no
        # sale: miramos casi a lo largo de los cañones); el centro llega al azul pálido de la rampa
        Rx = rot_x(math.radians(pose.get('abre', 0.0)))
        nb = (r['n'][sel] @ pose['R']) @ Rx                    # normal en espacio de los cañones
        Lb = (arma.luz @ pose['R']) @ Rx
        Lp = Lb * np.array([1.0, 1.0, 0.0])
        Lp /= np.linalg.norm(Lp)
        c = nb @ Lp
        lado = np.abs(nb[:, 2]) < 0.5                          # costados de los tubos, no las bocas
        I[sel] += lado * (0.3 * (c > 0.93) + 0.16 * (c > 0.985))
    sel = (r['mat'] == arma.idx('cuero')) & (pc[..., 2] > 7.0) & (pc[..., 1] < -1.0)
    if sel.any():
        _, pt = mano_guardamanos(pc[sel])
        D = np.sort(np.stack(pt['dedos'], 1), 1)
        surco = (D[:, 1] - D[:, 0] < 0.3) & (D[:, 1] < 0.5)
        surco |= (np.abs(pt['pulgar'] - D[:, 0]) < 0.3) & (np.maximum(pt['pulgar'], D[:, 0]) < 0.5)
        v = I[sel]
        v[surco] -= 0.38
        I[sel] = v
    if 'carga_R' in pose:
        R, o = pose['carga_R'], pose['carga_o']

        def marco(q):
            return (girar(q, BISAGRA, rot_x(math.radians(pose.get('abre', 0.0)))) - o) @ R
        cerca = np.zeros(r['mat'].shape, bool)
        selc = r['mat'] == arma.idx('cuero')
        cerca[selc] = np.linalg.norm(marco(pl[selc]) - CENTRO_CARGA, axis=1) < 7.0 * ESCALA_CARGA
        detalle_puno(arma, r, I, cerca, escala=ESCALA_CARGA, marco=marco)


ARMA = Arma(MATS, modelo, BRILLO, GANANCIA, detalle, rampas=RAMPAS_ESC)

# ---------------------------------------------------------------------------------------------
# Poses y fotogramas
# ---------------------------------------------------------------------------------------------

LIENZO = (40, 50, 312, 160)    # x0, y0, ancho, alto (pantalla completa; hasta x = 352 e y = 210: margen para el balanceo)
CODO_I = v3(-11.0, -44.0, 32.0)  # codos en espacio de cámara (cm)
CODO_D = v3(18.0, -36.0, -2.0)

POSE_A = {'recamara': (238.0, 168.0, 44.0), 'boca': (152.0, 114.0), 'alabeo': 25.0,
          'abre': 0.0, 'perrillos': -40.0, 'llave': 0.0}
PIVOTE = (0.0, -1.5, -14.0)      # los giros de la recarga, alrededor de la mano derecha


def preparar(pose):
    """Pose → (R, T) y direcciones de los antebrazos en espacio del arma."""
    p = dict(pose)
    R, T = matriz_canon(p['recamara'], p['boca'], LARGO, p['alabeo'])
    if 'giro' in p:      # giro extra (cabeceo, guiñada, alabeo en grados) alrededor de 'pivote'
        gx, gy, gz = (math.radians(a) for a in p['giro'])
        Rr = rot_y(gy) @ rot_x(gx) @ rot_z(gz)
        R, T = mover_pose(R, T, Rr, p.get('pivote', PIVOTE), p.get('empuje', (0, 0, 0)))
    p['R'], p['T'] = R, T
    # brazos: de cada muñeca hacia su codo
    Rc = rot_x(math.radians(p.get('abre', 0.0)))
    codo_i = R.T @ (CODO_I - T)                      # espacio del arma
    codo_i_c = (codo_i - BISAGRA) @ Rc + BISAGRA     # espacio de los cañones (bascula)
    p['brazo_i'] = unit(codo_i_c - MUNECA_I)
    codo_d = R.T @ (CODO_D - T)
    _, w0d = mano_agarre(np.zeros((1, 3)), MANO_D, v3(0, 0, -1))
    p['brazo_d'] = unit(codo_d - w0d)
    p['w0_d'] = w0d
    if 'carga' in p:
        # mano que carga: se coloca en espacio de cámara (dorso hacia el jugador, nudillos desde el
        # codo hacia las recámaras) y se pasa al espacio de los cañones
        c = p['carga']
        Rcb = R @ Rc                                  # cañones → cámara
        Tcb = R @ BISAGRA - Rcb @ BISAGRA + T
        C = Rcb @ v3(*c['centro']) + Tcb + v3(*c.get('desp', (0.0, 0.0, 0.0)))   # desp: cm de cámara
        codo = v3(*c['codo'])
        Rh = marco_mira(unit(C - codo), c.get('dorso', (0.0, 1.0, 0.0)), c.get('alabeo', 0.0))
        Th = C - Rh @ CENTRO_CARGA
        p['carga_R'] = Rcb.T @ Rh
        p['carga_o'] = Rcb.T @ (Th - Tcb)
        p['carga_brazo'] = unit(Rh.T @ (codo - Th) - MUNECA_PUNO * ESCALA_CARGA)
    return p


def pose_de(base, **cambios):
    p = dict(base)
    p.update(cambios)
    return p


POSES = {
    'SHTGA0': POSE_A,
    # tras el retroceso: baja un poco, perrillos caídos, el pulgar empuja la llave y empieza a bascular
    'SHTGB0': pose_de(POSE_A, recamara=(234.0, 174.0, 42.0), boca=(146.0, 124.0), alabeo=22.0,
                      perrillos=0.0, llave=30.0, abre=8.0),
    # quebrada: el arma se baja y gira, los cañones caen hacia abajo a la izquierda y se ven las
    # recámaras con los culotes de latón (vale a la ida, vainas vacías, y a la vuelta, cartuchos)
    'SHTGC0': pose_de(POSE_A, recamara=(212.0, 152.0, 44.0), boca=(112.0, 144.0), alabeo=30.0,
                      perrillos=0.0, llave=30.0, abre=28.0),
    # abierta del todo: la mano derecha deja la culata y mete los dos cartuchos rojos
    'SHTGD0': pose_de(POSE_A, recamara=(204.0, 152.0, 42.0), boca=(112.0, 128.0), alabeo=30.0,
                      perrillos=0.0, llave=30.0, abre=45.0, cartucho_fuera=4.5, mano_d=False,
                      carga={'centro': (BX, 0.0, -4.5), 'desp': (6.0, -2.0, 6.0), 'codo': (26.0, -26.0, 20.0),
                             'dorso': (0.0, 0.6, -1.0)}),
}


def render_fotograma(nombre, S=4):
    pose = preparar(POSES[nombre])
    return dibujar(ARMA, pose, pose['R'], pose['T'], LIENZO, S, previo=True, t0=8.0, tmax=150.0, pasos=220)


def fogonazos():
    """SHTFA0 (llamarada doble, blanca y amarilla) y SHTFB0 (más grande, naranja, abriéndose en
    humo), centradas en las dos bocas del fotograma A. → [(lump, img, x0, y0)] en pantalla."""
    pose = preparar(POSE_A)
    bocas = [proyectar((sx * BX, 0.2, LARGO + 1.8), pose['R'], pose['T']) for sx in (-1, 1)]
    cx = sum(b[0] for b in bocas) / 2
    cy = sum(b[1] for b in bocas) / 2
    out = []
    # A: dos núcleos (uno por cañón) que se juntan en una llamarada grande
    w, h = 50, 46
    x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2 - 3))
    focos = [(bx - x0, by - y0 - 1.5, 10.5, 1.0, 0.0 + i) for i, (bx, by) in enumerate(bocas)]
    focos.append((cx - x0, cy - y0 - 6.0, 13.0, 0.95, 2.0))
    img = llamarada(w, h, focos, semilla=11, lenguas=7, chispas=16, potencia=1.0)
    out.append(('SHTFA0', img, x0, y0))
    # B: más grande y más naranja, deshaciéndose (sin humo: el fogonazo se pinta a pleno brillo)
    w, h = 66, 60
    x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2 - 6))
    focos = [(bx - x0, by - y0 - 3.0, 12.0, 1.0, 1.0 + i) for i, (bx, by) in enumerate(bocas)]
    focos.append((cx - x0, cy - y0 - 10.0, 17.0, 0.9, 3.0))
    img = llamarada(w, h, focos, semilla=12, lenguas=9, chispas=28, potencia=0.6)
    out.append(('SHTFB0', img, x0, y0))
    return out


def recoger(salida):
    """SHOTA0: la escopeta tirada en el suelo, vista de lado (cámara lejana, casi ortográfica).
    Escala de los objetos del mundo: 1 unidad de Doom ≈ 2,9 cm → ~38 px de largo."""
    pose = dict(POSE_A, manos=False, perrillos=-36.0)
    # de lado (lado derecho, bocas a la izquierda), un poco desde arriba, tumbada sobre el costado;
    # el grosor se exagera (x1,9) para que se lea a esta escala, como los objetos de Doom
    Rl = np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]], float)
    R = rot_x(math.radians(-32)) @ Rl @ rot_z(math.radians(-8))
    dist = 430.0
    c = v3(0.0, -3.0, 4.0)
    T = v3(0.0, 0.0, dist) - R @ c
    k = np.array([1 / 1.9, 1 / 1.9, 1.0])
    claro = dict(GANANCIA, pavonado=0.95, hierro=0.85, nogal=1.0)   # en el suelo, algo más claro
    rampas = dict(RAMPAS_ESC, pavonado=RAMPAS['hierro'])
    gorda = Arma(MATS, lambda P, pz: modelo(P * k, pz), BRILLO, claro, detalle, rampas=rampas)
    img = dibujar(gorda, pose, R, T, (125, 80, 70, 40), 4, bordes=False, t0=dist - 90, tmax=dist + 90, pasos=300)
    a = img[..., 3] > 0
    ys, xs = np.nonzero(a)
    img = img[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    from PIL import Image
    Image.fromarray(img, 'RGBA').save(os.path.join(salida, 'SHOTA0.png'))
    h, w = img.shape[:2]
    return [w // 2, h]         # centrada y apoyada en el suelo (como la de Freedoom)


def vista(carpeta, salida):
    from PIL import Image, ImageDraw
    from arma1p import simular_pantalla
    estados = [['SHTGA0'], ['SHTGA0', 'SHTFA0'], ['SHTGA0', 'SHTFB0'], ['SHTGB0'], ['SHTGC0'], ['SHTGD0']]
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
    ap.add_argument('--muestreo', type=int, default=4, help='rayos por lado de píxel (4 = 16 por píxel)')
    ap.add_argument('--solo', default=None, help='solo estos lumps (separados por comas)')
    ap.add_argument('--vista', default=None, help='PNG con las pantallas simuladas')
    args = ap.parse_args()
    os.makedirs(args.salida, exist_ok=True)
    solo = [s.strip().upper() for s in args.solo.split(',')] if args.solo else None
    x0, y0, _, _ = LIENZO
    offsets = {}
    for nombre in POSES:
        if solo and nombre not in solo:
            continue
        img = render_fotograma(nombre, args.muestreo)
        offsets[nombre], g = guardar(img, x0, y0, os.path.join(args.salida, nombre + '.png'))
        print(f'{nombre}: {g[2]}x{g[3]} en pantalla ({g[0]}, {g[1]}) offsets {offsets[nombre]}')
    for nombre, img, fx, fy in fogonazos():
        if solo and nombre not in solo:
            continue
        offsets[nombre], g = guardar(img, fx, fy, os.path.join(args.salida, nombre + '.png'))
        print(f'{nombre}: {g[2]}x{g[3]} en pantalla ({g[0]}, {g[1]}) offsets {offsets[nombre]}')
    if not solo or 'SHOTA0' in solo:
        offsets['SHOTA0'] = recoger(args.salida)
        print(f'SHOTA0: offsets {offsets["SHOTA0"]}')
    guardar_offsets(args.salida, offsets)
    if args.vista:
        vista(args.salida, args.vista)


if __name__ == '__main__':
    main()
