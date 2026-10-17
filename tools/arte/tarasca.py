#!/usr/bin/env python3
"""tarasca.py — dibuja POR CÓDIGO a LA TARASCA (sustituye a la mente maestra araña SPID de Freedoom; jefe).

La dragona de las procesiones del Corpus convertida en monstruo: cuerpo de tortuga-dragón con un caparazón
abombado de placas verde oscuro y pinchos de cuerno, SEIS patas cortas y gruesas que se abren a los lados
(con garras y un espolón en el codo), cuello largo con cresta y cabeza de dragón (cuernos hacia atrás, cejas
pesadas, ojos rojos que brillan, fauces llenas de dientes y lengua roja), y cola de serpiente que arrastra.
Encima del caparazón, el ARMAZÓN DE MADERA de una carroza de procesión: tablero con moldura dorada vieja,
faldón de terciopelo rojo raído con flecos dorados, barandilla de balaustres torneados con remates de bola,
telas rojas rotas colgadas de la barandilla y dos sogas que lo atan al caparazón; y montada en el centro,
una AMETRALLADORA de siete cañones en corona giratoria (con el aire del órgano de fuego del jugador: cajón de
nogal, flejes de hierro, tolva y manivela; platos de latón): de frente se lee un anillo de bocas negras. Su
ráfaga va en el propio sprite: un fogonazo amarillo-blanco grande DELANTE de las bocas (disco, lengua y
estrella de rayos; en G en cruz y en H en aspa, con la corona girada medio paso), que de frente tapa la boca
del arma y sobresale del cajón; así A a pleno brillo se lee como «apunta» y G/H como «ráfaga». El caparazón
es verde oscuro con sombra en las juntas y manchas de mugre parda.

Técnica: la de todas las criaturas (tools/arte/sdf.py): modelo 3D de primitivas SDF con poses paramétricas,
trazado ortográfico (cámara 10° desde arriba), rampas EXACTAS de PLAYPAL, reducción con prioridad a lo cercano
y a lo que brilla, contorno de 1 px. Como el sprite es enorme (~250 px de largo de lado), el trazado es propio
(TRender, sin tocar el motor común): 3x3 submuestras por píxel (a este tamaño no se nota frente a 4x4), cada
rayo solo evalúa los grupos cuya esfera envolvente atraviesa (y salta hasta la siguiente), por trozos para no
gastar memoria; y los lumps se reparten entre varios procesos. Las placas del caparazón y las escamas son
celdas de Voronoi 3D en el marco del cuerpo (no «nadan» al andar). El humo de la muerte se pinta en 2D detrás
del modelo, con un campo de densidad (ruido determinista) cuantizado a una rampa de grises.

Fotogramas (info.c, SPR_SPID; Freedoom rota A-J):
    A-F  andar: trípodes alternos (delantera y trasera de un lado + la de en medio del otro) .. 8 ángulos
         (A también apuntando, a pleno brillo, 20 tics)
    G-H  ráfaga (a pleno brillo): G disparan los cañones 1, 3, 5, 7; H los 2, 4, 6, con retroceso 8 ángulos
    I    dolor: se encabrita, la cabeza atrás y las fauces abiertas .......................... 8 ángulos
    J    muerte (A_Scream): ruge hacia arriba, escupe sangre, el arma da un tirón ............. 8 ángulos
    K-S  muerte de frente (ángulo 0): se le doblan las patas (K), cae de panza y se parte un poste (L),
         la carroza se ladea (M), el arma se suelta y cae al suelo y la cabeza, ya en el suelo, empieza a
         girar hacia el flanco (N), el tablero se parte y cada mitad
         resbala por un flanco del caparazón mientras la cabeza cae de lado al suelo, de perfil y con las
         fauces abiertas (O), humo y brasas (P-R) y queda tumbada, con un charco de sangre que sale de la
         boca y el humo que se apaga (S, el cadáver).

Apoyo: offsets EXPLÍCITOS en arte/sprites/offsets_tarasca.json (este script lo escribe/actualiza): el eje del
cuerpo en el centro del ancho y el suelo del modelo (en el eje) SINK px por debajo del origen en TODOS los
fotogramas y ángulos. Apoyo «de pintor», como en los sprites de Doom: con la cámara a 10° lo que pisa el suelo
cerca de la cámara (garras, talones, la cola que arrastra) caería por debajo de la línea del suelo; se sube
justo lo que baja por la perspectiva (profundidad x tan 10°), de modo que en A-J lo más bajo queda a 4-6 px del
origen (8-9 en I6 y J4, por el muslo trasero al encabritarse) sin mover el cuerpo entre ángulos. En las
muertes se mide (rejilla) y se sube lo que yace delante: en K-M la cabeza que se desploma, y en todas el arma
caída y los restos; la cabeza tumbada de N-S y el cuerpo de panza se quedan en el suelo (10-16 px).

Uso (determinista; regenera los 89 PNG SPID* y offsets_tarasca.json; ~13 min de CPU: ~2-3 min con 6 núcleos):
    ~/.venvs/pesadilla/bin/python tools/arte/tarasca.py --salida arte/sprites
    … --solo SPIDA1,SPIDG3      solo esos lumps (offsets_tarasca.json se actualiza, no se pisa)
    … --hoja hoja.png           además, hoja de contactos ampliada x3 con etiquetas
    … --procesos N              procesos en paralelo (por defecto, uno por núcleo)
    (de espaldas, ángulos 4-6, el trazado usa 2x2 submuestras: allí no hay detalle fino)
"""
import argparse
import fcntl
import json
import math
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdf  # noqa: E402
from sdf import (V, nrm, rot_x, rot_y, rot_z, rad, basis, Frame, _len, Prim,  # noqa: E402
                 Sphere, Ellipsoid, RoundCone, CappedCone, Box, Ring, Group, vnoise, scene_eval,
                 Render, finish, ik, apply_shine, cli, sprite_rows, TILT)

# ----------------------------------------------------------------------------- materiales
(SHELL, SKIN, BELLY, SPIKE, SPIKEB, CLAW, HORN, TEETH, MOUTH, TONGUE, EYE, SOCKET, DEADEYE,
 WOOD, GILT, CLOTH, FRINGE, ROPE, IRON, WALNUT, BRASS, SOOT, BORE, FLASH, BLOOD, EMBER, CHAR, GRIME) = range(28)
RAMPS = {
    SHELL: [12, 127, 126, 125, 124, 123, 122],             # placas del caparazón: verde oscuro, sombra olivácea
    GRIME: [2, 12, 11, 10, 9, 158],                         # mugre y verdín pardo sobre el caparazón
    SKIN: [12, 11, 10, 9, 158, 157, 156, 155, 154],         # piel escamosa: verde oliva sucio
    BELLY: [1, 79, 151, 150, 149, 148, 147, 146, 145],      # vientre y garganta: escamas pajizas
    SPIKE: [2, 151, 149, 147, 145, 144, 129, 128],          # punta de los pinchos (hueso)
    SPIKEB: [0, 2, 239, 238, 237, 236, 13],                 # base de los pinchos (cuerno oscuro)
    CLAW: [0, 2, 239, 237, 141, 139, 136, 133],             # garras
    HORN: [2, 239, 237, 236, 141, 138, 135, 132, 129],      # cuernos
    TEETH: [2, 150, 148, 146, 144, 130, 129, 128],          # dientes sucios: raíz parda, punta marfil
    MOUTH: [0, 47, 46, 44, 42, 40, 38],                     # dentro de la boca
    TONGUE: [0, 46, 42, 38, 35, 32, 29, 26],                # lengua
    EYE: [180, 176, 173],                                   # ojos rojos que brillan (borde, iris, núcleo)
    SOCKET: [0],
    DEADEYE: [0, 7],
    WOOD: [1, 239, 238, 237, 76, 74, 72, 70],               # madera vieja de la carroza
    GILT: [2, 79, 167, 166, 165, 164, 163, 162],            # dorado viejo, sin pulir
    CLOTH: [2, 47, 45, 43, 41, 39, 37, 35, 33],             # terciopelo rojo desteñido
    FRINGE: [2, 79, 166, 165, 164, 163, 162],               # flecos dorados sucios
    ROPE: [1, 2, 151, 150, 149, 148, 147],                  # soga de esparto
    IRON: [6, 5, 111, 109, 107, 104, 102, 99, 96],          # cañones y flejes (como el órgano de fuego)
    WALNUT: [1, 239, 237, 74, 72, 69, 67, 65],              # cajón de nogal (como el órgano de fuego)
    BRASS: [79, 238, 167, 166, 165, 164, 163],              # latón viejo
    SOOT: [0, 8, 7, 6, 5],                                  # hollín de las bocas
    BORE: [0],
    FLASH: [215, 231, 230, 229, 226, 225, 224],             # fogonazo (del borde al corazón): amarillo-blanco
    BLOOD: [191, 189, 187, 185, 182, 179],
    EMBER: [186, 183, 235, 233, 221, 217],                  # brasas
    CHAR: [0, 1, 2, 239, 238],                              # madera y tela quemadas
}
EMISSIVE = (EYE, FLASH, EMBER)
OUTLINE = 2                                                 # (23,15,7): casi negro cálido
SMOKE_RAMP = [5, 111, 109, 107, 105, 103, 101, 99]          # humo (como el del Ánima)
SS3 = int(os.environ.get('TARASCA_SS', 3))                  # submuestras por píxel y eje (3x3; 2 para pruebas)


# ----------------------------------------------------------------------------- ruido y celdas
def cells(Q, size, seed):
    """Voronoi 3D: (distancia al punto más cercano, al segundo, id de la celda) en unidades de celda."""
    X = Q / size
    i = np.floor(X).astype(np.int64)
    f = X - i
    n = len(X)
    f1 = np.full(n, 9.0)
    f2 = np.full(n, 9.0)
    cid = np.zeros(n, np.int64)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                h = ((i[:, 0] + dx) * 73856093) ^ ((i[:, 1] + dy) * 19349663) ^ ((i[:, 2] + dz) * 83492791) \
                    ^ (seed * 2654435761)
                h = (h ^ (h >> 13)) * 1274126177
                h = h ^ (h >> 16)
                jx = (h & 1023) / 1023.0
                jy = ((h >> 10) & 1023) / 1023.0
                jz = ((h >> 20) & 1023) / 1023.0
                ex = dx + 0.12 + 0.76 * jx - f[:, 0]
                ey = dy + 0.12 + 0.76 * jy - f[:, 1]
                ez = dz + 0.12 + 0.76 * jz - f[:, 2]
                d = np.sqrt(ex * ex + ey * ey + ez * ez)
                c1 = d < f1
                f2 = np.where(c1, f1, np.minimum(f2, d))
                cid = np.where(c1, h, cid)
                f1 = np.where(c1, d, f1)
    return f1, f2, cid


def fbm2(x, y, scale, seed):
    P = np.column_stack([np.ravel(x), np.ravel(y), np.full(np.size(x), 0.37 + seed)])
    n = vnoise(P, scale, seed) * 0.6 + vnoise(P, scale * 2.1, seed + 1) * 0.3 + vnoise(P, scale * 4.3, seed + 2) * 0.1
    return n.reshape(np.shape(x))


_N1, _N2 = {}, {}


def noise1(x, scale, seed):
    """Ruido 1D determinista en [0, 1] (tabla precalculada e interpolada: se evalúa millones de veces)."""
    key = (scale, seed)
    if key not in _N1:
        xs = np.arange(-200.0, 200.01, 0.25)
        P = np.column_stack([xs, np.full(len(xs), 0.5 + seed * 3.1), np.full(len(xs), 0.25)])
        _N1[key] = (xs, vnoise(P, scale, seed))
    xs, v = _N1[key]
    return np.interp(x, xs, v)


def noise2(x, y, scale, seed, z=0.0):
    """Ruido 2D determinista en [0, 1] (tabla de 0,5 en 0,5 con interpolación bilineal)."""
    key = (scale, seed, z)
    if key not in _N2:
        xs = np.arange(-100.0, 100.01, 0.5)
        ys = np.arange(-60.0, 20.01, 0.5)
        X, Y = np.meshgrid(xs, ys)
        P = np.column_stack([X.ravel(), Y.ravel(), np.full(X.size, z)])
        _N2[key] = vnoise(P, scale, seed).reshape(X.shape)
    T = _N2[key]
    fx = np.clip((x + 100.0) / 0.5, 0, T.shape[1] - 1.001)
    fy = np.clip((y + 60.0) / 0.5, 0, T.shape[0] - 1.001)
    ix, iy = fx.astype(int), fy.astype(int)
    ax, ay = fx - ix, fy - iy
    return ((T[iy, ix] * (1 - ax) + T[iy, ix + 1] * ax) * (1 - ay)
            + (T[iy + 1, ix] * (1 - ax) + T[iy + 1, ix + 1] * ax) * ay)


