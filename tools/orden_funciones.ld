/*
 * 热函数置于 .text 开头的链接排序文件（对应 ROTTR_ORDEN_FUNCIONES=ON）。
 *
 * 来源：实机堆栈采样得到的"最热"函数清单（热在前）。尚未采样时本文件只有
 * 必须的 crt0 一行；采样后可参考参考移植 nfsmw 的 tools/calientes.py 生成
 * __imp__sub_XXXXXXXX 条目并追加到 .text : { ... } 内。
 *
 * !!! 陷阱（参考项目实测踩过）:链接器把本文件列出的内容放在其自带脚本的
 * 一切之前，包括 libnx 启动代码。若 .text 首行不是 KEEP(*(.crt0))，
 * memcpy 等函数会跑到地址 0，NRO 无法启动（Atmosphère 报 undefined
 * instruction at +0x14）。每次改动后检查 _start 位于地址 0：
 *   aarch64-none-elf-nm rottr | grep " _start$"   # 必须输出 0000000000000000
 */
.text : {
  KEEP (*(.crt0))
}
