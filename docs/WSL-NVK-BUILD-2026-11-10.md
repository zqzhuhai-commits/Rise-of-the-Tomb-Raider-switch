# WSL / Horizon NVK 构建进度（2026-11-10）

已在本机重新构建真实 NVK 静态驱动，不再停留在缺少 Rust 工具链的阶段。

| 项目 | 本次结果 |
|---|---|
| Mesa | 固定提交 `d4a00ea0ab3f59afb967cc5d779e4263d237bd77`，26.2.3，应用锁定参考补丁 |
| Linux 交叉编译器 | 官方锁定镜像中的 devkitA64 GCC 15.2.0 |
| Rust | nightly-2026-09-26 / 1.100.0-nightly |
| 绑定工具 | bindgen 0.73.0、cbindgen 0.29.0 |
| 主机工具 | LLVM/Clang 21.1.8，`mesa_clc`、`vtn_bindgen2` 已实际编译和链接；mesa_clc 可启动 |
| libvulkan.a | 89,625,370 字节；1,545 个成员全部为 AArch64 ELF64，无非 ELF 成员 |
| 驱动 SHA-256 | `e57873077a9429b29b6956fca965c934b51208ac61ba11400f75df9e8ad4ee2c` |

结构化结果见 `mesa-wsl-result.json`。驱动构建通过不代表游戏或驱动已在 Switch 实机运行。

## 工具链与目录

WSL 直接访问 Docker Registry 在本机失败，Windows HTTP 通道可用。
新增 `tools/download_devkit_layers.ps1 -CacheRoot <缓存目录>`，读取固定镜像清单、下载
层文件并逐层校验 SHA-256；随后可在 WSL 中运行：

```sh
python3 tools/bootstrap_devkit.py --offline --root /var/tmp/rottr-devkit --cache /path/to/toolchain-downloads
```

`bootstrap_devkit.py` 新增 `--root`、`--cache` 和 `--offline`，默认行为保持不变。
本机 `/tmp` 是 tmpfs，WSL 重启会清空，不能用它保存后续阶段要复用的工具链。
下载缓存、Rust 和主要构建输出保存在 E 盘；工具链放在 WSL 的持久 `/var/tmp`。

主机 shader 工具本次使用隔离解压的 Ubuntu 26.04 开发包（LLVM 21、Clang、libclc、
SPIRV-Tools、LLVM-SPIRV、zlib、zstd、expat、libdrm）。需要把 pkg-config 元数据和
llvm-config 与开发文件一起重定位，并提供同版本 Clang resource headers；主机依赖
准备仍是手动步骤，尚不是全新机器的一键安装流程。

## NVK 构建入口

新增 `tools/build_mesa_horizon.py`，在 Linux/WSL 中使用显式路径：

```sh
python3 tools/build_mesa_horizon.py \
  --mesa /path/to/patched-mesa --build /path/to/mesa-switch \
  --devkitpro /var/tmp/rottr-devkit/opt/devkitpro \
  --native-build /path/to/mesa-native \
  --cargo-home /path/to/rust/cargo --rustup-home /path/to/rust/rustup \
  --rust-tools /path/to/rust-tools --host-prefix /path/to/host-deps --jobs 6
```

入口会生成本地 cross file 和包装器。对 Meson 1.10 的 `sanity.rs` 名称补充识别：
只有 sanity probe 使用宿主编译器，真实驱动 Rust 代码继续使用 ARM64 ELF 目标。
最终归档的全部成员机器类型已实际检查。

## 运行层构建中的修复

第三方源码由 Windows Git 检出时，libmspack 的源码符号链接被保存为单行路径文本，
导致 `lzxd.c` 编译报错。新增 `tools/repair_vendor_links.py <thirdparty>`，只处理
C/C++ 源文件中可解析到第三方目录内部真实文件的相对路径文本。本次修复 16 个文件；
`build_runtime.sh` 已在 SDK 配置之前调用它。

CPU 对象来自 GCC 16.1.0，运行层使用 GCC 15.2.0。已用两版编译器分别生成结构布局
常量并比较，PPCContext 均为 2,688 字节、64 字节对齐，所查关键字段偏移完全一致。
见 `context-layout-result.json`。这只验证结构布局，不能替代运行兼容性或实机测试。

完整运行层正在构建；本阶段尚未记录新的 NRO 成功结果，也未运行游戏。