class Grp(Group):
    """sdf.Group más rápido para grupos grandes: el descarte por esfera envolvente de cada primitiva se hace de
    una vez (matriz puntos x primitivas) y cada primitiva solo se evalúa (y se funde) en los puntos que tiene
    cerca; las lejanas (a más de sdf.CULL, mayor que la k de cualquier grupo) entran como cota con un mínimo
    duro, que en la superficie da lo mismo que la unión suave."""

    def __init__(self, prims, **kw):
        super().__init__(prims, **kw)
        self.BC = np.array([p.bc for p in prims])
        self.BR = np.array([p.br for p in prims])
        self.CC = (self.BC * self.BC).sum(1)
        self.MATS = np.array([p.mat for p in prims])

    def eval(self, P):
        n = len(P)
        if self.xf is not None:
            A, t, ds = self.xf
            Q = (P - t) @ np.linalg.inv(A).T
        else:
            Q, ds = P, 1.0
        gb = _len(Q - self.bc) - self.br
        d = gb.copy()
        mat = np.full(n, self.prims[0].mat, int)
        near = np.nonzero(gb < sdf.CULL)[0]
        if len(near):
            Qn = Q[near]
            qq = np.einsum('ij,ij->i', Qn, Qn)
            Dm = np.sqrt(np.maximum(qq[:, None] - 2 * (Qn @ self.BC.T) + self.CC[None], 0)) - self.BR[None]
            sel = Dm < sdf.CULL
            far = np.where(sel, np.inf, Dm)
            j0 = far.argmin(1)
            best = np.minimum(far[np.arange(len(near)), j0], 1e9)
            raw = best.copy()
            mn = self.MATS[j0]
            for j in np.nonzero(sel.any(0))[0]:
                s = np.nonzero(sel[:, j])[0]
                dp = self.prims[j](Qn[s])
                b = best[s]
                if self.k > 0:
                    h = np.clip(0.5 + 0.5 * (b - dp) / self.k, 0, 1)
                    best[s] = b * (1 - h) + dp * h - self.k * h * (1 - h)
                else:
                    best[s] = np.minimum(b, dp)
                closer = dp < raw[s]
                mn[s[closer]] = self.MATS[j]
                raw[s] = np.minimum(raw[s], dp)
            if self.cut is not None:
                best = np.maximum(best, self.cut(Qn))
            d[near] = best
            mat[near] = mn
        return d * ds, mat


# ----------------------------------------------------------------------------- primitivas propias
class Curtain(Prim):
    """Tela que cuelga: hoja en el marco F (x' a lo ancho, y' arriba; cuelga de y' = 0 hacia abajo, z' hacia
    fuera) con pliegues (más hondos abajo), algo de vuelo hacia fuera, bajo rasgado en jirones y agujeros.
    threads > 0: flecos (la hoja se corta en hilos verticales de ese paso)."""

    def __init__(self, F, half_w, drop, mat, amp=0.8, k=0.8, ph=0.0, thick=0.55, flare=0.12, tear=0.0,
                 seed=0, holes=0.0, threads=0.0, sway=0.0, xr=None):
        self.F, self.hw, self.drop, self.mat = F, half_w, drop, mat
        lo, hi = xr if xr is not None else (-half_w, half_w)       # trozo de la tela (para grupos pequeños)
        self.xm, self.xh = (lo + hi) / 2, (hi - lo) / 2
        self.amp, self.k, self.ph, self.thick, self.flare = amp, k, ph, thick, flare
        self.tear, self.seed, self.holes, self.threads, self.sway = tear, seed, holes, threads, sway
        self.L = math.sqrt(1 + (amp * k) ** 2 + (flare + abs(sway) / max(drop, 1)) ** 2) * 1.15
        self.bc = F.p((self.xm, -drop / 2, 0))
        self.br = math.hypot(self.xh, drop / 2 + tear) + amp + abs(flare) * drop + abs(sway) + 2

    def sdf(self, P):
        q = self.F.to_local(P)
        x, y, z = q[:, 0], q[:, 1], q[:, 2]
        t = np.clip(-y / self.drop, 0, 1.4)
        a = self.amp * (0.35 + 0.65 * t)
        zc = a * np.sin(self.k * x + self.ph) + self.flare * (-y) + self.sway * t * t
        d = np.abs(z - zc) / self.L - self.thick
        bottom = -self.drop
        if self.tear > 0:
            n1 = noise1(x, 0.42, self.seed)
            n2 = noise1(x, 1.35, self.seed + 7)
            bottom = -self.drop + self.tear * (0.9 * n1 + 0.6 * n2 - 0.55)
        d = np.maximum(d, np.maximum(y, bottom - y) / 1.6)
        d = np.maximum(d, np.maximum(np.abs(x) - self.hw, np.abs(x - self.xm) - self.xh))
        if self.holes > 0:
            hn = noise2(x, y, 0.33, self.seed + 3, self.seed * 1.7)
            d = np.maximum(d, (hn - (1 - self.holes)) * 2.4 * (t > 0.15))
        if self.threads > 0:
            s = np.sin(x * math.pi / self.threads)
            d = np.maximum(d, (s - 0.25) * 0.5 * (y < -0.8))
        return d


# ----------------------------------------------------------------------------- materiales por punto
def materiales(P, mat, inten, nz, nr, spec, lvl_extra, extras):
    """Placas del caparazón, escamas, vientre, vetas de la madera, terciopelo, ojos, bocas de los cañones,
    fogonazos, sangre, brasas y quemado."""
    bo, bR = extras['body']
    Q = (P - bo) @ bR
    m = mat == SHELL
    if m.any():                                      # placas: Voronoi en el marco del cuerpo
        ii = np.nonzero(m)[0]
        f1, f2, cid = cells(Q[m], 13.0, 3)
        rnd = (cid & 1023) / 1023.0
        inten[ii] *= (0.84 + 0.30 * rnd) * (1.12 - 0.34 * np.clip(f1, 0, 1))
        rings = np.sin(f1 * 21.0) > 0.55            # anillos de crecimiento
        inten[ii[rings]] *= 0.86
        groove = (f2 - f1) < 0.1
        inten[ii[groove]] *= 0.34
        near = ((f2 - f1) < 0.22) & ~groove          # sombra junto a las juntas
        inten[ii[near]] *= 0.82
        moss = vnoise(Q[m], 0.21, 9) > 0.7           # manchas de verdín más claro
        inten[ii[moss & ~groove]] *= 1.08
        # mugre: manchas pardas (más hacia el borde de abajo) y suciedad metida en las juntas
        low = np.clip((8.0 - Q[m, 1]) / 14.0, 0, 1)
        dirt = (vnoise(Q[m], 0.16, 23) * 0.7 + vnoise(Q[m], 0.55, 24) * 0.3 + 0.28 * low) > 0.66
        mat[ii[dirt | (groove & (vnoise(Q[m], 0.4, 25) > 0.45))]] = GRIME
    ro, rR = extras['root']
    m = np.isin(mat, (SKIN,))
    if m.any():                                      # escamas pequeñas
        ii = np.nonzero(m)[0]
        Qr = (P[m] - ro) @ rR
        f1, f2, cid = cells(Qr, 3.8, 5)
        inten[ii] *= 0.9 + 0.16 * (1 - np.clip(f1, 0, 1)) + 0.06 * ((cid & 255) / 255.0)
        inten[ii[(f2 - f1) < 0.1]] *= 0.7
        top = np.clip(nr[ii, 1] - 0.2, 0, 1)
        inten[ii] += 0.12 * top
    m = mat == BELLY
    if m.any():                                      # vientre: placas en bandas
        ii = np.nonzero(m)[0]
        Qr = (P[m] - ro) @ rR
        f1, f2, cid = cells(Qr * np.array([1.0, 1.0, 1.6]), 5.0, 7)
        inten[ii] *= 0.88 + 0.2 * (1 - np.clip(f1, 0, 1))
        inten[ii[(f2 - f1) < 0.1]] *= 0.6
    m = mat == WOOD
    if m.any():
        ii = np.nonzero(m)[0]
        g = vnoise(Q[m] * np.array([1.0, 0.18, 1.0]), 1.6, 13) * 0.6 + vnoise(Q[m] * np.array([0.18, 1.0, 0.18]), 1.6, 14) * 0.4
        inten[ii] *= 0.72 + 0.42 * g
    m = mat == CLOTH
    if m.any():                                      # terciopelo gastado y sucio
        ii = np.nonzero(m)[0]
        inten[ii] *= 0.78 + 0.36 * vnoise(Q[m], 0.45, 17)
        worn = vnoise(Q[m], 1.3, 18) > 0.72
        inten[ii[worn]] *= 1.18
    m = mat == ROPE
    if m.any():
        ii = np.nonzero(m)[0]
        inten[ii] *= 0.75 + 0.4 * (np.sin((Q[m, 0] + Q[m, 1] + Q[m, 2]) * 2.6) > 0)
    apply_shine(mat, inten, spec, ((SHELL, 0.35, 7), (SKIN, 0.25, 6), (SPIKE, 0.3, 7), (HORN, 0.35, 7),
                                   (CLAW, 0.4, 8), (TEETH, 0.3, 6), (TONGUE, 0.8, 10), (MOUTH, 0.4, 8),
                                   (IRON, 0.55, 14), (BRASS, 0.5, 10), (GILT, 0.55, 10), (BLOOD, 0.6, 12)))
    # Ollares.
    for c in extras.get('nostrils', []):
        mm = np.isin(mat, (SKIN,)) & (_len(P - c) < 1.15)
        mat[mm] = SOCKET
    # Ojos: núcleo más claro (o apagados).
    for c, r in extras.get('eyes', []):
        de = _len(P - c)
        mm = (mat == EYE) & (de < r * 1.7)
        lvl_extra[mm] = np.where(de[mm] < r * 0.6, 2, 1)
        lvl_extra[(mat == EYE) & (de >= r * 1.7)] = 0
    # Bocas de los cañones: ánima negra y hollín alrededor.
    #     La cara de la boca queda de hierro claro (hace de aro alrededor del agujero, se lee de frente); el
    #     hollín va por el costado del cañón.
    for tip, ax, rb in extras.get('muzzles', []):
        rel = P - tip
        al = rel @ ax
        perp = _len(rel - np.outer(al, ax))
        face = (nr @ ax) > 0.55
        mm = np.isin(mat, (IRON,)) & (al > -3.2) & ~face
        mat[mm & (vnoise(P, 1.7, 21) > 0.35)] = SOOT
        ff = np.isin(mat, (IRON,)) & face & (al > -0.6)
        inten[ff] = np.maximum(inten[ff] * 1.25, 0.62)
        mat[np.isin(mat, (IRON, SOOT)) & (al > -0.6) & (perp < rb)] = BORE
    # Fogonazos: nivel por distancia al foco más cercano.
    m = mat == FLASH
    if m.any():
        best = np.zeros(m.sum())
        for a_, b_, r in extras.get('flash', []):          # distancia al tramo del eje del fogonazo
            ab = b_ - a_
            u = np.clip((P[m] - a_) @ ab / max(ab @ ab, 1e-9), 0, 1)
            best = np.maximum(best, 1 - _len(P[m] - a_ - np.outer(u, ab)) / r)
        n = len(RAMPS[FLASH])
        lvl_extra[m] = np.clip(best * n * 1.2, 0, n - 1)
    # Sangre sobre piel, caparazón y madera.
    for sc, sr in extras.get('stains', []):
        ds = _len(P - sc)
        mm = np.isin(mat, (SKIN, SHELL, GRIME, BELLY, WOOD, CLOTH, TEETH)) & (ds < sr * (0.75 + 0.5 * nz))
        mat[mm] = BLOOD
    # Quemado y brasas (muerte).
    for c, r in extras.get('char', []):
        ds = _len(P - c)
        mm = np.isin(mat, (WOOD, CLOTH, FRINGE, GILT, WALNUT)) & (ds < r * (0.7 + 0.6 * nz))
        mat[mm] = CHAR
    for c, r in extras.get('embers', []):
        ds = _len(P - c)
        mm = np.isin(mat, (CHAR, CLOTH, WOOD)) & (ds < r) & (vnoise(P, 0.9, 31) > 0.58)
        mat[mm] = EMBER
        lvl_extra[mm] = np.clip((1 - ds[mm] / r) * 7, 0, 5)


