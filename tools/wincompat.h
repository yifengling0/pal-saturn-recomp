/* Windows test shim, force-included only by tools/check_windows.sh's runtime-test build.
 *
 * runtime/tests/bup_test.cpp points the save directory at a scratch folder with POSIX setenv() and
 * passes dir.c_str(): MinGW has no setenv at all, and std::filesystem::path::value_type is
 * wchar_t there, so the call is (const char*, const wchar_t*, int). The runtime also reads
 * %APPDATA% rather than XDG_DATA_HOME on Windows (runtime/src/machine/bios.cpp: sat_data_dir), so
 * XDG_DATA_HOME alone would leave those two tests checking a directory this platform never uses.
 * Both are set, which keeps the tests testing the branch Windows actually takes.
 * Nothing in the recompiler or the runtime depends on this file. */
#ifdef _WIN32
#include <stdlib.h>
#include <string.h>
#include <windows.h>

static inline int win_setenv(const char *name, const char *value, int overwrite) {
    if (!overwrite && getenv(name) != NULL) return 0;
    if (_putenv_s(name, value) != 0) return -1;
    if (strcmp(name, "XDG_DATA_HOME") == 0 && _putenv_s("APPDATA", value) != 0) return -1;
    return 0;
}

static inline int win_setenv(const char *name, const wchar_t *value, int overwrite) {
    char buf[4096];
    if (WideCharToMultiByte(CP_UTF8, 0, value, -1, buf, sizeof buf, NULL, NULL) <= 0) return -1;
    return win_setenv(name, buf, overwrite);
}

#define setenv win_setenv
#endif
