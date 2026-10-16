#!/usr/bin/env python3
"""pistolon.py — EL PISTOLÓN DE CHISPA (sustituye a la pistola de Freedoom), dibujado por código.

Uso:
    ~/.venvs/pesadilla/bin/python tools/arte/pistolon.py --salida arte/sprites
    (opcional: --vista <carpeta> guarda además una hoja de contactos y simulaciones de pantalla)

Escribe PISGA0.png (reposo), PISGB0.png (disparo), PISGC0.png (vuelta), PISFA0.png (fogonazo) y
añade sus desplazamientos a <salida>/offsets.json (conserva las claves de otros lumps).

Cómo se dibuja (determinista, sin IA ni azar no sembrado):
- Modelo 3D hecho con primitivas SDF (cápsulas, conos, cajas redondeadas, elipsoides) en
  centímetros: cañón de hierro con boca de latón, caja de nogal con culata curvada, llave de
  chispa (pie de gato, batería, cazoleta) y mano derecha con guante de cuero y manga.
- Se traza con raymarching vectorizado (numpy) desde el ojo del jugador, con la proyección de los
  «psprites» de Doom: pantalla 320x200 cuyos píxeles se ven 1,2 veces más altos que anchos.
- Se renderiza a 4x, se reduce por mayoría de alfa, se sombrea con rampas de la paleta PLAYPAL
  (luz desde arriba-izquierda-delante), se oscurecen los bordes de profundidad y se añade un
  contorno oscuro de 1 px.
- Los tres fotogramas comparten sistema de coordenadas de pantalla: los desplazamientos salen de
  la posición real en pantalla (x_izq = 1 - izq, y_sup = 32 - sup, vista completa 320x200), así
  no hay saltos entre fotogramas y el fogonazo cae en la boca del cañón del fotograma B.
"""
import argparse
import json
import math
import os

import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------------------------
# Paleta: rampas de colores EXACTOS de PLAYPAL (de oscuro a claro)
# ---------------------------------------------------------------------------------------------


def _hx(*cols):
    return [((c >> 16) & 255, (c >> 8) & 255, c & 255) for c in cols]


RAMPAS = {
    # hierro: grises neutros 111..82
    'hierro': _hx(0x1b1b1b, 0x2f2f2f, 0x434343, 0x5b5b5b, 0x777777, 0x979797, 0xbfbfbf, 0xdfdfdf),
    # latón: rampa dorada 167..161
    'laton': _hx(0x372313, 0x732b00, 0x874307, 0x9b5b13, 0xaf7b1f, 0xc39b2f, 0xd7bb43, 0xebdb57),
    # nogal: marrón cálido 239, 237, 74..66
    'nogal': _hx(0x1f170b, 0x2f1b0b, 0x432f1b, 0x5f4323, 0x774f2b, 0x8f5f37, 0xa36b3f, 0xb37347),
    # guante: cuero marrón oscuro, más apagado que la madera
    'cuero': _hx(0x170f07, 0x2b230f, 0x3f2f17, 0x4b371b, 0x574333, 0x67533f, 0x775f4b, 0x8b735b),
    # vuelta del guante (ribete más claro)
    'ribete': _hx(0x2b230f, 0x533f1f, 0x6b4727, 0x7f532f, 0x9b633b, 0xb37347, 0xcf8353, 0xdf9363),
    # manga: paño granate oscuro
    'manga': _hx(0x1f170b, 0x430000, 0x5b0707, 0x6b0f0f, 0x7f1b1b, 0x8f2b2b, 0xa33b3b, 0xb34f4f),
    # pedernal: gris pardo
    'pedernal': _hx(0x232323, 0x372313, 0x4f3b27, 0x5f4b37, 0x775f4b, 0x8b735b, 0x9f876f, 0xb79f87),
    # humo
    'humo': _hx(0x434343, 0x575757, 0x6b6b6b, 0x7f7f7f, 0x979797, 0xababab, 0xc7c7c7, 0xdbdbdb),
}
MATS = ['hierro', 'laton', 'nogal', 'cuero', 'ribete', 'manga', 'pedernal']
CONTORNO = (0x17, 0x0f, 0x07)  # PLAYPAL 2

# Fogonazo (se dibuja a pleno brillo): blanco → amarillo → naranja → rojo oscuro
FUEGO = _hx(0xffffff, 0xffffd7, 0xffff8f, 0xffff47, 0xffe74b, 0xffc79b, 0xffa35b, 0xff8f3b,
            0xff7f1b, 0xeb6f0f, 0xd75f0b, 0xc34f00, 0xa73f00, 0x872300)

# ---------------------------------------------------------------------------------------------
# Primitivas SDF (P: array (N,3) en cm)
# ---------------------------------------------------------------------------------------------


