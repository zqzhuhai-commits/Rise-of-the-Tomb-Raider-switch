"""Verify a homebrew NRO container and its embedded application metadata."""
import argparse
import hashlib
import json
import pathlib
import struct


def verify(path):
    size = path.stat().st_size
    with path.open('rb') as file:
        header = file.read(0x80)
        if len(header) != 0x80 or header[0x10:0x14] != b'NRO0':
            raise ValueError('Missing NRO0 header')
        nro_size = struct.unpack_from('<I', header, 0x18)[0]
        if not 0x80 <= nro_size <= size:
            raise ValueError('Invalid NRO image size')
        segments = []
        for name, offset in [('text', 0x20), ('rodata', 0x28), ('data', 0x30)]:
            start, length = struct.unpack_from('<II', header, offset)
            if start % 0x1000 or length % 0x1000 or start+length > nro_size:
                raise ValueError('Invalid segment: '+name)
            segments.append(dict(name=name, offset=start, size=length))
        for first, second in zip(segments, segments[1:]):
            if first['offset']+first['size'] > second['offset']:
                raise ValueError('Overlapping NRO segments')
        file.seek(nro_size)
        asset = file.read(56)
        if len(asset) != 56 or asset[:4] != b'ASET':
            raise ValueError('Missing NRO asset header')
        sections = {}
        for name, offset in [('icon', 8), ('nacp', 24), ('romfs', 40)]:
            start, length = struct.unpack_from('<QQ', asset, offset)
            if length and (start < 56 or nro_size+start+length > size):
                raise ValueError('Invalid asset: '+name)
            sections[name] = dict(offset=start, size=length)
        nacp = sections['nacp']
        if nacp['size'] != 0x4000:
            raise ValueError('Invalid NACP size')
        file.seek(nro_size+nacp['offset'])
        metadata = file.read(nacp['size'])
        title = metadata[:0x200].split(b'\0',1)[0].decode('utf-8')
        version = metadata[0x3060:0x3070].split(b'\0',1)[0].decode('utf-8')
    digest = hashlib.sha256()
    with path.open('rb') as file:
        while True:
            chunk = file.read(4*1024*1024)
            if not chunk:
                break
            digest.update(chunk)
    return dict(format='NRO0', file_bytes=size, nro_image_bytes=nro_size, sha256=digest.hexdigest(), segments=segments, segments_valid=True, bss_size=struct.unpack_from('<I',header,0x38)[0], assets=sections, nacp_title=title, nacp_version=version, runtime_linked=True, device_tested=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('nro', type=pathlib.Path)
    parser.add_argument('--report', type=pathlib.Path)
    args = parser.parse_args()
    report = verify(args.nro)
    if args.report:
        args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
