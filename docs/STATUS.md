# STATUS — PESADILLA

**Última actualización:** 2026-10-16 · CLI (Mac)

## Hecho
- Carpeta y git creados. Plan y licencias en CLAUDE.md.
- Motor: cloudflare/doom-wasm (commit 65e0d3ae2ffa604155eebd96ed40da6567bd08f4) copiado en `motor/` (sin su .git: lo modificaremos y la GPL pide publicar el código).
- Freedoom 0.13.0 bajado a `wads/` (SHA-256 verificado; se vuelve a bajar con tools/descargar_freedoom.sh).
- Homebrew: emscripten, automake, autoconf, pkg-config, sdl2_mixer, sdl2_net.

- **Motor compilado y funcionando en el navegador** con Freedoom (pantalla de título OK). Ajustes para
  Emscripten 6 en configure.ac (EXPORTED_RUNTIME_METHODS, INITIAL_MEMORY, sin USE_PTHREADS, SAFE_HEAP=0
  — con 1 abortaba por un acceso desalineado en D_CheckNetGame) y en scripts/build.sh (ac_cv_* para autoconf 2.72).

## Siguiente paso
1. Que Zarko lo pruebe jugando en local (`cd motor/src && python3 -m http.server 8765` → http://localhost:8765/).
   No se pudo probar el juego en sí desde el panel del navegador de Claude: con el panel oculto el bucle se pausa.
2. Elegir estilo con un PROTOTIPO: 1 enemigo + 1 arma propios en píxel, con su coste estimado ANTES de generar.
3. Crear el remoto en GitHub (privado o público: la GPL obliga a publicar el código del motor al publicar el juego).

## Preguntas abiertas
- Estilo de personajes (Zarko: sin preferencia → decidir viendo el prototipo).
- Temática de los personajes (qué sustituye a marines, demonios, armas).
