# 壳层的 add_subdirectory(third_party/sdl3-src) 已经把 SDL3::SDL3 定义好了；
# runtime.cmake 只认 find_package(SDL3 CONFIG) 的结果来决定用 host.cpp 还是 host_null.cpp，
# 所以这里补一份"已找到"的凭据。交叉编译没有 install 步骤，也就没有官方 SDL3Config.cmake。
if(NOT TARGET SDL3::SDL3)
    set(SDL3_FOUND FALSE)
    message(STATUS "SDL3Config: SDL3::SDL3 还没定义，先 add_subdirectory(sdl3-src)")
else()
    set(SDL3_FOUND TRUE)
endif()
