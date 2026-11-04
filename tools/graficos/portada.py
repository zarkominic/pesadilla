#!/usr/bin/env python3
"""portada.py — pantalla de título (TITLEPIC) y logotipo del menú (M_DOOM), dibujados por código.

La portada lleva el título, el protagonista con su bandana y «Adaptación hecha por Novak M.».
Uso: portada.py --salida arte/graficos
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(__file__))
from cara import W as CW, H as CH, cara  # noqa: E402

# Letras del título como trazos en una caja 0..1 (ancho) × 0..1 (alto).
TRAZOS = {
    'P': [[(0.1, 1), (0.1, 0), (0.8, 0), (0.95, 0.15), (0.95, 0.42), (0.8, 0.56), (0.1, 0.56)]],
    'E': [[(0.95, 0), (0.1, 0), (0.1, 1), (0.95, 1)], [(0.1, 0.5), (0.72, 0.5)]],
    'S': [[(0.95, 0.12), (0.8, 0), (0.2, 0), (0.05, 0.14), (0.05, 0.38), (0.2, 0.5), (0.8, 0.5), (0.95, 0.62), (0.95, 0.86), (0.8, 1), (0.2, 1), (0.05, 0.88)]],
    'A': [[(0.05, 1), (0.5, 0), (0.95, 1)], [(0.24, 0.62), (0.76, 0.62)]],
    'D': [[(0.1, 0), (0.1, 1), (0.7, 1), (0.95, 0.76), (0.95, 0.24), (0.7, 0), (0.1, 0)]],
    'I': [[(0.5, 0), (0.5, 1)]],
    'L': [[(0.1, 0), (0.1, 1), (0.95, 1)]],
}

# Letra pequeña 5x7 (+2 de descenso), solo lo que hace falta: «Adaptación hecha por Novak M.»
PEQ = {
    'A': '01110 10001 10001 11111 10001 10001 10001', 'N': '10001 11001 10101 10011 10001 10001 10001',
    'M': '10001 11011 10101 10101 10001 10001 10001', '.': '00000 00000 00000 00000 00000 00000 00100',
    'a': '00000 00000 01110 00001 01111 10001 01111', 'c': '00000 00000 01110 10000 10000 10001 01110',
    'd': '00001 00001 01101 10011 10001 10011 01101', 'e': '00000 00000 01110 10001 11111 10000 01110',
    'h': '10000 10000 10110 11001 10001 10001 10001', 'i': '00100 00000 01100 00100 00100 00100 01110',
    'k': '10000 10000 10010 10100 11000 10100 10010', 'n': '00000 00000 10110 11001 10001 10001 10001',
    'o': '00000 00000 01110 10001 10001 10001 01110', 'ó': '00010 00100 01110 10001 10001 10001 01110',
    'p': '00000 00000 11110 10001 10001 11110 10000 10000', 'r': '00000 00000 10110 11001 10000 10000 10000',
    't': '01000 01000 11100 01000 01000 01001 00110', 'v': '00000 00000 10001 10001 10001 01010 00100',
    ' ': '00000',
}
CREDITO = 'Adaptación hecha por Novak M.'


def texto(img, s, x, y, color):
    px = img.load()
    for ch in s:
        for j, fila in enumerate(PEQ[ch].split()):
            for i, c in enumerate(fila):
                if c == '1':
                    px[x + i, y + j] = color
        x += 6
    return x


def titulo(ancho, alto, grosor, sobre=4, gotas=True, semilla=7):
    """Máscara del texto PESADILLA (bool) con goterones; se dibuja con sobremuestreo."""
    letras = 'PESADILLA'
    pesos = [0.5 if c == 'I' else 1 for c in letras]
    sep = 0.12
    unidad = ancho / (sum(pesos) + sep * (len(letras) - 1))
    S = 4
    m = Image.new('L', (ancho * S, alto * S), 0)
    d = ImageDraw.Draw(m)
    xp = 0
    mg = grosor / 2 + 1
    rng = np.random.default_rng(semilla)
    h_l = alto - sobre - 2 * mg
    for c, p in zip(letras, pesos):
        aw = unidad * p
        for tr in TRAZOS[c]:
            pts = [((xp + mg * 0.6 + a * (aw - mg * 1.2)) * S, (mg + b * h_l) * S) for a, b in tr]
            d.line(pts, fill=255, width=int(grosor * S), joint='curve')
            for q in (pts[0], pts[-1]):  # remates cuadrados
                g = grosor * S / 2
                d.rectangle((q[0] - g, q[1] - g, q[0] + g, q[1] + g), fill=255)
        xp += aw + unidad * sep
    a = np.array(m.resize((ancho, alto), Image.BOX)) > 110
    if gotas:  # sangre que chorrea desde las partes bajas de las letras
        for x in rng.integers(1, ancho - 1, ancho // 6):
            ys = np.nonzero(a[:, x])[0]
            if len(ys) and ys[-1] < alto - 2:
                n = int(rng.integers(1, sobre + 1))
                a[ys[-1]:min(alto, ys[-1] + n + 1), x] = True
    return a


def pinta_titulo(rgb, mask, x0, y0, rel=(232, 32, 24), med=(176, 16, 16), som=(100, 0, 0)):
    h, w = mask.shape
    for y in range(h):
        for x in range(w):
            if mask[y, x]:
                t = y / max(1, h - 1)
                rgb[y0 + y, x0 + x] = rel if t < 0.35 else (med if t < 0.72 else som)
    # Sombra negra a la derecha y abajo.
    return rgb


def portada():
    w, h = 320, 200
    rng = np.random.default_rng(3)
    ys, xs = np.mgrid[0:h, 0:w]
    # Cielo de noche roja y luna.
    # Cielo con rojos que existen en la paleta del juego y trama ordenada entre ellos (si no, salen franjas).
    RAMPA = np.array([(7, 7, 7), (47, 0, 0), (67, 0, 0), (83, 0, 0), (107, 0, 0), (131, 0, 0)], float)
    BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16
    v = np.clip((ys - 40) / 125, 0, 1) ** 1.3 * (len(RAMPA) - 1)
    rgb = RAMPA[np.minimum((v + BAYER[ys % 4, xs % 4]).astype(int), len(RAMPA) - 1)]
    luna = ((xs - 256) ** 2 + (ys - 92) ** 2) < 26 ** 2
    rgb[luna] = (224, 188, 132)
    crater = (((xs - 248) ** 2 + (ys - 84) ** 2) < 7 ** 2) | (((xs - 266) ** 2 + (ys - 102) ** 2) < 5 ** 2) | (((xs - 262) ** 2 + (ys - 80) ** 2) < 3 ** 2)
    rgb[luna & crater] = (188, 148, 100)
    # Estrellas.
    for _ in range(50):
        x, y = rng.integers(0, w), rng.integers(44, 120)
        if not luna[y, x]:
            rgb[y, x] = (200, 180, 160)
    # Pueblo en silueta: casas con tejado, campanario sin símbolos y cerro.
    im = Image.fromarray(rgb.astype(np.uint8), 'RGB')
    d = ImageDraw.Draw(im)
    cerro = [(0, 150), (40, 132), (80, 128), (130, 142), (190, 138), (250, 122), (290, 128), (320, 118), (320, 200), (0, 200)]
    d.polygon(cerro, fill=(47, 0, 0))
    x = -6
    while x < 322:
        an = int(rng.integers(14, 28))
        al = int(rng.integers(12, 26))
        base = 164
        d.rectangle((x, base - al, x + an, 200), fill=(14, 6, 8))
        d.polygon([(x - 2, base - al), (x + an / 2, base - al - an / 2.4), (x + an + 2, base - al)], fill=(14, 6, 8))
        if rng.random() < 0.45:  # ventana encendida
            vx, vy = x + int(rng.integers(3, an - 4)), base - int(rng.integers(5, al))
            d.rectangle((vx, vy, vx + 2, vy + 3), fill=(236, 164, 44))
        x += an + int(rng.integers(0, 5))
    d.rectangle((0, 152, 320, 200), fill=(14, 6, 8))  # sin huecos entre las casas
    d.rectangle((282, 104, 296, 170), fill=(14, 6, 8))  # torre
    d.polygon([(280, 104), (289, 90), (298, 104)], fill=(14, 6, 8))
    d.rectangle((287, 110, 291, 118), fill=(47, 0, 0))
    rgb = np.array(im, float)

    # Protagonista: busto con la bandana (la misma cara de la barra, a escala).
    k = 4
    c = cara(k, gesto='decidido', mira=0)
    fh, fw = c.shape[:2]
    x0, y0 = (w - fw) // 2, 56
    # Hombros y chaqueta.
    im = Image.fromarray(rgb.astype(np.uint8), 'RGB')
    d = ImageDraw.Draw(im)
    d.polygon([(x0 - 34, 200), (x0 - 28, 176), (x0 + 8, 160), (x0 + fw - 8, 160), (x0 + fw + 28, 176), (x0 + fw + 34, 200)], fill=(44, 36, 28))
    d.polygon([(x0 + 18, 160), (x0 + fw - 18, 160), (x0 + fw // 2 + 8, 196), (x0 + fw // 2 - 8, 196)], fill=(124, 76, 48))
    d.rectangle((x0 + 30, 150, x0 + fw - 30, 172), fill=(128, 80, 50))
    rgb = np.array(im, float)
    vis = c[..., 3] > 0
    rgb[y0:y0 + fh, x0:x0 + fw][vis] = c[..., :3][vis]

    # Título, con sombra.
    m = titulo(300, 46, 8)
    sombra = np.zeros_like(rgb[..., 0], bool)
    sombra[8:8 + 46, 12:12 + 300] = m
    rgb[sombra] = (10, 2, 2)
    pinta_titulo(rgb, m, 10, 6)

    # Crédito sobre una banda oscura.
    an_t = len(CREDITO) * 6
    bx = (w - an_t) // 2
    rgb[186:200, bx - 8:bx + an_t + 8] = (8, 4, 4)
    img = Image.fromarray(rgb.astype(np.uint8), 'RGB')
    texto(img, CREDITO, bx, 188, (247, 207, 172))
    return img


def logo_menu():
    """M_DOOM: mismo tamaño que el original (159x37), fondo transparente."""
    w, h = 159, 37
    m = titulo(w - 1, h - 1, 4.6, sobre=3)
    rgb = np.zeros((h, w, 3), np.uint8)
    a = np.zeros((h, w), np.uint8)
    # Sombra.
    a[1:, 1:] = m * 255
    rgb[a > 0] = (20, 4, 4)
    mm = np.zeros((h, w), bool)
    mm[:h - 1, :w - 1] = m
    pinta_titulo(rgb, m, 0, 0)
    a[mm] = 255
    return Image.fromarray(np.dstack((rgb, a)), 'RGBA')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--salida', required=True)
    a = ap.parse_args()
    os.makedirs(a.salida, exist_ok=True)
    portada().save(os.path.join(a.salida, 'TITLEPIC.png'))
    logo_menu().save(os.path.join(a.salida, 'M_DOOM.png'))
    print('portada y logo')


if __name__ == '__main__':
    main()