# ----------------------------------------------------------------------------- trazado (propio, rápido)
class TRender(Render):
    """Como sdf.Render pero para sprites enormes: SS3 x SS3 submuestras, rayos por trozos, y cada rayo solo
    evalúa los grupos cuya esfera envolvente atraviesa en ese tramo (los demás le dejan avanzar hasta su
    entrada). El resultado es el del trazador común (misma luz, rampas, reducción y contorno)."""

    def __init__(self, ramps, ss=SS3, **kw):
        super().__init__(ramps, **kw)
        self.ss = ss

    def camera(self, angle):
        th = (angle - 1) * math.pi / 4 if angle else 0.0
        R = rot_y(-th)
        Xc = V(1, 0, 0)
        Uc = V(0, math.cos(self.tilt), -math.sin(self.tilt))
        Dc = V(0, -math.sin(self.tilt), -math.cos(self.tilt))
        return R, Xc, Uc, Dc

    def render(self, groups, extras, angle, tile=96, max_it=200):
        S = self.ss
        R, Xc, Uc, Dc = self.camera(angle)
        cen = [g.model_bound() for g in groups]
        xs, ys = [], []
        for c, r in cen:
            cc = R @ c
            xs += [cc[0] - r, cc[0] + r]
            ys += [cc @ Uc - r, cc @ Uc + r]
        hw = int(math.ceil(max(-min(xs), max(xs)))) + 2
        top = int(math.ceil(max(ys))) + 2
        bot = max(int(math.floor(min(ys))) - 2, -60)
        W, H = 2 * hw, top - bot
        jj, ii = np.meshgrid(np.arange(W * S), np.arange(H * S))
        sx = (-hw + (jj + 0.5) / S).ravel()
        sy = (top - (ii + 0.5) / S).ravel()
        N = sx.size
        D = Dc @ R
        O = np.outer(sx, Xc @ R) + np.outer(sy, Uc @ R) - 400 * D
        C = np.array([c for c, r in cen])
        Rr = np.array([r for c, r in cen])
        CS = C @ R.T                                      # centros en cámara: (x pantalla, ·, ·)
        csx, csy = CS @ Xc, CS @ Uc
        hit = np.zeros(N, bool)
        T = np.zeros(N)
        WS, HS_ = W * S, H * S
        for r0 in range(0, HS_, tile):                   # por baldosas: cada una solo mira sus grupos
            for c0 in range(0, WS, tile):
                rr = np.arange(r0, min(r0 + tile, HS_))
                cc = np.arange(c0, min(c0 + tile, WS))
                idx = (rr[:, None] * WS + cc[None, :]).ravel()
                x_lo, x_hi = -hw + c0 / S, -hw + (cc[-1] + 1) / S
                y_hi, y_lo = top - r0 / S, top - (rr[-1] + 1) / S
                ddx = np.maximum(np.maximum(x_lo - csx, csx - x_hi), 0)
                ddy = np.maximum(np.maximum(y_lo - csy, csy - y_hi), 0)
                gl = np.nonzero(ddx * ddx + ddy * ddy < Rr * Rr)[0]
                if not len(gl):
                    continue
                Oc = O[idx]
                n = len(Oc)
                G = len(gl)
                T0 = np.full((G, n), np.inf)
                T1 = np.full((G, n), -np.inf)
                for gi, g in enumerate(gl):
                    oc = Oc - C[g]
                    b = oc @ D
                    disc = b * b - (np.einsum('ij,ij->i', oc, oc) - Rr[g] * Rr[g])
                    ok = disc > 0
                    sq = np.sqrt(np.maximum(disc, 0))
                    T0[gi, ok] = (-b - sq)[ok]
                    T1[gi, ok] = (-b + sq)[ok]
                act = np.nonzero((T1 > 0).any(0))[0]
                if not len(act):
                    continue
                t = np.zeros(n)
                t[act] = np.maximum(np.where(T1[:, act] > 0, T0[:, act], np.inf).min(0), 0)
                tend = T1.max(0)
                hc = np.zeros(n, bool)
                for _ in range(max_it):
                    if not len(act):
                        break
                    ta = t[act]
                    Pa = Oc[act] + D * ta[:, None]
                    ahead = T0[:, act] - ta
                    inside = (ahead <= 1.0) & (ta <= T1[:, act])
                    d = np.where(ahead > 1.0, ahead, np.inf).min(0)
                    for gi in np.nonzero(inside.any(1))[0]:
                        s = np.nonzero(inside[gi])[0]
                        dg, _ = groups[gl[gi]].eval(Pa[s])
                        d[s] = np.minimum(d[s], dg)
                    h = d < 0.01
                    hc[act[h]] = True
                    t[act] += np.where(h, 0, np.maximum(d * 0.8, 0.004))
                    act = act[(~h) & (t[act] < tend[act])]
                hit[idx] = hc
                T[idx] = t
        hidx = np.nonzero(hit)[0]
        P = O[hidx] + D * T[hidx, None]
        # Grupos cercanos a algún punto de choque (para no evaluar los demás en normales y oclusión).
        near = [g for g, (c, r) in zip(groups, cen) if len(P) and (_len(P - c) - r).min() < 4.0]
        _, mat = scene_eval(near, P)
        e = 0.04
        nr = np.zeros_like(P)
        for k in range(3):
            dv = np.zeros(3)
            dv[k] = e
            nr[:, k] = scene_eval(near, P + dv)[0] - scene_eval(near, P - dv)[0]
        nr /= np.maximum(_len(nr), 1e-9)[:, None]
        occ = np.zeros(len(P))
        for hgt, w in ((0.7, 1.0), (1.6, 0.7), (3.0, 0.45)):
            dd = scene_eval(near, P + nr * hgt)[0]
            occ += w * np.clip((hgt - dd) / hgt, 0, 1)
        ao = np.clip(1 - 0.42 * occ, 0.3, 1)
        L = nrm((-0.5, 0.75, 0.55)) @ R
        Vv = -D
        diff = np.clip(nr @ L, 0, 1)
        inten = (0.24 + 0.86 * diff) * ao
        nz = vnoise(P, 0.9, 1) * 0.6 + vnoise(P, 2.3, 2) * 0.4
        inten *= 0.82 + 0.36 * nz
        refl = 2 * (nr @ L)[:, None] * nr - L
        spec = np.clip(refl @ Vv, 0, 1)
        lvl_extra = np.zeros(len(P))
        if self.hook is not None:
            self.hook(P, mat, inten, nz, nr, spec, lvl_extra, extras)
        idxs = np.zeros(len(P), int)
        for mm, ramp in self.ramps.items():
            m = mat == mm
            if not m.any():
                continue
            n = len(ramp)
            if mm in self.level_mats:
                lv = np.clip(lvl_extra[m], 0, n - 1)
            else:
                lv = np.clip(np.floor(inten[m] * n), 0, n - 1)
            idxs[m] = np.array(ramp)[lv.astype(int)]
        fl = extras.get('flash_light')
        if fl is not None:
            lp, lr = fl
            rel = lp - P
            dl = _len(rel)
            ndl = np.clip(np.einsum('ij,ij->i', nr, rel / dl[:, None]), 0, 1)
            amt = np.clip(1 - dl / lr, 0, 1) ** 1.3 * (0.35 + 0.65 * ndl)
            m = (amt > 0.08) & ~np.isin(mat, self.no_light)
            cache = {}
            for k in np.nonzero(m)[0]:
                key = (idxs[k], int(amt[k] * 8))
                if key not in cache:
                    base = self.palarr[idxs[k]]
                    a = key[1] / 8
                    cache[key] = self.nearest(base * (1 + 0.5 * a) + a * np.array([230, 140, 40]))
                idxs[k] = cache[key]
        IDX = np.full(N, -1, int)
        IDX[hidx] = idxs
        MAT = np.full(N, -1, int)
        MAT[hidx] = mat
        DEP = np.full(N, np.inf)
        DEP[hidx] = T[hidx]
        out, depth, mout = self.downsample3(IDX.reshape(H * S, W * S), MAT.reshape(H * S, W * S),
                                            DEP.reshape(H * S, W * S), W, H)
        fm = mout == FLASH                                 # el fogonazo es plano: sin líneas por dentro
        if fm.any():
            depth[fm] = depth[fm].min()
        cam = dict(R=R, Xc=Xc, Uc=Uc, D=D, hw=hw, top=top, W=W, H=H)
        return out, depth, cam

    def downsample3(self, IDX, MAT, DEP, W, H):
        S = self.ss
        K = S * S
        I = IDX.reshape(H, S, W, S).transpose(0, 2, 1, 3).reshape(H, W, K)
        M = MAT.reshape(H, S, W, S).transpose(0, 2, 1, 3).reshape(H, W, K)
        Dp = DEP.reshape(H, S, W, S).transpose(0, 2, 1, 3).reshape(H, W, K)
        out = np.full((H, W), -1, int)
        mout = np.full((H, W), -1, int)
        depth = np.full((H, W), np.inf)
        cov = (I >= 0).sum(2)
        need = max(2, int(round(K * 0.4)))                 # 6/16 en el trazador común
        cmin = max(2, int(round(K * 0.3)))
        for y, x in zip(*np.nonzero(cov >= need)):
            ii, mm, dd = I[y, x], M[y, x], Dp[y, x]
            sel = ii >= 0
            ii, mm, dd = ii[sel], mm[sel], dd[sel]
            mats, counts = np.unique(mm, return_counts=True)
            choice = None
            for em in self.emissive:
                if em in mats and counts[list(mats).index(em)] >= 2:
                    choice = em
            if choice is None:
                cand = [(dd[mm == q].mean(), q) for q, c in zip(mats, counts) if c >= cmin or c == counts.max()]
                choice = min(cand)[1]
            pick = ii[mm == choice]
            vals, vc = np.unique(pick, return_counts=True)
            best = vals[vc == vc.max()]
            out[y, x] = int(best[np.argmax(self.palarr[best].sum(1))])
            depth[y, x] = dd[mm == choice].min()
            mout[y, x] = choice
        return out, depth, mout


RENDERS = {}


def render(tilt=TILT, ss=SS3):
    key = (round(tilt, 5), ss)
    if key not in RENDERS:
        RENDERS[key] = TRender(RAMPS, ss=ss, hook=materiales, level_mats=(EYE, FLASH, EMBER), emissive=EMISSIVE,
                               no_light=(FLASH, EYE, SOCKET, BORE, EMBER, MOUTH), tilt=tilt)
    return RENDERS[key]


# ----------------------------------------------------------------------------- medidas (1 unidad ≈ 1 px)
BODY_Y = 25.0                          # centro del cuerpo sobre el suelo
DOME_C, DOME_R = V(0.0, 2.0, -3.0), V(46.0, 33.0, 58.0)    # caparazón (marco del cuerpo)
RIM_Y = -4.5                           # borde del caparazón
LEG_Z = (30.0, -3.0, -36.0)            # caderas: delante, en medio, detrás
HIP_X, HIP_Y = 31.0, -8.0
FOOT = ((55.0, 37.0), (65.0, -3.0), (55.0, -43.0))         # pies en el suelo (x, z) por defecto
THIGH, SHIN = 19.0, 15.5
ANKLE_Y = 4.2
DECK_C, DECK_H = V(0.0, 33.6, -4.0), V(25.0, 1.8, 31.0)    # tablero de la carroza (marco del cuerpo)
POST_H = 16.0                          # altura de los postes sobre el tablero
RAIL_AT = 14.5                         # altura de la baranda sobre el tablero
POST_XZ = [(23.3, 28.6), (23.3, 0.0), (23.3, -28.6), (-23.3, 28.6), (-23.3, 0.0), (-23.3, -28.6)]
GUN_AT = V(0.0, 25.0, 9.0)             # centro del cajón del arma (marco del tablero)
GS = 1.3                               # escala del arma
GUN_HALF = V(8.6, 5.0, 9.0)
NBAR = 7                               # cañones en corona (batería giratoria): de frente, un anillo de bocas
RC, RB = 4.7, 1.6                      # radio de la corona y de cada cañón
LB = 19.0                              # largo de los cañones por delante del cajón
ROT_A = 90.0                           # giro de la corona (un cañón arriba); en H gira medio paso
ODD, EVEN = (0, 2, 4, 6), (1, 3, 5)
SINK = 3                               # el suelo del modelo queda SINK px por debajo del origen
HS = 1.35                              # escala de la cabeza (se piensa a 1:1 y se agranda: se lee de lejos)
LIFT_TO = -4.0                         # muertes: lo que yace delante no baja más de esto bajo la línea del suelo
                                       # (el cuerpo tumbado ya llega a unas -6: la cabeza sube solo un poco)


# ----------------------------------------------------------------------------- utilidades
def surface_exit(group, a, dirv, hi=30.0):
    """Primer punto de salida del grupo desde a (dentro) en la dirección dirv."""
    lo = 0.0
    for _ in range(32):
        mid = (lo + hi) / 2
        if group.eval((a + dirv * mid)[None])[0][0] < 0:
            lo = mid
        else:
            hi = mid
    return a + dirv * lo


def bezier(p0, p1, p2, t):
    return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t * t * p2


def spike(base, d, length, r0, parts, inset=1.2, mid=0.45):
    """Pincho de cuerno: base oscura y punta de hueso."""
    d = nrm(d)
    a = base - d * inset
    m = base + d * length * mid
    tip = base + d * length
    parts += [CappedCone(a, m, r0, r0 * 0.5, SPIKEB), RoundCone(m, tip, r0 * 0.5, 0.22, SPIKE)]


