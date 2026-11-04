#!/usr/bin/env python3
"""cara.py — la cara del protagonista en la barra de estado: bandana con la bandera de España.

Sustituye los 42 STF* (5 niveles de heridas × 8 gestos, más invencible y muerto). La misma función
dibuja a cualquier escala: k=1 para la barra (26x31) y k grande para el retrato de la portada.
Uso: cara.py --salida arte/graficos
"""
import argparse
import json
import os

import numpy as np
from PIL import Image

W, H = 26, 31
PIEL = np.array([(92, 54, 34), (128, 80, 50), (168, 112, 76), (204, 144, 104), (231, 180, 140), (247, 207, 172)], float)
PELO = np.array((38, 24, 14), float)
ROJO = np.array([(112, 8, 8), (160, 12, 12), (204, 20, 20)], float)
AMAR = np.array([(176, 124, 0), (224, 172, 0), (255, 215, 0)], float)
OSCURO = np.array((26, 14, 10), float)
SANGRE = np.array((132, 0, 0), float)
DIENTE = np.array((236, 232, 216), float)
BLANCO = np.array((228, 224, 212), float)

# Manchas de sangre (x, y, radio) desde el centro de la cara; salen más cuanto más herido.
HERIDAS = [(5, 20, 1.2), (19, 21, 1.4), (9, 26, 1.0), (17, 15.5, 1.1), (21, 24, 1.3), (7, 16, 1.0),
           (13, 27, 1.2), (4, 24, 1.0), (15, 23, 0.9), (10, 20.5, 0.9), (19, 27, 1.1), (6, 27, 1.0)]


