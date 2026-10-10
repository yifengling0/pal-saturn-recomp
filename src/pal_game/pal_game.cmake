# 仙剑土星版游戏层，由 game.toml 的 [game] cmake = ["SATURN_EXTRA=..."] 引入。
# 生成的 CMakeLists.txt 在 saturn 可执行文件定义之后 include 本文件，所以这里只往 saturn 目标加源文件。
target_sources(saturn PRIVATE ${CMAKE_CURRENT_LIST_DIR}/pal_diag.cpp)