# ----------------------------------------------------------------------------- pose por defecto
DEFAULT = dict(
    yaw=0.0, shift=(0.0, 0.0), bob=0.0, pitch=0.0, roll=0.0,
    legs=None,                             # {'L1': spec, ...}; spec ('ground', (x, z), alzada) | ('body', A, fdir)
    npitch=0.0, nyaw=0.0, hpitch=-6.0, hyaw=0.0, hroll=0.0, jaw=17.0, tongue=0.0,
    eyes='on', eye_r=2.5,
    tail_sway=0.0, tail_phase=0.0, tail_up=0.0,
    deck=(0.0, 0.0, 0.0),                  # (alabeo, cabeceo, caída) del tablero respecto al caparazón
    deck_break=0.0,                        # grados que cae cada mitad del tablero partido (o (izq., der.))
    deck_slide=((0.0, 0.0), (0.0, 0.0)),   # (hacia fuera, hacia abajo) que resbala cada mitad (izq., der.)
    posts=(0, 0, 0, 0, 0, 0),              # inclinación (grados) o ('roto', altura del tocón)
    banners=(True, True), sway=0.0, valance_tear=1.0,
    gun=('mount', 0.0, -4.0, 0.0, 0.0),    # ('mount', retroceso, cabeceo, guiñada, alabeo) | ('free', Frame raíz)
    gun_rot=ROT_A,                         # giro de la corona de cañones (grados)
    fire=None,                             # cañones que disparan (índices)
    smoke_bar=(),                          # cañones que humean (bocanadas 3D pequeñas)
    stains=(), spray=(), pool=None, debris=(), char=(), embers=(),
    smoke2d=(),                            # columnas de humo 2D: (marco, punto, fuerza, altura, deriva)
    flatten=None, tilt=10.0,
    view=None,                             # (hacia la cámara en horizontal, tan inclinación): apoyo «de pintor»
    auto_lift=False, lifts=None,           # muertes: subir lo que yace en el suelo (cabeza, arma, restos, charco)
)


def leg_specs(over=None):
    out = {}
    for k, (fx, fz) in enumerate(FOOT):
        out[f'L{k + 1}'] = ('ground', (fx, fz), 0.0)
        out[f'R{k + 1}'] = ('ground', (-fx, fz), 0.0)
    if over:
        out.update(over)
    return out


