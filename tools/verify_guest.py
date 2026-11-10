"""Verify ARM64 guest objects and aliases; supports Windows devkitPro installs."""
import argparse
import json
import os
import pathlib
import re
import shutil
import struct
import subprocess


def main():
    root = pathlib.Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--objects', type=pathlib.Path, default=root/'build/guest-switch/CMakeFiles/rottr_guest.dir/generated/default')
    parser.add_argument('--nm', help='Path to aarch64-none-elf-nm')
    parser.add_argument('--compiler', help='Path to aarch64-none-elf-g++')
    parser.add_argument('--report', type=pathlib.Path, default=root/'guest-build-result.json')
    args = parser.parse_args()
    suffix = '.exe' if os.name == 'nt' else ''
    devkit = pathlib.Path(os.environ.get('DEVKITPRO', 'C:/devkitPro' if os.name == 'nt' else str(root.parent/'devkit-root/opt/devkitpro')))
    toolbin = devkit/'devkitA64/bin'
    nm = args.nm or shutil.which('aarch64-none-elf-nm') or str(toolbin/('aarch64-none-elf-nm'+suffix))
    compiler = args.compiler or str(pathlib.Path(nm).with_name('aarch64-none-elf-g++'+suffix))
    objects = sorted(args.objects.glob('*.obj'))
    if not objects:
        parser.error('No guest objects found: '+str(args.objects))
    weak, implementations = {}, {}
    # Batches keep command lines below Windows CreateProcess limits.
    for start in range(0, len(objects), 16):
        symbols = subprocess.check_output([nm, '--defined-only', '--format=posix', *map(str, objects[start:start+16])], text=True)
        for line in symbols.splitlines():
            fields = line.split()
            if len(fields) < 3:
                continue
            name, kind, address = fields[:3]
            if re.fullmatch(r'sub_[0-9A-Fa-f]+', name) and kind == 'W':
                weak[name] = address
            if re.fullmatch(r'__imp__sub_[0-9A-Fa-f]+', name):
                implementations[name[7:]] = address
    table = (root/'generated/default/rottr_register.cpp').read_text(encoding='utf-8')
    expected = {name for name in re.findall(r'registrar->SetFunction\(0x[0-9A-Fa-f]+,\s*(\w+)\);', table) if name.startswith('sub_')}
    missing = sorted(expected-weak.keys())
    mismatches = sorted(name for name in weak if implementations.get(name) != weak[name])
    invalid = []
    for path in objects:
        with path.open('rb') as file:
            header = file.read(64)
        if not (len(header) == 64 and header[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<H', header, 16)[0] == 1 and struct.unpack_from('<H', header, 18)[0] == 183):
            invalid.append(path.name)
    sources = list((root/'generated/default').glob('*.cpp'))
    report = dict(compiled_cpp_objects=len(objects), expected_cpp_objects=len(sources), expected_guest_entries=len(expected), defined_weak_guest_entries=len(weak), missing_guest_aliases=missing, alias_address_mismatches=mismatches, all_aarch64_elf64_relocatable=not invalid, invalid_objects=invalid, compiler=subprocess.check_output([compiler, '--version'], text=True).splitlines()[0], runtime_linked=False, device_tested=False)
    args.report.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    if not expected or len(objects) != len(sources) or invalid or missing or mismatches:
        raise SystemExit('Guest verification failed')


if __name__ == '__main__':
    main()
