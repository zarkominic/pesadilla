#!/usr/bin/env python3
"""catalogo.py — catálogo de materiales de los niveles (texturas, parches y suelos de Freedoom 1).

Se ejecuta A MANO (no forma parte de construir.sh: no escribe arte):

    ~/.venvs/pesadilla/bin/python tools/texturas/catalogo.py [--iwad wads/freedoom-0.13.0/freedoom1.wad]
        [--json arte/texturas/catalogo.json] [--hojas <carpeta para hojas de contactos>]

Lee el IWAD y escribe arte/texturas/catalogo.json:

- "texturas": {NOMBRE: {familia, ancho, alto, parches, colocacion, opaca, mapas, mapas_directos, lados,
               anim, origen, color_medio, [pareja, pulsado, acciona_en_freedoom1, llave, salida, tira,
               funciones]}}
    Todas las texturas de TEXTURE1 (801) y también las de TEXTURE2 (162): en Freedoom 1, como en el DOOM
    registrado, TEXTURE2 guarda las texturas de los episodios 2-4 (ASHWALL, CRATE1, MARBLE1, SKIN*…) y los
    mapas E2-E4 usan 140 de ellas. «origen» dice de qué lump viene cada una.
    · mapas = nº de mapas de E1-E4 donde se VE (puesta en un lado, o como fotograma de su animación, o
      como la otra cara de su interruptor, o como cielo del episodio); mapas_directos = puesta en un lado.
    · colocacion = [[parche, x, y], ...] tal como la compone TEXTURE1/2.
    · Interruptores: pareja (SW1↔SW2), pulsado (True en la SW2), acciona_en_freedoom1 (el motor solo conmuta
      las de su lista de episodio ≤ 2; las demás parejas por nombre salen con False). Llave: azul/rojo/
      amarillo. Salida: True. tira: True en las tiras de muestra de 512 px que ningún mapa usa.
    · funciones = {puerta, llave_azul/roja/amarilla, accionable, salida: nº de lados} vistos en la cara
      delantera de líneas con ese especial (p. ej. A-BROWN4 y WOODGARG hacen de puerta en los mapas).
- "parches": {NOMBRE: {familia, ancho, alto, opaco, texturas, color_medio, anim, [pulsado, llave, salida]}}
    para los parches que usan TEXTURE1 y TEXTURE2. La familia del parche es la mayoritaria entre sus texturas
    (por nº de lados en los mapas) y, si empatan, la más específica (ver PRIORIDAD); las tiras de muestra no
    votan. pulsado: True/False si solo lo usan SW2/SW1 (parche de estado del interruptor).
- "suelos": {NOMBRE: {familia, color_medio, anim, mapas, sectores, sectores_suelo, sectores_suelo_daninos,
    danino, peligroso}} para los 240 flats menos F_SKY1. danino = daño por tic si al menos un tercio de los
    sectores donde es SUELO (sumando su grupo animado) hacen daño; peligroso = dañino o líquido de
    veneno/lava/sangre (debe LEERSE como peligroso al redibujarlo).
- "familias_otro": por qué queda cada cosa en «otro» (solo negros/vacíos que no hay que redibujar).
- "animaciones": grupos animados del motor (p_spec.c) con sus fotogramas reales en el orden del WAD.
- "interruptores": parejas SW1/SW2 y si el motor las acciona en Freedoom 1 (p_switch.c, episodios 1-2).
- "familias": recuento por familia.

La familia se decide con reglas por nombre (prefijos de Freedoom/DOOM) y una tabla de EXCEPCIONES
revisada mirando las hojas de contactos (--hojas escribe una hoja por familia, con las texturas YA
compuestas). Determinista: la misma entrada da el mismo JSON byte a byte.
"""
import argparse
import collections
import json
import os
import re
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(RAIZ, 'tools', 'wad'))
from doomgfx import read_palette, read_wad  # noqa: E402

FAMILIAS_PARED = ['piedra', 'ladrillo', 'encalado', 'roca', 'madera', 'cajas', 'puerta', 'marco',
                  'llave_color', 'interruptor', 'salida', 'luz', 'tecno', 'metal', 'tuberia', 'reja', 'limo',
                  'infierno', 'cascada', 'mural', 'cielo', 'otro']
FAMILIAS_SUELO = ['suelo_piedra', 'suelo_baldosa', 'suelo_madera', 'suelo_tierra', 'hierba', 'suelo_metal',
                  'escalon', 'cajas_tapa', 'techo', 'techo_luz', 'liquido_agua', 'liquido_veneno',
                  'liquido_lava', 'liquido_sangre', 'roca', 'teletransporte', 'otro']

# Cuando un parche lo comparten texturas de familias distintas y empatan: gana la primera de esta lista
# (las que tienen una FUNCIÓN para el jugador primero, luego las más específicas, las genéricas al final).
PRIORIDAD = ['salida', 'llave_color', 'interruptor', 'cascada', 'cielo', 'puerta', 'luz', 'reja', 'limo',
             'infierno', 'tecno', 'mural', 'cajas', 'tuberia', 'marco', 'madera', 'ladrillo', 'roca',
             'encalado', 'piedra', 'metal', 'otro']

# ---------------------------------------------------------------------------------------------------
# Animaciones y conmutadores del motor (motor/src/doom/p_spec.c y p_switch.c)
# ---------------------------------------------------------------------------------------------------
ANIM_SUELOS = [('NUKAGE1', 'NUKAGE3'), ('FWATER1', 'FWATER4'), ('SWATER1', 'SWATER4'), ('LAVA1', 'LAVA4'),
               ('BLOOD1', 'BLOOD3'), ('RROCK05', 'RROCK08'), ('SLIME01', 'SLIME04'), ('SLIME05', 'SLIME08'),
               ('SLIME09', 'SLIME12')]
ANIM_PAREDES = [('BLODGR1', 'BLODGR4'), ('SLADRIP1', 'SLADRIP3'), ('BLODRIP1', 'BLODRIP4'),
                ('FIREWALA', 'FIREWALL'), ('GSTFONT1', 'GSTFONT3'), ('FIRELAV3', 'FIRELAVA'),
                ('FIREMAG1', 'FIREMAG3'), ('FIREBLU1', 'FIREBLU2'), ('ROCKRED1', 'ROCKRED3'),
                ('BFALL1', 'BFALL4'), ('SFALL1', 'SFALL4'), ('WFALL1', 'WFALL4'), ('DBRAIN1', 'DBRAIN4')]
