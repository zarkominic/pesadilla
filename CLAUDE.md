# CLAUDE.md — PESADILLA

> Manual operativo del proyecto. Léelo entero al empezar cada sesión.

**PESADILLA** es un juego GRATIS que se juega en el NAVEGADOR: la jugabilidad de DOOM (1993) tal
cual, con personajes, armas, texturas y sonidos propios (solo cambios estéticos). Se publicará
gratis (itch.io o web propia).

## Base técnica y licencias (decidido con Zarko el 2026-10-16)

| Pieza | Qué es | Licencia / obligación |
|---|---|---|
| `motor/` | [cloudflare/doom-wasm](https://github.com/cloudflare/doom-wasm): Chocolate Doom compilado a WebAssembly con Emscripten | **GPL-2.0**: hay que publicar el código del motor (y nuestros cambios) junto al juego |
| `wads/freedoom-0.13.0/` | [Freedoom](https://freedoom.github.io) 0.13.0: niveles y recursos libres, compatibles con DOOM | **BSD**: atribución obligatoria (CREDITS.txt) |
| Arte, sonido y música nuevos | Nuestros, en un WAD/PWAD aparte | Nuestros |

- **NUNCA** usar recursos ni niveles originales de id Software (doom.wad, doom2.wad, ni el
  shareware doom1.wad en lo que se publique): están protegidos.
- **NUNCA** llamar al juego «DOOM» ni usar su logo: es marca registrada.
- Limitaciones del motor: resolución original (320×200 escalada) y **paleta de 256 colores**
  (PLAYPAL). Todo el arte nuevo se convierte a esa paleta (o a una paleta propia en el WAD).
- Los enemigos de DOOM se ven desde **8 ángulos** y cada animación (andar, atacar, dolor, morir)
  tiene varios fotogramas: unos 40-60 sprites por enemigo. Presupuestar antes de generar.

## Reglas de trabajo con Zarko

1. Responde en **español**. Zarko sigue a menudo desde el móvil: mensajes cortos, imágenes con
   SendUserFile (nunca solo la ruta).
2. **Arte:** Zarko prefiere arte DIBUJADO POR CÓDIGO (tools/arte/*.py), sin PixelLab ni IA de pago.
   **Gasto de IA (REGLA FIRME), si algún día se usa:** antes de cualquier generación de pago (fal u otro), dar a Zarko
   la estimación (nº de imágenes/clips y $) y esperar su OK. Nada de agentes generando en paralelo.
   Si se usa fal, con una **clave de fal propia de este proyecto** (no la de Arcade), guardada en
   `secrets/` (que está en .gitignore y NUNCA se sube).
3. **Validación entre cambios:** tras cada cambio que se vea o se juegue, enseñárselo a Zarko
   (captura o enlace local) y esperar su visto bueno antes del siguiente.
4. Commit y push sin pedir permiso cuando haya remoto configurado.

## Comandos

```bash
# Compilar el motor para web (necesita Homebrew: emscripten automake autoconf pkg-config sdl2_mixer sdl2_net)
cd motor && ./scripts/clean.sh; ./scripts/build.sh     # salida: src/pesadilla.{js,wasm}

# Jugar en local: el motor carga src/doom1.wad (nombre fijo) → copiamos ahí el IWAD libre
cp ../wads/freedoom-0.13.0/freedoom1.wad src/doom1.wad
cd src && python3 -m http.server 8765      # abrir http://localhost:8765/

# Pruebas: index.html?args=-warp%201%207 añade parámetros del motor (-warp, -skill, -playdemo…)

# Volver a bajar Freedoom (si falta wads/)
tools/descargar_freedoom.sh

# Arte propio (dibujado por código, sin IA de pago): regenera arte/sprites/*.png y motor/src/pesadilla.wad
tools/arte/construir.sh          # necesita ~/.venvs/pesadilla con numpy y Pillow (tools/wad/README.md)
```

## Cómo funciona la versión web (motor/src/index.html)

- Partidas y opciones en `/libsdl/pesadilla/`, montado con IDBFS (IndexedDB del navegador); se
  sincroniza tras guardar. Solo una pestaña a la vez (candado). Si cambian los valores de fábrica de
  `default.cfg` (p. ej. teclas), subir `VERSION_CFG` en index.html.
- Móvil y tableta sin ratón: mandos táctiles en pantalla (`?tactil=1` o `=0` para forzarlos o quitarlos).
- Controles (seguros en navegador, sin Ctrl): WASD/flechas, ratón gira, clic o Espacio disparan,
  E o Enter usan/reaparecen, Mayús corre, C o Alt + flechas paso lateral.
- Música: OPL emulado (snd_musicdevice 3). Memoria: empieza en 64 MB y crece si hace falta; caché de sonido 16 MB
  (presupuestar sonidos propios: tamaño ×17 al expandirse a 48 kHz).
- Errores fatales (I_Error) se muestran en la página. «Quit Game» vuelve al título.
- Depuración: `emsymbolizer motor/src/pesadilla.wasm 0xOFFSET` traduce un offset de un error de wasm
  a fichero:línea (la build lleva -g; para publicar, quitar -g y -gsource-map: wasm 7,7 → 2,2 MB).

## Ojo: iCloud

`~/Documents` se sincroniza con iCloud y, al compilar, a veces crea copias «fichero 2» / «fichero 2.ext» (o 3, 4…).
Están en .gitignore; si molestan, `find . -name "* [0-9]*" -not -path "./.git/*" -delete`.
**iCloud borró objetos de `.git`** (2026-10-16; se recuperaron con `git fetch --refetch origin`). Desde entonces
la base de datos de git vive FUERA de iCloud: `.git` es un fichero que apunta a `~/git-dirs/pesadilla.git`
(`git init --separate-git-dir`). Si se clona en otro sitio, hacer lo mismo. Si git dice «invalid object» o
«missing blob»: `git fetch --refetch origin` y `git fsck`.

## Estado

Ver [`docs/STATUS.md`](docs/STATUS.md).
