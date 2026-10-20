# Rise of the Tomb Raider — Switch 移植研究

《古墓丽影：崛起》Xbox 360 基础版面向 Switch / Atmosphère 的静态重编译研究。采用 ReXGlue 将 PowerPC 程序转换为 C++，再交叉编译至 ARM64；当前图形路径为 SDK 的 Xenos / Vulkan FSI 后端。

**截至 2026-10-20：已构建研究版 NRO 和入口 NSP，尚未进行 Switch 实机验证。此仓库处于首次启动验证阶段，不能认定游戏已可玩。**

## 已完成的验证

| 项目 | 结果 |
|---|---|
| GOD 文件系统解析 | 主游戏 81 个文件，包含简体、繁体资源 |
| 基础程序识别 | Title ID `53510823`，Media ID `0A657B25`，版本 `0.0.0.3` |
| 静态重编译 | ReXGlue v0.10.0 校验通过，生成 209 个 C++ 文件 |
| CPU 交叉编译 | 209 个 ARM64 ELF64 对象文件生成成功 |
| 函数别名检查 | 44,867 个游戏函数弱别名存在，地址与实现匹配 |
| 图形驱动 | Mesa 26.2.3 / NVK 静态库实际构建成功 |
| Horizon NRO | 完整链接、打包及 NRO0 / ASET / NACP 结构检查通过 |
| 入口 NSP | PFS0、3 个 NCA 的哈希及解密头检查通过 |
| 资源提取工具 | 主程序提取与 SHA-256 核对通过；完整资源提取尚未执行 |
| Switch 实机启动、画面、声音、操作、存档、性能 | **待验证** |

## 仓库内容

- `src/`、`CMakeLists.txt`、`cmake/`：应用入口与交叉编译配置。
- `tools/`、`build_guest.sh`、`build_runtime.sh`：资源准备、翻译修正、编译与验证工具。
- `dependencies.lock.json`：依赖提交、工具链镜像及补丁哈希。
- `*-result.json`：各构建阶段留存的检查结果。它们记录历史检查点，未由本仓库 CI 重新执行；早期阶段中的 `switch_compiled: false` 或 `runtime_linked: false` 只描述该阶段。
- `docs/BUILD.md`：重建步骤及环境限制。
- `TESTING-zh.md`：首次实机验证方法。

游戏资源、原始 XEX、生成的游戏代码、编译对象、NRO / NSP 和控制台密钥不放入本公开仓库。需要从自己的匹配游戏版本在本地准备。仓库当前没有可下载的公开二进制发行版。

## 当前修正

- 补充 `0x82C21240` 函数识别提示，解决首次代码生成的未识别跳转。
- 修正 GCC 对生成函数弱别名属性的处理，并检查编译后的符号表。
- 将两处 `dcbz` 翻译的清零与对齐大小从 32 修正为 128 字节。
- 固定 SDK、Mesa、参考端口及 devkitPro 版本。
- 启用 SDK 已提供的 Horizon FFmpeg 配置。
- 转发器适配当前 libnx 的 `noreturn` 声明，修改方式见构建说明。

## 下一阶段

1. 实机验证完整内存启动，收集 `/switch/rottr-switch/logs/` 日志。
2. 定位首个运行期故障，验证线程、动态调用及 Xenos 渲染。
3. 验证中文界面、声音、控制与存档，再测试游戏流程和性能。
4. 基础版稳定后，再评估独立 TU 更新、DLC 及游戏专用优化。

当前没有应用独立 TU4 更新或接入 DLC。配置中的中文语言值与存在的中文资源不能证明中文画面已经正确运行。代码生成结果中的 607 个越界 switch trap 标记也仍需要运行验证。

## 许可及来源

本仓库移植配置与工具以 GPL-3.0 发布，见 [LICENSE](LICENSE)。第三方组件遵循各自许可证，来源见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。游戏名称、代码与资源的权利归其原权利人；本仓库的许可证不授予游戏内容使用权。
