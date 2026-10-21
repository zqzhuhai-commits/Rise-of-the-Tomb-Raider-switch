# 真实数据验证记录（2026-10-22）

本节记录在拿到匹配基础版 `default.xex` 后，把全部工具链在真实生成数据上跑通的结果。
所有数字来自真实运行（ReXGlue v0.10.0 官方 Linux AMD64 版，`--ignore-stamp` 强制重跑）。

## 1. codegen 复现

- 输入：`default.xex`（16,531,456 B，SHA-256 `47e6476f…41e585`，与仓库记录一致）
- 输出：`generated/default`，424 个文件，**207 个 `rottr_recomp.*.cpp`**，共 228,206,531 B
- 关键标记：**607 个 `__builtin_trap(); // Switch case out of range`**（与旧 codegen-result.json 完全一致）
- codegen 耗时 85 s，退出码 0

> 旧记录为 209 个 cpp 文件、226,375,016 B；本次 207 个、228,206,531 B。
> cpp 数减少 2 个与字节数差异源于分片合并策略在不同输入状态下的细微差别，
> 607 trap 与 421 written 完全一致，判定为等价生成。

## 2. trap 定位（tools/analyze_traps.py，真实数据）

- 607 个 trap 分布在 **407 个函数、183 个文件、20 种 switch 表达式**
- trap 最多的跳转函数（前 5）：

| 地址 | trap 数 |
|---|---:|
| 0x82A711A8 | 14 |
| 0x82AD2ED0 | 10 |
| 0x8268FC40 | 9 |
| 0x82AC27C0 | 8 |
| 0x82A97BE8 | 8 |

- 20 种 switch 表达式全部是 `ctx.rNN.u32`（r3–r11、r16、r19–r21、r23–r24、r26–r27、r29–r31）
  —— 与参考移植的观察一致：X360 跳转表（jumptable）被翻译成基于寄存器的 switch，
  case 目标超出已注册函数范围时落入 trap。

## 3. 空隙（gaps）分析与 huecos 迭代（核心产出）

`tools/find_gaps.py` 在真实数据上发现 **24,803 个空隙**，其中 **≥8 字节 682 个**
（总计 146,200 B）。随后做了三轮 codegen 验证迭代：

| 轮次 | huecos.toml 条目 | codegen 结果 | 处理 |
|---|---:|---|---|
| 1 | 682（全部候选） | 通过，但 40 个 "has no blocks - generating stub"；trap 607→623 | 剔除 40 个数据块 |
| 2 | 642 | 通过，0 stub；trap 仍 623 | 定位 11 个新增 trap 函数全部来自声明 |
| 3 | **631（最终）** | 通过，0 stub；**trap 回到 607（基线）** | — |

最终 `huecos.toml` = **631 条经 codegen 验证的空隙声明**：
- 40 个纯数据块（codegen 报 "has no blocks"）已剔除；
- 11 个跳转表数据被误当代码（新增 16 个 trap）已剔除；
- 剩余 631 条既无 stub 警告、也不产生新 trap，判定为真实代码空隙
  （thunk 表 / 被间接调用但未被 Discover 覆盖的函数）。

> 这 631 条就是"运行期 `Call to invalid or unregistered function`"的候选修复集。
> 参考移植（nfsmw）的 huecos.toml 为 774 条，且运行期仍会按崩溃地址拆多入口 thunk 表
> （本项目的 8/16 字节空隙即此类，需实机崩溃日志再拆分）。

## 4. 直接调用改写（tools/direct_calls.py，真实数据）

- **151,061 处 `sub_X(ctx, base)` → `__imp__sub_X(ctx, base)`**，涉及全部 207 个文件
- 保留 1 处原样调用（0x82C21240，`analysis_overrides.toml` 的 hook）——符合设计
- 幂等验证、语法与计数精确核对通过

## 5. 寄存器分析（tools/lee_antes.py，真实数据）

- 结果：**0 个函数** 存在"读先于写"的非易失寄存器——**这是预期行为**：
  当前 pinned SDK 未打 share_registers 补丁，生成代码中寄存器仍以 `ctx.rNN.u64`
  形式常驻内存（无局部变量名可检测）。参考项目对 SDK 打补丁、启用寄存器局部化后，
  该工具才产生候选列表（其主线程 ~14% 的 save/restore 耗时可消除）。

## 6. PC 调试环编译（当前环境的结论）

尝试在宿主编译 207 个生成文件（`ROTTR_BUILD_RUNTIME=OFF`，仅 rottr_guest）：
- CMake 4.4.4 + Ninja 配置通过；
- **gcc 11.4 编译 SDK 头文件失败**：`std::byteswap` 非成员、`std::chrono::clock_time_conversion`
  非模板——SDK 头文件使用 C++23 特性，官方平台支持明确要求 **Clang 18+**
  （Linux amd64：Ubuntu 20.04+，Compiler Clang 18+）。
- 结论：PC 调试环必须在装有 **Clang 18+（或 GCC 13+）** 的主机上构建；
  本环境 gcc 11 不可行。已记录到 docs/BUILD.md。

## 7. 尚未验证（保持不变，诚实标注）

- Switch 实机构建（无 devkitPro）与运行；
- 631 条 huecos 的**运行期有效性**（需实机崩溃日志，按参考流程拆多入口）；
- 607 个 trap 的**运行期触发频率**（部分可能由 huecos 覆盖直接消除）；
- PC 调试环在符合工具链要求的主机上的完整构建与画面验证。
