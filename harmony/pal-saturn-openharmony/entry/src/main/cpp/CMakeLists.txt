# 仙剑奇侠传 土星版 · HarmonyOS 原生构建
# hvigor 用 OHOS NDK 配置这里；产物必须是 libmain.so（鸿蒙只加载这个名字）。
cmake_minimum_required(VERSION 3.5.0)
project(palsaturn)

if(DEFINED PACKAGE_FIND_FILE)
    include(${PACKAGE_FIND_FILE})
endif()

# entry/src/main/cpp -> 仓库根
get_filename_component(PAL_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../../../../../" REALPATH)

# build/recomp 由 tools/winbuild.py（或 ohosbuild）生成，它只认那个分离出去的 PAL runtime 副本
set(SATURN_RUNTIME "${PAL_ROOT}/build/pal-keyboard-runtime" CACHE PATH "patched runtime copy")
set(SATURN_EXTRA "${PAL_ROOT}/src/pal_game/pal_game.cmake" CACHE FILEPATH "PAL game layer")

add_subdirectory("${PAL_ROOT}/third_party/sdl3-src" sdl3)
# runtime.cmake 用 find_package(SDL3 CONFIG) 决定真 host 还是空 host，见 cmake/SDL3Config.cmake
set(SDL3_DIR "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
add_subdirectory("${PAL_ROOT}/build/recomp" saturn_recomp)
# Missing display.presentation defaults to aspect-preserving fit on OHOS only.
# An explicit user original/fit/stretch setting still wins.
target_compile_definitions(saturn_host PRIVATE PAL_OHOS_DEFAULTS=1)

# 生成工程里的 find_package(Threads) 只在它自己的目录作用域有效，壳这层要自己找一次
find_package(Threads REQUIRED)

# 鸿蒙的引导只认 libmain.so 里的 SDL_main()，而 SDL 在这条路上不给命令行。
# 所以把 runtime 的 main 改名进壳，由 pal_ohos_entry.cpp 导出 SDL_main 并从 Download 目录拼出 argv。
add_library(main SHARED ${SATURN_RUNTIME}/src/app/main.cpp pal_ohos_entry.cpp)
set_target_properties(main PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON)
set_source_files_properties("${SATURN_RUNTIME}/src/app/main.cpp" PROPERTIES COMPILE_DEFINITIONS main=saturn_main)
target_include_directories(main PRIVATE ${SATURN_RUNTIME}/include)
target_link_libraries(main PUBLIC saturn_core saturn_machine saturn_host recomp Threads::Threads SDL3::SDL3)
target_link_libraries(main PRIVATE libohenvironment.so libhilog_ndk.z.so libability_runtime.so)

# 真机自测开关：cpp/selftest.txt 写 on 就打一张合成盘（不含任何原版数据），只为在设备上看见 SDL 窗口。
set(PAL_SELFTEST_SWITCH "${CMAKE_CURRENT_SOURCE_DIR}/selftest.txt")
if(EXISTS "${PAL_SELFTEST_SWITCH}")
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${PAL_SELFTEST_SWITCH}")
    file(READ "${PAL_SELFTEST_SWITCH}" PAL_SELFTEST)
    string(STRIP "${PAL_SELFTEST}" PAL_SELFTEST)
    if(PAL_SELFTEST MATCHES "on")
        target_compile_definitions(main PRIVATE PAL_OHOS_SELFTEST=1)
        message(STATUS "PAL selftest: boot a synthetic disc on the device")
    endif()
endif()
