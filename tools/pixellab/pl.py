#!/usr/bin/env python3
"""pl.py — cliente mínimo de la API de PixelLab (https://api.pixellab.ai/v2) para PESADILLA.

La clave es la PROPIA del proyecto y se lee de secrets/pixellab.key (en .gitignore, nunca se sube
ni se imprime). Cada llamada de pago apunta su coste en arte/gasto.jsonl.

REGLA DEL PROYECTO: antes de generar, dar a Zarko la estimación y esperar su OK (CLAUDE.md).

Uso:
    python3 tools/pixellab/pl.py saldo
    python3 tools/pixellab/pl.py personaje --desc "..." --tam 64 --vista side --semilla 1 --salida arte/prototipo/penitente_a
    python3 tools/pixellab/pl.py descargar --id CHARACTER_ID --salida arte/prototipo/penitente_a
    python3 tools/pixellab/pl.py imagen --desc "..." --ancho 96 --alto 96 --sin-fondo --salida arte/prototipo/pistolon.png
"""
import argparse
import base64
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CLAVE = os.path.join(RAIZ, 'secrets', 'pixellab.key')
GASTO = os.path.join(RAIZ, 'arte', 'gasto.jsonl')
API = 'https://api.pixellab.ai/v2'
DIRECCIONES = ['south', 'south-west', 'west', 'north-west', 'north', 'north-east', 'east', 'south-east']


def token():
    if not os.path.exists(CLAVE):
        sys.exit(f'Falta la clave del proyecto en {CLAVE}')
    t = open(CLAVE).read().strip()
    if not t:
        sys.exit(f'{CLAVE} está vacío')
    return t


def llamar(metodo, ruta, cuerpo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(API + ruta, data=datos, method=metodo, headers={
        'Authorization': 'Bearer ' + token(),
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    })
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        sys.exit(f'PixelLab {metodo} {ruta} → HTTP {e.code}: {e.read().decode(errors="replace")[:800]}')


def apuntar_gasto(accion, respuesta, extra=None):
    os.makedirs(os.path.dirname(GASTO), exist_ok=True)
    fila = {'fecha': datetime.datetime.now().isoformat(timespec='seconds'), 'accion': accion,
            'usage': respuesta.get('usage')}
    if extra:
        fila.update(extra)
    with open(GASTO, 'a') as f:
        f.write(json.dumps(fila, ensure_ascii=False) + '\n')
    print('gasto:', json.dumps(respuesta.get('usage'), ensure_ascii=False))


def esperar(job_id, cada=6, maximo=1800):
    t0 = time.time()
    while True:
        j = llamar('GET', f'/background-jobs/{job_id}')
        estado = j.get('status')
        if estado == 'completed':
            return j
        if estado == 'failed':
            sys.exit('trabajo fallido: ' + json.dumps(j.get('last_response'), ensure_ascii=False)[:800])
        if time.time() - t0 > maximo:
            sys.exit(f'trabajo {job_id} sin terminar tras {maximo} s')
        lr = j.get('last_response') or {}
        cola = lr.get('queue_position') if isinstance(lr, dict) else None
        print(f'  … {estado}' + (f' (cola {cola})' if cola is not None else ''), flush=True)
        time.sleep(cada)


def bajar(url, destino):
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as r, open(destino, 'wb') as f:
        f.write(r.read())


def descargar_personaje(cid, salida):
    c = llamar('GET', f'/characters/{cid}')
    for _ in range(30):  # las rotaciones llegan un poco después de acabar el trabajo
        if c.get('status') != 'pending':
            break
        time.sleep(5)
        c = llamar('GET', f'/characters/{cid}')
    os.makedirs(salida, exist_ok=True)
    json.dump(c, open(os.path.join(salida, 'personaje.json'), 'w'), ensure_ascii=False, indent=1)
    rot = c.get('rotation_urls') or c.get('rotations') or {}
    if isinstance(rot, list):
        rot = {r.get('direction'): r.get('url') for r in rot}
    n = 0
    for d in DIRECCIONES:
        url = rot.get(d) if isinstance(rot, dict) else None
        if isinstance(url, dict):
            url = url.get('url')
        if url:
            bajar(url, os.path.join(salida, f'rot_{d}.png'))
            n += 1
    print(f'{n} direcciones descargadas en {salida} (detalles en personaje.json)')
    return c


def cmd_saldo(a):
    print(json.dumps(llamar('GET', '/balance'), ensure_ascii=False, indent=1))


def cmd_personaje(a):
    cuerpo = {'description': a.desc, 'view': a.vista, 'image_size': {'width': a.tam, 'height': a.tam},
              'no_background': True, 'outline': a.contorno, 'detail': a.detalle}
    if a.semilla is not None:
        cuerpo['seed'] = a.semilla
    if a.nombre:
        cuerpo['name'] = a.nombre
    r = llamar('POST', '/create-character-v3', cuerpo)
    apuntar_gasto('create-character-v3', r, {'character_id': r.get('character_id'), 'desc': a.desc, 'tam': a.tam})
    print('personaje', r.get('character_id'), '· trabajo', r.get('background_job_id'))
    esperar(r['background_job_id'])
    descargar_personaje(r['character_id'], a.salida)


def cmd_descargar(a):
    descargar_personaje(a.id, a.salida)


def cmd_imagen(a):
    cuerpo = {'description': a.desc, 'image_size': {'width': a.ancho, 'height': a.alto},
              'no_background': a.sin_fondo}
    for k, v in (('view', a.vista), ('direction', a.direccion), ('outline', a.contorno),
                 ('detail', a.detalle), ('seed', a.semilla)):
        if v is not None:
            cuerpo[k] = v
    r = llamar('POST', '/create-image-pixflux', cuerpo)
    apuntar_gasto('create-image-pixflux', r, {'desc': a.desc, 'tam': [a.ancho, a.alto]})
    img = r['image']
    os.makedirs(os.path.dirname(os.path.abspath(a.salida)), exist_ok=True)
    open(a.salida, 'wb').write(base64.b64decode(img['base64']))
    print('→', a.salida)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('saldo').set_defaults(f=cmd_saldo)

    p = sub.add_parser('personaje')
    p.add_argument('--desc', required=True)
    p.add_argument('--tam', type=int, default=64)
    p.add_argument('--vista', default='side', choices=['side', 'low top-down', 'high top-down'])
    p.add_argument('--contorno', default='single color black outline')
    p.add_argument('--detalle', default='high detail')
    p.add_argument('--semilla', type=int)
    p.add_argument('--nombre')
    p.add_argument('--salida', required=True)
    p.set_defaults(f=cmd_personaje)

    p = sub.add_parser('descargar')
    p.add_argument('--id', required=True)
    p.add_argument('--salida', required=True)
    p.set_defaults(f=cmd_descargar)

    p = sub.add_parser('imagen')
    p.add_argument('--desc', required=True)
    p.add_argument('--ancho', type=int, required=True)
    p.add_argument('--alto', type=int, required=True)
    p.add_argument('--sin-fondo', action='store_true')
    p.add_argument('--vista')
    p.add_argument('--direccion')
    p.add_argument('--contorno')
    p.add_argument('--detalle')
    p.add_argument('--semilla', type=int)
    p.add_argument('--salida', required=True)
    p.set_defaults(f=cmd_imagen)

    a = ap.parse_args()
    a.f(a)


if __name__ == '__main__':
    main()
