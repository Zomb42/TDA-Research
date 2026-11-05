/* Finder entry point. Keep the runtime environment in ttk_env.sh. */
#include <mach-o/dyld.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(void) {
    char executable[PATH_MAX], resolved[PATH_MAX], launcher[PATH_MAX];
    uint32_t length = sizeof executable;
    if (_NSGetExecutablePath(executable, &length) != 0 ||
        realpath(executable, resolved) == NULL) return 1;
    /* Executable lives at project/ParaView TTK.app/Contents/MacOS/launcher. */
    for (int i = 0; i < 4; ++i) {
        char *slash = strrchr(resolved, '/');
        if (!slash) return 1;
        *slash = '\0';
    }
    int written = snprintf(launcher, sizeof launcher, "%s/Open ParaView.command", resolved);
    if (written < 0 || (size_t)written >= sizeof launcher) return 1;
    execl("/bin/sh", "sh", launcher, (char *)NULL);
    perror("Could not start ParaView TTK");
    return 1;
}
