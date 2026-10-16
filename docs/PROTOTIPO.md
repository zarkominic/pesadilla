# Prototipo de arte: 1 enemigo + 1 arma

Sustituyen al **zombi** (POSS, el primer enemigo de E1M1) y a la **pistola** (PISG/PISF, el arma
inicial) de Freedoom, en un PWAD aparte (`build/pesadilla.wad`, ver `tools/wad/README.md`).
La jugabilidad no cambia: mismos estados, tiempos, daño y vida (info.c); solo cambian los dibujos.

## Enemigo — 70 sprites (nombres POSS + fotograma + ángulo)

| Fotogramas | Uso en el juego (info.c) | Ángulos | Sprites |
|---|---|---|---|
| A, B, C, D | andar (A y B también en reposo) | 8 | 32 |
| E | apuntar (antes y después del disparo) | 8 | 8 |
| F | disparar (con fogonazo dibujado) | 8 | 8 |
| G | dolor | 8 | 8 |
| H, I, J, K, L | muerte normal (L = cadáver que queda) | 1 (`0`, siempre igual) | 5 |
| M … U | muerte despedazado (U = restos) | 1 (`0`) | 9 |
| | | **Total** | **70** |

Ángulos de Doom ↔ direcciones (comprobado con los sprites de Freedoom):

| Ángulo | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| Mira hacia | de frente (sur) | frente-izquierda (suroeste) | izquierda (oeste) | espalda-izquierda (noroeste) | de espaldas (norte) | espalda-derecha (noreste) | derecha (este) | frente-derecha (sureste) |

«Izquierda» es la izquierda de la pantalla. Doom permite reflejar ángulos (A2A8, A3A7, A4A6) para
dibujar solo 5 por fotograma, pero el enemigo quedaría simétrico (arma cambiando de mano), así que
el plan es dibujar los 8.

Tamaño de referencia (Freedoom): ~42×57 px de pie, 67×16 px los restos. El suelo queda 4 px por
encima del borde inferior del sprite. Vista lateral a la altura de los ojos (no cenital).

## Arma — 4 sprites

| Lump | Uso | Tamaño Freedoom |
|---|---|---|
| PISGA0 | en reposo (también al subir/bajar el arma) | 82×92 |
| PISGB0 | disparo (retroceso) | 82×96 |
| PISGC0 | vuelta tras el disparo | 84×100 |
| PISFA0 | fogonazo (se dibuja a pleno brillo encima) | 32×30 |

Vista en primera persona, la mano entra desde abajo; la parte inferior queda tapada por la barra de
estado. PISGD0/PISGE0 existen en Freedoom pero el juego no los usa.

## Paleta

Todo se convierte a los 256 colores de PLAYPAL (Freedoom). Conviene generar el arte ya con pocos
colores y contraste alto: la luz de Doom oscurece por distancia con COLORMAP, y los tonos muy
oscuros se pierden.
