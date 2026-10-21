// rottr - 插桩构建的 PGO profile 落盘（仅 ROTTR_PGO=generar 且 Switch 编译时启用）。
//
// 与参考移植 nfsmw 的 nfsmw_pgo.cpp 同机制（GPL-3.0）：GCC 会把每个对象的
// .gcda 路径（ROTTR_PGO_DIR\CMakeFiles#...#文件.gcda，编译机上的 Windows 风格
// 路径）嵌入可执行文件；Switch 上打不开该路径，因此用 --wrap=fopen 重定向到
// sdmc:/switch/rottr-switch/pgo/。
//
// Switch 常被 HOME 键直接杀掉进程，不能依赖退出时落盘：一个线程每 3 分钟
// __gcov_dump 一次并 __gcov_reset 清零。libgcov 对已有 .gcda 做累加，多次
// 落盘即得到本次运行的总 profile。
#if defined(ROTTR_PGO_GENERAR) && defined(__SWITCH__)

#include <switch.h>

#include <cstdio>
#include <cstring>
#include <string>
#include <sys/stat.h>

extern "C" {
FILE* __real_fopen(const char* ruta, const char* modo);
void __gcov_dump(void);
void __gcov_reset(void);

FILE* __wrap_fopen(const char* ruta, const char* modo) {
  static constexpr char kPrefijo[] = ROTTR_PGO_DIR;
  if (ruta && std::strncmp(ruta, kPrefijo, sizeof(kPrefijo) - 1) == 0) {
    const char* resto = ruta + sizeof(kPrefijo) - 1;
    while (*resto == '\\' || *resto == '/') {
      ++resto;
    }
    std::string nueva = "sdmc:/switch/rottr-switch/pgo/";
    for (; *resto; ++resto) {
      nueva += (*resto == '\\') ? '/' : *resto;
    }
    return __real_fopen(nueva.c_str(), modo);
  }
  return __real_fopen(ruta, modo);
}
}

namespace {
Thread g_hilo_pgo;

void HiloPgo(void*) {
  for (int volcado = 1;; ++volcado) {
    svcSleepThread(180LL * 1000 * 1000 * 1000);
    mkdir("sdmc:/switch/rottr-switch/pgo", 0777);
    const u64 antes = armGetSystemTick();
    __gcov_dump();
    __gcov_reset();
    const double ms = double(armTicksToNs(armGetSystemTick() - antes)) / 1e6;
    if (FILE* f = __real_fopen("sdmc:/switch/rottr-switch/pgo/volcados.txt", "a")) {
      std::fprintf(f, "volcado %d: %.0f ms\n", volcado, ms);
      std::fclose(f);
    }
  }
}

__attribute__((constructor)) void IniciarPgo() {
  // 游戏常规优先级 0x3B、任意核心：每 3 分钟跑一次足够，不抢渲染线程。
  if (R_SUCCEEDED(threadCreate(&g_hilo_pgo, HiloPgo, nullptr, nullptr, 64 * 1024, 0x3B, -2))) {
    threadStart(&g_hilo_pgo);
  }
}
}  // namespace

#endif
