# 《古墓丽影：崛起》Switch 移植 —— 差距分析与推进路线图

> 依据社区已验证可玩的 Xbox 360→Switch ReXGlue 移植项目 **StevensND/nfsmw-nx**
> （《极品飞车：最高通缉 2005》，同技术栈：ReXGlue 静态重编译 PowerPC→C++、Mesa NVK Vulkan 渲染、实机 30FPS 无超频）逐项对照得出。
> 参考仓库：https://github.com/StevensND/nfsmw-nx （其 `docs/porting-another-game.md` 是整套移植手册）。
>
> 截止 2026-10-20：本项目已构建研究版 NRO 与入口 NSP，**未实机验证**，图形走 SDK 通用 Xenos/Vulkan FSI 路径。

---

## 一、阶段对照（移植顺序按参考项目验证过的先后）

| # | 阶段 | 参考项目（nfsmw-nx）做法 | 本项目（ROTTR）现状 | 差距 |
|---|---|---|---|---|
| 1 | PC 端重编译跑通 | 先在 PC 上把 default.xex 翻译为 C++，用重编译器的图形在 PC 上跑通并修错；维护 PC 构建目标 | 有 codegen（209 文件，45,368 登记项），但**无 PC 构建目标**，直接跳到 Switch | **重大**：缺少 PC 调试环，607 个越界 switch trap 无从定位 |
| 1a | 函数/缺口补全 | `huecos.toml`（774 个 ≥8B 缺口声明为函数）+ `overrides.toml`（手写专项发现） | 仅 `analysis_overrides.toml` 1 个手工函数（`0x82C21240`） | **重大**：607 个越界 trap 大概率对应大量未覆盖函数/跳转表/分片 |
| 1b | 寄存器本地化 | codegen `share_registers` 选项 + `lee_antes.py` 检测读先于写；198 个分片函数标记 | 未使用 | 中：Switch 慢核上影响大（参考项目省 ~14% 主线程耗时） |
| 2 | 移入 Switch 系统 | SDK 的 Switch 层（内存、异常、线程优先级、时钟、音频、出帧）复用；记录平台坑 | 已构建 NRO/NSP，结构校验通过 | **实机未测**，平台坑未记录 |
| 3 | 首个画面→原生渲染器 | 通用路径仅"每秒几帧"；随后写**原生渲染器**：ring 线程读 PM4 命令环，直接以 Vulkan 绘制 | 仅 SDK 通用 Xenos/Vulkan FSI 后端 | **最大工作量**：无原生渲染器 |
| 4 | 着色器预翻译 | XenosRecomp→HLSL→DXC→SPIR-V，按 microcode 指纹建着色器库（.nfsp），避免运行时翻译卡顿 | 无 | 大：无着色器库 |
| 5 | 实机测量 | measuring.md：A/B 对比、GPU 时间×1.627、逐线程 CPU、帧时间分布 | 未开始 | — |
| 6 | 优化 | 直接调用 + LTO + PGO + 函数排序 | 仅 -O3，无 LTO/PGO/直接调用/排序 | 中-大 |

**驱动（Mesa/NVK）**：本项目已构建 Mesa 26.2.3/NVK 静态库。参考项目在 mesa-switch（commit `1a8c1a66d6f`）上加 `mesa-switch-nfsmw.patch`，补了 ZCULL 早深度测试、NAK 内存等待与分支优化、绘制路径减负、CPU 写内存免缓存等——这些优化可移植复用。

---

## 二、首个实机启动要避开的平台坑（参考 `platform-notes.md`）

| 坑 | 后果 |
|---|---|
| Horizon 内存映射数上限 | 报错 `2001-0103`；游戏多镜像视图会耗尽映射 |
| libnx 全程序单一异常栈 | 两线程同时崩溃会互相覆盖数据 |
| `std::thread::detach()` | 在 Horizon 上直接关游戏；应建一次线程并常驻 |
| 同优先级线程不共享 CPU（除 `0x3B` 游戏优先级） | 忙线程可永久饿死其他线程 |
| 只有 3 个可用核心（非 4） | 满载线程需为渲染/音频让路 |