# ----------------------------------------------------------------------------- modelo
def build(pose):
    p = dict(DEFAULT)
    p.update(pose)
    root = Frame((p['shift'][0], 0.0, p['shift'][1]), rot_y(rad(p['yaw'])))
    B = root * Frame((0, BODY_Y + p['bob'], 0), rot_x(rad(p['pitch'])) @ rot_z(rad(p['roll'])))
    extras = {'body': (B.o, B.R), 'root': (root.o, root.R), 'eyes': [], 'nostrils': [], 'muzzles': [],
              'flash': [], 'stains': [], 'char': [], 'embers': []}
    groups = []

    def where(fr, pt):
        return {'body': B.p, 'root': root.p}[fr](pt)

    # Apoyo «de pintor» (como los sprites de Doom): con la cámara a 10° lo que pisa el suelo más cerca de la
    # cámara caería por debajo de la línea del suelo; se sube justo lo que baja por la perspectiva
    # (profundidad x tan 10°), así todo lo que apoya queda en la línea del suelo del eje y el cuerpo no se mueve.
    axis_w = root.p((0, 0, 0))
    view = p['view']

    def depth(pt):
        return 0.0 if view is None else float((pt - axis_w) @ view[0])

    def lift_for(pt):
        return 0.0 if view is None else max(0.0, depth(pt)) * view[1]

    # --- caparazón: cúpula de placas con el borde vuelto; por debajo, piel y peto
    dome = Ellipsoid(B.p(DOME_C), DOME_R, B.M(), SHELL)
    dome.cut = lambda P, B=B: RIM_Y - B.to_local(P)[:, 1]
    sy = RIM_Y - DOME_C[1]
    s = math.sqrt(1 - (sy / DOME_R[1]) ** 2)
    rim = Ring(Frame(B.p((DOME_C[0], RIM_Y, DOME_C[2])), B.M()), DOME_R[0] * s + 0.4, DOME_R[2] * s + 0.4, 3.0, SHELL)
    shell = Grp([dome, rim], k=1.5, name='shell')
    groups.append(shell)
    under = [Ellipsoid(B.p((0, -7.0, -3.0)), (40.0, 9.0, 52.0), B.M(), SKIN),
             Ellipsoid(B.p((0, -11.0, -3.0)), (33.0, 6.5, 45.0), B.M(), BELLY)]
    groups.append(Grp(under, k=2.0, name='under'))

    # --- pinchos del caparazón (dos coronas, fuera del tablero, sin tapar cuello ni cola)
    sp_groups = {}
    for ring_i, (elev, step, off, ln, r0) in enumerate(((38.0, 30.0, 15.0, 11.0, 3.6), (14.0, 30.0, 0.0, 9.0, 3.2))):
        for k in range(12):
            az = off + step * k
            azn = ((az + 180) % 360) - 180
            if ring_i == 1 and (abs(azn) < 26 or abs(azn) > 158):
                continue
            if ring_i == 0 and abs(azn) < 12:
                continue
            ce, se = math.cos(rad(elev)), math.sin(rad(elev))
            dl = nrm((ce * math.sin(rad(az)), se, ce * math.cos(rad(az))))
            q = DOME_C + dl * 0.0
            # punto de la superficie de la cúpula en esa dirección (elipsoide exacto)
            u = dl / DOME_R
            tq = 1.0 / math.sqrt(u @ u)
            sp = DOME_C + dl * tq
            nn = nrm((sp - DOME_C) / (DOME_R * DOME_R))
            dirv = nrm(nn + V(0, 0.35, 0) - V(0, 0, 0.18) * np.sign(dl[2]) * 0)
            if abs(sp[0]) < DECK_H[0] + 3 and abs(sp[2] - DECK_C[2]) < DECK_H[2] + 3:
                continue
            key = ('L' if sp[0] > 0 else 'R') + ('F' if sp[2] > -3 else 'B') + str(ring_i)
            spike(B.p(sp), B.d(dirv), ln, r0, sp_groups.setdefault(key, []))
    for key, parts in sp_groups.items():
        groups.append(Grp(parts, k=0.3, name='spikes'))

    # --- seis patas cortas y gruesas, abiertas a los lados, con garras y espolón en el codo
    legs = p['legs'] or leg_specs()
    for side, sname in ((1, 'L'), (-1, 'R')):
        for k in range(3):
            spec = legs[f'{sname}{k + 1}']
            S = B.p((side * HIP_X, HIP_Y, LEG_Z[k]))
            if spec[0] == 'ground':
                (x, z), lift = spec[1], spec[2]
                A = root.p((x, ANKLE_Y + lift, z))
                fdir = root.d(nrm((side * (0.35 + 0.15 * (k == 1)), -0.25 * min(lift / 4.0, 1.0), 1.0)))
                fup = root.d((0, 1, 0))
                sv_ = nrm(np.cross(fup, fdir))                   # garras, talón y costados del pie, en la línea
                A = A + fup * max(lift_for(A + fdir * 12.0), lift_for(A - fdir * 5.5),
                                  lift_for(A + sv_ * 6.5), lift_for(A - sv_ * 6.5))
            else:                                    # ('body'|'root', tobillo, dirección del pie[, arriba])
                fr = B if spec[0] == 'body' else root
                A = fr.p(spec[1])
                fdir = fr.d(nrm(spec[2]))
                fup = fr.d(spec[3]) if len(spec) > 3 else root.d((0, 1, 0))
            fup = nrm(fup - fdir * (fup @ fdir))
            pole = B.d(nrm((side * 1.0, 0.9, 0.1)))
            K = ik(S, A, THIGH, SHIN, pole)
            parts = [RoundCone(S, K, 8.6, 7.0, SKIN), Sphere(K, 7.0, SKIN), RoundCone(K, A, 6.6, 5.6, SKIN),
                     Ellipsoid(A + fdir * 2.6 - fup * 1.1, (6.3, 3.4, 7.4), basis(fdir, fup), SKIN)]
            groups.append(Grp(parts, k=2.2, name='leg'))
            sv = nrm(np.cross(fup, fdir))
            claws = []
            for j, off in enumerate((-1.5, -0.5, 0.5, 1.5)):
                base = A + fdir * 7.4 + sv * off * 2.9 - fup * 1.6
                d1 = nrm(fdir + sv * off * 0.22 - fup * 0.12)
                tip = base + d1 * 4.4 - fup * 1.7
                claws.append(RoundCone(base, tip, 1.45, 0.25, CLAW))
            out = nrm(K - S)
            groups.append(Grp(claws, k=0.2, name='claws'))
            elbow = []
            spike(K, nrm(out * 0.6 + B.d((side * 0.6, 0.3, -0.5))), 7.5, 2.4, elbow, inset=2.0)
            groups.append(Grp(elbow, k=0.2, name='elbow'))

    # --- cuello largo con cresta
    Rn = rot_y(rad(p['nyaw'])) @ rot_x(rad(-p['npitch']))
    P0 = V(0.0, -2.0, 42.0)
    P1 = P0 + Rn @ (V(0.0, 4.0, 60.0) - P0)
    P2 = P0 + Rn @ (V(0.0, 15.0, 74.0) - P0)
    lifts = p['lifts'] or {}
    if lifts.get('head'):                  # la cabeza yace más cerca de la cámara: sube con el cuello
        P0 = P0 + V(0, 0.25 * lifts['head'], 0)
        P1 = P1 + V(0, 0.6 * lifts['head'], 0)
        P2 = P2 + V(0, lifts['head'], 0)
    n_head0 = len(groups)
    radii = [13.0, 12.2, 11.4, 10.6, 10.0, 9.6]
    pts = [B.p(bezier(P0, P1, P2, t)) for t in np.linspace(0, 1, 6)]
    neck = [RoundCone(pts[i], pts[i + 1], radii[i], radii[i + 1], SKIN) for i in range(5)]
    throat = [Ellipsoid(B.p(bezier(P0, P1, P2, 0.5)) + B.d(Rn @ V(0, -5.0, 0)), (7.8, 5.2, 12.0),
                        B.M(Rn @ basis(nrm(P2 - P0))), BELLY)]
    Hd = B * Frame(P2, Rn @ rot_y(rad(p['hyaw'])) @ rot_x(rad(-p['hpitch'])) @ rot_z(rad(p['hroll'])))
    H = Hd.M()

    def hp(q):
        return Hd.p(V(q) * HS)
    cran = Ellipsoid(hp((0, 3.5, 3.5)), V(9.5, 8.5, 10.5) * HS, H, SKIN)
    groups.append(Grp(neck + throat + [cran], k=3.0, name='neck'))
    crest = []
    for t in np.linspace(0.05, 0.8, 6):
        c = bezier(P0, P1, P2, t)
        tg = nrm(bezier(P0, P1, P2, t + 0.02) - c)
        up = nrm(V(0, 1, 0) - tg * tg[1])
        r = np.interp(t, np.linspace(0, 1, 6), radii)
        base = B.p(c + up * (r - 1.0))
        spike(base, B.d(nrm(up - tg * 0.6)), 9.0 - 3.0 * t, 3.3 - 1.0 * t, crest, inset=1.2)
    groups.append(Grp(crest, k=0.3, name='crest'))

    # --- cabeza de dragona: cráneo, hocico, cejas, pómulos, cuernos; mandíbula con bisagra (HS: escala)
    head = [cran,
            Ellipsoid(hp((0, 2.4, 17.0)), V(7.2, 5.2, 12.0) * HS, H, SKIN),
            Ellipsoid(hp((0, 2.8, 27.0)), V(5.6, 4.6, 5.0) * HS, H, SKIN)]
    for sx in (-1, 1):
        head += [Ellipsoid(hp((5.4 * sx, 8.4, 11.0)), V(3.6, 2.5, 7.4) * HS, H @ rot_y(rad(14 * sx)) @ rot_x(rad(8)), SKIN),
                 Ellipsoid(hp((7.2 * sx, 0.5, 5.5)), V(4.0, 5.0, 6.6) * HS, H, SKIN),
                 Sphere(hp((2.9 * sx, 6.3, 28.0)), 2.0 * HS, SKIN)]
    hg = Grp(head, k=1.6 * HS, name='head')
    groups.append(hg)
    for sx in (-1, 1):
        extras['nostrils'].append(hp((2.9 * sx, 7.4, 29.2)))
    jaw = p['jaw']
    J = Hd * Frame(V(0, -1.4, 4.0) * HS, rot_x(rad(jaw)))
    Jm = Hd * Frame(V(0, -1.4, 4.0) * HS, rot_x(rad(jaw * 0.5)))

    def jp(q, F=J):
        return F.p(V(q) * HS)
    jawp = [Ellipsoid(jp((0, -2.6, 12.5)), V(6.3, 3.2, 12.0) * HS, J.M(), SKIN),
            Ellipsoid(jp((0, -2.4, 23.8)), V(4.5, 2.8, 4.2) * HS, J.M(), SKIN),
            Ellipsoid(jp((0, -4.2, 9.0)), V(4.6, 2.2, 8.0) * HS, J.M(), BELLY)]
    jg = Grp(jawp, k=1.2 * HS, name='jaw')
    groups.append(jg)
    mouth = [Ellipsoid(jp((0, -0.6, 14.0), Jm), V(5.0, 0.8 + 0.13 * jaw, 12.0) * HS, Jm.M(), MOUTH)]
    tg_ = p['tongue']
    mouth.append(RoundCone(jp((0, -1.2, 6.0)), jp((0, -0.7, 19.0)), 2.5 * HS, 1.7 * HS, TONGUE))
    if tg_ > 0:                                   # lengua fuera, bífida
        a = jp((0, -0.7, 19.0))
        b = jp((0, -1.2 - 3.0 * tg_, 19.0 + 10.0 * tg_))
        mouth.append(RoundCone(a, b, 1.7 * HS, 1.2 * HS, TONGUE))
        for sx in (-1, 1):
            mouth.append(RoundCone(b, b + J.d(V(1.8 * sx, -1.4 * tg_, 3.5 * tg_) * HS), 1.0 * HS, 0.35 * HS, TONGUE))
    groups.append(Grp(mouth, k=0.8, name='mouth'))
    teeth = []
    for sx in (-1, 1):
        for k in range(7):
            z = 9.0 + 2.85 * k
            xin = 4.3 - 0.33 * k
            big = k == 5
            ln = (4.8 if big else 3.0 + 0.3 * (k % 2)) * HS
            r = (1.25 if big else 0.95) * HS
            a = surface_exit(hg, hp((xin * sx, 2.0, z)), Hd.d(nrm((0.25 * sx, -1, 0))), 16.0)
            teeth.append(RoundCone(a + Hd.d((0, 0.9, 0)), a + Hd.d((0.15 * sx, -ln, 0.6)), r, 0.2, TEETH))
            zl = 8.5 + 2.75 * k
            b = surface_exit(jg, jp((xin * 0.92 * sx, -2.4, zl)), J.d(nrm((0.25 * sx, 1, 0))), 16.0)
            lnl = (3.8 if k == 6 else 2.5 + 0.3 * ((k + 1) % 2)) * HS
            teeth.append(RoundCone(b - J.d((0, 0.8, 0)), b + J.d((0.1 * sx, lnl, 0.5)), (0.9 if k < 6 else 1.15) * HS,
                                   0.2, TEETH))
    groups.append(Grp(teeth, name='teeth'))
    horns = []
    for sx in (-1, 1):
        hpts = [(5.5, 9.0, 1.5), (7.4, 12.6, -4.0), (8.8, 15.2, -10.5), (9.4, 16.4, -16.5), (8.9, 16.1, -21.0)]
        hr = [3.1, 2.5, 1.8, 1.1, 0.35]
        q = [hp((x * sx, y, z)) for x, y, z in hpts]
        horns += [RoundCone(q[i], q[i + 1], hr[i] * HS, hr[i + 1] * HS, HORN) for i in range(4)]
        a = hp((8.6 * sx, 1.5, 1.5))
        horns.append(RoundCone(a, a + Hd.d(V(5.2 * sx, 1.6, -6.0) * HS), 1.7 * HS, 0.25, HORN))   # púa del pómulo
    groups.append(Grp(horns, k=0.6, name='horns'))
    if p['eyes'] != 'none':
        eyes = []
        for sx in (-1, 1):
            a = hp((3.6 * sx, 6.0, 12.5))
            dv = Hd.d(nrm((0.72 * sx, 0.18, 0.62)))
            c = surface_exit(hg, a, dv)
            r = p['eye_r']
            if p['eyes'] == 'dead':
                eyes.append(Sphere(c - dv * 0.35, r * 0.9, DEADEYE))
            else:
                eyes += [Sphere(c - dv * 0.75, r * 1.25, SOCKET), Sphere(c + dv * 0.05, r, EYE)]
                extras['eyes'].append((c + dv * 0.05, r))
        groups.append(Grp(eyes, name='eyes'))

    # --- cola de serpiente que arrastra
    sw, ph, tu = p['tail_sway'], p['tail_phase'], p['tail_up']
    tpts = [B.p((0, -2.0, -50.0)), B.p((0, -7.0, -69.0))]
    for k, (y, z) in enumerate(((5.0 + 5 * tu, -86.0), (4.0 + 6 * tu, -101.0), (3.0 + 4 * tu, -113.0),
                                (2.0 + 2 * tu, -122.0), (1.2 + tu, -128.0))):
        x = sw * math.sin(ph + 0.95 * (k + 1)) * (0.35 + 0.3 * k)
        tpts.append(root.p((x, y, z)))
    trad = [12.5, 10.8, 8.4, 6.4, 4.5, 2.6, 0.6]
    if view is not None:                   # la cola, que arrastra, también sube lo que baja por la perspectiva
        ct, st_ = 1.0 / math.sqrt(1 + view[1] ** 2), view[1] / math.sqrt(1 + view[1] ** 2)
        fy = root.p((0, 0, 0))[1]
        phis = np.linspace(-math.pi, math.pi, 48)

        def lowest(y, d, r):
            py = y + r * np.sin(phis)
            pd = d + r * np.cos(phis)
            cutd = d + math.sqrt(max(r * r - y * y, 0.0))
            pd = np.where(py < 0, cutd, pd)
            py = np.maximum(py, 0)
            return (py * ct - pd * st_).min()
        prev = 0.0
        for i in range(len(tpts)):
            y, d, r = tpts[i][1] - fy, depth(tpts[i]), trad[i]
            lo_, hi_ = 0.0, 40.0
            if lowest(y, d, r) < -0.5:
                for _ in range(24):
                    mid = (lo_ + hi_) / 2
                    if lowest(y + mid, d, r) < -0.5:
                        lo_ = mid
                    else:
                        hi_ = mid
                lo_ = hi_
            prev = max(lo_, prev * 0.85)
            tpts[i] = tpts[i] + root.d((0, 1, 0)) * prev
    tail = [RoundCone(tpts[i], tpts[i + 1], trad[i], trad[i + 1], SKIN) for i in range(len(tpts) - 1)]
    for j in range(0, len(tail), 2):
        groups.append(Grp(tail[j:j + 2], k=2.0, name='tail'))
    tsp = []
    for i in range(1, 4):
        c = (tpts[i] + tpts[i + 1]) / 2
        tg = nrm(tpts[i + 1] - tpts[i])
        up = nrm(V(0, 1, 0) - tg * tg[1])
        r = (trad[i] + trad[i + 1]) / 2
        spike(c + up * (r - 0.8), nrm(up - tg * 0.5), 6.0 - 1.2 * i, 2.4 - 0.4 * i, tsp, inset=1.0)
    groups.append(Grp(tsp, k=0.3, name='tail_spikes'))
    for g in groups[n_head0:]:
        if g.name in ('head', 'jaw', 'mouth', 'teeth', 'horns', 'eyes'):
            g.lk = 'head'

    # --- carroza: tablero, moldura dorada, faldón rojo con flecos, barandilla, telas, sogas. Al morir el
    #     tablero se parte por la quilla del caparazón y cada mitad (con sus postes y su faldón) cae hacia fuera.
    roll_d, pitch_d, drop_d = p['deck']
    brk = p['deck_break']
    brk_l, brk_r = brk if isinstance(brk, tuple) else (brk, brk)
    brk = max(brk_l, brk_r)
    (sl_o, sl_d), (sr_o, sr_d) = p['deck_slide']
    hx, hy, hz = DECK_H
    Dk = B * Frame(DECK_C - V(0, drop_d, 0), rot_z(rad(roll_d)) @ rot_x(rad(pitch_d)))
    # cada mitad gira por la quilla y además puede resbalar hacia fuera y abajo por la cúpula
    half = {1: Dk * Frame((sl_o, -hy - sl_d, 0), rot_z(rad(-brk_l))) * Frame((0, hy, 0)),
            -1: Dk * Frame((-sr_o, -hy - sr_d, 0), rot_z(rad(brk_r))) * Frame((0, hy, 0))}
    if brk <= 0:
        deck = [Box(Dk.p((0, 0, 0)), DECK_H, Dk.M(), 0.4, WOOD),
                Box(Dk.p((0, 0.5, 0)), (hx + 0.55, 0.75, hz + 0.55), Dk.M(), 0.3, GILT)]
        groups.append(Grp(deck, name='deck'))
    else:
        for s, Dh in half.items():
            deck = [Box(Dh.p((s * hx / 2, 0, 0)), (hx / 2 - 0.4, hy, hz), Dh.M(), 0.4, WOOD),
                    Box(Dh.p((s * (hx / 2 + 0.3), 0.5, 0)), (hx / 2 + 0.25, 0.75, hz + 0.55), Dh.M(), 0.3, GILT)]
            for k in range(5):                               # astillas en la rotura
                z = -hz + 3 + k * (2 * hz - 6) / 4
                deck.append(RoundCone(Dh.p((s * 0.4, 0.0, z)), Dh.p((-s * 1.2, 1.6 + 0.8 * (k % 2), z + 1.0)), 0.7, 0.15, WOOD))
            groups.append(Grp(deck, k=0.3, name='deck'))
    val, fri = [], []
    sides = [((0, -hy + 0.4, hz + 0.6), 0.0, hx + 0.6), ((0, -hy + 0.4, -hz - 0.6), 180.0, hx + 0.6),
             ((hx + 0.6, -hy + 0.4, 0), 90.0, hz + 0.6), ((-hx - 0.6, -hy + 0.4, 0), -90.0, hz + 0.6)]
    for si, (o, ay, w) in enumerate(sides):
        for xr in ((-w, 0.0), (0.0, w)):
            # mitad del tablero a la que pertenece este trozo de tela (x del tablero de su centro)
            xm = o[0] if si >= 2 else (xr[0] + xr[1]) / 2 * (1 if si == 0 else -1)
            Dh = half[1 if xm > 0 else -1]
            F = Dh * Frame(o, rot_y(rad(ay)))
            val.append(Grp([Curtain(F, w, 10.0, CLOTH, amp=0.9, k=0.75, ph=si * 1.3, flare=0.1,
                                    tear=3.2 * p['valance_tear'], seed=40 + si, holes=0.12 * p['valance_tear'], xr=xr)],
                           name='valance'))
            Ff = Dh * Frame((o[0] * (1 + 0.4 / max(abs(o[0]), 1e-6)) if o[0] else 0, -0.1,
                             o[2] * (1 + 0.4 / max(abs(o[2]), 1e-6)) if o[2] else 0), rot_y(rad(ay)))
            fxr = (xr[0] - 0.3, xr[1]) if xr[0] < 0 else (xr[0], xr[1] + 0.3)
            fri.append(Grp([Curtain(Ff, w + 0.3, 3.6, FRINGE, amp=0.25, k=1.1, flare=0.05, thick=0.5, threads=1.15,
                                    seed=60 + si, xr=fxr)], name='fringe'))
    groups += val + fri
    # Sogas que atan el armazón al caparazón (dos cinchas alrededor de la cúpula).
    for zr in (16.0, -24.0):
        zz = (zr - DOME_C[2]) / DOME_R[2]
        sc = math.sqrt(1 - zz * zz)
        rx, ry = DOME_R[0] * sc + 0.9, DOME_R[1] * sc + 0.9
        for sx in (-1, 1):
            angs = np.linspace(math.asin((RIM_Y + 1.5 - DOME_C[1]) / ry), 1.25, 7)
            q = [B.p((sx * rx * math.cos(t), DOME_C[1] + ry * math.sin(t), zr)) for t in angs]
            groups.append(Grp([RoundCone(q[i], q[i + 1], 1.25, 1.25, ROPE) for i in range(6)], k=0.3, name='ropes'))
    # Postes torneados con remate de bola, baranda, balaustres.
    post_top, post_base = {}, {}
    for i, (px, pz) in enumerate(POST_XZ):
        st = p['posts'][i]
        Dh = half[1 if px > 0 else -1]
        base = Dh.p((px, hy, pz))
        post_base[i] = (base, Dh)
        if isinstance(st, tuple):                         # roto: queda el tocón astillado
            hgt = st[1]
            up = Dh.d((0, 1, 0))
            parts = [Box(base + up * 1.2, (1.9, 1.2, 1.9), Dh.M(), 0.3, WOOD),
                     RoundCone(base, base + up * hgt, 1.5, 1.2, WOOD),
                     RoundCone(base + up * hgt, base + up * (hgt + 2.2) + Dh.d((0.6, 0, 0.4)), 0.9, 0.2, WOOD)]
            groups.append(Grp(parts, k=0.4, name='post'))
            post_top[i] = None
            continue
        lean = rad(st)
        out = V(np.sign(px), 0, 0) if abs(pz) < 1 else nrm(V(np.sign(px) * 0.6, 0, np.sign(pz)))
        ax = np.cross(V(0, 1, 0), out)
        Rp = Dh.M() @ sdf.rot_axis(ax, lean)
        up = Rp[:, 1]
        parts = [Box(base + up * 1.2, (1.9, 1.2, 1.9), Rp, 0.3, WOOD),
                 RoundCone(base + up * 2.0, base + up * POST_H, 1.45, 1.25, WOOD),
                 Sphere(base + up * 5.0, 2.05, WOOD), Sphere(base + up * 10.8, 1.8, WOOD),
                 Box(base + up * POST_H, (1.9, 0.9, 1.9), Rp, 0.3, WOOD)]
        fin = [Sphere(base + up * (POST_H + 2.4), 1.85, GILT),
               RoundCone(base + up * (POST_H + 3.6), base + up * (POST_H + 6.2), 0.9, 0.12, GILT)]
        groups.append(Grp(parts, k=0.6, name='post'))
        groups.append(Grp(fin, k=0.3, name='finial'))
        post_top[i] = base + up * RAIL_AT
    rails, spind = [], []
    rng = np.random.default_rng(7)

    def hanging(pa, da, db, Dh, reach):
        """Baranda rota: cuelga del poste que queda hasta reach (fracción) del tramo, con algunos balaustres."""
        end = da + (db - da) * reach + Dh.d((0, 1.5, 0))
        rails.append([RoundCone(pa, end, 1.0, 0.9, WOOD)])
        spind.append([])
        n = int(np.linalg.norm(db - da) / 5.4)
        for j in range(1, n):
            u = j / n
            if u > reach - 0.05 or rng.random() < 0.3:
                continue
            spind[-1].append(RoundCone(da + (db - da) * u, pa + (end - pa) * (u / reach), 0.75, 0.75, WOOD))
    for a_, b_ in ((0, 1), (1, 2), (3, 4), (4, 5), (0, 3), (2, 5)):
        pa, pb = post_top[a_], post_top[b_]
        (da, Da), (db, Db) = post_base[a_], post_base[b_]
        cross = a_ in (0, 2) and b_ in (3, 5)
        if cross and brk > 0:                              # el tablero se ha partido: cada lado cuelga
            if pa is not None:
                hanging(pa, da, Da.p((0.0, hy, POST_XZ[a_][1])), Da, 0.9)
            if pb is not None:
                hanging(pb, db, Db.p((0.0, hy, POST_XZ[b_][1])), Db, 0.9)
            continue
        if pa is None and pb is None:
            continue
        if pa is None or pb is None:                       # la baranda cuelga del poste que queda
            if pa is None:
                pa, pb, da, db = pb, pa, db, da
            hanging(pa, da, db, Da, 0.55)
            continue
        rails.append([RoundCone(pa, pb, 1.05, 1.05, WOOD)])
        spind.append([])
        n = int(np.linalg.norm(db - da) / 5.4)
        for j in range(1, n):
            u = j / n
            spind[-1] += [RoundCone(da + (db - da) * u, pa + (pb - pa) * u, 0.72, 0.72, WOOD),
                          Sphere(da + (db - da) * u + (pa - da + (pb - pa) * u - (db - da) * u) * 0.5, 1.15, WOOD)]
    for r_ in rails:
        groups.append(Grp(r_, name='rails'))
    for s_ in spind:
        for j in range(0, len(s_), 8):
            groups.append(Grp(s_[j:j + 8], k=0.3, name='spindles'))
    # Telas rojas rotas colgadas de la baranda, por fuera (entre el poste de en medio y el de atrás).
    for si, (i0, i1, sx) in enumerate(((1, 2, 1), (4, 5, -1))):
        if not p['banners'][si] or post_top[i0] is None or post_top[i1] is None:
            continue
        Dh = half[sx]
        c = (post_top[i0] + post_top[i1]) / 2
        w = np.linalg.norm(post_top[i1] - post_top[i0]) / 2 - 1.6
        F = Frame(c + Dh.d((sx * 1.3, 0.9, 0)), Dh.M() @ rot_y(rad(90 * sx)))
        groups.append(Grp([Curtain(F, w, 18.0, CLOTH, amp=1.2, k=0.62, ph=0.7 + si, flare=0.06,
                                   tear=6.0, seed=80 + si, holes=0.22, sway=p['sway'] * sx)], name='banner'))

    # --- ametralladora de siete cañones (se piensa a 1:1 y se agranda GS: se lee de lejos)
    gun = p['gun']
    gx, gyh, gz = GUN_HALF

    def gpt(q):
        return Gf.p(V(q) * GS)
    if gun[0] == 'mount':
        _, rec, gp, gy, gr = gun
        Gf = Dk * Frame(GUN_AT, rot_y(rad(gy)) @ rot_x(rad(gp)) @ rot_z(rad(gr))) * Frame((0, 0, -rec))
        col_a = Dk.p((0, hy, GUN_AT[2] - 1.0))
        col_b = gpt((0, -gyh - 2.6, 0))
        mount = [RoundCone(col_a, col_b, 2.6, 2.2, IRON), Sphere(col_b, 2.9, IRON),
                 Box(Dk.p((0, hy + 0.5, GUN_AT[2] - 1.0)), (4.5, 0.6, 4.5), Dk.M(), 0.3, IRON)]
        for sx in (-1, 1):
            mount += [Box(gpt((sx * (gx + 1.0), -2.4, 0.0)), V(0.7, 3.4, 2.6) * GS, Gf.M(), 0.3, IRON),
                      RoundCone(gpt((sx * (gx + 1.0), -5.0, 0.0)), col_b, 1.2, 1.5, IRON)]
        groups.append(Grp(mount, k=0.6, name='mount'))
    else:
        Gf = root * Frame((0, lifts.get('gun', 0.0), 0)) * gun[1]
    n_gun0 = len(groups)
    box = [Box(gpt((0, 0, 0)), GUN_HALF * GS, Gf.M(), 0.9, WALNUT),
           Box(gpt((0, gyh + 2.2, -2.5)), V(4.2, 2.6, 4.8) * GS, Gf.M(), 0.5, WALNUT),            # tolva
           Box(gpt((0, gyh + 4.7, -2.5)), V(4.7, 0.5, 5.3) * GS, Gf.M(), 0.2, BRASS)]
    for z in (-5.0, 3.0):
        box.append(Box(gpt((0, 0, z)), V(gx + 0.4, gyh + 0.4, 0.85) * GS, Gf.M(), 0.4, IRON))
    for sx in (-1, 1):
        for sy_ in (-1, 1):
            box.append(Box(gpt((sx * (gx - 0.4), sy_ * (gyh - 0.3), -gz + 1.0)), V(1.2, 1.2, 1.4) * GS, Gf.M(), 0.3, BRASS))
    groups.append(Grp(box, k=0.2, name='gunbox'))
    crank = [RoundCone(gpt((-gx - 0.2, 0.0, -3.0)), gpt((-gx - 2.6, 0.0, -3.0)), 1.0 * GS, 1.0 * GS, IRON),
             Ring(Frame(gpt((-gx - 2.6, 0.0, -3.0)), Gf.M() @ rot_z(rad(90))), 2.6 * GS, 2.6 * GS, 0.55 * GS, IRON),
             RoundCone(gpt((-gx - 2.6, 0.0, -3.0)), gpt((-gx - 2.6, -2.8, -6.2)), 0.6 * GS, 0.6 * GS, IRON),
             RoundCone(gpt((-gx - 2.6, -2.8, -6.2)), gpt((-gx - 5.6, -2.8, -6.2)), 0.8 * GS, 0.8 * GS, WALNUT)]
    groups.append(Grp(crank, k=0.3, name='crank'))
    # Batería giratoria: siete cañones en corona alrededor de un eje, atados por tres platos (atrás, en medio
    # y el de la boca, de latón); de frente se lee como un anillo de bocas negras.
    bars, rings = [], []
    fwd = Gf.d((0, 0, 1))
    up_ = Gf.d((0, 1, 0))
    side_ = Gf.d((1, 0, 0))
    tips = []
    rot = p['gun_rot']
    for i in range(NBAR):
        an = rad(rot + 360.0 * i / NBAR)
        x, yb = RC * math.cos(an), RC * math.sin(an)
        a = gpt((x, yb, gz - 1.0))
        tip = gpt((x, yb, gz + LB))
        bars += [CappedCone(a, tip - fwd * 1.3 * GS, RB * GS, RB * GS, IRON),
                 CappedCone(tip - fwd * 1.3 * GS, tip, (RB + 0.4) * GS, (RB + 0.4) * GS, IRON)]      # boca reforzada
        tips.append(tip)
        extras['muzzles'].append((tip, fwd, 1.15 * GS))
    rp = RC + RB + 0.7
    rings += [CappedCone(gpt((0, 0, gz + 0.4)), gpt((0, 0, gz + 1.8)), rp, rp, BRASS),                # plato de atrás
              CappedCone(gpt((0, 0, gz + 9.0)), gpt((0, 0, gz + 10.2)), rp - 0.2, rp - 0.2, IRON),    # abrazadera
              CappedCone(gpt((0, 0, gz + LB - 3.6)), gpt((0, 0, gz + LB - 2.3)), rp, rp, BRASS),     # plato de la boca
              CappedCone(gpt((0, 0, gz - 1.0)), gpt((0, 0, gz + LB - 1.4)), 1.7 * GS, 1.7 * GS, IRON)]  # eje
    groups.append(Grp(bars, name='barrels'))
    groups.append(Grp(rings, name='barrels'))
    fire = p['fire'] or ()
    if fire:
        # Fogonazo grande DELANTE de la corona: estrella de rayos en el plano de las bocas (de frente se ve
        # entera, ~20 px), lengua hacia delante y llamitas en las bocas que disparan. G y H cambian la estrella.
        h_ = fire == EVEN
        c = gpt((0, 0, gz + LB)) + fwd * 3.2
        base = 22.5 if h_ else 0.0
        fl = [Sphere(c, 4.4 if h_ else 5.0, FLASH),
              RoundCone(c, c + fwd * (10.0 if h_ else 15.0), 4.4 if h_ else 5.0, 0.4, FLASH),
              Ellipsoid(c - fwd * 1.6, (8.4 if h_ else 8.8, 8.4 if h_ else 8.8, 1.8), Gf.M(), FLASH)]   # tapa las bocas
        for k in range(8):
            an = rad(base + 45.0 * k)
            dd = nrm(up_ * math.sin(an) + side_ * math.cos(an) + fwd * 0.22)
            ln = (14.0 if k % 2 == 0 else 8.0) if not h_ else (7.5 if k % 2 == 0 else 13.0)
            fl.append(RoundCone(c + dd * 1.5, c + dd * ln, 2.5, 0.45, FLASH))
        for i in fire:
            fl.append(RoundCone(tips[i] + fwd * 0.4, tips[i] + fwd * 3.4, 1.5, 0.6, FLASH))
        groups.append(Grp(fl, k=0.7, name='flash'))
        extras['flash'].append((c, c + fwd * (5.0 if h_ else 7.5), 15.0))
        extras['flash_light'] = (c, 34.0)
    if p['smoke_bar']:
        puffs = []
        rng2 = np.random.default_rng(11)
        for i in p['smoke_bar']:
            m = tips[i] + fwd * 1.5 * GS
            for k in range(3):
                puffs.append(Sphere(m + fwd * (1.2 + 1.8 * k) + V(rng2.uniform(-0.6, 0.6), 1.0 + 1.4 * k, 0),
                                    1.3 + 0.5 * k, SOOT))
        groups.append(Grp(puffs, k=0.8, name='puffs'))

    if gun[0] != 'mount':
        for g in groups[n_gun0:]:
            g.lk = 'gun'
    # --- sangre, restos, quemado
    def loc(fr, pt):
        return {'body': B.p, 'root': root.p, 'deck': Dk.p, 'deckL': half[1].p, 'deckR': half[-1].p, 'gun': gpt,
                'head': hp}[fr](pt)
    extras['stains'] += [(loc(fr, pt), r) for fr, pt, r in p['stains']]
    if p['spray']:
        sp = []
        for fr, pt, r in p['spray']:
            sp.append(Sphere(loc(fr, pt), r, BLOOD))
        groups.append(Grp(sp, name='spray'))
        if all(fr == 'head' for fr, _, _ in p['spray']):
            groups[-1].lk = 'head'
    if p['pool'] is not None:
        c, rr, ang = p['pool']
        if isinstance(c, str):                   # 'mouth': charco que sale de la boca (la cabeza en el suelo)
            m_ = jp((0, -1.0, 22.0))
            c0 = root.to_local(m_[None])[0]
            fw = root.to_local((m_ + Hd.d((0, 0, 1)))[None])[0] - c0
            fw[1] = 0
            fw = nrm(fw) if np.linalg.norm(fw) > 1e-6 else V(0, 0, 1)
            c = V(c0[0], 0.1, c0[2]) + fw * rr[2] * 0.35
            ang = math.degrees(math.atan2(fw[0], fw[2]))
        rl = root * Frame((0, lifts.get('pool', 0.0), 0))
        pl = [Ellipsoid(rl.p(c), rr, rl.M() @ rot_y(rad(ang)), BLOOD)]
        for k, (dx, dz, sc) in enumerate(((0.55, 0.45, 0.55), (-0.6, 0.2, 0.45), (0.1, 0.85, 0.4))):
            o = rot_y(rad(ang)) @ V(dx * rr[0], 0, dz * rr[2])
            pl.append(Ellipsoid(rl.p(c + o), V(rr[0] * sc, rr[1], rr[2] * sc), rl.M() @ rot_y(rad(ang + 30 * k)), BLOOD))
        groups.append(Grp(pl, k=1.0, name='pool'))
        groups[-1].lk = 'pool'
    for i, g in enumerate(p['debris']):
        groups.append(g(root * Frame((0, lifts.get(f'debris{i}', 0.0), 0))))
        groups[-1].lk = f'debris{i}'
    extras['char'] = [(loc(fr, pt), r) for fr, pt, r in p['char']]
    extras['embers'] = [(loc(fr, pt), r) for fr, pt, r in p['embers']]
    extras['smoke2d'] = []
    for fr, pt, power, hgt, drift in p['smoke2d']:
        extras['smoke2d'].append((loc(fr, pt), power, hgt, drift))
    floor = root.p((0, 0, 0))[1]
    for g in groups:                       # nada atraviesa el suelo
        g.cut = lambda P, fy=floor: fy - P[:, 1]
    if p['flatten'] is not None:
        A, t, ds = p['flatten']
        for g in groups:
            if g.name not in ('pool', 'spray', 'debris'):
                g.xf = (A, V(t), ds)
    ax = root.p((0, 0, 0))
    extras['axis'] = (ax[0], ax[2])
    return groups, extras


