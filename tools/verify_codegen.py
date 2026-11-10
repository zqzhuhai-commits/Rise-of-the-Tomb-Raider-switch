"""Reject generated C++ functions with gotos to missing local labels."""
import argparse
import pathlib
import re
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gen', type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1]/'generated/default')
    args = parser.parse_args()
    paths = sorted(args.gen.glob('rottr_recomp.*.cpp'))
    if not paths:
        parser.error('No generated recompilation sources found')
    errors = []
    for path in paths:
        parts = re.split(r'DEFINE_REX_FUNC\((\w+)\)\s*\{', path.read_text(encoding='utf-8'))
        for index in range(1, len(parts), 2):
            name, body = parts[index:index+2]
            labels = set(re.findall(r'^\s*(loc_[0-9A-Fa-f]+):', body, re.M))
            jumps = set(re.findall(r'\bgoto\s+(loc_[0-9A-Fa-f]+)\s*;', body))
            for label in sorted(jumps-labels):
                errors.append(f'{path.name}: {name}: undefined label {label}')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        raise SystemExit(1)
    print(f'Local branch labels verified in {len(paths)} recompilation sources')


if __name__ == '__main__':
    main()
