/* Read-only, bounded TAKP X window/property diagnosis on a private connection.
 * No focus change, warp, grab, input injection, property write or atom creation.
 * Build: cc -std=c11 -O2 -Wall -Wextra -Werror takp-window-inspect.c -lX11
 * DISPLAY/XAUTHORITY select the client display; optional argument is 1..300 s.
 */
#define _POSIX_C_SOURCE 200809L
#include <X11/Xlib.h>
#include <X11/Xatom.h>
#include <errno.h>
#include <signal.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
#include "observe-log.h"

#define INSPECT_PATH_LIMIT 16u
#define INSPECT_TREE_LIMIT 128u
#define INSPECT_PROPERTY_BYTES 128u
struct property {
    Atom type;
    int status, format;
    unsigned long count, after;
    size_t bytes;
    unsigned char value[INSPECT_PROPERTY_BYTES];
};
struct inspector {
    Display *display;
    Window root;
    Atom utf8, compound;
    struct trasc_observe_log log;
    uint64_t start_ms, snapshots, paths, candidates, tree_reads;
    int tree_done;
};
static volatile sig_atomic_t stopping;
static unsigned xerrors;
static void stop_signal(int value) { (void)value; stopping = 1; }
static void hard_timeout(int value) { (void)value; _exit(124); }
static int error_handler(Display *display, XErrorEvent *event) {
    (void)display; (void)event; xerrors++; return 0;
}
static uint64_t clock_ms(clockid_t clock) {
    struct timespec value;
    if (clock_gettime(clock, &value)) return 0;
    return (uint64_t)value.tv_sec * 1000u + (uint64_t)value.tv_nsec / 1000000u;
}
static uint64_t elapsed_ms(const struct inspector *inspector) {
    return clock_ms(CLOCK_MONOTONIC) - inspector->start_ms;
}