def v3(x, y, z):
    return np.array([x, y, z], dtype=np.float64)


def capsula(P, a, b, ra, rb=None):
    """Cápsula de a a b con radio que pasa de ra a rb (cono redondeado aproximado)."""
    rb = ra if rb is None else rb
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    ba = b - a
    pa = P - a
    t = np.clip(pa @ ba / (ba @ ba), 0.0, 1.0)
    q = pa - t[:, None] * ba
    return np.sqrt((q * q).sum(1)) - (ra + t * (rb - ra))


def elipsoide(P, c, r):
    q = (P - np.asarray(c, float)) / np.asarray(r, float)
    k0 = np.sqrt((q * q).sum(1))
    k1 = np.sqrt(((q / np.asarray(r, float)) ** 2).sum(1))
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-6)


def caja(P, c, h, rr=0.0):
    q = np.abs(P - np.asarray(c, float)) - (np.asarray(h, float) - rr)
    return np.sqrt((np.maximum(q, 0) ** 2).sum(1)) + np.minimum(q.max(1), 0) - rr


def tubo_z(P, z0, z1, r0, r1, octo=False, cx=0.0, cy=0.0):
    """Cilindro (u octógono) a lo largo de z, de z0 a z1, radio de r0 a r1."""
    x = P[:, 0] - cx
    y = P[:, 1] - cy
    z = P[:, 2]
    t = np.clip((z - z0) / (z1 - z0), 0, 1)
    r = r0 + t * (r1 - r0)
    if octo:
        ax, ay = np.abs(x), np.abs(y)
        d2 = np.maximum(np.maximum(ax, ay), (ax + ay) * 0.70710678) - r
    else:
        d2 = np.sqrt(x * x + y * y) - r
    dz = np.abs(z - (z0 + z1) / 2) - (z1 - z0) / 2
    return np.sqrt(np.maximum(d2, 0) ** 2 + np.maximum(dz, 0) ** 2) + np.minimum(np.maximum(d2, dz), 0)


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def rot_x(g):
    c, s = math.cos(g), math.sin(g)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(g):
    c, s = math.cos(g), math.sin(g)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_z(g):
    c, s = math.cos(g), math.sin(g)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def girar(P, pivote, R):
    """Puntos del espacio del arma → espacio de una pieza girada R alrededor de pivote."""
    return (P - pivote) @ R + pivote  # R ortogonal: (R^T (p - c))^T = (p - c)^T R


# ---------------------------------------------------------------------------------------------
# El modelo (espacio del arma: origen en la recámara, z hacia la boca, y arriba, x a la derecha)
# ---------------------------------------------------------------------------------------------

LARGO = 23.0                 # cañón (cm)
PIVOTE_GATO = v3(2.2, -1.0, -4.4)       # eje del pie de gato (en la platina)
PIVOTE_BATERIA = v3(2.2, 0.15, 1.9)     # eje de la batería (delante de la cazoleta)

# Culata: línea central de la empuñadura, que baja hacia atrás desde la garganta
G0 = v3(0.0, -1.5, -7.0)                 # arriba de la empuñadura (donde se apoya la membrana)
GE = v3(0.0, -0.75, -0.66) / np.linalg.norm([0.0, -0.75, -0.66])   # eje de la empuñadura
GF = v3(0.0, -0.66, 0.75) / np.linalg.norm([0.0, -0.66, 0.75])     # «delante» de la empuñadura
GX = v3(1.0, 0.0, 0.0)
ANTEBRAZO = v3(0.5, -0.6, -0.62) / np.linalg.norm([0.5, -0.6, -0.62])


def en_mano(s, x, f):
    """Punto de la mano: s cm bajando por la empuñadura, x a la derecha, f hacia delante."""
    return G0 + s * GE + x * GX + f * GF


def elipsoide_ejes(P, c, ejes, r):
    """Elipsoide con centro c, ejes (3 vectores unitarios) y semiejes r."""
    q = (P - c) @ np.stack(ejes, 1)
    return elipsoide(q, (0, 0, 0), r)


