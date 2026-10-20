"""Correct the Xbox 360 cache-line size in ReXGlue v0.10.0 output.

The same correction is used by fungalspores/prototype-switch. Do not copy its
game-address hooks or performance shortcuts: they have not been checked here.
"""
import pathlib
import re

root = pathlib.Path(__file__).resolve().parents[1] / 'generated/default'
pattern = re.compile(
    r'(// dcbz [^\n]*\n\s*ea = [^\n;]*& )~31;'
    r'(\n\s*memset\(\(void\*\)REX_RAW_ADDR\(ea\), 0, )32\);')
total = 0
for path in sorted(root.glob('rottr_recomp.*.cpp')):
    text = path.read_text()
    fixed, count = pattern.subn(r'\1~127;\g<2>128);', text)
    if count:
        path.write_text(fixed)
        total += count
print('Updated dcbz cache-line translations:', total)