static struct property read_property(struct inspector *inspector, Window window, Atom atom) {
    struct property property = {.status = Success};
    unsigned char *data = NULL;
    if (atom == None) return property;
    property.status = XGetWindowProperty(inspector->display, window, atom, 0,
        INSPECT_PROPERTY_BYTES / 4u, False, AnyPropertyType, &property.type,
        &property.format, &property.count, &property.after, &data);
    if (property.status == Success && data) {
        size_t bytes = property.count * (unsigned)property.format / 8u;
        if (bytes > sizeof(property.value)) bytes = sizeof(property.value);
        if (property.format == 8) {
            memcpy(property.value, data, bytes);
            property.bytes = bytes;
        } else if (property.format == 16) {
            for (size_t i = 0; i + 1u < bytes; i += 2u) {
                unsigned value = ((unsigned short *)data)[i / 2u];
                property.value[i] = (unsigned char)value;
                property.value[i + 1u] = (unsigned char)(value >> 8);
            }
            property.bytes = bytes;
        } else if (property.format == 32) {
            /* Xlib expands 32-bit items to native unsigned long on LP64. */
            for (size_t i = 0; i + 3u < bytes; i += 4u) {
                uint32_t value = (uint32_t)((unsigned long *)data)[i / 4u];
                for (unsigned byte = 0; byte < 4; byte++)
                    property.value[i + byte] = (unsigned char)(value >> (8u * byte));
            }
            property.bytes = bytes;
        }
    }
    if (data) XFree(data);
    return property;
}
static void quote_bytes(char *quoted, size_t capacity, const unsigned char *bytes, size_t length) {
    size_t used = 0;
    if (!capacity) return;
    for (size_t i = 0; i < length; i++) {
        char escaped[8], one[2] = {(char)bytes[i], 0};
        if (!bytes[i]) strcpy(escaped, "\\u0000");
        else trasc_observe_quote(escaped, sizeof(escaped), one);
        size_t count = strlen(escaped);
        if (count >= capacity - used) break;
        memcpy(quoted + used, escaped, count); used += count;
    }
    quoted[used] = 0;
}
static int byte_match(const struct property *property, const unsigned char *expected, size_t bytes) {
    return property->status == Success && property->format == 8 && !property->after &&
           property->bytes == bytes && !memcmp(property->value, expected, bytes);
}
static int title_match(const struct property *property, int trailing_nul) {
    static const unsigned char title[] = "EqW-TAKP";
    return byte_match(property, title, sizeof(title) - (trailing_nul ? 0u : 1u));
}
static int class_match(const struct property *property, int trailing_nul) {
    static const unsigned char name[] = "eqgame.exe\0eqgame.exe\0";
    /* Two canonical terminators; optional means one extra terminal NUL. */
    return byte_match(property, name, sizeof(name) - (trailing_nul ? 0u : 1u));
}
static int eqgame_class_field(const struct property *property) {
    static const unsigned char name[] = "eqgame.exe";
    if (property->status != Success || property->format != 8) return 0;
    for (size_t start = 0; start < property->bytes;) {
        size_t end = start;
        while (end < property->bytes && property->value[end]) end++;
        if (end - start == sizeof(name) - 1u && !memcmp(property->value + start, name, sizeof(name) - 1u)) return 1;
        if (end == property->bytes) break;
        start = end + 1u;
    }
    return 0;
}
static const char *type_name(struct inspector *inspector, Atom type) {
    if (type == None) return "None";
    if (type == XA_STRING) return "STRING";
    if (type == XA_CARDINAL) return "CARDINAL";
    /* These atoms can also first appear after launch; resolve any cached miss. */
    if (inspector->utf8 == None) inspector->utf8 = XInternAtom(inspector->display, "UTF8_STRING", True);
    if (inspector->compound == None) inspector->compound = XInternAtom(inspector->display, "COMPOUND_TEXT", True);
    if (inspector->utf8 != None && type == inspector->utf8) return "UTF8_STRING";
    if (inspector->compound != None && type == inspector->compound) return "COMPOUND_TEXT";
    return "other";
}
static void report_property(struct inspector *inspector, Window window, const char *source,
                             const char *name, const struct property *property, int is_class) {
    char quoted[INSPECT_PROPERTY_BYTES * 6u + 1u], hex[INSPECT_PROPERTY_BYTES * 2u + 1u];
    quote_bytes(quoted, sizeof(quoted), property->value, property->bytes);
    for (size_t i = 0; i < property->bytes; i++) snprintf(hex + i * 2u, 3, "%02x", property->value[i]);
    hex[property->bytes * 2u] = 0;
    int exact = is_class ? class_match(property, 0) : title_match(property, 0);
    int optional_nul = is_class ? class_match(property, 1) : title_match(property, 1);
    trasc_observe_emit(&inspector->log, 0,
        "{\"record\":\"property\",\"t_ms\":%llu,\"source\":\"%s\",\"window\":%lu,\"property\":\"%s\",\"status\":%d,\"type\":%lu,\"type_name\":\"%s\",\"format\":%d,\"count\":%lu,\"after\":%lu,\"returned_bytes\":%zu,\"limit_bytes\":%u,\"raw\":\"%s\",\"hex\":\"%s\",\"bytes_exact\":%s,\"bytes_optional_terminal_nul\":%s,\"focus_guard_exact\":%s}",
        (unsigned long long)elapsed_ms(inspector), source, (unsigned long)window, name,
        property->status, (unsigned long)property->type, type_name(inspector, property->type),
        property->format, property->count, property->after, property->bytes, INSPECT_PROPERTY_BYTES,
        quoted, hex, exact ? "true" : "false", optional_nul ? "true" : "false",
        exact && property->type == XA_STRING ? "true" : "false");
}
static unsigned long window_pid(struct inspector *inspector, Window window, int *present) {
    /* This atom may not exist before Wine maps its first window. Resolve again
     * at read time without creating an atom or caching a permanent miss. */
    Atom atom = XInternAtom(inspector->display, "_NET_WM_PID", True);
    struct property property = read_property(inspector, window, atom);
    *present = property.status == Success && property.type == XA_CARDINAL && property.format == 32 &&
               property.count == 1 && property.bytes == 4 && !property.after;
    if (!*present) return 0;
    uint32_t pid = 0;
    for (unsigned i = 0; i < 4; i++) pid |= (uint32_t)property.value[i] << (i * 8u);
    return pid;
}
static void report_window(struct inspector *inspector, Window window, const char *source,
                           unsigned index, const struct property *name, const struct property *klass) {
    Window root = None, parent = None, *children = NULL;
    unsigned child_count = 0;
    Status tree_ok = XQueryTree(inspector->display, window, &root, &parent, &children, &child_count);
    if (children) XFree(children);
    XWindowAttributes attributes = {0};
    Status attributes_ok = XGetWindowAttributes(inspector->display, window, &attributes);
    int pid_present = 0;
    unsigned long pid = window_pid(inspector, window, &pid_present);
    int exact = name->type == XA_STRING && title_match(name, 0) && klass->type == XA_STRING && class_match(klass, 0);
    trasc_observe_emit(&inspector->log, 0,
        "{\"record\":\"window\",\"t_ms\":%llu,\"source\":\"%s\",\"index\":%u,\"window\":%lu,\"parent\":%lu,\"root\":%lu,\"tree_ok\":%s,\"children\":%u,\"attributes_ok\":%s,\"map_state\":%d,\"window_class\":%d,\"x\":%d,\"y\":%d,\"width\":%d,\"height\":%d,\"border\":%d,\"depth\":%d,\"pid_present\":%s,\"pid\":%lu,\"exact_identity\":%s,\"focus_guard_viewable\":%s}",
        (unsigned long long)elapsed_ms(inspector), source, index, (unsigned long)window,
        (unsigned long)parent, (unsigned long)root, tree_ok ? "true" : "false", child_count,
        attributes_ok ? "true" : "false", attributes.map_state, attributes.class,
        attributes.x, attributes.y, attributes.width, attributes.height, attributes.border_width, attributes.depth,
        pid_present ? "true" : "false", pid, exact ? "true" : "false",
        attributes_ok && attributes.map_state == IsViewable && attributes.class == InputOutput &&
        attributes.width > 0 && attributes.height > 0 ? "true" : "false");
    report_property(inspector, window, source, "WM_NAME", name, 0);
    report_property(inspector, window, source, "WM_CLASS", klass, 1);
    Atom atom = XInternAtom(inspector->display, "_NET_WM_NAME", True);
    struct property net_name = read_property(inspector, window, atom);
    report_property(inspector, window, source, "_NET_WM_NAME", &net_name, 0);
}
static void inspect_pointer_path(struct inspector *inspector) {
    Window window = inspector->root;
    unsigned reported = 0;
    int complete = 0;
    for (unsigned depth = 0; depth < INSPECT_PATH_LIMIT && !inspector->log.full && !stopping; depth++) {
        struct property name = read_property(inspector, window, XA_WM_NAME);
        struct property klass = read_property(inspector, window, XA_WM_CLASS);
        report_window(inspector, window, "pointer_path", depth, &name, &klass);
        reported++;
        Window root = None, child = None;
        int root_x = 0, root_y = 0, x = 0, y = 0;
        unsigned mask = 0;
        Bool result = XQueryPointer(inspector->display, window, &root, &child, &root_x, &root_y, &x, &y, &mask);
        if (!result || !(mask & Button3Mask)) break;
        if (child == None) { complete = 1; break; }
        if (child == window || child == inspector->root) break;
        window = child;
    }
    inspector->paths++;
    trasc_observe_emit(&inspector->log, 0,
        "{\"record\":\"path_end\",\"t_ms\":%llu,\"windows\":%u,\"limit\":%u,\"complete\":%s}",
        (unsigned long long)elapsed_ms(inspector), reported, INSPECT_PATH_LIMIT, complete ? "true" : "false");
}
static void inspect_candidates_once(struct inspector *inspector) {
    struct pending {Window window; unsigned depth;} pending[INSPECT_TREE_LIMIT];
    size_t next = 0, count = 1;
    pending[0] = (struct pending){inspector->root, 0};
    inspector->tree_done = 1;
    while (next < count && next < INSPECT_TREE_LIMIT && !stopping && !inspector->log.full) {
        struct pending entry = pending[next++];
        inspector->tree_reads++;
        struct property name = read_property(inspector, entry.window, XA_WM_NAME);
        struct property klass = read_property(inspector, entry.window, XA_WM_CLASS);
        /* Report only relevant game candidates outside the path. The bounded
         * tree walk never emits names/classes of unrelated processes. */
        if (title_match(&name, 0) || title_match(&name, 1) || eqgame_class_field(&klass)) {
            report_window(inspector, entry.window, "bounded_candidate_tree", entry.depth, &name, &klass);
            inspector->candidates++;
        }
        if (entry.depth + 1u >= INSPECT_PATH_LIMIT) continue;
        Window root = None, parent = None, *children = NULL;
        unsigned children_count = 0;
        if (XQueryTree(inspector->display, entry.window, &root, &parent, &children, &children_count)) {
            for (unsigned i = 0; i < children_count && count < INSPECT_TREE_LIMIT; i++)
                pending[count++] = (struct pending){children[i], entry.depth + 1u};
        }
        if (children) XFree(children);
    }
    trasc_observe_emit(&inspector->log, 0,
        "{\"record\":\"candidate_tree_end\",\"t_ms\":%llu,\"nodes_read\":%llu,\"nodes_enqueued\":%zu,\"node_limit\":%u,\"depth_limit\":%u,\"candidates\":%llu,\"node_limit_reached\":%s}",
        (unsigned long long)elapsed_ms(inspector), (unsigned long long)inspector->tree_reads, count,
        INSPECT_TREE_LIMIT, INSPECT_PATH_LIMIT, (unsigned long long)inspector->candidates,
        count == INSPECT_TREE_LIMIT ? "true" : "false");
}

