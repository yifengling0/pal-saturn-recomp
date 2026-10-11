# PAL game-specific compatibility sources must be attached to the actual entry target.
# Generated desktop builds use saturn; Harmony includes this again for libmain.
if(NOT DEFINED PAL_GAME_TARGET)
  set(PAL_GAME_TARGET saturn)
  set(_pal_default_target TRUE)
endif()
if(NOT TARGET ${PAL_GAME_TARGET})
  message(FATAL_ERROR "PAL game layer target does not exist: ${PAL_GAME_TARGET}")
endif()
target_sources(${PAL_GAME_TARGET} PRIVATE
  ${CMAKE_CURRENT_LIST_DIR}/pal_diag.cpp
  ${CMAKE_CURRENT_LIST_DIR}/pal_audio_stream_init.cpp)
if(_pal_default_target)
  unset(PAL_GAME_TARGET)
  unset(_pal_default_target)
endif()