def cara(k=1, mira=0, giro=0, gesto='normal', dolor=0):
    """Devuelve RGBA uint8 de (H*k, W*k). mira: pupilas -1..1. giro: cabeza -3..3 (+ = derecha)."""
    ys, xs = np.mgrid[0:H * k, 0:W * k]
    x, y = (xs + 0.5) / k, (ys + 0.5) / k
    rgb = np.zeros((H * k, W * k, 3))
    alfa = np.zeros((H * k, W * k), bool)

    cx = 13 + giro * 0.3      # centro de la cabeza
    fx = 13 + giro * 1.15     # centro de los rasgos (giran más que la cabeza)
    anc = 9.6 * np.clip(1 - np.abs((y - 15.5) / 13.6) ** 3, 0, 1) ** 0.6
    cabeza = np.abs(x - cx) < anc
    nx = (x - cx) / np.maximum(anc, 0.1)

    # Orejas (la del lado contrario al giro se ve más).
    for lado in (-1, 1):
        ox = cx + lado * (9.4 - max(0, giro * lado) * 0.5)
        oreja = ((x - ox) / 1.5) ** 2 + ((y - 18.5) / 2.3) ** 2 < 1
        rgb[oreja] = PIEL[2]
        alfa |= oreja

    # Piel con luz desde arriba a la izquierda; pómulos y barbilla.
    luz = 0.72 - 0.42 * nx - 0.012 * (y - 15) - 0.25 * np.clip(y - 24, 0, 5) / 5 * np.abs(nx)
    luz += 0.10 * np.exp(-(((x - fx + 5) / 2.2) ** 2 + ((y - 21) / 1.7) ** 2))
    luz += 0.08 * np.exp(-(((x - fx - 5) / 2.2) ** 2 + ((y - 21) / 1.7) ** 2))
    if gesto == 'muerto':
        luz -= 0.22
    if dolor >= 3:
        luz -= 0.06 * (dolor - 2)
    i = np.clip((luz * len(PIEL)).astype(int), 0, len(PIEL) - 1)
    rgb[cabeza] = PIEL[i][cabeza]
    alfa |= cabeza
    if gesto == 'furia':  # rojo de rabia
        rgb[cabeza] = rgb[cabeza] * np.array((1.05, 0.72, 0.68))

    # Barba de tres días (trama en la mandíbula).
    trama = ((xs // max(1, k // 2) + ys // max(1, k // 2)) % 2 == 0)
    barba = cabeza & (y > 23.2 - 1.5 * np.abs(nx)) & (np.abs(nx) < 0.97) & trama
    rgb[barba] = rgb[barba] * 0.72

    # Bandana: la franja se arquea con la cabeza. Bandera 1-2-1: rojo, amarillo (doble), rojo.
    arriba = 5.0 + 0.030 * (x - fx) ** 2
    alto = 9.0
    t = (y - arriba) / alto
    banda = (t >= 0) & (t < 1) & (np.abs(x - cx) < 10.2 * np.clip(1 - np.abs((y - 15.5) / 15) ** 4, 0, 1))
    tono = np.clip((0.95 - 0.75 * ((x - cx + 3) / 12) ** 2) * 3, 0, 2.99).astype(int)
    if k > 2:  # pliegues solo en el retrato grande
        pliegue = np.sin((x - fx) * 1.6 + y * 0.5) > 0.82
        tono = np.clip(tono - pliegue.astype(int), 0, 2)
    amarilla = (t >= 0.25) & (t < 0.75)
    rgb[banda] = ROJO[tono][banda]
    rgb[banda & amarilla] = AMAR[tono][banda & amarilla]
    alfa |= banda

    # Pelo por encima de la bandana, con mechones.
    mechon = 2.3 + 0.9 * np.sin(x * 1.9) + 0.03 * (x - cx) ** 2
    pelo = (y < arriba + 0.2) & (y > mechon) & (np.abs(x - cx) < 9.3)
    rgb[pelo] = PELO
    rgb[pelo & (np.sin(x * 3.1 + y) > 0.5)] = PELO * 1.5
    alfa |= pelo
    calva = cabeza & (y < arriba) & ~pelo  # sin piel asomando entre los mechones
    alfa[calva] = False
    # Patillas bajo la bandana.
    pat = cabeza & (np.abs(nx) > 0.84) & (y >= arriba + alto) & (y < 19.5)
    rgb[pat] = PELO

    # Nudo y puntas de la bandana, al lado contrario de donde mira.
    lado = -1 if giro > 0 else 1
    nudo_x, nudo_y = cx + lado * 9.8, 10.0
    if True:
        nudo = ((x - nudo_x) / 1.5) ** 2 + ((y - nudo_y) / 1.7) ** 2 < 1
        for j, (dx, r) in enumerate(((2.1, 0), (0.7, 1))):
            bx = nudo_x + lado * dx
            d = (y - nudo_y)
            punta = (d > 0) & (d < 8.5 - j * 1.6) & (np.abs(x - (bx + lado * d * 0.16)) < 0.95 + 0.04 * d)
            rgb[punta] = (ROJO[1] if j == 0 else AMAR[1])
            alfa |= punta
        rgb[nudo] = ROJO[0]
        alfa |= nudo

    # Ojos y cejas.
    ojo_y = 16.9
    for lado_o in (-1, 1):
        ex = fx + lado_o * 4.1
        rx, ry = 2.3, 1.45
        if gesto == 'ay':
            ry = 2.1
        if gesto == 'mueca':
            ry = 1.0
        hinchado = dolor >= 3 and lado_o == 1
        if hinchado:
            ry *= 0.45
            mora = ((x - ex) / 3.4) ** 2 + ((y - ojo_y) / 2.8) ** 2 < 1
            rgb[mora & cabeza] = rgb[mora & cabeza] * np.array((0.82, 0.58, 0.72))
        ojo = ((x - ex) / rx) ** 2 + ((y - ojo_y) / ry) ** 2 < 1
        if gesto == 'muerto':
            d1 = np.abs((x - ex) - (y - ojo_y)) < 0.62
            d2 = np.abs((x - ex) + (y - ojo_y)) < 0.62
            aspa = (d1 | d2) & (np.abs(x - ex) < 1.9) & (np.abs(y - ojo_y) < 1.9)
            rgb[aspa] = OSCURO
        else:
            rgb[ojo] = BLANCO * (0.85 if dolor >= 2 else 1)
            px = ex + mira * 1.1
            r_p = 0.95 if k == 1 else 1.0
            pupila = ojo & (((x - px) / r_p) ** 2 + ((y - ojo_y) / (r_p * 1.1)) ** 2 < 1)
            if gesto == 'dios':
                rgb[ojo] = AMAR[2]
                rgb[pupila] = (255, 255, 200)
            else:
                rgb[pupila] = OSCURO
            parpado = ((x - ex) / (rx + 0.5)) ** 2 + ((y - ojo_y + 0.9) / (ry + 0.5)) ** 2 < 1
            rgb[parpado & ~ojo & cabeza & (y > arriba + alto) & (y < ojo_y)] *= 0.72
        # Ceja: inclinación según el gesto (positivo = baja hacia la nariz).
        incl = {'furia': 0.75, 'malo': 0.55, 'ay': -0.35, 'mueca': 0.35, 'decidido': 0.7}.get(gesto, 0.12)
        cej_y = ojo_y - 2.5 - (0.5 if gesto == 'ay' else 0)
        linea = cej_y + incl * (-(x - ex) * lado_o) * 0.6
        ceja = (np.abs(x - ex) < 2.9) & (np.abs(y - linea) < 0.72) & cabeza & (y > arriba + alto - 1)
        if gesto != 'muerto':
            rgb[ceja] = PELO

    # Nariz.
    nariz = (np.abs(x - (fx + 0.9)) < 0.55) & (y > 17.5) & (y < 21.6) & cabeza
    rgb[nariz] = rgb[nariz] * 0.74
    base_n = (np.abs(x - fx) < 1.8) & (np.abs(y - 21.9) < 0.55) & cabeza
    rgb[base_n] = rgb[base_n] * 0.66

    # Boca.
    my = 25.0
    if gesto in ('normal', 'decidido'):
        if dolor >= 4:
            boca = ((x - fx) / 2.4) ** 2 + ((y - my) / 1.5) ** 2 < 1
            rgb[boca] = OSCURO
        else:
            curva = my + 0.5 + 0.03 * dolor * (x - fx) ** 2
            boca = (np.abs(x - fx) < 3.2) & (np.abs(y - curva) < 0.48)
            rgb[boca] = OSCURO
    elif gesto == 'ay':
        boca = ((x - fx) / 3.2) ** 2 + ((y - my) / 2.9) ** 2 < 1
        rgb[boca] = (70, 8, 8)
        rgb[boca & (y < my - 1.6)] = DIENTE
    elif gesto == 'mueca':
        boca = (np.abs(x - fx) < 3.4) & (np.abs(y - my) < 1.1)
        rgb[boca] = DIENTE
        rgb[boca & ((np.floor((x - fx) * max(1, 1)) % 2) == 0)] = DIENTE * 0.72
    elif gesto == 'malo':
        curva = my - 0.6 - 0.09 * (x - fx) ** 2 + 0.6
        boca = (np.abs(x - fx) < 4.5) & (np.abs(y - curva) < 1.15)
        rgb[boca] = DIENTE
        borde = (np.abs(x - fx) < 4.9) & (np.abs(y - curva) < 1.75) & ~boca
        rgb[borde] = OSCURO
    elif gesto == 'furia':
        boca = (np.abs(x - fx) < 4.2) & (np.abs(y - my) < 1.7)
        rgb[boca] = DIENTE
        rgb[boca & (np.abs(y - my) < 0.32)] = OSCURO
        rgb[boca & (np.floor(x - fx) % 2 == 0)] *= 0.72
        borde = (np.abs(x - fx) < 4.8) & (np.abs(y - my) < 2.3) & ~boca
        rgb[borde] = OSCURO
    elif gesto == 'dios':
        boca = (np.abs(x - fx) < 3.2) & (np.abs(y - (my - 0.09 * (x - fx) ** 2 + 0.5)) < 0.6)
        rgb[boca] = OSCURO
    elif gesto == 'muerto':
        boca = ((x - fx) / 3.0) ** 2 + ((y - (my + 0.5)) / 2.3) ** 2 < 1
        rgb[boca] = (50, 6, 6)

    # Sangre según las heridas (y mucha si está muerto).
    n = 3 * dolor if gesto != 'muerto' else len(HERIDAS)
    for (hx, hy, r) in HERIDAS[:n]:
        bx = hx + giro * 0.7
        blob = (((x - bx) / r) ** 2 + ((y - hy) / r) ** 2 < 1) | ((np.abs(x - bx) < r * 0.4) & (y > hy) & (y < hy + r * 2.4))
        blob &= cabeza & ~banda
        rgb[blob] = SANGRE

    # Contorno oscuro de 1 px (de barra).
    a = alfa.copy()
    paso = max(1, k // 2)
    borde = np.zeros_like(a)
    for dy, dx in ((paso, 0), (-paso, 0), (0, paso), (0, -paso)):
        borde |= np.roll(np.roll(a, dy, 0), dx, 1) & ~a
    borde[0, :] = borde[-1, :] = False
    borde[:, 0] = borde[:, -1] = False
    # Solo oscurece por dentro, para no salirse del marco.
    interior = a & (~np.roll(a, paso, 0) | ~np.roll(a, -paso, 0) | ~np.roll(a, paso, 1) | ~np.roll(a, -paso, 1))
    rgb[interior] = OSCURO

    out = np.zeros((H * k, W * k, 4), np.uint8)
    out[..., :3] = np.clip(rgb, 0, 255)
    out[..., 3] = alfa * 255
    return out


# (lump, kwargs) por nivel de heridas. STF{ST,TR,TL,OUCH,EVL,KILL}.
GESTOS = [('ST{}0', dict(mira=-1, giro=-1)), ('ST{}1', dict()), ('ST{}2', dict(mira=1, giro=1)),
          ('TR{}0', dict(mira=1, giro=3, gesto='mueca')), ('TL{}0', dict(mira=-1, giro=-3, gesto='mueca')),
          ('OUCH{}', dict(gesto='ay')), ('EVL{}', dict(gesto='malo')), ('KILL{}', dict(gesto='furia'))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--salida', required=True)
    a = ap.parse_args()
    os.makedirs(a.salida, exist_ok=True)
    off = {}
    for d in range(5):
        for plantilla, kw in GESTOS:
            n = 'STF' + plantilla.format(d)
            Image.fromarray(cara(1, dolor=d, **kw), 'RGBA').save(os.path.join(a.salida, n + '.png'))
            off[n] = [-4, -1]
    Image.fromarray(cara(1, gesto='dios'), 'RGBA').save(os.path.join(a.salida, 'STFGOD0.png'))
    Image.fromarray(cara(1, gesto='muerto', dolor=4), 'RGBA').save(os.path.join(a.salida, 'STFDEAD0.png'))
    off['STFGOD0'] = off['STFDEAD0'] = [-4, -1]
    json.dump(off, open(os.path.join(a.salida, 'offsets_cara.json'), 'w'), indent=0, sort_keys=True)
    print(len(off), 'caras')


if __name__ == '__main__':
    main()
