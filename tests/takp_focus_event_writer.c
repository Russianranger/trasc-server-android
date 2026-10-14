#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdlib.h>
#include "../native/presentation/takp-focus-event.h"

static void contents(const char *path, const char *expected) {
    char bytes[128] = {0};
    int file = open(path, O_RDONLY | O_NOFOLLOW); assert(file >= 0);
    ssize_t length = read(file, bytes, sizeof(bytes)); assert(length >= 0);
    assert(close(file) == 0);
    assert((size_t)length == strlen(expected) && !memcmp(bytes, expected, (size_t)length));
}
int main(void) {
    char directory[] = "/tmp/trasc-focus-event-XXXXXX";
    assert(mkdtemp(directory));
    char path[256], other[256], temporary[288];
    assert(snprintf(path, sizeof(path), "%s/event", directory) > 0);
    assert(snprintf(other, sizeof(other), "%s/linked", directory) > 0);
    assert(snprintf(temporary, sizeof(temporary), "%s.tmp.%ld", path, (long)getpid()) > 0);
    const char *token = "0123456789abcdef0123456789abcdef";
    const char *first = "TRASCFOCUS1 0123456789abcdef0123456789abcdef 1\n";
    const char *second = "TRASCFOCUS1 0123456789abcdef0123456789abcdef 2\n";
    assert(trasc_focus_event_write(path, token, 1)); contents(path, first);
    struct stat value; assert(!lstat(path, &value));
    assert((value.st_mode & 0777) == 0600 && value.st_nlink == 1);
    int previous = open(path, O_RDONLY | O_NOFOLLOW); assert(previous >= 0);
    assert(trasc_focus_event_write(path, token, 2)); contents(path, second);
    char old[128] = {0}; ssize_t count = read(previous, old, sizeof(old)); assert(count > 0);
    assert((size_t)count == strlen(first) && !memcmp(old, first, (size_t)count)); assert(!close(previous));
    assert(!trasc_focus_event_write(path, token, 0)); contents(path, second);
    assert(!trasc_focus_event_write(path, "0123456789abcdef0123456789abcdeg", 3)); contents(path, second);
    assert(!trasc_focus_event_write("relative", token, 3));
    assert(!link(path, other)); assert(!trasc_focus_event_write(path, token, 3)); contents(path, second);
    assert(!unlink(other));
    assert(!rename(path, other)); assert(!symlink(other, path));
    assert(!trasc_focus_event_write(path, token, 3)); contents(other, second);
    assert(!unlink(path)); assert(!unlink(other));
    assert(!mkfifo(path, 0600)); assert(!trasc_focus_event_write(path, token, 3)); assert(!unlink(path));
    int file = open(path, O_WRONLY | O_CREAT | O_EXCL, 0600); assert(file >= 0);
    char oversized[97] = {0}; assert(write(file, oversized, sizeof(oversized)) == (ssize_t)sizeof(oversized)); assert(!close(file));
    assert(!trasc_focus_event_write(path, token, 3)); assert(!unlink(path));
    file = open(temporary, O_WRONLY | O_CREAT | O_EXCL, 0600); assert(file >= 0);
    assert(write(file, "private existing", 16) == 16); assert(!close(file));
    assert(!trasc_focus_event_write(path, token, 3)); contents(temporary, "private existing");
    assert(!unlink(temporary)); assert(!rmdir(directory));
    puts("PASS: bounded canonical focus event, atomic readers, private permissions and link/type/temp refusal");
    return 0;
}
