# STATUS — PESADILLA

**Última actualización:** 2026-10-16 · CLI (Mac)

## Hecho
- Carpeta y git creados. Plan y licencias en CLAUDE.md.
- Motor: cloudflare/doom-wasm (commit 65e0d3ae2ffa604155eebd96ed40da6567bd08f4) copiado en `motor/` (sin su .git: lo modificaremos y la GPL pide publicar el código).
- Freedoom 0.13.0 bajado a `wads/` (SHA-256 verificado; se vuelve a bajar con tools/descargar_freedoom.sh).
- Homebrew: emscripten, automake, autoconf, pkg-config, sdl2_mixer, sdl2_net.
- Motor compilado con Emscripten 6 (ajustes en configure.ac y scripts/build.sh).
- **Repositorio GitHub (privado):** https://github.com/zarkominic/pesadilla. Hacerlo público al publicar
  el juego (GPL; la página ya enlaza al código y a las licencias).
- **Partida completa probada a fondo** (Playwright headless, 5 áreas en paralelo + verificador escéptico
  por área): 36 mapas × 2 dificultades, demos, menús, intermedios, salida secreta, los 4 finales,
  muerte/reaparición, guardar/cargar, teclado/ratón/foco, tamaños de pantalla, sonido, ritmo (35 tics/s
  exactos) y memoria (sin fugas en 5 min). Fallos encontrados y arreglados:
  - Cuelgue al empezar cualquier nivel (`boolean` de 1 byte en unos ficheros y 4 en otros por stdbool.h).
  - Guardar en 7 de los 36 mapas colgaba el juego (límite de 180 KB del DOOM original).
  - Partidas y opciones se perdían al recargar → IndexedDB (IDBFS), una sola pestaña a la vez.
  - Errores fatales: pantalla negra y bucle hasta desbordar la pila → mensaje en la página.
  - Tecla F congelaba 1 s; «Quit Game» dejaba la página muerta; no pausaba al cambiar de pestaña.
  - Música: colgaba el juego si se activaba (OPL_Delay) → arreglada y activada.
  - Marca «Doom» en el título → PESADILLA. Página nueva adaptable (móvil a 4K), controles y créditos.
  - Controles seguros en navegador (sin Ctrl: en Mac Ctrl+flecha cambia de escritorio).
  - Memoria que crece (antes 64 MB fijos y cualquier exceso abortaba).
  - Batería de 18 comprobaciones automáticas: scratchpad de la sesión (pw/arreglos.mjs); todas OK.
- **tools/wad/**: PNG → patch de Doom → PWAD (`construir_pwad.py`), cargado con `-merge`. Probado con
  sprites teñidos del zombi y la pistola.
- Ficha técnica del prototipo: `docs/PROTOTIPO.md` (zombi POSS = 70 sprites; pistola = 4).

- **Prototipo de arte hecho y DENTRO del juego** (2026-10-16): temática folk horror español, dibujado por
  código (sin IA de pago, decisión de Zarko): **el Penitente** sustituye al zombi (POSS, 70 sprites) y **el
  pistolón de chispa** a la pistola (4). `tools/arte/construir.sh` regenera todo; la página carga
  `pesadilla.wad` de serie. Batería de 18 pruebas OK con el arte cargado.

## En curso
- Zarko aprobó el estilo (2026-10-16): seguir igual con el resto. Plan y estado en `docs/BESTIARIO.md`.
- **Lote 1 hecho y dentro del juego** (307 sprites en `pesadilla.wad`, batería 18/18 OK): Bandolero (SPOS),
  Meiga + bola de fuego (TROO, BAL1), Toro Negro (SARG, también el espectro), escopeta de caza
  (SHTG/SHTF/SHOT) y puño (PUNG). Revisado por un director de arte (agente) y corregido.
  Motores comunes: `tools/arte/sdf.py` (criaturas) y `tools/arte/arma1p.py` (armas).
- Pendiente del lote 1 (menor): apoyo de 0-3 px distinto en cadáveres del Bandolero/Toro; texto
  «Got the pump-action shotgun!» (cambiarlo con el resto de textos).
- Siguiente: enseñárselo a Zarko y, con su OK, lote 2 (Ánima, Coco, Hombre del Saco, hoz, órgano de fuego…).

## Pendiente para publicar
- Build release: quitar `-g` (configure.ac:29) y `-gsource-map --source-map-base /` (configure.ac:118):
  wasm 7,7 → 2,2 MB (enlazar con `--emit-symbol-map` para seguir pudiendo traducir errores; ese fichero no se
  publica). Servir comprimido (gzip/brotli): descarga total de 37 MB a ~11 MB. El WAD final
  debería llevar solo lo que usemos (Freedoom1 completo es el 90 % de la descarga).
- Repo público (GPL) y créditos de Freedoom (CREDITS.txt) junto al juego.
- Opcional: D_RunFrame duerme con Asyncify ~210 veces/s (≈265 rAF/s); se puede alinear a vsync.

## Preguntas abiertas
- Estilo y temática de los personajes (propuesta: folk horror español; decidir viendo el prototipo).
