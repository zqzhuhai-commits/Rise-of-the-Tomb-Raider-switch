cmake_minimum_required(VERSION 3.25)
project(rottr_switch_research VERSION 0.0.1 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(REXSDK_DIR "" CACHE PATH "Pinned Horizon ReXGlue SDK source directory")
set(REX_DEPS_INCLUDE "" CACHE PATH "Third-party include directory from ReXGlue v0.10.0")
option(ROTTR_BUILD_RUNTIME "Link experimental Horizon application; requires the full SDK and NVK" OFF)
set(ROTTR_GUEST_OBJECTS_DIR "" CACHE PATH "Previously verified ARM64 guest objects built with the pinned SDK")
if(NOT REXGLUE_PLATFORM_SWITCH)
    message(FATAL_ERROR "Configure with cmake/switch-devkitA64.cmake")
endif()
if(NOT EXISTS "${REXSDK_DIR}/include/rex/ppc.h")
    message(FATAL_ERROR "REXSDK_DIR must contain the Horizon SDK headers")
endif()
if(NOT EXISTS "${REX_DEPS_INCLUDE}/simde/x86/avx.h")
    message(FATAL_ERROR "REX_DEPS_INCLUDE must contain the SDK third-party headers")
endif()

set(GEN "${CMAKE_CURRENT_SOURCE_DIR}/generated/default")
include("${GEN}/sources.cmake")
# This target validates the game CPU translation against the real libnx/ARM64
# toolchain. It deliberately has no executable or NRO packaging step: the
# full runtime is linked only when ROTTR_BUILD_RUNTIME is enabled.
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
    "${REXSDK_DIR}/switch_compat" "${REXSDK_DIR}/include"
    "${REX_DEPS_INCLUDE}")
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
    "${REXSDK_DIR}/switch_compat" "${REXSDK_DIR}/include" "${REX_DEPS_INCLUDE}")
target_compile_definitions(rottr_entry_probe PRIVATE
    SPDLOG_COMPILED_LIB SPDLOG_FMT_EXTERNAL REX_HAS_FIDELITYFX_SDK=1)
target_precompile_headers(rottr_entry_probe PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/rottr_codegen_compat.h" "${GEN}/rottr_pch.h")

if(ROTTR_BUILD_RUNTIME)
    if(NOT EXISTS "${REXGLUE_SWITCH_NVK_SDK}/lib/libvulkan.a")
        message(FATAL_ERROR "The real Horizon NVK static driver is required before linking an NRO. Set REXGLUE_SWITCH_NVK_SDK.")
    endif()
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
    rexglue_switch_add_nro(rottr NAME "Rise of the Tomb Raider" AUTHOR "Switch port contributors" VERSION "0.0.1-research")
endif()
