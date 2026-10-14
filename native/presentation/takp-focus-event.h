/* Atomic, bounded notification in the launcher's private transient session.
 * Never edit a client asset, prefix, registry or an externally linked file. */
#ifndef TRASC_TAKP_FOCUS_EVENT_H
#define TRASC_TAKP_FOCUS_EVENT_H
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define TRASC_FOCUS_EVENT_MAX_BYTES 96u
static int trasc_focus_event_config(const char *path, const char *token) {
    if (!path || path[0] != '/' || strlen(path) > 512u || !token || strlen(token) != 32u) return 0;
    for (unsigned i = 0; i < 32u; i++)
        if (!((token[i] >= '0' && token[i] <= '9') || (token[i] >= 'a' && token[i] <= 'f'))) return 0;
    return 1;
}
static int trasc_focus_event_target(const char *path) {
    struct stat value;
    if (lstat(path, &value)) return errno == ENOENT;
    if (S_ISREG(value.st_mode) && value.st_nlink == 1 && value.st_size <= TRASC_FOCUS_EVENT_MAX_BYTES) return 1;
    errno = EINVAL;
    return 0;
}
static int trasc_focus_event_write(const char *path, const char *token, unsigned long long sequence) {
    if (!trasc_focus_event_config(path, token) || !sequence) { errno = EINVAL; return 0; }
    if (!trasc_focus_event_target(path)) return 0;
    char bytes[TRASC_FOCUS_EVENT_MAX_BYTES + 1u], temporary[576];
    int size = snprintf(bytes, sizeof(bytes), "TRASCFOCUS1 %s %llu\n", token, sequence);
    int name_size = snprintf(temporary, sizeof(temporary), "%s.tmp.%ld", path, (long)getpid());
    if (size < 1 || (unsigned)size > TRASC_FOCUS_EVENT_MAX_BYTES || name_size < 1 ||
        (size_t)name_size >= sizeof(temporary)) { errno = EINVAL; return 0; }
    int file = open(temporary, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (file < 0) return 0;
    size_t used = 0;
    int ok = 1;
    while (used < (size_t)size) {
        ssize_t written = write(file, bytes + used, (size_t)size - used);
        if (written < 0 && errno == EINTR) continue;
        if (written < 1) { ok = 0; break; }
        used += (size_t)written;
    }
    /* This is transient notification, not durable user data. Close+rename
     * publishes complete bytes without waiting for a storage flush. */
    int saved_error = errno;
    if (close(file) && ok) { ok = 0; saved_error = errno; }
    if (ok && !trasc_focus_event_target(path)) { ok = 0; saved_error = errno; }
    if (ok && rename(temporary, path)) { ok = 0; saved_error = errno; }
    if (!ok) { unlink(temporary); errno = saved_error; }
    return ok;
}
#endif
