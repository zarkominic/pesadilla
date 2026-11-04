#!/usr/bin/env python3
"""generar.py — paredes, suelos y cielos del pueblo de pesadilla, por código (sin IA).

Cada familia del catálogo (arte/texturas/catalogo.json) tiene un material propio. Los materiales repiten
cada 64 px, así que dos parches contiguos casan. De cada parche original (Freedoom, BSD) se conserva
la forma: su luminosidad modula el material, sus huecos se respetan y sus colores vivos (luces de interruptor
o de llave) se mantienen. Por eso puertas, interruptores y animaciones se siguen reconociendo y funcionando.

No se redibujan: cascadas y limo (animados, ya legibles), colores de llave y marcadores vacíos («otro»).
Se regenera con tools/arte/construir.sh.
Uso: generar.py --salida arte/texturas [--iwad wads/freedoom-0.13.0/freedoom1.wad]
"""
import argparse
import colorsys
import json
import os
import sys
import zlib

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'wad'))
from doomgfx import decode_patch, read_palette, read_wad  # noqa: E402

T = 64


def ruido(semilla, escala=8, n=T, potencia=1.4):
    """Ruido periódico en [0,1]: ruido blanco filtrado en frecuencia."""
    rng = np.random.default_rng(zlib.crc32(semilla.encode()))
    f = np.fft.fft2(rng.standard_normal((n, n)))
    fy, fx = np.fft.fftfreq(n), np.fft.fftfreq(n)
    r = np.hypot(*np.meshgrid(fx, fy, indexing='xy'))
    r[0, 0] = 1
    a = 1 / (r * n / max(1, n / escala) + 1) ** potencia
    a[0, 0] = 0
    z = np.real(np.fft.ifft2(f * a))
    z -= z.min()
    return z / max(z.max(), 1e-6)


def rampa(v, *colores):
    c = np.array(colores, float)
    x = np.clip(v, 0, 1) * (len(c) - 1)
    i = np.minimum(x.astype(int), len(c) - 2)
    return c[i] + (c[i + 1] - c[i]) * (x - i)[..., None]


