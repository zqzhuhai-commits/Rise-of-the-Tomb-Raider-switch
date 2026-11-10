"""Materialize C/C++ vendor symlinks checked out as path text on Windows."""
import argparse
import pathlib
import re
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('thirdparty', type=pathlib.Path)
    args = parser.parse_args()
    root = args.thirdparty.resolve()
    count = 0
    for path in root.rglob('*'):
        if path.is_symlink() or path.suffix not in {'.c', '.h', '.cc', '.cpp', '.hpp', '.S'} or not path.is_file() or not 0 < path.stat().st_size < 512:
            continue
        text = path.read_text(encoding='utf-8', errors='replace').strip()
        if not re.fullmatch(r'(?:\.\.?/)+[A-Za-z0-9_./+-]+', text):
            continue
        target = (path.parent/text).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            raise ValueError('Vendor link leaves third-party directory: '+str(path))
        if not target.is_file():
            raise FileNotFoundError(str(target))
        shutil.copyfile(target, path)
        count += 1
        print('Materialized:', path.relative_to(root))
    print('Vendor source links repaired:', count)


if __name__ == '__main__':
    main()
