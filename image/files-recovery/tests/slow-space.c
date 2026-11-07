// SPDX-License-Identifier: GPL-3.0-or-later
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>
#include <sys/statfs.h>
#include <sys/statvfs.h>
#include <unistd.h>
static _Atomic unsigned calls;
unsigned monet_slow_space_calls(void) { return calls; }
static void delay(void) {
    const char *armed = getenv("MONET_TEST_SLOW_SPACE");
    if (armed && strcmp(armed, "1") == 0) { ++calls; usleep(1500000); }
}
#define WRAP(name, type) \
int name(const char *path, struct type *info) { \
    static int (*real)(const char *, struct type *); \
    if (!real) real = dlsym(RTLD_NEXT, #name); \
    delay(); return real(path, info); \
}
WRAP(statfs, statfs)
WRAP(statfs64, statfs64)
WRAP(statvfs, statvfs)
WRAP(statvfs64, statvfs64)
