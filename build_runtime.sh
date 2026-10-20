#!/bin/sh
# Link the experimental NRO with the pinned Horizon SDK and real NVK driver.
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
work_dir=$(CDPATH= cd -- "$project_dir/.." && pwd)
cmake_exe=${ROTTR_CMAKE:-"$work_dir/build-tools/cmake/data/bin/cmake"}
ninja_exe=${ROTTR_NINJA:-"$work_dir/build-tools/bin/ninja"}
sdk_dir=${ROTTR_SDK_SOURCE:-"$work_dir/masseffect-nx-review/sdk"}
deps_include=${ROTTR_DEPS_INCLUDE:-"$work_dir/rexglue-sdk-linux/linux-amd64/include"}
export DEVKITPRO=${DEVKITPRO:-"$work_dir/devkit-root/opt/devkitpro"}
driver_dir=${ROTTR_NVK_SDK:-"$work_dir/mesa-sdk/opt/devkitpro/portlibs/switch"}
guest_dir=${ROTTR_GUEST_OBJECTS_DIR:-"$project_dir/build/guest-switch/CMakeFiles/rottr_guest.dir/generated/default"}
if [ ! -f "$guest_dir/rottr_init.cpp.obj" ] && [ -d "$project_dir/artifacts/guest_objects" ]; then
  guest_dir="$project_dir/artifacts/guest_objects"
fi
python3 "$project_dir/tools/prepare_sdk.py" "$sdk_dir"
"$cmake_exe" -S "$project_dir" -B "$project_dir/build/runtime-switch" -G Ninja \
  -DCMAKE_MAKE_PROGRAM="$ninja_exe" -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_TOOLCHAIN_FILE="$project_dir/cmake/switch-devkitA64.cmake" \
  -DDEVKITPRO="$DEVKITPRO" -DREXSDK_DIR="$sdk_dir" -DREX_DEPS_INCLUDE="$deps_include" \
  -DROTTR_BUILD_RUNTIME=ON -DROTTR_GUEST_OBJECTS_DIR="$guest_dir" \
  -DREXGLUE_SWITCH_NVK_SDK="$driver_dir"
"$cmake_exe" --build "$project_dir/build/runtime-switch" --target rottr -j "${ROTTR_JOBS:-8}"
