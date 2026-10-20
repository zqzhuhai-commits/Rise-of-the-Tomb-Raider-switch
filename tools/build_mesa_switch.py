"""Build the pinned Horizon NVK driver; never substitute an empty driver archive."""
import os
import pathlib
import re
import shutil
import subprocess
import sys
from build_mesa_native import env, mesa, work

env = env.copy()
env.pop('LIBRARY_PATH', None)
dkp = work/'devkit-root/opt/devkitpro'
wrappers = work/'mesa-wrappers'
wrappers.mkdir(exist_ok=True)
for src, name in [('rustc-switch-wrapper.sh', 'rustc'), ('bindgen-switch-wrapper.sh', 'bindgen'),
                  ('bindgen-atomic-shim.h', 'bindgen-atomic-shim.h')]:
    target = wrappers/name
    shutil.copyfile(mesa/src, target)
    target.chmod(0o755 if name in ('rustc', 'bindgen') else 0o644)
cross = (mesa/'switch_cross_file.txt').read_text().replace('/opt/devkitpro', str(dkp))
cross = cross.replace('/usr/local/libexec/rustc', str(wrappers/'rustc'))
cross = cross.replace('/usr/local/libexec/bindgen', str(wrappers/'bindgen'))
cross_path = wrappers/'switch-cross.ini'
cross_path.write_text(cross)
env.update({'DEVKITPRO':str(dkp), 'MESA_SWITCH_RUST_TARGET':'aarch64-unknown-linux-gnu',
    'MESA_SWITCH_RUSTC':str(work/'rust/cargo/bin/rustc'),
    'MESA_SWITCH_BINDGEN':str(work/'rust-tools/bin/bindgen')})
env['PATH'] = os.pathsep.join(map(str, [mesa/'builddir-native/src/compiler/clc',
    mesa/'builddir-native/src/compiler/spirv'])) + os.pathsep + env['PATH']
# Relocate package metadata in the isolated devkitPro image, without changing
# system files. The Switch pkg-config wrapper uses these files for cross deps.
for path in (dkp/'portlibs/switch/lib/pkgconfig').glob('*.pc'):
    text = path.read_text()
    path.write_text(re.sub(r'(?<![\w./-])/opt/devkitpro', str(dkp), text))
shutil.copyfile(mesa/'src/nouveau/headers/nv_device_info.h', dkp/'portlibs/switch/include/nv_device_info.h')
# Rust's Linux std names these compatibility archives. Actual used symbols
# must still be supplied by Mesa's rust_switch_stubs.c or libnx; missing symbols
# remain link errors. This follows upstream's Horizon build procedure.
stub = wrappers/'posix_archive_marker.c'
stub.write_text('void __mesa_switch_link_compat_archive_marker(void) {}\n')
obj = wrappers/'posix_archive_marker.o'
cc = dkp/'devkitA64/bin/aarch64-none-elf-gcc'
ar = dkp/'devkitA64/bin/aarch64-none-elf-ar'
subprocess.run([str(cc), '-c', str(stub), '-o', str(obj)], env=env, check=True)
for name in ['dl', 'rt', 'util']:
    archive = dkp/f'portlibs/switch/lib/lib{name}.a'
    if not archive.exists(): subprocess.run([str(ar), 'rcs', str(archive), str(obj)], env=env, check=True)
build = mesa/'builddir-switch'
subprocess.run([sys.executable, '-m', 'mesonbuild.mesonmain', 'setup', str(build), str(mesa),
    '--cross-file', str(cross_path), '--buildtype=release', '-Doptimization=2', '-Db_lto=false',
    '-Db_ndebug=true', '-Dvulkan-drivers=nouveau', '-Dgallium-drivers=nouveau',
    '-Dshader-cache=enabled', '-Dgallium-rusticl=false', '-Dplatforms=switch', '-Dglx=disabled',
    '-Degl=disabled', '-Dopengl=false', '-Dgles1=disabled', '-Dgles2=disabled', '-Dllvm=disabled',
    '-Dshared-glapi=disabled', '-Dshared-llvm=disabled', '-Dmesa-clc=system',
    '-Dprecomp-compiler=system', '-Dcpp_rtti=false'], env=env, check=True)
subprocess.run([str(work/'build-tools/bin/ninja'), '-C', str(build), '-j', '6',
    'src/nouveau/vulkan/libvulkan.a', 'src/nouveau/compiler/libnak_rs.a'], env=env, check=True)