int main(int argc, char **argv) {
    unsigned seconds = 300;
    if (argc == 2) {
        char *end = NULL;
        errno = 0;
        unsigned long value = strtoul(argv[1], &end, 10);
        if (errno || !end || *end || !value || value > 300) return 2;
        seconds = (unsigned)value;
    } else if (argc != 1) return 2;
    signal(SIGPIPE, SIG_IGN); signal(SIGINT, stop_signal); signal(SIGTERM, stop_signal);
    signal(SIGALRM, hard_timeout);
    setvbuf(stdout, NULL, _IONBF, 0);
    struct inspector inspector = {.log = {.file = stdout}, .start_ms = clock_ms(CLOCK_MONOTONIC)};
    alarm(seconds + 1u);
    trasc_observe_emit(&inspector.log, 0,
        "{\"record\":\"begin\",\"marker\":\"TRASC_TAKP_WINDOW_INSPECT_V1\",\"pid\":%ld,\"monotonic_ms\":%llu,\"epoch_ms\":%llu,\"max_seconds\":%u,\"hard_timeout_seconds\":%u,\"max_bytes\":%u,\"property_bytes\":%u,\"path_limit\":%u,\"tree_node_limit\":%u,\"poll_ms\":200,\"sample_ms\":1000,\"read_only\":true,\"changes_focus_pointer_properties\":false}",
        (long)getpid(), (unsigned long long)inspector.start_ms, (unsigned long long)clock_ms(CLOCK_REALTIME),
        seconds, seconds + 1u, TRASC_OBSERVE_MAX_BYTES, INSPECT_PROPERTY_BYTES,
        INSPECT_PATH_LIMIT, INSPECT_TREE_LIMIT);
    XSetErrorHandler(error_handler);
    inspector.display = XOpenDisplay(NULL);
    if (!inspector.display) {
        trasc_observe_emit(&inspector.log, 1, "{\"record\":\"end\",\"reason\":\"no_x_display\"}");
        return 3;
    }
    inspector.root = DefaultRootWindow(inspector.display);
    inspector.utf8 = XInternAtom(inspector.display, "UTF8_STRING", True);
    inspector.compound = XInternAtom(inspector.display, "COMPOUND_TEXT", True);
    uint64_t last_snapshot = 0;
    while (!stopping && !inspector.log.full && !inspector.log.failed && elapsed_ms(&inspector) < (uint64_t)seconds * 1000u) {
        uint64_t time = elapsed_ms(&inspector);
        if (!inspector.snapshots || time - last_snapshot >= 1000u) {
            Window focus = None, root = None, child = None;
            int revert = 0, root_x = 0, root_y = 0, x = 0, y = 0;
            unsigned mask = 0;
            XGetInputFocus(inspector.display, &focus, &revert);
            Bool result = XQueryPointer(inspector.display, inspector.root, &root, &child, &root_x, &root_y, &x, &y, &mask);
            trasc_observe_emit(&inspector.log, 0,
                "{\"record\":\"snapshot\",\"t_ms\":%llu,\"focus\":%lu,\"revert\":%d,\"pointer_ok\":%s,\"root\":%lu,\"child\":%lu,\"x\":%d,\"y\":%d,\"buttons_mask\":%u,\"rmb\":%s,\"xerrors\":%u}",
                (unsigned long long)time, (unsigned long)focus, revert, result ? "true" : "false",
                (unsigned long)root, (unsigned long)child, root_x, root_y, mask,
                mask & Button3Mask ? "true" : "false", xerrors);
            inspector.snapshots++;
            last_snapshot = time;
            if (result && mask & Button3Mask) {
                inspect_pointer_path(&inspector);
                if (!inspector.tree_done && !inspector.log.full) inspect_candidates_once(&inspector);
            }
        }
        struct timespec pause = {.tv_nsec = 200000000};
        while (!stopping && nanosleep(&pause, &pause) && errno == EINTR) {}
    }
    trasc_observe_emit(&inspector.log, 1,
        "{\"record\":\"end\",\"t_ms\":%llu,\"reason\":\"%s\",\"snapshots\":%llu,\"paths\":%llu,\"tree_nodes\":%llu,\"candidates\":%llu,\"bytes_before_end\":%zu,\"dropped\":%llu,\"xerrors\":%u}",
        (unsigned long long)elapsed_ms(&inspector), stopping ? "signal" : inspector.log.full ? "byte_limit" : inspector.log.failed ? "write_failure" : "duration",
        (unsigned long long)inspector.snapshots, (unsigned long long)inspector.paths,
        (unsigned long long)inspector.tree_reads, (unsigned long long)inspector.candidates,
        inspector.log.bytes, (unsigned long long)inspector.log.dropped, xerrors);
    XCloseDisplay(inspector.display);
    alarm(0);
    return inspector.log.failed ? 4 : 0;
}
