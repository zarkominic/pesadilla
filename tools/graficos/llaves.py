#!/usr/bin/env python3
"""llaves.py — iconos de llaves de la barra de estado (STKEYS0-8), a juego con los objetos del juego.

0-2: llaves de hierro con el ojo de color. 3-5: calaveras de hueso con ojos de color.
6-8: las dos a la vez. Orden del motor: azul, amarillo, rojo.
Uso: llaves.py --salida arte/graficos
"""
import argparse
import os

from PIL import Image

COLOR = {'azul': (((0, 0, 255), (0, 0, 155))), 'amarillo': ((255, 255, 0), (175, 123, 31)), 'rojo': ((255, 0, 0), (155, 0, 0))}
LLAVE = ['.CC....',
         'C.dC...',
         'C.dIIII',
         'C.dC.I.',
         '.CC.I..']
CALAVERA = ['.BBBBB.',
            'BBBBBBb',
            'BCCBCCb',
            'BCdBCdb',
            'BBB.BBb',
            '.BbBbb.',
            '.B.B.b.']
AMBAS = ['.BBBBB.',
         'BCCBCCb',
         'BBB.BBb',
         '.BbBbb.',
         'C.CIIII',
         '.C..I.I',
         '.......']


def pinta(dibujo, color):
    c, d = color
    tinta = {'C': c, 'd': d, 'I': (191, 191, 191), 'B': (239, 227, 191), 'b': (155, 127, 107)}
    h, w = len(dibujo), len(dibujo[0])
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    for y, fila in enumerate(dibujo):
        for x, q in enumerate(fila):
            if q != '.':
                im.putpixel((x, y), tinta[q] + (255,))
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--salida', required=True)
    a = ap.parse_args()
    os.makedirs(a.salida, exist_ok=True)
    for i, nombre in enumerate(('azul', 'amarillo', 'rojo')):
        pinta(LLAVE, COLOR[nombre]).save(os.path.join(a.salida, f'STKEYS{i}.png'))
        pinta(CALAVERA, COLOR[nombre]).save(os.path.join(a.salida, f'STKEYS{i + 3}.png'))
        pinta(AMBAS, COLOR[nombre]).save(os.path.join(a.salida, f'STKEYS{i + 6}.png'))
    print('9 iconos')


if __name__ == '__main__':
    main()
