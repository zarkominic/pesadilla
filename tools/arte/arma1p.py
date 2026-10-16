#!/usr/bin/env python3
"""arma1p.py — motor común de las ARMAS EN PRIMERA PERSONA de PESADILLA (dibujadas por código).

Lo usan pistolon.py, escopeta.py, puno.py… para que todas compartan proyección, luz, paleta,
contorno, fogonazos y humo. Es un módulo (no se ejecuta solo).

Cómo funciona (determinista, sin IA ni azar no sembrado):
- Cada arma es un modelo 3D de primitivas SDF en CENTÍMETROS («espacio del arma»): una función
  modelo(P, pose) → (distancia, material) con P un array (N, 3). Un objeto Arma junta el modelo,
  sus materiales (rampas EXACTAS de PLAYPAL), brillos y un gancho de detalle (costuras, vetas…).
- La cámara es la del jugador con la proyección de los «psprites» de Doom: pantalla completa
  320x200 cuyos píxeles se ven 1,2 veces más altos que anchos (F = 170 px de focal horizontal).
  Una pose se pone en pantalla con matriz_canon (dónde se ve la recámara y hacia dónde apunta la
  boca) o con cualquier (R, T): p_cámara = R · p_arma + T.
- trazar → raymarching vectorizado (numpy) con S x S rayos por píxel; reducir → alfa por mayoría,
  material mayoritario e intensidad media; colorear → rampas de PLAYPAL, líneas de profundidad y
  contorno oscuro de 1 px (luz desde arriba-izquierda-delante, como las criaturas).
- Todos los fotogramas de un arma se dibujan en el MISMO lienzo de pantalla (x0, y0, ancho, alto):
  guardar() recorta lo transparente y saca los desplazamientos de Doom de la posición real en
  pantalla (izq = 1 - x, sup = 32 - y), así no hay saltos entre fotogramas y el fogonazo cae
  donde está la boca. guardar_offsets() los mezcla en offsets.json sin tocar las claves ajenas.

Piezas reutilizables: primitivas (capsula, elipsoide, caja, tubo_z, tubo…); el guante del
pistolón: puno/puno_partes (puño cerrado) + detalle_puno (pespuntes y surcos de los dedos),
mano_agarre (mano que agarra un cilindro: derecha o izquierda según el marco Agarre), guante
(manopla acampanada con ribete y manga de paño), pliegues / pliegues_pano (surcos del paño) y filo
(el color claro solo en el borde iluminado); veta del nogal; bocanada (humo);
fogonazo y llamarada (fogonazos a pleno brillo, de uno o varios focos); mover_pose (giros extra
de un arma); dibujar(previo=True) acelera lienzos grandes; simular_pantalla compone lumps con sus
offsets en una pantalla 320x200 (con barra de estado o sin ella) para revisar.
Usuarios: pistolon.py (PISG/PISF), escopeta.py (SHTG/SHTF/SHOT), puno.py (PUNG).
"""
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
    # hierro pavonado: grises muy oscuros (7, 6, 5, 111, 109, 107, 104, 100); el brillo especular
    # (fino) llega al último, un azul pálido (195): en PLAYPAL no hay grises azulados, y al
    # oscurecerse por la luz del sector pasa a los azules oscuros (240..), que leen como pavón
    'pavonado': _hx(0x0b0b0b, 0x131313, 0x1b1b1b, 0x232323, 0x2f2f2f, 0x3b3b3b, 0x4f4f4f, 0x6b6b6b, 0x8f8fff),
    # paño de la manga: granate oscuro como el capirote del Penitente (2, 47, 45, 43, 40); el
    # último (37) solo lo alcanza el filo iluminado (ver filo())
    'pano': _hx(0x0b0b0b, 0x170f07, 0x430000, 0x4f0000, 0x5b0707, 0x6b0f0f, 0x7f1b1b),
    # cartón de los cartuchos: rojo (191..179)
    'carton': _hx(0x430000, 0x5b0000, 0x730000, 0x8b0000, 0xa70000, 0xbf0000, 0xd70000),
    # hueco: el interior de un cañón (casi negro)
    'hueco': _hx(0x000000, 0x070707, 0x0b0b0b, 0x131313),
}
CONTORNO = (0x17, 0x0f, 0x07)  # PLAYPAL 2

# Fogonazo (se dibuja a pleno brillo): blanco → amarillo → naranja → rojo oscuro
FUEGO = _hx(0xffffff, 0xffffd7, 0xffff8f, 0xffff47, 0xffe74b, 0xffc79b, 0xffa35b, 0xff8f3b,
            0xff7f1b, 0xeb6f0f, 0xd75f0b, 0xc34f00, 0xa73f00, 0x872300)