# (SW1, SW2, episodio): el motor solo acciona las de episodio <= 2 con un IWAD de DOOM 1 (Freedoom 1).
INTERRUPTORES = [
    ('SW1BRCOM', 'SW2BRCOM', 1), ('SW1BRN1', 'SW2BRN1', 1), ('SW1BRN2', 'SW2BRN2', 1), ('SW1BRNGN', 'SW2BRNGN', 1),
    ('SW1BROWN', 'SW2BROWN', 1), ('SW1COMM', 'SW2COMM', 1), ('SW1COMP', 'SW2COMP', 1), ('SW1DIRT', 'SW2DIRT', 1),
    ('SW1EXIT', 'SW2EXIT', 1), ('SW1GRAY', 'SW2GRAY', 1), ('SW1GRAY1', 'SW2GRAY1', 1), ('SW1METAL', 'SW2METAL', 1),
    ('SW1PIPE', 'SW2PIPE', 1), ('SW1SLAD', 'SW2SLAD', 1), ('SW1STARG', 'SW2STARG', 1), ('SW1STON1', 'SW2STON1', 1),
    ('SW1STON2', 'SW2STON2', 1), ('SW1STONE', 'SW2STONE', 1), ('SW1STRTN', 'SW2STRTN', 1),
    ('SW1BLUE', 'SW2BLUE', 2), ('SW1CMT', 'SW2CMT', 2), ('SW1GARG', 'SW2GARG', 2), ('SW1GSTON', 'SW2GSTON', 2),
    ('SW1HOT', 'SW2HOT', 2), ('SW1LION', 'SW2LION', 2), ('SW1SATYR', 'SW2SATYR', 2), ('SW1SKIN', 'SW2SKIN', 2),
    ('SW1VINE', 'SW2VINE', 2), ('SW1WOOD', 'SW2WOOD', 2),
    ('SW1PANEL', 'SW2PANEL', 3), ('SW1ROCK', 'SW2ROCK', 3), ('SW1MET2', 'SW2MET2', 3), ('SW1WDMET', 'SW2WDMET', 3),
    ('SW1BRIK', 'SW2BRIK', 3), ('SW1MOD1', 'SW2MOD1', 3), ('SW1ZIM', 'SW2ZIM', 3), ('SW1STON6', 'SW2STON6', 3),
    ('SW1TEK', 'SW2TEK', 3), ('SW1MARB', 'SW2MARB', 3), ('SW1SKULL', 'SW2SKULL', 3)]
CIELOS_EPISODIO = {1: 'SKY1', 2: 'SKY2', 3: 'SKY3', 4: 'SKY4'}

# Especiales de línea (linedefs) y de sector que sirven de PRUEBA al clasificar (DOOM 1).
LINEA_SALIDA = {11, 51, 52, 124}               # 11/51 interruptor de salida (normal/secreta), 52/124 cruzar
LINEA_LLAVE = {26: 'azul', 32: 'azul', 99: 'azul', 133: 'azul', 27: 'amarillo', 34: 'amarillo', 136: 'amarillo',
               137: 'amarillo', 28: 'rojo', 33: 'rojo', 134: 'rojo', 135: 'rojo'}
LINEA_PUERTA = {1, 26, 27, 28, 31, 32, 33, 34, 117, 118}   # puertas que se abren al usarlas (lado de delante)
# Especiales que se accionan al USAR la línea (S1/SR: interruptores), en DOOM 1 / Chocolate Doom.
LINEA_INTERRUPTOR = {7, 9, 11, 14, 15, 18, 20, 21, 23, 29, 41, 42, 43, 45, 49, 50, 51, 55, 60, 61, 62, 63, 64,
                     65, 66, 67, 68, 69, 70, 71, 101, 102, 103, 111, 112, 113, 114, 115, 116, 122, 123, 127,
                     131, 132, 133, 134, 135, 136, 137, 138, 139, 140}
SECTOR_DANINO = {4: 20, 5: 10, 7: 5, 11: 20, 16: 20}   # especial de sector → daño por tic de daño

