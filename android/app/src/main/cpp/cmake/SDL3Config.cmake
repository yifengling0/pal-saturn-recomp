# SDL has already been added as a subdirectory. Do not import its own generated
# export file back into the same configure (which fails on the second build).
if(NOT TARGET SDL3::SDL3)
  message(FATAL_ERROR "Android SDL3 target missing")
endif()
set(SDL3_FOUND TRUE)
