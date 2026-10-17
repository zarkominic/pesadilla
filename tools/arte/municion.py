#!/usr/bin/env python3
"""municion.py — LA MUNICIÓN Y LOS BARRILES de PESADILLA (sustituyen a los de Freedoom), dibujados
por código con el motor de criaturas (sdf.py): modelos 3D de primitivas SDF a 1 unidad = 1 px,
trazado ortográfico, rampas EXACTAS de PLAYPAL, contorno oscuro de 1 px y luz desde
arriba-izquierda-delante. Los objetos no rotan (lumps X?0) y se ven desde la altura de los ojos y
algo desde arriba (cámara a 14-30°, según el tamaño).

Uso:
    ~/.venvs/pesadilla/bin/python tools/arte/municion.py --salida arte/sprites
    … --solo CLIPA0,BAR1A0        solo esos lumps
    … --hoja <png>                además, hoja de contactos ampliada junto a los de Freedoom

Cada munición recuerda a SU arma:
- CLIPA0 (balas del pistolón y del órgano): bolsita de cuero con la boca abierta y balas de plomo
  redondas asomando (y una suelta en el suelo).
- AMMOA0 (caja de balas): caja de pino con la tapa abierta, llena de balas de plomo y cebos de cobre.
- SHELA0 (cartuchos): cuatro cartuchos de cartón rojo con culote de latón (los de la recarga de la
  escopeta): tres de pie y uno tumbado.
- SBOXA0 (caja de cartuchos): caja de cartón abierta con dos filas de cartuchos de pie (el latón
  arriba) y uno tirado delante.
- ROCKA0 (un cohete): el cohete de feria del lanzacohetes (cono rojo, cuerpo de papel a franjas
  verde, amarillo y rojo, tapón de barro, varilla de caña atada), de pie clavado en su varilla.
- BROKA0 (caja de cohetes): caja de pino con cinco cohetes de feria tumbados (tres abajo, dos encima).
- CELLA0 (celda): tarro de cristal tapado con un trapo atado y un fuego fatuo azul dentro (la
  munición del farol; el cristal se pinta con lo que se ve a través, como en farol.py).
- CELPA0 (pack de celdas): damajuana de cristal forrada de mimbre (con asas) y tres fuegos fatuos
  dentro; el resplandor azul asoma también por las rendijas del mimbre.
- BPAKA0 (mochila): zurrón de pastor de piel de cabra con pelo (pardo con manchas claras), la boca
  fruncida y atada con un cordel y la correa en arco con su hebilla.
- BAR1A0-B0 (barril explosivo): barril de pólvora de duelas de roble con cuatro aros de hierro, una
  calavera pintada con cal (marca de peligro), un montoncito de pólvora derramada al pie y una mecha
  corta encendida que chisporrotea (A y B cambian las chispas y el hilo de humo).
- BEXPA0-E0 (explosión, a pleno brillo): A la mecha llega al tapón y las juntas de las duelas se
  encienden; B el barril se hincha, salta la tapa y sale una llamarada por arriba y fuego por las
  juntas; C revienta en una bola de fuego con las duelas y los aros volando; D gran bola de fuego
  (blanca en el centro) con duelas y chispas; E se apaga en humo con brasas y las duelas cayendo.

Desplazamientos explícitos de todos en <salida>/offsets_municion.json: centrados en horizontal y
con el punto del suelo del centro del objeto en la base (los objetos vistos desde arriba bajan 1-3 px
por delante, como los de Freedoom). Todo determinista (ruido y azar con semilla fija).
"""
import argparse
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdf  # noqa: E402
from sdf import (V, Box, CappedCone, Ellipsoid, Frame, Group, Ring, RoundCone, Sphere,  # noqa: E402
                 rad, rot_x, rot_y, rot_z, rot_axis, vnoise, _len)
from arma1p import guardar_offsets  # noqa: E402
from cohetes import (fbm2, lluvia_chispas, malla, pintar_fuego,  # noqa: E402
                     pintar_humo)
import farol  # noqa: E402

PAL = sdf.read_palette(sdf.IWAD)
PALARR = np.array(PAL, float)
IWAD_REF = sdf.IWAD

# ---------------------------------------------------------------------------------------------
# Materiales y rampas (índices EXACTOS de PLAYPAL, de oscuro a claro)
# ---------------------------------------------------------------------------------------------
(PINO, ROBLE, CUERO, CUERDA, PLOMO, LATON, COBRE, CARTON_R, CIERRE, CARTON, HIERRO, PAPEL_R,
 PAPEL_Y, PAPEL_G, CANA, BARRO, VIDRIO, REFLEJO, TRAPO, CORCHO, MIMBRE, PIEL, PIEL_B, POLVORA,
 CAL, MECHA, BRASA, LUMBRE, CUERO_OSC, PISTON) = range(30)

RAMPAS = {
    PINO: [2, 79, 77, 75, 73, 71, 69, 67, 65, 64],              # pino de caja
    ROBLE: [2, 239, 238, 237, 76, 74, 72, 70, 68, 66],          # roble del barril (más oscuro que el pino)
    CUERO: [2, 239, 238, 237, 236, 13, 73, 71, 69],             # cuero de la bolsita
    CUERO_OSC: [2, 239, 238, 237, 236, 141, 139],               # correa del zurrón
    CUERDA: [239, 238, 237, 236, 141, 139, 137],                # cordel de cáñamo
    PLOMO: [5, 109, 106, 103, 100, 97, 94, 91, 88],             # plomo (gris mate)
    LATON: [238, 167, 166, 165, 164, 163, 162, 161],            # latón
    COBRE: [239, 235, 233, 232, 222, 219, 216, 214],            # cebos de cobre
    CARTON_R: [191, 189, 187, 185, 183, 181, 179, 177],         # cartón rojo de los cartuchos
    CIERRE: [191, 190, 189, 188, 187],                          # cierre en estrella (rojo oscuro)
    CARTON: [2, 143, 141, 139, 137, 135, 133, 131, 129],        # cartón de la caja
    HIERRO: [5, 111, 109, 107, 105, 103, 101, 99],              # aros de hierro
    PAPEL_R: [190, 187, 184, 181, 178, 174],                    # papeles del cohete (cohetes.py)
    PAPEL_Y: [166, 165, 164, 163, 162, 161],
    PAPEL_G: [126, 124, 122, 120, 118, 116],
    CANA: [238, 149, 147, 145, 144, 131],                       # varilla de caña
    BARRO: [8, 6, 109, 106, 103],                               # tapón de barro
    VIDRIO: list(farol.VIDRIO),                                 # cristal: lo que se ve a través
    REFLEJO: [106, 101, 96, 90, 84],                            # brillo del cristal
    TRAPO: [2, 141, 139, 137, 134, 131, 129, 128],              # trapo de lino sucio
    CORCHO: [239, 238, 237, 236, 141, 139, 137],
    MIMBRE: [2, 151, 150, 149, 148, 147, 146, 145, 144],        # mimbre
    PIEL: [2, 239, 238, 237, 76, 74, 72, 70, 68],               # piel de cabra parda
    PIEL_B: [2, 141, 139, 136, 133, 131, 129, 128],             # manchas claras del pelo
    POLVORA: [0, 8, 6, 5, 111, 109, 107],                       # pólvora negra
    CAL: [104, 99, 94, 90, 86, 83, 81],                         # pintura de cal
    MECHA: [7, 239, 238, 237, 236, 141, 139],                   # mecha
    BRASA: [186, 183, 179, 176, 215, 213, 211, 227],            # brasa de la mecha
    LUMBRE: [232, 223, 220, 217, 215, 213, 211, 227, 225],      # fuego visto por las juntas
    PISTON: [8, 235, 233, 232],                                 # pistón del culote (cobre oscuro)
}
LEVEL_MATS = (VIDRIO, LUMBRE, BRASA)
EMISSIVE = (COBRE, LATON, BRASA, LUMBRE)
GANANCIA = {PINO: 1.0, ROBLE: 1.0, PLOMO: 1.05, LATON: 1.0, CARTON_R: 1.0, CARTON: 1.0, HIERRO: 0.9,
            PIEL: 1.05, PIEL_B: 1.0, POLVORA: 0.9, CAL: 1.05, MIMBRE: 1.05, CUERO: 1.05}