# ---------------------------------------------------------------------------------------------------
# Reglas por nombre (paredes). La primera que encaja manda; EXCEPCIONES_TEXTURAS va antes que todas.
# ---------------------------------------------------------------------------------------------------
REGLAS_TEXTURAS = [
    # Funciones para el jugador
    (r'^SW[12]', 'interruptor'),
    (r'^(EXITSIGN|EXITSGN2|EXITSTON|PNK4EXIT|EXITDOOR)$', 'salida'),
    (r'^(DOOR(BLU|RED|YEL)2?|M_[BRY]DOOR)$', 'llave_color'),
    (r'^(DOOR(STOP|TRAK)|DR(FRONT|SIDE\d|TOPFR|TOPSID))$', 'marco'),
    (r'^(BIGDOOR|BIGDOR|DOOR|SPCDOOR|AQDOOR|ZDOOR|ZELDOOR|ICKDOOR|METALDR|TNTDOOR)', 'puerta'),
    (r'^(P-SKY|T-SKY|SKY)\d', 'cielo'),
    # Tiras de muestra de 512 de ancho que nadie usa (mezclan parches de todo: caras, ordenadores, telarañas…)
    (r'^(T-BLODG|T-SLDRP|T-WFALL|BLOD3$|FALL3$|SLAD([2-9]|1[01])$)', 'mural'),
    # Animadas (los fotogramas los fija ANIM_PAREDES; aquí la familia). DBRAIN en Freedoom es una cortina
    # de fuego, no un cerebro: va con las demás cascadas para animarse con coherencia.
    (r'^(BFALL|SFALL|WFALL|BLODGR|BLODRIP|SLADRIP|GSTFONT|FIRELAV|FIREWAL|FIREMAG|FIREBLU|ROCKRED|DBRAIN)',
     'cascada'),
    (r'^P-FRBLU', 'piedra'),          # pese al nombre: empedrado gris con musgo (sin usar)
    (r'^P-DBRAN', 'roca'),            # pese al nombre: barro oscuro (sin usar)
    # Luz (paneles de luz, focos; P* = colores lisos; EG* = tiras de luz de 8 px)
    (r'^(LITE|AQLITE|BRICKLIT|COMPLIT|P(RED|BLUE|GREEN|ORAN|WHITE)$|EG(GREENI|REDI)$)', 'luz'),
    # Reja / huecos (midtextures con transparencia: rejas, ventanas, alambre, enredaderas colgantes)
    (r'^(MIDBARS|MIDGRATE|MIDBRN|MIDSPACE|MIDSPCSM|MIDVINE|MIDBRONZ|WEB[LR]$|A-GRATE|A-RAIL|A-VINE[12]$|'
     r'CEILVINE|CGRATE|DOBWIRE|DOGRID|DOWINDOW|DOGLPANL|SMGLASS|TYIRON|BRNSMAL|BRNBIG[CLR]$|BRNOPEN)', 'reja'),
    # Limo / veneno (y carteles de veneno)
    (r'^(NUKE|SLADPOIS|BRNPOIS|STONPOIS|CEMPOIS|GRAYPOIS|A-POIS|SLIME3$|GRAY9$)', 'limo'),
    # Infierno (carne, caras, calaveras, grietas de lava)
    (r'^(SKIN|SKSNAKE|SKSPINE|SKULWAL|SP_DUDE|SP_FACE|SP_HOT|ZZZFACE|MARBFAC|CRACKLE|SLOPPY|REDWALL|'
     r'GSTGARG|GSTLION|GSTSATYR|STONGARG|WOODSKUL|SLADSKUL|MARBLOD|A-ASKIN|SK_(LEFT|RIGHT)$|REDOPEN$|'
     r'DORED$|AASHITTY$|GRAYTAN[12]$)', 'infierno'),
    # Murales, banderas, carteles y logotipos, decorados especiales
    (r'^(MURAL|BIGMURAL|ZZWOLF|DLEVSIGN|PAN(BLACK|BLUE|RED)$|LONGWALL$|SKIRTING$|BIGWALL$|DISASTER$|DOC1$|'
     r'SAW2$|DEXAL$|SHAWN[13]$|BTNTSLVR$|YELMETAL$|GRAYDANG$|GRAYTAN3$|SLADAGN$|TYWHEEL)', 'mural'),
    # Tecnología (ordenadores, consolas, paneles de mando, maquinaria)
    (r'^(COMP|TEKWALL|TEKGREN|TEKBRON|TEKLITE|M_TEC|AQCOMP|AQSECT|SPACEW|PLANET|CUBICLE|ESPI(GR|TAN|BR|G)2$|'
     r'CEMENT[24]$|SILVER3$)', 'tecno'),
    # Tuberías
    (r'^(PIPE|AQPIPE|BROWNPIP)', 'tuberia'),
    # Cajas (y fardos: MTNT = lona militar con letras)
    (r'^(CRATE|CRAT|CR\d|CR[A-Z]+\d|CRBW|CRAW|CRSMB|CRTINY|CRLWDVS$|MTNT)', 'cajas'),
    # Madera
    (r'^(WOOD|A-WOOD|A-MYWOOD|PAN(EL|BOOK|BORD|CASE)|SLIME1$)', 'madera'),
    # Ladrillo / adobe
    (r'^(BRICK|BIGBRIK|A-BRICK|A-BRBRK|A-BRBK|A-DBRI|A-MOSBRI|A-MOSBK|A-PBRIK|A-PBRK|A-BROK|A-BROCK|AQBRIK|'
     r'BRWINDOW|STWALL$|A-TILE$|SLIME[245]$)', 'ladrillo'),
    # Mampostería de cantos rodados con junta: es obra (piedra), no roca natural
    (r'^(AROCK|A-ROCK$|A-MOSRK|A-MOSROK|ROCK[123]$)', 'piedra'),
    # Roca natural, tierra y vegetación (MC* = tierra con musgo de E1; A-CAMO = follaje; A-BROWN/CARL = tierra)
    (r'^(ROCK\d|TANROCK|CAVERN|A-DROCK|A-REDROK|ASHWALL|SP_ROCK|ZIMMER|A-MUD|A-MOULD|MC\d|A-BROWN|A-CAMO|CARL|'
     r'AQDIRT|GRNMEN|GRNOPEN|DOGLDIR|DOGRMSC|DOKGRIR|DOKODO1B|DOPUNK|ALTAQUA|A-VINE[34S]|STONE[567]$)', 'roca'),
    # Encalado / paneles claros
    (r'^(STUCCO|STARTAN|STARG|STARBR|STARGR)', 'encalado'),
    # Piedra / hormigón / mármol / losas
    (r'^(STONE|BSTONE|GSTONE|SMSTONE|MARBLE|MARBGRAY|CEMENT|A-CONCTE|AQCONC|A-MARBLE|GRAY|SLADWALL|SLAD|'
     r'BROVINE|GSTVINE|A-VINE|A-MOSS|ESPI|AQTILE|BASE\d?$|ASPHALT$|PILLAR$)', 'piedra'),
    # Metal (paneles, soportes, remates, chapas, peldaños)
    (r'^(METAL|AQMETL|AQRUST|AQSUPP|AQTRIM|AQPANL|SUPPORT|SHAWN|BRONZE|SILVER|BTNT|TYUNDER|PLAT|STEP|BROWN|'
     r'BRN|ICKWALL|MODWALL|MOD\d|AMOD|WOODMET|EGSUPRT|BLAKWAL)', 'metal'),
]

# Excepciones revisadas a mano mirando las hojas de contactos (familia → nombres). Van antes que las reglas.
_EXC_TEX = {
    # Solo dos se quedan en «otro», a propósito: no hay nada que redibujar.
    'otro': 'AASTINKY '     # textura nula (índice 0 de TEXTURE1: el motor nunca la dibuja)
            'PDUMMY',       # negro liso (fondo de vacío en E2M1-E2M5, junto a salidas): debe seguir negro
    'salida': 'GRAYTAN4',                                   # pared con el cartel rojo EXIT (sin usar)
    'llave_color': 'GRAYTAN7 GRAYTAN8 GRAYTAN9',            # pilotos azul / rojo / amarillo (sin usar)
    'puerta': 'A-BROWN4 '   # hoja con calavera: en los mapas está en líneas de puerta (también de llave)
              'WOODGARG '   # tablas con mascarón: la mitad de sus usos son puertas
              'DOKODO2B ZZWOLF10',
    'luz': 'METAL6 METAL7 SILVER2 BSTONE3 SLIME8 '          # paneles con lámpara/fluorescente o brasero
           'A-YELLOW',                                      # pilotito amarillo de 16x8
    'metal': 'TEKGREN2',                                    # chapas verdes remachadas, sin aparatos
    'piedra': 'SPACEW4 ZZWOLF1 ZZWOLF9',                    # losas / sillares
    'madera': 'ZZWOLF5',
    'ladrillo': 'ZZWOLF11',
}
EXCEPCIONES_TEXTURAS = {n: fam for fam, noms in _EXC_TEX.items() for n in noms.split()}
# Una textura de material genérico que tiene huecos (alfa) se dibuja como reja/ventana.
FAMILIAS_A_REJA_SI_HUECOS = {'metal', 'piedra', 'madera', 'ladrillo', 'encalado'}

