#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检测生成代码中"读先于写"的非易失寄存器，为 share_registers 与分片函数提供依据。

与参考移植 StevensND/nfsmw-nx 的 tools/lee_antes.py 同逻辑（GPL-3.0）。

背景：codegen 把游戏函数翻译成 C++。默认每个 Xbox 360 寄存器都存在于 ctx 结构，
每次读写都是一次内存访问；把寄存器组提升为 C++ 局部变量（share_registers /
cr_as_local 等 codegen 选项）能大幅省 CPU——参考项目主线程约 14% 耗时来自
__savegprlr_29 / __restgprlr_29 两个 helper，改成局部变量后消失。

风险：提升为局部变量后，分片函数（主块跳入另一块）的 r14-r31 / cr / ctr / xer
不会跨块传递；hook 读取调用者寄存器的函数也会读到旧值。这些函数必须标记
share_registers。本工具找出所有"读先于写"的寄存器，即需要这些标记的候选。

用法：
    python3 tools/lee_antes.py [--gen generated/default] [--salida lee-antes-result.json]
"""
import argparse
import glob
import json
import os
import re
import sys

FN_RE = re.compile(r'^DEFINE_REX_FUNC\((sub_[0-9A-F]+)\)')
# 非易失寄存器：r14-r31、f14-f31、v14-v31 / v64-v127、cr0-7、ctr、xer
TOK = re.compile(r'(?<![.\w])(r(?:1[4-9]|2[0-9]|3[01])|f(?:1[4-9]|2[0-9]|3[01])'
                 r'|v(?:1[4-9]|2[0-9]|3[01]|6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])'
                 r'|cr[0-7]|ctr|xer)\b')
ASG = re.compile(r'^([A-Za-z0-9_]+)(?:\.[A-Za-z0-9_\[\]]+)*\s*=[^=]')


def analizar(gen_dir):
    """返回 {函数名: {'registers': [r31, ...], 'sample': '首条触发行'}}。"""
    res = {}
    for f in sorted(glob.glob(os.path.join(gen_dir, 'rottr_recomp.*.cpp'))):
        cur = None
        for ln in open(f, encoding='utf-8', errors='ignore'):
            m = FN_RE.match(ln)
            if m:
                cur = m.group(1)
                written = set()
                bad = {}
                continue
            if cur is None:
                continue
            if ln.startswith('}'):
                if bad:
                    res[cur] = bad
                cur = None
                continue
            s = ln.strip()
            if not s or s.startswith('//') or s.startswith('PPC') \
                    or s.startswith('uint') or s.startswith('REX_FUNC_PROLOGUE'):
                continue
            # 函数序言的寄存器保存（写入 ctx.r1 栈区）不视为"写寄存器"
            if s.startswith('REX_STORE') \
                    and re.search(r',\s*(r|f)\d+\.(u64|f64)\);$', s) \
                    and 'ctx.r1.' in s:
                continue
            s2 = re.sub(r'compare<[^>]*>\([^;]*,\s*xer\)', '', s)
            s2 = re.sub(r'cr\d\.so = xer\.so;', '', s2)
            # crN.compare(...)：crN 是目标（写），其余为读
            mc = re.match(r'^(cr[0-7])\.compare', s)
            if mc:
                for r in TOK.findall(re.sub(r',\s*xer\)', ')', s[len(mc.group(1)):])):
                    if r not in written and r not in bad:
                        bad[r] = s[:100]
                written.add(mc.group(1))
                continue
            # simde_mm_store*(vN.xxx, ...)：vN 是目标（写），RHS 为读
            ms = re.match(r'^simde_mm_store\w*\(\(?(?:simde__m128i\*\))?(v\d+)\.\w+,(.*)$', s2)
            if ms:
                for r in TOK.findall(ms.group(2)):
                    if r not in written and r not in bad:
                        bad[r] = s[:100]
                written.add(ms.group(1))
                continue
            m2 = ASG.match(s2)
            lhs = None
            rhs = s2
            if m2:
                lhs = m2.group(1)
                rhs = s2[m2.end() - 1:]
            for r in TOK.findall(rhs):
                if r not in written and r not in bad:
                    bad[r] = s[:100]
            if lhs and TOK.fullmatch(lhs):
                written.add(lhs)
    return res


def main():
    p = argparse.ArgumentParser(description='检测生成代码中读先于写的非易失寄存器')
    p.add_argument('--gen', default='generated/default', help='codegen 输出目录')
    p.add_argument('--salida', default='lee-antes-result.json', help='JSON 输出路径')
    args = p.parse_args()

    if not os.path.isdir(args.gen):
        raise SystemExit('目录不存在: %s' % args.gen)

    res = analizar(args.gen)
    report = {
        'tool': 'lee_antes (register read-before-write)',
        'source': 'reference nfsmw-nx tools/lee_antes.py (GPL-3.0)',
        'total_functions_with_read_before_write': len(res),
        'functions': [{'name': n, 'registers': sorted(v), 'sample': next(iter(v.values()))}
                      for n, v in res.items()],
    }
    os.makedirs(os.path.dirname(args.salida) or '.', exist_ok=True)
    with open(args.salida, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    print('读先于写且需标记 share_registers 的函数数: %d' % len(res))
    for n, v in sorted(res.items()):
        print('  %s  %s  |  %s' % (n, ' '.join(sorted(v)), list(v.values())[0]))
    print()
    print('完整报告: %s' % args.salida)


if __name__ == '__main__':
    main()
