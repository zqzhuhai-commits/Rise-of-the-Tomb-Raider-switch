#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""找出 codegen 输出中没有函数归属的代码空隙（gaps / huecos）。

原理与参考移植 StevensND/nfsmw-nx 的 tools/huecos.py 一致（GPL-3.0）：
- PowerPC 每条指令固定 4 字节，ReXGlue codegen 对每条指令恰好输出一行
  "\t// <asm>" 注释；
- 从 codegen.partition.json 得到每个函数的起始地址，再从生成 C++ 中数出每个
  函数的指令条数，从而算出其结束地址；
- 一个函数结束地址与下一个函数起始地址之间的区域就是"无主空隙"。间接调用
  （函数指针 / vtable）可能跳到其中，运行期报
      [FATAL] Call to invalid or unregistered function at guest address 0xXXXXXXXX
- 把空隙起始地址声明为函数（huecos.toml 的 [functions]）即可让 codegen 的
  Discover 阶段覆盖它。

注意（与参考项目相同的已知限制）：一个空隙不一定只有一个函数。声明空隙起始
地址后若运行期仍报"落在已声明空隙内部"（+8/+24/+64 字节处），说明该空隙含
多个小函数（常见为 8/16 字节 thunk 表），需手工拆分或按运行期崩溃地址逐个加。

用法：
    python3 tools/find_gaps.py                # 默认 --min 8，输出报告与参考 TOML
    python3 tools/find_gaps.py --min 4        # 更小的空隙
    python3 tools/find_gaps.py --comprobar 0x82C21240 0x8215FEA8   # 定位具体地址
"""
import argparse
import bisect
import json
import os
import re
import sys

RE_FUNC = re.compile(r'^DEFINE_REX_FUNC\((?:sub_)?([0-9A-Fa-f]{8})\)')

DEFAULT_GEN = 'generated/default'
DEFAULT_EXCLUDE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'huecos_excluir.txt')


def medir_funciones(gen_dir):
    """返回 {起始地址: 指令条数}：遍历生成 C++，数每个函数体里的 \\t// 注释行。"""
    tamanos = {}
    ficheros = sorted(f for f in os.listdir(gen_dir) if f.endswith('.cpp'))
    for idx, nombre in enumerate(ficheros, 1):
        ruta = os.path.join(gen_dir, nombre)
        actual = None
        n = 0
        with open(ruta, 'r', encoding='utf-8', errors='replace') as fh:
            for linea in fh:
                if linea.startswith('DEFINE_REX_FUNC('):
                    m = RE_FUNC.match(linea)
                    if m:
                        actual = int(m.group(1), 16)
                        n = 0
                elif actual is not None:
                    if linea.startswith('\t// '):
                        n += 1
                    elif linea.startswith('}'):
                        tamanos[actual] = n
                        actual = None
        sys.stderr.write("\r  已读 %d/%d 个文件" % (idx, len(ficheros)))
        sys.stderr.flush()
    sys.stderr.write('\n')
    return tamanos


def leer_assignments(gen_dir):
    """读取 codegen.partition.json 的函数归属表，返回排序后的起始地址列表。"""
    part = os.path.join(gen_dir, 'codegen.partition.json')
    if not os.path.exists(part):
        raise SystemExit('缺少 %s。请先运行 ReXGlue codegen。' % part)
    asignaciones = json.load(open(part, encoding='utf-8'))['assignments']
    return sorted(int(k, 16) for k in asignaciones)


def leer_exclusiones(path):
    """读取排除列表：即使空隙也不得声明为函数（多为 .text 内嵌数据块）。"""
    exclu = set()
    if os.path.exists(path):
        with open(path, encoding='utf-8') as fh:
            for linea in fh:
                s = linea.split('#', 1)[0].strip()
                if re.fullmatch(r'0x[0-9A-Fa-f]+', s):
                    exclu.add(int(s, 16))
    return exclu