LIFT = 40.0                       # el modelo se sube: sdf.Render solo dibuja por encima de y = -1


# ---------------------------------------------------------------------------------------------
# Ayudas de modelado
# ---------------------------------------------------------------------------------------------

def cil(a, b, r, mat, r2=None):
    return CappedCone(V(a), V(b), r, r if r2 is None else r2, mat)


def anillo(c, rx, rz, tubo, mat, R=None):
    return Ring(Frame(c, R), rx, rz, tubo, mat)


def caja_abierta(c, h, grueso, mat, rnd=0.35, fondo=1.0):
    """Caja sin tapa: c centro, h medias medidas, grueso de las tablas (fondo: grosor del suelo)."""
    b = Box(c, h, rnd=rnd, mat=mat)
    dentro = Box((c[0], c[1] + fondo, c[2]), (h[0] - grueso, h[1], h[2] - grueso), rnd=0.0, mat=mat)
    b.cut = lambda P, d=dentro: -d.sdf(P)
    return b


def con_corte(p, f):
    p.cut = f
    return p


def cartucho(base, eje, L=8.6, r=1.45, laton=1.9):
    """Cartucho de escopeta: base = cara del culote, eje hacia el cierre (unidades = px)."""
    e = sdf.nrm(eje)
    b = V(base)
    return [cil(b + e * laton * 0.7, b + e * L, r, CARTON_R),
            cil(b + e * 0.3, b + e * laton, r + 0.12, LATON),
            cil(b, b + e * 0.45, r + 0.42, LATON),
            cil(b - e * 0.08, b + e * 0.2, 0.55, PISTON),
            cil(b + e * (L - 0.1), b + e * (L + 0.12), r * 0.62, CIERRE, r * 0.5)]


def cohete(cola, eje, r=2.9, largo=(2.6, 2.6, 2.7, 2.6), cono=5.2, varilla=None, ataduras=True):
    """Cohete de feria (como el del lanzacohetes): desde el tapón de barro (cola) hacia el cono,
    franjas verde, amarillo, rojo y amarillo, cono rojo y punta; varilla de caña: (lado, largo)
    en el lado dado (vector perpendicular al eje), desde cerca del cono hacia atrás."""
    e = sdf.nrm(eje)
    c = V(cola)
    prims = [cil(c - e * 0.7, c + e * 0.25, r - 0.35, BARRO, r - 0.15)]
    z = 0.0
    for L, m in zip(largo, (PAPEL_G, PAPEL_Y, PAPEL_R, PAPEL_Y)):
        prims.append(cil(c + e * z, c + e * (z + L), r, m))
        z += L
    prims.append(CappedCone(c + e * (z - 0.15), c + e * (z + cono), r + 0.15, 0.35, PAPEL_R))
    prims.append(Sphere(c + e * (z + cono), 0.5, PAPEL_R))
    palo = []
    if varilla is not None:
        lado, lv = varilla
        s = sdf.nrm(lado)
        a = c + e * (z - 1.5) + s * (r + 0.55)
        b = c - e * (lv - z) + s * (r + 0.45)
        palo.append(RoundCone(a, b, 0.75, 0.62, CANA))
        if ataduras:
            for zz in (1.2, z - 2.0):
                mid = c + e * zz + s * 0.55
                Rr = np.column_stack([s, e, np.cross(s, e)])
                palo.append(Ring(Frame(mid, Rr), r + 1.0, r + 0.35, 0.42, CUERDA))
    return prims, palo


# ---------------------------------------------------------------------------------------------
# Render: cámara del motor de criaturas, algo más inclinada; el modelo se sube LIFT unidades
# ---------------------------------------------------------------------------------------------

_RENDERS = {}


def render_obj(groups, tilt, extras=None, A=None):
    """Traza los grupos (modelo con el suelo en y = 0) → (img RGBA con contorno, vista).
    vista.px(p) da la posición (x, y) continua de un punto del modelo en la imagen."""
    if tilt not in _RENDERS:
        _RENDERS[tilt] = sdf.Render(RAMPAS, gancho, level_mats=LEVEL_MATS, emissive=EMISSIVE, tilt=rad(tilt))
    R_ = _RENDERS[tilt]
    A = np.eye(3) if A is None else A
    for g in groups:
        g.xf = (A, V(0, LIFT, 0), 1.0)
    ex = dict(extras or {})
    ex['tilt'] = rad(tilt)
    ex['A'] = A
    out, depth = R_.render(groups, ex, 0)
    if ex.get('lineas'):                      # líneas interiores más finas que las de sdf.finish
        out = lineas_interiores(out, depth, R_.palarr, ex['lineas'])
    img = np.array(sdf.finish(out, depth, R_.palarr, 2))
    img[img[..., 3] < 128] = 0
    return img, Vista(groups, tilt, A), depth


def lineas_interiores(out, depth, palarr, umbral, oscuro=2):
    """Oscurece el píxel de detrás junto a algo más cercano (umbral en px de profundidad), como la
    línea interior de sdf.finish pero con un umbral propio: separa piezas que se tocan."""
    H, W = out.shape
    res = out.copy()
    op = out >= 0
    for y, x in zip(*np.nonzero(op)):
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            yy, xx = y + dy, x + dx
            if 0 <= yy < H and 0 <= xx < W and op[yy, xx] and depth[yy, xx] < depth[y, x] - umbral:
                if palarr[out[y, x]].sum() > 3 * 40:
                    res[y, x] = oscuro
                break
    return res


class Vista:
    def __init__(self, groups, tilt, A):
        t = rad(tilt)
        self.Uc = V(0, math.cos(t), -math.sin(t))
        self.A = A
        xs, ys = [], []
        for g in groups:
            c, r = g.model_bound()
            xs += [c[0] - r, c[0] + r]
            ys += [c @ self.Uc - r, c @ self.Uc + r]
        self.hw = int(math.ceil(max(-min(xs), max(xs)))) + 2
        self.top = int(math.ceil(max(ys))) + 2

    def px(self, p):
        q = self.A @ V(p) + V(0, LIFT, 0)
        return self.hw + q[0], self.top - q @ self.Uc


def recortar(img, vista, bajo_max=3, extra=None):
    """Recorta lo transparente (simétrico respecto al eje del objeto) → (img, [izq, sup]).
    sup: la fila del suelo bajo el centro del objeto (como mucho bajo_max px por encima de la base)."""
    vis = img[..., 3] > 0
    ys, xs = np.nonzero(vis)
    hw = vista.hw
    need = max(hw - xs.min(), xs.max() + 1 - hw)
    x0, x1 = hw - need, hw + need
    pad = max(0, -x0, x1 - img.shape[1])
    if pad:
        img = np.pad(img, ((0, 0), (pad, pad), (0, 0)))
        x0, x1 = x0 + pad, x1 + pad
    y0, y1 = ys.min(), ys.max() + 1
    out = img[y0:y1, x0:x1].copy()
    h = out.shape[0]
    _, yf = vista.px((0, 0, 0))
    sup = int(round(yf - y0))
    sup = max(h - bajo_max, min(h, sup))
    return out, [need, sup], (x0 - pad, y0)