def modelo(P, pose):
    """Devuelve (distancia, material) por punto. material = índice en MATS."""
    d = {}

    # --- hierro: cañón (ochavado atrás, redondo delante), llave, pie de gato, batería ---
    canon = np.minimum(tubo_z(P, -0.4, 8.0, 1.66, 1.52, octo=True),
                       tubo_z(P, 7.5, LARGO - 0.9, 1.47, 1.28))
    anillo = tubo_z(P, 7.6, 8.4, 1.72, 1.72, octo=True)               # moldura
    cola = capsula(P, (0, 1.05, -0.3), (0, 0.4, -6.2), 0.42, 0.3)     # cola de la recámara
    platina = caja(P, (1.78, -1.1, -2.9), (0.26, 1.15, 4.7), 0.4)     # platina de la llave
    hierro = np.minimum(np.minimum(canon, anillo), np.minimum(cola, platina))

    # pie de gato: gira alrededor de su eje; pose['gato'] en grados (0 = montado, + = caído)
    Pg = girar(P, PIVOTE_GATO, rot_x(math.radians(pose['gato'])))
    o = PIVOTE_GATO
    k = 1.2  # tamaño de la llave (exagerado para que se lea)
    cuello = np.minimum(capsula(Pg, o + k * v3(0, -0.2, 0.3), o + k * v3(0, 1.3, -1.25), 0.6, 0.5),
                        capsula(Pg, o + k * v3(0, 1.3, -1.25), o + k * v3(0, 2.75, -0.75), 0.5, 0.45))
    talon = capsula(Pg, o + k * v3(0, -0.2, 0.3), o + k * v3(0, -0.55, 1.3), 0.46, 0.34)
    mandibula = caja(Pg, o + k * v3(0, 2.95, -0.25), (0.46, 0.48, 0.92), 0.16)
    mand_sup = caja(Pg, o + k * v3(0, 3.75, -0.3), (0.42, 0.24, 0.88), 0.14)
    tornillo = np.minimum(capsula(Pg, o + k * v3(0, 3.55, -0.55), o + k * v3(0, 4.65, -0.55), 0.28),
                          capsula(Pg, o + k * v3(-0.32, 4.65, -0.55), o + k * v3(0.32, 4.65, -0.55), 0.24))
    gato = np.minimum(np.minimum(np.minimum(cuello, talon), mandibula), np.minimum(mand_sup, tornillo))
    pedernal = caja(Pg, o + k * v3(0, 3.35, 0.75), (0.42, 0.3, 0.6), 0.08)

    # batería (rastrillo): placa vertical que tapa la cazoleta; pose['bateria'] en grados (- = abierta)
    Pb = girar(P, PIVOTE_BATERIA, rot_x(math.radians(pose['bateria'])))
    ob = PIVOTE_BATERIA
    bateria = np.minimum(caja(Pb, ob + k * v3(0, 1.45, -0.7), (0.5, 1.75, 0.2), 0.1),
                         caja(Pb, ob + k * v3(0, 0.12, -1.0), (0.52, 0.16, 0.84), 0.08))
    muelle = capsula(P, ob + k * v3(0, -0.75, 0.2), ob + k * v3(0, -0.85, 2.4), 0.26, 0.14)
    hierro = np.minimum(np.minimum(hierro, gato), np.minimum(bateria, muelle))
    d['hierro'] = hierro
    d['pedernal'] = pedernal

    # --- latón: boca del cañón (con labio), punto de mira, cazoleta, punta de la caja, pomo ---
    boca = np.minimum(tubo_z(P, LARGO - 1.6, LARGO - 0.3, 1.55, 1.7), tubo_z(P, LARGO - 0.5, LARGO, 1.85, 1.85))
    mira = caja(P, (0, 1.5, LARGO - 2.5), (0.18, 0.4, 0.55), 0.08)
    cazoleta = caja(P, (2.15, -0.05, 0.85), (0.6, 0.26, 0.9), 0.1)
    punta_caja = tubo_z(P, 16.6, 17.5, 1.32, 1.32, cy=-1.4)
    pomo = elipsoide(P, en_mano(10.6, 0, -0.6), (2.0, 1.9, 2.0))
    laton = np.minimum(np.minimum(boca, mira), np.minimum(cazoleta, np.minimum(punta_caja, pomo)))
    d['laton'] = laton

    # --- nogal: caja bajo el cañón, cuerpo de la llave, garganta y culata curvada ---
    caja_del = caja(P, (0, -1.5, 7.6), (1.42, 1.15, 9.4), 0.85)
    cuerpo = caja(P, (0.1, -1.35, -2.9), (1.72, 1.42, 5.0), 0.95)
    culata = np.minimum(capsula(P, (0, -1.0, -6.0), G0 + 0.0 * GE, 1.3, 1.35),
                        capsula(P, G0, en_mano(9.5, 0, -0.4), 1.35, 1.95))
    nogal = smin(np.minimum(caja_del, cuerpo), culata, 0.9)
    d['nogal'] = nogal

    # --- mano derecha con guante: dorso a la derecha, pulgar a la izquierda, dedos por delante ---
    dorso = elipsoide_ejes(P, en_mano(4.3, 1.75, -0.45), (GX, GE, GF), (1.4, 4.1, 2.8))
    palma = elipsoide_ejes(P, en_mano(4.6, 0.3, -1.3), (GX, GE, GF), (1.7, 3.9, 1.9))
    tenar = elipsoide_ejes(P, en_mano(2.4, -1.15, -1.25), (GX, GE, GF), (1.05, 2.1, 1.6))
    membrana = capsula(P, en_mano(0.9, 1.2, -0.5), en_mano(0.9, -0.9, -1.3), 0.95, 0.9)
    pulgar = np.minimum(capsula(P, en_mano(1.6, -1.35, -1.0), (-1.7, -0.75, -5.4), 0.95, 0.82),
                        capsula(P, (-1.7, -0.75, -5.4), (-1.75, -0.3, -3.3), 0.82, 0.72))
    mano = smin(smin(dorso, palma, 1.0), smin(smin(tenar, membrana, 0.8), pulgar, 0.6), 0.8)
    dedos = None
    for i, s in enumerate((0.9, 2.95, 4.9, 6.75)):
        r = 0.9 - 0.05 * i
        delante = 0.7 if i == 0 else 0.0                      # el índice va al gatillo, más adelante
        k = en_mano(s, 1.65, 1.3 + delante)                   # nudillo
        a = en_mano(s, 0.35, 2.35 + delante)                  # delante de la empuñadura
        b = en_mano(s + 0.2, -1.45, 1.35 + delante * 0.5)     # esquina izquierda
        c = en_mano(s + 0.3, -1.85, -0.15)                    # punta, en el lado izquierdo
        f = np.minimum(np.minimum(capsula(P, k, a, r, r * 0.95), capsula(P, a, b, r * 0.95, r * 0.9)),
                       capsula(P, b, c, r * 0.9, r * 0.82))
        dedos = f if dedos is None else np.minimum(dedos, f)
    mano = smin(mano, dedos, 0.45)
    w0 = en_mano(7.0, 0.9, -2.0)
    muneca = capsula(P, w0, w0 + 3.0 * ANTEBRAZO, 2.25, 2.3)
    mano = smin(mano, muneca, 1.2)
    d['cuero'] = mano

    # manopla acampanada del guante (mismo cuero), con un ribete claro en el borde, y manga
    ea, eb = w0 + 1.6 * ANTEBRAZO, w0 + 4.6 * ANTEBRAZO
    vuelta = capsula(P, ea, eb, 2.5, 3.5)
    hueco = capsula(P, eb - 0.1 * (eb - ea), eb + 0.6 * (eb - ea), 3.05)
    vuelta = np.maximum(vuelta, -hueco)
    d['cuero'] = smin(d['cuero'], vuelta, 0.6)
    t = (P - ea) @ ANTEBRAZO
    d['ribete'] = np.maximum(vuelta - 0.06, 3.7 - t)  # el último medio centímetro de la manopla
    d['manga'] = capsula(P, w0 + 4.0 * ANTEBRAZO, w0 + 30 * ANTEBRAZO, 3.0, 4.6)

    D = np.stack([d[m] for m in MATS], 1)
    mat = D.argmin(1)
    return D.min(1), mat