def main():
    p = argparse.ArgumentParser(description='找出 codegen 输出中没有函数归属的代码空隙')
    p.add_argument('--gen', default=DEFAULT_GEN, help='codegen 输出目录（默认 generated/default）')
    p.add_argument('--min', type=int, default=8, help='要列出的空隙最小字节数（默认 8）')
    p.add_argument('--comprobar', nargs='*', default=[], help='要定位的具体地址，如 0x82C21240')
    p.add_argument('--salida', default='docs/huecos.txt', help='人类可读报告输出路径')
    p.add_argument('--toml', default='tools/huecos_functions.toml', help='参考 TOML 块输出路径')
    p.add_argument('--excluir', default=DEFAULT_EXCLUDE, help='排除地址列表')
    args = p.parse_args()

    gen_dir = args.gen
    if not os.path.isdir(gen_dir):
        raise SystemExit('目录不存在: %s' % gen_dir)

    print('读取函数归属表...')
    inicios = leer_assignments(gen_dir)
    print('  %d 个函数' % len(inicios))

    print('测量生成 C++ 中每个函数的指令数...')
    tamanos = medir_funciones(gen_dir)
    print('  %d 个已测量' % len(tamanos))

    faltan = [a for a in inicios if a not in tamanos]
    if faltan:
        print('  警告: %d 个函数未能测量（忽略）' % len(faltan))

    # 计算空隙：函数结束地址与下一个函数起始地址之间的空白
    huecos = []
    for i, a in enumerate(inicios[:-1]):
        n = tamanos.get(a)
        if n is None:
            continue
        fin = a + 4 * n
        siguiente = inicios[i + 1]
        if fin < siguiente:
            huecos.append((fin, siguiente - fin, a, siguiente))

    exclu = leer_exclusiones(args.excluir)
    grandes = [h for h in huecos if h[1] >= args.min and h[0] not in exclu]
    excluidos = [h for h in huecos if h[1] >= args.min and h[0] in exclu]

    dist = {}
    for _, tam, _, _ in huecos:
        dist[tam] = dist.get(tam, 0) + 1

    lineas = []
    def w(s=''):
        print(s)
        lineas.append(s)

    w()
    w('=' * 60)
    w('  无函数归属的代码空隙')
    w('=' * 60)
    w('函数总数            : %d' % len(inicios))
    w('空隙总数            : %d' % len(huecos))
    w('空隙 >= %d 字节      : %d' % (args.min, len(grandes)))
    w('被排除列表滤掉       : %d' % len(excluidos))
    w('空隙总字节数         : %d' % sum(h[1] for h in huecos))
    w()
    w('空隙大小分布:')
    for tam in sorted(dist):
        w('   %5d 字节  x %d' % (tam, dist[tam]))
    w()

    if args.comprobar:
        w('-' * 60)
        w('查询地址:')
        for s in args.comprobar:
            t = int(s, 16)
            pos = bisect.bisect_left(inicios, t)
            es_inicio = pos < len(inicios) and inicios[pos] == t
            dentro = next((h for h in huecos if h[0] <= t < h[0] + h[1]), None)
            w('  0x%08X  是函数起始: %s' % (t, '是' if es_inicio else '否'))
            if dentro:
                w('      落在 %d 字节空隙内: 0x%08X - 0x%08X'
                  % (dentro[1], dentro[0], dentro[0] + dentro[1]))
                w('      （函数 0x%08X 之后、0x%08X 之前）' % (dentro[2], dentro[3]))
            elif not es_inicio:
                w('      不在任何已知空隙内')
        w()

    w('-' * 60)
    w('前 60 个 >= %d 字节的空隙:' % args.min)
    for fin, tam, ini, sig in grandes[:60]:
        w('  0x%08X  %5d 字节  （函数 0x%08X 之后、0x%08X 之前）' % (fin, tam, ini, sig))
    if len(grandes) > 60:
        w('  ... 以及另外 %d 个' % (len(grandes) - 60))

    os.makedirs(os.path.dirname(args.salida) or '.', exist_ok=True)
    with open(args.salida, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lineas) + '\n')
        fh.write('\n' + '-' * 60 + '\n全部 >= %d 字节的空隙:\n' % args.min)
        for fin, tam, ini, sig in grandes:
            fh.write('  0x%08X  %5d 字节  （函数 0x%08X 之后、0x%08X 之前）\n'
                     % (fin, tam, ini, sig))
    print()
    print('完整报告: %s' % args.salida)

    os.makedirs(os.path.dirname(args.toml) or '.', exist_ok=True)
    with open(args.toml, 'w', encoding='utf-8') as fh:
        fh.write('# 由 tools/find_gaps.py 生成 - 不要整块直接使用。\n')
        fh.write('# 空隙可能是数据块/填充，声明为函数可能破坏 codegen；\n')
        fh.write('# 只复制确实需要的条目到 huecos.toml。\n')
        fh.write('[functions]\n')
        for fin, tam, ini, sig in grandes:
            fh.write('"0x%08X" = { }   # %d 字节，函数 0x%08X 之后\n' % (fin, tam, ini))
    print('参考 TOML 块: %s' % args.toml)


if __name__ == '__main__':
    main()