# ---------------------------------------------------------------------------------------------
# Gancho de materiales: vetas, tablas, duelas, cristal con fuego fatuo, mimbre, pelo, pintura
# ---------------------------------------------------------------------------------------------

def gancho(P, mat, inten, nz, nr, spec, lvl, ex):
    A = ex['A']
    Pl = (P - V(0, LIFT, 0)) @ A           # coordenadas del modelo (A es una rotación)
    nl = nr @ A
    t = ex['tilt']
    Uc = V(0, math.cos(t), -math.sin(t))
    vista = V(0, math.sin(t), math.cos(t)) @ A
    for m, g in GANANCIA.items():
        inten[mat == m] *= g
    obj = ex.get('obj', '')
    # --- madera de caja: tablas horizontales en los costados, a lo largo en el fondo y la tapa
    sel = mat == PINO
    if sel.any():
        q, n = Pl[sel], nl[sel]
        tabla = ex.get('tabla', 3.6)
        lado = np.abs(n[:, 1]) < 0.6
        fx = np.abs(n[:, 0]) > 0.7
        v = np.where(lado, q[:, 1], q[:, 2])
        if 'tapa' in ex:                      # en la tapa, tablas en su plano
            hinge, Rt = ex['tapa']
            qt = (q - hinge) @ Rt
            en_tapa = (qt[:, 1] > -0.2) & (qt[:, 1] < 1.4) & (np.abs(qt[:, 0]) < 9.5)
            v = np.where(en_tapa, qt[:, 2], v)
        junta = np.abs(((v + 0.3) / tabla) % 1.0 - 0.5) > 0.42
        grano = vnoise(np.column_stack([np.where(fx, q[:, 2], q[:, 0]) * 0.25, q[:, 1] * 2.5, q[:, 2] * 2.5]), 1.0, 3)
        ii = inten[sel]
        ii += 0.1 * (grano - 0.5)
        ii[junta] -= 0.34
        # cantos más claros (madera gastada en las aristas de arriba)
        inten[sel] = ii
    # --- duelas del barril (eje vertical en el origen) y su tapa
    sel = mat == ROBLE
    if sel.any() and obj in ('barril',):
        q, n = Pl[sel], nl[sel]
        th = np.arctan2(q[:, 0], q[:, 2])
        nd = ex.get('duelas', 16)
        f = (th / (2 * math.pi) * nd + 0.25) % 1.0
        k = np.floor(th / (2 * math.pi) * nd + 0.25).astype(int) % nd
        tono = (np.sin(k * 12.9898) * 43758.5453) % 1.0
        ii = inten[sel]
        tapa = n[:, 1] > 0.75
        ii += np.where(tapa, 0, 0.14 * (tono - 0.5))
        grano = vnoise(np.column_stack([q[:, 0] * 2.2, q[:, 1] * 0.3, q[:, 2] * 2.2]), 1.0, 7)
        ii += 0.14 * (grano - 0.5)
        ancho = ex.get('junta', 0.06)
        junta = ((f < ancho) | (f > 1 - ancho)) & ~tapa
        jt = tapa & (np.abs((q[:, 0] + 0.5) / 3.4 % 1.0 - 0.5) > 0.4)
        ii[junta | jt] -= 0.32
        inten[sel] = ii
        # calavera pintada con cal en la panza (marca de peligro)
        cal = (~tapa) & (n[:, 2] > 0.25) & calavera(q[:, 0], q[:, 1], ex.get('calavera', (0.0, 14.0)))
        idx = np.nonzero(sel)[0]
        mat[idx[cal]] = CAL
        inten[idx[cal]] = 0.55 + 0.6 * np.clip(n[cal, 2], 0, 1) - 0.12 * (vnoise(q[cal], 1.3, 9) > 0.62)
        # fuego por las juntas (explosión): las juntas pasan a LUMBRE
        if ex.get('lumbre', 0) > 0:
            arde = (junta | jt) & (vnoise(q * np.array([0.6, 0.12, 0.6]), 1.0, 13) < ex['lumbre'])
            mat[idx[arde]] = LUMBRE
            lvl[idx[arde]] = np.clip(1.5 + 4.5 * ex['lumbre'] - 0.12 * (q[arde, 1] - 12), 1, 7)
        if ex.get('fuego_dentro'):            # sin tapa: dentro arde (el fondo y las paredes del hueco)
            dentro = (q[:, 1] > BAR_C + BAR_H - 6.2) & (np.hypot(q[:, 0], q[:, 2]) < r_barril(BAR_C + BAR_H, 1.07) - 1.0)
            mat[idx[dentro]] = LUMBRE
            lvl[idx[dentro]] = 8
    # --- tablas del fondo y costados de la caja de cartón
    sel = mat == CARTON
    if sel.any():
        q = Pl[sel]
        inten[sel] += 0.08 * (vnoise(q, 0.7, 21) - 0.5)
        if 'etiqueta' in ex:
            (x0, x1, y0, y1) = ex['etiqueta']
            n = nl[sel]
            lab = (n[:, 2] > 0.7) & (q[:, 0] > x0) & (q[:, 0] < x1) & (q[:, 1] > y0) & (q[:, 1] < y1)
            idx = np.nonzero(sel)[0]
            mat[idx[lab]] = CARTON_R
            inten[idx[lab]] = 0.45 + 0.1 * (vnoise(q[lab], 1.0, 5) - 0.5)
    # --- plomo, latón, cobre: brillos
    sdf.apply_shine(mat, inten, spec, ((PLOMO, 0.55, 8), (LATON, 0.6, 10), (COBRE, 0.5, 8),
                                       (HIERRO, 0.35, 12), (PAPEL_R, 0.2, 6), (PAPEL_Y, 0.2, 6),
                                       (PAPEL_G, 0.2, 6), (CARTON_R, 0.25, 8)))
    # --- mimbre: hileras trenzadas; por algunas rendijas asoma el resplandor azul
    sel = mat == MIMBRE
    if sel.any():
        q = Pl[sel]
        th = np.arctan2(q[:, 0], q[:, 2])
        rr = np.hypot(q[:, 0], q[:, 2])
        alto = 1.6
        fila = np.floor(q[:, 1] / alto)
        arco = th * rr
        seg = np.floor((arco + (fila % 2) * 1.5) / 3.0)
        ii = inten[sel]
        ii += 0.14 * np.where(seg % 2 == 0, 1, -1)
        entre = (q[:, 1] / alto) % 1.0 < 0.26
        ii[entre] -= 0.25
        inten[sel] = ii
        if 'llamas' in ex and ex.get('rendijas', True):
            h = (np.sin(fila * 7.13 + seg * 3.71) * 9187.31) % 1.0
            hueco = entre & (h < 0.35) & (q[:, 1] < ex.get('mimbre_top', 99) - 1.0)
            idx = np.nonzero(sel)[0]
            mat[idx[hueco]] = VIDRIO
    # --- pelo de cabra del zurrón: manchas claras y mechones
    sel = mat == PIEL
    if sel.any():
        q = Pl[sel]
        mancha = (vnoise(q * np.array([1.0, 0.8, 1.0]), 0.42, 41) * 0.75 + vnoise(q, 1.1, 42) * 0.25) > 0.62
        idx = np.nonzero(sel)[0]
        mat[idx[mancha]] = PIEL_B
        pelo = vnoise(np.column_stack([q[:, 0] * 2.4, q[:, 1] * 0.45, q[:, 2] * 2.4]), 1.0, 43)
        inten[idx] += 0.22 * (pelo - 0.5)
        # pliegues que suben hacia el atado (más marcados arriba)
        th = np.arctan2(q[:, 0], q[:, 2])
        sube = np.clip((q[:, 1] - 4.0) / 10.0, 0, 1)
        inten[idx] += 0.2 * sube * np.sin(th * 7.0 + 0.25 * q[:, 1])
    # --- cristal: lo que se ve a través (fuegos fatuos), oscuro en los bordes, brillo arriba
    sel = mat == VIDRIO
    if sel.any() and 'llamas' in ex:
        q = Pl[sel]
        sx, sy = q[:, 0], q @ Uc
        lv = np.full(len(q), -1.0)
        for c, fr in ex['llamas']:
            c = V(c)
            calor, dist = farol.fuego2d(sx - c[0], sy - c @ Uc, fr)
            lv = np.maximum(lv, farol.niveles_llama(calor, dist, fr))
        n = nl[sel]
        ndv = np.abs(n @ vista)
        mugre = vnoise(q, 0.8, 33) * 0.65 + vnoise(q, 2.0, 34) * 0.35
        llama = lv >= farol.L_LLAMA
        lv = lv - np.where(llama, 1.0, 5.0) * (1 - ndv) ** 1.5 - np.where(llama, 0.5, 2.5) * np.clip((mugre - 0.5) / 0.2, 0, 1)
        if 'mimbre_top' in ex:                # bajo el mimbre (rendijas): algo más oscuro
            lv = np.where(q[:, 1] < ex['mimbre_top'], lv - 2.0, lv)
        idx = np.nonzero(sel)[0]
        lvl[idx] = np.clip(lv, 1, farol.N_V - 1)
        # brillo de la luz en el cristal: arriba a la izquierda
        br = (spec[idx] > 0.93) & (n[:, 1] > -0.2)
        mat[idx[br]] = REFLEJO
        inten[idx[br]] = 0.7 + 0.5 * (spec[idx[br]] - 0.93) / 0.07
    # --- trapo: arrugas
    sel = mat == TRAPO
    if sel.any():
        q = Pl[sel]
        th = np.arctan2(q[:, 0], q[:, 2])
        inten[sel] += 0.15 * np.sin(th * 7 + 2.0 * vnoise(q, 1.0, 51))
    # --- pólvora: granos que brillan un poco
    sel = mat == POLVORA
    if sel.any():
        q = Pl[sel]
        inten[sel] += 0.35 * (vnoise(q, 2.6, 61) > 0.72)
    # --- mecha retorcida y brasa
    sel = mat == MECHA
    if sel.any():
        inten[sel] += 0.18 * np.sign(np.sin(Pl[sel] @ np.array([2.6, 3.4, 2.2])))
    sel = mat == BRASA
    if sel.any() and 'brasa' in ex:
        c, rr = ex['brasa']
        d = _len(Pl[sel] - V(c))
        lvl[sel] = np.clip((1.0 - d / rr) * 9, 1, 7)


