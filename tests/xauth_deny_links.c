/* Test-only reproduction of an Android policy that denies hard-link creation.
 * Preload into xauth/Xtigervnc/Python, never package this helper in the APK. */
#include <errno.h>
#include <unistd.h>

static int denied(void) {
    static const char message[] = "TRASC test: hard-link creation denied\n";
    (void)write(STDERR_FILENO, message, sizeof(message) - 1);
    errno = EACCES;
    return -1;
}

int link(const char *old_path, const char *new_path) {
    (void)old_path;
    (void)new_path;
    return denied();
}

int linkat(int old_dir, const char *old_path, int new_dir,
           const char *new_path, int flags) {
    (void)old_dir;
    (void)old_path;
    (void)new_dir;
    (void)new_path;
    (void)flags;
    return denied();
}