# ---------------------------------------------------------------------------------------------
# Cámara y raymarching
# ---------------------------------------------------------------------------------------------

F = 170.0        # distancia focal en píxeles de pantalla (horizontal)
ASPECTO = 1.2    # los píxeles de Doom se ven 1,2 veces más altos


def pose_a_matriz(pose):
    """Pose → (R, T): p_cámara = R · p_arma + T.

    La pose se da en pantalla: 'recamara' = (x, y, Z) posición en pantalla completa y profundidad
    (cm) de la recámara; 'boca' = (x, y) donde debe verse el centro de la boca del cañón;
    'alabeo' = giro (grados) sobre el eje del cañón (positivo: el costado derecho, el de la llave,
    se inclina hacia arriba).
    """
    bx, by, bz = pose['recamara']
    T = np.array([(bx - 160) * bz / F, -(by - 100) * ASPECTO * bz / F, bz])
    mx, my = pose['boca']
    u = np.array([(mx - 160) / F, -(my - 100) * ASPECTO / F, 1.0])  # rayo hacia la boca
    # |Zm·u - T| = LARGO  →  (u·u) Zm² - 2 (u·T) Zm + T·T - LARGO² = 0 (raíz lejana)
    a, b, c = u @ u, -2 * (u @ T), T @ T - LARGO ** 2
    zm = (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a)
    dz = zm * u - T
    dz /= np.linalg.norm(dz)
    dx = np.cross([0.0, 1.0, 0.0], dz)
    dx /= np.linalg.norm(dx)
    dy = np.cross(dz, dx)
    g = math.radians(pose['alabeo'])
    dx, dy = math.cos(g) * dx + math.sin(g) * dy, -math.sin(g) * dx + math.cos(g) * dy
    R = np.stack([dx, dy, dz], 1)
    # retroceso: el arma gira (boca arriba) alrededor de la muñeca y se desplaza (cm, cámara)
    giro = pose.get('retroceso', 0.0)
    if giro or 'empuje' in pose:
        Rr = rot_x(-math.radians(giro))
        pv = en_mano(4.0, 0.0, -1.0)
        T = R @ pv - R @ Rr @ pv + T + np.asarray(pose.get('empuje', (0, 0, 0)), float)
        R = R @ Rr
    return R, T