def calavera(x, y, c):
    """Máscara de la calavera pintada (coordenadas de la superficie del barril vista de frente)."""
    cx, cy = c
    u, v = x - cx, y - cy
    craneo = (u / 4.4) ** 2 + ((v - 1.6) / 3.9) ** 2 < 1.0
    mandibula = (np.abs(u) < 2.7) & (v > -4.3) & (v < -0.8)
    pomulos = ((u / 3.6) ** 2 + ((v + 0.4) / 2.2) ** 2) < 1.0
    forma = craneo | mandibula | pomulos
    ojos = (((np.abs(u) - 1.85) / 1.3) ** 2 + ((v - 0.9) / 1.35) ** 2) < 1.0
    nariz = (v < -0.3) & (v > -1.9) & (np.abs(u) < 0.25 + 0.5 * (v + 1.9) / 1.6)
    nariz &= (np.abs(u) < 0.95)
    dientes = (v < -2.0) & (v > -4.3) & ((np.abs((u + 0.15) / 1.25 % 1.0 - 0.5) > 0.36) | (np.abs(v + 3.1) < 0.28))
    return forma & ~ojos & ~nariz & ~dientes


# ---------------------------------------------------------------------------------------------
# Los objetos
# ---------------------------------------------------------------------------------------------

def bolsita():
    """CLIPA0: bolsita de cuero con balas de plomo asomando por la boca y una suelta en el suelo."""
    cuerpo = con_corte(Ellipsoid((0, 4.2, 0), (4.9, 4.4, 4.3), mat=CUERO), lambda P: 0.2 - P[:, 1])
    cuello = cil((0, 6.6, 0), (0, 8.2, 0), 3.6, CUERO, 2.8)
    labio = anillo((0, 8.5, 0), 3.0, 3.0, 0.75, CUERO)
    bolsa = Group([cuerpo, cuello, labio], k=1.0)
    cordon = Group([anillo((0, 7.4, 0), 3.15, 3.15, 0.5, CUERDA), Sphere((2.2, 7.3, 2.2), 0.8, CUERDA),
                    RoundCone((2.3, 7.1, 2.4), (3.5, 4.3, 3.8), 0.45, 0.42, CUERDA)])
    balas = Group([Sphere(c, 1.6, PLOMO) for c in
                   ((-1.3, 9.5, -0.2), (1.35, 9.6, -0.5), (0.0, 10.8, 0.4), (-0.2, 9.4, 1.6),
                    (6.1, 1.6, 2.0))])
    return [bolsa, cordon, balas], {'obj': 'bolsita'}, 26


def caja_balas():
    """AMMOA0: caja de pino con la tapa abierta, llena de balas de plomo y unos cebos de cobre."""
    caja = caja_abierta((0, 3.4, 0), (9.0, 3.4, 5.0), 1.0, PINO)
    # la tapa, abierta hacia atrás sobre las bisagras del canto de atrás
    hinge = V(0, 6.8, -5.0)
    Rt = rot_x(rad(-62))
    tapa = Box(hinge + Rt @ V(0, 0.55, 5.0), (9.0, 0.55, 5.0), M=Rt, rnd=0.3, mat=PINO)
    rng = np.random.default_rng(7)
    balas = []
    for j, z in enumerate((-2.6, 0.5, 3.4)):
        for i, x in enumerate(np.linspace(-6.4, 6.4, 5) + (0.0 if j % 2 else 1.5)):
            if x > 7.0:
                continue
            jx, jz = rng.uniform(-0.3, 0.3, 2)
            y = 6.0 + 1.0 * math.exp(-(x * x / 28 + z * z / 10)) + rng.uniform(-0.2, 0.2)
            balas.append(Sphere((x + jx, y, z + jz), 1.7, PLOMO))
    cebos = []
    for k in range(3):
        x, z = rng.uniform(-6.5, 6.5), rng.uniform(-3.2, 3.2)
        y = 6.0 + 1.0 * math.exp(-(x * x / 28 + z * z / 10)) + 1.5
        z = abs(z) + 0.5
        e = sdf.nrm(V(rng.uniform(-0.5, 0.5), 1.0, rng.uniform(-0.5, 0.5)))
        cebos.append(cil(V(x, y, z) - e * 0.3, V(x, y, z) + e * 0.3, 0.7, COBRE))
    ex = {'obj': 'caja_balas', 'tapa': (hinge, Rt), 'tabla': 3.6}
    return [Group([caja]), Group([tapa]), Group(balas), Group(cebos)], ex, 38


def cartuchos4():
    """SHELA0: tres cartuchos de pie y uno tumbado delante."""
    grupos = []
    for base, eje in (((-5.5, 0.0, 0.8), (-0.08, 1, 0.02)), ((-1.85, 0.0, -2.2), (0.03, 1, -0.03)),
                      ((1.85, 0.0, 1.4), (-0.03, 1, 0.05)), ((5.55, 0.0, -1.2), (0.1, 1, 0.0))):
        grupos.append(Group(cartucho(base, eje, L=8.6, r=1.5, laton=2.5)))
    return grupos, {'obj': 'cartuchos'}, 22


