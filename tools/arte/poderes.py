#!/usr/bin/env python3
"""poderes.py — PODERES Y LLAVES de PESADILLA (sustituyen a los de Freedoom), dibujados POR CÓDIGO.

Uso (determinista, regenera los 28 PNG del grupo y arte/sprites/offsets_poderes.json):
    ~/.venvs/pesadilla/bin/python tools/arte/poderes.py --salida arte/sprites
    … --solo PINVA0,BKEYB0      solo esos lumps
    … --hoja hoja.png           además, hoja de contactos ampliada junto a los de Freedoom

Objetos (estados de info.c; ninguno rota: lumps X?0):
- PINVA0-D0  invulnerabilidad (pleno brillo, flota): un gran amuleto de AZABACHE negro engastado en
             plata, con una luz verde-blanca que late a su alrededor (A-D: el halo crece y mengua).
- PSTRA0     berserk (pleno brillo): una BOTA DE VINO NEGRA (de pez, con lustre) tumbada en horizontal, con
             su boquilla de cuerno claro, el tapón rojo, el cordón rojo en lazo y un charco de vino delante
             (negra y apaisada: no se confunde con el zurrón ni la bolsita de munición, pardos y de pie).
- PINSA0-D0  invisibilidad parcial (pleno brillo, flota): una CAPA DE NIEBLA, un jirón de tela gris
             translúcida (tramado) con capucha que se retuerce; dentro, dos ojos que se abren y se cierran.
- SUITA0     traje antirradiación (pleno brillo): el CHUBASQUERO encerado amarillo de un marinero gallego
             con su sueste y sus botas de goma, de pie y vacío (no hay nadie dentro).
- PMAPA0-D0  mapa (pleno brillo; el juego hace A B C D C B): un PERGAMINO medio enrollado con el plano
             de un pueblo cuya tinta se enciende a ratos (D = el brillo más fuerte).
- PVISA0-B0  visión nocturna (A a pleno brillo): un CANDIL de hierro de mano, con su pico y su garabato
             para colgarlo; A con la llama viva, B con la llama baja que titila.
- BKEY/RKEY/YKEY A-B  llaves de tarjeta: una LLAVE grande de hierro antigua (ojo de anillo) con un lazo
             del color del juego (azul, rojo, amarillo); en B (pleno brillo) el lazo brilla.
- BSKU/RSKU/YSKU A-B  llaves de calavera: una LLAVE DE HUESO tallado cuyo ojo es una CALAVERA TEÑIDA del
             color (como de cristal), con chispas claras en las cuencas; en B la calavera brilla con halo.
             Las dos clases de llave tienen la caña corta (unos 22-23 px de alto).

Técnica: el mismo motor que las criaturas (tools/arte/sdf.py): modelos 3D de primitivas SDF trazados con
rampas EXACTAS de PLAYPAL, luz desde arriba-izquierda-delante y contorno oscuro de 1 px. La cámara mira
algo desde arriba (más en los objetos tumbados: bota y pergamino). Las luces (halo del amuleto, llama del
candil, brillo de los lazos y las gemas) y la translucidez de la capa (tramado ordenado) se pintan en 2D
encima del trazado, también con colores exactos de PLAYPAL.

Apoyo (offsets explícitos en offsets_poderes.json), anclado al trazado SÓLIDO (sin los halos ni la llama
pintados encima) para que los fotogramas de un objeto no salten: centrado horizontal; los objetos del suelo
apoyan su fila de abajo en el suelo (0-2 px por debajo, como los de Freedoom) y los que flotan quedan en el
aire como las esferas de Freedoom (el amuleto, 8 px; la capa, anclada a su capucha, unos 5-8 px).
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdf  # noqa: E402
from sdf import (V, rot_x, rot_y, rot_z, rad, Frame, Prim,  # noqa: E402
                 Sphere, Ellipsoid, RoundCone, CappedCone, EllCone, Box, Ring, Group, vnoise,
                 Render, finish, apply_shine)

OUTLINE = 2                      # (23,15,7): casi negro cálido, el contorno de todo PESADILLA
LIFT = 14.0                      # el modelo se sube esto antes de trazar (nada cae por debajo del lienzo)
PAD = 8                          # margen del lienzo para los halos 2D
OFFSETS_JSON = 'offsets_poderes.json'

# ----------------------------------------------------------------------------- materiales y rampas
(HIERRO, OXIDO, PLATA, AZABACHE, AZ_VERDE, CUERO, COSTURA, CUERNO, TAPON, CORDON, CORDON2, VINO,
 HULE, GOMA, HUECO, BOTON, PERG, PERG_OSC, TINTA, HUESO, HUESO_OSC, CUENCA, NIEBLA, OJO, ACEITE,
 MECHA, LACRE) = range(27)
CINTA = 40                       # + 0 azul, 1 rojo, 2 amarillo; + 3 el mismo color encendido (fotograma B)
GEMA = 50                        # ídem para las gemas de las llaves de hueso
CALAV = 60                       # ídem para la calavera teñida del color de las llaves de hueso
COLORES = ('azul', 'rojo', 'amarillo')

RAMPS = {
    HIERRO: [5, 109, 106, 103, 99, 95, 90, 86],          # hierro viejo (grises neutros)
    OXIDO: [2, 79, 77, 75, 73, 70, 67],                   # herrumbre
    PLATA: [108, 104, 100, 96, 92, 88, 84, 81, 4],        # plata (el último, el brillo)
    AZABACHE: [0, 8, 7, 6, 5, 111, 108, 104, 97, 88, 80, 4],   # azabache: negro con brillo vítreo
    AZ_VERDE: [127, 126, 125, 124, 123, 122, 121, 119],  # el azabache teñido por su propia luz verde
    CUERO: [0, 8, 7, 2, 6, 1, 5, 110, 108, 105, 101, 96, 91, 86],  # cuero de la bota: NEGRO de pez, lustre gris claro
    COSTURA: [2, 79, 77, 143, 140, 137],                 # pespunte de la costura (cáñamo sucio)
    CUERNO: [2, 79, 77, 75, 73, 71, 69, 67, 65, 145, 144],   # boquilla de cuerno de buey (melado claro)
    TAPON: [189, 187, 185, 183, 181, 179, 176],          # tapón rojo
    CORDON: [191, 189, 187, 185, 183, 181, 179, 177],    # cordón rojo
    CORDON2: [79, 151, 149, 147, 145, 144],              # la otra hebra del cordón (crudo)
    VINO: [190, 188, 186, 184, 182, 180, 178, 176, 173, 170],   # vino tinto derramado (rojo vivo, brilla)
    HULE: [167, 166, 165, 164, 163, 162, 161, 160],      # hule encerado amarillo del chubasquero
    GOMA: [0, 7, 6, 5, 111, 109, 107, 104, 100],         # botas de goma negras
    HUECO: [0, 8, 7],                                     # el vacío de dentro
    BOTON: [2, 79, 237, 236, 75, 73],                    # botones de cuerno oscuro
    PERG: [151, 149, 147, 146, 145, 144, 128],           # pergamino
    PERG_OSC: [79, 77, 143, 141, 139, 137],              # el revés del pergamino (más oscuro)
    TINTA: [77, 75, 73, 235, 233, 221, 218, 216, 214, 212, 161, 160],  # tinta parda → encendida
    HUESO: [2, 149, 147, 145, 144, 129, 128, 87, 84],    # hueso marfil sucio
    HUESO_OSC: [2, 79, 151, 149, 147],                   # tallas y surcos del hueso
    CUENCA: [0, 8],
    NIEBLA: [106, 104, 102, 99, 96, 93, 90, 87, 84],     # tela de niebla (gris)
    OJO: [164, 162, 161, 160, 227, 225],                 # ojos de la capa (amarillo pálido)
    ACEITE: [0, 8, 2, 79],                               # aceite negro del candil
    MECHA: [2, 79, 77],
    LACRE: [46, 189, 187, 185, 183, 181, 179],           # sello de lacre del pergamino
}
RAMP_COLOR = {   # lazo y gemas: (normal, encendido)
    'azul': ([241, 206, 205, 204, 203, 202, 201, 200, 198], [204, 202, 200, 199, 198, 197, 196, 194, 193]),
    'rojo': ([46, 189, 187, 186, 185, 183, 181, 179, 177], [186, 184, 182, 180, 178, 176, 175, 173, 171]),
    'amarillo': ([79, 166, 165, 164, 163, 162, 161, 160, 231], [165, 164, 163, 162, 161, 160, 231, 229, 227]),
}
RAMP_CALAV = {   # calavera teñida (como de cristal del color): rampa larga, del fondo oscuro al reflejo
    'azul': ([242, 207, 205, 204, 203, 202, 201, 200, 199, 198, 196, 194],
             [206, 204, 202, 201, 200, 199, 198, 197, 196, 194, 193, 192]),
    'rojo': ([47, 191, 189, 187, 185, 183, 181, 179, 177, 175, 173, 171],
             [186, 184, 182, 180, 178, 177, 176, 175, 174, 172, 170, 169]),
    'amarillo': ([167, 166, 165, 164, 163, 163, 162, 162, 161, 161, 160, 228],
                 [164, 163, 162, 162, 161, 161, 160, 160, 229, 228, 227, 226]),
}
for _i, _c in enumerate(COLORES):
    RAMPS[CINTA + _i], RAMPS[CINTA + 3 + _i] = RAMP_COLOR[_c]
    RAMPS[GEMA + _i], RAMPS[GEMA + 3 + _i] = RAMP_COLOR[_c]
    RAMPS[CALAV + _i], RAMPS[CALAV + 3 + _i] = RAMP_CALAV[_c]

# ganancia y desplazamiento de la intensidad por material; brillo especular (fuerza, exponente)
GAIN = {HIERRO: (0.8, 0.0), OXIDO: (0.85, 0.0), PLATA: (0.95, 0.05), AZABACHE: (0.42, 0.0),
        CUERO: (0.5, 0.0), CUERNO: (0.95, 0.1), TAPON: (0.9, 0.0), CORDON: (0.95, 0.05), VINO: (0.7, 0.0),
        HULE: (0.95, 0.02), GOMA: (0.55, 0.0), PERG: (0.95, 0.05), HUESO: (0.95, 0.08), NIEBLA: (0.9, 0.1),
        LACRE: (0.9, 0.05)}
SHINE = ((HIERRO, 0.25, 14), (PLATA, 0.7, 10), (AZABACHE, 1.4, 22), (CUERO, 1.0, 60), (CUERNO, 0.3, 10),
         (VINO, 0.9, 26), (HULE, 0.38, 9), (GOMA, 0.6, 14), (HUESO, 0.25, 6), (TAPON, 0.2, 8),
         (LACRE, 0.5, 12))
for _i in range(6):
    GAIN[CINTA + _i] = (1.0, 0.05)
    GAIN[GEMA + _i] = (0.9, 0.15)
    GAIN[CALAV + _i] = (0.78, 0.0)
SHINE = (SHINE + tuple((CINTA + i, 0.25, 8) for i in range(6)) + tuple((GEMA + i, 1.0, 12) for i in range(6))
         + tuple((CALAV + i, 0.7, 18) for i in range(6)))
EMISSIVE = (TINTA, OJO, MECHA) + tuple(GEMA + i for i in range(6))

PAL = np.array(sdf.read_palette(sdf.IWAD), float)
R90 = rot_x(rad(90))             # para anillos que miran a la cámara (eje del anillo = z)


# ----------------------------------------------------------------------------- trazado común
def hook(P, mat, inten, nz, nr, spec, lvl, extras):
    """Gancho de materiales: lo propio del objeto (extras['pre'], en coordenadas del modelo),
    ganancia y brillos por material, y un último retoque (extras['post'])."""
    R = extras['R']
    Q = ((P - V(0, LIFT, 0)) @ R) / extras.get('escala', 1.0)   # coordenadas del modelo (suelo en y = 0)
    nl = nr @ R                                     # normales en el modelo
    if extras.get('pre'):
        extras['pre'](Q, mat, inten, nz, nl, spec, lvl, extras)
    for m, (g, o) in GAIN.items():
        s = mat == m
        if s.any():
            inten[s] = inten[s] * g + o
    apply_shine(mat, inten, spec, SHINE)
    if extras.get('post'):
        extras['post'](Q, mat, inten, nz, nl, spec, lvl, extras)


RENDERS = {}


def render_de(tilt):
    if tilt not in RENDERS:
        RENDERS[tilt] = Render(RAMPS, hook=hook, emissive=EMISSIVE, no_light=(HUECO, CUENCA, OJO, ACEITE),
                               level_mats=(TINTA,), tilt=math.radians(tilt))
    return RENDERS[tilt]


class Fn(Prim):
    """Primitiva a partir de una función de distancia cualquiera (con su esfera envolvente)."""

    def __init__(self, f, bc, br, mat):
        self.f, self.bc, self.br, self.mat = f, V(bc), br, mat

    def sdf(self, P):
        return self.f(P)


def a_mundo(R, q, escala=1.0):
    """Punto del modelo → mundo trazado (girado, escalado y subido)."""
    return escala * (R @ V(q)) + V(0, LIFT, 0)


def a_pantalla(R, tilt, q, img_shape, escala=1.0):
    """Punto del modelo → (x, y) en píxeles (continuos) del lienzo de trazar() (con su margen)."""
    p = a_mundo(R, q, escala)
    t = math.radians(tilt)
    sx = p[0]
    sy = p[1] * math.cos(t) - p[2] * math.sin(t)
    H, W = img_shape[0] - 2 * PAD, img_shape[1] - 2 * PAD
    return W / 2 + sx + PAD, (H - 1) - sy + PAD


ULTIMO = {}     # lo que deja trazar() para colocar(): eje, fila del suelo del modelo y silueta sólida


def trazar(groups, extras, tilt, R=None, escala=1.0):
    """Modelo → lienzo RGBA (numpy) con margen PAD alrededor. R: giro del modelo; escala: tamaño."""
    R = np.eye(3) if R is None else np.asarray(R, float)
    Rd = render_de(tilt)
    extras = dict(extras)
    extras['R'] = R
    extras['escala'] = escala
    extras['view'] = V(0, math.sin(math.radians(tilt)), math.cos(math.radians(tilt))) @ R   # hacia la cámara
    for g in groups:
        g.xf = (escala * R, V(0, LIFT, 0), escala)
    out, depth = Rd.render(groups, extras, 0)
    img = np.array(finish(out, depth, Rd.palarr, OUTLINE))
    img[img[..., 3] < 128] = 0
    big = np.zeros((img.shape[0] + 2 * PAD, img.shape[1] + 2 * PAD, 4), np.uint8)
    big[PAD:-PAD, PAD:-PAD] = img
    ULTIMO.clear()
    ULTIMO['ax'], ULTIMO['oy'] = a_pantalla(R, tilt, (0, 0, 0), big.shape, escala)
    ULTIMO['solido'] = big[..., 3] > 0
    return big


def colocar(img, abajo=None, flota=None, origen=None):
    """Recorte ajustado y offsets [izq, sup] anclados al trazado SÓLIDO (sin halos ni llamas pintados
    encima), para que los fotogramas de un mismo objeto no salten:
    - izq: centro horizontal de la silueta sólida (con origen: el eje del modelo).
    - sup: la fila de abajo de la silueta sólida queda `abajo` px bajo el suelo, o `flota` px por encima;
      con origen, el suelo del modelo (y = 0) queda `origen` px por encima del suelo del juego."""
    vis = img[..., 3] >= 128
    img = img.copy()
    img[~vis] = 0
    ys, xs = np.nonzero(vis)
    y0, x0 = ys.min(), xs.min()
    a = img[y0:ys.max() + 1, x0:xs.max() + 1]
    sol = ULTIMO['solido']
    sy, sx = np.nonzero(sol)
    if origen is not None:
        izq = ULTIMO['ax'] - x0
        sup = ULTIMO['oy'] - y0 + origen
    else:
        izq = (sx.min() + sx.max() + 1) / 2 - x0
        fondo = sy.max() + 1 - y0                  # filas por encima del borde de abajo del sólido
        sup = fondo - abajo if flota is None else fondo + flota
    return Image.fromarray(a, 'RGBA'), [int(math.floor(izq)), int(round(sup))]


def pintar(img, mask, ramp, nivel, solo_vacio=True):
    """Pinta en img los píxeles de mask con ramp[nivel] (nivel: array de índices)."""
    m = mask & (img[..., 3] == 0) if solo_vacio else mask.copy()
    rr = np.array(ramp)
    img[m, :3] = PAL[rr[np.clip(nivel[m], 0, len(ramp) - 1)]].astype(np.uint8)
    img[m, 3] = 255
    return m


def es_color(img, idxs):
    """Máscara de los píxeles opacos de img que tienen alguno de los colores de PLAYPAL idxs."""
    a = img[..., :3].astype(int)
    m = np.zeros(img.shape[:2], bool)
    for i in idxs:
        m |= np.all(a == PAL[i].astype(int), axis=2)
    return m & (img[..., 3] > 0)


def fbm2(x, y, scale, seed):
    P = np.column_stack([np.ravel(x), np.ravel(y), np.full(np.size(x), 0.61 + seed)])
    n = vnoise(P, scale, seed) * 0.6 + vnoise(P, scale * 2.1, seed + 1) * 0.3 + vnoise(P, scale * 4.3, seed + 2) * 0.1
    return n.reshape(np.shape(x))


def dist_mask(mask, maxd=12):
    """Distancia aproximada (px; octogonal) de cada píxel a la máscara."""
    d = np.full(mask.shape, 99.0)
    d[mask] = 0
    cur = mask.copy()
    for k in range(1, maxd + 1):
        grow = cur.copy()
        grow[1:] |= cur[:-1]
        grow[:-1] |= cur[1:]
        grow[:, 1:] |= cur[:, :-1]
        grow[:, :-1] |= cur[:, 1:]
        if k % 2 == 0:
            grow[1:, 1:] |= cur[:-1, :-1]
            grow[:-1, :-1] |= cur[1:, 1:]
            grow[1:, :-1] |= cur[:-1, 1:]
            grow[:-1, 1:] |= cur[1:, :-1]
        d[grow & ~cur] = k
        cur = grow
    return d


BAYER4 = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + 0.5) / 16.0


def bayer(shape, dx=0, dy=0):
    H, W = shape
    yy, xx = np.mgrid[0:H, 0:W]
    return BAYER4[(yy + dy) % 4, (xx + dx) % 4]


def resplandor(img, ramp, src, radio, seed=3, fuerza=1.0):
    """Halo de la rampa (oscuro → claro) alrededor de la máscara src: más denso cerca, tramado lejos."""
    d = dist_mask(src, int(radio) + 2)
    H, W = src.shape
    yy, xx = np.mgrid[0:H, 0:W]
    n = fbm2(xx * 1.0, yy * 1.0, 0.45, seed)
    g = (1 - d / (radio + 1.0)) * (0.7 + 0.6 * n) * fuerza
    halo = (d > 0) & (g > 0.18) & (img[..., 3] == 0)
    halo &= (g > 0.5) | (bayer(src.shape) < g * 1.3)
    n_r = len(ramp)
    lv = np.clip((g * n_r).astype(int), 0, n_r - 1)
    return pintar(img, halo, ramp, lv)


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


# ============================================================================= LLAVES de hierro
CANA = 4.5          # lo que se acortó la caña de las llaves (unidades del modelo) para que no se vean tan altas


def llave_hierro(color, encendida):
    cin = CINTA + COLORES.index(color) + (3 if encendida else 0)
    d = CANA
    hierro = [
        Ring(Frame((0, 20.6 - d, 0), R90), 3.3, 3.6, 1.05, HIERRO),       # el ojo: anillo grande
        Sphere((0, 16.6 - d, 0), 1.45, HIERRO),                            # nudo bajo el ojo
        Ring(Frame((0, 15.3 - d, 0)), 1.3, 1.3, 0.6, HIERRO),
        RoundCone((0, 2.0, 0), (0, 16.0 - d, 0), 1.2, 1.1, HIERRO),      # caña
        Sphere((0, 1.5, 0), 1.5, HIERRO),                                  # punta
        Box((3.3, 3.7, 0), (2.4, 2.9, 0.8), rnd=0.2, mat=HIERRO),          # paletón
    ]
    muescas = [Box((5.5, 2.3, 0), (1.05, 0.62, 1.3)), Box((5.5, 5.1, 0), (1.05, 0.62, 1.3)),
               Box((3.3, 3.7, 0), (0.45, 1.05, 1.3))]

    def cut(Q):
        return -np.minimum.reduce([b.sdf(Q) for b in muescas])
    g_hierro = Group(hierro, k=0.35, cut=cut)
    # el lazo del color: nudo, dos lazadas hacia arriba y dos caídas abiertas, atado bajo el ojo
    lazo = [Ellipsoid((0, 16.7 - d, 1.45), (1.6, 1.4, 1.1), mat=cin)]
    for s in (-1, 1):
        lazo.append(Ellipsoid((s * 3.3, 17.7 - d, 1.0), (3.0, 1.65, 0.8), rot_z(rad(s * 26)) @ rot_y(rad(s * 15)), cin))
        lazo.append(Box((s * 2.0, 14.1 - d, 1.2), (0.95, 2.3, 0.3), rot_z(rad(s * 24)) @ rot_y(rad(s * 15)), 0.15, cin))
    g_lazo = Group(lazo, k=0.4)

    def pre(Q, mat, inten, nz, nr, spec, lvl, ex):
        m = np.nonzero(mat == HIERRO)[0]
        rust = vnoise(Q[m], 0.55, 31) > 0.64                     # herrumbre a manchas
        mat[m[rust]] = OXIDO
        inten[m] *= 0.85 + 0.3 * vnoise(Q[m], 1.7, 32)         # hierro picado
        c = mat == cin                                           # pliegues de la cinta
        inten[c] *= 0.8 + 0.32 * np.sin(Q[c, 0] * 2.2 + Q[c, 1] * 1.3) ** 2
    img = trazar([g_hierro, g_lazo], {'pre': pre}, 12, rot_y(rad(-18)))
    if encendida:
        src = es_color(img, RAMP_COLOR[color][1][4:])
        resplandor(img, RAMP_COLOR[color][1][1:6], src, 2.4, seed=COLORES.index(color))
    return colocar(img, abajo=2)


# ============================================================================= LLAVES de hueso
def llave_hueso(color, encendida):
    """Llave de hueso tallado cuyo ojo es una CALAVERA TEÑIDA del color (como de cristal: brilla), con
    chispas claras al fondo de las cuencas; cuelga de una anilla de cordón del mismo color. La caña y el
    paletón siguen siendo de hueso. La de hierro lleva el ojo de hierro y un lazo atado debajo: así se
    distinguen por la silueta y por dónde está el color (aquí, toda la cabeza)."""
    ci = COLORES.index(color) + (3 if encendida else 0)
    cal = CALAV + ci
    K_ = 1.2                                             # la calavera, exagerada (que se lea de lejos)
    d = 1.8                                              # caña algo más corta (unidades del modelo, escala 0.9)
    Sk = Frame((0, 16.4 - d, 0), rot_x(rad(-12)) * K_)
    p, M = Sk.p, rot_x(rad(-12))

    def r(*v):
        return tuple(x * K_ for x in v)
    craneo = [
        Ellipsoid(p((0, 2.2, -0.6)), r(4.4, 3.7, 3.9), M, cal),         # bóveda
        Ellipsoid(p((0, 0.5, 1.0)), r(3.9, 2.6, 3.0), M, cal),          # frente y órbitas
        Ellipsoid(p((2.5, -1.0, 1.8)), r(1.1, 1.0, 1.3), M, cal),       # pómulos
        Ellipsoid(p((-2.5, -1.0, 1.8)), r(1.1, 1.0, 1.3), M, cal),
        Ellipsoid(p((0, -2.1, 1.4)), r(2.1, 1.4, 1.9), M, cal),         # maxilar y dientes
        Ellipsoid(p((0, -3.3, 0.9)), r(1.8, 1.0, 1.6), M, cal),         # mandíbula
        Sphere(p((0, 4.9, -0.6)), 1.0 * K_, cal),                       # base de la argolla
    ]
    huecos = [Ellipsoid(p((1.7, -0.1, 3.3)), r(1.7, 1.55, 1.75), M, CUENCA),
              Ellipsoid(p((-1.7, -0.1, 3.3)), r(1.7, 1.55, 1.75), M, CUENCA),
              Ellipsoid(p((0, -1.75, 3.4)), r(0.65, 0.8, 1.0), M, CUENCA)]

    def cut_cr(Q):
        return -np.minimum.reduce([h.sdf(Q) for h in huecos])
    g_cr = Group(craneo, k=0.7, cut=cut_cr)
    fondo = Group([Ellipsoid(p((1.6, -0.1, 1.9)), r(1.4, 1.3, 0.8), M, CUENCA),
                   Ellipsoid(p((-1.6, -0.1, 1.9)), r(1.4, 1.3, 0.8), M, CUENCA)])
    chispa = GEMA + COLORES.index(color) + 3             # el fondo de las cuencas, siempre del color encendido
    gemas = Group([Sphere(p((1.5, -0.25, 2.3)), 0.36 * K_, chispa), Sphere(p((-1.5, -0.25, 2.3)), 0.36 * K_, chispa)])
    cana_top = 12.6 - d
    hueso = [
        RoundCone((0, 1.8, 0), (0, cana_top, 0), 1.15, 1.05, HUESO),     # caña
        Sphere((0, 1.4, 0), 1.35, HUESO),
        Ellipsoid((0, 6.6, 0), (1.5, 0.9, 1.5), mat=HUESO),              # nudo tallado (vértebra)
        Ring(Frame((0, cana_top - 1.0, 0)), 1.35, 1.35, 0.6, HUESO),     # collar bajo la calavera
        Box((2.6, 2.7, 0), (2.0, 2.0, 0.75), rnd=0.3, mat=HUESO),        # paletón
    ]
    muescas = [Box((3.4, 2.8, 0), (0.5, 0.75, 1.2)), Box((4.7, 1.3, 0), (0.6, 0.55, 1.2))]

    def cut_h(Q):
        return -np.minimum.reduce([b.sdf(Q) for b in muescas])
    g_h = Group(hueso, k=0.5, cut=cut_h)
    # una argolla pequeña tallada en la coronilla (sin cordón: que la silueta sea la de una calavera)
    top = Sk.p((0, 5.5, -0.6))
    g_an = Group([Ring(Frame(top + V(0, 0.9, -0.1), R90), 1.35, 1.5, 0.6, cal)])

    def pre(Q, mat, inten, nz, nr, spec, lvl, ex):
        h = np.nonzero(mat == HUESO)[0]
        inten[h] *= 0.85 + 0.25 * vnoise(Q[h], 0.9, 41)
        q = Q[h]
        grooves = (q[:, 1] < cana_top - 1.2) & (q[:, 1] > 2.6) & (np.abs(np.sin(q[:, 1] * 2.4)) < 0.16)   # tallas
        mat[h[grooves]] = HUESO_OSC
        k = np.nonzero(mat == cal)[0]                    # la calavera: dientes y boca marcados en oscuro
        inten[k] *= 0.88 + 0.22 * vnoise(Q[k], 0.9, 43)
        qs = Sk.to_local(Q[k]) / K_ ** 2
        teeth = (qs[:, 1] < -2.1) & (qs[:, 1] > -3.2) & (qs[:, 2] > 2.0) & (np.abs(np.sin(qs[:, 0] * 2.9 + 0.2)) < 0.3)
        mouth = (np.abs(qs[:, 1] + 2.9) < 0.25) & (qs[:, 2] > 1.8) & (np.abs(qs[:, 0]) < 1.9)
        inten[k[teeth | mouth]] *= 0.35
    img = trazar([g_cr, fondo, gemas, g_h, g_an], {'pre': pre}, 12, rot_y(rad(-12)), escala=0.9)
    if encendida:
        src = es_color(img, RAMP_CALAV[color][1][6:])
        resplandor(img, RAMP_COLOR[color][1][1:6], src, 2.2, seed=10 + COLORES.index(color), fuerza=0.9)
    return colocar(img, abajo=1)


# ============================================================================= PINV: amuleto de azabache
PINV_FASE = {'A': (2.6, 0.0, 0.75), 'B': (3.6, 0.8, 0.9), 'C': (4.6, 1.6, 1.1), 'D': (3.6, 2.4, 0.9)}


def amuleto(fr):
    radio, fase, pulso = PINV_FASE[fr]
    C = V(0, 12.0, 0)
    piedra = [Ellipsoid(C + V(0, 0, 0.4), (5.4, 6.8, 3.6), mat=AZABACHE)]
    plata = [Ring(Frame(C + V(0, 0, -0.5), R90), 6.1, 7.5, 1.0, PLATA)]
    for k in range(14):                                     # granulado de plata alrededor del bisel
        a = 2 * math.pi * k / 14
        plata.append(Sphere(C + V(7.25 * math.cos(a), 8.7 * math.sin(a), -0.4), 0.8, PLATA))
    for a in (45, 135, 225, 315):                           # garras que sujetan la piedra
        a = rad(a)
        plata.append(Ellipsoid(C + V(4.7 * math.cos(a), 5.9 * math.sin(a), 1.6), (0.9, 0.9, 0.7), mat=PLATA))
    plata += [Ellipsoid(C + V(0, 9.4, -0.3), (1.9, 1.5, 1.3), mat=PLATA),        # asa
              Ring(Frame(C + V(0, 11.6, -0.3), R90), 1.7, 1.7, 0.62, PLATA),
              Sphere(C + V(0, -9.6, -0.3), 1.2, PLATA), Sphere(C + V(0, -11.0, -0.3), 0.7, PLATA)]
    R = rot_y(rad(16)) @ rot_x(rad(-8))

    def pre(Q, mat, inten, nz, nr, spec, lvl, ex):
        j = np.nonzero(mat == AZABACHE)[0]
        vv = ex['view_l']
        fres = 1 - np.abs(nr[j] @ vv)
        verde = (fres > 0.5 - 0.08 * pulso) & (nr[j, 0] - nr[j, 1] > 0.1)   # el borde de abajo a la dcha. refleja la luz verde
        mat[j[verde]] = AZ_VERDE
        inten[j[verde]] = np.clip((fres[verde] - 0.4) * 1.6 * pulso, 0, 0.99)

    ex = {'pre': pre, 'view_l': V(0, math.sin(rad(12)), math.cos(rad(12))) @ R}
    img = trazar([Group(piedra), Group(plata, k=0.3)], ex, 12, R, escala=0.9)
    # brillo vítreo: el reflejo de una ventana arriba a la izquierda de la piedra (2-3 píxeles)
    gx, gy = a_pantalla(R, 12, C + V(-2.4, 2.9, 3.0), img.shape, 0.9)
    for dx, dy, c in ((0, 0, 4), (1, 0, 84), (-1, 1, 93)):
        x, y = int(gx) + dx, int(gy) + dy
        if img[y, x, 3] and img[y, x, :3].sum() < 120:
            img[y, x, :3] = PAL[c]
    # halo verde-blanco que late: rayos suaves alrededor de la silueta
    sil = img[..., 3] > 0
    H, W = sil.shape
    cx, cy = a_pantalla(R, 12, C, img.shape, 0.9)
    yy, xx = np.mgrid[0:H, 0:W]
    th = np.arctan2(yy - cy, xx - cx)
    rayos = fbm2(np.cos(th + fase) * 2.2, np.sin(th + fase) * 2.2, 1.0, 71)
    d = dist_mask(sil, int(radio) + 4)
    g = (1 - d / (radio * (0.75 + 0.7 * rayos) + 1.0))
    halo = (d > 0) & (g > 0) & ((g > 0.45) | (bayer(sil.shape, int(fase * 2)) < g * 1.6))
    VERDE = [123, 121, 119, 117, 115, 113, 112]
    lv = np.clip((g * len(VERDE) * pulso).astype(int), 0, len(VERDE) - 1)
    pintar(img, halo, VERDE, lv)
    # el contorno pegado al halo más vivo se vuelve verde oscuro (la luz sale del amuleto)
    borde = es_color(img, [OUTLINE])
    vivo = np.zeros_like(sil)
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        vivo |= np.roll(np.roll(halo & (lv >= 4), dy, 0), dx, 1)
    pintar(img, borde & vivo, [124], np.zeros_like(lv), solo_vacio=False)
    # chispas blancas sueltas
    rng = np.random.default_rng(80 + ord(fr))
    for _ in range(3 + int(pulso * 2)):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(7.5, 9.5 + radio)
        px, py = int(cx + math.cos(a) * r), int(cy + math.sin(a) * r * 1.15)
        if 0 <= px < W and 0 <= py < H and img[py, px, 3] == 0:
            img[py, px, :3] = PAL[80 if rng.uniform() < 0.5 else 112]
            img[py, px, 3] = 255
    return colocar(img, flota=8)



# ============================================================================= PSTR: bota de vino
def bota():
    """La bota NEGRA (de pez), TUMBADA en horizontal: el vientre a la izquierda, el cuello, la boquilla de
    cuerno claro y el tapón rojo a la derecha; el cordón rojo hace un lazo por encima, del cuello al culo,
    y bajo la boquilla se ha hecho un charco de vino. Negra, apaisada y con mucho rojo, para que no se
    confunda con el zurrón y la bolsita de la munición (cuero pardo claro, de pie)."""
    Rb = rot_z(rad(7)) @ rot_x(rad(-48))                  # la cara mira arriba y a la cámara; el cuello, algo alzado
    RB, GZ = 6.0, 1.8                                     # radio del vientre; aplastado de la bota (canto)
    h = math.sqrt((Rb[1, 0] * RB) ** 2 + (Rb[1, 1] * RB) ** 2 + (Rb[1, 2] * RB / GZ) ** 2) - (Rb @ V(-3.4, 0, 0))[1]
    B = Frame((-0.6, h, 0), Rb)                           # el vientre toca el suelo
    p, M = B.p, B.M()
    RX = M @ rot_z(rad(-90))                               # anillos alrededor del eje largo (x de la bota)
    gota = RoundCone((-3.4, 0, 0), (9.4, 0.3, 0), RB, 1.35, CUERO)   # la gota: vientre redondo y cuello

    def f_gota(P):
        q = B.to_local(P)
        q[:, 2] *= GZ
        return gota.sdf(q) / GZ
    cuerpo = [Fn(f_gota, p((2.4, 0, 0)), 12.5, CUERO)]
    boca = [CappedCone(p((9.2, 0.3, 0)), p((13.0, 0.35, 0)), 1.5, 1.05, CUERNO),     # boquilla de cuerno
            Ellipsoid(p((9.6, 0.3, 0)), (0.6, 1.85, 1.85), M, CUERNO),               # su reborde
            CappedCone(p((12.8, 0.35, 0)), p((14.8, 0.4, 0)), 1.45, 1.25, TAPON),   # tapón
            Sphere(p((14.7, 0.4, 0)), 1.2, TAPON)]
    atado = [Ring(Frame(p((8.4, 0.28, 0)), RX), 1.6, 1.6, 0.6, CORDON),
             Ring(Frame(p((-9.6, 0.0, 0)), RX), 1.1, 1.1, 0.55, CORDON)]
    # el cordón: atado al cuello, hace un lazo por encima (separado del cuero) y se anuda al culo de la bota
    camino = [(8.2, 1.4, -0.2), (6.4, 5.4, -0.4), (1.6, 8.8, -0.6), (-4.2, 9.2, -0.6), (-8.8, 6.6, -0.4),
              (-10.8, 2.4, -0.2), (-9.8, 0.2, 0)]
    cord = [RoundCone(p(a), p(b), 0.58, 0.58, CORDON) for a, b in zip(camino[:-1], camino[1:])]
    cord += [RoundCone(p((-10.0, -0.3, 0.3)), p((-12.0, -3.4, 0.5)), 0.62, 0.5, CORDON),   # la borla del nudo
             RoundCone(p((-9.8, -0.5, 0.5)), p((-10.4, -4.2, 0.8)), 0.62, 0.5, CORDON)]
    tip = B.p((14.6, 0.4, 0))
    cv = V(tip[0] - 1.6, 0.0, tip[2] + 3.2)                # el charco, bajo la boquilla y hacia delante

    def f_vino(P):
        dx, dz = (P[:, 0] - cv[0]) / 7.2, (P[:, 2] - cv[2]) / 4.4
        r = np.sqrt(dx * dx + dz * dz)
        th = np.arctan2(dz, dx)
        borde = 1 + 0.16 * np.sin(th * 3 + 0.7) + 0.1 * np.sin(th * 5 + 2.1)    # orilla irregular
        d2 = (r - borde) * 4.4
        return np.maximum(d2, np.abs(P[:, 1]) - 0.45)
    vino = [Fn(f_vino, cv, 9.5, VINO),
            Ellipsoid((tip[0] + 5.6, 0.0, tip[2] + 8.4), (1.3, 0.35, 0.9), mat=VINO),
            Ellipsoid((tip[0] - 7.4, 0.0, tip[2] + 7.0), (1.0, 0.32, 0.7), mat=VINO)]

    def pre(Q, mat, inten, nz, nr, spec, lvl, ex):
        c = np.nonzero(mat == CUERO)[0]
        q = B.to_local(Q[c])
        # costura del canto: las dos piezas de cuero se cosen por todo el borde (pespunte de cáñamo)
        canto = (np.abs(q[:, 2]) < 1.1) & (q[:, 0] < 7.0)
        punto = np.sin(np.arctan2(q[:, 1], q[:, 0] + 1.0) * 20) > 0.1
        mat[c[canto & punto]] = COSTURA
        inten[c] *= 0.85 + 0.3 * vnoise(q, 0.7, 51)         # cuero arrugado y gastado
        # lustre de la pez: una media luna clara en el hombro de arriba a la izquierda (no un brillo plano)
        nb = nr[c] @ M
        phi = np.arctan2(nb[:, 1], nb[:, 0])
        luna = np.exp(-((nb[:, 2] - 0.72) / 0.16) ** 2) * np.clip(np.cos(phi - rad(125)), 0, 1) ** 1.5
        inten[c] += 1.5 * luna
        spec[c] *= 0.35
        k = np.nonzero(mat == CORDON)[0]
        ql = B.to_local(Q[k])
        tw = np.sin((ql[:, 0] + ql[:, 1]) * 2.4) > 0.6       # hebras retorcidas
        inten[k[tw]] *= 0.6
        v_ = np.nonzero(mat == VINO)[0]                      # el charco: más oscuro al borde, brillos mojados
        qv = Q[v_]
        inten[v_] *= 0.75 + 0.35 * vnoise(qv, 0.8, 57)
        inten[v_] += 0.55 * (vnoise(qv, 0.55, 58) > 0.66)
        h_ = np.nonzero(mat == CUERNO)[0]                    # vetas del cuerno
        qh = B.to_local(Q[h_])
        inten[h_] *= 0.8 + 0.3 * np.sin(qh[:, 0] * 3.1 + 0.6 * qh[:, 1]) ** 2
    img = trazar([Group(cuerpo, k=2.4), Group(boca, k=0.25), Group(atado, k=0.2), Group(cord, k=0.3),
                  Group(vino, k=0.8)], {'pre': pre}, 26, rot_y(rad(-10)))
    return colocar(img, abajo=1)


# ============================================================================= PINS: capa de niebla
PINS_FASE = {'A': (0.0, 1.0), 'B': (90.0, 0.5), 'C': (180.0, 0.0), 'D': (270.0, 0.5)}


def capa(fr):
    fase, ojos = PINS_FASE[fr]
    ph = rad(fase)
    tw = rad(34) * math.sin(ph)
    sway = 2.6 * math.cos(ph)

    def warp(P):
        y = P[:, 1]
        t = np.clip((21.0 - y) / 16.0, 0, 1.3)
        a = tw * t
        c, s = np.cos(a), np.sin(a)
        x = P[:, 0] - sway * t * t + 0.8 * np.sin(y * 0.5 + ph) * t
        return np.column_stack([c * x + s * P[:, 2], y, -s * x + c * P[:, 2]])

    capucha = Ellipsoid((0, 23.5, -0.4), (5.2, 6.0, 5.4), mat=NIEBLA)
    cara = Ellipsoid((0, 22.6, 1.0), (3.3, 3.7, 9.0), mat=NIEBLA)
    cono = EllCone(Frame((0, 2.0, -0.6)), 19.5, (9.8, 7.6), (4.4, 4.0), NIEBLA)

    def tela(P):
        Q = warp(P)
        dh = np.abs(capucha.sdf(Q)) - 0.55
        dh = np.maximum(dh, -np.maximum(cara.sdf(Q), -(Q[:, 2] - 0.4)))   # el hueco de la cara
        dc = np.abs(cono.sdf(Q)) - 0.55
        # la capa se abre por delante, cada vez más hacia abajo
        abre = np.maximum(np.maximum(-(Q[:, 2] - 0.5), np.abs(Q[:, 0]) - np.clip((19.0 - Q[:, 1]) * 0.3, 0, 9)),
                          Q[:, 1] - 19.0)
        dc = np.maximum(dc, -abre)
        # jirones largos en el borde de abajo
        ang = np.arctan2(Q[:, 0], Q[:, 2])
        jir = 3.0 + 6.5 * fbm2(np.cos(ang) * 2.5, np.sin(ang) * 2.5, 1.0, 61) + 1.6 * np.sin(ang * 5 + ph)
        dc = np.maximum(dc, jir - Q[:, 1])
        dc = np.maximum(dc, Q[:, 1] - 20.5)                 # sin la tapa de arriba del cono
        return smin(dc, dh, 1.2)

    def fondo(P):
        return Ellipsoid((0, 23.0, -1.6), (4.0, 4.6, 3.6)).sdf(warp(P))

    groups = [Group([Fn(tela, (0, 13, 0), 16.5, NIEBLA)]), Group([Fn(fondo, (0, 23, -1.6), 5.0, HUECO)])]
    if ojos > 0:
        def ojo(P, s):
            return Ellipsoid((s * 1.5, 22.9, 2.7), (0.9, 1.05 * ojos, 0.6)).sdf(warp(P))
        groups.append(Group([Fn(lambda P: ojo(P, 1), (1.45, 22.9, 2.7), 1.3, OJO),
                             Fn(lambda P: ojo(P, -1), (-1.45, 22.9, 2.7), 1.3, OJO)]))

    def pre(Q, mat, inten, nz, nr, spec, lvl, ex):
        n = np.nonzero(mat == NIEBLA)[0]
        W = warp(Q[n])
        # el envés de la tela (lo que se ve por dentro) queda en sombra
        rad_ = np.column_stack([W[:, 0], np.zeros(len(n)), W[:, 2] + 0.6])
        dentro = np.einsum('ij,ij->i', nr[n], rad_) < 0
        inten[n[dentro]] *= 0.5
        inten[n] *= 0.8 + 0.35 * vnoise(W, 0.5, 62)
        o = mat == OJO
        inten[o] = 0.45 + 0.25 * ojos
    img = trazar(groups, {'pre': pre}, 12, rot_y(rad(10)), escala=1.12)
    # translucidez: tramado ordenado con densidad que baja hacia los jirones y los bordes
    vis = img[..., 3] > 0
    H, W = vis.shape
    ys, xs = np.nonzero(vis)
    y0, y1 = ys.min(), ys.max()
    yy, xx = np.mgrid[0:H, 0:W]
    t = (yy - y0) / max(1, y1 - y0)                       # 0 arriba, 1 abajo
    dborde = dist_mask(~vis, 4)
    n = fbm2(xx * 1.0, yy * 1.0 + fase * 0.05, 0.3, 63)
    dens = 0.92 - 0.62 * np.clip((t - 0.2) / 0.8, 0, 1) - 0.15 * (dborde <= 1) + 0.4 * (n - 0.5)
    fijo = es_color(img, RAMPS[HUECO] + RAMPS[OJO])
    quita = vis & ~fijo & (bayer(vis.shape, int(fase // 90), int(fase // 180)) > dens)
    img[quita] = 0
    # volutas de niebla sueltas alrededor de los jirones
    rng = np.random.default_rng(64 + ord(fr))
    for _ in range(10):
        x = int(rng.normal(W / 2, 6.0))
        y = int(y1 - rng.uniform(-2, 10))
        if 0 <= x < W and 0 <= y < H and img[y, x, 3] == 0:
            img[y, x, :3] = PAL[[99, 96, 93][rng.integers(3)]]
            img[y, x, 3] = 255
    return colocar(img, origen=5)


# ============================================================================= SUIT: chubasquero de marinero
def chubasquero():
    goma = []
    for s in (-1, 1):
        x = s * 3.0
        goma += [RoundCone((x, 1.6, -0.3), (x, 11.6, -0.2), 2.35, 2.45, GOMA),
                 Ellipsoid((x, 1.6, 1.5), (2.2, 1.6, 3.6), mat=GOMA),
                 Box((x, 0.45, 1.1), (2.35, 0.45, 3.7), rnd=0.3, mat=GOMA),
                 Ring(Frame((x, 11.7, -0.2)), 2.45, 2.45, 0.5, GOMA)]
    hule = [EllCone(Frame((0, 10.6, 0)), 29.0, (8.6, 6.0), (6.3, 4.1), HULE),
            Ellipsoid((0, 37.4, 0), (7.4, 3.8, 4.4), mat=HULE)]
    mangas = []
    for s in (-1, 1):
        mangas += [RoundCone((s * 7.0, 37.4, -0.2), (s * 8.7, 22.4, 0.8), 2.75, 2.45, HULE),
                   Ring(Frame((s * 8.72, 22.9, 0.8), rot_z(rad(-s * 6))), 2.35, 2.35, 0.45, HULE)]
    cuello = [CappedCone((0, 39.0, 0), (0, 43.4, 0.3), 3.4, 3.8, HULE)]
    copa = Ellipsoid((0, 46.4, -0.5), (3.9, 3.0, 4.1), mat=HULE)

    def ala(P):   # el ala del sueste: corta delante, ancha y caída por los lados y detrás
        e = Ellipsoid((0, 42.4, -1.3), (6.3, 3.1, 6.9)).sdf(P)
        d = np.abs(e) - 0.34
        d = np.maximum(d, P[:, 1] - 45.4)
        lim = 42.7 + np.clip(P[:, 2] - 0.8, 0, None) * 0.6
        return np.maximum(d, lim - P[:, 1])
    sombrero = [copa, Fn(ala, (0, 44, -1.3), 7.5, HULE)]
    huecos = [Ellipsoid((0, 43.2, 0.3), (3.0, 0.6, 3.0), mat=HUECO),           # el cuello, vacío
              Ellipsoid((0, 44.0, 0.5), (3.2, 1.0, 3.2), mat=HUECO)]           # nadie bajo el sueste
    for s in (-1, 1):
        huecos.append(Ellipsoid((s * 8.72, 22.1, 0.85), (1.8, 0.45, 1.8), mat=HUECO))   # mangas vacías
    botones = []
    for y in (16.0, 21.5, 27.0, 32.5):
        rz = 6.0 + (4.1 - 6.0) * (y - 10.6) / 29.0
        botones.append(Ellipsoid((0.6, y, rz + 0.05), (0.75, 0.55, 0.5), mat=BOTON))

    def pre(Q, mat, inten, nz, nr, spec, lvl, ex):
        h = np.nonzero(mat == HULE)[0]
        q = Q[h]
        ang = np.arctan2(q[:, 0], q[:, 2])
        falda = q[:, 1] < 36.5
        pl = np.sin(ang * 6.5 + 0.6 * np.sin(q[:, 1] * 0.25)) * np.clip((36.0 - q[:, 1]) / 20.0, 0, 1)
        inten[h] *= np.where(falda, 0.9 + 0.22 * pl, 1.0)
        inten[h] *= 0.86 + 0.24 * vnoise(q, 0.6, 81)                 # hule gastado, a manchas
        abertura = falda & (np.abs(q[:, 0]) < 0.38) & (q[:, 2] > 0)
        bolsillo = (np.abs(np.abs(q[:, 0]) - 4.2) < 1.6) & (np.abs(q[:, 1] - 20.5) < 0.3) & (q[:, 2] > 0)
        bajo = (np.abs(q[:, 1] - 11.2) < 0.45)                        # dobladillo
        mat[h[abertura | bolsillo]] = BOTON
        inten[h[bajo]] *= 0.6
        ala_ = (q[:, 1] < 45.3) & (q[:, 1] > 42.0) & (np.hypot(q[:, 0], q[:, 2] + 0.5) > 3.6)
        inten[h[ala_ & (nr[h, 1] < 0)]] *= 0.5                         # el revés del ala, en sombra
    groups = [Group(goma, k=0.4), Group(hule + cuello, k=1.6), Group(mangas, k=0.6),
              Group(sombrero, k=0.5, cut=lambda Q: np.where(Q[:, 1] > 45.2, -9.0, np.where(
                  np.hypot(Q[:, 0], Q[:, 2] + 0.5) < 3.6, 44.4 - Q[:, 1], -9.0))),
              Group(huecos), Group(botones)]
    img = trazar(groups, {'pre': pre}, 10, rot_y(rad(-14)))
    return colocar(img, abajo=0)


# ============================================================================= PMAP: pergamino del pueblo
PMAP_BRILLO = {'A': 0.0, 'B': 0.33, 'C': 0.66, 'D': 1.0}
PX0, PX1, PY1 = -9.0, 11.0, 15.0     # el pliego (coordenadas del papel): de la parte enrollada al borde
P_ROLLO = 2.4                         # radio del rollo


def plano_pueblo(u, v):
    """Dibujo del plano: (máscara de tinta, cuánto se enciende cada trazo) en el papel (u, v)."""
    cu = (PX0 + PX1) / 2 + 1.2
    hu, hv = (PX1 - PX0) / 2 - 1.2, (PY1 - 0.6) / 2
    cv = 0.6 + hv
    du, dv = np.abs(u - cu), np.abs(v - cv)
    marco = (np.maximum(du - (hu - 0.9), dv - (hv - 0.9)) > -0.3) & (du < hu - 0.6) & (dv < hv - 0.6)
    rio = np.abs(v - (3.2 + (u - PX0) * 0.2 + 1.4 * np.sin((u - PX0) * 0.55))) < 0.48
    PC = (2.2, 10.2)
    rp = np.hypot(u - PC[0], v - PC[1])
    plaza = np.abs(rp - 1.5) < 0.3
    calles = ((np.abs(v - PC[1] - (u - PC[0]) * 0.1) < 0.24) | (np.abs(u - PC[0] + (v - PC[1]) * 0.25) < 0.24)) & \
        (rp > 1.5) & (rp < 6.0)
    casas = np.zeros(len(u), bool)
    for hu_, hv_ in ((-0.7, 12.4), (5.0, 12.2), (5.2, 8.1), (-1.0, 8.0)):
        casas |= (np.abs(u - hu_) < 0.7) & (np.abs(v - hv_) < 0.55)
    camino = (np.abs(u - (8.2 - (v - 2.0) * 0.5)) < 0.24) & (v < 7.4) & (v > 2.0) & (np.sin(v * 2.6) > -0.2)
    tinta = np.zeros(len(u), bool)
    vivo = np.zeros(len(u))
    for m, w in ((marco, 0.45), (rio, 1.0), (plaza, 0.95), (calles, 0.8), (casas, 0.65), (camino, 0.7)):
        tinta |= m
        vivo = np.where(m, np.maximum(vivo, w), vivo)
    return tinta, vivo


def pergamino(fr):
    g = PMAP_BRILLO[fr]
    S = Frame((0, 0, 0), rot_x(rad(-26)))             # el papel, echado hacia atrás, apoyado en el suelo

    def curva(q):
        z = np.where(q[:, 0] > PX1 - 3.5, -(q[:, 0] - (PX1 - 3.5)) ** 2 * 0.16, 0.0)
        return z + np.where(q[:, 1] > PY1 - 2.5, -(q[:, 1] - (PY1 - 2.5)) ** 2 * 0.1, 0.0)

    def pliego(P):
        q = S.to_local(P)
        d2 = np.maximum(np.maximum(PX0 - q[:, 0], q[:, 0] - PX1), np.maximum(0.6 - q[:, 1], q[:, 1] - PY1))
        return np.maximum(np.abs(q[:, 2] - curva(q)) - 0.3, d2)
    rollo = [RoundCone(S.p((PX0, 0.4 + P_ROLLO * 0.3, -P_ROLLO + 0.3)), S.p((PX0, PY1 + 0.4, -P_ROLLO + 0.3)),
                       P_ROLLO, P_ROLLO, PERG)]
    sello = [Ellipsoid(S.p((PX1 - 3.6, 3.0, 0.35)), (1.55, 1.55, 0.45), S.M(), LACRE)]
    lazo = [Ring(S * Frame((PX0, 7.0, -P_ROLLO + 0.3)), P_ROLLO + 0.3, P_ROLLO + 0.3, 0.42, CORDON),
            RoundCone(S.p((PX0 + 0.8, 6.8, 0.5)), S.p((PX0 + 2.0, 2.6, 0.7)), 0.42, 0.42, CORDON),
            RoundCone(S.p((PX0 + 0.8, 6.8, 0.5)), S.p((PX0 + 3.0, 3.8, 0.9)), 0.42, 0.42, CORDON)]

    def pre(Q, mat, inten, nz, nr, spec, lvl, ex):
        p = np.nonzero(mat == PERG)[0]
        q = S.to_local(Q[p])
        nl = nr[p] @ S.R
        plano = q[:, 0] > PX0 + 0.3
        inten[p] *= 0.8 + 0.3 * vnoise(q, 0.45, 91)               # manchas
        borde = np.minimum(np.minimum(q[:, 0] - PX0, PX1 - q[:, 0]), np.minimum(q[:, 1], PY1 - q[:, 1]))
        inten[p[(borde < 0.9) & plano]] *= 0.62                    # bordes tostados
        reves = plano & (nl[:, 2] < 0)
        mat[p[reves]] = PERG_OSC
        tinta, vivo = plano_pueblo(q[:, 0], q[:, 1])
        tinta &= plano & ~reves
        mat[p[tinta]] = TINTA
        base = 0.4 + 1.4 * vnoise(q[tinta], 1.2, 92)
        lvl[p[tinta]] = np.clip(base + g * vivo[tinta] * 10.0, 0, len(RAMPS[TINTA]) - 1)
    groups = [Group([Fn(pliego, ((PX0 + PX1) / 2, PY1 / 2, -1.0), 14.0, PERG)] + rollo, k=0.4), Group(sello),
              Group(lazo, k=0.2)]
    img = trazar(groups, {'pre': pre}, 14, rot_y(rad(-16)), escala=1.15)
    if g > 0.5:     # la tinta encendida alumbra el pergamino de alrededor
        src = es_color(img, RAMPS[TINTA][8:])
        d = dist_mask(src, 2)
        cerca = (d == 1) & es_color(img, RAMPS[PERG][2:])
        pintar(img, cerca & (bayer(src.shape) < (g - 0.4)), [64, 61, 58, 56], np.full(src.shape, int(g * 3)),
               solo_vacio=False)
    return colocar(img, abajo=1)


# ============================================================================= PVIS: candil de hierro
def candil(fr):
    viva = fr == 'A'

    def plato(P):
        e = Ellipsoid((0, 3.0, 0), (5.6, 2.6, 5.2)).sdf(P)
        sp = RoundCone((3.0, 3.6, 0), (10.0, 4.8, 0), 2.4, 0.95, 0).sdf(P)
        d = smin(e, sp, 1.6)
        ei = Ellipsoid((0, 3.7, 0), (4.9, 2.1, 4.5)).sdf(P)
        si = RoundCone((3.0, 4.1, 0), (9.6, 5.15, 0), 1.7, 0.4, 0).sdf(P)
        d = np.maximum(d, -smin(ei, si, 1.6))
        return np.maximum(d, P[:, 1] - (5.1 + 0.1 * np.clip(P[:, 0], 0, None)))
    hierro = [Fn(plato, (2.5, 3.6, 0), 9.0, HIERRO),
              Ring(Frame((0, 0.7, 0)), 2.6, 2.6, 0.6, HIERRO),                       # pie
              RoundCone((-5.3, 4.4, 0), (-5.7, 12.0, 0), 0.72, 0.62, HIERRO),        # varilla
              RoundCone((-5.7, 12.0, 0), (-5.2, 14.0, 0), 0.6, 0.58, HIERRO),        # el garabato
              RoundCone((-5.2, 14.0, 0), (-3.6, 14.8, 0), 0.58, 0.52, HIERRO),
              RoundCone((-3.6, 14.8, 0), (-2.2, 14.2, 0), 0.52, 0.48, HIERRO),
              RoundCone((-2.2, 14.2, 0), (-1.9, 13.0, 0), 0.48, 0.42, HIERRO),
              RoundCone((-5.7, 12.0, 0), (-8.3, 12.9, 0), 0.55, 0.18, HIERRO)]       # el pincho
    for y in (6.6, 8.1, 9.6, 11.1):                                                  # cremallera
        hierro.append(Box((-6.0, y, 0), (0.55, 0.3, 0.5), rot_z(rad(-30)), 0.1, HIERRO))
    aceite = [Ellipsoid((0, 4.3, 0), (4.7, 0.25, 4.3), mat=ACEITE)]
    mecha = [RoundCone((7.6, 4.95, 0), (10.1, 5.75, 0), 0.55, 0.5, MECHA)]
    R = rot_y(rad(-30))
    punta = V(10.35, 5.85, 0)
    ex = {}
    if viva:
        ex['flash_light'] = (a_mundo(R, punta + V(0, 3.0, 0)), 12.0)

    def pre(Q, mat, inten, nz, nr, spec, lvl, e):
        m = np.nonzero(mat == HIERRO)[0]
        rust = vnoise(Q[m], 0.6, 101) > 0.64
        mat[m[rust]] = OXIDO
        inten[m] *= 0.85 + 0.3 * vnoise(Q[m], 1.6, 102)
    ex['pre'] = pre
    img = trazar([Group(hierro, k=0.3), Group(aceite), Group(mecha)], ex, 24, R)
    # la llama (2D, colores exactos): gota que sube desde la punta de la mecha
    fx, fy = a_pantalla(R, 24, punta, img.shape)
    H, W = img.shape[:2]
    sub = 4
    jj, ii = np.meshgrid(np.arange(W * sub), np.arange(H * sub))
    x = (jj + 0.5) / sub - fx
    y = fy - (ii + 0.5) / sub                      # hacia arriba
    alto, ancho, sem = (10.0, 2.7, 111) if viva else (4.2, 1.5, 113)
    t = np.clip(y / alto, 0, 1)
    vaiv = (0.6 if viva else 1.4) * np.sin(t * 3.0 + (0.4 if viva else 2.0)) * t
    anch = ancho * np.sqrt(np.clip(np.sin(np.pi * np.clip(t * 0.85 + 0.15, 0, 1)), 0, 1)) * (1 - t) ** 0.4
    anch = np.where(y < 0, ancho * np.sqrt(np.clip(1 - (y / 1.3) ** 2, 0, 1)) * 0.8, anch)
    n = fbm2(x * 0.6, y * 0.35, 1.0, sem)
    calor = (1 - np.abs(x - vaiv) / np.maximum(anch, 1e-3)) * (1.2 - 0.8 * t) + 0.25 * (n - 0.5)
    calor = np.where((y > -1.3) & (y < alto) & (anch > 0.05), calor, 0)
    on = calor > 0.08
    cnt = on.reshape(H, sub, W, sub).sum(axis=(1, 3))
    hs = np.where(on, calor, 0).reshape(H, sub, W, sub).sum(axis=(1, 3))
    hm = np.where(cnt >= 5, hs / np.maximum(cnt, 1), 0)
    FUEGO = [186, 235, 233, 221, 217, 215, 214, 162, 161, 160, 227, 225] if viva else [186, 235, 233, 221, 217, 216]
    lv = np.clip((hm * len(FUEGO) * (1.05 if viva else 0.95)).astype(int), 0, len(FUEGO) - 1)
    fuego = hm > 0
    rr = np.array(FUEGO)
    img[fuego, :3] = PAL[rr[lv[fuego]]].astype(np.uint8)
    img[fuego, 3] = 255
    if viva:   # un resplandor tenue alrededor de la llama
        resplandor(img, [233, 221, 217, 214], fuego, 1.6, seed=114, fuerza=0.7)
    return colocar(img, abajo=1)


# ============================================================================= lista de lumps
def lumps():
    out = {}
    for fr in 'ABCD':
        out[f'PINV{fr}0'] = (amuleto, (fr,))
        out[f'PINS{fr}0'] = (capa, (fr,))
        out[f'PMAP{fr}0'] = (pergamino, (fr,))
    out['PSTRA0'] = (bota, ())
    out['SUITA0'] = (chubasquero, ())
    for fr in 'AB':
        out[f'PVIS{fr}0'] = (candil, (fr,))
    for pre, color in (('B', 'azul'), ('R', 'rojo'), ('Y', 'amarillo')):
        for fr in 'AB':
            out[f'{pre}KEY{fr}0'] = (llave_hierro, (color, fr == 'B'))
            out[f'{pre}SKU{fr}0'] = (llave_hueso, (color, fr == 'B'))
    return out


FILAS = [['PINVA0', 'PINVB0', 'PINVC0', 'PINVD0', 'PSTRA0', 'SUITA0'],
         ['PINSA0', 'PINSB0', 'PINSC0', 'PINSD0', 'PVISA0', 'PVISB0'],
         ['PMAPA0', 'PMAPB0', 'PMAPC0', 'PMAPD0'],
         ['BKEYA0', 'BKEYB0', 'RKEYA0', 'RKEYB0', 'YKEYA0', 'YKEYB0'],
         ['BSKUA0', 'BSKUB0', 'RSKUA0', 'RSKUB0', 'YSKUA0', 'YSKUB0']]


def freedoom(nombre):
    """Sprite de Freedoom y sus offsets (referencia para la hoja)."""
    sys.path.insert(0, os.path.join(sdf.RAIZ, 'tools', 'wad'))
    from doomgfx import read_wad, decode_patch
    if not hasattr(freedoom, 'lumps'):
        freedoom.lumps = dict(read_wad(sdf.IWAD)[1])
    return decode_patch(freedoom.lumps[nombre], [tuple(int(c) for c in p) for p in PAL])


def hoja(carpeta, ruta, offsets, escala=3):
    """Hoja de contactos: cada lump nuestro (izquierda) junto al de Freedoom (derecha), a la misma escala
    y apoyados en la misma línea de suelo (raya roja = suelo del objeto; marca = origen)."""
    cw, ch = 84 * escala, 74 * escala
    ncol = max(len(f) for f in FILAS)
    S = Image.new('RGB', (cw * ncol, ch * len(FILAS)), (70, 70, 78))
    d = ImageDraw.Draw(S)
    for r, fila in enumerate(FILAS):
        for c, n in enumerate(fila):
            x0, y0 = c * cw, r * ch
            suelo = y0 + ch - 14 * escala
            d.line([(x0 + 4, suelo), (x0 + cw - 4, suelo)], fill=(150, 40, 40))
            mio = Image.open(os.path.join(carpeta, n + '.png')).convert('RGBA')
            for k, (im, off) in enumerate(((mio, offsets.get(n)), freedoom(n))):
                if off is None:
                    continue
                big = im.resize((im.width * escala, im.height * escala), Image.NEAREST)
                ox = x0 + (cw * 3 // 10 if k == 0 else cw * 3 // 4)
                S.paste(big, (ox - off[0] * escala, suelo - off[1] * escala), big)
                d.line([(ox, suelo + 2), (ox, suelo + 8)], fill=(255, 80, 80))
            d.text((x0 + 3, y0 + 3), f'{n} {mio.width}x{mio.height}  (Freedoom a la dcha.)', fill=(240, 240, 240))
    S.save(ruta)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--salida', required=True, help='carpeta de PNG (arte/sprites)')
    ap.add_argument('--solo', default='', help='lumps separados por comas')
    ap.add_argument('--hoja', default='', help='ruta de la hoja de contactos (PNG)')
    args = ap.parse_args()
    os.makedirs(args.salida, exist_ok=True)
    todos = lumps()
    nombres = [n.strip().upper() for n in args.solo.split(',') if n.strip()] or list(todos)
    ruta_off = os.path.join(args.salida, OFFSETS_JSON)
    offsets = {}
    if os.path.exists(ruta_off):
        with open(ruta_off) as fh:
            offsets = json.load(fh)
    for n in nombres:
        fn, a = todos[n]
        im, off = fn(*a)
        im.save(os.path.join(args.salida, n + '.png'))
        offsets[n] = off
        print(f'{n} {im.width}x{im.height} offsets {off}', flush=True)
    with open(ruta_off, 'w') as fh:
        json.dump(dict(sorted(offsets.items())), fh, indent=1)
        fh.write('\n')
    if args.hoja:
        hoja(args.salida, args.hoja, offsets)


if __name__ == '__main__':
    main()