def proyectar(p_arma, pose):
    """Punto del espacio del arma → (x, y) en la pantalla completa 320x200."""
    R, T = pose_a_matriz(pose)
    q = R @ np.asarray(p_arma, float) + T
    return 160 + F * q[0] / q[2], 100 - F / ASPECTO * q[1] / q[2]


def trazar(pose, x0, y0, w, h, S):
    """Traza el lienzo [x0, x0+w) x [y0, y0+h) de la pantalla con S x S rayos por píxel."""
    R, T = pose_a_matriz(pose)
    xs = x0 + (np.arange(w * S) + 0.5) / S
    ys = y0 + (np.arange(h * S) + 0.5) / S
    X, Y = np.meshgrid(xs, ys)
    D = np.stack([(X - 160) / F, -(Y - 100) * ASPECTO / F, np.ones_like(X)], -1).reshape(-1, 3)
    D /= np.linalg.norm(D, axis=1, keepdims=True)
    N = D.shape[0]
    t = np.full(N, 15.0)
    hit = np.zeros(N, bool)
    vivos = np.arange(N)
    for _ in range(160):
        if vivos.size == 0:
            break
        p = D[vivos] * t[vivos, None]
        dist, _ = modelo((p - T) @ R, pose)
        t[vivos] += dist * 0.8
        acierto = dist < 0.01
        hit[vivos[acierto]] = True
        vivos = vivos[~acierto & (t[vivos] < 110)]
    idx = np.nonzero(hit)[0]
    P = D[idx] * t[idx, None]
    Pl = (P - T) @ R
    _, mat = modelo(Pl, pose)
    # normal por tetraedro (en espacio del arma) → espacio de cámara
    e = 0.004
    ks = np.array([[1, -1, -1], [-1, -1, 1], [-1, 1, -1], [1, 1, 1]], float)
    n = np.zeros_like(Pl)
    for k in ks:
        n += k * modelo(Pl + e * k, pose)[0][:, None]
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-9
    n = n @ R.T
    # oclusión ambiental barata
    ao = np.ones(len(idx))
    nl = n @ R
    for i, s in enumerate([0.15, 0.35, 0.7, 1.2]):
        dd = modelo(Pl + nl * s, pose)[0]
        ao -= (s - np.clip(dd, 0, s)) / s * (0.5 ** (i + 1)) * 0.9
    out = {
        'hit': hit.reshape(h * S, w * S),
        'mat': np.full(N, -1), 'n': np.zeros((N, 3)), 'z': np.full(N, np.inf), 'ao': np.ones(N),
        'pl': np.zeros((N, 3)), 'dir': D,
    }
    out['mat'][idx] = mat
    out['n'][idx] = n
    out['z'][idx] = P[:, 2]
    out['ao'][idx] = np.clip(ao, 0.2, 1)
    out['pl'][idx] = Pl
    for k in ('mat', 'z', 'ao'):
        out[k] = out[k].reshape(h * S, w * S)
    out['n'] = out['n'].reshape(h * S, w * S, 3)
    out['pl'] = out['pl'].reshape(h * S, w * S, 3)
    out['dir'] = D.reshape(h * S, w * S, 3)
    return out


LUZ = np.array([-0.55, 0.72, -0.42])
LUZ /= np.linalg.norm(LUZ)
BRILLO = {'hierro': (0.55, 30), 'laton': (0.6, 22), 'nogal': (0.15, 12), 'cuero': (0.12, 10),
          'ribete': (0.1, 10), 'manga': (0.0, 1), 'pedernal': (0.3, 20)}


# cuánto de la rampa usa cada material con luz plena (el hierro queda oscuro salvo en los brillos)
GANANCIA = {'hierro': 0.72, 'laton': 0.9, 'nogal': 0.92, 'cuero': 1.0, 'ribete': 0.9, 'manga': 1.0,
            'pedernal': 0.9}