def caja_cartuchos():
    """SBOXA0: caja de cartón abierta con dos filas de cartuchos de pie (latón arriba)."""
    caja = caja_abierta((0, 2.5, 0), (12.6, 2.5, 5.4), 0.7, CARTON, rnd=0.25, fondo=0.8)
    hinge = V(0, 5.0, -5.4)
    Rt = rot_x(rad(-104))
    solapa = Box(hinge + Rt @ V(0, 0.2, 2.6), (12.6, 0.2, 2.6), M=Rt, rnd=0.1, mat=CARTON)
    filas = []
    for z, dx, n in ((2.3, 0.0, 7), (-2.3, 1.7, 6)):
        prims = []
        for i in range(n):
            x = -10.2 + 3.4 * i + dx
            e = V(0.04 * math.sin(i * 2.1), -1, 0.04 * math.cos(i * 1.7))
            prims += cartucho(V(x, 0.8, z) - e * 10.4, e, L=10.4, r=1.5, laton=2.2)
        filas.append(Group(prims))
    suelto = cartucho((9.0, 1.95, 8.2), (-1.0, 0.0, 0.12), L=8.6, r=1.5, laton=2.5)
    ex = {'obj': 'caja_cartuchos'}
    return [Group([caja]), Group([solapa])] + filas + [Group(suelto)], ex, 24


def un_cohete():
    """ROCKA0: un cohete de feria de pie, clavado en su varilla de caña."""
    prims, palo = cohete((0.6, 9.0, 0), (0, 1, 0), r=3.0, varilla=((-1, 0, 0.0), 9.0 + 10.5))
    # la varilla llega al suelo
    return [Group(prims), Group(palo)], {'obj': 'cohete'}, 22, rot_z(rad(-5))


def caja_cohetes():
    """BROKA0: caja de pino con cinco cohetes de feria tumbados (tres abajo y dos encima)."""
    caja = caja_abierta((0, 2.8, 0), (19.6, 2.8, 9.3), 1.0, PINO)
    grupos = [Group([caja])]
    # (lado del cono, desplazamiento, altura, z): cabeza con cola, las varillas por debajo de los otros
    for (sx, dx, y, z, gu) in ((-1, -1.4, 3.75, -5.45, 3), (1, 1.2, 3.75, 0.0, -2), (-1, 0.6, 3.75, 5.45, -3),
                               (1, -1.6, 8.45, -2.72, 4), (-1, 1.9, 8.45, 2.72, -2)):
        e = rot_y(rad(gu)) @ V(sx, 0.0, 0.0)
        cola = V(dx - sx * 0.4, y, z)
        prims, palo = cohete(cola, e, r=2.72, largo=(3.0, 3.0, 3.2, 3.0), cono=5.3,
                             varilla=((0, -0.8, 0.6), 18.0), ataduras=False)
        grupos += [Group(prims), Group(palo)]
    return grupos, {'obj': 'caja_cohetes', 'tabla': 2.8}, 30


LLAMA_TARRO = [((0.0, 3.4, 0.0), {'tam': 1.25, 'semilla': 5, 'fase': 0.6, 'brillo': 1.1, 'alcance': 1.25})]


def tarro():
    """CELLA0: tarro de cristal tapado con un trapo atado y un fuego fatuo azul dentro."""
    cuerpo = cil((0, 0.4, 0), (0, 7.2, 0), 5.8, VIDRIO)
    hombro = RoundCone(V(0, 7.2, 0), V(0, 8.6, 0), 5.3, 4.2, VIDRIO)
    cuello = cil((0, 8.2, 0), (0, 9.8, 0), 4.2, VIDRIO)
    vidrio = Group([cuerpo, hombro, cuello], k=1.2)
    trapo = Group([cil((0, 9.2, 0), (0, 10.6, 0), 4.6, TRAPO, 4.9),
                   Ellipsoid((0, 10.6, 0), (4.9, 1.2, 4.9), mat=TRAPO)], k=0.6)
    cordel = Group([anillo((0, 9.7, 0), 4.75, 4.75, 0.45, CUERDA), Sphere((3.3, 9.7, 3.4), 0.75, CUERDA)])
    ex = {'obj': 'tarro', 'llamas': LLAMA_TARRO}
    return [vidrio, trapo, cordel], ex, 22


LLAMAS_DAMAJUANA = [((-4.4, 13.6, 3.0), {'tam': 1.0, 'semilla': 7, 'fase': 1.1, 'brillo': 1.05, 'alcance': 1.1}),
                    ((4.0, 12.8, 3.0), {'tam': 1.05, 'semilla': 9, 'fase': 2.7, 'brillo': 1.05, 'alcance': 1.1}),
                    ((0.0, 17.2, 1.0), {'tam': 0.9, 'semilla': 11, 'fase': 4.0, 'brillo': 1.05, 'alcance': 1.1}),
                    ((-1.0, 7.0, 4.0), {'tam': 1.0, 'semilla': 13, 'fase': 0.3, 'brillo': 1.2, 'alcance': 1.8})]
MIMBRE_TOP = 12.6


def damajuana():
    """CELPA0: damajuana de cristal forrada de mimbre, con asas y tres fuegos fatuos dentro."""
    cuerpo = con_corte(Ellipsoid((0, 10.6, 0), (11.0, 10.4, 11.0), mat=VIDRIO), lambda P: 0.3 - P[:, 1])
    hombro = RoundCone(V(0, 17.0, 0), V(0, 22.0, 0), 5.8, 2.3, VIDRIO)
    cuello = cil((0, 21.0, 0), (0, 24.6, 0), 2.25, VIDRIO)
    labio = anillo((0, 24.5, 0), 2.3, 2.3, 0.6, VIDRIO)
    vidrio = Group([cuerpo, hombro, cuello, labio], k=2.0)
    corcho = Group([cil((0, 24.2, 0), (0, 26.6, 0), 1.9, CORCHO, 2.3)])
    forro = con_corte(Ellipsoid((0, 10.6, 0), (11.8, 11.2, 11.8), mat=MIMBRE),
                      lambda P: np.maximum(P[:, 1] - MIMBRE_TOP, -P[:, 1]))
    rr = 11.8 * math.sqrt(max(1 - ((MIMBRE_TOP - 10.6) / 11.2) ** 2, 0))
    borde = anillo((0, MIMBRE_TOP, 0), rr, rr, 0.95, MIMBRE)
    asas = [con_corte(anillo((sx * 9.2, MIMBRE_TOP + 0.6, 0), 2.6, 2.9, 0.75, MIMBRE, rot_x(math.pi / 2)),
                      lambda P: MIMBRE_TOP - 0.5 - P[:, 1]) for sx in (-1, 1)]
    mimbre = Group([forro, borde] + asas)
    ex = {'obj': 'damajuana', 'llamas': LLAMAS_DAMAJUANA, 'mimbre_top': MIMBRE_TOP}
    return [vidrio, corcho, mimbre], ex, 20


