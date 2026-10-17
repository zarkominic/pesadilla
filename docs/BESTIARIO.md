# Bestiario y armería de PESADILLA

Temática: **folk horror español** (aprobada por Zarko el 2026-10-16). Todo el arte se dibuja POR
CÓDIGO (`tools/arte/*.py`), con el mismo motor y estilo que el prototipo. La jugabilidad no cambia:
cada pieza sustituye solo los dibujos de su equivalente de Freedoom (mismos estados de `info.c`).
Nada de símbolos religiosos explícitos ni parecidos con el KKK (capirotes oscuros, nunca blancos).

## Enemigos (Freedoom 1 = los 9 de DOOM 1)

| Sprite | Sustituye a | Nuestro enemigo | Idea | Estado |
|---|---|---|---|---|
| POSS | zombi | **El Penitente** | nazareno con capirote granate y trabuco | ✅ hecho |
| SPOS | sargento de escopeta | **El Bandolero** | bandolero de Sierra Morena no muerto: sombrero calañés, manta al hombro, faja, escopeta de dos cañones, cara de calavera | ✅ lote 1 |
| TROO | imp (bola de fuego) | **La Meiga** | bruja gallega encorvada, harapos y pelo blanco, garras, lanza bolas de fuego verde-amarillo (BAL1) | ✅ lote 1 |
| SARG | demonio (y espectro) | **El Toro Negro** | toro negro de pesadilla a cuatro patas, cuernos enormes, ojos rojos, banderillas | ✅ lote 1 |
| SKUL | alma perdida | **El Ánima** | calavera en llamas, de las que van en la Santa Compaña | ✅ lote 2 |
| HEAD | cacodemonio | **El Coco** | cabeza flotante deforme con una boca enorme; escupe fuego anaranjado (BAL2) | ✅ lote 2 |
| BOSS | barón del infierno | **El Hombre del Saco** | gigantón con saco a la espalda, lanza fuego verde (BAL7) | ✅ lote 2 |
| CYBR | ciberdemonio | **El Gran Cabrón** | macho cabrío gigante del aquelarre (Goya), con cañón de feria a la cadera (dispara MISL) | ✅ lote 3 |
| SPID | mente maestra araña | **La Tarasca** | dragona de seis patas de las procesiones con su carroza y una batería de cañones | ✅ lote 3 |

## Armas

| Sprites | Sustituye a | Nuestra arma | Estado |
|---|---|---|---|
| PISG/PISF | pistola | **Pistolón de chispa** | ✅ hecho |
| PUNG | puño | **Puño** (misma mano enguantada) | ✅ lote 1 |
| SHTG/SHTF + SHOT | escopeta | **Escopeta de caza** de dos cañones | ✅ lote 1 (texto «pump-action» pendiente) |
| SAWG + CSAW | motosierra | **La hoz** (siega continua) | ✅ lote 2 |
| CHGG/CHGF + MGUN | ametralladora | **El órgano de fuego** (cañones en batería) | ✅ lote 2 |
| MISG/MISF + LAUN, MISL | lanzacohetes | **Lanzacohetes de feria** (pirotecnia de fallas); el cohete MISL lo usa también el Gran Cabrón | ✅ lote 2 |
| PLSG/PLSF + PLAS, PLSS/PLSE | rifle de plasma | **Farol de fuegos fatuos** (bolas azules) | ✅ lote 3 |
| BFGG/BFGF + BFUG, BFS1/BFE1/BFE2 | BFG | **La Campana de Velilla** (toque que lo arrasa todo) | ✅ lote 3 |

**Todos los enemigos y armas de Freedoom 1 están hechos** (713 sprites, 17 scripts, 2026-10-17).
Pendiente de texto: los mensajes al recoger armas siguen siendo los de Freedoom («Got the pump-action
shotgun!», «You got the chainsaw!»…): cambiarlos cuando se traduzcan los textos.

## Cómo se hace cada pieza

- Criaturas: `tools/arte/sdf.py` (motor común: primitivas SDF, render, paleta, contorno, `cli`).
  Ejemplo completo: `tools/arte/penitente.py`. Todos los fotogramas que usa `info.c`, con 8
  ángulos REALES para los que rotan y de frente (ángulo 0) para muertes.
- Armas en primera persona: motor común `tools/arte/arma1p.py`; ejemplos `pistolon.py`, `escopeta.py`, `puno.py`
  (offsets en `arte/sprites/offsets.json`).
- `tools/arte/construir.sh` regenera todo y el WAD; ver `docs/PROTOTIPO.md` para ángulos y tamaños.
