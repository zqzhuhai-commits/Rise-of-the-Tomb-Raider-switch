#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把没有 hook 的游戏函数调用改写为直接调用，使 LTO 能跨文件内联。

原理与参考移植 StevensND/nfsmw-nx 的 tools/llamadas_directas.py 一致（GPL-3.0）：
- GCC 下每个重编译函数 sub_X 都是 __imp__sub_X 的弱别名（DEFINE_REX_FUNC），
  hook（REX_HOOK_RAW）在链接期替换 sub_X；
- codegen 一律调用 sub_X。编译器无法内联弱函数（hook 可能在链接期替换它），
  同文件内与 LTO 下都不行；
- 本工具把没有 hook 的 sub_X(ctx, base); 改写成 __imp__sub_X(ctx, base);——
  语义完全相同，但现在可以被内联（配合 ROTTR_LTO）。

"有 hook" 的判定：凡是出现在 src/、SDK 源码与头文件、各 toml、CMakeLists.txt
中的 82xxxxxx 地址都视为有 hook（比实际需要略多，安全；D3D trace 之类会用
sub_##addr 拼 hook 名）。

不改 rottr_init.cpp / rottr_register.cpp：间接调用分发表仍指向 sub_X，因此
hook 依然生效。每次 codegen 后都必须重跑本工具（新生成的代码会恢复 sub_X 调用）。

用法：
    python3 tools/direct_calls.py [--deshacer] [--gen <generated 目录>] [--sdk <SDK 目录>]
"""
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(RAIZ, 'generated', 'default')
SDK = os.path.join(RAIZ, '..', 'masseffect-nx-review', 'sdk')
TOMLS = ['analysis_overrides.toml', 'huecos.toml', 'rottr_manifest.toml',
         'rottr-switch.toml', 'CMakeLists.txt']


def enganchadas(sdk_dir):
    """收集所有视为有 hook 的地址，返回 {'sub_XXXXXXXX', ...}。"""
    nombres = set()
    fuentes = [os.path.join(RAIZ, 'src')]
    if os.path.isdir(sdk_dir):
        fuentes += [os.path.join(sdk_dir, 'src'), os.path.join(sdk_dir, 'include')]
    for toml in TOMLS:
        ruta = os.path.join(RAIZ, toml)
        if os.path.isfile(ruta):
            fuentes.append(ruta)
    for raiz in fuentes:
        if os.path.isfile(raiz):
            rutas = [raiz]
        else:
            rutas = [os.path.join(d, f) for d, _, fs in os.walk(raiz) for f in fs
                     if not f.endswith(('.a', '.obj', '.o', '.png', '.jpg', '.bin', '.wasm'))]
        for ruta in rutas:
            try:
                with open(ruta, encoding='utf-8', errors='ignore') as fh:
                    texto = fh.read()
            except OSError:
                continue
            for m in re.findall(r'(?<![0-9A-Fa-f])(82[0-9A-Fa-f]{6})(?![0-9A-Fa-f])', texto):
                nombres.add('sub_' + m.upper())
    return nombres


def main():
    deshacer = '--deshacer' in sys.argv
    gen = sys.argv[sys.argv.index('--gen') + 1] if '--gen' in sys.argv else GEN
    if '--sdk' in sys.argv:
        sdk_dir = sys.argv[sys.argv.index('--sdk') + 1]
    else:
        sdk_dir = SDK
    if '--enganchadas' in sys.argv:
        with open(sys.argv[sys.argv.index('--enganchadas') + 1], encoding='utf-8') as fh:
            con_gancho = set(fh.read().split())
    else:
        con_gancho = enganchadas(sdk_dir)

    llamada = re.compile(r'(?<![\w])sub_([0-9A-Fa-f]{8})\(ctx,\s*base\);')
    directa = re.compile(r'(?<![\w])__imp__sub_([0-9A-Fa-f]{8})\(ctx,\s*base\);')
    cambiadas = 0
    ficheros = 0
    for f in sorted(os.listdir(gen)):
        if not (f.startswith('rottr_recomp.') and f.endswith('.cpp')):
            continue
        ruta = os.path.join(gen, f)
        with open(ruta, encoding='utf-8') as fh:
            texto = fh.read()
        if deshacer:
            nuevo, n = directa.subn(lambda m: 'sub_%s(ctx, base);' % m.group(1).upper(), texto)
        else:
            def cambiar(m):
                if 'sub_' + m.group(1).upper() in con_gancho:
                    return m.group(0)
                return '__imp__sub_%s(ctx, base);' % m.group(1).upper()
            nuevo = llamada.sub(cambiar, texto)
            n = len(llamada.findall(texto)) - len(llamada.findall(nuevo))
        if nuevo != texto:
            with open(ruta, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(nuevo)
            ficheros += 1
        cambiadas += n
    print('%s: %d 处调用，涉及 %d 个文件；%d 个地址视为有 hook 被保留' %
          ('已还原' if deshacer else '已改写为直接调用', cambiadas, ficheros, len(con_gancho)))


if __name__ == '__main__':
    main()
