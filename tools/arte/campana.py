#!/usr/bin/env python3
"""campana.py — LA CAMPANA DE VELILLA (sustituye a la BFG de Freedoom), dibujada por código.

Uso:
    ~/.venvs/pesadilla/bin/python tools/arte/campana.py --salida arte/sprites
    … --solo BFGGA0,BFS1A0        solo esos lumps
    … --vista <png>               además, pantallas simuladas del arma (con barra y sin ella)
    … --hoja <png>                además, hoja de contactos ampliada del toque y sus estallidos

La campana legendaria que tañía sola anunciando desgracias. Escribe:
- BFGGA0 (reposo y carga: en info.c A dura los 20 tics de la carga) y BFGGB0 (disparo: el badajo
  golpea el borde de arriba, la campana da un respingo hacia el jugador y la boca sube).
- BFGFA0-BFGFB0: el resplandor verde espectral que sale de la boca (a pleno brillo; se dibuja
  encima de BFGGB0): A, el golpe (anillo de onda que se despega del borde y la pátina encendida);
  B, la onda más ancha que se apaga.
- BFUGA0: la campana en el suelo (de pie, con la boca abajo y el yugo encima), para recogerla.
- BFS1A0-B0: «el toque» en vuelo: una esfera de ondas concéntricas verde pálido (a pleno brillo;
  A y B alternan la fase de las ondas, que parecen salir del centro).
- BFE1A0-F0: el gran estallido del toque: los anillos se abren (C es el fotograma del rayo) y se
  deshacen en jirones; BFE2A0-D0: el estallido pequeño sobre cada enemigo alcanzado por el rayo.
Y los desplazamientos de todos en <salida>/offsets_campana.json (arma1p.guardar_offsets).

El ARMA (motor común arma1p.py: misma proyección, luz, paleta y contorno que las demás armas): una
campana de bronce con pátina verdosa (cabeza, hombro con cordones, inscripción gastada en una
banda, medio, cordones del medio pie y boca acampanada), con una grieta que baja desde la boca;
colgada de un yugo de madera (como los de las campanas de los campanarios españoles) con cinchos de
hierro, pernos y los muñones de hierro en las puntas. El jugador la lleva con las dos manos (el
mismo guante de cuero y la manga de paño granate) agarrando las puntas del yugo, con la boca al
frente; dentro cuelga el badajo de hierro, que en el disparo golpea el borde de arriba y asoma.

El TOQUE y los ESTALLIDOS son 2D (como la bola de la Meiga o la traca del cohete), deterministas:
ondas concéntricas verde pálido y blanco con halo gris verdoso (más pálido y fantasmal que el verde
saturado de la Meiga y del Hombre del Saco), jirones con ruido de semilla fija.
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from arma1p import (RAMPAS, Agarre, Arma, caja, capsula, costuras, dibujar, elipsoide,  # noqa: E402
                    filo, guante, guardar, guardar_offsets, mano_agarre, matriz_canon, mover_pose,
                    pliegues_pano, proyectar, rot_x, rot_y, rot_z, smin, tubo, unit, v3)
import sdf  # noqa: E402

# ---------------------------------------------------------------------------------------------
# Paleta: rampas de colores EXACTOS de PLAYPAL (de oscuro a claro; índice 0 = línea de profundidad)
# ---------------------------------------------------------------------------------------------

_PAL = sdf.read_palette(sdf.IWAD)


def _pp(*idx):
    return [tuple(_PAL[i]) for i in idx]


RAMPAS_CAM = dict(
    RAMPAS,
    # bronce viejo: pardo oliváceo oscuro (239, 238, 237, 151..147: menos rojo que la madera y el
    # cuero) con el dorado del latón (164, 163) solo en los brillos del metal
    bronce=_pp(2, 239, 238, 237, 151, 150, 149, 148, 147, 164, 163),
    # pátina: gris verdoso (cardenillo apagado: 11, 10, 9, 159..152)
    patina=_pp(2, 11, 10, 9, 159, 158, 157, 156, 155, 154, 153, 152),
    # interior de la campana: bronce en sombra
    hueco=_pp(0, 2, 151, 150, 149),
    # yugo: roble viejo, curtido a la intemperie (pardo grisáceo: 79, 238, 143..135)
    madera=_pp(2, 79, 238, 78, 77, 76, 143, 141, 139, 137),
    # hierro negro de fragua (cinchos, pernos, muñones, badajo): 7, 6, 5, 111, 109, 107, 104, 102
    hierro=_pp(7, 6, 5, 111, 109, 107, 104, 102, 100),
    manga=RAMPAS['pano'],
)
MATS = ['bronce', 'patina', 'hueco', 'madera', 'hierro', 'cuero', 'ribete', 'manga']
BRILLO = {'bronce': (0.45, 22), 'patina': (0.05, 6), 'hueco': (0.0, 1), 'madera': (0.1, 10), 'hierro': (0.3, 20),
          'cuero': (0.12, 10), 'ribete': (0.1, 10), 'manga': (0.0, 1)}
GANANCIA = {'bronce': 0.62, 'patina': 0.7, 'hueco': 0.6, 'madera': 0.56, 'hierro': 0.7, 'cuero': 1.0, 'ribete': 0.62,
            'manga': 0.8}

# ---------------------------------------------------------------------------------------------
# El modelo (espacio del arma: eje de la campana en z, de la cabeza (z = 0) a la boca (z = H);
# y arriba, x a la derecha; el yugo queda detrás de la cabeza, z < 0)
# ---------------------------------------------------------------------------------------------

R = 15.0                       # radio de la boca (por fuera)
H = 23.0                       # de la cabeza a la boca
T_CABEZA = 1.6                 # grosor de la cabeza
CORDONES = ((0.07, 0.32, 0.30), (0.115, 0.26, 0.26), (0.30, 0.22, 0.24), (0.78, 0.30, 0.30), (0.83, 0.24, 0.26))
BANDA = (0.13, 0.28)           # banda de la inscripción (fracción de H)


def _perfil(s):
    """Radio exterior (sin cordones) en la fracción s = z / H."""
    s = np.clip(s, 0.0, 1.0)
    hombro = 0.09 * (1.0 - np.clip(s / 0.13, 0, 1)) ** 2     # el hombro se redondea hacia la cabeza
    return R * (0.50 + 0.17 * s - hombro + 0.33 * np.maximum(0.0, (s - 0.5) / 0.5) ** 2.2)


def r_ext(z):
    s = z / H
    r = _perfil(s)
    for (sc, a, w) in CORDONES:
        r = r + a * np.exp(-((s - sc) * H / w) ** 2)
    return r


def r_int(z):
    """Radio interior: el bronce es más grueso en el medio pie (donde golpea el badajo)."""
    s = np.clip(z / H, 0.0, 1.0)
    grueso = R * (0.065 + 0.075 * np.exp(-((s - 0.87) / 0.08) ** 2))
    return _perfil(s) - grueso


def _lado(P, f, z):
    rho = np.sqrt(P[:, 0] ** 2 + P[:, 1] ** 2)
    e = 0.05
    der = (f(z + e) - f(z - e)) / (2 * e)
    return (rho - f(z)) / np.sqrt(1.0 + der * der)


def campana(P):
    """→ (bronce, hueco): distancia al bronce y a la cara de dentro (para pintarla oscura)."""
    z = P[:, 2]
    zc = np.clip(z, -0.5, H + 0.5)
    fuera = np.maximum(np.maximum(_lado(P, r_ext, zc), -z), z - H)
    dentro = np.maximum(_lado(P, r_int, zc), T_CABEZA - z)
    # el labio de la boca: un bisel por dentro
    bronce = np.maximum(fuera, -dentro)
    return bronce, dentro


# --- el yugo (madera) y sus hierros -------------------------------------------------------------
YW = 12.5                      # medio largo del yugo (bloque)
YZ = (-7.0, -0.4)              # de atrás (hacia el jugador) a la cabeza de la campana
YY = (-4.0, 4.5)               # de abajo arriba (en el medio; arriba se arquea)
MANGO = (YW - 1.0, YW + 9.0)   # mangos redondos (x) donde agarran las manos
MANGO_R = 1.75
Y_MANGO = 0.6                  # altura del eje de los mangos
Z_MANGO = (YZ[0] + YZ[1]) / 2
CINCHOS = (-5.5, 5.5)          # cinchos de hierro que abrazan el yugo y la cabeza
ARCO = 2.6                     # cuánto se arquea el lomo del yugo


def yugo(P):
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    ax = np.abs(x)
    # bloque con el lomo arqueado y las puntas rebajadas en curva (como las cabezas de los yugos)
    arco = ARCO * (1.0 - np.clip(ax / YW, 0, 1) ** 2)
    baja = 3.0 * np.clip((ax - (YW - 5.0)) / 5.0, 0, 1) ** 1.5
    top = YY[1] + arco - baja
    bot = YY[0] + baja * 0.8
    yc = (top + bot) / 2
    hy = (top - bot) / 2
    q = np.stack([ax - YW, np.abs(y - yc) - hy, np.abs(z - (YZ[0] + YZ[1]) / 2) - (YZ[1] - YZ[0]) / 2], 1)
    q = q * np.array([1.0, 0.85, 1.0])
    rr = 0.7
    q = q + rr
    madera = np.sqrt((np.maximum(q, 0) ** 2).sum(1)) + np.minimum(q.max(1), 0) - rr
    # mangos redondos
    for sx in (-1, 1):
        a = v3(sx * MANGO[0], Y_MANGO, Z_MANGO)
        b = v3(sx * MANGO[1], Y_MANGO, Z_MANGO)
        madera = np.minimum(madera, capsula(P, a, b, MANGO_R + 0.25, MANGO_R))
    return madera


def hierros(P):
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    out = None
    # cinchos: pletinas que dan la vuelta al yugo (arriba, atrás y abajo) y se clavan en la cabeza
    for xc in CINCHOS:
        top = YY[1] + ARCO * (1.0 - (xc / YW) ** 2)
        lazo = caja(P, (xc, (top + YY[0]) / 2, (YZ[0] + 1.2) / 2), (1.05, (top - YY[0]) / 2 + 0.28, (1.2 - YZ[0]) / 2 + 0.28), 0.2)
        hueco_ = caja(P, (xc, (top + YY[0]) / 2, (YZ[0] + 1.2) / 2 + 0.4), (1.3, (top - YY[0]) / 2, (1.2 - YZ[0]) / 2), 0.0)
        c = np.maximum(lazo, -hueco_)
        out = c if out is None else np.minimum(out, c)
        # pernos: cabezas redondas en la cara de atrás y tuercas cuadradas arriba
        for yb in (-2.6, 3.0):
            out = np.minimum(out, elipsoide(P, (xc, yb, YZ[0] - 0.35), (0.55, 0.55, 0.4)))
    # cantoneras en las puntas del bloque y virolas de los mangos
    for sx in (-1, 1):
        a = v3(sx * (MANGO[0] - 0.2), Y_MANGO, Z_MANGO)
        b = v3(sx * (MANGO[0] + 1.3), Y_MANGO, Z_MANGO)
        out = np.minimum(out, tubo(P, a, b, MANGO_R + 0.6))
        # muñón: la punta de hierro del eje en cada extremo
        a = v3(sx * (MANGO[1] - 0.4), Y_MANGO, Z_MANGO)
        b = v3(sx * (MANGO[1] + 1.4), Y_MANGO, Z_MANGO)
        out = np.minimum(out, tubo(P, a, b, MANGO_R + 0.35, MANGO_R * 0.75))
    return out


# --- el badajo ------------------------------------------------------------------------------------
BOLA_Z = 0.80 * H              # la bola del badajo (donde golpea: el medio pie)
BOLA_R = 2.3


def badajo(P, ang):
    """Badajo de hierro: cuelga de la cabeza; ang = hacia dónde está caído (0 abajo, pi arriba)."""
    b, dirn = _bola_badajo(ang)
    a = v3(0.0, 0.0, T_CABEZA + 0.3)
    vara = capsula(P, a, b, 0.75, 1.05)
    bola = elipsoide(P, b, (BOLA_R, BOLA_R, BOLA_R * 1.25))
    # la «lengua» del badajo: sale de la bola hacia la boca y asoma por ella
    c = punta_badajo(ang)
    lengua = smin(capsula(P, b, c, 1.0, 1.25), elipsoide(P, c, (POMO_R, POMO_R, POMO_R * 1.2)), 0.6)
    return np.minimum(smin(vara, bola, 0.8), lengua)


POMO_R = 1.9


def _bola_badajo(ang):
    rho = r_int(BOLA_Z) - BOLA_R - 0.15
    dirn = v3(math.sin(ang), -math.cos(ang), 0.0)
    return v3(0.0, 0.0, BOLA_Z) + rho * dirn, dirn


def punta_badajo(ang):
    """El pomo de la lengua del badajo, que asoma por la boca (los badajos de las campanas de
    volteo son largos)."""
    b, dirn = _bola_badajo(ang)
    return b + v3(0.0, 0.0, H - BOLA_Z + 9.0) + 4.0 * dirn


def angulo_badajo(R_, T, cual):
    """'abajo': caído por su peso (hacia abajo en pantalla); 'arriba': golpeando el borde por el
    lado en que el pomo más asoma por encima del labio visto desde el jugador (determinista)."""
    angs = np.linspace(0, 2 * math.pi, 49)[:-1]
    if cual == 'abajo':
        ys = [proyectar(v3(math.sin(a), -math.cos(a), 0.0) * 8.0 + v3(0, 0, H), R_, T)[1] for a in angs]
        return float(angs[int(np.argmax(ys))])
    cam = R_.T @ (-T)
    # puntos de la cara del pomo que mira al jugador; se cuentan los que no tapa el bronce
    rng = np.random.default_rng(3)
    U = rng.normal(size=(60, 3))
    U /= np.linalg.norm(U, axis=1, keepdims=True)
    t = np.linspace(0.0, 1.0, 300)[:-10]
    mejor, amejor = -1, 0.0
    for a in angs:
        c = punta_badajo(a)
        Q = c + U * POMO_R
        Q = Q[(Q - c) @ (cam - c) > 0]
        pts = (cam[None, None, :] + t[None, :, None] * (Q - cam)[:, None, :]).reshape(-1, 3)
        bz, _ = campana(pts)
        vis = int((bz.reshape(len(Q), -1).min(1) > 0).sum())
        if vis > mejor:
            mejor, amejor = vis, a
    return float(amejor)


# --- las manos en los mangos (agarre de manillar: dorso arriba y atrás, índice hacia dentro) ------
def _marco_mano(lado):
    GE = v3(1.0, 0.0, 0.0)
    GX = unit(v3(0.0, 0.72, -0.69))
    GF = -np.cross(GX, GE)
    G0 = v3(MANGO[0] + 2.3, Y_MANGO, Z_MANGO)
    if lado < 0:
        M = v3(-1, 1, 1)
        GX, GF, GE, G0 = GX * M, GF * M, GE * M, G0 * M
    return Agarre(G0=G0, GE=GE, GF=GF, GX=GX, r=MANGO_R)


MANOS = {1: _marco_mano(1), -1: _marco_mano(-1)}
PLIEGUES = (8.0, 15.0, 22.0)

MARGEN = 1.5
COTA_CAMP = (v3(0.0, 0.0, H / 2 + 6.0), v3(R + 0.6, R + 0.6, H / 2 + 8.5))
COTA_YUGO = (v3(0.0, 0.5, (YZ[0] + 1.5) / 2), v3(MANGO[1] + 1.8, 8.5, (1.5 - YZ[0]) / 2 + 1.0))


def _parcial(P, cota, fn, mats):
    """Evalúa fn(P_sub) → dict solo donde la cota es pequeña; fuera, la cota (que nunca es mayor
    que la distancia real) para el primer material."""
    sel = cota < MARGEN
    d = {m: np.full(len(P), 1e9) for m in mats}
    if sel.any():
        sub = fn(P[sel])
        for m in mats:
            d[m][sel] = sub[m]
    d[mats[0]] = np.where(sel, d[mats[0]], cota)
    return d


def modelo(P, pose):
    n = len(P)
    d = {m: np.full(n, 1e9) for m in MATS}

    def f_camp(Q):
        b, dentro = campana(Q)
        sub = {}
        # la cara de dentro (cerca de la superficie interior) se pinta oscura
        interior = (dentro < 0.3) & (Q[:, 2] > T_CABEZA + 0.2)
        sub['bronce'] = np.where(interior, 1e9, b)
        sub['hueco'] = np.where(interior, b, 1e9)
        sub['hierro'] = badajo(Q, pose.get('badajo', 0.0)) if pose.get('con_badajo', True) else np.full(len(Q), 1e9)
        return sub
    dc = _parcial(P, caja(P, *COTA_CAMP), f_camp, ['bronce', 'hueco', 'hierro'])

    def f_yugo(Q):
        return {'madera': yugo(Q), 'hierro': hierros(Q)}
    dy = _parcial(P, caja(P, *COTA_YUGO), f_yugo, ['madera', 'hierro'])
    d['bronce'] = dc['bronce']
    d['hueco'] = dc['hueco']
    d['hierro'] = np.minimum(dc['hierro'], dy['hierro'])
    d['madera'] = dy['madera']
    # pátina: manchas sobre el bronce (solo junto a la superficie: el ruido es caro)
    cerca = np.abs(d['bronce']) < 0.3
    if cerca.any():
        pat = patina(P[cerca])
        db = d['bronce'][cerca]
        d['patina'][cerca] = np.where(pat, db, 1e9)
        d['bronce'][cerca] = np.where(pat, 1e9, db)
    if pose.get('manos', True):
        for lado in (1, -1):
            A = MANOS[lado]
            br = pose['brazo'][lado]
            w0 = pose['w0'][lado]
            cota = np.minimum(np.linalg.norm(P - (A.G0 + 3.6 * A.GE), axis=1) - 8.0,
                              capsula(P, w0, w0 + 40.0 * br, 6.2))

            def mano(Q, A=A, br=br):
                m, w = mano_agarre(Q, A, br)
                dm = {'cuero': m}
                guante(dm, Q, w, br, largo_manga=40.0)
                return dm
            dm = _parcial(P, cota, mano, ['cuero', 'ribete', 'manga'])
            for m in ('cuero', 'ribete', 'manga'):
                d[m] = np.minimum(d[m], dm[m])
    D = np.stack([d[m] for m in MATS], 1)
    return D.min(1), D.argmin(1)


def patina(Q):
    """Dónde el bronce está cubierto de cardenillo: manchas, más en lo alto y en los cordones, y
    chorreones que bajan hacia la boca (la lluvia de siglos en el campanario)."""
    s = Q[:, 2] / H
    ang = np.arctan2(Q[:, 0], Q[:, 1])
    n = sdf.vnoise(Q, 0.42, 31) * 0.6 + sdf.vnoise(Q, 1.1, 32) * 0.4
    chorro = sdf.vnoise(np.column_stack([ang * 6.0, Q[:, 2] * 0.12, np.zeros(len(Q))]), 1.0, 33)
    cord = np.zeros(len(Q))
    for (sc, a, w) in CORDONES:
        cord += np.exp(-((s - sc) * H / (w * 2.2)) ** 2)
    # junto a la grieta el bronce está recién roto (sin cardenillo): así la raja se lee siempre
    _, _, dd, ancho = _grieta_dist(Q)
    limpio = np.abs(dd) < ancho + 0.07
    return ((n + 0.2 * cord + 0.33 * (chorro > 0.6) - 0.15 * s) > 0.56) & ~limpio


# ---------------------------------------------------------------------------------------------
# Detalle: inscripción gastada, grieta, vetas del yugo, pespuntes y pliegues
# ---------------------------------------------------------------------------------------------

# letras de 3x5 (la inscripción: «VELILLA» y un año en números romanos); a 1x se ven como un
# relieve gastado, no se leen, pero dan el ritmo de una leyenda fundida en el bronce
FUENTE = {
    'V': ('1.1', '1.1', '1.1', '1.1', '.1.'), 'E': ('111', '1..', '11.', '1..', '111'),
    'L': ('1..', '1..', '1..', '1..', '111'), 'I': ('111', '.1.', '.1.', '.1.', '111'),
    'A': ('.1.', '1.1', '111', '1.1', '1.1'), 'M': ('1.1', '111', '111', '1.1', '1.1'),
    'D': ('11.', '1.1', '1.1', '1.1', '11.'), 'X': ('1.1', '1.1', '.1.', '1.1', '1.1'),
    'C': ('.11', '1..', '1..', '1..', '.11'), '.': ('...', '...', '...', '...', '.1.'), ' ': ('...',) * 5,
}
LEYENDA = 'VELILLA . MDLXVIII . '


def _bitmap_leyenda():
    cols = []
    for ch in LEYENDA:
        g = FUENTE[ch]
        for c in range(3):
            cols.append([g[r][c] == '1' for r in range(5)])
        cols.append([False] * 5)
    return np.array(cols, bool).T          # (5, ncols)


LEY = _bitmap_leyenda()


def letras(pl):
    """→ máscara de los puntos que caen en el relieve de una letra (banda de la inscripción)."""
    s = pl[:, 2] / H
    ang = np.arctan2(pl[:, 0], pl[:, 1])                  # 0 arriba
    fila = np.floor((s - BANDA[0]) / (BANDA[1] - BANDA[0]) * 5).astype(int)
    col = np.floor((ang / (2 * math.pi) + 0.5) * LEY.shape[1]).astype(int) % LEY.shape[1]
    ok = (fila >= 0) & (fila < 5)
    out = np.zeros(len(pl), bool)
    out[ok] = LEY[fila[ok], col[ok]]
    return out


# la grieta: baja desde la boca por el costado de arriba a la izquierda (ángulo, s)
GRIETA = [(-0.62, 1.0), (-0.58, 0.9), (-0.66, 0.8), (-0.6, 0.69), (-0.65, 0.58), (-0.6, 0.47), (-0.63, 0.4)]


def _grieta_dist(pl):
    """→ (s, ok, dd, ancho): fracción de altura, si cae en el tramo de la grieta, distancia
    (angular, escalada) a su eje y su medio ancho."""
    s = pl[:, 2] / H
    ang = np.arctan2(pl[:, 0], pl[:, 1])
    ga = np.interp(-s, [-p[1] for p in GRIETA], [p[0] for p in GRIETA])
    ok = s > GRIETA[-1][1]
    ancho = 0.012 + 0.03 * np.clip((s - 0.4) / 0.6, 0, 1)
    dd = np.where(ok, (ang - ga) * r_ext(pl[:, 2]) / R, 1e9)
    return s, ok, dd, ancho


def grieta(pl):
    """→ (dentro, borde): la raja y su labio claro (en coordenadas de la superficie)."""
    s, ok, dd, ancho = _grieta_dist(pl)
    dentro = ok & (np.abs(dd) < ancho)
    borde = ok & (dd > ancho) & (dd < ancho + 0.03)
    return dentro, borde


def detalle(arma, r, I):
    pose = r.get('pose') or {}
    pl = r['pl']
    for m in ('bronce', 'patina'):
        sel = r['mat'] == arma.idx(m)
        if not sel.any():
            continue
        q = pl[sel]
        v = I[sel]
        # bronce fundido: no es liso (picado del molde) y tiene mugre
        v += 0.1 * (sdf.vnoise(q, 1.7, 41) - 0.5)
        # inscripción gastada: relieve claro (con sombra debajo) que se pierde a trozos
        le = letras(q) & (sdf.vnoise(q, 0.9, 43) > 0.33)
        le_sombra = letras(q + v3(0.0, 0.0, -0.35)) & ~le
        v[le] += 0.13
        v[le_sombra & (sdf.vnoise(q, 0.9, 43) > 0.33)] -= 0.18
        # la grieta
        g_in, g_bo = grieta(q)
        v[g_in] = np.minimum(v[g_in] - 0.6, 0.1)
        v[g_bo] += 0.15
        I[sel] = v
    # interior: más oscuro hacia la cabeza
    sel = r['mat'] == arma.idx('hueco')
    if sel.any():
        I[sel] *= np.clip(0.35 + 0.65 * pl[sel][:, 2] / H, 0.2, 1.0)
    # yugo: vetas a lo largo (x), nudos y mugre
    sel = r['mat'] == arma.idx('madera')
    if sel.any():
        q = pl[sel]
        w = (q[:, 1] + q[:, 2]) * 1.9 + 0.7 * np.sin(q[:, 0] * 0.3 + q[:, 2] * 0.5) + 2.2 * sdf.vnoise(q * v3(0.12, 1, 1), 0.8, 51)
        v = 0.15 * np.sin(w) - 0.22 * (np.sin(w * 2.3 + 1.0) > 0.82) - 0.15 * (sdf.vnoise(q, 0.7, 52) > 0.7)
        # moldura tallada: un surco que recorre la cara de atrás junto al borde de arriba y el de abajo
        ax = np.abs(q[:, 0])
        top = YY[1] + ARCO * (1.0 - np.clip(ax / YW, 0, 1) ** 2) - 3.0 * np.clip((ax - (YW - 5.0)) / 5.0, 0, 1) ** 1.5
        atras = q[:, 2] < YZ[0] + 0.25
        surco = atras & (ax < YW - 1.0) & ((np.abs(q[:, 1] - (top - 1.3)) < 0.28) | (np.abs(q[:, 1] - (YY[0] + 1.3)) < 0.28))
        v[surco] -= 0.35
        I[sel] += v
        filo(arma, r, I, mat='madera', fuerza=0.3, umbral=0.72)
    sel = r['mat'] == arma.idx('hierro')
    if sel.any():
        I[sel] += 0.12 * (sdf.vnoise(pl[sel], 2.4, 53) - 0.5)
    if pose.get('manos', True) and 'brazo' in pose:
        selm = r['mat'] == arma.idx('manga')
        q = pl[selm]
        dist = []
        for lado in (1, -1):
            o, e = pose['w0'][lado], pose['brazo'][lado]
            t = np.maximum((q - o) @ e, 0.0)
            dist.append(np.linalg.norm(q - o - np.outer(t, e), axis=1))
        k = np.argmin(np.stack(dist, 1), 1) if len(q) else np.zeros(0, int)
        for i, lado in enumerate((1, -1)):
            m = np.zeros(selm.shape, bool)
            m[selm] = k == i
            pliegues_pano(arma, r, I, pose['w0'][lado], pose['brazo'][lado], PLIEGUES, sel=m)
            A = MANOS[lado]
            cerca = np.linalg.norm(pl - A.G0, axis=-1) < 9.0
            Ic = I.copy()
            costuras(arma, r, Ic, A)
            I[cerca] = Ic[cerca]
        filo(arma, r, I)


ARMA = Arma(MATS, modelo, BRILLO, GANANCIA, detalle, rampas=RAMPAS_CAM)

# ---------------------------------------------------------------------------------------------
# Poses y fotogramas del arma
# ---------------------------------------------------------------------------------------------

LIENZO = (0, 56, 320, 160)       # x0, y0, ancho, alto (pantalla completa; abajo sale por el borde)
CODOS = {1: v3(34.0, -40.0, 4.0), -1: v3(-34.0, -40.0, 4.0)}   # codos en espacio de cámara (cm)
PIVOTE = v3(0.0, 0.0, -6.0)      # el respingo gira alrededor de las manos (el yugo)

POSE_A = {'recamara': (205.0, 178.0, 46.0), 'boca': (172.0, 140.0), 'alabeo': -8.0, 'badajo': 'abajo'}
POSES = {
    'BFGGA0': POSE_A,
    # el golpe: el badajo da en el borde de arriba (asoma por la boca) y la campana da un respingo
    'BFGGB0': dict(POSE_A, giro=(-2.5, 0.0, 1.5), empuje=(-0.4, -0.3, -2.0), badajo='arriba'),
}


def preparar(pose):
    p = dict(pose)
    R_, T = matriz_canon(p['recamara'], p['boca'], H, p['alabeo'])
    if 'giro' in p:
        gx, gy, gz = (math.radians(a) for a in p['giro'])
        R_, T = mover_pose(R_, T, rot_y(gy) @ rot_x(gx) @ rot_z(gz), PIVOTE, p.get('empuje', (0, 0, 0)))
    p['R'], p['T'] = R_, T
    # el badajo: caído hacia abajo (gravedad, en pantalla) o golpeando el borde por donde más asoma
    p['badajo'] = angulo_badajo(R_, T, p['badajo'])
    p['brazo'], p['w0'] = {}, {}
    for lado in (1, -1):
        _, w0 = mano_agarre(np.zeros((1, 3)), MANOS[lado], v3(0, 0, -1))
        codo = R_.T @ (CODOS[lado] - T)
        p['brazo'][lado] = unit(codo - w0)
        p['w0'][lado] = w0
    return p


_CACHE = {}


def render_fotograma(nombre, S=4):
    clave = (nombre, S)
    if clave not in _CACHE:
        pose = preparar(POSES[nombre])
        _CACHE[clave] = dibujar(ARMA, pose, pose['R'], pose['T'], LIENZO, S, previo=True, t0=6.0, tmax=110.0,
                                pasos=220)
    return _CACHE[clave].copy()


# ---------------------------------------------------------------------------------------------
# Efectos 2D a pleno brillo: el verde pálido espectral del toque (deterministas)
# ---------------------------------------------------------------------------------------------

SS2 = 4                                  # submuestras por píxel y eje
# Niveles de la onda, de la penumbra a la cresta: cada uno es un damero de dos colores EXACTOS de
# PLAYPAL (un gris y un verde de la misma luz: así sale un verde pálido, que la paleta no tiene);
# en los dos primeros un color es «agujero» y el halo se ve a través, como un fantasma.
NIVELES = [(None, 123), (None, 120), (105, 121), (101, 119), (98, 117), (94, 115), (88, 113), (84, 112), (80, 112),
           (4, 80), (4, 4)]
PARES = np.array([[_PAL[a] if a is not None else (0, 0, 0), _PAL[b]] for a, b in NIVELES], np.uint8)
AGUJERO = np.array([a is None for a, b in NIVELES])


def fbm2(x, y, escala, semilla):
    P = np.column_stack([x.ravel(), y.ravel(), np.full(x.size, 0.37 + semilla)])
    n = (sdf.vnoise(P, escala, semilla) * 0.6 + sdf.vnoise(P, escala * 2.1, semilla + 1) * 0.3
         + sdf.vnoise(P, escala * 4.3, semilla + 2) * 0.1)
    return n.reshape(x.shape)


def malla(W, H, cx, cy):
    """Coordenadas de las submuestras (x a la derecha, y hacia ARRIBA) respecto a (cx, cy)."""
    jj, ii = np.meshgrid(np.arange(W * SS2), np.arange(H * SS2))
    return (jj + 0.5) / SS2 - cx, cy - (ii + 0.5) / SS2


def reducir2(a, W, H):
    return a.reshape(H, SS2, W, SS2).mean(axis=(1, 3))


def pintar_onda(img, val, vis, encima=True):
    """val (0..1, por píxel) → niveles en damero donde vis (encima=False: solo donde no hay nada)."""
    H, W = val.shape
    n = len(NIVELES) - 1
    lvl = np.clip(np.round(np.clip(val, 0, 1) * n), 0, n).astype(int)
    jj, ii = np.meshgrid(np.arange(W), np.arange(H))
    dam = ((ii + jj) % 2).astype(int)
    col = PARES[lvl, dam]
    sel = vis & ~(AGUJERO[lvl] & (dam == 0))
    if not encima:
        sel &= img[..., 3] == 0
    img[sel, :3] = col[sel]
    img[sel, 3] = 255


def campo_onda(x, y, nucleo=(0.0, 0.0), anillos=(), halo=(0.0, 0.0, 0.0), semilla=1, rompe=0.0, aspecto=1.1,
               jirones=0.0):
    """Campo (submuestras) de un toque: núcleo (radio, fuerza), anillos [(radio, ancho, fuerza)],
    halo (radio, fuerza, rugosidad) que se deshilacha, rompe (0..1: cuánto se rompen los anillos
    en trozos), jirones (fuerza de las hebras que salen hacia fuera)."""
    r = np.hypot(x, y * aspecto)
    th = np.arctan2(y * aspecto, x)
    v = np.zeros_like(r)
    rh, kh, rug = halo
    if kh > 0:
        borde = rh * (1.0 + rug * (fbm2(np.cos(th) * 2.4, np.sin(th) * 2.4, 1.0, semilla) - 0.5))
        v += kh * np.clip(1.0 - r / borde, 0, 1) ** 0.7
    # los anillos ondulan un poco (no son una diana perfecta)
    ond = 1.2 * (fbm2(np.cos(th) * 3.0, np.sin(th) * 3.0, 1.0, semilla + 4) - 0.5)
    for i, (ra, an, ka) in enumerate(anillos):
        a = ka * np.exp(-((r - ra * (1.0 + 0.06 * ond)) / an) ** 2)
        if rompe > 0:
            trozos = fbm2(np.cos(th) * (2.0 + ra * 0.08), np.sin(th) * (2.0 + ra * 0.08), 1.0, semilla + 10 + i)
            a *= np.clip((trozos - rompe * 0.75) * 4.0, 0, 1)
        v += a
    if jirones > 0 and rh > 0:
        # hebras que se escapan del halo hacia fuera, curvadas (como el humo de una vela)
        u = np.clip((r - 0.7 * rh) / (0.6 * rh), 0, 1)
        giro = th + 0.9 * u
        heb = fbm2(np.cos(giro) * 4.5, np.sin(giro) * 4.5, 1.0, semilla + 20)
        v += jirones * np.clip((heb - 0.58) * 4.0, 0, 1) * np.sin(math.pi * u) * (r > 0.7 * rh)
    rn, kn = nucleo
    if kn > 0:
        v += kn * np.clip(1.0 - r / rn, 0, 1) ** 0.8
    v += 0.06 * (fbm2(x, y, 0.4, semilla + 30) - 0.5) * (v > 0.05)
    return v


def onda_img(W, H, umbral=0.06, **kw):
    """→ (img RGBA, cx, cy): el campo de campo_onda pintado en un lienzo W x H centrado."""
    cx, cy = W / 2, H / 2
    x, y = malla(W, H, cx, cy)
    v = campo_onda(x, y, **kw)
    on = v > umbral
    cob = reducir2(on.astype(float), W, H)
    vv = reducir2(np.where(on, v, 0), W, H) / np.maximum(cob, 1e-6)
    img = np.zeros((H, W, 4), np.uint8)
    pintar_onda(img, vv, cob >= 0.4)
    return img, cx, cy


def anclas(img):
    """Píxeles invisibles en las esquinas de abajo: construir_pwad no recorta (ni mueve) el lienzo."""
    H, W = img.shape[:2]
    for x in (0, W - 1):
        if img[H - 1, x, 3] == 0:
            img[H - 1, x] = (0, 0, 0, 1)
    return img


def centrar(img, cx, cy, sube):
    """Desplazamientos de un efecto centrado: el centro del lienzo en el origen en x, y 'sube' px
    por encima del origen (como Freedoom: el origen algo por debajo del centro)."""
    return [int(round(cx)), int(round(cy + sube))]


# BFS1: el toque en vuelo (A y B: las ondas avanzan media vuelta)
def toque(fr):
    fase = {'A': 0.0, 'B': 0.5}[fr]
    W, H = 52, 48
    paso = 6.0
    anillos = [((k + fase) * paso + 3.0, 1.15, 0.62 * (1.0 - ((k + fase) * paso + 3.0) / 24.0) + 0.1) for k in range(4)]
    img, cx, cy = onda_img(W, H, nucleo=(8.0, 1.05), anillos=anillos, halo=(21.0, 0.3, 0.45), semilla=5 + (fr == 'B'),
                           jirones=0.25)
    return anclas(img), centrar(img, cx, cy, 8)


# BFE1: el gran estallido (A el golpe, B-C los anillos se abren (C: el rayo), D-F se deshacen)
ESTALLIDO = {
    'A': dict(W=76, H=68, nucleo=(14.0, 1.2), anillos=[(20.0, 2.3, 0.95), (10.0, 1.5, 0.3)], halo=(26.0, 0.42, 0.5),
              jirones=0.5),
    'B': dict(W=100, H=88, nucleo=(10.0, 0.85), anillos=[(32.0, 2.5, 0.9), (22.0, 1.9, 0.6), (13.0, 1.4, 0.35)],
              halo=(37.0, 0.26, 0.45), jirones=0.5),
    'C': dict(W=128, H=112, nucleo=(7.0, 0.6), anillos=[(46.0, 2.5, 0.85), (35.0, 2.1, 0.62), (24.0, 1.7, 0.42)],
              halo=(51.0, 0.16, 0.4), jirones=0.5, rompe=0.1),
    'D': dict(W=136, H=120, nucleo=(4.0, 0.3), anillos=[(54.0, 2.3, 0.66), (43.0, 1.9, 0.45), (31.0, 1.5, 0.28)],
              halo=(57.0, 0.07, 0.4), jirones=0.45, rompe=0.4),
    'E': dict(W=140, H=124, anillos=[(59.0, 2.0, 0.46), (48.0, 1.6, 0.28)], halo=(61.0, 0.0, 0.4), rompe=0.6),
    'F': dict(W=144, H=128, anillos=[(63.0, 1.8, 0.3), (52.0, 1.4, 0.16)], rompe=0.75),
}


def estallido(fr):
    kw = dict(ESTALLIDO[fr])
    W, H = kw.pop('W'), kw.pop('H')
    img, cx, cy = onda_img(W, H, semilla=60 + 'ABCDEF'.index(fr), **kw)
    return anclas(img), centrar(img, cx, cy, round(0.08 * H))


# BFE2: el estallido pequeño sobre cada enemigo alcanzado por el rayo
CHISPAZO = {
    'A': dict(W=50, H=46, nucleo=(9.0, 1.15), anillos=[(14.0, 1.8, 0.9)], halo=(17.0, 0.38, 0.5), jirones=0.5),
    'B': dict(W=64, H=58, nucleo=(6.0, 0.7), anillos=[(21.0, 2.0, 0.8), (12.0, 1.4, 0.42)], halo=(24.0, 0.18, 0.45),
              jirones=0.5),
    'C': dict(W=70, H=64, anillos=[(26.0, 1.8, 0.55), (17.0, 1.3, 0.3)], halo=(28.0, 0.04, 0.4), rompe=0.45),
    'D': dict(W=74, H=68, anillos=[(30.0, 1.6, 0.36), (21.0, 1.2, 0.18)], rompe=0.65),
}


def chispazo(fr):
    kw = dict(CHISPAZO[fr])
    W, H = kw.pop('W'), kw.pop('H')
    img, cx, cy = onda_img(W, H, semilla=80 + 'ABCD'.index(fr), **kw)
    return anclas(img), centrar(img, cx, cy, 7)


# ---------------------------------------------------------------------------------------------
# BFGF: el resplandor del toque sobre el arma (fotograma B), a pleno brillo
# ---------------------------------------------------------------------------------------------

LIENZO_F = (0, 8, 320, 208)       # lienzo del resplandor (más alto: las ondas suben)


def mascaras_b(S=2):
    """Por píxel del lienzo del resplandor (fotograma B): alfa del arma, y dónde hay pátina, grieta
    e inscripción (lo que se enciende), y la altura en el eje de la campana (z del arma)."""
    from arma1p import trazar
    pose = preparar(POSES['BFGGB0'])
    x0, y0, w, h = LIENZO_F
    r = trazar(ARMA, pose, pose['R'], pose['T'], x0, y0, w, h, S, t0=6.0, tmax=110.0, pasos=220)
    mat, pl, hit = r['mat'], r['pl'], r['hit']
    bell = (mat == ARMA.idx('bronce')) | (mat == ARMA.idx('patina'))
    plf = pl.reshape(-1, 3)
    g_in, _ = grieta(plf)
    le = letras(plf)

    def red_(a):
        return a.reshape(h, S, w, S).mean(axis=(1, 3))
    return {
        'alfa': red_(hit.astype(float)) >= 0.5,
        'campana': red_(bell.astype(float)) >= 0.5,
        'patina': red_((mat == ARMA.idx('patina')).astype(float)) >= 0.5,
        'grieta': red_((bell.reshape(-1) & g_in).reshape(mat.shape).astype(float)) >= 0.25,
        'letras': red_((bell.reshape(-1) & le).reshape(mat.shape).astype(float)) >= 0.4,
        'z': red_(np.where(bell, pl[..., 2], 0.0)) / np.maximum(red_(bell.astype(float)), 1e-6),
        'pose': pose,
    }


# las ondas del golpe: (distancia delante de la boca, radio, medio ancho, fuerza), en cm
ONDAS_F = {'A': [(1.5, R + 1.0, 0.9, 1.0), (7.0, R + 5.0, 0.8, 0.7)],
           'B': [(9.0, R + 8.0, 0.9, 0.75), (19.0, R + 15.0, 0.9, 0.45)]}


def resplandor(fr, M):
    """→ (img, x0, y0) en pantalla completa: A, el golpe (la campana se enciende: pátina, grieta e
    inscripción; la luz rebosa por el labio y una onda se despega de la boca); B, la onda ya ancha
    que se apaga. Las ondas van en planos delante de la boca (geometría de verdad: rayos de la
    cámara cortados con esos planos); lo que queda detrás de la campana no se ve."""
    x0, y0, w, h = LIENZO_F
    pose = M['pose']
    R_, T = pose['R'], pose['T']
    img = np.zeros((h, w, 4), np.uint8)
    fuerte = fr == 'A'
    # 1) la campana se enciende, más cuanto más cerca de la boca (la cabeza queda apagada)
    zf = np.clip(M['z'] / H, 0, 1)
    v = np.zeros((h, w))
    # (el cardenillo cubre media campana: solo se enciende la mitad de la boca, en degradado)
    pat = M['patina'] & M['campana'] & (zf > 0.5)
    k = (zf[pat] - 0.5) / 0.5
    v[pat] = (0.1 + 0.4 * k) if fuerte else (0.05 + 0.25 * k)
    le = M['letras'] & M['campana'] & ~pat
    v[le] = 0.45 if fuerte else 0.3
    gr = M['grieta'] & M['campana']
    v[gr] = (1.0 if fuerte else 0.75) - 0.35 * (1 - zf[gr])
    pintar_onda(img, v, pat | le | gr)
    # 2) fuera de la campana: rayos de la cámara (submuestras) al espacio de la campana
    jj, ii = np.meshgrid(np.arange(w * SS2), np.arange(h * SS2))
    X = x0 + (jj + 0.5) / SS2
    Y = y0 + (ii + 0.5) / SS2
    D = np.stack([(X - 160) / 170.0, -(Y - 100) * 1.2 / 170.0, np.ones_like(X)], -1)
    Ow = R_.T @ (-T)
    Dw = D @ R_                                   # (R^T d) por fila

    def rho_en(zp):
        t = (zp - Ow[2]) / Dw[..., 2]
        q = Ow[None, None, :2] + t[..., None] * Dw[..., :2]
        return np.hypot(q[..., 0], q[..., 1]), t > 0
    campo = np.zeros(X.shape)
    for k, (dz, rad, an, fz) in enumerate(ONDAS_F[fr]):
        rho, ok = rho_en(H + dz)
        a = fz * np.exp(-((rho - rad) / an) ** 2) * ok
        if not fuerte:                            # la onda ancha se rompe en trozos
            trozo = fbm2(X * 0.06, Y * 0.06, 1.0, 93 + k)
            a *= np.clip((trozo - 0.3) * 3.0, 0, 1)
        campo += a
    # la luz que rebosa por el labio: un disco brillante justo delante de la boca, algo más ancho
    rho, ok = rho_en(H + 1.0)
    borde = R * (1.18 if fuerte else 1.08)
    campo += (1.0 if fuerte else 0.5) * np.clip((borde - rho) / (borde - R * 0.85), 0, 1) ** 1.3 * ok
    campo += 0.06 * (fbm2(X * 0.25, Y * 0.25, 1.0, 95) - 0.5) * (campo > 0.06)
    on = campo > 0.07
    cob = reducir2(on.astype(float), w, h)
    vv = reducir2(np.where(on, campo, 0), w, h) / np.maximum(cob, 1e-6)
    pintar_onda(img, vv, (cob >= 0.4) & ~M['alfa'])
    return img, x0, y0


# ---------------------------------------------------------------------------------------------
# BFUG: la campana en el suelo (de pie, la boca abajo y el yugo encima)
# ---------------------------------------------------------------------------------------------

def recoger(salida, S=4):
    pose = {'manos': False, 'con_badajo': False}
    # eje de la campana (z del arma) hacia abajo, yugo arriba (−z del arma hacia arriba), largo del
    # yugo (x) de lado a lado; vista desde algo arriba y un poco girada para que se vea el volumen
    Rb = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]).T
    Rb = np.stack([v3(1, 0, 0), v3(0, 0, 1), v3(0, -1, 0)], 1)
    R_ = rot_x(math.radians(-22)) @ rot_y(math.radians(-28)) @ Rb
    dist = 290.0
    E = 1.9
    c = v3(0.0, 0.0, H * 0.42) * E
    T = v3(0.0, 0.0, dist) - R_ @ c
    k = 1.0 / E
    claro = dict(GANANCIA, bronce=0.72, patina=0.85, madera=0.75, hierro=0.85)
    gordo = Arma(MATS, lambda P, pz: modelo(P * k, pz), BRILLO, claro, detalle, rampas=RAMPAS_CAM)
    img = dibujar(gordo, pose, R_, T, (110, 60, 100, 80), S, bordes=False, t0=dist - 90, tmax=dist + 90, pasos=300)
    a = img[..., 3] > 0
    ys, xs = np.nonzero(a)
    img = img[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    Image.fromarray(img, 'RGBA').save(os.path.join(salida, 'BFUGA0.png'))
    hh, ww = img.shape[:2]
    return [ww // 2, hh]


# ---------------------------------------------------------------------------------------------
# Revisión: pantallas simuladas y hoja de contactos
# ---------------------------------------------------------------------------------------------

def leer_mios(carpeta):
    ruta = os.path.join(carpeta, 'offsets_campana.json')
    if os.path.exists(ruta):
        with open(ruta) as fh:
            return json.load(fh)
    return {}


def vista(carpeta, salida):
    from arma1p import simular_pantalla
    estados = [['BFGGA0'], ['BFGGB0', 'BFGFA0'], ['BFGGB0', 'BFGFB0'], ['BFGGB0']]
    W = Image.new('RGBA', (330 * len(estados), 210 * 2 + 20), (20, 20, 20, 255))
    for c, capas in enumerate(estados):
        for r, barra in enumerate((True, False)):
            W.paste(simular_pantalla(carpeta, capas, barra), (330 * c, 210 * r + 20))
        ImageDraw.Draw(W).text((330 * c + 4, 4), '+'.join(capas), fill=(230, 230, 230, 255))
    W = W.resize((W.width * 2, int(W.height * 1.2) * 2), Image.NEAREST)
    W.save(salida)


def hoja(carpeta, ruta):
    """Hoja de contactos ampliada del toque, los estallidos y la campana en el suelo (la cruz roja
    marca el origen del objeto)."""
    off = leer_mios(carpeta)
    filas = [['BFS1A0', 'BFS1B0', 'BFUGA0', 'BFE2A0', 'BFE2B0', 'BFE2C0', 'BFE2D0'],
             ['BFE1A0', 'BFE1B0', 'BFE1C0'], ['BFE1D0', 'BFE1E0', 'BFE1F0']]
    ims = {n: Image.open(os.path.join(carpeta, n + '.png')).convert('RGBA') for f in filas for n in f
           if os.path.exists(os.path.join(carpeta, n + '.png'))}
    escalas = [4, 3, 3]
    fondo = (70, 70, 78, 255)
    bloques = []
    for f, e in zip(filas, escalas):
        cw = [ims[n].width * e + 16 if n in ims else 0 for n in f]
        hf = max(ims[n].height for n in f if n in ims) * e + 30
        bloques.append((f, e, cw, hf))
    S = Image.new('RGBA', (max(sum(b[2]) for b in bloques), sum(b[3] for b in bloques)), fondo)
    d = ImageDraw.Draw(S)
    y = 0
    for f, e, cw, hf in bloques:
        x = 0
        for n, c in zip(f, cw):
            if n not in ims:
                continue
            im = ims[n]
            S.alpha_composite(im.resize((im.width * e, im.height * e), Image.NEAREST), (x + 8, y + 20))
            d.text((x + 8, y + 4), f'{n} {im.width}x{im.height} {off.get(n)}', fill=(240, 240, 240))
            if n in off:
                ox, oy = x + 8 + off[n][0] * e, y + 20 + off[n][1] * e
                d.line([(ox - 6, oy), (ox + 6, oy)], fill=(255, 40, 40))
                d.line([(ox, oy - 6), (ox, oy + 6)], fill=(255, 40, 40))
            x += c
        y += hf
    S.save(ruta)


# ---------------------------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--salida', required=True, help='carpeta de PNG (arte/sprites)')
    ap.add_argument('--muestreo', type=int, default=4, help='rayos por lado de píxel del arma (4 = 16)')
    ap.add_argument('--solo', default=None, help='solo estos lumps (separados por comas)')
    ap.add_argument('--vista', default=None, help='PNG con las pantallas simuladas del arma')
    ap.add_argument('--hoja', default=None, help='PNG con la hoja de contactos del toque')
    args = ap.parse_args()
    os.makedirs(args.salida, exist_ok=True)
    solo = [s.strip().upper() for s in args.solo.split(',')] if args.solo else None

    def toca(n):
        return not solo or n in solo
    x0, y0, _, _ = LIENZO
    offsets = leer_mios(args.salida) if solo else {}
    for nombre in POSES:
        if not toca(nombre):
            continue
        img = render_fotograma(nombre, args.muestreo)
        offsets[nombre], g = guardar(img, x0, y0, os.path.join(args.salida, nombre + '.png'))
        print(f'{nombre}: {g[2]}x{g[3]} en pantalla ({g[0]}, {g[1]}) offsets {offsets[nombre]}', flush=True)
    if toca('BFGFA0') or toca('BFGFB0'):
        M = mascaras_b()
        for fr in 'AB':
            nombre = f'BFGF{fr}0'
            if not toca(nombre):
                continue
            img, fx, fy = resplandor(fr, M)
            offsets[nombre], g = guardar(img, fx, fy, os.path.join(args.salida, nombre + '.png'))
            print(f'{nombre}: {g[2]}x{g[3]} en pantalla ({g[0]}, {g[1]}) offsets {offsets[nombre]}', flush=True)
    for fr in 'AB':
        nombre = f'BFS1{fr}0'
        if toca(nombre):
            img, offsets[nombre] = toque(fr)
            Image.fromarray(img, 'RGBA').save(os.path.join(args.salida, nombre + '.png'))
            print(f'{nombre}: {img.shape[1]}x{img.shape[0]} offsets {offsets[nombre]}', flush=True)
    for fr in 'ABCDEF':
        nombre = f'BFE1{fr}0'
        if toca(nombre):
            img, offsets[nombre] = estallido(fr)
            Image.fromarray(img, 'RGBA').save(os.path.join(args.salida, nombre + '.png'))
            print(f'{nombre}: {img.shape[1]}x{img.shape[0]} offsets {offsets[nombre]}', flush=True)
    for fr in 'ABCD':
        nombre = f'BFE2{fr}0'
        if toca(nombre):
            img, offsets[nombre] = chispazo(fr)
            Image.fromarray(img, 'RGBA').save(os.path.join(args.salida, nombre + '.png'))
            print(f'{nombre}: {img.shape[1]}x{img.shape[0]} offsets {offsets[nombre]}', flush=True)
    if toca('BFUGA0'):
        offsets['BFUGA0'] = recoger(args.salida, args.muestreo)
        print(f'BFUGA0: offsets {offsets["BFUGA0"]}', flush=True)
    guardar_offsets(args.salida, offsets, 'campana')
    if args.vista:
        vista(args.salida, args.vista)
    if args.hoja:
        hoja(args.salida, args.hoja)


if __name__ == '__main__':
    main()
