# Windows 本地重编译验证（2026-11-10）

## 本次修复

基础 XEX 的 SHA-256 与锁定版本一致：
`47e6476f6d393d86612e7af938979e9c706b54dc526d8422413711999d41e585`。

ReXGlue v0.10.0 Windows 官方发行包可成功生成代码。首次 Release
交叉编译在 `sub_825A2090` 失败：跳转引用 `loc_825A2570`，但标签不存在。
该地址被 `huecos.toml` 误声明为独立函数，生成器因此把原函数内部的分支块分离。

移除这一条函数提示，并加入 `tools/huecos_excluir.txt`，重新生成后：

- `loc_825A2570` 恢复到原函数内部。
- `0x825A25D0 -> 0x825A232C` 的回跳恢复，不再生成该处的 unresolved-branch fatal。
- 全部 208 个重编译分片通过 `tools/verify_codegen.py` 的局部标签检查。
- 保留 607 个越界 switch trap 标记，需要运行调试，不能据此认定游戏可启动。

此前“631 条经 codegen 验证”的记录只代表当时生成器接受了这些配置，
不代表每条都是正确的独立函数。本次配置剩余 630 条。

## Windows CPU 构建

使用原生 Windows CMake 和 Ninja，不能使用 devkitPro MSYS 目录中的 CMake
代替（本次遇到路径被改写、工具链文件查找失败）。本次工具为 CMake 4.4.5、
Ninja 1.13.2、devkitA64 GCC 16.1.0；与历史 Linux GCC 15.2.0 检查点分别记录。

先按 `docs/BUILD.md` 获取锁定 SDK、应用并验证参考补丁，准备官方 v0.10.0
Windows SDK 发行包头文件。将匹配的 `default.xex` 放到仓库根目录后：

```powershell
& C:/tools/rexglue/win-amd64/bin/rexglue.exe codegen rottr_manifest.toml
./build_guest.ps1 -Sdk ../masseffect-nx-review/sdk `
  -DepsInclude C:/tools/rexglue/win-amd64/include `
  -CMake C:/tools/cmake/bin/cmake.exe -Ninja C:/tools/ninja/ninja.exe `
  -BuildType Debug -Jobs 8
```

`build_guest.ps1` 依次检查局部标签、修正 dcbz、改写直接调用、配置并编译 CPU
对象、验证 ARM64 ELF 和函数别名。任何阶段失败都会停止。默认仍为 Release；
Debug 用于较快验证编译修复。可使用 `-BuildDir` 单独保存不同配置。
验证报告保存在构建目录，避免覆盖历史检查点。

游戏生成代码、对象文件和原始资源不上传仓库。基础版构建不合并 TU4 或 DLC。

## 最终运行层

CPU 对象通过并不等于已生成可运行的 NRO。本机现有 WSL Ubuntu 的 Mesa
交叉配置探测在 `/usr/local/libexec/rustc` 缺失处失败；WSL devkitA64 为 14.1.0，
也与 Windows 和锁定历史工具链不同。需要准备固定 Rust 工具链、Rust/bindgen
包装器、主机 shader 工具和 Horizon NVK 静态库，再构建并链接 SDK 运行层。
实机的画面、音频、输入、存档和性能仍待验证。