实机步骤按 `TESTING-zh.md`，日志落在 `/switch/rottr-switch/logs/`。

---

## 三、下一步推进顺序（按投入/收益）

### 第 0 步（立刻，可在本环境做代码工作）
建立 **PC（linux-amd64 / x64）构建目标**，用重编译器通用图形把游戏在 PC 上跑起来。这是参考项目反复强调的第 1 步，也是定位 607 个 trap、缺函数、分片问题最省力的手段。缺这条环，实机上每个崩溃都要靠 addr2line 盲猜。

### 第 1 步（需要你的实机）
按 `TESTING-zh.md` 首次实机启动，收集日志，定位首个运行期故障（线程、动态调用、Xenos 渲染）。同时注意上表平台坑。

### 第 2 步（大工程）
移植原生渲染器骨架，可复用参考项目 `app/src/nfsmw_nativo_*` 的通用件：
- PM4 命令环读取器 / GPU 状态跟踪 / draw 记录
- 渲染目标为 Vulkan 图像、避免多余拷贝的 resolve
- 纹理缓存（上传时"untiling"还原顺序）
- 管线缓存（启动时预编译已知管线）
- 用 guard 替换最热游戏函数为原生码

游戏特有部分：hook 地址、识别各渲染 pass（阴影/反射/cubemap）。先做 D3D trace 阶段（对应 `nfsmw_d3d_trace.cpp`）确认每个地址，再替换。

### 第 3 步
着色器预翻译建库（XenosRecomp + DXC → SPIR-V，指纹索引），消除运行时翻译卡顿。

### 第 4 步
测量 + 优化：直接调用（对应 `llamadas_directas.py`）、LTO（`-flto=2`）、PGO（两段式，注意 `-fno-profile-values` 与 `-fprofile-correction` 两个坑）、函数排序（注意 `.text` 首行必须 `KEEP(*(.crt0))`，否则 `_start` 不在地址 0、NRO 无法启动）。

### 第 5 步
把 mesa-switch 的 ZCULL / NAK / 绘制路径补丁按需移植到本项目的 NVK 构建。

---

## 四、可直接复用的参考资产（nfsmw-nx 仓库内路径）

| 资产 | 路径 |
|---|---|
| 移植总手册 | `docs/porting-another-game.md` |
| Horizon 平台坑 | `docs/platform-notes.md` |
| 原生渲染器设计 | `docs/native-renderer.md` |
| 工具链（LTO/PGO/直接调用/寄存器本地化） | `docs/toolchain.md` |
| Mesa/NVK 驱动优化 | `docs/mesa.md`（补丁 `mesa/mesa-switch-nfsmw.patch`） |
| 缺口声明（huecos） | `app/huecos.toml`（774 条） |
| 函数本地化标记 | `app/overrides.toml`（share_registers） |
| 直接调用改写 | `tools/llamadas_directas.py` |
| 读先于写检测 | `tools/lee_antes.py` |
| 热函数排序 | `app/orden_funciones.ld`（注意 crt0 陷阱） |
| LTO/PGO 的 CMake 选项 | `app/CMakeLists.txt` |

---

## 五、结论

本项目的构建链路（codegen→交叉编译→NVK→NRO/NSP）已跑通，但**尚停留在"能构建、未实机、通用慢渲染"阶段**。要走到"可玩"，参考项目证明必须补齐：①PC 调试环、②函数/缺口补全（607 trap 归零）、③原生渲染器、④着色器库、⑤LTO/PGO/直接调用优化、⑥NVK 驱动补丁。

其中 ① 的 PC 构建目标和函数补全属于**可在普通 Linux 环境推进的代码工作**；②③④⑥ 中的渲染器与驱动工程量大，属于长期工作；实机启动与测量必须依赖你的 Switch 实机和游戏文件。