# ----------------------------------------------------------------------------- poses
def walk(i):
    """Seis fotogramas: trípodes alternos (L1, R2, L3) y (R1, L2, R3); el cuerpo se mece y la cola culebrea."""
    ph = i * 2 * math.pi / 6
    legs = {}
    for k, (fx, fz) in enumerate(FOOT):
        for side, sname in ((1, 'L'), (-1, 'R')):
            grp = (sname == 'L') == (k != 1)
            u = ph if grp else ph + math.pi
            dz = 7.5 * math.cos(u)
            lift = 4.8 * max(0.0, -math.sin(u))
            legs[f'{sname}{k + 1}'] = ('ground', (side * fx, fz + dz), lift)
    s, c2 = math.sin(ph), math.cos(2 * ph)
    return dict(legs=legs, bob=0.9 * c2 - 0.3, roll=1.6 * s, pitch=0.6 * math.cos(ph), yaw=0.0,
                nyaw=-4.0 * s, npitch=1.5 * c2 + 5.0, hyaw=-3.0 * s, hpitch=-6.0 + 1.5 * math.cos(ph), jaw=17.0 + 4.0 * s,
                tail_sway=7.0, tail_phase=ph, sway=1.2 * s, gun=('mount', 0.0, -4.0, 1.5 * s, -1.2 * s))