# ---------------------------------------------------------------------------------------------------
# Suelos y techos
# ---------------------------------------------------------------------------------------------------
REGLAS_SUELOS = [
    # Líquidos (grupos animados enteros en la misma familia)
    (r'^NUKAGE', 'liquido_veneno'),
    (r'^(FWATER|SWATER|SLIME0[1-8]$)', 'liquido_agua'),       # SLIME01-08: agua cenagosa parda, no hace daño
    (r'^(LAVA|SLIME(09|1[012])$|RROCK0[5-8]$)', 'liquido_lava'),  # SLIME09-12 y RROCK05-08: brasas/lava, dañinas
    (r'^BLOOD', 'liquido_sangre'),
    (r'^GATE', 'teletransporte'),
    (r'^DUMMY', 'otro'),                                       # negros lisos de relleno: no se redibujan
    (r'^(TLITE|CEIL1_2|CEIL1_3|CEIL3_4|CEIL3_6|GRNLITE|FLOOR1_7|FLAT2$|FLAT17$|FLAT22$|'
     r'AQF0(1[0-5]|3[5-9]|4[0-4]|5[89]|6[0-6])$)', 'techo_luz'),
    (r'^(CRATOP|CONS1_)', 'cajas_tapa'),                       # CONS1_*: tapa de consolas (muebles-bloque)
    (r'^(STEP|AQF01[89]$)', 'escalon'),                        # bandas de aviso de bordes y peldaños
    (r'^(GRASS|FLOOR7_2$|RROCK(19|20)$|AQF022$)', 'hierba'),
    (r'^(CEIL|FLAT1$|FLAT9$)', 'techo'),
    (r'^(RROCK0[1-3]$|RROCK1[78]$|FLAT5_[78]$|MFLR8_4$)', 'roca'),
    (r'^(MFLR8_2$|FLOOR7_1$|FLAT5_5$|FLAT10$|RROCK(09|15|16)$|AQF0(08|23)$|FLAT5_6|SFLR)', 'suelo_tierra'),
    (r'^(FLAT5_[12]$|FLOOR0_[12]$|FLOOR5_4$|AQF00[56]$)', 'suelo_madera'),
    (r'^(FLAT5_4$|MFLR8_[13]$|FLAT1_[12]$|FLOOR6_2$|FLAT1[89]$|FLOOR3_3$|RROCK(04|1[123])$|SLIME1[45]$|GRNROCK|'
     r'DEM1_|AQF0(25|28|52|67)$)', 'suelo_piedra'),
    (r'^(FLAT5$|FLOOR4_[68]$|FLAT20$|FLAT8$|FLAT14$|FLOOR1_[16]$|FLOOR6_1$|FLAT5_3$|FLOOR5_[123]$|'
     r'RROCK1[04]$|SLIME1[36]$|AQF0(01|27|4[5-9]|5[01]|53|57|7[4-6])$)', 'suelo_baldosa'),
    (r'^(FLAT23$|FLAT3$|FLOOR0_[3-7]$|FLAT4$|FLAT1_3$|FLOOR4_[15]$|COMP01|FCGRATE|AQF0)', 'suelo_metal'),
]
EXCEPCIONES_SUELOS = {
}


def familia_por_reglas(nombre, reglas, excepciones, defecto='otro'):
    if nombre in excepciones:
        return excepciones[nombre]
    for patron, fam in reglas:
        if re.match(patron, nombre):
            return fam
    return defecto


# ---------------------------------------------------------------------------------------------------
# Lectura del WAD
# ---------------------------------------------------------------------------------------------------
def nombre8(b):
    return b.split(b'\0')[0].decode('ascii', 'replace').upper()


def seccion(lumps, inicios, finales):
    out, dentro = [], False
    for nombre, datos in lumps:
        if nombre in inicios:
            dentro = True
        elif nombre in finales:
            dentro = False
        elif dentro and datos:
            out.append((nombre, datos))
    return out


def leer_texturas(datos):
    n = struct.unpack('<i', datos[:4])[0]
    offs = struct.unpack('<%di' % n, datos[4:4 + 4 * n])
    out = []
    for o in offs:
        nombre = nombre8(datos[o:o + 8])
        _masked, w, h, _coldir, npar = struct.unpack('<ihhih', datos[o + 8:o + 22])
        parches = [struct.unpack('<hhhhh', datos[o + 22 + 10 * i:o + 32 + 10 * i]) for i in range(npar)]
        out.append((nombre, w, h, parches))   # parche: (x, y, índice PNAMES, stepdir, colormap)
    return out


def decodificar_parche(datos):
    """Patch de Doom → (índices uint8 HxW, máscara bool HxW). Admite «tall patches» (fila relativa)."""
    w, h = struct.unpack('<hh', datos[:4])
    idx = np.zeros((h, w), np.uint8)
    msk = np.zeros((h, w), bool)
    for x in range(w):
        p = struct.unpack('<I', datos[8 + 4 * x:12 + 4 * x])[0]
        fila_prev = -1
        while datos[p] != 0xFF:
            fila, largo = datos[p], datos[p + 1]
            if fila <= fila_prev:      # DeePsea tall patch: la fila es relativa
                fila += fila_prev
            fila_prev = fila
            col = np.frombuffer(datos[p + 3:p + 3 + largo], np.uint8)
            fin = min(h, fila + largo)
            if fila < h:
                idx[fila:fin, x] = col[:fin - fila]
                msk[fila:fin, x] = True
            p += largo + 4
    return idx, msk


