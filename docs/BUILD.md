# 构建检查点与重建说明

此文记录 2026-10-20 的成功构建环境。现有辅助脚本沿用隔离 Linux AMD64 工作目录布局；主机依赖准备尚未完全自动化，也没有进行全新环境的一键重建测试。

## 目录布局

```text
work/
  Rise-of-the-Tomb-Raider-switch/
  rexglue-sdk-linux/linux-amd64/
  masseffect-nx-review/sdk/
  prototype-switch-review/
  mesa-switch-review/
  devkit-root/opt/devkitpro/
  build-tools/
  host-deps/
  native-prefix/
  rust/
  rust-tools/
```

依赖提交及补丁 SHA-256 以根目录 `dependencies.lock.json` 为准。不要直接使用 SDK 或 Mesa 的最新提交代替固定版本。

1. 获取固定提交的三个源码仓库。将参考端口的 `patches/rexglue-sdk-masseffect-nx.patch` 应用到 `masseffect-nx-review` 仓库根目录；将 `patches/mesa-switch.patch` 应用到 `mesa-switch-review` 根目录。应用前核对锁文件中的补丁哈希。
2. 运行 SDK 仓库中的 `tools/fetch_thirdparty.py` 准备第三方源码；检查该工具所用依赖与 ReXGlue v0.10.0 一致。运行 `python3 tools/prepare_sdk.py ../masseffect-nx-review/sdk` 启用 Switch FFmpeg 配置。
3. 运行 `python3 tools/bootstrap_devkit.py`，从固定官方 AMD64 镜像提取工具链到同级 `devkit-root`。需要 Python 3.12+ 的 tar 数据过滤支持及 Docker Registry 网络访问；脚本会下载并验证镜像层。
4. 从 ReXGlue 官方 v0.10.0 发布包准备 Linux AMD64 代码生成器和第三方头文件。主机工具链使用 CMake 4.4.4、Ninja 1.13.2、Meson 1.12.1、Mako 1.4.3、PyYAML 6.0.3、packaging 26.3；辅助脚本默认从同级 `build-tools` 读取，可通过 `ROTTR_CMAKE`、`ROTTR_NINJA` 覆盖 shell 脚本中的可执行路径。
5. 从自己的匹配 GOD ZIP 提取程序：

   ```sh
   python3 tools/prepare_game.py /path/gmly.zip --output /path/extracted-game --only-default
   cp /path/extracted-game/default.xex ./default.xex
   ```

   期望 SHA-256：`47e6476f6d393d86612e7af938979e9c706b54dc526d8422413711999d41e585`。仅匹配基础版本；不是 TU4 主程序。
6. 在仓库根目录使用 v0.10.0 代码生成器的 `codegen` 命令，输入 `rottr_manifest.toml`；具体命令参数以该发布包 `--help` 为准。输出必须位于 `generated/default/`，并包含 `sources.cmake`。运行 `sh build_guest.sh`，脚本会先修正 `dcbz` 翻译，再编译 CPU 对象。完成后运行 `python3 tools/verify_guest.py`，检查 209 个 ARM64 对象和函数别名。验证脚本使用上述默认 devkitPro 布局。
7. 准备真正的 NVK 静态库，见下节。设置 `ROTTR_NVK_SDK` 指向包含 `lib/libvulkan.a` 的 SDK 目录，然后运行 `sh build_runtime.sh`。该脚本复用 CPU 编译对象，并启用完整 Horizon 运行层链接；NRO 位于 `build/runtime-switch/` 构建树。

可覆盖变量：`DEVKITPRO`、`ROTTR_SDK_SOURCE`、`ROTTR_DEPS_INCLUDE`、`ROTTR_GUEST_OBJECTS_DIR`、`ROTTR_JOBS`。这些覆盖适用于 shell 构建入口；Mesa 辅助脚本仍依赖上面的目录布局。

## NVK 构建环境

成功检查点使用隔离提取的 Ubuntu 24.04 包、Clang / LLVM 15.0.7、libLLVMSPIRVLib15、libclc15、flex、bison、pkgconf；SPIRV-Tools `vulkan-sdk-1.3.290.0` 安装到 `native-prefix`；Rust `nightly-2026-09-26`，安装 rust-src、rustfmt 和 aarch64-unknown-linux-gnu 标准库；bindgen-cli 0.73.0、cbindgen 0.29.0。