# ---------------------------------------------------------------------------------------------
# Primitivas SDF (P: array (N,3) en cm)
# ---------------------------------------------------------------------------------------------


def v3(x, y, z):
    return np.array([x, y, z], dtype=np.float64)


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


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


def tubo(P, a, b, r0, r1=None):
    """Cilindro de tapas planas de a a b (radio de r0 a r1), eje cualquiera."""
    r1 = r0 if r1 is None else r1
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    ba = b - a
    L = math.sqrt(ba @ ba)
    u = ba / L
    pa = P - a
    s = pa @ u
    q = pa - s[:, None] * u
    t = np.clip(s / L, 0, 1)
    d2 = np.sqrt((q * q).sum(1)) - (r0 + t * (r1 - r0))
    dz = np.abs(s - L / 2) - L / 2
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


def rot_eje(eje, g):
    """Giro de g radianes alrededor de un eje cualquiera (regla de la mano derecha)."""
    x, y, z = unit(eje)
    c, s, t = math.cos(g), math.sin(g), 1 - math.cos(g)
    return np.array([[t * x * x + c, t * x * y - s * z, t * x * z + s * y],
                     [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
                     [t * x * z - s * y, t * y * z + s * x, t * z * z + c]])


def girar(P, pivote, R):
    """Puntos del espacio del arma → espacio de una pieza girada R alrededor de pivote."""
    return (P - pivote) @ R + pivote  # R ortogonal: (R^T (p - c))^T = (p - c)^T R


def elipsoide_ejes(P, c, ejes, r):
    """Elipsoide con centro c, ejes (3 vectores unitarios) y semiejes r."""
    q = (P - c) @ np.stack(ejes, 1)
    return elipsoide(q, (0, 0, 0), r)


# ---------------------------------------------------------------------------------------------
# Cámara del jugador (proyección de los psprites de Doom)
# ---------------------------------------------------------------------------------------------

F = 170.0        # distancia focal en píxeles de pantalla (horizontal)
ASPECTO = 1.2    # los píxeles de Doom se ven 1,2 veces más altos


def matriz_canon(recamara, boca, largo, alabeo):
    """Pone un arma alargada en pantalla → (R, T) con p_cámara = R · p_arma + T.

    recamara = (x, y, Z): dónde se ve en pantalla completa el origen del arma y a qué profundidad
    (cm); boca = (x, y): dónde debe verse el punto (0, 0, largo) del arma (la boca del cañón);
    alabeo = giro (grados) sobre el eje del cañón (positivo: el costado derecho sube).
    """
    bx, by, bz = recamara
    T = np.array([(bx - 160) * bz / F, -(by - 100) * ASPECTO * bz / F, bz])
    mx, my = boca
    u = np.array([(mx - 160) / F, -(my - 100) * ASPECTO / F, 1.0])  # rayo hacia la boca
    # |Zm·u - T| = largo  →  (u·u) Zm² - 2 (u·T) Zm + T·T - largo² = 0 (raíz lejana)
    a, b, c = u @ u, -2 * (u @ T), T @ T - largo ** 2
    zm = (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a)
    dz = zm * u - T
    dz /= np.linalg.norm(dz)
    dx = np.cross([0.0, 1.0, 0.0], dz)
    dx /= np.linalg.norm(dx)
    dy = np.cross(dz, dx)
    g = math.radians(alabeo)
    dx, dy = math.cos(g) * dx + math.sin(g) * dy, -math.sin(g) * dx + math.cos(g) * dy
    R = np.stack([dx, dy, dz], 1)
    return R, T


def retroceso(R, T, giro, empuje, pivote):
    """Retroceso: el arma gira 'giro' grados (boca arriba) alrededor de 'pivote' (espacio del
    arma) y se desplaza 'empuje' (cm, espacio de cámara)."""
    Rr = rot_x(-math.radians(giro))
    pv = pivote
    T = R @ pv - R @ Rr @ pv + T + np.asarray(empuje, float)
    R = R @ Rr
    return R, T


def mover_pose(R, T, Rr, pivote, empuje=(0.0, 0.0, 0.0)):
    """Gira el arma Rr (matriz en espacio del arma) alrededor de 'pivote' (espacio del arma) y la
    desplaza 'empuje' (cm, espacio de cámara). → (R, T) nuevos."""
    pv = np.asarray(pivote, float)
    T = R @ pv - R @ Rr @ pv + T + np.asarray(empuje, float)
    return R @ Rr, T


def proyectar(p_arma, R, T):
    """Punto del espacio del arma → (x, y) en la pantalla completa 320x200."""
    q = R @ np.asarray(p_arma, float) + T
    return 160 + F * q[0] / q[2], 100 - F / ASPECTO * q[1] / q[2]


def pantalla_a_camara(x, y, z):
    """Punto de pantalla completa (x, y) a profundidad z (cm) → espacio de cámara."""
    return np.array([(x - 160) * z / F, -(y - 100) * ASPECTO * z / F, z])


# ---------------------------------------------------------------------------------------------
# Trazado, luz, reducción y color
# ---------------------------------------------------------------------------------------------

LUZ = np.array([-0.55, 0.72, -0.42])
LUZ /= np.linalg.norm(LUZ)


class Arma:
    """Un arma (o mano) dibujable.

    mats: nombres de material (índices de 'modelo'); modelo(P, pose) → (distancia, material);
    brillo: {mat: (fuerza, exponente)}; ganancia: {mat: parte de la rampa con luz plena};
    detalle(arma, r, I): gancho que retoca la intensidad (costuras, vetas…); rampas: por nombre.
    """

    def __init__(self, mats, modelo, brillo, ganancia, detalle=None, rampas=None, luz=None):
        self.mats = list(mats)
        self.modelo = modelo
        self.brillo = brillo
        self.ganancia = ganancia
        self.detalle = detalle
        self.rampas = RAMPAS if rampas is None else rampas
        self.luz = LUZ if luz is None else luz

    def idx(self, nombre):
        return self.mats.index(nombre)


def trazar(arma, pose, R, T, x0, y0, w, h, S, t0=15.0, tmax=110.0, pasos=160, mascara=None):
    """Traza el lienzo [x0, x0+w) x [y0, y0+h) de la pantalla con S x S rayos por píxel.
    mascara (h x w, opcional): solo se trazan los píxeles marcados (los demás quedan vacíos)."""
    modelo = arma.modelo
    xs = x0 + (np.arange(w * S) + 0.5) / S
    ys = y0 + (np.arange(h * S) + 0.5) / S
    X, Y = np.meshgrid(xs, ys)
    D = np.stack([(X - 160) / F, -(Y - 100) * ASPECTO / F, np.ones_like(X)], -1).reshape(-1, 3)
    D /= np.linalg.norm(D, axis=1, keepdims=True)
    N = D.shape[0]
    t = np.full(N, float(t0))
    hit = np.zeros(N, bool)
    if mascara is None:
        vivos = np.arange(N)
    else:
        vivos = np.nonzero(np.repeat(np.repeat(mascara, S, 0), S, 1).reshape(-1))[0]
    for _ in range(pasos):
        if vivos.size == 0:
            break
        p = D[vivos] * t[vivos, None]
        dist, _ = modelo((p - T) @ R, pose)
        t[vivos] += dist * 0.8
        acierto = dist < 0.01
        hit[vivos[acierto]] = True
        vivos = vivos[~acierto & (t[vivos] < tmax)]
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
    out['pose'] = pose
    return out


def intensidad(arma, r):
    """Intensidad de luz continua (0..1+) por sub-píxel."""
    n = r['n']
    V = -r['dir']
    LZ = arma.luz
    lam = np.clip((n * LZ).sum(-1), 0, 1)
    H = LZ + V
    H /= np.linalg.norm(H, axis=-1, keepdims=True)
    nh = np.clip((n * H).sum(-1), 0, 1)
    I = 0.2 + 0.8 * lam
    I = I * (0.55 + 0.45 * r['ao'])
    spec = np.zeros_like(I)
    for i, m in enumerate(arma.mats):
        k, p = arma.brillo[m]
        sel = r['mat'] == i
        spec[sel] = k * nh[sel] ** p
    I = I + spec
    if arma.detalle is not None:
        arma.detalle(arma, r, I)
    return I


def veta(arma, r, I, mat='nogal', fuerza=0.07):
    """Veta de la madera: bandas suaves a lo largo de la pieza (en espacio del arma)."""
    pl = r['pl']
    v = np.sin(pl[..., 2] * 2.1 + np.sin(pl[..., 1] * 3.3 + pl[..., 0] * 1.7) * 1.6)
    sel = r['mat'] == arma.idx(mat)
    I[sel] += fuerza * v[sel]


def reducir(arma, r, S):
    """Sub-píxeles → píxeles: alfa por mayoría, material mayoritario, intensidad media."""
    hS, wS = r['hit'].shape
    h, w = hS // S, wS // S
    hit = r['hit'].reshape(h, S, w, S).transpose(0, 2, 1, 3).reshape(h, w, S * S)
    mat = r['mat'].reshape(h, S, w, S).transpose(0, 2, 1, 3).reshape(h, w, S * S)
    I = intensidad(arma, r).reshape(h, S, w, S).transpose(0, 2, 1, 3).reshape(h, w, S * S)
    z = r['z'].reshape(h, S, w, S).transpose(0, 2, 1, 3).reshape(h, w, S * S)
    alfa = hit.mean(-1) >= 0.5
    cuenta = np.stack([(mat == i).sum(-1) for i in range(len(arma.mats))], -1)
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


def colorear(arma, alfa, m, I, z, contorno=True, bordes=True):
    h, w = alfa.shape
    nivel = np.zeros((h, w), int)
    for i, nombre in enumerate(arma.mats):
        n = len(arma.rampas[nombre])
        sel = m == i
        nivel[sel] = np.clip(np.floor(I[sel] * arma.ganancia[nombre] * (n - 1) + 0.35), 1, n - 1)
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
    for i, nombre in enumerate(arma.mats):
        ramp = np.array(arma.rampas[nombre], np.uint8)
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


def dibujar(arma, pose, R, T, lienzo, S=4, previo=False, bordes=True, **kw):
    """Traza, reduce y colorea un fotograma en el lienzo de pantalla (x0, y0, ancho, alto) → RGBA.
    previo=True: primero una pasada barata (2x2 rayos por píxel) para saber dónde hay algo, y la
    buena solo ahí (y 2 píxeles alrededor): mucho más rápido en lienzos grandes.
    bordes=False: sin líneas de profundidad (para objetos lejanos, donde todo saltaría)."""
    x0, y0, w, h = lienzo
    if previo:
        r0 = trazar(arma, pose, R, T, x0, y0, w, h, 2, **kw)
        m = r0['hit'].reshape(h, 2, w, 2).any(axis=(1, 3))
        for _ in range(2):
            m = m | desplazar(m, 1, 0, False) | desplazar(m, -1, 0, False) | desplazar(m, 0, 1, False) | desplazar(m, 0, -1, False)
        kw['mascara'] = m
    r = trazar(arma, pose, R, T, x0, y0, w, h, S, **kw)
    alfa, m, I, z = reducir(arma, r, S)
    return colorear(arma, alfa, m, I, z, bordes=bordes)


def componer(abajo, arriba):
    """Pone 'arriba' (RGBA, mismo tamaño) encima de 'abajo' (sin mezclas: píxel opaco gana)."""
    out = abajo.copy()
    sel = arriba[..., 3] > 0
    out[sel] = arriba[sel]
    return out


# ---------------------------------------------------------------------------------------------
# Mano enguantada (el mismo guante de cuero del pistolón) y manga
# ---------------------------------------------------------------------------------------------


class Agarre:
    """Marco de una mano que agarra un cilindro (como la del pistolón en la culata).

    G0: punto del eje del cilindro a la altura del índice; GE: eje del cilindro del índice hacia el
    meñique; GF: «delante» (por donde los dedos rodean el cilindro); GX: lado del dorso.
    Con (GX, GE, GF) de mano derecha (GX × GE = -GF) sale una mano derecha; con GX al revés, la
    izquierda (espejo). r: radio del cilindro agarrado (el del pistolón ≈ 1,4 cm).
    """

    def __init__(self, G0, GE, GF, GX, r=1.4):
        self.G0 = np.asarray(G0, float)
        self.GE = unit(GE)
        self.GF = unit(GF)
        self.GX = unit(GX)
        self.r = r

    def p(self, s, x, f):
        """Punto de la mano: s cm bajando por el cilindro, x hacia el dorso, f hacia delante."""
        return self.G0 + s * self.GE + x * self.GX + f * self.GF

    def ejes(self):
        return (self.GX, self.GE, self.GF)


def mano_agarre(P, A, antebrazo, cerrada=0.0):
    """Distancia a una mano enguantada que agarra el cilindro del marco A (sin manopla).

    antebrazo: dirección (espacio del arma) en la que sale el antebrazo desde la muñeca.
    cerrada: 0 = agarra el cilindro de radio A.r; 1 = puño cerrado (los dedos se meten en la palma).
    Devuelve (distancia, punto de la muñeca).
    """
    k = A.r / 1.4                       # los dedos rodean un cilindro más grueso o más fino
    ej = A.ejes()
    dorso = elipsoide_ejes(P, A.p(4.3, 1.75 * k, -0.45 * k), ej, (1.4, 4.1, 2.8 * max(k, 0.8)))
    palma = elipsoide_ejes(P, A.p(4.6, 0.3 * k, -1.3 * k), ej, (1.7, 3.9, 1.9))
    tenar = elipsoide_ejes(P, A.p(2.4, -1.15 * k, -1.25 * k), ej, (1.05, 2.1, 1.6))
    membrana = capsula(P, A.p(0.9, 1.2 * k, -0.5 * k), A.p(0.9, -0.9 * k, -1.3 * k), 0.95, 0.9)
    # pulgar: por el lado contrario al dorso, hacia delante y arriba del cilindro
    t0 = A.p(1.6, -1.35 * k, -1.0 * k)
    t1 = A.p(-1.2 - 0.6 * cerrada, -1.45 * k - 0.3, 0.6 * k + 0.9 * cerrada)
    t2 = A.p(-1.0 - 0.4 * cerrada, -0.5 * k - 0.6 * cerrada, 1.8 * k + 0.9 * cerrada)
    pulgar = np.minimum(capsula(P, t0, t1, 0.95, 0.82), capsula(P, t1, t2, 0.82, 0.72))
    mano = smin(smin(dorso, palma, 1.0), smin(smin(tenar, membrana, 0.8), pulgar, 0.6), 0.8)
    dedos = None
    for i, s in enumerate((0.9, 2.95, 4.9, 6.75)):
        r = 0.9 - 0.05 * i
        nud = A.p(s, 1.65 * k, 1.3 * k)                         # nudillo
        a = A.p(s, 0.35 * k, 2.35 * k)                          # delante del cilindro
        b = A.p(s + 0.2, -1.45 * k, 1.35 * k)                   # esquina del otro lado
        c = A.p(s + 0.3, -1.85 * k + 0.9 * cerrada, -0.15 * k - 1.2 * cerrada)   # punta
        f = np.minimum(np.minimum(capsula(P, nud, a, r, r * 0.95), capsula(P, a, b, r * 0.95, r * 0.9)),
                       capsula(P, b, c, r * 0.9, r * 0.82))
        dedos = f if dedos is None else np.minimum(dedos, f)
    mano = smin(mano, dedos, 0.45)
    w0 = A.p(7.0, 0.9 * k, -2.0 * k)
    muneca = capsula(P, w0, w0 + 3.0 * antebrazo, 2.25, 2.3)
    mano = smin(mano, muneca, 1.2)
    return mano, w0


def guante(d, P, w0, antebrazo, largo_manga=30.0, escala=1.0):
    """Manopla acampanada del guante (mismo cuero que el pistolón) con ribete claro en el borde, y
    manga de paño. d: dict de distancias por material; d['cuero'] ya tiene la mano."""
    e = escala
    L = 3.4 * e
    ea = w0 + 1.0 * e * antebrazo
    eb = ea + L * antebrazo
    vuelta = tubo(P, ea, eb, 2.55 * e, 3.85 * e) - 0.15 * e
    hueco = tubo(P, ea + 0.8 * e * antebrazo, eb + 1.0 * e * antebrazo, 1.9 * e, 3.3 * e)
    vuelta = np.maximum(vuelta, -hueco)
    d['cuero'] = smin(d['cuero'], vuelta, 0.6 * e)
    t = (P - ea) @ antebrazo
    rib = np.maximum(vuelta - 0.05, (L - 0.75 * e) - t)  # el último centímetro de la manopla
    d['ribete'] = rib if 'ribete' not in d else np.minimum(d['ribete'], rib)
    manga = capsula(P, ea + (L - 1.0 * e) * antebrazo, w0 + largo_manga * antebrazo, 3.25 * e, 4.8 * e)
    d['manga'] = manga if 'manga' not in d else np.minimum(d['manga'], manga)


def pliegues(arma, r, I, origen, eje, mat='manga', fuerza=0.12):
    """Pliegues de la manga: bandas oblicuas a lo largo del eje (espacio del arma)."""
    sel = r['mat'] == arma.idx(mat)
    if not sel.any():
        return
    q = r['pl'][sel] - origen
    t = q @ eje
    lado = q - np.outer(t, eje)
    ang = np.arctan2(lado @ np.cross(eje, (0.0, 1.0, 0.0)), lado[:, 1])
    v = np.sin(t * 0.75 + 0.9 * np.sin(ang * 2.0))
    I[sel] += fuerza * v


def pliegues_pano(arma, r, I, origen, eje, posiciones, mat='manga', ancho=0.9, fuerza=0.22, oblicuo=1.1,
                  sel=None):
    """Pliegues marcados del paño (2-3 surcos): para cada t0 de 'posiciones' (cm a lo largo de 'eje'
    desde 'origen', espacio del arma) un surco oscuro algo oblicuo, con el lomo iluminado detrás.
    sel (opcional): solo esos sub-píxeles (p. ej. una de las dos mangas)."""
    sel = (r['mat'] == arma.idx(mat)) if sel is None else (sel & (r['mat'] == arma.idx(mat)))
    if not sel.any():
        return
    q = r['pl'][sel] - origen
    t = q @ eje
    lado = q - np.outer(t, eje)
    ang = np.arctan2(lado @ np.cross(eje, (0.0, 1.0, 0.0)), lado[:, 1])
    v = np.zeros(len(t))
    for i, t0 in enumerate(posiciones):
        s = t - t0 - oblicuo * np.sin(ang + 0.7 * i)
        v -= fuerza * (np.abs(s) < ancho * 0.5)
        v += 0.5 * fuerza * ((s > ancho * 0.5) & (s < ancho * 1.6))
    I[sel] += v


def filo(arma, r, I, mat='manga', fuerza=0.6, umbral=0.7):
    """Brillo fino en el filo iluminado (la silueta del lado de la luz) de un material: así el
    color más claro de su rampa sale solo en el borde y no en una mancha en el centro."""
    sel = r['mat'] == arma.idx(mat)
    if not sel.any():
        return
    n = r['n'][sel]
    V = -r['dir'][sel]
    rasante = 1.0 - np.abs((n * V).sum(-1))
    luz = n @ arma.luz
    I[sel] += fuerza * ((rasante > umbral) & (luz > 0.2))


def costuras(arma, r, I, A, lado=1.2, mat='cuero', fuerza=0.3):
    """Pespuntes del dorso del guante (tres líneas entre los dedos) para la mano del marco A."""
    pl = r['pl']
    q = pl - A.G0
    sg, fg, xg = q @ A.GE, q @ A.GF, q @ A.GX
    k = A.r / 1.4
    cos = np.zeros(sg.shape, bool)
    for s0 in (1.95, 3.95, 5.85):
        cos |= (np.abs(sg - s0 - 0.25 * fg) < 0.16) & (xg > lado * k) & (fg > -2.6 * k) & (fg < 1.4 * k)
    sel = (r['mat'] == arma.idx(mat)) & cos
    I[sel] -= fuerza


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


def llamarada(w, h, focos, semilla=7, lenguas=7, chispas=18, S=4, potencia=1.2):
    """Fogonazo general (a pleno brillo) en un lienzo w x h: unión de varias llamas en estrella.

    focos: [(cx, cy, radio, alargamiento_y, desfase)], en píxeles del lienzo; la intensidad
    va del blanco (centro de cada foco) al rojo oscuro (borde).
    """
    rng = np.random.default_rng(semilla)
    Y, X = np.mgrid[0:h * S, 0:w * S]
    tmin = np.full(X.shape, 9.0)
    for (cx, cy, rad, ay, fase) in focos:
        dx = (X + 0.5) / S - cx
        dy = ((Y + 0.5) / S - cy) / ay
        r = np.sqrt(dx ** 2 + dy ** 2)
        ang = np.arctan2(dy, dx)
        fases = rng.uniform(0, 2 * np.pi, 3) + fase
        borde = (1.0 + 0.42 * np.maximum(0, np.cos(lenguas * ang + fases[0])) ** 3
                 + 0.17 * np.sin(3 * ang + fases[1]) + 0.1 * np.sin(11 * ang + fases[2])) * rad
        tmin = np.minimum(tmin, r / borde)
    dentro = tmin <= 1.0

    def red(a):
        return a.reshape(h, S, w, S).mean((1, 3))
    alfa = red(dentro.astype(float)) >= 0.5
    tt = red(np.where(dentro, tmin, 1.0))
    idx = np.clip((tt ** potencia) * (len(FUEGO) - 1) + 0.2, 0, len(FUEGO) - 1).astype(int)
    img = np.zeros((h, w, 4), np.uint8)
    col = np.array(FUEGO, np.uint8)
    img[alfa, :3] = col[idx[alfa]]
    img[alfa, 3] = 255
    # chispas sueltas alrededor de los focos
    for _ in range(chispas):
        cx, cy, rad, ay, _f = focos[rng.integers(len(focos))]
        a = rng.uniform(0, 2 * np.pi)
        rr = rng.uniform(1.05, 1.6) * rad
        sx, sy = int(round(cx + math.cos(a) * rr)), int(round(cy + math.sin(a) * rr * ay))
        if 0 <= sx < w and 0 <= sy < h and img[sy, sx, 3] == 0:
            img[sy, sx, :3] = col[rng.integers(1, 7)]
            img[sy, sx, 3] = 255
    return img


# ---------------------------------------------------------------------------------------------
# Guardado
# ---------------------------------------------------------------------------------------------


def guardar(img, x0, y0, ruta):
    """Recorta lo transparente y devuelve los desplazamientos de Doom (izq, sup) del recorte."""
    a = img[..., 3] > 0
    ys, xs = np.nonzero(a)
    cx0, cx1, cy0, cy1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    Image.fromarray(img[cy0:cy1, cx0:cx1], 'RGBA').save(ruta)
    sx, sy = x0 + cx0, y0 + cy0          # esquina superior izquierda en pantalla completa
    return [int(1 - sx), int(32 - sy)], (int(sx), int(sy), int(cx1 - cx0), int(cy1 - cy0))


def guardar_offsets(carpeta, offsets):
    """Añade/actualiza 'offsets' en <carpeta>/offsets.json conservando las claves de otros lumps."""
    ruta = os.path.join(carpeta, 'offsets.json')
    todos = {}
    if os.path.exists(ruta):
        with open(ruta) as fh:
            todos = json.load(fh)
    todos.update(offsets)
    with open(ruta, 'w') as fh:
        json.dump(dict(sorted(todos.items())), fh, indent=1)
        fh.write('\n')


def simular_pantalla(carpeta, capas, barra=True, fondo=None):
    """Compone lumps de 'carpeta' (con su offsets.json) en una pantalla 320x200 como el juego
    (con barra de estado el arma sube 16 px y la barra tapa desde y = 168). → Image RGBA."""
    from PIL import ImageDraw
    with open(os.path.join(carpeta, 'offsets.json')) as fh:
        off = json.load(fh)
    s = Image.new('RGBA', (320, 200), (0, 0, 0, 255))
    d = ImageDraw.Draw(s)
    if fondo is None:
        d.rectangle((0, 0, 320, 90), fill=(55, 50, 45, 255))
        d.rectangle((0, 90, 320, 200), fill=(35, 30, 25, 255))
        for x in range(0, 320, 32):
            d.line((x, 0, x, 90), fill=(45, 40, 35, 255))
    else:
        s.paste(fondo)
    dy = -16 if barra else 0
    for n in capas:
        ruta = os.path.join(carpeta, n + '.png')
        if not os.path.exists(ruta):
            continue
        im = Image.open(ruta).convert('RGBA')
        L, T = off[n]
        capa = Image.new('RGBA', (320, 200), (0, 0, 0, 0))
        capa.paste(im, (1 - L, 32 - T + dy))
        s.alpha_composite(capa)
    if barra:
        d = ImageDraw.Draw(s)
        d.rectangle((0, 168, 320, 200), fill=(90, 90, 90, 255))
    return s


# ---------------------------------------------------------------------------------------------
# Puño cerrado (espacio de la mano: origen en la muñeca, z hacia los nudillos, y hacia el dorso,
# x a la derecha; en la mano derecha el pulgar queda en -x)
# ---------------------------------------------------------------------------------------------

# dedos del puño: (x, altura y adelanto del nudillo, radio); índice en el lado del pulgar (-x)
DEDOS_PUNO = ((-2.65, 0.5, 8.0, 1.08), (-0.85, 0.55, 8.15, 1.08), (0.95, 0.4, 7.9, 1.02), (2.65, 0.05, 7.35, 0.92))
MUNECA_PUNO = v3(0.0, -0.3, -0.5)


def puno_partes(P, izquierda=False, escala=1.0):
    """Partes del puño cerrado enguantado (sin manopla ni manga), en espacio de la mano.
    → dict con 'mano' (palma y dorso), 'dedos' (lista de 4, índice primero), 'pulgar', 'muneca'.
    escala: tamaño (1 = mano de verdad; los guantes de Doom se exageran un poco)."""
    P = P / escala
    if izquierda:
        P = P * np.array([-1.0, 1.0, 1.0])
    dorso = elipsoide(P, (0.0, 0.15, 4.6), (4.0, 1.75, 3.7))
    palma = elipsoide(P, (0.3, -1.35, 4.3), (3.6, 1.65, 3.3))
    partes = {'mano': smin(dorso, palma, 1.0) * escala, 'dedos': []}
    for (x, y, z, r) in DEDOS_PUNO:
        k = r / 1.08
        nud = v3(x, y, z)
        a = v3(x * 1.02, y - 2.95 * k, z + 0.75 * k)        # falange: baja por delante
        b = v3(x * 1.0, y - 3.75 * k, z - 1.6 * k)          # falange media: vuelve por debajo
        c = v3(x * 0.95, y - 2.7 * k, z - 2.7 * k)          # punta: metida en la palma
        f = np.minimum(np.minimum(capsula(P, nud, a, r, r * 0.95), capsula(P, a, b, r * 0.95, r * 0.88)),
                       capsula(P, b, c, r * 0.88, r * 0.8))
        f = np.minimum(f, elipsoide(P, nud, (r * 0.95, r * 0.9, r * 0.95)))
        partes['dedos'].append(f * escala)
    # pulgar: nace junto a la muñeca, abulta en el costado y cruza por delante de índice y corazón
    t0, t1, t2, t3 = v3(-2.9, -0.9, 2.0), v3(-3.95, -1.75, 5.0), v3(-3.5, -2.75, 8.2), v3(-0.9, -2.95, 9.25)
    partes['pulgar'] = np.minimum(np.minimum(capsula(P, t0, t1, 1.3, 1.08), capsula(P, t1, t2, 1.08, 0.95)),
                                  capsula(P, t2, t3, 0.95, 0.85)) * escala
    partes['muneca'] = capsula(P, MUNECA_PUNO + v3(0, 0, 1.0), MUNECA_PUNO + v3(0, 0, -2.5), 2.35, 2.4) * escala
    return partes


def puno(P, izquierda=False, escala=1.0):
    """Distancia a un puño cerrado enguantado (sin manopla ni manga). → (distancia, muñeca)."""
    pt = puno_partes(P, izquierda, escala)
    dedos = pt['dedos'][0]
    for f in pt['dedos'][1:]:
        dedos = smin(dedos, f, 0.25 * escala)
    mano = smin(pt['mano'], dedos, 0.7 * escala)
    mano = smin(mano, pt['pulgar'], 0.6 * escala)
    mano = smin(mano, pt['muneca'], 1.2 * escala)
    return mano, MUNECA_PUNO * escala


def detalle_puno(arma, r, I, sel_mano, izquierda=False, escala=1.0, marco=None, mat='cuero'):
    """Pespuntes del dorso (tres líneas de los nudillos a la muñeca) y surcos entre los dedos y
    alrededor del pulgar, para que el puño se lea a 1x. sel_mano: sub-píxeles de esta mano;
    marco: función pl → espacio de la mano (si la mano no es el espacio del arma)."""
    sel = (r['mat'] == arma.idx(mat)) & sel_mano
    if not sel.any():
        return
    pl = r['pl'][sel] if marco is None else marco(r['pl'][sel])
    q = pl / escala * np.array([-1.0 if izquierda else 1.0, 1.0, 1.0])
    x, y, z = q[:, 0], q[:, 1], q[:, 2]
    cos = np.zeros(len(q), bool)
    for x0 in (-1.75, 0.05, 1.8):
        cos |= (np.abs(x - x0 - 0.12 * (z - 6.0)) < 0.17) & (z > 3.6) & (z < 7.2) & (y > 0.9)
    pt = puno_partes(pl, izquierda, escala)
    D = np.sort(np.stack(pt['dedos'], 1), 1)
    dmin = D[:, 0]
    surco = (D[:, 1] - D[:, 0] < 0.3 * escala) & (D[:, 1] < 0.45 * escala)        # entre dos dedos
    surco |= (np.abs(pt['pulgar'] - dmin) < 0.28 * escala) & (np.maximum(pt['pulgar'], dmin) < 0.5 * escala)
    v = I[sel]
    v[cos] -= 0.3
    v[surco & ~cos] -= 0.38
    I[sel] = v


def marco_mira(dirz, arriba=(0.0, 1.0, 0.0), alabeo=0.0):
    """Matriz (columnas x, y, z) con z = dirz, y lo más parecido a 'arriba', girada 'alabeo'
    grados sobre z (positivo: el lado derecho sube)."""
    z = unit(dirz)
    x = np.cross(np.asarray(arriba, float), z)
    x = unit(x)
    y = np.cross(z, x)
    g = math.radians(alabeo)
    x, y = math.cos(g) * x + math.sin(g) * y, -math.sin(g) * x + math.cos(g) * y
    return np.stack([x, y, z], 1)
