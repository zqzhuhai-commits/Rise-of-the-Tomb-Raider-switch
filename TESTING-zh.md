# 《古墓丽影：崛起》Switch 兼容性测试版

本次已经实际完成 ARM64 编译、Horizon 运行层链接及 NRO/NSP 打包。尚未在 Switch 上启动验证，不能据此认定可玩、可通关或达到某个帧率。

本文适用于已经自行构建或另行取得研究测试包的开发者。公开仓库只提供源码和检查点记录，不包含以下 NRO / NSP。

## 文件用途

- `nsp/ROTTR-Switch-TEST.nsp`：HOME 菜单入口，标题 ID 为 `01524F5454520000`。
- `switch/rottr-switch/rottr.nro`：实际程序，必须放在 SD 卡对应位置。
- `switch/rottr-switch/rottr-switch.toml`：首次测试配置，语言设为简体中文，开启信息日志。
- `tools/prepare_game.py`（测试包中为 `prepare_game.py`）：从你提供的 Xbox 360 GOD ZIP 中提取匹配的基础游戏资源；需要电脑上的 Python 3，不需要额外 Python 包。

NSP 是入口转发器，不能单独运行游戏。程序和原游戏资源需要同时保留在 SD 卡上。原游戏资源约 6.55 GB，需要自行准备。

## 准备 SD 卡

1. 将本包的 `switch` 文件夹合并复制到 SD 卡根目录。准备至少 8 GB 可用空间。
2. 将你提供的原始 `gmly.zip` 下载到电脑，保持 ZIP 原样。这个包包含 GOD 主程序、独立更新包及 DLC；本轮只使用基础游戏。
3. 在本测试包解压目录打开终端，执行下面的命令。`D:\gmly.zip` 换成原包位置，`E:` 换成 SD 卡盘符：

   ```powershell
   py -3 prepare_game.py "D:\gmly.zip" --output "E:\switch\rottr-switch\game"
   ```

   macOS/Linux 可使用 `python3 prepare_game.py /path/gmly.zip --output /path/to/SD/switch/rottr-switch/game`。

4. 完成后，确认 SD 卡上存在 `switch/rottr-switch/game/default.xex`，以及同目录的 `bigfile.000.tiger`、`bigfile_SIMPLCHINESE.000.tiger`、`movies` 等原始文件。
5. 用你常用的安装器安装测试 NSP，再从 HOME 菜单启动。也可以按住 R 打开一款已安装游戏进入完整内存 hbmenu，再启动 `rottr.nro`。

提取脚本会核对 `default.xex` 的 SHA-256，拒绝不匹配的基础版本，并拒绝覆盖已有目标文件。完整资源提取尚未在本轮执行；已验证目录读取及主程序提取与校验。

## 首次测试反馈

请记录：是否进入原游戏画面、最后停留的画面、错误代码、声音和按键是否有反应。黑屏或退出后，请将 `switch/rottr-switch/logs` 目录及首屏/报错图片发回。

当前采用 SDK Xenos/Vulkan 兼容渲染后端。游戏逻辑、动态调用、线程同步、存档、渲染正确性及性能都需要实机验证。独立 TU 更新和 DLC 尚未接入；请先测试基础版。

## 来源与许可

- ReXGlue：<https://github.com/rexglue/rexglue-sdk>，v0.10.0。
- Horizon SDK：<https://github.com/nebadasSwifty/masseffect-nx>，`a85b0b419ec3e332165ae1617c980bd399856a44`，叠加参考端口的 SDK 补丁及本项目记录的配置修正。
- Mesa/NVK：<https://github.com/danfromtico/mesa-switch>，`d4a00ea0ab3f59afb967cc5d779e4263d237bd77`，叠加参考端口补丁。
- 参考端口及 NSP 容器源码：<https://github.com/fungalspores/prototype-switch>，`292de4b382dbe335011d8b4f56ec4212df5ef74c`。
- 转发器源码：<https://github.com/Skywalker25/Forwarder-Mod>，`9853bd9167d5a7f0c5fdf935864245c1fbcf8282`。本项目仅将 `void NORETURN nroEntrypointTrampoline` 修正为 `void __attribute__((noreturn)) nroEntrypointTrampoline`，并由构建脚本填入本应用标题 ID、启动路径及内存权限。

完整开发检查点提供本次源码、构建配置、日志及编译结果。第三方组件仍遵循各自许可证；游戏名称和资源属于其原权利人。
