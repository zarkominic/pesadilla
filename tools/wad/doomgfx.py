"""doomgfx.py — leer/escribir WADs y convertir imágenes al formato «patch» de Doom.

Sin dependencias salvo Pillow (venv: ~/.venvs/pesadilla, ver tools/wad/README.md).

- Un WAD es: cabecera (IWAD/PWAD, nº de lumps, desplazamiento del directorio),
  los datos y un directorio de 16 bytes por lump (desplazamiento, tamaño, nombre[8]).
- Un patch (sprite, arma, textura) es: ancho, alto, desplazamiento izquierdo y
  superior (int16), un puntero por columna (uint32) y, por columna, «posts» de
  píxeles opacos: [fila inicial, longitud, relleno, píxeles…, relleno], acabando en 0xFF.
  Lo transparente simplemente no se dibuja: no hace falta un color clave.
"""
import struct
from PIL import Image


def read_wad(path):
    """Devuelve (tipo, [(nombre, bytes), ...]) en el orden del directorio."""
    data = open(path, 'rb').read()
    ident, n, diroff = struct.unpack('<4sii', data[:12])
    lumps = []
    for i in range(n):
        off, size, name = struct.unpack('<ii8s', data[diroff + 16 * i: diroff + 16 * i + 16])
        lumps.append((name.rstrip(b'\0').decode('ascii'), data[off:off + size]))
    return ident.decode('ascii'), lumps


def write_wad(path, lumps, ident='PWAD'):
    body = bytearray()
    directory = bytearray()
    pos = 12
    for name, data in lumps:
        directory += struct.pack('<ii8s', pos if data else 0, len(data), name.upper().encode('ascii'))
        body += data
        pos += len(data)
    with open(path, 'wb') as f:
        f.write(struct.pack('<4sii', ident.encode('ascii'), len(lumps), 12 + len(body)))
        f.write(body)
        f.write(directory)


def read_palette(wad_path):
    """Primera paleta de PLAYPAL como lista de 256 tuplas (r, g, b)."""
    _, lumps = read_wad(wad_path)
    playpal = next(d for n, d in lumps if n == 'PLAYPAL')
    return [tuple(playpal[i * 3:i * 3 + 3]) for i in range(256)]


def decode_patch(data, palette):
    """Patch de Doom → (imagen RGBA, (izq, sup))."""
    w, h, left, top = struct.unpack('<hhhh', data[:8])
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    px = img.load()
    for x in range(w):
        p = struct.unpack('<I', data[8 + 4 * x: 12 + 4 * x])[0]
        while data[p] != 0xFF:
            row, length = data[p], data[p + 1]
            for i in range(length):
                px[x, row + i] = palette[data[p + 3 + i]] + (255,)
            p += length + 4
    return img, (left, top)


class PaletteMapper:
    """Color RGB → índice de la paleta más cercano (distancia ponderada), con caché."""

    def __init__(self, palette, exclude=()):
        self.palette = [(i, c) for i, c in enumerate(palette) if i not in exclude]
        self.cache = {}

    def index(self, rgb):
        hit = self.cache.get(rgb)
        if hit is None:
            r, g, b = rgb
            best, bestd = 0, None
            for i, (pr, pg, pb) in self.palette:
                rm = (r + pr) / 2
                d = (2 + rm / 256) * (r - pr) ** 2 + 4 * (g - pg) ** 2 + (2 + (255 - rm) / 256) * (b - pb) ** 2
                if bestd is None or d < bestd:
                    best, bestd = i, d
            hit = self.cache[rgb] = best
        return hit


def encode_patch(img, offsets, mapper, alpha_threshold=128):
    """Imagen (RGBA) → bytes de un patch de Doom. offsets = (izq, sup)."""
    img = img.convert('RGBA')
    w, h = img.size
    if h > 254:
        raise ValueError('patch de más de 254 píxeles de alto: no soportado')
    px = img.load()
    columns = []
    for x in range(w):
        col = bytearray()
        y = 0
        while y < h:
            if px[x, y][3] < alpha_threshold:
                y += 1
                continue
            start = y
            run = []
            while y < h and px[x, y][3] >= alpha_threshold and len(run) < 254:
                run.append(mapper.index(px[x, y][:3]))
                y += 1
            col += bytes([start, len(run), run[0]]) + bytes(run) + bytes([run[-1]])
        col += b'\xff'
        columns.append(bytes(col))
    header = struct.pack('<hhhh', w, h, offsets[0], offsets[1])
    pos = 8 + 4 * w
    pointers = bytearray()
    for col in columns:
        pointers += struct.pack('<I', pos)
        pos += len(col)
    return header + pointers + b''.join(columns)