def zurron():
    """BPAKA0: zurrón de pastor de piel de cabra, boca fruncida y atada, correa con hebilla."""
    cuerpo = con_corte(Ellipsoid((0, 6.8, 0.4), (9.4, 7.0, 6.6), mat=PIEL), lambda P: 0.3 - P[:, 1])
    hombros = Ellipsoid((0.4, 12.4, 0), (6.8, 5.6, 5.0), mat=PIEL)
    cuello = RoundCone(V(0.6, 15.0, 0), V(2.0, 19.0, 0.4), 4.2, 2.2, PIEL)
    bolsa = Group([cuerpo, hombros, cuello], k=3.0)
    eje = sdf.nrm(V(0.45, 1.0, 0.1))           # la boca, fruncida y doblada hacia la derecha
    o = V(2.2, 19.2, 0.4)
    Rb = sdf.basis(eje, (0, 0, 1))
    Rb = np.column_stack([Rb[:, 0], eje, np.cross(Rb[:, 0], eje)])

    def ondas(P):
        q = (P - o) @ Rb
        th = np.arctan2(q[:, 0], q[:, 2])
        return q[:, 1] - (3.0 + 0.7 * np.sin(6 * th))
    boca = Group([con_corte(CappedCone(o - eje * 0.2, o + eje * 3.8, 2.2, 4.0, PIEL), ondas)])
    atado = Group([Ring(Frame(o + eje * 0.1, Rb), 2.5, 2.5, 0.85, CUERDA), Sphere(o + V(-1.2, -0.4, 2.0), 0.95, CUERDA),
                   RoundCone(o + V(-1.3, -0.8, 2.2), V(-0.6, 13.6, 5.6), 0.5, 0.45, CUERDA),
                   RoundCone(o + V(-1.6, -0.6, 2.0), V(-2.6, 14.4, 5.0), 0.5, 0.45, CUERDA)])
    pts = [V(-6.4, 12.6, 2.6), V(-8.8, 8.0, 4.0), V(-9.6, 3.0, 5.6), V(-8.6, 0.8, 8.4), V(-5.0, 0.7, 10.2),
           V(-1.6, 0.7, 10.6)]
    correa = [RoundCone(a, b, 1.0, 1.0, CUERO_OSC) for a, b in zip(pts[:-1], pts[1:])]
    hebilla = Box(V(-9.5, 4.6, 5.0), (0.7, 1.5, 1.4), M=rot_z(rad(-12)), rnd=0.3, mat=LATON)
    return [bolsa, boca, atado, Group(correa, k=0.4), Group([hebilla])], {'obj': 'zurron'}, 20


# --- barril de pólvora ---------------------------------------------------------------------
BAR_R, BAR_RV, BAR_C, BAR_H = 10.8, 30.0, 14.6, 14.2       # radio, radio vertical de la panza, centro, medio alto
AROS = (2.4, 5.3, 23.9, 26.8)
MECHA_PTS = [(2.6, 28.0, 1.8), (2.9, 30.6, 2.3), (4.4, 32.3, 2.8), (6.4, 32.7, 3.2)]


def r_barril(y, k=1.0):
    return k * BAR_R * math.sqrt(max(1 - ((y - BAR_C) / BAR_RV) ** 2, 0))


def barril(mecha=True, hinchado=1.0, sin_tapa=False):
    k = hinchado

    def corte(P):
        rxz = np.hypot(P[:, 0], P[:, 2])
        fuera = np.abs(P[:, 1] - BAR_C) - BAR_H
        hueco = np.maximum(rxz - (r_barril(BAR_C + BAR_H, k) - 1.1), (BAR_C + BAR_H - (6.0 if sin_tapa else 1.0)) - P[:, 1])
        return np.maximum(fuera, -hueco)
    cuerpo = con_corte(Ellipsoid((0, BAR_C, 0), (BAR_R * k, BAR_RV, BAR_R * k), mat=ROBLE), corte)
    aros = [anillo((0, y, 0), r_barril(y, k) + 0.25, r_barril(y, k) + 0.25, 0.72, HIERRO) for y in AROS]
    grupos = [Group([cuerpo]), Group(aros)]
    if mecha:
        tapon = cil((2.6, BAR_C + BAR_H - 1.6, 1.8), (2.6, BAR_C + BAR_H - 0.6, 1.8), 1.3, HIERRO)
        m = [RoundCone(V(a), V(b), 0.55, 0.5, MECHA) for a, b in zip(MECHA_PTS[:-1], MECHA_PTS[1:])]
        grupos.append(Group([tapon] + m))
        grupos.append(Group([Sphere(MECHA_PTS[-1], 0.8, BRASA)]))
    polvora = [Ellipsoid((5.4, 0.0, 9.6), (4.6, 1.5, 2.7), mat=POLVORA),
               Ellipsoid((1.6, 0.0, 10.6), (2.4, 0.9, 1.7), mat=POLVORA)]
    polvora += [Sphere(c, 0.55, POLVORA) for c in ((10.4, 0.3, 11.2), (-1.8, 0.3, 12.0), (8.8, 0.3, 12.6))]
    grupos.append(Group(polvora, k=0.8))
    ex = {'obj': 'barril', 'duelas': 16, 'brasa': (MECHA_PTS[-1], 1.0), 'calavera': (-0.6, 13.2)}
    return grupos, ex, 14


# ---------------------------------------------------------------------------------------------
# Efectos 2D: chispas de la mecha, humo, llamas de la explosión
# ---------------------------------------------------------------------------------------------

def estrella(img, x, y, tam, semilla, n_chispas=4, largo=(2, 4)):
    """Chisporroteo de la mecha: estrella blanca y amarilla con unas chispas sueltas."""
    H, W = img.shape[:2]
    blanco, amarillo, naranja = PAL[4], PAL[231], PAL[215]
    xi, yi = int(math.floor(x)), int(math.floor(y))

    def pon(px, py, c):
        if 0 <= px < W and 0 <= py < H:
            img[py, px, :3] = c
            img[py, px, 3] = 255
    for dx in range(-tam, tam + 1):
        pon(xi + dx, yi, amarillo if abs(dx) < tam else naranja)
    for dy in range(-tam, tam + 1):
        pon(xi, yi + dy, amarillo if abs(dy) < tam else naranja)
    if tam >= 2:
        for d in (-1, 1):
            pon(xi + d, yi + d, naranja)
            pon(xi + d, yi - d, naranja)
    pon(xi, yi, blanco)
    lluvia_chispas(img, x, y, n_chispas, tam + 1.0, tam + 3.5, largo, semilla, ['oro', 'oro', 'blanco'],
                   caida=0.6, dir_=-math.pi / 2, abre=1.6)