`tools/build_mesa_native.py` 和 `tools/build_mesa_switch.py` 记录主机 shader 工具及 Horizon 驱动的实际构建配置，需要先手动准备这些主机依赖。依次运行：

```sh
python3 tools/build_mesa_native.py
python3 tools/build_mesa_switch.py
```

静态库输出为 `../mesa-switch-review/builddir-switch/src/nouveau/vulkan/libvulkan.a`。创建单独 SDK 目录，将其放在 `lib/libvulkan.a`，Vulkan 头文件取自固定 Mesa 源码的 `include`；通过 `ROTTR_NVK_SDK` 指定该 SDK 目录。不能用空库代替驱动。

## NSP 转发器

检查点使用 Forwarder-Mod 提交 `9853bd9167d5a7f0c5fdf935864245c1fbcf8282`，以及参考端口同提交版本的 NSP 容器构建工具。对该转发器将声明 `void NORETURN nroEntrypointTrampoline` 改为 `void __attribute__((noreturn)) nroEntrypointTrampoline`，以适配当前 libnx。

打包参数：标题 ID `01524F5454520000`、版本 `0.0.1-test`、标题 `Rise of the Tomb Raider TEST`、目标 `sdmc:/switch/rottr-switch/rottr.nro`；使用完整应用内存配置。NSP 构建入口尚未整理成本仓库自动脚本，需按上游工具说明自行构建，并在本地提供其所需密钥。NSP 仅为 NRO 入口，不包含游戏。

## 已生成文件的检查点哈希

| 文件 | 字节数 | SHA-256 |
|---|---:|---|
| rottr.nro | 78,637,253 | `40757983a60c265a0b20578a7d3fd7791883aa0504760e4819ef470ad64f360f` |
| ROTTR-Switch-TEST.nsp | 342,744 | `aa4fb3f279fc0665fd3e60b988aee5a81d0eb64b07ec3c761a39143de6e2bc88` |

这些值用于识别已有私有构建；本仓库不包含对应二进制。链接和文件结构检查通过不代表 Switch 已能运行游戏。

## 优化选项（可选，参考移植 nfsmw 的已验证做法）

默认构建不启用以下优化，行为与历史检查点一致。启用时 `build_guest.sh` 与 `build_runtime.sh` 必须传相同值。

### 直接调用（自动执行）
`build_guest.sh` / `build_pc.sh` 会在 `prepare_codegen.py` 之后自动运行 `tools/direct_calls.py`，把没有 hook 的游戏函数调用 `sub_X(ctx, base)` 改写为 `__imp__sub_X(ctx, base)`，使编译器能跨文件内联（LTO 前提）。幂等；每次 codegen 后必须重跑（脚本已自动做）。若需还原：`python3 tools/direct_calls.py --deshacer`。

### LTO
```sh
ROTTR_LTO=ON sh build_guest.sh
ROTTR_LTO=ON sh build_runtime.sh
```
对重编译代码与应用一起做 `-flto=2 -flto-partition=balanced` 链接期优化。注意内存占用大（参考项目约 16 GB 可跑）。

### PGO（两段式）
```sh
# 1) 插桩构建（记录 profile；NRO 每 3 分钟把 .gcda 落盘到
#    sdmc:/switch/rottr-switch/pgo/，src/rottr_pgo.cpp 负责）
ROTTR_PGO=generar sh build_guest.sh
ROTTR_PGO=generar sh build_runtime.sh
# 2) 实机游玩一段（菜单、流程、视频各模式都跑到），把 SD 卡
#    sdmc:/switch/rottr-switch/pgo/ 下的 .gcda 拷到编译机 ROTTR_PGO_DIR
#    （默认 work/pgo/）后重编译
ROTTR_PGO=usar sh build_guest.sh
ROTTR_PGO=usar sh build_runtime.sh
```
两个必须的坑（参考项目逐个踩过）：`-fno-profile-values`（libnx 不用 `tpidr_el0`，间接调用插桩启动即崩）与 `-fprofile-correction`（多线程累加计数器为负，GCC 视为损坏 profile）。两次构建必须使用同一份生成代码/源码与同一构建目录路径。

### 构建脚本新增覆盖变量
`ROTTR_LTO`、`ROTTR_PGO`（见上），沿用既有 `ROTTR_*` 覆盖惯例。