def intensidad(r):
    """Intensidad de luz continua (0..1+) por sub-píxel."""
    n = r['n']
    V = -r['dir']
    lam = np.clip((n * LUZ).sum(-1), 0, 1)
    H = LUZ + V
    H /= np.linalg.norm(H, axis=-1, keepdims=True)
    nh = np.clip((n * H).sum(-1), 0, 1)
    I = 0.2 + 0.8 * lam
    I = I * (0.55 + 0.45 * r['ao'])
    spec = np.zeros_like(I)
    for i, m in enumerate(MATS):
        k, p = BRILLO[m]
        sel = r['mat'] == i
        spec[sel] = k * nh[sel] ** p
    I = I + spec
    # costuras del dorso del guante: tres pespuntes entre los dedos
    pl = r['pl']
    q = pl - G0
    sg, fg, xg = q @ GE, q @ GF, q[..., 0]
    cos = np.zeros(sg.shape, bool)
    for s0 in (1.95, 3.95, 5.85):
        cos |= (np.abs(sg - s0 - 0.25 * fg) < 0.16) & (xg > 1.2) & (fg > -2.6) & (fg < 1.4)
    sel = (r['mat'] == MATS.index('cuero')) & cos
    I[sel] -= 0.3
    # veta del nogal: bandas suaves a lo largo de la madera
    pl = r['pl']
    veta = np.sin(pl[..., 2] * 2.1 + np.sin(pl[..., 1] * 3.3 + pl[..., 0] * 1.7) * 1.6)
    sel = r['mat'] == MATS.index('nogal')
    I[sel] += 0.07 * veta[sel]
    return I


def reducir(r, S):
    """Sub-píxeles → píxeles: alfa por mayoría, material mayoritario, intensidad media."""
    hS, wS = r['hit'].shape
    h, w = hS // S, wS // S
    hit = r['hit'].reshape(h, S, w, S).transpose(0, 2, 1, 3).reshape(h, w, S * S)
    mat = r['mat'].reshape(h, S, w, S).transpose(0, 2, 1, 3).reshape(h, w, S * S)
    I = intensidad(r).reshape(h, S, w, S).transpose(0, 2, 1, 3).reshape(h, w, S * S)
    z = r['z'].reshape(h, S, w, S).transpose(0, 2, 1, 3).reshape(h, w, S * S)
    alfa = hit.mean(-1) >= 0.5
    cuenta = np.stack([(mat == i).sum(-1) for i in range(len(MATS))], -1)
    m = cuenta.argmax(-1)
    sel = mat == m[..., None]
    Im = np.where(sel, I, 0).sum(-1) / np.maximum(sel.sum(-1), 1)
    zm = np.where(sel, z, 0).sum(-1) / np.maximum(sel.sum(-1), 1)
    m = np.where(alfa, m, -1)
    return alfa, m, Im, zm


def desplazar(a, dy, dx, relleno):
    """Como np.roll pero sin dar la vuelta: lo que entra por el borde es 'relleno'."""
    out = np.full_like(a, relleno)
    h, w = a.shape[:2]
    out[max(dy, 0):h + min(dy, 0), max(dx, 0):w + min(dx, 0)] = a[max(-dy, 0):h + min(-dy, 0), max(-dx, 0):w + min(-dx, 0)]
    return out


def colorear(alfa, m, I, z, contorno=True, bordes=True):
    h, w = alfa.shape
    nivel = np.zeros((h, w), int)
    for i, nombre in enumerate(MATS):
        n = len(RAMPAS[nombre])
        sel = m == i
        nivel[sel] = np.clip(np.floor(I[sel] * GANANCIA[nombre] * (n - 1) + 0.35), 1, n - 1)
    if bordes:
        # línea de profundidad: un píxel con un vecino mucho más cercano (o de otra pieza) se oscurece
        zz = np.where(alfa, z, 1e9)
        lejos = np.zeros((h, w), bool)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            vecino = desplazar(zz, dy, dx, 1e9)
            vm = desplazar(m, dy, dx, -1)
            lejos |= alfa & (vecino < zz - 0.9) & (vm >= 0)
            lejos |= alfa & (vm >= 0) & (vm != m) & (vecino < zz - 0.15)
        nivel = np.where(lejos, np.maximum(nivel - 3, 0), nivel)
    img = np.zeros((h, w, 4), np.uint8)
    for i, nombre in enumerate(MATS):
        ramp = np.array(RAMPAS[nombre], np.uint8)
        sel = m == i
        img[sel, :3] = ramp[nivel[sel]]
        img[sel, 3] = 255
    if contorno:
        borde = np.zeros((h, w), bool)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            borde |= desplazar(alfa, dy, dx, False)
        borde &= ~alfa
        borde[-1, :] = False  # el borde inferior sale de la pantalla
        img[borde, :3] = CONTORNO
        img[borde, 3] = 255
    return img


