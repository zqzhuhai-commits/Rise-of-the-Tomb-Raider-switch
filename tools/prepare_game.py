"""Extract the matching base game from an Xbox 360 GOD ZIP or Data directory.

Usage: python prepare_game.py gmly.zip --output /path/to/SD/switch/rottr-switch/game
For an extracted GOD, pass the directory containing Data0000 instead of gmly.zip.
Only standard Python modules are required. Does not apply title updates or DLC.
"""
import argparse
import hashlib
import pathlib
import struct
import zipfile

EXPECTED_XEX = '47e6476f6d393d86612e7af938979e9c706b54dc526d8422413711999d41e585'
PART_BYTES = 203 * 204 * 4096
GROUP_BYTES = 204 * 4096


class GodArchive:
    def __init__(self, archive):
        archive = pathlib.Path(archive)
        self.zip = None
        self.data_directory = None
        if archive.is_dir():
            # Prefer the exact selected Data directory; otherwise find one below it.
            if (archive / 'Data0000').is_file():
                candidates = [archive]
            else:
                candidates = sorted({p.parent for p in archive.rglob('Data0000') if p.is_file()})
            if not candidates:
                raise ValueError('No Data0000 found. Select the folder containing the GOD Data files.')
            if len(candidates) != 1:
                raise ValueError('Multiple GOD data folders found. Select the exact folder containing the main game Data0000.')
            self.data_directory = candidates[0]
            self.prefix = ''
        else:
            self.zip = zipfile.ZipFile(archive)
            parts = sorted(name for name in self.zip.namelist()
                if '/53510823/00007000/' in name and '.data/Data' in name)
            if not parts:
                self.zip.close()
                raise ValueError('Matching Rise of the Tomb Raider GOD data not found')
            self.prefix = parts[0].rsplit('/', 1)[0]
        self.cache_key = None
        self.cache = b''

    def read(self, offset, length):
        result = bytearray()
        while length:
            part, local = divmod(offset, PART_BYTES)
            group, inside = divmod(local, GROUP_BYTES)
            key = self.prefix + '/Data%04d' % part
            if key != self.cache_key:
                if self.data_directory is not None:
                    part_path = self.data_directory / ('Data%04d' % part)
                    if not part_path.is_file():
                        raise FileNotFoundError('Missing GOD data part: ' + str(part_path))
                    self.cache = part_path.read_bytes()
                else:
                    self.cache = self.zip.read(key)  # validates this ZIP entry's CRC
                self.cache_key = key
            count = min(length, GROUP_BYTES-inside, PART_BYTES-local)
            position = 8192 + group*(GROUP_BYTES+4096) + inside
            block = self.cache[position:position+count]
            if len(block) != count: raise ValueError('Truncated GOD data')
            result.extend(block)
            offset += count
            length -= count
        return bytes(result)

    def files(self):
        volume = self.read(0x10000, 36)
        if volume[:20] != b'MICROSOFT*XBOX*MEDIA': raise ValueError('Invalid GOD filesystem')
        sector, size = struct.unpack_from('<II', volume, 20)
        result, visited = [], set()

        def directory(sector, size, prefix='', depth=0):
            if depth > 32 or size > 32*1024*1024 or (sector, size) in visited:
                raise ValueError('Invalid directory tree')
            visited.add((sector, size))
            raw = self.read(sector*2048, size)
            seen = set()

            def node(pos):
                if pos in seen or pos+14 > len(raw): raise ValueError('Invalid directory node')
                seen.add(pos)
                left, right, sec, length, flags, nl = struct.unpack_from('<HHIIBB', raw, pos)
                if left == 65535 or right == 65535: return
                if pos+14+nl > len(raw): raise ValueError('Truncated filename')
                name = raw[pos+14:pos+14+nl].decode('utf-8')
                if name in ('', '.', '..') or '/' in name or '\\' in name:
                    raise ValueError('Unsafe filename')
                if left: node(left*4)
                path = prefix+name
                if flags & 16: directory(sec, length, path+'/', depth+1)
                else: result.append({'path':path, 'sector':sec, 'size':length})
                if right: node(right*4)
            if size: node(0)

        directory(sector, size)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=pathlib.Path, help='Original GOD ZIP or directory containing Data0000')
    parser.add_argument('--output', required=True, type=pathlib.Path)
    parser.add_argument('--only-default', action='store_true', help='Extract only the executable for verification')
    args = parser.parse_args()
    god = GodArchive(args.archive)
    files = god.files()
    executable = next(f for f in files if f['path'].lower() == 'default.xex')
    digest = hashlib.sha256(god.read(executable['sector']*2048, executable['size'])).hexdigest()
    if digest != EXPECTED_XEX: raise ValueError('This executable differs from the analyzed base version: '+digest)
    selected = [f for f in files if not f['path'].lower().startswith('$systemupdate/')
        and (not args.only_default or f is executable)]
    output = args.output.resolve()
    for f in selected:
        if (output/f['path']).exists(): raise FileExistsError(str(output/f['path']))
    output.mkdir(parents=True, exist_ok=True)
    for f in sorted(selected, key=lambda item:item['sector']):
        target = output/f['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        position, remaining = f['sector']*2048, f['size']
        with target.open('xb') as dst:
            while remaining:
                count = min(4*1024*1024, remaining)
                dst.write(god.read(position, count))
                position += count
                remaining -= count
        print(f['path'], f['size'], flush=True)
    print('Complete:', len(selected), 'files; base executable SHA-256:', digest, flush=True)


if __name__ == '__main__': main()