def humito(img, x, y, semilla, alto=7):
    """Hilo de humo gris que sube de la mecha (2D, solo donde no hay nada)."""
    H, W = img.shape[:2]
    rng = np.random.default_rng(semilla)
    gris = [PAL[i] for i in (99, 101, 103, 105)]
    for k in range(alto):
        px = int(round(x + 1.3 * math.sin(k * 0.9 + semilla) + rng.uniform(-0.3, 0.3)))
        py = int(round(y - k))
        if 0 <= px < W and 0 <= py < H and img[py, px, 3] == 0:
            img[py, px, :3] = gris[min(k * len(gris) // alto, len(gris) - 1)]
            img[py, px, 3] = 255


def lienzo_con_margen(img, arriba=0, lados=0):
    H, W = img.shape[:2]
    out = np.zeros((H + arriba, W + 2 * lados, 4), np.uint8)
    out[arriba:, lados:lados + W] = img
    return out


def dibujar_barril(lump):
    """BAR1A0/B0 (y BEXPA0, BEXPB0): barril trazado + chispas 2D → (img, offsets)."""
    if lump in ('BAR1A0', 'BAR1B0'):
        grupos, ex, tilt = barril()
    elif lump == 'BEXPA0':
        grupos, ex, tilt = barril(mecha=False)
        ex['lumbre'] = 0.35
    else:   # BEXPB0
        grupos, ex, tilt = barril(mecha=False, hinchado=1.07, sin_tapa=True)
        ex['lumbre'] = 0.9
        ex['junta'] = 0.075
        ex['fuego_dentro'] = True
    img, vista, _ = render_obj(grupos, tilt, ex)
    M = 12
    img = lienzo_con_margen(img, arriba=M + (16 if lump == 'BEXPB0' else 0), lados=M)
    ox, oy = M, M + (16 if lump == 'BEXPB0' else 0)
    if lump in ('BAR1A0', 'BAR1B0'):
        x, y = vista.px(MECHA_PTS[-1])
        x, y = x + ox + 0.6, y + oy - 0.4
        if lump == 'BAR1A0':
            estrella(img, x, y, 1, 71, n_chispas=3, largo=(1, 3))
            humito(img, x + 0.5, y - 3, 3, alto=4)
        else:
            estrella(img, x, y, 2, 72, n_chispas=4, largo=(2, 3))
            humito(img, x - 0.5, y - 4, 5, alto=5)
    elif lump == 'BEXPA0':
        x, y = vista.px((2.6, BAR_C + BAR_H - 0.6, 1.8))
        x, y = x + ox, y + oy
        llamita(img, x, y - 1.5, 3.2, 81)
        estrella(img, x, y - 2, 2, 82, n_chispas=7, largo=(2, 4))
    else:
        x, y = vista.px((0, BAR_C + BAR_H, 0))
        x, y = x + ox, y + oy
        llamarada_barril(img, x, y)
    vista.hw += ox
    vista.top += oy
    out, off, _ = recortar(img, vista, bajo_max=3)
    return out, off


def llamita(img, cx, cy, R, semilla):
    """Llamita naranja (2D) con la base en (cx, cy)."""
    H, W = img.shape[:2]
    x, y = malla(W, H, cx, cy)
    yy = np.clip(y, 0, None)
    r = np.hypot(x * (1.0 + yy / (2.2 * R)), np.where(y < 0, y * 1.6, y * 0.55))
    n = fbm2(x * 0.6, y * 0.4, 1.0, semilla)
    calor = 1.05 - r / R - 0.6 * np.clip(n - 0.45, 0, None)
    pintar_fuego(img, calor, W, H)


def llamarada_barril(img, cx, cy):
    """BEXPB0: la tapa salta y sale una llamarada por arriba (2D, encima del barril)."""
    H, W = img.shape[:2]
    x, y = malla(W, H, cx, cy)
    yy = np.clip(y, 0, None)
    ancho = 8.5 + 0.35 * yy
    r = np.hypot(x / ancho * 8.5, np.where(y < 0, y * 2.5, y * 0.55))
    th = np.arctan2(y, x)
    n = fbm2(x * 0.5, y * 0.35, 1.0, 91)
    calor = 1.12 - r / 11.0 - 0.9 * np.clip(n - 0.42, 0, None) * (0.4 + yy / 10.0)
    calor = np.where(y > -2.5, calor, -1)
    pintar_fuego(img, calor, W, H)
    lluvia_chispas(img, cx, cy - 8, 12, 9, 15, (2, 4), 92, ['oro', 'oro', 'rojo', 'blanco'], caida=0.4,
                   dir_=-math.pi / 2, abre=1.3, encima=False)


# --- la explosión: bola de fuego, duelas y aros volando (C-E) ----------------------------------

def duelas_volando(fr):
    """Trozos del barril en vuelo para el fotograma fr: [(centro, rotación, medidas, material)]."""
    rng = np.random.default_rng({'C': 101, 'D': 102, 'E': 103}[fr])
    piezas = []
    dist = {'C': 13.0, 'D': 21.0, 'E': 25.0}[fr]
    alto = {'C': 16.0, 'D': 22.0, 'E': 18.0}[fr]
    n = {'C': 9, 'D': 8, 'E': 5}[fr]
    for k in range(n):
        a = (k + rng.uniform(-0.3, 0.3)) * 2 * math.pi / n + 0.3
        rr = dist * rng.uniform(0.8, 1.15)
        x, yy = math.cos(a) * rr, math.sin(a) * rr * 0.85
        if fr == 'E':
            yy = -abs(yy) * 0.6 - 4.0 + rng.uniform(-2, 2)
        z = rng.uniform(-6, 6)
        ax = sdf.nrm(rng.normal(size=3))
        R = rot_axis(ax, rng.uniform(0, 2 * math.pi)) @ rot_z(a - math.pi / 2)
        piezas.append((V(x, alto + yy, z), R, V(1.6, rng.uniform(4.5, 7.0), 0.6), ROBLE))
    if fr == 'C':
        # un aro de hierro que sale disparado hacia arriba, casi de canto
        piezas.append((V(-4.0, alto + dist * 0.95, 1.0), rot_x(rad(78)) @ rot_z(rad(28)), None, HIERRO))
    return piezas


def render_piezas(piezas, delante, fuego_c):
    prims = []
    for c, R, h, m in piezas:
        if (c[2] >= 0) != delante:
            continue
        if h is None:
            prims.append(Ring(Frame(c, R), 6.5, 6.5, 0.6, m))
        else:
            prims.append(Box(c, h, M=R, rnd=0.35, mat=m))
    if not prims:
        return None
    grupos = [Group([p]) for p in prims]
    ex = {'obj': 'piezas', 'flash_light': (V(fuego_c) + V(0, LIFT, 0), 34.0)}
    img, vista, _ = render_obj(grupos, 14, ex)
    return img, vista


def pegar(dst, src, x0, y0):
    H, W = dst.shape[:2]
    h, w = src.shape[:2]
    for yy in range(h):
        ty = y0 + yy
        if not 0 <= ty < H:
            continue
        for xx in range(w):
            tx = x0 + xx
            if 0 <= tx < W and src[yy, xx, 3] > 0:
                dst[ty, tx] = src[yy, xx]


LIENZO_BEXP = {'C': (40, 44), 'D': (58, 54), 'E': (62, 56)}


def explosion(fr):
    """BEXPC0-E0: (img, offsets) con la base en el suelo y centrada en el barril."""
    W, H = LIENZO_BEXP[fr]
    cx = W / 2
    alto = {'C': 16.0, 'D': 22.0, 'E': 22.0}[fr]
    cy = H - alto
    img = np.zeros((H, W, 4), np.uint8)
    piezas = duelas_volando(fr)
    # trozos de detrás
    detras = render_piezas(piezas, False, (0, alto, 0))
    if detras is not None:
        im, v = detras
        pegar(img, im, int(round(cx - v.hw)), int(round(H - (v.top - LIFT * v.Uc[1]))))
    capa = np.zeros_like(img)
    x, y = malla(W, H, cx, cy)
    th = np.arctan2(y, x)
    sem = {'C': 111, 'D': 112, 'E': 113}[fr]
    lob = fbm2(np.cos(th) * 3.0, np.sin(th) * 3.0, 1.0, sem)
    ruido = fbm2(x, y, 0.22, sem + 3)
    if fr == 'C':
        R = 14.0 * (0.7 + 0.55 * lob)
        r = np.hypot(x, np.where(y > 0, y * 0.8, y * 1.15))
        calor = 1.2 - r / R + 0.45 * (ruido - 0.5)
        pintar_fuego(capa, calor, W, H)
        dens = (fbm2(x, y, 0.2, sem + 8) > 0.66) & (y > 10) & (r < R + 3)
        pintar_humo(capa, dens.astype(float), np.clip(0.35 + y / 30.0, 0, 1), W, H, calido=(y < 14).astype(float))
        lluvia_chispas(capa, cx, cy, 16, 13, 20, (2, 5), sem, ['oro', 'oro', 'rojo', 'blanco'], caida=0.6,
                       aplasta=0.9, encima=False)
    elif fr == 'D':
        R = 22.0 * (0.7 + 0.5 * lob)
        r = np.hypot(x, np.where(y > 0, y * 0.85, y * 1.1))
        calor = 1.25 - r / R + 0.5 * (ruido - 0.5)
        pintar_fuego(capa, calor, W, H)
        dens = (fbm2(x, y, 0.15, sem + 8) > 0.55) & (y > 12) & (r < R + 5)
        pintar_humo(capa, dens.astype(float), np.clip(0.3 + y / 40.0, 0, 1), W, H, calido=(y < 18).astype(float))
        lluvia_chispas(capa, cx, cy, 24, 21, 28, (3, 6), sem, ['oro', 'oro', 'rojo', 'blanco'], caida=0.9,
                       aplasta=0.9, encima=False)
    else:
        R = 25.0 * (0.72 + 0.5 * lob)
        r = np.hypot(x, np.where(y > 0, y * 0.85, y * 1.1))
        base = np.clip(1.0 - r / R, 0, 1)
        n = fbm2(x, y, 0.15, sem + 4)
        calor = base * 2.0 * (n - 0.38) + 0.2 * np.clip(1 - r / 8.0, 0, 1)
        calor = np.where(base > 0.02, calor, -1.0)
        pintar_fuego(capa, calor * 0.75, W, H)
        dens = ((base > 0.04) & (fbm2(x, y, 0.1, sem + 8) > 0.4)).astype(float)
        luz = np.clip(0.25 + (y + 10) / 50.0 + 0.3 * (fbm2(x, y, 0.3, sem + 2) - 0.5), 0, 1)
        pintar_humo(capa, dens, luz, W, H, calido=(base > 0.5).astype(float))
        lluvia_chispas(capa, cx, cy, 16, 24, 31, (2, 4), sem, ['oro', 'rojo', 'oro'], caida=2.5,
                       aplasta=0.9, nivel=1, encima=False)
    sel = capa[..., 3] > 0
    img[sel] = capa[sel]
    delante = render_piezas(piezas, True, (0, alto, 0))
    if delante is not None:
        im, v = delante
        pegar(img, im, int(round(cx - v.hw)), int(round(H - (v.top - LIFT * v.Uc[1]))))
    ys, xs = np.nonzero(img[..., 3] > 0)
    # recorte simétrico respecto a cx, base en el suelo
    need = int(math.ceil(max(cx - xs.min(), xs.max() + 1 - cx)))
    x0 = int(round(cx)) - need
    pad = max(0, -x0, x0 + 2 * need - W)
    if pad:
        img = np.pad(img, ((0, 0), (pad, pad), (0, 0)))
        x0 += pad
    out = img[ys.min():, x0:x0 + 2 * need]
    return out, [need, out.shape[0]]


# ---------------------------------------------------------------------------------------------
# Lumps
# ---------------------------------------------------------------------------------------------

OBJETOS = {'CLIPA0': bolsita, 'AMMOA0': caja_balas, 'SHELA0': cartuchos4, 'SBOXA0': caja_cartuchos,
           'ROCKA0': un_cohete, 'BROKA0': caja_cohetes, 'CELLA0': tarro, 'CELPA0': damajuana,
           'BPAKA0': zurron}
LUMPS = list(OBJETOS) + ['BAR1A0', 'BAR1B0', 'BEXPA0', 'BEXPB0', 'BEXPC0', 'BEXPD0', 'BEXPE0']


def dibujar(lump):
    if lump in OBJETOS:
        r = OBJETOS[lump]()
        grupos, ex, tilt = r[:3]
        A = r[3] if len(r) > 3 else None
        img, vista, _ = render_obj(grupos, tilt, ex, A)
        out, off, _ = recortar(img, vista)
        return out, off
    if lump[:4] in ('BAR1',) or lump in ('BEXPA0', 'BEXPB0'):
        return dibujar_barril(lump)
    return explosion(lump[4])


def hoja(carpeta, ruta, offsets, escala=4):
    """Hoja de contactos: cada lump nuestro junto al de Freedoom a la misma escala, con la línea del
    suelo (roja) y el eje (marca roja)."""
    sys.path.insert(0, os.path.join(sdf.RAIZ, 'tools', 'wad'))
    from doomgfx import decode_patch, read_wad
    _, lumps = read_wad(IWAD_REF)
    fd = {}
    dentro = False
    for n, d in lumps:
        if n == 'S_START':
            dentro = True
        elif n == 'S_END':
            dentro = False
        elif dentro and n in LUMPS:
            fd[n] = decode_patch(d, PAL)
    filas = [['CLIPA0', 'AMMOA0', 'SHELA0', 'SBOXA0', 'ROCKA0', 'BROKA0'],
             ['CELLA0', 'CELPA0', 'BPAKA0', 'BAR1A0', 'BAR1B0'],
             ['BEXPA0', 'BEXPB0', 'BEXPC0', 'BEXPD0', 'BEXPE0']]
    celdas = []
    for fila in filas:
        c = []
        for n in fila:
            p = os.path.join(carpeta, n + '.png')
            if not os.path.exists(p):
                continue
            c.append((n, Image.open(p).convert('RGBA'), offsets.get(n), fd.get(n)))
        celdas.append(c)
    ancho = max(sum((im.width + (f[0].width if f else 0)) * escala + 40 for _, im, _, f in c) for c in celdas) + 20
    altos = [max(max(im.height, f[0].height if f else 0) for _, im, _, f in c) * escala + 50 for c in celdas]
    S = Image.new('RGB', (ancho, sum(altos)), (92, 92, 100))
    d = ImageDraw.Draw(S)
    y = 0
    for c, hf in zip(celdas, altos):
        x = 10
        suelo = y + hf - 20
        for n, im, off, f in c:
            d.text((x, y + 4), f'{n} {im.width}x{im.height} {off}', fill=(240, 240, 240))
            for k, (pic, o) in enumerate(((im, off), f if f else (None, None))):
                if pic is None:
                    continue
                big = pic.resize((pic.width * escala, pic.height * escala), Image.NEAREST)
                top = suelo - (o[1] if o else pic.height) * escala
                S.paste(big, (x, top), big)
                if o:
                    d.line([(x + o[0] * escala, suelo - 4), (x + o[0] * escala, suelo + 4)], fill=(255, 50, 50))
                d.line([(x, suelo), (x + big.width, suelo)], fill=(255, 50, 50) if k == 0 else (60, 200, 255))
                x += big.width + 12
            x += 28
        y += hf
    S.save(ruta)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--salida', required=True, help='carpeta de PNG (arte/sprites)')
    ap.add_argument('--solo', default=None, help='solo estos lumps (separados por comas)')
    ap.add_argument('--hoja', default=None, help='PNG con la hoja de contactos junto a Freedoom')
    args = ap.parse_args()
    os.makedirs(args.salida, exist_ok=True)
    solo = [s.strip().upper() for s in args.solo.split(',')] if args.solo else None
    ruta_off = os.path.join(args.salida, 'offsets_municion.json')
    offsets = {}
    if os.path.exists(ruta_off):
        import json
        with open(ruta_off) as fh:
            offsets = json.load(fh)
    for n in LUMPS:
        if solo and n not in solo:
            continue
        img, off = dibujar(n)
        Image.fromarray(img, 'RGBA').save(os.path.join(args.salida, n + '.png'))
        offsets[n] = [int(off[0]), int(off[1])]
        print(f'{n}: {img.shape[1]}x{img.shape[0]} offsets {offsets[n]}', flush=True)
    guardar_offsets(args.salida, offsets, 'municion')
    if args.hoja:
        hoja(args.salida, args.hoja, offsets)


if __name__ == '__main__':
    main()