ATK_LEGS = leg_specs({'L1': ('ground', (57.0, 41.0), 0.0), 'R1': ('ground', (-57.0, 39.0), 0.0),
                      'L3': ('ground', (57.0, -46.0), 0.0), 'R3': ('ground', (-57.0, -45.0), 0.0)})
ATK_G = dict(legs=ATK_LEGS, bob=-0.8, pitch=1.0, npitch=8.0, hpitch=-2.0, jaw=26.0, tongue=0.0, eye_r=2.7,
             tail_sway=9.0, tail_phase=1.0, gun=('mount', 0.0, -5.0, 0.0, 0.0), fire=ODD)
ATK_H = dict(ATK_G, bob=-1.1, jaw=30.0, npitch=9.0, gun=('mount', 1.8, -2.5, 0.6, 0.4), fire=EVEN,
             gun_rot=ROT_A + 180.0 / NBAR,
             tail_phase=1.6, sway=0.8)
PAIN = dict(legs=leg_specs({'L1': ('ground', (56.0, 36.0), 6.0), 'R1': ('ground', (-58.0, 40.0), 2.0)}),
            bob=1.6, pitch=-6.0, roll=4.0, npitch=16.0, nyaw=8.0, hpitch=20.0, hyaw=10.0, hroll=-10.0,
            jaw=36.0, tongue=0.6, eye_r=2.9, tail_sway=12.0, tail_phase=2.4, tail_up=0.6, sway=-1.6,
            gun=('mount', 1.0, 8.0, 10.0, 6.0))


# ----------------------------------------------------------------------------- muerte (J-S)
WOUNDS = [('body', (14.0, 26.0, 30.0), 4.0), ('body', (-20.0, 22.0, 22.0), 3.0), ('body', (4.0, 12.0, 48.0), 3.5),
          ('body', (-6.0, 8.0, 60.0), 3.0)]
MOUTH_SPRAY = [('head', (0.5, 1.0, 34.0), 1.6), ('head', (-1.0, 3.5, 38.0), 1.3), ('head', (1.5, 6.5, 41.0), 1.0),
               ('head', (-0.5, 9.0, 43.5), 0.8), ('head', (2.0, 1.0, 39.0), 1.0), ('head', (-2.0, 12.0, 45.0), 0.6)]


def death_j():
    return dict(legs=leg_specs({'L1': ('ground', (57.0, 40.0), 7.0), 'R1': ('ground', (-56.0, 38.0), 5.0)}),
                bob=2.4, pitch=-9.0, roll=-3.0, npitch=26.0, nyaw=-6.0, hpitch=26.0, hyaw=-8.0, hroll=8.0,
                jaw=44.0, tongue=1.0, eye_r=3.0, tail_sway=13.0, tail_phase=0.4, tail_up=0.9, sway=1.8,
                gun=('mount', 2.0, 16.0, -14.0, -8.0), stains=WOUNDS, spray=MOUTH_SPRAY)


def post_piece(c, ang_y, ang_z, length=14.0):
    """Trozo de poste roto tirado (marco raíz)."""
    def make(root, c=c, ay=ang_y, az=ang_z, length=length):
        F = root * Frame(c, rot_y(rad(ay)) @ rot_z(rad(az)))
        a, b = F.p((0, 0, -length / 2)), F.p((0, 0, length / 2))
        parts = [RoundCone(a, b, 1.4, 1.3, WOOD), Sphere(F.p((0, 0, -length / 2 + 4.0)), 1.9, WOOD),
                 Sphere(F.p((0, 0, length / 2 - 1.5)), 1.75, GILT)]
        return Grp(parts, k=0.5, name='debris')
    return make


def plank(c, half, ang_y, ang_x=0.0, ang_z=0.0, mat=WOOD):
    def make(root, c=c, half=half, ay=ang_y, ax=ang_x, az=ang_z, mat=mat):
        R = root.M() @ rot_y(rad(ay)) @ rot_x(rad(ax)) @ rot_z(rad(az))
        return Grp([Box(root.p(c), half, R, 0.35, mat)], name='debris')
    return make


def rag(c, ang_y, w, drop, seed, ang_x=70.0):
    """Tela caída (casi tendida en el suelo)."""
    def make(root, c=c, ay=ang_y, w=w, drop=drop, seed=seed, ax=ang_x):
        F = root * Frame(c, rot_y(rad(ay)) @ rot_x(rad(-ax)))
        return Grp([Curtain(F, w, drop, CLOTH, amp=1.0, k=0.7, flare=0.0, tear=4.0, seed=seed, holes=0.25)],
                     name='debris')
    return make


def deaths():
    """K-S (siempre de frente): se le doblan las patas, cae de panza, el tablero se parte por la quilla, el arma
    se suelta y cae al suelo a su izquierda, la cabeza cae de lado a su derecha; humo y brasas; cadáver."""
    def splay(dx, dz=0.0):
        return leg_specs({f'{s}{k + 1}': ('ground', (sg * (fx + dx * (1.0 if k != 1 else 1.2)), fz + dz * (k - 1)), 0.0)
                          for k, (fx, fz) in enumerate(FOOT) for s, sg in (('L', 1), ('R', -1))})
    base = dict(stains=WOUNDS + [('head', (0.0, -2.0, 24.0), 3.0)], tail_sway=6.0, tail_phase=0.8, eye_r=2.5)
    K = dict(base, legs=splay(4.0), bob=-6.0, pitch=7.0, roll=-3.0, npitch=-10.0, nyaw=-6.0, hpitch=-8.0, hyaw=-6.0,
             hroll=-8.0, jaw=30.0, tongue=0.6, posts=(10.0, 0, 0, 0, 0, 0), gun=('mount', 0.0, -12.0, -6.0, -4.0),
             spray=[('head', (0.0, -3.0, 25.0), 1.6), ('head', (1.0, -6.0, 26.0), 1.2), ('head', (-0.5, -9.0, 26.5), 0.9)])
    L = dict(base, legs=splay(10.0, 2.0), bob=-8.6, pitch=4.0, roll=-4.0, npitch=-20.0, nyaw=-12.0, hpitch=-5.0,
             hyaw=-8.0, hroll=-12.0, jaw=26.0, tongue=0.8, deck_break=5.0, posts=(('roto', 5.0), 0, 0, -6.0, 0, 0),
             gun=('mount', 0.0, -10.0, -18.0, -16.0), valance_tear=1.4,
             debris=[post_piece((44.0, 2.0, 30.0), 20.0, 0.0)],
             smoke2d=[('gun', (0.0, 5.0, -3.0), 0.35, 26.0, 5.0)])
    gun_m = Frame((31.0, 44.0, 10.0), rot_y(rad(14.0)) @ rot_z(rad(-38.0)) @ rot_x(rad(-12.0)))
    M = dict(base, legs=splay(13.0, 3.0), bob=-9.0, pitch=4.0, roll=-6.0, npitch=-24.0, nyaw=-18.0, hpitch=-5.0,
             hyaw=-10.0, hroll=-16.0, jaw=26.0, tongue=1.0, deck_break=11.0,
             posts=(('roto', 5.0), -12.0, 0, 18.0, 0, -10.0), banners=(True, False), valance_tear=1.6,
             gun=('free', gun_m),
             debris=[post_piece((44.0, 2.0, 30.0), 20.0, 0.0), rag((-40.0, 5.0, -12.0), -90.0, 12.0, 14.0, 91, 60.0)],
             smoke2d=[('gun', (0.0, 5.0, -3.0), 0.6, 40.0, 8.0)])
    gun_g = Frame((70.0, 7.5, 16.0), rot_y(rad(58.0)) @ rot_z(rad(-82.0)))
    N = dict(base, legs=splay(15.0, 3.5), bob=-9.2, pitch=3.0, roll=-7.0, npitch=-29.0, nyaw=-50.0, hpitch=10.0,
             hyaw=-52.0, hroll=14.0, jaw=32.0, tongue=1.2, deck_break=20.0,
             posts=(('roto', 5.0), ('roto', 7.0), -10.0, 26.0, 6.0, -14.0), banners=(False, False), valance_tear=1.8,
             gun=('free', gun_g),
             debris=[post_piece((44.0, 2.0, 30.0), 20.0, 0.0), post_piece((48.0, 5.0, -6.0), -30.0, 30.0, 11.0),
                     rag((-40.0, 5.0, -12.0), -90.0, 12.0, 14.0, 91, 60.0), rag((44.0, 5.0, -22.0), 90.0, 11.0, 13.0, 92, 50.0)],
             char=[('gun', (0.0, 0.0, 0.0), 9.0)],
             smoke2d=[('gun', (0.0, 0.0, -4.0), 0.8, 50.0, 10.0), ('deck', (8.0, 3.0, 6.0), 0.35, 26.0, 6.0)])
    O = dict(N, legs=splay(16.0, 4.0), bob=-9.4, roll=-8.0, npitch=-30.0, nyaw=-60.0, hpitch=14.0, hyaw=-66.0,
             hroll=22.0, jaw=34.0, tongue=1.3, deck_break=(32.0, 26.0), deck_slide=((18.0, -0.6), (14.0, -1.5)),
             eye_r=2.1, posts=(('roto', 5.0), ('roto', 7.0), 8.0, 10.0, ('roto', 6.0), ('roto', 8.0)),
             debris=N['debris'] + [post_piece((-46.0, 4.0, 8.0), 60.0, 8.0, 12.0), post_piece((22.0, 3.0, 54.0), -10.0, 0.0, 10.0),
                                   plank((30.0, 2.0, 46.0), (8.0, 0.9, 1.0), 30.0, 0.0, 10.0)],
             char=[('gun', (0.0, 0.0, 0.0), 11.0), ('deckL', (12.0, 2.0, 4.0), 9.0)],
             embers=[('deckL', (12.0, 2.0, 4.0), 7.0)],
             smoke2d=[('gun', (0.0, 0.0, -4.0), 1.0, 64.0, 12.0), ('deckL', (12.0, 3.0, 4.0), 0.7, 46.0, 9.0)])
    P = dict(O, jaw=36.0, eye_r=2.0, char=[('gun', (0.0, 0.0, 0.0), 12.0), ('deckL', (12.0, 2.0, 4.0), 13.0)],
             embers=[('deckL', (12.0, 2.0, 4.0), 10.0), ('gun', (0.0, 3.0, 0.0), 6.0)],
             smoke2d=[('gun', (0.0, 0.0, -4.0), 1.0, 78.0, 16.0), ('deckL', (12.0, 3.0, 4.0), 1.0, 66.0, 12.0)],
             pool=('mouth', (8.0, 0.5, 6.0), 0.0))
    Q = dict(P, eyes='dead', pool=('mouth', (11.0, 0.5, 8.0), 0.0),
             embers=[('deckL', (12.0, 2.0, 4.0), 7.0)],
             smoke2d=[('gun', (0.0, 0.0, -4.0), 0.75, 76.0, 20.0), ('deckL', (12.0, 3.0, 4.0), 0.75, 62.0, 16.0)])
    R_ = dict(Q, pool=('mouth', (14.0, 0.5, 10.0), 0.0), embers=[('deckL', (12.0, 2.0, 4.0), 4.5)],
              smoke2d=[('gun', (0.0, 0.0, -4.0), 0.5, 62.0, 24.0), ('deckL', (12.0, 3.0, 4.0), 0.45, 48.0, 18.0)])
    S_ = dict(R_, pool=('mouth', (16.0, 0.5, 12.0), 0.0), embers=[],
              smoke2d=[('deckL', (12.0, 3.0, 4.0), 0.3, 30.0, 10.0)])
    # K-M: la cabeza que se desploma hacia delante se apoya en la línea del suelo; de N en adelante cae al
    # suelo de lado (más cerca, junto al flanco) y solo se suben el arma caída y los restos.
    return [dict(x, auto_lift=True) for x in (K, L, M)] + \
        [dict(x, auto_lift=('gun', 'debris')) for x in (N, O, P, Q, R_, S_)]