def hiladas(alto, largo, s, n=T):
    """Aparejo: (junta bool, id de pieza, v en pieza) con filas alternas desplazadas."""
    ys, xs = np.mgrid[0:n, 0:n]
    fila = ys // alto
    x = (xs + (fila % 2) * (largo // 2)) % n
    pieza = x // largo + fila * 97
    junta = (ys % alto == alto - 1) | (x % largo == largo - 1)
    return junta, pieza, ys % alto / alto


def por_pieza(pieza, semilla):
    rng = np.random.default_rng(zlib.crc32(semilla.encode()))
    t = rng.random(int(pieza.max()) + 2)
    return t[pieza]


def m_cal():
    # Cal vieja: manchas grandes y suaves, sin motas, y no blanca del todo (deslumbra en pantalla).
    n = ruido('cal', 60, potencia=2.2) * .75 + ruido('calf', 12) * .25
    c = rampa(n, (112, 98, 78), (146, 130, 106), (172, 158, 132), (190, 178, 152))
    grieta = np.abs(ruido('grieta', 70, potencia=2.4) - .5) < .006
    c[grieta] *= .55
    return c


def m_ladrillo():
    j, p, v = hiladas(8, 16, 'l')
    tono = por_pieza(p, 'ladr') * .55 + ruido('lad', 16) * .45
    c = rampa(tono, (84, 36, 22), (124, 54, 32), (160, 76, 46), (186, 104, 68))
    c[v < .13] *= 1.14
    c[j] = (58, 50, 44)
    return c


def m_piedra():
    j, p, v = hiladas(16, 32, 'p')
    tono = por_pieza(p, 'pied') * .4 + ruido('pie', 14) * .6
    c = rampa(tono, (58, 54, 50), (92, 86, 78), (126, 118, 104), (152, 144, 126))
    c[v < .08] *= 1.2
    c[j] = (26, 24, 22)
    return c


def m_roca():
    n = ruido('roca', 3, potencia=1.2) * .6 + ruido('rocaf', 18) * .4
    return rampa(n, (32, 24, 18), (66, 50, 36), (104, 80, 56), (138, 110, 80))


def m_hierro():
    n = ruido('hie', 10) * .6 + ruido('hie2', 3) * .4
    c = rampa(n, (30, 28, 28), (58, 54, 52), (84, 78, 72), (108, 100, 90))
    oxido = ruido('oxi', 5) > .64
    c[oxido] = c[oxido] * .55 + np.array((104, 52, 24)) * .45
    ys, xs = np.mgrid[0:T, 0:T]
    c[(xs % 32 - 4) ** 2 + (ys % 32 - 4) ** 2 <= 2] = (136, 126, 112)  # remaches
    return c


def m_madera(ancho=16, base=((44, 26, 14), (78, 48, 24), (112, 72, 38), (140, 96, 54))):
    ys, xs = np.mgrid[0:T, 0:T]
    tabla = xs // ancho
    veta = ruido('veta', 22)[:, ::-1]
    veta = np.roll(veta, 7, 0) * .5 + np.take_along_axis(ruido('vet2', 28), (ys // 6 * 6) % T, 0) * .5
    tono = por_pieza(tabla, 'tab') * .35 + veta * .65
    c = rampa(tono, *base)
    c[xs % ancho == ancho - 1] = (20, 12, 6)
    return c


def m_nogal():
    return m_madera(32, ((22, 12, 8), (42, 24, 14), (66, 40, 22), (92, 58, 32)))


M = {}


def material(nombre):
    if nombre not in M:
        M[nombre] = {'cal': m_cal, 'ladrillo': m_ladrillo, 'piedra': m_piedra, 'roca': m_roca, 'hierro': m_hierro,
                     'madera': m_madera, 'nogal': m_nogal}[nombre]()
    return M[nombre]


# familia → (material, fuerza de la forma original 0..1)
MODULADAS = {'encalado': ('cal', .30), 'ladrillo': ('ladrillo', .22), 'piedra': ('piedra', .45), 'roca': ('roca', .40),
             'metal': ('hierro', .85), 'tecno': ('nogal', 1.0), 'madera': ('madera', .40), 'cajas': ('madera', .75),
             'puerta': ('nogal', .85), 'marco': ('hierro', .9), 'interruptor': ('hierro', 1.0)}
# familia → colores por luminosidad.
RAMPAS = {'infierno': ((12, 4, 4), (58, 14, 10), (118, 72, 40), (186, 158, 112), (232, 216, 176)),  # osario
          'reja': ((6, 6, 6), (24, 22, 22), (52, 48, 46), (92, 86, 80)),
          'tuberia': ((22, 12, 8), (72, 38, 20), (132, 76, 40), (190, 124, 72), (232, 184, 132)),  # cobre
          'luz': ((30, 16, 6), (108, 54, 12), (206, 128, 32), (252, 200, 92), (255, 244, 188)),  # candil
          'mural': ((16, 10, 8), (66, 42, 26), (128, 92, 60), (188, 152, 108), (226, 204, 166))}  # pintura vieja
# Colores vivos que se conservan (luces de interruptor, llaves).
CONSERVA_VIVOS = {'interruptor', 'puerta', 'marco', 'metal', 'cajas'}
NO_TOCAR = {'cascada', 'limo', 'llave_color', 'otro', 'cielo', 'salida'}

# Letra 4x7 para los carteles: SALIDA cabe en los 32 px de ancho del original.
LETRAS = {'S': '0111 1000 1000 0110 0001 0001 1110', 'A': '0110 1001 1001 1111 1001 1001 1001',
          'L': '1000 1000 1000 1000 1000 1000 1111', 'I': '111 010 010 010 010 010 111',
          'D': '1110 1001 1001 1001 1001 1001 1110'}


def cartel(w, h, tinta):
    rgb = np.zeros((h, w, 3)) + (24, 14, 10)
    t = 'SALIDA'
    total = sum(len(LETRAS[ch].split()[0]) + 1 for ch in t) - 1
    x = max(0, (w - total) // 2)
    y = max(0, (h - 7) // 2)
    for ch in t:
        for j, fila in enumerate(LETRAS[ch].split()):
            for i, b in enumerate(fila):
                if b == '1' and x + i < w and y + j < h:
                    rgb[y + j, x + i] = tinta
        x += len(LETRAS[ch].split()[0]) + 1
    return rgb


def luminosidad(rgb):
    return (rgb[..., 0] * .3 + rgb[..., 1] * .59 + rgb[..., 2] * .11) / 255


def saturacion(rgb):
    mx, mn = rgb.max(-1), rgb.min(-1)
    return (mx - mn) / np.maximum(mx, 1)


def parche(rgba, info, ox, oy, lf, nombre):
    rgb = rgba[..., :3].astype(float)
    h, w = rgb.shape[:2]
    lum = luminosidad(rgb)
    f = info['familia']
    if f in RAMPAS:
        # Algo de textura para que no parezca un simple viraje de color.
        n = ruido('r' + f, 12)
        ys, xs = np.mgrid[0:h, 0:w]
        v = np.clip(lum ** .85 * 1.15 + (n[(ys + oy) % T, (xs + ox) % T] - .5) * .1, 0, 1)
        out = rampa(v, *RAMPAS[f])
    else:
        mat, fuerza = MODULADAS[f]
        m = material(mat)
        ys, xs = np.mgrid[0:h, 0:w]
        base = m[(ys + oy) % T, (xs + ox) % T]
        g = np.clip(1 + fuerza * (lum - lf) * 2.6, .18, 1.9)[..., None]
        out = base * g
        if f == 'tecno':  # las luces de las máquinas pasan a ser latón y candil
            vivo = (saturacion(rgb) > .45) & (lum > .28) | (lum > .72)
            out[vivo] = rampa(np.clip(lum[vivo] * 1.2, 0, 1), (120, 72, 18), (206, 150, 52), (252, 220, 130))
        if f in CONSERVA_VIVOS:
            vivo = (saturacion(rgb) > .55) & (rgb.max(-1) > 90)
            out[vivo] = rgb[vivo]
    return np.dstack((np.clip(out, 0, 255), rgba[..., 3]))


# --- Suelos -------------------------------------------------------------------------------------------------

def s_baldosa(nombre):
    """Baldosa hidráulica: la variante depende del nombre."""
    k = zlib.crc32(nombre.encode())
    pares = [((150, 136, 110), (56, 40, 30), (132, 44, 30)), ((176, 164, 140), (40, 44, 48), (120, 96, 40)),
             ((122, 56, 36), (168, 150, 120), (44, 34, 28)), ((96, 104, 92), (168, 160, 136), (64, 42, 28))]
    a, b, c = (np.array(x, float) for x in pares[k % 4])
    ys, xs = np.mgrid[0:T, 0:T]
    u, v = (xs % 16) - 7.5, (ys % 16) - 7.5
    celda = ((xs // 16 + ys // 16) % 2 == 0)
    out = np.where(celda[..., None], a, b)
    if k & 16:
        rombo = np.abs(u) + np.abs(v) < 5
        out[rombo] = c
    else:
        out[(u ** 2 + v ** 2 < 16) & celda] = c
    out = out * .62 + out.mean((0, 1)) * .38  # poco contraste, para no tapar a los enemigos
    out *= (.72 + .3 * ruido('bal', 10))[..., None]
    out[(xs % 16 == 15) | (ys % 16 == 15)] = (28, 24, 20)
    return out


def s_adoquin(nombre):
    j, p, v = hiladas(10, 16, 'a')
    tono = por_pieza(p, nombre) * .5 + ruido('ado', 10) * .5
    c = rampa(tono, (52, 48, 44), (88, 80, 72), (122, 112, 98), (148, 138, 120))
    c[j] = (20, 16, 12)
    return c


def s_tierra(nombre):
    n = ruido(nombre, 6) * .5 + ruido('tierra', 24) * .5
    return rampa(n, (36, 24, 14), (70, 48, 28), (100, 72, 44), (126, 96, 62))


def s_hierba(nombre):
    n = ruido(nombre, 28) * .6 + ruido('hb', 5) * .4
    return rampa(n, (20, 28, 10), (40, 56, 18), (66, 82, 28), (92, 104, 40))


def s_vigas(nombre):
    c = m_madera(32, ((16, 10, 6), (40, 24, 14), (66, 42, 24), (88, 58, 34)))
    return c.transpose(1, 0, 2)


def s_tapa(nombre):
    c = m_madera(16)
    ys, xs = np.mgrid[0:T, 0:T]
    marco = (xs < 4) | (xs > 59) | (ys < 4) | (ys > 59)
    c[marco] *= .62
    return c


def s_portal(nombre, fase):
    """Teletransporte: remolino de fuego fatuo (sin símbolos)."""
    ys, xs = np.mgrid[0:T, 0:T]
    u, v = xs - 31.5, ys - 31.5
    r, a = np.hypot(u, v), np.arctan2(v, u)
    onda = .5 + .5 * np.sin(a * 3 + r * .45 - fase * np.pi / 2)
    c = rampa(np.clip(onda * (1 - r / 46), 0, 1), (8, 10, 30), (24, 44, 110), (70, 130, 210), (190, 230, 255))
    c[r > 31] = (20, 18, 22)
    c[(r > 29) & (r <= 31)] = (120, 110, 96)
    return c


def s_liquido(semilla, fase, nfases, colores):
    """Animación en bucle: dos capas de ruido periódico que se cruzan."""
    # Manchas grandes y suaves: si no, a distancia el líquido parece ruido de televisor.
    a = ruido(semilla + 'a', 60, potencia=2.2)
    b = ruido(semilla + 'b', 45, potencia=2.2)
    d = fase * T // nfases
    n = np.roll(a, d, 1) * .5 + np.roll(b, -d, 0) * .5
    return rampa(np.clip((n - .22) / .56, 0, 1), *colores)


LIQUIDOS = {'liquido_agua': ((6, 16, 22), (14, 40, 46), (30, 74, 70), (78, 128, 112)),
            'liquido_lava': ((70, 6, 0), (168, 28, 0), (240, 104, 0), (255, 216, 60)),
            'liquido_sangre': ((40, 0, 0), (92, 0, 0), (150, 6, 6), (210, 30, 24)),
            'liquido_veneno': ((10, 44, 4), (32, 104, 8), (92, 180, 16), (196, 240, 70))}


def suelo(nombre, info, orig, anim):
    f = info['familia']
    lum = luminosidad(orig)
    grupo = anim.get(nombre)
    if f in LIQUIDOS:
        if grupo:
            return s_liquido(f, grupo.index(nombre), len(grupo), LIQUIDOS[f])
        return s_liquido(f + nombre, 0, 1, LIQUIDOS[f])
    if grupo and f != 'teletransporte':  # animados que no son líquidos: viraje a oscuro, conservan el movimiento
        return rampa(lum, (20, 10, 6), (84, 46, 20), (170, 110, 50), (240, 200, 110))
    if f == 'teletransporte':
        return s_portal(nombre, int(nombre[-1]))
    if f == 'techo_luz':
        return rampa(np.clip(lum ** 1.2 * 1.2, 0, 1), (28, 18, 10), (78, 50, 24), (176, 110, 34), (252, 204, 100), (255, 244, 196))
    if f == 'suelo_metal':
        return material('hierro') * np.clip(1 + .85 * (lum - .42) * 2.6, .25, 1.8)[..., None]
    if f == 'suelo_baldosa':
        return s_baldosa(nombre)
    if f in ('suelo_piedra', 'escalon'):
        return s_adoquin(nombre) * np.clip(1 + .3 * (lum - .4) * 2.6, .4, 1.5)[..., None]
    if f in ('suelo_tierra', 'roca'):
        return s_tierra(nombre) * np.clip(1 + .4 * (lum - .4) * 2.6, .4, 1.5)[..., None]
    if f == 'suelo_madera':
        return material('madera')
    if f == 'hierba':
        return s_hierba(nombre)
    if f == 'techo':
        return s_vigas(nombre)
    if f == 'cajas_tapa':
        return s_tapa(nombre)
    return None


# --- Cielos: noche roja con sierras (periódico en 256) ---------------------------------------------------------

def cielo(nombre):
    w, h = 256, 128
    k = zlib.crc32(nombre.encode())
    tono = [((6, 4, 10), (34, 8, 12), (92, 16, 14)), ((4, 6, 16), (16, 18, 44), (70, 30, 50)),
            ((10, 6, 4), (52, 24, 10), (130, 60, 16)), ((4, 4, 6), (24, 16, 26), (72, 22, 30))][k % 4]
    ys, xs = np.mgrid[0:h, 0:w]
    n = ruido(nombre, 6, n=256)[:h, :]
    v = ys / h * .85 + (n - .5) * .35
    c = rampa(v, *tono)
    rng = np.random.default_rng(k)
    for _ in range(50):
        x, y = rng.integers(0, w), rng.integers(0, 70)
        c[y, x] = (200, 190, 170)
    for ampl, base, col, sem in ((14, 92, (26, 12, 14), 1), (10, 106, (10, 6, 8), 2)):
        r = np.random.default_rng(k + sem)
        fases = r.random(5) * 6.283
        x = np.arange(w)
        perfil = sum(np.sin(x * 2 * np.pi * m / w + fases[m - 1]) * ampl / m for m in range(1, 6)) + base
        c[ys > perfil[xs]] = col
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--salida', required=True)
    ap.add_argument('--iwad', default='wads/freedoom-0.13.0/freedoom1.wad')
    ap.add_argument('--catalogo', default='arte/texturas/catalogo.json')
    a = ap.parse_args()
    cat = json.load(open(a.catalogo))
    _, lumps = read_wad(a.iwad)
    d = dict(lumps)
    pal = read_palette(a.iwad)
    dp, ds = os.path.join(a.salida, 'parches'), os.path.join(a.salida, 'suelos')
    os.makedirs(dp, exist_ok=True)
    os.makedirs(ds, exist_ok=True)

    originales = {}
    for n, p in cat['parches'].items():
        if n in d:
            originales[n] = np.array(decode_patch(d[n], pal)[0])
    # Luminosidad media de cada familia: referencia común, para que los parches contiguos casen.
    lf = {}
    for n, r in originales.items():
        f = cat['parches'][n]['familia']
        lf.setdefault(f, []).append(luminosidad(r[..., :3].astype(float))[r[..., 3] > 0].mean() if (r[..., 3] > 0).any() else .4)
    lf = {f: float(np.median(v)) for f, v in lf.items()}

    # Posición del parche en su textura más usada, para que el material siga en las contiguas.
    pos = {}
    for t, info in sorted(cat['texturas'].items(), key=lambda kv: kv[1]['mapas']):
        for pn, x, y in info['colocacion']:
            pos[pn] = (x, y)

    hechos = 0
    for n, r in sorted(originales.items()):
        info = cat['parches'][n]
        f = info['familia']
        if f == 'cielo':
            out = np.dstack((cielo(n), r[..., 3]))
        elif f == 'salida':
            h, w = r.shape[:2]
            if w >= 32 and h <= 16:
                tinta = (96, 220, 64) if 'GRN' in n else (240, 40, 24)
                out = np.dstack((cartel(w, h, tinta), r[..., 3]))
            else:
                out = parche(r, dict(info, familia='puerta'), *pos.get(n, (0, 0)), lf['puerta'], n)
        elif f in NO_TOCAR:
            continue
        else:
            out = parche(r, info, *pos.get(n, (0, 0)), lf[f], n)
        out = out.astype(np.uint8)
        out[..., :3] = out[..., :3] // 4 * 4  # menos colores: la conversión a paleta va mucho más rápida
        Image.fromarray(out, 'RGBA').save(os.path.join(dp, n + '.png'))
        hechos += 1

    # Suelos: para cada animación se necesitan todos sus fotogramas.
    anim = {}
    for g in cat['animaciones']['suelos'].values():
        for x in g:
            anim[x] = g
    pl = np.array(pal, np.uint8)
    ns = 0
    for n, info in sorted(cat['suelos'].items()):
        if n not in d or len(d[n]) != 4096:
            continue
        orig = pl[np.frombuffer(d[n], np.uint8)].reshape(64, 64, 3).astype(float)
        s = suelo(n, info, orig, anim)
        if s is None:
            continue
        Image.fromarray(np.clip(s, 0, 255).astype(np.uint8) // 4 * 4, 'RGB').save(os.path.join(ds, n + '.png'))
        ns += 1
    print(f'{hechos} parches, {ns} suelos')


if __name__ == '__main__':
    main()
