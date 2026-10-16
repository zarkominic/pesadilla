# STATUS — PESADILLA

**Última actualización:** 2026-10-16 · CLI (Mac)

## Hecho
- Carpeta y git creados. Plan y licencias en CLAUDE.md.
- Motor: cloudflare/doom-wasm (commit 65e0d3ae2ffa604155eebd96ed40da6567bd08f4) copiado en `motor/` (sin su .git: lo modificaremos y la GPL pide publicar el código).
- Freedoom 0.13.0 bajado a `wads/` (SHA-256 verificado; se vuelve a bajar con tools/descargar_freedoom.sh).
- Homebrew: emscripten, automake, autoconf, pkg-config, sdl2_mixer, sdl2_net.

## Siguiente paso
1. Compilar el motor (`motor/scripts/build.sh`) y jugar Freedoom en el navegador en local.
2. Elegir estilo con un PROTOTIPO: 1 enemigo + 1 arma propios en píxel, con su coste estimado ANTES de generar.
3. Crear el remoto en GitHub (privado o público: la GPL obliga a publicar el código del motor al publicar el juego).

## Preguntas abiertas
- Estilo de personajes (Zarko: sin preferencia → decidir viendo el prototipo).
- Temática de los personajes (qué sustituye a marines, demonios, armas).
