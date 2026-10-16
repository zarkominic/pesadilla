# STATUS — PESADILLA

**Última actualización:** 2026-10-16 · CLI (Mac)

## Hecho
- Carpeta y git creados. Plan y licencias en CLAUDE.md.
- Motor: cloudflare/doom-wasm (commit 65e0d3ae2ffa604155eebd96ed40da6567bd08f4) copiado en `motor/` (sin su .git: lo modificaremos y la GPL pide publicar el código).
- Freedoom 0.13.0 bajado a `wads/` (SHA-256 verificado; se vuelve a bajar con tools/descargar_freedoom.sh).
- Homebrew: emscripten, automake, autoconf, pkg-config, sdl2_mixer, sdl2_net.
- Motor compilado con Emscripten 6. Ajustes en configure.ac (EXPORTED_RUNTIME_METHODS, INITIAL_MEMORY,
  sin USE_PTHREADS, SAFE_HEAP=0) y en scripts/build.sh (ac_cv_* para autoconf 2.72).
- **Arreglado el cuelgue al empezar cualquier nivel** («memory access out of bounds» en P_PlayerThink):
  con Emscripten 6, `<emscripten.h>` incluye `<stdbool.h>` y 5 ficheros veían `boolean` de 1 byte y el
  resto de 4 → `playeringame[]` y otros globales se leían mal. Ahora `boolean` es siempre `int`
  (motor/src/doomtype.h, con _Static_assert). Se juega E1M1, menús y disparo OK.
- **Repositorio GitHub (privado):** https://github.com/zarkominic/pesadilla. Hacerlo público al publicar
  el juego (GPL). `index.html` y `default.cfg` no estaban en git por un .gitignore heredado: ya están.
- **tools/wad/**: PNG → patch de Doom → PWAD (`construir_pwad.py`), cargado con `-merge`. Probado con
  sprites teñidos del zombi y la pistola: entran bien en el juego.
- Ficha técnica del prototipo: `docs/PROTOTIPO.md` (zombi POSS = 70 sprites; pistola = 4).

## En curso
- Prueba exhaustiva automática (Playwright headless, en el scratchpad de la sesión): mapas E1–E4 y demos,
  mecánicas/intermedios, guardar/cargar (¿persiste al recargar?), teclado/ratón/página, sonido/música/
  rendimiento. Después: arreglar lo confirmado y enseñárselo a Zarko.

## Siguiente paso
1. Zarko prueba en local: `cd motor/src && python3 -m http.server 8765` → http://localhost:8765/
2. PROTOTIPO: proponer temática + nº de sprites + coste a Zarko y esperar su OK ANTES de generar.
   PixelLab (conectado por MCP) tiene la suscripción caducada (2026-09-30) y puede ser la cuenta de
   Arcade → pedir clave propia del proyecto (o de fal) y guardarla en `secrets/`.

## Preguntas abiertas
- Estilo de personajes (Zarko: sin preferencia → decidir viendo el prototipo).
- Temática de los personajes (qué sustituye a marines, demonios, armas).
