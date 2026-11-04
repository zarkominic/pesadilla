#!/usr/bin/env python3
"""jugador.py — el protagonista (PLAY): chaqueta de cuero, pistolón y bandana de España.

Se ve poco en una partida normal, pero sus fotogramas de muerte salen como cadáveres de decoración en los
mapas (N y S). Usa las poses y las piezas del Penitente, con otro cuerpo.
Uso: jugador.py --salida arte/sprites [--solo PLAYA1] [--hoja hoja.png]
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import penitente as P  # noqa: E402
from penitente import (BLOOD, BONE, BRASS, EMISSIVE, EYE, FLASH, FLESH, HOLE, OUTLINE, SOCKET,  # noqa: E402
                       NECK, SHOULDER, UPPER_ARM, FOREARM, HIP_Y, walk, AIM, FIRE, PAIN, deaths, fall_root,
                       gun_parts, hand)
from sdf import (V, nrm, rot_x, rot_y, rot_z, rad, basis, Frame, _len, Sphere, Ellipsoid, RoundCone, EllCone,  # noqa: E402
                 Ring, Group, Render, finish, trim, ik, cli, sprite_rows)

CUERO, PANTALON, BOTA, PIEL, PELO, BANDA, ROJO, AMARILLO, CAMISA, OJO = range(20, 30)
RAMPS = dict(P.RAMPS)
RAMPS.update({
    CUERO: [79, 78, 77, 76, 75, 74, 73],
    PANTALON: [7, 6, 5, 110, 108, 105],
    BOTA: [0, 2, 239, 238],
    PIEL: [74, 71, 67, 63, 59, 55],
    PELO: [0, 7, 6, 5],
    ROJO: [187, 184, 181, 178, 176],
    AMARILLO: [164, 163, 162, 161, 160, 231],
    BANDA: [184],
    OJO: [0],
    CAMISA: [141, 137, 133, 130, 128],
})
TELAS = (CUERO, PANTALON, CAMISA, PIEL, P.RAG)


def materiales(Q, mat, inten, nz, nr, spec, lvl_extra, extras):
    banda = extras.get('banda')
    if banda is not None:
        F, h = banda
        y = F.to_local(Q)[:, 1] / h
        m = mat == BANDA
        mat[m] = ROJO
        mat[m & (y > .27) & (y < .73)] = AMARILLO  # bandera: 1-2-1
    for sc, sr in extras.get('stains', []):
        d = _len(Q - sc)
        mat[np.isin(mat, TELAS) & (d < sr * (.75 + .5 * nz))] = BLOOD
    sin_manchas = dict(extras, stains=[], eyes=[])
    P.materiales(Q, mat, inten, nz, nr, spec, lvl_extra, sin_manchas)


RENDER = None


def render():
    global RENDER
    if RENDER is None:
        RENDER = Render(RAMPS, hook=materiales, flash_mats=(FLASH,), level_mats=(EYE,), emissive=EMISSIVE + (OJO,),
                        no_light=(FLASH, EYE, HOLE, SOCKET, OJO))
    return RENDER


DEFAULT = dict(P.DEFAULT, skirt=True)


def build(pose):
    p = dict(DEFAULT)
    p.update(pose)
    root = p['root'] or Frame()
    xf = p['flatten']
    groups = []
    extras = {'stains': []}
    up = root * Frame((0, HIP_Y + p['bob'], 0), rot_y(rad(p['twist'])) @ rot_x(rad(p['lean'])) @ rot_z(rad(p['side'])))
    head = up * Frame(NECK, rot_x(rad(p['head_pitch'])) @ rot_z(rad(p['head_roll'])))

    if p['legs']:
        tela, botas = [], []
        for sx, foot, lift in ((-1, p['foot_r'], p['lift_r']), (1, p['foot_l'], p['lift_l'])):
            cad = root.p((3.0 * sx, HIP_Y - 1 + p['bob'], 0))
            tob = root.p(V(foot) + (0, 1.6 + lift, 0))
            rod = ik(cad, tob, 12.8, 12.8, root.d((0, 0, 1)))
            fwd = root.d((.12 * sx, -.05 if lift == 0 else -.25, 1))
            tela += [RoundCone(cad, rod, 3.3, 2.7, PANTALON), RoundCone(rod, tob + (rod - tob) * .3, 2.7, 2.2, PANTALON)]
            botas += [RoundCone(tob - fwd * 1.0 - root.d((0, .4, 0)), tob + fwd * 3.9 - root.d((0, .9, 0)), 1.7, 1.4, BOTA),
                      RoundCone(tob, tob + (rod - tob) * .34, 2.0, 2.3, BOTA)]
        groups += [Group(tela, k=1.2, name='piernas'), Group(botas, k=.5, name='botas')]

    if not p['no_torso']:
        cuerpo = [Ellipsoid(up.p((0, 6.8, -.2)), (5.9, 8.2, 3.9), up.M(), CUERO), Sphere(up.p((0, 10.4, -1.3)), 3.9, CUERO),
                  Ellipsoid(up.p((0, -.6, 0)), (5.4, 3.4, 3.8), up.M(), PANTALON)]
        for sx in (-1, 1):
            cuerpo.append(Sphere(up.p((SHOULDER[0] * sx, SHOULDER[1], SHOULDER[2])), 2.6, CUERO))
        groups.append(Group(cuerpo, k=2.0, name='torso'))
        groups.append(Group([Ellipsoid(up.p((0, 10.0, 3.1)), (1.7, 4.2, 1.1), up.M(), CAMISA)], k=0, name='camisa'))
        groups.append(Group([Ring(up * Frame((0, 1.6, .1)), 5.9, 4.2, .7, BOTA)], name='cinto'))

    if not p['no_hood']:  # cabeza
        cara = [Ellipsoid(head.p((0, 3.5, .5)), (3.4, 4.4, 3.7), head.M(), PIEL),
                RoundCone(up.p((0, 13.0, 0)), head.p((0, 1.0, 0)), 1.9, 1.8, PIEL),
                Sphere(head.p((0, 3.0, 4.2)), .8, PIEL)]
        groups.append(Group(cara, k=.7, name='cara'))
        groups.append(Group([Ellipsoid(head.p((0, 7.6, -.2)), (3.6, 2.5, 3.8), head.M(), PELO),
                             Ellipsoid(head.p((0, 3.5, -2.4)), (3.1, 3.6, 2.0), head.M(), PELO)], k=.8, name='pelo'))
        ojos = [Sphere(head.p((1.55 * s, 2.9, 3.55)), .85, OJO) for s in (-1, 1)]
        groups.append(Group(ojos, name='ojos'))
        F = head * Frame((0, 4.7, .1))  # en la frente, por encima de los ojos
        h = 3.2
        groups.append(Group([EllCone(F, h, (3.8, 4.05), (3.5, 3.85), BANDA)], name='banda'))
        extras['banda'] = (F, h)
        n = head.p((0, 6.0, -4.1))
        cola = [Sphere(n, 1.05, ROJO), RoundCone(n, head.p((-1.7, .6, -5.8)), .75, .55, ROJO),
                RoundCone(n, head.p((1.7, 1.2, -5.8)), .75, .55, AMARILLO)]
        groups.append(Group(cola, k=.2, name='nudo'))

    GF = None
    gs = p['gun']
    if not p['no_gun'] and gs is not None:
        Mg = basis(gs['f'], gs.get('up', (0, 1, 0)))
        GF = up * Frame(gs['grip'], Mg) if gs['frame'] == 'upper' else Frame(gs['grip'], Mg)
        partes, boca = gun_parts(GF)
        groups.append(Group(partes, k=.25, name='gun'))
        extras['muzzle'] = boca
        if p['flash']:
            mc, f, _ = boca
            nucleo = mc + f * 2.2
            fl = [Sphere(nucleo, 2.5, FLASH), RoundCone(mc + f * .8, mc + f * 8.5, 1.8, .25, FLASH)]
            for dv in (GF.d((1, 0, 0)), GF.d((-1, 0, 0)), GF.d((0, 1, 0)), GF.d((0, -1, 0))):
                fl.append(RoundCone(mc + f * 1.6, mc + f * 1.6 + nrm(f * .8 + dv) * 5.5, 1.1, .2, FLASH))
            groups.append(Group(fl, k=.6, name='flash'))
            extras['flash_core'] = (nucleo, 9.0)
            extras['flash_light'] = (nucleo, 22.0)

    if not p['no_arms']:
        mangas, manos = [], []
        for sx, cual, ag in ((-1, 'hand_r', 'grip_r'), (1, 'hand_l', 'grip_l')):
            S = up.p((SHOULDER[0] * sx, SHOULDER[1], SHOULDER[2]))
            spec = p[cual]
            if spec == 'gun' and GF is not None:
                T, along = GF.p(p[ag]), GF.d((0, 0, 1))
            elif spec == 'gun':
                continue
            else:
                T = up.p(spec[1]) if spec[0] == 'upper' else root.p(spec[1]) if spec[0] == 'root' else V(spec[1])
                along = nrm(T - S)
            E = ik(S, T, UPPER_ARM, FOREARM, up.d((.8 * sx, -.6, -.7)))
            mangas += [RoundCone(S, E, 2.2, 1.9, CUERO), RoundCone(E, T - nrm(T - E) * 1.6, 1.9, 1.7, CUERO)]
            manos += hand(T, along if spec == 'gun' else nrm(T - E), PIEL)
        if mangas:
            groups += [Group(mangas, k=.8, name='mangas'), Group(manos, k=.4, name='manos')]

    def donde(fr, pt):
        return up.p(pt) if fr == 'upper' else root.p(pt) if fr == 'root' else head.p(pt) if fr == 'head' else V(pt)

    extras['stains'] = [(donde(fr, pt), r) for fr, pt, r in p['stains']]
    if p['spray']:
        groups.append(Group([Sphere(donde(fr, pt), r, BLOOD) for fr, pt, r in p['spray']], name='spray'))
    groups += list(p['extra'])
    if xf is not None:
        for g in groups:
            if g.name not in ('gun', 'extra', 'pool', 'spray'):
                g.xf = xf
    ax = root.p((0, 0, 0))
    extras['axis'] = (ax[0], ax[2])
    return groups, extras


def muertes():
    """H-N: siete fotogramas. Las cinco poses del Penitente y dos intermedias."""
    H, I, J, K, L = deaths()
    J2 = dict(J, root=fall_root(58, 35, 13, 1.5), hand_r=('root', (-14.5, 29.0, 4.0)), hand_l=('root', (13.5, 32.0, 2.0)))
    K2 = {k: v for k, v in L.items() if k not in ('flatten', 'crush', 'extra')}
    K2.update(root=fall_root(84, 50, 24, 4.2))
    return [H, I, J, J2, K, K2, L]


GIB_T = [0.0, .10, .22, .34, .46, .58, .72, .86, 1.0]
GIB_S = [1.0, .95, .8, .66, .52, .4, .3, .22, .17]


def fragmentos():
    rng = np.random.default_rng(1978)
    out = []

    def add(tipo, mat, tam, y0, n, vx=(10, 30), vy=(30, 70)):
        for _ in range(n):
            a = rng.uniform(0, 2 * math.pi)
            sp = rng.uniform(*vx)
            out.append((tipo, mat, tam * rng.uniform(.75, 1.25), V(rng.uniform(-4, 4), y0 + rng.uniform(-4, 4), rng.uniform(-2, 2)),
                        V(math.cos(a) * sp, rng.uniform(*vy), math.sin(a) * sp * .45), rng.uniform(-6, 6)))
    add('tela', CUERO, 3.0, 38, 8)
    add('hueso', BONE, 3.2, 40, 5)
    add('bola', FLESH, 1.7, 40, 4)
    add('bola', BLOOD, 1.2, 40, 14, (8, 34), (20, 80))
    out.append(('tela', ROJO, 2.4, V(1, 50, 0), V(9, 70, -2), 3.0))    # la bandana, hecha jirones
    out.append(('tela', AMARILLO, 2.4, V(-1, 50, 0), V(-7, 78, 2), -3.0))
    out.append(('calavera', BONE, 2.7, V(.5, 48, .5), V(-14, 62, 3), 3.0))
    return out


def gib(k):
    t = GIB_T[k]
    if k == 0:
        H = dict(deaths()[0])
        H['spray'] = list(H['spray']) + [('upper', (-3, 8, 6.5), 1.7), ('upper', (4.5, 6, 6), 1.5), ('upper', (0, 4, 7.5), 1.3),
                                         ('upper', (-5.5, 11, 8.5), 1.0), ('upper', (6, 12, 9), .9)]
        return build(H)
    s = GIB_S[k]
    base = dict(no_torso=True, no_hood=True, no_arms=True, no_gun=True, legs=True, lean=0.0,
                flatten=(np.diag([1.0, s, 1.0]), V(0, 0, 0), s),
                stains=[('root', (1, 25 * s, 2.5), 3.5), ('root', (-2.5, 20 * s, 2.8), 2.5)])
    partes = []
    for tipo, mat, tam, p0, v, giro in fragmentos():
        rest = {'tela': .6, 'hueso': .8, 'bola': tam * .5, 'calavera': tam}[tipo]
        c, cayo = P._ballistic(p0, v, t, rest)
        Rm = rot_z(giro * min(t, .6)) @ rot_x(.7 * giro * min(t, .6))
        if tipo == 'tela':
            partes.append(Ellipsoid(c, (tam * 1.5, tam * (.35 if cayo else .6), tam), Rm, mat))
        elif tipo == 'hueso':
            ax = Rm @ V(1, .2, 0)
            if cayo:
                ax = nrm(V(ax[0], 0, ax[2]))
            partes += [RoundCone(c - ax * tam, c + ax * tam, .75, .6, mat), Sphere(c - ax * tam, .95, mat), Sphere(c + ax * tam, .95, mat)]
        elif tipo == 'bola':
            if cayo and mat == BLOOD:
                partes.append(Ellipsoid(V(c[0], .2, c[2]), (tam * 2.2, .4, tam * 1.6), None, mat))
            else:
                partes.append(Sphere(c, tam, mat))
        else:
            partes += [Sphere(c, tam, BONE), Ellipsoid(c + V(0, -1.6, 1.0), (1.6, 1.1, 1.4), None, BONE)]
    groups, extras = build(base)
    groups.append(Group(partes, k=.3, name='extra'))
    if k >= 4:
        rr = 6.0 + 14.0 * (k - 4) / 4
        groups.append(Group([Ellipsoid((1, .15, -1), (rr, .5, rr * .42), None, BLOOD)], name='pool'))
    return groups, extras


def lumps():
    out = {}
    for i, fr in enumerate('ABCD'):
        for a in range(1, 9):
            out[f'PLAY{fr}{a}'] = (walk(i), a)
    for fr, pose in (('E', AIM), ('F', FIRE), ('G', PAIN)):
        for a in range(1, 9):
            out[f'PLAY{fr}{a}'] = (pose, a)
    for fr, pose in zip('HIJKLMN', muertes()):
        out[f'PLAY{fr}0'] = (pose, 1)
    for k, fr in enumerate('OPQRSTUVW'):
        out[f'PLAY{fr}0'] = (('gib', k), 1)
    return out


def draw(pose, angle):
    groups, extras = gib(pose[1]) if isinstance(pose, tuple) else build(pose)
    R = render()
    out, depth = R.render(groups, extras, angle)
    return trim(finish(out, depth, R.palarr, OUTLINE))


if __name__ == '__main__':
    cli(lumps, draw, sprite_rows('PLAY', 'ABCDEFG', 'HIJKLMNOPQRSTUVW'))
