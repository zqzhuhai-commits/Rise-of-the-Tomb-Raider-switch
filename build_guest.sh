#!/bin/sh
# Compile CPU objects only. This does not link a runtime or package an NRO.
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
work_dir=$(CDPATH= cd -- "$project_dir/.." && pwd)
cmake_exe=${ROTTR_CMAKE:-"$work_dir/build-tools/cmake/data/bin/cmake"}
ninja_exe=${ROTTR_NINJA:-"$work_dir/build-tools/bin/ninja"}
sdk_dir=${ROTTR_SDK_SOURCE:-"$work_dir/masseffect-nx-review/sdk"}
deps_include=${ROTTR_DEPS_INCLUDE:-"$work_dir/rexglue-sdk-linux/linux-amd64/include"}
export DEVKITPRO=${DEVKITPRO:-"$work_dir/devkit-root/opt/devkitpro"}
python3 "$project_dir/tools/prepare_codegen.py"
# 把没有 hook 的游戏函数调用改写为直接调用（LTO 前提；幂等，可 --deshacer 还原）。
# 每次 codegen 后生成的代码都会恢复 sub_X 调用，必须重跑。
python3 "$project_dir/tools/direct_calls.py" --sdk "$sdk_dir"
"$cmake_exe" -S "$project_dir" -B "$project_dir/build/guest-switch" -G Ninja \
  -DCMAKE_MAKE_PROGRAM="$ninja_exe" -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_TOOLCHAIN_FILE="$project_dir/cmake/switch-devkitA64.cmake" \
  -DDEVKITPRO="$DEVKITPRO" -DREXSDK_DIR="$sdk_dir" -DREX_DEPS_INCLUDE="$deps_include" \
  -DROTTR_LTO="${ROTTR_LTO:-OFF}" -DROTTR_PGO="${ROTTR_PGO:-}"
"$cmake_exe" --build "$project_dir/build/guest-switch" --target rottr_guest -j "${ROTTR_JOBS:-4}"