# ---------------------------------------------------------------------------------------------
# Humo y fogonazo (2D, deterministas)
# ---------------------------------------------------------------------------------------------


def bocanada(img, cx, cy, radios, semilla, nivel_max=6):
    """Dibuja una bocanada de humo (círculos sombreados de la rampa 'humo') sobre img (RGBA)."""
    h, w = img.shape[:2]
    rng = np.random.default_rng(semilla)
    ramp = np.array(RAMPAS['humo'], np.uint8)
    mascara = np.zeros((h, w), bool)
    luz = np.zeros((h, w))
    Y, X = np.mgrid[0:h, 0:w]
    for (dx, dy, r) in radios:
        jx, jy = rng.uniform(-0.6, 0.6, 2)
        ex, ey = cx + dx + jx, cy + dy + jy
        dd = np.sqrt((X - ex) ** 2 + ((Y - ey) * 1.0) ** 2)
        dentro = dd <= r
        # luz desde arriba-izquierda dentro de cada bola
        l = 1 - np.clip(np.sqrt((X - ex + r * 0.4) ** 2 + (Y - ey + r * 0.45) ** 2) / (1.6 * r), 0, 1)
        luz = np.where(dentro, np.maximum(luz, l), luz)
        mascara |= dentro
    nivel = np.clip(np.round(1 + luz * (nivel_max - 1)), 1, nivel_max).astype(int)
    # tramado suave en el borde: píxeles sueltos para que no parezca una mancha sólida
    img[mascara, :3] = ramp[nivel[mascara]]
    img[mascara, 3] = 255
    borde = np.zeros((h, w), bool)
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        borde |= desplazar(mascara, dy, dx, False)
    borde &= ~mascara & (img[..., 3] == 0)
    img[borde, :3] = ramp[0]
    img[borde, 3] = 255


def fogonazo(tam=34, semilla=7):
    """Fogonazo de pólvora negra visto desde atrás: núcleo blanco, llamas en estrella, chispas."""
    rng = np.random.default_rng(semilla)
    S = 4
    n = tam * S
    c = (n - 1) / 2
    Y, X = np.mgrid[0:n, 0:n]
    dx, dy = (X - c) / S, (Y - c) / S * 1.0
    r = np.sqrt(dx ** 2 + (dy * 1.08) ** 2)
    ang = np.arctan2(dy, dx)
    # radio del borde de la llama en función del ángulo: 7 lenguas irregulares
    k = 7
    fases = rng.uniform(0, 2 * np.pi, 3)
    borde = (9.0 + 3.6 * np.maximum(0, np.cos(k * ang + fases[0])) ** 3
             + 1.6 * np.sin(3 * ang + fases[1]) + 1.0 * np.sin(11 * ang + fases[2]))
    borde *= tam / 34
    t = r / borde
    dentro = t <= 1.0
    # reducción por mayoría
    def red(a):
        return a.reshape(tam, S, tam, S).mean((1, 3))
    alfa = red(dentro.astype(float)) >= 0.5
    tt = red(np.where(dentro, t, 1.0))
    idx = np.clip((tt ** 1.2) * (len(FUEGO) - 1) + 0.2, 0, len(FUEGO) - 1).astype(int)
    img = np.zeros((tam, tam, 4), np.uint8)
    col = np.array(FUEGO, np.uint8)
    img[alfa, :3] = col[idx[alfa]]
    img[alfa, 3] = 255
    # chispas sueltas alrededor
    for _ in range(14):
        a = rng.uniform(0, 2 * np.pi)
        rr = rng.uniform(0.8, 1.25) * 15 * tam / 34
        sx, sy = int(round(tam / 2 + math.cos(a) * rr)), int(round(tam / 2 + math.sin(a) * rr))
        if 0 <= sx < tam and 0 <= sy < tam and img[sy, sx, 3] == 0:
            img[sy, sx, :3] = col[rng.integers(1, 6)]
            img[sy, sx, 3] = 255
    return img


# ---------------------------------------------------------------------------------------------
# Fotogramas
# ---------------------------------------------------------------------------------------------

# Lienzo común en coordenadas de pantalla completa (320x200); se recorta al guardar.
LIENZO = (100, 70, 170, 140)  # x0, y0, ancho, alto (abajo llega a y=210: sale por el borde)

POSE_A = {'recamara': (194.0, 136.0, 42.0), 'boca': (162.0, 110.0), 'alabeo': -8.0,
          'gato': 0.0, 'bateria': 0.0}


def pose_de(base, **cambios):
    p = dict(base)
    for k, v in cambios.items():
        if k in ('recamara', 'boca'):
            p[k] = tuple(a + b for a, b in zip(p[k], v))  # desplazamiento relativo
        elif k.startswith('d'):
            p[k[1:]] += v
        else:
            p[k] = v
    return p