# ----------------------------------------------------------------------------- humo (2D)
def smoke_layer(Hh, Ww, sources, seed):
    """Humo en el lienzo: por cada fuente, bocanadas que suben, crecen, derivan y se deshilachan arriba; cada
    bocanada con luz desde arriba-izquierda, más oscura y densa abajo. → (nivel de la rampa o -1, fuente)."""
    Y, X = np.mgrid[0:Hh, 0:Ww].astype(float)
    lvl = np.full((Hh, Ww), -1, int)
    who = np.full((Hh, Ww), -1, int)
    n = len(SMOKE_RAMP)
    for si, (cx, cy, power, hgt, drift) in enumerate(sources):
        rng = np.random.default_rng(seed + 17 * si)
        npf = int(5 + 9 * power)
        puffs = []
        for k in range(npf):
            u = (k + rng.uniform(0.0, 0.7)) / npf
            x = cx + drift * u ** 1.5 + rng.uniform(-1.2, 1.2) * (0.4 + 2.5 * u)
            y = cy - u * hgt
            r = (2.0 + 7.0 * u ** 0.8) * (0.65 + 0.45 * power) * rng.uniform(0.85, 1.15)
            puffs.append((u, x, y, r))
        for u, x, y, r in sorted(puffs, key=lambda q: -q[0]):          # de arriba abajo: las de abajo encima
            x0, x1 = int(max(0, x - r * 1.4 - 1)), int(min(Ww, x + r * 1.4 + 2))
            y0, y1 = int(max(0, y - r * 1.4 - 1)), int(min(Hh, y + r * 1.4 + 2))
            if x0 >= x1 or y0 >= y1:
                continue
            xs, ys = X[y0:y1, x0:x1], Y[y0:y1, x0:x1]
            nz = fbm2(xs * 0.35, ys * 0.35, 1.0, seed + si * 7)
            d = np.hypot(xs - x, (ys - y) * 1.1)
            inside = d < r * (0.72 + 0.5 * nz)
            if u > 0.55:                                                 # arriba se deshilacha
                inside &= fbm2(xs * 0.5, ys * 0.5, 1.0, seed + si * 7 + 3) > (u - 0.55) * 1.3
            lum = np.clip(1 - np.hypot(xs - (x - 0.35 * r), ys - (y - 0.4 * r)) / (1.5 * r), 0, 1)
            lv = np.clip(np.round((0.25 + 0.55 * u + 0.55 * lum - 0.25 * power * (1 - u)) * (n - 1)), 0, n - 1).astype(int)
            sub = lvl[y0:y1, x0:x1]
            sub[inside] = lv[inside]
            who[y0:y1, x0:x1][inside] = si
    return lvl, who


def project(cam, P):
    """Punto del modelo → (columna, fila) en el lienzo del trazado (continuo)."""
    c = cam['R'] @ P
    return cam['hw'] + c @ cam['Xc'], cam['top'] - c @ cam['Uc']


# ----------------------------------------------------------------------------- salida
OFFSETS = {}


def lowest_by_key(groups, view, axis, step=1.0):
    """Por cada pieza marcada (g.lk), el punto más bajo en pantalla respecto a la línea del suelo del eje
    (unidades; <0 = por debajo), muestreando su interior en una rejilla."""
    v, tt = view
    ct, st = 1 / math.sqrt(1 + tt * tt), tt / math.sqrt(1 + tt * tt)
    res = {}
    for g in groups:
        k = getattr(g, 'lk', None)
        if k is None:
            continue
        c, r = g.model_bound()
        ax = np.arange(-r, r + step, step)
        X, Y, Z = np.meshgrid(ax, ax, ax, indexing='ij')
        P = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
        P = P[(P * P).sum(1) <= r * r] + c
        a3 = V(axis[0], 0.0, axis[1])
        P = P[(P[:, 1] * ct - ((P - a3) @ v) * st) < 2.0]       # solo lo que podría quedar bajo la línea
        if not len(P):
            continue
        d, _ = g.eval(P)
        ins = P[d < 0]
        if len(ins):
            sy = ins[:, 1] * ct - ((ins - a3) @ v) * st
            res[k] = min(res.get(k, np.inf), float(sy.min()))
    return res


def draw_creature(pose, angle, name):
    tilt = rad(pose.get('tilt', 10.0))
    # De espaldas (4-6) basta con 2x2 submuestras (allí no hay detalle fino: caparazón, carroza y cola).
    R = render(tilt, ss=min(SS3, 2) if angle in (4, 5, 6) else SS3)
    Rc, Xc, Uc, Dc = R.camera(angle)
    vv = -(Dc @ Rc)
    vv[1] = 0.0
    pose = dict(pose, view=(nrm(vv), math.tan(tilt)))
    groups, extras = build(pose)
    if pose.get('auto_lift'):             # 2-3 pasadas: medir lo que cae bajo la línea del suelo y subirlo
        lifts = {}
        for _ in range(3):
            low = lowest_by_key(groups, pose['view'], extras['axis'])
            if isinstance(pose['auto_lift'], tuple):
                low = {k: v for k, v in low.items() if k.startswith(pose['auto_lift'])}
            add = {k: max(0.0, LIFT_TO - v) / math.cos(tilt) for k, v in low.items() if v < LIFT_TO - 0.3}
            if not add:
                break
            for k, v in add.items():
                lifts[k] = lifts.get(k, 0.0) + v
            groups, extras = build(dict(pose, lifts=lifts))
    out, depth, cam = R.render(groups, extras, angle)
    img = np.array(finish(out, depth, R.palarr, OUTLINE))
    H, W = img.shape[:2]
    floor_row = cam['top']                 # borde de arriba de esta fila = suelo en el eje
    ax = cam['hw']
    if extras.get('smoke2d'):
        pt, px_ = 90, 30
        big = np.zeros((H + pt, W + 2 * px_, 4), np.uint8)
        big[pt:, px_:px_ + W] = img
        dep = np.full(big.shape[:2], np.inf)
        dep[pt:, px_:px_ + W] = np.where(img[:, :, 3] >= 128, depth, np.inf)
        srcs, tsrc = [], []
        for c, power, hgt, drift in extras['smoke2d']:
            cx, cy = project(cam, c)
            srcs.append((cx + px_, cy + pt, power, hgt, drift))
            tsrc.append(c @ cam['D'] + 400.0)
        lvl, who = smoke_layer(big.shape[0], big.shape[1], srcs, 500 + ord(name[4]))
        ts = np.where(who >= 0, np.array(tsrc + [0.0])[who], np.inf)
        sm = (lvl >= 0) & (dep > ts - 3.0)                   # el humo tapa lo que está detrás de su fuente
        pal = R.palarr
        big[sm, :3] = pal[np.array(SMOKE_RAMP)[lvl[sm]]].astype(np.uint8)
        big[sm, 3] = 255
        img = big
        floor_row += pt
        ax += px_
    vis = img[:, :, 3] >= 128
    img[~vis] = 0
    cols = np.nonzero(vis.any(0))[0]
    rows = np.nonzero(vis.any(1))[0]
    need = max(ax - cols.min(), cols.max() + 1 - ax)
    x0 = ax - need
    pad_l = max(0, -x0)
    if pad_l:
        img = np.concatenate([np.zeros((img.shape[0], pad_l, 4), np.uint8), img], axis=1)
        ax += pad_l
        x0 += pad_l
    if ax + need > img.shape[1]:
        img = np.concatenate([img, np.zeros((img.shape[0], ax + need - img.shape[1], 4), np.uint8)], axis=1)
    r0, r1 = rows.min(), rows.max() + 1
    b = img[r0:r1, x0:ax + need].copy()
    h, w = b.shape[:2]
    for x in (0, w - 1):                   # anclas invisibles: construir_pwad no recorta el lienzo
        if b[h - 1, x, 3] == 0:
            b[h - 1, x] = (0, 0, 0, 1)
        if b[0, x, 3] == 0:
            b[0, x] = (0, 0, 0, 1)
    OFFSETS[name] = [need, int(floor_row - SINK - r0)]
    return Image.fromarray(b, 'RGBA')


def lumps():
    out = {}
    for fi, fr in enumerate('ABCDEF'):
        for a in range(1, 9):
            out[f'SPID{fr}{a}'] = ((f'SPID{fr}{a}', walk(fi)), a)
    for fr, pose in (('G', ATK_G), ('H', ATK_H), ('I', PAIN), ('J', death_j())):
        for a in range(1, 9):
            out[f'SPID{fr}{a}'] = ((f'SPID{fr}{a}', pose), a)
    for fr, pose in zip('KLMNOPQRS', deaths()):
        out[f'SPID{fr}0'] = ((f'SPID{fr}0', pose), 1)
    return out


def draw(item, angle):
    name, pose = item
    return draw_creature(pose, angle, name)


def guardar_offsets(salida):
    """Actualiza arte/sprites/offsets_tarasca.json con los lumps dibujados (sin perder los demás)."""
    if not OFFSETS:
        return
    path = os.path.join(salida, 'offsets_tarasca.json')
    with open(path, 'a+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        txt = f.read()
        cur = json.loads(txt) if txt.strip() else {}
        cur.update(OFFSETS)
        f.seek(0)
        f.truncate()
        f.write('{\n' + ',\n'.join(f'  "{k}": [{v[0]}, {v[1]}]' for k, v in sorted(cur.items())) + '\n}\n')
        f.flush()
        fcntl.flock(f, fcntl.LOCK_UN)


# Render en paralelo: varios procesos llenan una caché y luego sdf.cli guarda los PNG y la hoja como siempre
# (cada sprite es independiente y sus semillas son fijas: el resultado es idéntico al secuencial).
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
    ap.add_argument('--procesos', type=int, default=os.cpu_count() or 4)
    args, _ = ap.parse_known_args()
    todos = lumps()
    names = [n.strip().upper() for n in args.solo.split(',') if n.strip()] or list(todos)
    pesados = sorted(names, key=lambda n: (n[4] < 'J', n))          # muertes (con humo) primero
    if len(names) > 1 and args.procesos > 1:
        with ProcessPoolExecutor(max_workers=min(args.procesos, os.cpu_count() or 1)) as ex:
            for name, arr, off in ex.map(_work, pesados):
                CACHE[name] = (Image.fromarray(arr, 'RGBA'), off)
    argv, skip = [], False                                         # sdf.cli no conoce --procesos
    for a in sys.argv:
        if skip:
            skip = False
        elif a == '--procesos':
            skip = True
        elif not a.startswith('--procesos='):
            argv.append(a)
    sys.argv = argv
    cli(lumps, draw_cached, sprite_rows('SPID', 'ABCDEFGHIJ', 'KLMNOPQRS'))
    guardar_offsets(args.salida)
