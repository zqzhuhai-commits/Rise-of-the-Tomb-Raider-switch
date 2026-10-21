#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析 codegen 输出中的越界 switch trap，为缺口补全提供依据。

codegen-result.json 记录了 607 处
    __builtin_trap(); // Switch case out of range
这类 trap 出现在跳转表翻译成的 switch 的 default 分支：switch 变量命中了
"映射表里没有的地址"。可能原因：
1. 跳转目标地址没有被识别为函数（缺 huecos / overrides 声明）——需要补；
2. 该 case 指向的是数据、thunk 或合法死路径——需人工判断，不能盲补。

本工具逐条定位每个 trap：所在文件、所在函数、switch 表达式、该 switch 已覆盖
的 case 值。输出 gap-analysis-result.json 并与 codegen-result.json 的 607
核对，不一致时报警。

用法：
    python3 tools/analyze_traps.py [--gen generated/default]
"""
import argparse
import json
import os
import re
import sys

MARKER = '__builtin_trap(); // Switch case out of range'
RE_FUNC = re.compile(r'^DEFINE_REX_FUNC\(sub_([0-9A-Fa-f]{8})\)')
RE_SWITCH = re.compile(r'\bswitch\s*\((.*)\)\s*\{?\s*$')
RE_CASE = re.compile(r'^\s*case\s+0x([0-9A-Fa-f]+)\s*:')
RE_TRAP = re.compile(re.escape(MARKER))


def analizar(gen_dir):
    """扫描生成 C++，返回 (traps 列表, 每个文件的 trap 数)。"""
    traps = []
    por_archivo = {}
    ficheros = sorted(f for f in os.listdir(gen_dir) if f.endswith('.cpp'))
    for nombre in ficheros:
        ruta = os.path.join(gen_dir, nombre)
        with open(ruta, encoding='utf-8', errors='replace') as fh:
            funcion = None       # 当前函数地址（int）
            switch = None        # {expr, cases, depth} 或 None
            depth = 0
            for lineno, linea in enumerate(fh, 1):
                m = RE_FUNC.match(linea)
                if m:
                    funcion = int(m.group(1), 16)
                    switch = None
                    depth = 0
                # 更新括号深度（忽略字符串/注释中的括号；生成代码为机器生成，足够可靠）
                depth += linea.count('{') - linea.count('}')
                ms = RE_SWITCH.search(linea)
                if ms and 'default' not in linea:
                    switch = {'expr': ms.group(1).strip(), 'cases': [], 'depth': depth}
                if switch is not None:
                    if depth < switch['depth']:
                        switch = None
                    else:
                        for mc in RE_CASE.finditer(linea):
                            switch['cases'].append(int(mc.group(1), 16))
                if RE_TRAP.search(linea):
                    tramo = {
                        'file': nombre,
                        'line': lineno,
                        'function': '0x%08X' % funcion if funcion else None,
                    }
                    if switch is not None:
                        tramo['switch_expr'] = switch['expr']
                        tramo['covered_cases'] = ['0x%X' % c for c in switch['cases']]
                    traps.append(tramo)
                    por_archivo[nombre] = por_archivo.get(nombre, 0) + 1
    return traps, por_archivo


def main():
    p = argparse.ArgumentParser(description='分析越界 switch trap，为缺口补全提供依据')
    p.add_argument('--gen', default='generated/default', help='codegen 输出目录')
    p.add_argument('--salida', default='gap-analysis-result.json', help='JSON 输出路径')
    args = p.parse_args()

    if not os.path.isdir(args.gen):
        raise SystemExit('目录不存在: %s' % args.gen)

    traps, por_archivo = analizar(args.gen)

    # 按函数聚合
    por_funcion = {}
    for t in traps:
        key = t.get('function') or '(unknown)'
        por_funcion.setdefault(key, []).append(t)
    funciones = [{'address': a, 'traps': len(v)} for a, v in por_funcion.items()]
    funciones.sort(key=lambda x: x['traps'], reverse=True)

    # 不同的 switch 表达式（同类跳转表）
    exprs = sorted({t['switch_expr'] for t in traps if 'switch_expr' in t})

    # 与 codegen-result.json 核对
    esperado = None
    codegen_json = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'codegen-result.json')
    if os.path.exists(codegen_json):
        with open(codegen_json, encoding='utf-8') as fh:
            esperado = json.load(fh).get('trap_markers', {}).get(
                '__builtin_trap(); // Switch case out of range')

    report = {
        'trap_marker': MARKER,
        'total_traps': len(traps),
        'codegen_result_json_traps': esperado,
        'matches_codegen_result': esperado is None or esperado == len(traps),
        'files_with_traps': sorted(por_archivo),
        'distinct_switch_expressions': len(exprs),
        'functions': funciones,
        'sites': traps,
    }
    os.makedirs(os.path.dirname(args.salida) or '.', exist_ok=True)
    with open(args.salida, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    print('trap 总数            : %d' % len(traps))
    if esperado is not None:
        print('codegen-result.json  : %d  %s' % (
            esperado, '一致' if esperado == len(traps) else '** 不一致，请核查 **'))
    print('涉及文件             : %d' % len(por_archivo))
    print('不同 switch 表达式   : %d' % len(exprs))
    print()
    print('trap 最多的函数:')
    for f in funciones[:20]:
        print('  %s  %d 处' % (f['address'], f['traps']))
    print()
    print('不同的 switch 表达式（同类跳转表可批量判断）:')
    for e in exprs[:30]:
        print('  switch (%s)' % e)
    if len(exprs) > 30:
        print('  ... 以及另外 %d 个' % (len(exprs) - 30))
    print()
    print('完整逐条报告: %s' % args.salida)


if __name__ == '__main__':
    main()
