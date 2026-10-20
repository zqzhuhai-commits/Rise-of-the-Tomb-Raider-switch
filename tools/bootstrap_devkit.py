"""Fetch the official devkitPro AMD64 toolchain image, extracting only /opt/devkitpro."""
import hashlib, json, pathlib, tarfile, urllib.request

REPO = 'devkitpro/devkita64'
DIGEST = 'sha256:82575ea78651b530b2e232bb3799cfd1fe331514e053d5f724bb4b28191fb79d'
ROOT = pathlib.Path(__file__).resolve().parents[2] / 'devkit-root'
CACHE = pathlib.Path(__file__).resolve().parents[2] / 'toolchain-downloads'
CACHE.mkdir(exist_ok=True)

def get(url, token=None, accept=None):
    headers = {}
    if token: headers['Authorization'] = 'Bearer ' + token
    if accept: headers['Accept'] = accept
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=45)

token = json.load(get(f'https://auth.docker.io/token?service=registry.docker.io&scope=repository:{REPO}:pull'))['token']
manifest = json.load(get(f'https://registry-1.docker.io/v2/{REPO}/manifests/{DIGEST}', token,
    'application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json'))
(CACHE/'manifest.json').write_text(json.dumps(manifest, indent=2))
for i, layer in enumerate(manifest['layers']):
    path = CACHE / (layer['digest'].replace(':', '-') + '.tgz')
    if not path.exists() or path.stat().st_size != layer['size']:
        print('Downloading layer', i, 'MiB', round(layer['size']/2**20), flush=True)
        with get(f'https://registry-1.docker.io/v2/{REPO}/blobs/{layer["digest"]}', token) as src, path.open('wb') as dst:
            while block := src.read(4*1024*1024): dst.write(block)
    h = hashlib.sha256()
    with path.open('rb') as src:
        while block := src.read(4*1024*1024): h.update(block)
    assert 'sha256:'+h.hexdigest() == layer['digest'], 'Layer checksum mismatch'
    count = 0
    with tarfile.open(path) as archive:
        for member in archive:
            name = member.name.removeprefix('./')
            if not name.startswith('opt/devkitpro/') or '/.wh.' in name: continue
            if not (member.isfile() or member.isdir() or member.issym() or member.islnk()): continue
            archive.extract(member, ROOT, filter='data')
            count += 1
    print('Layer', i, 'verified; toolchain entries', count, flush=True)
print('DEVKITPRO', (ROOT/'opt/devkitpro').resolve(), flush=True)