def leer_mapas(lumps):
    """Por mapa (E1M1…E4M9): lados (sidedefs), sectores y líneas con su especial."""
    mapas = {}
    for i, (nombre, _) in enumerate(lumps):
        if not re.fullmatch(r'E[1-4]M[1-9]', nombre):
            continue
        partes = {lumps[i + k][0]: lumps[i + k][1] for k in range(1, 11)}
        sd, ld, sc = partes['SIDEDEFS'], partes['LINEDEFS'], partes['SECTORS']
        lados = []
        for k in range(len(sd) // 30):
            b = sd[30 * k:30 * k + 30]
            lados.append((nombre8(b[4:12]), nombre8(b[12:20]), nombre8(b[20:28]), struct.unpack('<h', b[28:30])[0]))
        sectores = []
        for k in range(len(sc) // 26):
            b = sc[26 * k:26 * k + 26]
            _fh, _ch = struct.unpack('<hh', b[:4])
            luz, esp, _tag = struct.unpack('<hhh', b[20:26])
            sectores.append((nombre8(b[4:12]), nombre8(b[12:20]), luz, esp))
        lineas = []
        for k in range(len(ld) // 14):
            _v1, _v2, _flags, esp, _tag, dch, izq = struct.unpack('<hhhhhHH', ld[14 * k:14 * k + 14])
            lineas.append((esp, dch, izq))
        mapas[nombre] = (lados, sectores, lineas)
    return mapas


# ---------------------------------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------------------------------
def construir(iwad):
    _, lumps = read_wad(iwad)
    d = {}
    for nombre, datos in lumps:
        d.setdefault(nombre, datos)
    paleta = np.array(read_palette(iwad), np.uint8)

    pn = d['PNAMES']
    pnames = [nombre8(pn[4 + 8 * i:12 + 8 * i]) for i in range(struct.unpack('<i', pn[:4])[0])]
    lumps_parche = dict(seccion(lumps, ('P_START', 'PP_START'), ('P_END', 'PP_END')))
    flats = seccion(lumps, ('F_START', 'FF_START'), ('F_END', 'FF_END'))
    orden_flats = [n for n, _ in flats]

    texturas = [(n, w, h, p, 'TEXTURE1') for n, w, h, p in leer_texturas(d['TEXTURE1'])]
    if 'TEXTURE2' in d:
        texturas += [(n, w, h, p, 'TEXTURE2') for n, w, h, p in leer_texturas(d['TEXTURE2'])]
    orden_tex = [t[0] for t in texturas]

    # Parches decodificados (solo los que usan las texturas)
    cache_parche = {}

    def parche(nombre):
        if nombre not in cache_parche:
            datos = lumps_parche.get(nombre)
            cache_parche[nombre] = decodificar_parche(datos) if datos else None
        return cache_parche[nombre]

    # Componer texturas
    compuestas = {}
    for nombre, w, h, ps, _orig in texturas:
        idx = np.zeros((h, w), np.uint8)
        msk = np.zeros((h, w), bool)
        for x0, y0, pi, _sd, _cm in ps:
            pp = parche(pnames[pi])
            if pp is None:
                continue
            pidx, pmsk = pp
            ph, pw = pidx.shape
            xa, ya = max(0, x0), max(0, y0)
            xb, yb = min(w, x0 + pw), min(h, y0 + ph)
            if xa >= xb or ya >= yb:
                continue
            sub = pmsk[ya - y0:yb - y0, xa - x0:xb - x0]
            idx[ya:yb, xa:xb][sub] = pidx[ya - y0:yb - y0, xa - x0:xb - x0][sub]
            msk[ya:yb, xa:xb] |= sub
        compuestas[nombre] = (idx, msk)

    # Animaciones reales según el orden de texturas/flats del WAD
    def grupos(pares, orden):
        out = {}
        for a, b in pares:
            if a in orden and b in orden and orden.index(b) > orden.index(a):
                out[f'{a}-{b}'] = orden[orden.index(a):orden.index(b) + 1]
        return out
    anim_tex = grupos(ANIM_PAREDES, orden_tex)
    anim_flat = grupos(ANIM_SUELOS, orden_flats)
    tex_anim = {t: g for g, fr in anim_tex.items() for t in fr}
    flat_anim = {f: g for g, fr in anim_flat.items() for f in fr}

    sw_pareja = {}
    for a, b, ep in INTERRUPTORES:
        if a in compuestas and b in compuestas:
            sw_pareja[a] = (b, ep, False)
            sw_pareja[b] = (a, ep, True)
    # Parejas por nombre que el motor NO acciona (no están en su lista): se marcan igual, con episodio 99
    for t in orden_tex:
        if t.startswith('SW1') and t not in sw_pareja and 'SW2' + t[3:] in compuestas:
            sw_pareja[t] = ('SW2' + t[3:], 99, False)
            sw_pareja['SW2' + t[3:]] = (t, 99, True)

    # Uso en los mapas
    mapas = leer_mapas(lumps)
    tex_mapas = collections.defaultdict(set)
    tex_lados = collections.Counter()
    tex_esp = collections.defaultdict(collections.Counter)
    flat_mapas = collections.defaultdict(set)
    flat_sect = collections.Counter()
    flat_esp = collections.defaultdict(collections.Counter)
    mapas_con_cielo = set()
    tex_func = collections.defaultdict(collections.Counter)   # funciones vistas en la cara delantera
    flat_suelo = collections.Counter()                         # sectores con ese flat como SUELO
    flat_suelo_danino = collections.defaultdict(collections.Counter)   # daño → nº de sectores
    for m, (lados, sectores, lineas) in mapas.items():
        for alto, bajo, medio, _sec in lados:
            for t in (alto, bajo, medio):
                if t != '-' and t in compuestas:
                    tex_mapas[t].add(m)
                    tex_lados[t] += 1
        for esp, dch, izq in lineas:
            for lado in (dch, izq):
                if lado != 0xFFFF and lado < len(lados):
                    for t in lados[lado][:3]:
                        if t != '-':
                            tex_esp[t][esp] += 1
            if dch != 0xFFFF and dch < len(lados):
                for f in funciones_de_linea(esp):
                    for t in lados[dch][:3]:
                        if t != '-' and t in compuestas:
                            tex_func[t][f] += 1
        for suelo, techo, _luz, esp in sectores:
            for f in (suelo, techo):
                flat_mapas[f].add(m)
                flat_sect[f] += 1
                flat_esp[f][esp] += 1
            flat_suelo[suelo] += 1
            if esp in SECTOR_DANINO:
                flat_suelo_danino[suelo][SECTOR_DANINO[esp]] += 1
            if 'F_SKY1' in (suelo, techo):
                mapas_con_cielo.add(m)

    def vistos(t):
        s = set(tex_mapas.get(t, ()))
        if t in tex_anim:
            for o in anim_tex[tex_anim[t]]:
                s |= tex_mapas.get(o, set())
        if t in sw_pareja:
            s |= tex_mapas.get(sw_pareja[t][0], set())
        for ep, cielo in CIELOS_EPISODIO.items():
            if t == cielo:
                s |= {m for m in mapas_con_cielo if m[1] == str(ep)}
        return s

    # ---- texturas
    cat_tex = {}
    for nombre, w, h, ps, orig in texturas:
        idx, msk = compuestas[nombre]
        fam = familia_por_reglas(nombre, REGLAS_TEXTURAS, EXCEPCIONES_TEXTURAS)
        if fam in FAMILIAS_A_REJA_SI_HUECOS and not msk.all() and nombre not in EXCEPCIONES_TEXTURAS:
            fam = 'reja'
        e = {
            'familia': fam, 'ancho': w, 'alto': h,
            'parches': list(dict.fromkeys(pnames[p[2]] for p in ps)),
            'colocacion': [[pnames[p[2]], p[0], p[1]] for p in ps],
            'opaca': bool(msk.all()),
            'mapas': len(vistos(nombre)), 'mapas_directos': len(tex_mapas.get(nombre, ())),
            'lados': tex_lados.get(nombre, 0),
            'anim': tex_anim.get(nombre), 'origen': orig,
            'color_medio': color_medio(paleta, idx, msk),
        }
        if nombre in sw_pareja:
            par, ep, pulsado = sw_pareja[nombre]
            e['pareja'] = par
            e['pulsado'] = pulsado
            e['acciona_en_freedoom1'] = ep <= 2
        llave = llave_de(nombre, tex_esp.get(nombre, {}))
        if llave:
            e['llave'] = llave
        if fam == 'salida' or nombre in ('SW1EXIT', 'SW2EXIT'):
            e['salida'] = True
        if re.match(TIRAS_MUESTRA, nombre):
            e['tira'] = True     # tira de muestra de 512 px sin usar: sus parches no deciden familia
        if tex_func.get(nombre):
            # nº de lados (cara delantera) en líneas con esa función: puerta, llave_azul/roja/amarilla,
            # accionable (interruptor S1/SR) y salida. Sirve para no perder la lectura al redibujar.
            e['funciones'] = dict(sorted(tex_func[nombre].items()))
        cat_tex[nombre] = e

    # ---- parches
    usos_parche = collections.defaultdict(list)
    for nombre, w, h, ps, _orig in texturas:
        for p in ps:
            if nombre not in usos_parche[pnames[p[2]]]:
                usos_parche[pnames[p[2]]].append(nombre)
    cat_par = {}
    for pnom in sorted(usos_parche):
        pp = parche(pnom)
        if pp is None:
            continue   # PNAMES apunta a un lump que no es parche (p. ej. TFOGF0): el motor no lo usa
        pidx, pmsk = pp
        texs = usos_parche[pnom]
        # Las tiras de muestra no votan (mezclan de todo); si el parche solo sale en ellas, manda su nombre.
        texs_voto = [t for t in texs if not cat_tex[t].get('tira')]
        peso = collections.Counter()
        for t in texs_voto:
            peso[cat_tex[t]['familia']] += 1000 * cat_tex[t]['lados'] + 10 * cat_tex[t]['mapas'] + 1
        fam = familia_parche(pnom, peso)
        texs = texs_voto or texs     # para anim/pulsado/llave tampoco cuentan las tiras
        anims = sorted({cat_tex[t]['anim'] for t in texs if cat_tex[t]['anim']})
        cat_par[pnom] = {
            'familia': fam, 'ancho': int(pidx.shape[1]), 'alto': int(pidx.shape[0]),
            'opaco': bool(pmsk.all()), 'texturas': usos_parche[pnom],
            'color_medio': color_medio(paleta, pidx, pmsk),
            'anim': anims[0] if anims else None,
        }
        if len(anims) > 1:
            cat_par[pnom]['anims'] = anims
        # Interruptores: si solo lo usan SW1 (o solo SW2) es un parche de estado; hay que distinguirlos.
        estados = {cat_tex[t].get('pulsado') for t in texs}
        if estados == {True} or estados == {False}:
            cat_par[pnom]['pulsado'] = estados.pop()
        llaves = sorted({cat_tex[t]['llave'] for t in texs if cat_tex[t].get('llave')})
        if llaves:
            cat_par[pnom]['llave'] = llaves[0] if len(llaves) == 1 else llaves
        if any(cat_tex[t].get('salida') for t in texs):
            cat_par[pnom]['salida'] = True

    # ---- suelos
    cat_suelos = {}
    for nombre, datos in flats:
        if nombre == 'F_SKY1':
            continue
        idx = np.frombuffer(datos[:4096], np.uint8).reshape(64, 64) if len(datos) >= 4096 else \
            np.zeros((64, 64), np.uint8)
        fam = familia_por_reglas(nombre, REGLAS_SUELOS, EXCEPCIONES_SUELOS)
        # Daño: se mira el grupo animado entero y solo los sectores donde el flat es SUELO. «danino» es el
        # daño por tic si al menos un tercio de esos sectores hacen daño (si no, 0: daña solo por casualidad).
        grupo = anim_flat.get(flat_anim.get(nombre), [nombre])
        n_suelo = sum(flat_suelo.get(o, 0) for o in grupo)
        dan = collections.Counter()
        for o in grupo:
            dan.update(flat_suelo_danino.get(o, {}))
        n_dan = sum(dan.values())
        danino = max(dan) if dan and 3 * n_dan >= n_suelo else 0
        cat_suelos[nombre] = {
            'familia': fam, 'color_medio': color_medio(paleta, idx, np.ones_like(idx, bool)),
            'anim': flat_anim.get(nombre),
            'mapas': len(flat_mapas.get(nombre, set()) |
                         set().union(*[flat_mapas.get(o, set()) for o in anim_flat.get(flat_anim.get(nombre), [])])),
            'mapas_directos': len(flat_mapas.get(nombre, ())),
            'sectores': flat_sect.get(nombre, 0),
            'sectores_suelo': flat_suelo.get(nombre, 0),
            'sectores_suelo_daninos': sum(flat_suelo_danino.get(nombre, {}).values()),
            'danino': danino,
            'peligroso': bool(danino) or fam in ('liquido_veneno', 'liquido_lava', 'liquido_sangre'),
        }

    datos_hojas = dict(paleta=paleta, compuestas=compuestas, parche=parche, flats=dict(flats),
                       tex_esp=tex_esp, flat_esp=flat_esp)
    catalogo = {
        'fuente': os.path.basename(iwad),
        'texturas': cat_tex,
        'parches': cat_par,
        'suelos': cat_suelos,
        'animaciones': {'paredes': anim_tex, 'suelos': anim_flat},
        'interruptores': [{'sw1': a, 'sw2': b, 'acciona_en_freedoom1': ep <= 2}
                          for a, b, ep in INTERRUPTORES if a in compuestas and b in compuestas],
    }
    catalogo['familias'] = {
        'texturas': recuento(cat_tex), 'parches': recuento(cat_par), 'suelos': recuento(cat_suelos)}
    catalogo['familias_otro'] = {
        tipo: {n: MOTIVOS_OTRO.get(n, '¿sin revisar?') for n, e in dic.items() if e['familia'] == 'otro'}
        for tipo, dic in (('texturas', cat_tex), ('parches', cat_par), ('suelos', cat_suelos))}
    return catalogo, datos_hojas


MOTIVOS_OTRO = {
    'AASTINKY': 'textura nula (índice 0 de TEXTURE1): el motor nunca la dibuja',
    'PDUMMY': 'negro liso: fondo de vacío en E2M1-E2M5 (junto a salidas); debe seguir negro',
    'PBLAK': 'relleno negro de las tiras de muestra',
    'SMFILLER': 'relleno negro de 4 px de las tiras de muestra',
    'CYAN': 'parche vacío (todo transparente) de las tiras de muestra',
    'DUMMY1': 'negro liso de relleno (vacíos oscuros en E2M1, E2M3, E2M4 y E4M3)',
    'DUMMY2': 'negro liso sin usar',
    'DUMMY3': 'rombo negro sin usar',
}


def recuento(dic):
    c = collections.Counter(e['familia'] for e in dic.values())
    return dict(sorted(c.items(), key=lambda kv: (-kv[1], kv[0])))


def color_medio(paleta, idx, msk):
    if not msk.any():
        return [0, 0, 0]
    rgb = paleta[idx[msk]].astype(np.float64)
    return [int(round(v)) for v in rgb.mean(axis=0)]


LLAVES_EXTRA = {'GRAYTAN7': 'azul', 'GRAYTAN8': 'rojo', 'GRAYTAN9': 'amarillo'}


def funciones_de_linea(esp):
    """Funciones de un especial de línea de DOOM 1 para quien mira su cara delantera."""
    out = []
    if esp in LINEA_PUERTA:
        out.append('puerta')
    if esp in LINEA_LLAVE:
        out.append('llave_' + {'azul': 'azul', 'rojo': 'roja', 'amarillo': 'amarilla'}[LINEA_LLAVE[esp]])
    if esp in LINEA_INTERRUPTOR:
        out.append('accionable')
    if esp in LINEA_SALIDA:
        out.append('salida')
    return out


def llave_de(nombre, especiales):
    if nombre in LLAVES_EXTRA:
        return LLAVES_EXTRA[nombre]
    m = re.match(r'^DOOR(BLU|RED|YEL)', nombre)
    if m:
        return {'BLU': 'azul', 'RED': 'rojo', 'YEL': 'amarillo'}[m.group(1)]
    m = re.match(r'^M_([BRY])DOOR', nombre)
    if m:
        return {'B': 'azul', 'R': 'rojo', 'Y': 'amarillo'}[m.group(1)]
    return None


def familia_parche(nombre, peso):
    if nombre in EXCEPCIONES_PARCHES:
        return EXCEPCIONES_PARCHES[nombre]
    if not peso:   # solo aparece en tiras de muestra: se clasifica por lo que dibuja (visto en las hojas)
        return familia_por_reglas(nombre, REGLAS_PARCHES_DE_TIRAS, {}, defecto='mural')
    mejor = max(peso.values())
    empatadas = [f for f, v in peso.items() if v == mejor]
    return min(empatadas, key=PRIORIDAD.index)


# Tiras de muestra de 512 px que ningún mapa usa (las de nombre SW1T*/SW2T* siguen siendo interruptores).
TIRAS_MUESTRA = r'^(T-BLODG|T-SLDRP|T-WFALL|BLOD3$|FALL3$|SLAD([2-9]|1[01])$|SW[12]T(SKUL|STON)$)'
# Parches que solo salen en esas tiras, por su contenido.
REGLAS_PARCHES_DE_TIRAS = [
    (r'^(DOBIGTV|DOBLIP|DOTV|DOSH[A-F]1|DOSLVR|PL_|PREEL)', 'tecno'),     # pantallas, armarios, pilotos, bobinas
    (r'^DOSPI', 'reja'),                                                 # telarañas con hueco
    (r'^DOSWX?\d', 'infierno'),                                          # calavera en hornacina de roca
    (r'^TYWFALL', 'cascada'),                                            # agua azul cayendo
    (r'^SAW\dSD$', 'metal'),                                             # costado acanalado de la sierra
    (r'^SAW\d$', 'mural'),                                               # discos de sierra (decorado)
    (r'^(PBLAK|CYAN|SMFILLER)$', 'otro'),                                # rellenos negros / vacíos
]
EXCEPCIONES_PARCHES = {
    'BLOD64B': 'infierno',   # salpicadura de sangre con alfa que se pega sobre chapas (METAL2BD, METAL-BD…)
    # Parches de material liso compartidos con una textura «funcional» que gana por poco el voto:
    'STEP07': 'metal',       # remate pardo de 32x8: zócalo de BROWNPIP, contrahuella de STEP6 y base de DOOR*2
    'SW11_4': 'encalado',    # columnas de bloques anaranjados de STARBR1 (también bajo COMPUTE3)
    'SW11_5': 'encalado',
    'W35_1': 'piedra',       # panel gris de GRAY6 y de los GRAYTAN7-9 (los pilotos de color van en otros parches)
}


# ---------------------------------------------------------------------------------------------------
# Hojas de contactos
# ---------------------------------------------------------------------------------------------------
def fuente(t):
    for ruta in ('/System/Library/Fonts/Geneva.ttf', '/System/Library/Fonts/Supplemental/Arial.ttf',
                 '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if os.path.exists(ruta):
            return ImageFont.truetype(ruta, t)
    return ImageFont.load_default(size=t)


def rgba_de(paleta, idx, msk):
    rgb = paleta[idx]
    a = np.where(msk, 255, 0).astype(np.uint8)
    return Image.fromarray(np.dstack([rgb, a]), 'RGBA')


def fondo_ajedrez(w, h, c=8):
    yy, xx = np.mgrid[0:h, 0:w]
    tablero = ((xx // c + yy // c) % 2).astype(bool)
    arr = np.where(tablero[..., None], np.array([200, 0, 200], np.uint8), np.array([90, 0, 90], np.uint8))
    return Image.fromarray(arr.astype(np.uint8), 'RGB')


def hoja(items, titulo, ruta, celda=(176, 172), caja=(160, 128), columnas=9):
    """items: [(imagen RGBA, etiqueta1, etiqueta2)] → PNG con rejilla."""
    f1, f2, ft = fuente(13), fuente(11), fuente(18)
    filas = max(1, (len(items) + columnas - 1) // columnas)
    W, H = columnas * celda[0], 34 + filas * celda[1]
    img = Image.new('RGB', (W, H), (24, 24, 28))
    dr = ImageDraw.Draw(img)
    dr.text((8, 6), titulo, fill=(255, 230, 120), font=ft)
    for k, (im, e1, e2) in enumerate(items):
        cx, cy = (k % columnas) * celda[0], 34 + (k // columnas) * celda[1]
        w, h = im.size
        esc = min(caja[0] / w, caja[1] / h)
        esc = 2 if esc >= 2 else (1 if esc >= 1 else esc)
        nw, nh = max(1, int(w * esc)), max(1, int(h * esc))
        mini = im.resize((nw, nh), Image.NEAREST if esc >= 1 else Image.BOX)
        ox, oy = cx + (celda[0] - nw) // 2, cy + 2 + (caja[1] - nh) // 2
        base = fondo_ajedrez(nw, nh)
        base.paste(mini, (0, 0), mini)
        img.paste(base, (ox, oy))
        dr.text((cx + 4, cy + caja[1] + 6), e1, fill=(255, 255, 255), font=f1)
        dr.text((cx + 4, cy + caja[1] + 22), e2, fill=(170, 170, 170), font=f2)
    img.save(ruta)


def escribir_hojas(catalogo, dh, carpeta, por_hoja=81):
    os.makedirs(carpeta, exist_ok=True)
    for fn in os.listdir(carpeta):
        if fn.endswith('.png'):
            os.remove(os.path.join(carpeta, fn))
    pal = dh['paleta']
    escritas = []
    # texturas por familia (orden: más usadas primero)
    por_fam = collections.defaultdict(list)
    for n, e in catalogo['texturas'].items():
        por_fam[e['familia']].append(n)
    for fam in FAMILIAS_PARED + sorted(set(por_fam) - set(FAMILIAS_PARED)):
        noms = sorted(por_fam.get(fam, []), key=lambda n: (-catalogo['texturas'][n]['lados'], n))
        for parte in range(0, len(noms), por_hoja):
            items = []
            for n in noms[parte:parte + por_hoja]:
                e = catalogo['texturas'][n]
                idx, msk = dh['compuestas'][n]
                marcas = ''.join([
                    'A' if e['anim'] else '', '2' if e['origen'] == 'TEXTURE2' else '',
                    'H' if not e['opaca'] else '', '*' if e.get('pulsado') else '',
                    ('K' + {'azul': 'az', 'rojo': 'ro', 'amarillo': 'am'}[e['llave']]) if e.get('llave') else '', 'S' if e.get('salida') else ''])
                items.append((rgba_de(pal, idx, msk), n, f"{e['ancho']}x{e['alto']} m{e['mapas']} l{e['lados']} {marcas}"))
            ruta = os.path.join(carpeta, f'tex_{fam}_{parte // por_hoja + 1}.png')
            hoja(items, f'TEXTURAS · {fam} ({len(noms)})  [A anim · 2 TEXTURE2 · H huecos · * SW2 · K llave · S salida]', ruta)
            escritas.append(ruta)
    # suelos por familia
    por_fam = collections.defaultdict(list)
    for n, e in catalogo['suelos'].items():
        por_fam[e['familia']].append(n)
    items = []
    for fam in FAMILIAS_SUELO + sorted(set(por_fam) - set(FAMILIAS_SUELO)):
        for n in sorted(por_fam.get(fam, []), key=lambda n: (-catalogo['suelos'][n]['sectores'], n)):
            e = catalogo['suelos'][n]
            idx = np.frombuffer(dh['flats'][n][:4096], np.uint8).reshape(64, 64)
            items.append((fam, rgba_de(pal, idx, np.ones((64, 64), bool)), n,
                          f"{fam[:12]} m{e['mapas']} s{e['sectores']}{' A' if e['anim'] else ''}{' D' if e['danino'] else ''}"))
    por_hoja_s = 72
    for parte in range(0, len(items), por_hoja_s):
        trozo = items[parte:parte + por_hoja_s]
        fams = sorted({t[0] for t in trozo}, key=(FAMILIAS_SUELO + ['zz']).index)
        ruta = os.path.join(carpeta, f'suelos_{parte // por_hoja_s + 1}.png')
        hoja([t[1:] for t in trozo], 'SUELOS · ' + ', '.join(fams) + '  [A anim · D dañino]', ruta,
             celda=(150, 168), caja=(128, 128), columnas=10)
        escritas.append(ruta)
    # parches por familia (solo los de varias texturas o distintos de su textura homónima)
    por_fam = collections.defaultdict(list)
    for n, e in catalogo['parches'].items():
        por_fam[e['familia']].append(n)
    for fam in FAMILIAS_PARED:
        noms = sorted(por_fam.get(fam, []))
        for parte in range(0, len(noms), 99):
            items = []
            for n in noms[parte:parte + 99]:
                e = catalogo['parches'][n]
                pidx, pmsk = dh['parche'](n)
                items.append((rgba_de(pal, pidx, pmsk), n, f"{e['ancho']}x{e['alto']} t{len(e['texturas'])}{'' if e['opaco'] else ' H'}"))
            ruta = os.path.join(carpeta, f'parches_{fam}_{parte // 99 + 1}.png')
            hoja(items, f'PARCHES · {fam} ({len(noms)})', ruta, celda=(150, 120), caja=(128, 80), columnas=11)
            escritas.append(ruta)
    return escritas


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--iwad', default=os.path.join(RAIZ, 'wads', 'freedoom-0.13.0', 'freedoom1.wad'))
    ap.add_argument('--json', default=os.path.join(RAIZ, 'arte', 'texturas', 'catalogo.json'))
    ap.add_argument('--hojas', help='carpeta donde escribir hojas de contactos por familia (opcional)')
    args = ap.parse_args()
    catalogo, dh = construir(args.iwad)
    os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
    with open(args.json, 'w', encoding='utf-8') as f:
        json.dump(catalogo, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write('\n')
    print(f"→ {args.json}: {len(catalogo['texturas'])} texturas, {len(catalogo['parches'])} parches, "
          f"{len(catalogo['suelos'])} suelos")
    for k, v in catalogo['familias'].items():
        print(f'  {k}: ' + ', '.join(f'{f} {n}' for f, n in v.items()))
    if args.hojas:
        rutas = escribir_hojas(catalogo, dh, args.hojas)
        print(f'→ {len(rutas)} hojas en {args.hojas}')


if __name__ == '__main__':
    main()