POSES = {
    'PISGA0': POSE_A,
    # disparo: la boca salta hacia arriba girando sobre la muñeca y el arma retrocede hacia el
    # jugador; el pie de gato ha caído y la batería está abierta
    'PISGB0': pose_de(POSE_A, retroceso=10.0, empuje=(0.4, 1.2, -3.0), gato=58.0, bateria=-62.0),
    # vuelta: a medio camino
    'PISGC0': pose_de(POSE_A, retroceso=4.5, empuje=(0.2, 0.5, -1.4), gato=58.0, bateria=-62.0),
}


def render_fotograma(nombre, S=4):
    x0, y0, w, h = LIENZO
    pose = POSES[nombre]
    r = trazar(pose, x0, y0, w, h, S)
    alfa, m, I, z = reducir(r, S)
    img = colorear(alfa, m, I, z)
    # humo
    if nombre == 'PISGB0':
        px, py = proyectar(PIVOTE_BATERIA + (0.3, 0.6, -0.6), pose)
        bocanada(img, px - x0 + 2, py - y0 - 4,
                 [(0, 0, 3.2), (3, -3, 2.6), (-2, -5, 2.2), (2, -8, 1.8)], semilla=3)
    if nombre == 'PISGC0':
        px, py = proyectar(PIVOTE_BATERIA + (0.3, 0.6, -0.6), pose)
        bocanada(img, px - x0 + 4, py - y0 - 10, [(0, 0, 2.2), (2, -3, 1.8), (-1, -5, 1.4)], semilla=5, nivel_max=5)
        mx, my = proyectar((0, 0, LARGO + 2.0), pose)
        bocanada(img, mx - x0, my - y0 - 3, [(0, 0, 3.4), (-3, -2, 2.6), (3, -3, 2.8), (0, -6, 2.4), (-2, -8, 1.6)],
                 semilla=9, nivel_max=6)
    return img


def guardar(img, x0, y0, ruta):
    """Recorta lo transparente y devuelve los desplazamientos de Doom (izq, sup) del recorte."""
    a = img[..., 3] > 0
    ys, xs = np.nonzero(a)
    cx0, cx1, cy0, cy1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    Image.fromarray(img[cy0:cy1, cx0:cx1], 'RGBA').save(ruta)
    sx, sy = x0 + cx0, y0 + cy0          # esquina superior izquierda en pantalla completa
    return [int(1 - sx), int(32 - sy)], (int(sx), int(sy), int(cx1 - cx0), int(cy1 - cy0))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--salida', required=True, help='carpeta de PNG (arte/sprites)')
    ap.add_argument('--muestreo', type=int, default=4, help='rayos por lado de píxel (4 = 16 por píxel)')
    ap.add_argument('--solo', default=None, help='solo este lump (para pruebas)')
    args = ap.parse_args()
    os.makedirs(args.salida, exist_ok=True)
    x0, y0, _, _ = LIENZO
    offsets = {}
    geometria = {}
    for nombre in POSES:
        if args.solo and nombre != args.solo:
            continue
        img = render_fotograma(nombre, args.muestreo)
        offsets[nombre], geometria[nombre] = guardar(img, x0, y0, os.path.join(args.salida, nombre + '.png'))
        print(f'{nombre}: {geometria[nombre][2]}x{geometria[nombre][3]} en pantalla ({geometria[nombre][0]}, '
              f'{geometria[nombre][1]}) offsets {offsets[nombre]}')
    if not args.solo or args.solo == 'PISFA0':
        # fogonazo: centrado un poco por delante de la boca del cañón del fotograma B
        fx, fy = proyectar((0, 0.2, LARGO + 1.6), POSES['PISGB0'])
        f = fogonazo()
        ruta = os.path.join(args.salida, 'PISFA0.png')
        sx, sy = int(round(fx - f.shape[1] / 2)), int(round(fy - f.shape[0] / 2))
        offsets['PISFA0'], g = guardar(f, sx, sy, ruta)
        print(f'PISFA0: {g[2]}x{g[3]} en pantalla ({g[0]}, {g[1]}) offsets {offsets["PISFA0"]}')
    # offsets.json: conserva las claves de otros lumps
    ruta = os.path.join(args.salida, 'offsets.json')
    todos = {}
    if os.path.exists(ruta):
        with open(ruta) as fh:
            todos = json.load(fh)
    todos.update(offsets)
    with open(ruta, 'w') as fh:
        json.dump(dict(sorted(todos.items())), fh, indent=1)
        fh.write('\n')


if __name__ == '__main__':
    main()
