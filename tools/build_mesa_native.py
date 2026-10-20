"""Configure and build Mesa's real native shader-generation tools locally."""
import os
import pathlib
import subprocess
import sys

work = pathlib.Path(__file__).resolve().parents[2]
host = work/'host-deps'
mesa = work/'mesa-switch-review'
native = work/'native-prefix'
# Mesa's runtime OpenCL include lookup uses the LLVM major version; Ubuntu's
# LLVM 15 package stores the actual headers under the complete version.
resource_root = host/'usr/lib/llvm-15/lib/clang'
major_resource = resource_root/'15'
if not major_resource.exists():
    candidates = sorted(resource_root.glob('15.*'))
    if len(candidates) == 1:
        major_resource.symlink_to(candidates[0].name, target_is_directory=True)
env = os.environ.copy()
env.update({
    'PYTHONPATH': str(work/'build-tools'),
    'LD_LIBRARY_PATH': str(host/'usr/lib/x86_64-linux-gnu'),
    'LIBRARY_PATH': os.pathsep.join([str(host/'usr/lib/x86_64-linux-gnu'), str(host/'usr/lib')]),
    'PKG_CONFIG_PATH': os.pathsep.join([str(native/'lib/pkgconfig'), str(host/'usr/lib/x86_64-linux-gnu/pkgconfig')]),
    'PKG_CONFIG': str(host/'usr/bin/pkgconf'),
    'LLVM_CONFIG': str(host/'usr/lib/llvm-15/bin/llvm-config'),
    'CC': str(host/'usr/lib/llvm-15/bin/clang'),
    'CXX': str(host/'usr/lib/llvm-15/bin/clang++'),
    'BISON_PKGDATADIR': str(host/'usr/share/bison'),
    'CARGO_HOME': str(work/'rust/cargo'),
    'RUSTUP_HOME': str(work/'rust/rustup'),
    'LIBCLANG_PATH': str(host/'usr/lib/llvm-15/lib'),
})
env['PATH'] = os.pathsep.join(map(str, [host/'usr/lib/llvm-15/bin', host/'usr/bin',
    work/'build-tools/bin', work/'build-tools/cmake/data/bin', work/'rust/cargo/bin',
    work/'rust-tools/bin'])) + os.pathsep + env['PATH']
# Package metadata was extracted rather than installed into /usr.
for path in (host/'usr').rglob('*.pc'):
    text = path.read_text()
    if '/workspace/' not in text:
        path.write_text(text.replace('/usr', str(host/'usr')))
setup = [sys.executable, '-m', 'mesonbuild.mesonmain', 'setup', str(mesa/'builddir-native'), str(mesa),
    '-Dvulkan-drivers=', '-Dgallium-drivers=', '-Dshader-cache=true', '-Dplatforms=',
    '-Dglx=disabled', '-Degl=disabled', '-Dopengl=false', '-Dgles1=disabled', '-Dgles2=disabled',
    '-Dtools=[]', '-Dllvm=enabled', '-Dmesa-clc=enabled', '-Dprecomp-compiler=enabled', '-Dinstall-mesa-clc=true']
if __name__ == '__main__':
    subprocess.run(setup, env=env, check=True)
    subprocess.run([str(work/'build-tools/bin/ninja'), '-C', str(mesa/'builddir-native'), '-j', '8',
        'src/compiler/clc/mesa_clc', 'src/compiler/spirv/vtn_bindgen2'], env=env, check=True)
