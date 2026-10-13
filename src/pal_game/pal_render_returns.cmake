# Reject stale or altered generated render-return lowering for every platform.
# Pins cover full caller/callee bodies; only discovery's ran[] index is normalized.
# This also protects OHOS --skip-learn and direct CMake reuse of old generation.
if(NOT TARGET recomp)
  message(FATAL_ERROR "PAL render returns require actual recomp target")
endif()
get_target_property(_pal_rr_root recomp SOURCE_DIR)
get_target_property(_pal_rr_sources recomp SOURCES)
set(_pal_rr_text "")
foreach(_pal_rr_source IN LISTS _pal_rr_sources)
  if(_pal_rr_source MATCHES "(^|/)p_(prog|true)_[0-9]+\\.cpp$")
    get_filename_component(_pal_rr_path "${_pal_rr_source}" ABSOLUTE BASE_DIR "${_pal_rr_root}")
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${_pal_rr_path}")
    file(READ "${_pal_rr_path}" _pal_rr_part)
    string(APPEND _pal_rr_text "${_pal_rr_part}\n")
  endif()
endforeach()
string(REPLACE "\r\n" "\n" _pal_rr_text "${_pal_rr_text}")
foreach(_pal_rr_pair IN ITEMS
  "06038F14|d405763d1e1fa791f7ba46c6792f6e029a3bdbe553eb34d299411d24c7d1a12c|d405763d1e1fa791f7ba46c6792f6e029a3bdbe553eb34d299411d24c7d1a12c"
  "06038F72|31a0c140499991d7e28a73f056445a807e5403b5b26f379b765c9a0cc02ad08d|31a0c140499991d7e28a73f056445a807e5403b5b26f379b765c9a0cc02ad08d"
  "06038FD8|168358b1e1e4afbca8a2b5e053645699e889f928ddf6a92c7db8bb318b228ba8|168358b1e1e4afbca8a2b5e053645699e889f928ddf6a92c7db8bb318b228ba8"
  "0605E398|039bd97866f078aba00915a27612138ed049024d31bc1ee2a8a8c4fe1cf567bb|e8f997505612a6e9c70ece0a6d1adf8444cd3eb5377828f61078656f9103bec9"
  "06060870|6380091000848413485460b0dd2443e405aa01c9329276bbe1a1e05c50225ecb|6380091000848413485460b0dd2443e405aa01c9329276bbe1a1e05c50225ecb"
  "06065DC8|789645639e556af6de295fc79d93141a02471eec4c862cac1f225002e6d1a865|789645639e556af6de295fc79d93141a02471eec4c862cac1f225002e6d1a865"
  "06065E26|97ba6884d55172a96d5bf66857c1270764074d2163b37d6c9ae767bc7bc17c0d|97ba6884d55172a96d5bf66857c1270764074d2163b37d6c9ae767bc7bc17c0d"
  "06065E8C|f1302823c3ab94dd4f92943a62c4264a3cbc31f9d37ef9f85a67cd5c22160815|f1302823c3ab94dd4f92943a62c4264a3cbc31f9d37ef9f85a67cd5c22160815"
 )
  string(REPLACE "|" ";" _pal_rr_fields "${_pal_rr_pair}")
  list(GET _pal_rr_fields 0 _pal_rr_address)
  list(GET _pal_rr_fields 1 _pal_rr_expected)
  list(GET _pal_rr_fields 2 _pal_rr_probe_expected)
  set(_pal_rr_marker "void f_${_pal_rr_address}(SH2Context& c) {\n")
  string(FIND "${_pal_rr_text}" "${_pal_rr_marker}" _pal_rr_start)
  if(_pal_rr_start EQUAL -1)
    message(FATAL_ERROR "PAL render return function missing: ${_pal_rr_address}; regenerate game code")
  endif()
  string(SUBSTRING "${_pal_rr_text}" ${_pal_rr_start} -1 _pal_rr_tail)
  string(FIND "${_pal_rr_tail}" "\n}" _pal_rr_end)
  math(EXPR _pal_rr_length "${_pal_rr_end} + 2")
  string(SUBSTRING "${_pal_rr_tail}" 0 ${_pal_rr_length} _pal_rr_body)
  string(REGEX REPLACE "ran\\[[0-9]+\\]" "ran[INDEX]" _pal_rr_body "${_pal_rr_body}")
  string(SHA256 _pal_rr_actual "${_pal_rr_body}")
  if(NOT _pal_rr_actual STREQUAL _pal_rr_expected AND NOT _pal_rr_actual STREQUAL _pal_rr_probe_expected)
    message(FATAL_ERROR "PAL render return lowering stale/altered at ${_pal_rr_address}; regenerate game code with current tools (do not reuse old --skip-learn output)")
  endif()
  string(SUBSTRING "${_pal_rr_tail}" ${_pal_rr_length} -1 _pal_rr_rest)
  string(FIND "${_pal_rr_rest}" "${_pal_rr_marker}" _pal_rr_duplicate)
  if(NOT _pal_rr_duplicate EQUAL -1)
    message(FATAL_ERROR "PAL render return function duplicated: ${_pal_rr_address}")
  endif()
endforeach()
