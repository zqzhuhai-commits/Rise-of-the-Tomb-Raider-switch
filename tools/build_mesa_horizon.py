"""Build Horizon NVK with explicit, relocatable dependency paths (Linux/WSL)."""
import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['mesa', 'build', 'devkitpro', 'native-build', 'cargo-home', 'rustup-home', 'rust-tools']:
        parser.add_argument('--'+name, type=pathlib.Path, required=True)
    parser.add_argument('--host-prefix', type=pathlib.Path)
    parser.add_argument('--jobs', type=int, default=6)
    args = parser.parse_args()
    mesa, build, dkp = args.mesa.resolve(), args.build.resolve(), args.devkitpro.resolve()
    wrappers = build.parent/'mesa-wrappers'
    wrappers.mkdir(parents=True, exist_ok=True)
    for source, name in [('rustc-switch-wrapper.sh', 'rustc'), ('bindgen-switch-wrapper.sh', 'bindgen'), ('bindgen-atomic-shim.h', 'bindgen-atomic-shim.h')]:
        target = wrappers/name
        shutil.copyfile(mesa/source, target)
        if name == 'rustc':
            # Meson 1.10 names its native sanity probe sanity.rs. Keep real
            # driver Rust compilation on the ARM64 target.
            text = target.read_text()
            text = text.replace('*sanity_check_for_rust.rs*|*sanitycheckrs.rs*)', '*sanity_check_for_rust.rs*|*sanitycheckrs.rs*|*/sanity.rs)')
            target.write_text(text)
        target.chmod(0o755 if name != 'bindgen-atomic-shim.h' else 0o644)
    cross = (mesa/'switch_cross_file.txt').read_text()
    cross = cross.replace('/opt/devkitpro', str(dkp)).replace('/usr/local/libexec/rustc', str(wrappers/'rustc')).replace('/usr/local/libexec/bindgen', str(wrappers/'bindgen'))
    cross_path = wrappers/'switch-cross.ini'
    cross_path.write_text(cross)
    env = os.environ.copy()
    env.update(DEVKITPRO=str(dkp), CARGO_HOME=str(args.cargo_home.resolve()), RUSTUP_HOME=str(args.rustup_home.resolve()), MESA_SWITCH_RUST_TARGET='aarch64-unknown-linux-gnu', MESA_SWITCH_RUSTC=str(args.cargo_home.resolve()/'bin/rustc'), MESA_SWITCH_BINDGEN=str(args.rust_tools.resolve()/'bin/bindgen'))
    tools = [args.native_build.resolve()/'src/compiler/clc', args.native_build.resolve()/'src/compiler/spirv', args.rust_tools.resolve()/'bin', args.cargo_home.resolve()/'bin']
    if args.host_prefix:
        tools.insert(0, args.host_prefix.resolve()/'usr/bin')
        env['LD_LIBRARY_PATH'] = str(args.host_prefix.resolve()/'usr/lib/x86_64-linux-gnu')
    env['PATH'] = os.pathsep.join(map(str, tools))+os.pathsep+env['PATH']
    env.pop('LIBRARY_PATH', None)
    for path in (dkp/'portlibs/switch/lib/pkgconfig').glob('*.pc'):
        text = path.read_text()
        path.write_text(re.sub(r'(?<![\w./-])/opt/devkitpro', str(dkp), text))
    shutil.copyfile(mesa/'src/nouveau/headers/nv_device_info.h', dkp/'portlibs/switch/include/nv_device_info.h')
    # Compatibility archive markers only. Used POSIX symbols still must resolve
    # from Mesa's real Switch implementations or libnx at final link.
    marker = wrappers/'posix_archive_marker.c'
    marker.write_text('void __mesa_switch_link_compat_archive_marker(void) {}\n')
    obj = wrappers/'posix_archive_marker.o'
    subprocess.run([str(dkp/'devkitA64/bin/aarch64-none-elf-gcc'), '-c', str(marker), '-o', str(obj)], env=env, check=True)
    for name in ['dl', 'rt', 'util']:
        archive = dkp/f'portlibs/switch/lib/lib{name}.a'
        if not archive.exists():
            subprocess.run([str(dkp/'devkitA64/bin/aarch64-none-elf-ar'), 'rcs', str(archive), str(obj)], env=env, check=True)
    command = [sys.executable, '-m', 'mesonbuild.mesonmain', 'setup', str(build), str(mesa), '--cross-file', str(cross_path), '--buildtype=release', '-Doptimization=2', '-Db_lto=false', '-Db_ndebug=true', '-Dvulkan-drivers=nouveau', '-Dgallium-drivers=nouveau', '-Dshader-cache=enabled', '-Dgallium-rusticl=false', '-Dplatforms=switch', '-Dglx=disabled', '-Degl=disabled', '-Dopengl=false', '-Dgles1=disabled', '-Dgles2=disabled', '-Dllvm=disabled', '-Dshared-glapi=disabled', '-Dshared-llvm=disabled', '-Dmesa-clc=system', '-Dprecomp-compiler=system', '-Dcpp_rtti=false']
    subprocess.run(command, env=env, check=True)
    subprocess.run(['ninja', '-C', str(build), '-j', str(args.jobs), 'src/nouveau/vulkan/libvulkan.a', 'src/nouveau/compiler/libnak_rs.a'], env=env, check=True)


if __name__ == '__main__':
    main()
