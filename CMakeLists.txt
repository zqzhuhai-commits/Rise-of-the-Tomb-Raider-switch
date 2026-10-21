cmake_minimum_required(VERSION 3.25)
project(rottr_switch_research VERSION 0.0.1 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(REXSDK_DIR "" CACHE PATH "Pinned ReXGlue SDK source directory (Horizon for Switch; host SDK for the PC debug build)")
set(REX_DEPS_INCLUDE "" CACHE PATH "Third-party include directory from ReXGlue v0.10.0")
option(ROTTR_BUILD_RUNTIME "Link the full application (Horizon NRO on Switch; a host executable on the PC debug build)" OFF)
set(ROTTR_GUEST_OBJECTS_DIR "" CACHE PATH "Previously verified ARM64 guest objects built with the pinned SDK")

# Switch 最终链接期的优化（默认全关，不改变现有行为）。要启用时 build_guest.sh
# 与 build_runtime.sh 需传相同值，保证 rottr_guest 对象与应用一致：
#   ROTTR_LTO=ON  ROTTR_PGO=generar|usar  （见 docs/BUILD.md 与参考移植 nfsmw）
option(ROTTR_LTO "Link-time optimization for the recompiled game and app (Switch)" OFF)
set(ROTTR_PGO "" CACHE STRING "Profile-guided optimization (Switch): empty, generar or usar")
set(ROTTR_PGO_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../pgo" ABSOLUTE CACHE PATH "PGO profile folder")

# This repository is configured either with the Switch cross toolchain
# (cmake/switch-devkitA64.cmake, which sets REXGLUE_PLATFORM_SWITCH) or natively
# for a PC debugging loop. The PC loop is the recommended first step before device
# work: it runs the recompiled game on the host with the SDK's Xenos/Vulkan
# graphics, so translation bugs (uncovered functions, jump tables, split chunks)
# are found on a machine instead of on the console. The reference ReXGlue Switch
# port nfsmw-nx follows the same order; see docs/PORTING-GAP-ANALYSIS-zh.md.
if(NOT EXISTS "${REXSDK_DIR}/include/rex/ppc.h")
    message(FATAL_ERROR "REXSDK_DIR must contain the SDK headers (include/rex/ppc.h)")
endif()
if(NOT EXISTS "${REX_DEPS_INCLUDE}/simde/x86/avx.h")
    message(FATAL_ERROR "REX_DEPS_INCLUDE must contain the SDK third-party headers")
endif()

if(NOT REXGLUE_PLATFORM_SWITCH)
    message(STATUS "Configuring the native PC debug build (host toolchain).")
endif()

set(GEN "${CMAKE_CURRENT_SOURCE_DIR}/generated/default")
if(NOT EXISTS "${GEN}/sources.cmake")
    message(FATAL_ERROR
        "generated/default/sources.cmake is missing. Run the ReXGlue code generator "
        "on your own default.xex first (see docs/BUILD.md); generated code is never "
        "committed to this repository.")
endif()
include("${GEN}/sources.cmake")

# Validates the game CPU translation against the real toolchain: ARM64 objects on
# Switch, host objects in the PC debug build. This target deliberately has no
# executable or packaging step; the full application is linked only when
# ROTTR_BUILD_RUNTIME is enabled.
if(ROTTR_GUEST_OBJECTS_DIR)
    set(_guest_objects)
    foreach(_source IN LISTS GENERATED_SOURCES)
        get_filename_component(_name "${_source}" NAME)
        set(_object "${ROTTR_GUEST_OBJECTS_DIR}/${_name}.obj")
        if(NOT EXISTS "${_object}")
            message(FATAL_ERROR "Missing verified guest object: ${_object}")
        endif()
        list(APPEND _guest_objects "${_object}")
    endforeach()
    add_library(rottr_guest OBJECT IMPORTED GLOBAL)
    set_target_properties(rottr_guest PROPERTIES IMPORTED_OBJECTS "${_guest_objects}")
else()
add_library(rottr_guest OBJECT ${GENERATED_SOURCES})
target_include_directories(rottr_guest PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}" "${GEN}"
    "${REXSDK_DIR}/include"
    "${REX_DEPS_INCLUDE}")
if(REXGLUE_PLATFORM_SWITCH)
    target_include_directories(rottr_guest PRIVATE "${REXSDK_DIR}/switch_compat")
endif()
target_compile_definitions(rottr_guest PRIVATE
    SPDLOG_COMPILED_LIB SPDLOG_FMT_EXTERNAL REX_HAS_FIDELITYFX_SDK=1)
target_compile_options(rottr_guest PRIVATE
    -ffp-contract=off -fno-strict-aliasing
    -fno-tree-vectorize -fno-tree-slp-vectorize)
target_precompile_headers(rottr_guest PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/rottr_codegen_compat.h"
    "${GEN}/rottr_pch.h")
# The registration table is large and does not benefit from optimization.
set_source_files_properties("${GEN}/rottr_register.cpp"
    PROPERTIES COMPILE_OPTIONS "-O0" SKIP_PRECOMPILE_HEADERS ON)
endif()

# Compile-check the application entry point separately from linking the runtime.
add_library(rottr_entry_probe OBJECT src/main.cpp)
target_include_directories(rottr_entry_probe PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/src" "${GEN}"
    "${REXSDK_DIR}/include" "${REX_DEPS_INCLUDE}")
if(REXGLUE_PLATFORM_SWITCH)
    target_include_directories(rottr_entry_probe PRIVATE "${REXSDK_DIR}/switch_compat")
endif()
target_compile_definitions(rottr_entry_probe PRIVATE
    SPDLOG_COMPILED_LIB SPDLOG_FMT_EXTERNAL REX_HAS_FIDELITYFX_SDK=1)
target_precompile_headers(rottr_entry_probe PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/rottr_codegen_compat.h" "${GEN}/rottr_pch.h")

if(ROTTR_BUILD_RUNTIME)
    add_compile_definitions(REX_HAS_FIDELITYFX_SDK=1)
    add_subdirectory("${REXSDK_DIR}" rexglue-sdk)
    if(NOT ROTTR_GUEST_OBJECTS_DIR)
        target_link_libraries(rottr_guest PRIVATE rex::runtime)
    endif()
    add_executable(rottr src/main.cpp)
    target_include_directories(rottr PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/src" "${GEN}")
    target_link_libraries(rottr PRIVATE rottr_guest rex::runtime)
    target_precompile_headers(rottr PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/rottr_codegen_compat.h" "${GEN}/rottr_pch.h")
    rexglue_configure_target(rottr GPU_PLUGINS xenos)
    if(REXGLUE_PLATFORM_SWITCH)
        if(NOT EXISTS "${REXGLUE_SWITCH_NVK_SDK}/lib/libvulkan.a")
            message(FATAL_ERROR "The real Horizon NVK static driver is required before linking an NRO. Set REXGLUE_SWITCH_NVK_SDK.")
        endif()
        # LTO：对重编译代码与应用一起做链接期优化。配合 tools/direct_calls.py 的
        # 直接调用改写，编译器才能跨文件内联小游戏函数。注意内存占用大
        # （-flto=2、balanced 分区；参考项目 16 GB 内存可跑）。
        if(ROTTR_LTO)
            foreach(_lto_target rottr_guest rottr)
                if(TARGET ${_lto_target})
                    get_target_property(_lto_imported ${_lto_target} IMPORTED)
                    if(NOT _lto_imported)
                        target_compile_options(${_lto_target} PRIVATE -flto -fno-fat-lto-objects)
                    endif()
                endif()
            endforeach()
            target_link_options(rottr PRIVATE -flto=2 -flto-partition=balanced)
        endif()
        # PGO 两段式（与参考项目同机制，含两个必须的坑）：
        #   generar: 插桩构建，src/rottr_pgo.cpp 每 3 分钟把 .gcda 落盘到
        #            sdmc:/switch/rottr-switch/pgo/（--wrap=fopen 重定向）。
        #            -fno-profile-values 必须：Horizon 上 libnx 不用 tpidr_el0
        #            （-mtp=soft），GCC 的间接调用插桩读它恒为 0，会启动即崩。
        #   usar:    把 .gcda 拷回编译机的 ROTTR_PGO_DIR 后重编译。
        #            -fprofile-correction 必须：多线程累加的计数器会变负，
        #            GCC 视为损坏 profile 而拒绝。
        # 两次构建必须同一份生成代码/源码与同一构建目录路径。
        if(ROTTR_PGO)
            file(TO_NATIVE_PATH "${CMAKE_BINARY_DIR}" ROTTR_PGO_PREFIJO)
            if(ROTTR_PGO STREQUAL "generar")
                set(_pgo_opciones -fprofile-generate=${ROTTR_PGO_DIR}
                    "-fprofile-prefix-path=${ROTTR_PGO_PREFIJO}"
                    -fprofile-update=single -fno-profile-values)
                target_link_options(rottr PRIVATE -fprofile-generate -Wl,--wrap=fopen)
                target_compile_definitions(rottr PRIVATE ROTTR_PGO_GENERAR=1
                    "ROTTR_PGO_DIR=\"${ROTTR_PGO_DIR}\"")
                target_sources(rottr PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/src/rottr_pgo.cpp")
            elseif(ROTTR_PGO STREQUAL "usar")
                set(_pgo_opciones -fprofile-use=${ROTTR_PGO_DIR}
                    "-fprofile-prefix-path=${ROTTR_PGO_PREFIJO}"
                    -fprofile-partial-training -fno-profile-values -fprofile-correction
                    -Wno-missing-profile -Wno-error=coverage-mismatch)
                target_link_options(rottr PRIVATE -fprofile-use -fprofile-partial-training -fprofile-correction)
            else()
                message(FATAL_ERROR "ROTTR_PGO 必须为空、generar 或 usar（当前为 '${ROTTR_PGO}'）")
            endif()
            foreach(_pgo_target rottr_guest rottr)
                if(TARGET ${_pgo_target})
                    get_target_property(_pgo_imported ${_pgo_target} IMPORTED)
                    if(NOT _pgo_imported)
                        target_compile_options(${_pgo_target} PRIVATE ${_pgo_opciones})
                    endif()
                endif()
            endforeach()
        endif()
        rexglue_switch_add_nro(rottr NAME "Rise of the Tomb Raider" AUTHOR "Switch port contributors" VERSION "0.0.1-research")
    else()
        message(STATUS
            "PC debug build: 'rottr' runs the game with the SDK's Xenos/Vulkan backend. "
            "It expects the extracted game in a 'game' folder next to the executable "
            "(src/rottr_app.h). gpu_plugin=xenos is set by default in rottr_app.h; "
            "the Xenos GPU plugin DLL is placed next to the executable by the SDK.")
    endif()
endif()
