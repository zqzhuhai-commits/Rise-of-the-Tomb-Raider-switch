#!/bin/sh
# Build and run the native PC debugging loop.
#
# This compiles the recompiled game for the host (x86-64) and links it into an
# executable that runs with the SDK's Xenos/Vulkan graphics backend. It is the
# recommended first step before Switch device work: translation bugs (uncovered
# functions, jump tables, split function chunks) are far easier to find and fix
# on a PC than on the console. See docs/PORTING-GAP-ANALYSIS-zh.md and the
# reference port StevensND/nfsmw-nx (docs/porting-another-game.md).
#
# Requirements (same as the Switch build up to codegen):
#   - ReXGlue codegen already run: generated/default/sources.cmake must exist
#     (produced from your own default.xex; never committed).
#   - The pinned SDK source (REXSDK_DIR) and third-party headers (REX_DEPS_INCLUDE).
#   - A host C++ compiler; on Windows, Clang 20+ / MSVC and a Vulkan-capable GPU.
#
# Optional overrides: ROTTR_CMAKE, ROTTR_NINJA, ROTTR_SDK_SOURCE,
# ROTTR_DEPS_INCLUDE, ROTTR_JOBS (see also build_guest.sh).
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
work_dir=$(CDPATH= cd -- "$project_dir/.." && pwd)
cmake_exe=${ROTTR_CMAKE:-"$work_dir/build-tools/cmake/data/bin/cmake"}
ninja_exe=${ROTTR_NINJA:-"$work_dir/build-tools/bin/ninja"}
sdk_dir=${ROTTR_SDK_SOURCE:-"$work_dir/masseffect-nx-review/sdk"}
deps_include=${ROTTR_DEPS_INCLUDE:-"$work_dir/rexglue-sdk-linux/linux-amd64/include"}
python3 "$project_dir/tools/prepare_codegen.py"
# 把没有 hook 的游戏函数调用改写为直接调用（LTO 前提；幂等，可 --deshacer 还原）。
python3 "$project_dir/tools/direct_calls.py" --sdk "$sdk_dir"
"$cmake_exe" -S "$project_dir" -B "$project_dir/build/pc" -G Ninja \
  -DCMAKE_MAKE_PROGRAM="$ninja_exe" -DCMAKE_BUILD_TYPE=Release \
  -DREXSDK_DIR="$sdk_dir" -DREX_DEPS_INCLUDE="$deps_include" \
  -DROTTR_BUILD_RUNTIME=ON
"$cmake_exe" --build "$project_dir/build/pc" --target rottr -j "${ROTTR_JOBS:-8}"

echo
echo "PC debug build ready: $project_dir/build/pc/rottr"
echo "Run it next to the extracted game so src/rottr_app.h finds ./game:"
echo "  cp -r /path/extracted-game/game $project_dir/build/pc/game"
echo "  $project_dir/build/pc/rottr"
echo "It uses gpu_plugin=xenos (set by default in src/rottr_app.h)."
