#!/bin/bash
# build.sh — compila el motor a WebAssembly (salida: src/websockets-doom.{html,js,wasm}).
# 2026-10-16 (PESADILLA): con autoconf ≥2.72 y Emscripten 6, configure se rompe en las pruebas de
# C23 y de builtins no declarados → se fuerzan esas respuestas (ac_cv_*). Ver CLAUDE.md.
cd "`dirname \"$0\"`/.."

emmake make clean
emconfigure autoreconf -fiv
ac_cv_exeext=".html" ac_cv_prog_cc_c23=no ac_cv_prog_cc_c11="-std=gnu11" \
  ac_cv_c_undeclared_builtin_options="none needed" \
  emconfigure ./configure --host=none-none-none

emmake make
