"""Verify compiled ARM64 objects against the generated registration table."""
import json
import pathlib
import re
import struct
import subprocess

root = pathlib.Path(__file__).resolve().parents[1]
work = root.parent
objects = sorted((root/'build/guest-switch/CMakeFiles/rottr_guest.dir/generated/default').glob('*.obj'))
nm = work/'devkit-root/opt/devkitpro/devkitA64/bin/aarch64-none-elf-nm'
symbols = subprocess.check_output([str(nm), '--defined-only', '--format=posix',
    *map(str, objects)], text=True)
weak, implementations = {}, {}
for line in symbols.splitlines():
    fields = line.split()
    if len(fields) < 3: continue
    name, kind, address = fields[:3]
    if re.fullmatch(r'sub_[0-9A-Fa-f]+', name) and kind == 'W': weak[name] = address
    if re.fullmatch(r'__imp__sub_[0-9A-Fa-f]+', name): implementations[name[7:]] = address
table = (root/'generated/default/rottr_register.cpp').read_text()
expected = {name for name in re.findall(r'registrar->SetFunction\(0x[0-9A-Fa-f]+,\s*(\w+)\);', table)
    if name.startswith('sub_')}
missing = sorted(expected-weak.keys())
mismatches = sorted(name for name in weak if implementations.get(name) != weak[name])
elf_ok = True
for path in objects:
    header = path.read_bytes()[:64]
    elf_ok &= (header[:6] == b'\x7fELF\x02\x01' and
        struct.unpack_from('<H', header, 16)[0] == 1 and struct.unpack_from('<H', header, 18)[0] == 183)
report = {'compiled_cpp_objects': len(objects), 'expected_guest_entries': len(expected),
    'defined_weak_guest_entries': len(weak), 'missing_guest_aliases': missing,
    'alias_address_mismatches': mismatches, 'all_aarch64_elf64_relocatable': elf_ok,
    'compiler': 'devkitA64 GCC 15.2.0', 'runtime_linked': False, 'device_tested': False}
(root/'guest-build-result.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
assert len(objects) == 209 and elf_ok and not missing and not mismatches
