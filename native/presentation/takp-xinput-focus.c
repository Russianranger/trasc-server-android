/* Restore missing X focus only for an intentional TAKP mouse-look gesture.
 * This companion changes X focus; the separate xinput observer stays read-only.
 * No cursor warps, input injection, pointer/keyboard/server grabs or properties.
 * Build: cc -std=c11 -O2 -Wall -Wextra -Werror takp-xinput-focus.c -lX11
 * Run with the current private DISPLAY/XAUTHORITY. SIGTERM ends the companion.
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

#define TRASC_FOCUS_PATH_LIMIT 16u
#define TRASC_FOCUS_REQUEST_TIMEOUT 2u
static volatile sig_atomic_t stopping;
static unsigned xerrors;
static void stop_signal(int value) { (void)value; stopping = 1; }
static void request_timeout(int value) { (void)value; _exit(124); }
static int error_handler(Display *display, XErrorEvent *event) {
    (void)display; (void)event; xerrors++; return 0;
}
static uint64_t clock_ms(clockid_t clock) {
    struct timespec value;
    if (clock_gettime(clock, &value)) return 0;
    return (uint64_t)value.tv_sec * 1000u + (uint64_t)value.tv_nsec / 1000000u;
}
static void request_begin(void) { alarm(TRASC_FOCUS_REQUEST_TIMEOUT); }
static void request_end(void) { alarm(0); }
static int unowned_focus(Display *display, Window *focus) {
    int revert = 0;
    request_begin();
    int result = XGetInputFocus(display, focus, &revert);
    request_end();
    return result && (*focus == None || *focus == PointerRoot);
}
static int pointer(Display *display, Window window, Window *child, unsigned *mask) {
    Window root = None;
    int root_x = 0, root_y = 0, x = 0, y = 0;
    request_begin();
    Bool result = XQueryPointer(display, window, &root, child, &root_x, &root_y, &x, &y, mask);
    request_end();
    return result;
}

/* Wine10 sets both WM_CLASS strings to the lowercase process basename on each
 * whole window. EQW creates the game window with the exact title EqW-TAKP.
 * Avoid unbounded XFetchName/XGetClassHint reads and deny missing properties. */
static int exact_property(Display *display, Window window, Atom property,
                          const unsigned char *expected, size_t expected_bytes) {
    Atom type = None;
    int format = 0;
    unsigned long count = 0, after = 0;
    unsigned char *data = NULL;
    request_begin();
    int result = XGetWindowProperty(display, window, property, 0, 64, False,
                                    XA_STRING, &type, &format, &count, &after, &data);
    request_end();
    int matches = result == Success && type == XA_STRING && format == 8 && !after &&
                  count == expected_bytes && data && !memcmp(data, expected, expected_bytes);
    if (data) XFree(data);
    return matches;
}
static int identity(Display *display, Window window) {
    static const unsigned char title[] = "EqW-TAKP";
    static const unsigned char class_name[] = "eqgame.exe\0eqgame.exe";
    XWindowAttributes attributes;
    request_begin();
    Status found = XGetWindowAttributes(display, window, &attributes);
    request_end();
    if (!found || attributes.map_state != IsViewable || attributes.class != InputOutput ||
        attributes.width < 1 || attributes.height < 1) return 0;
    return exact_property(display, window, XA_WM_NAME, title, sizeof(title) - 1u) &&
           exact_property(display, window, XA_WM_CLASS, class_name, sizeof(class_name));
}

/* Traverse only the pointer's actual descendant path, never a global search.
 * A game obscured by another sibling, hidden/minimized or under another
 * concrete focused window cannot become a candidate. */
static Window candidate_under_pointer(Display *display, Window root, unsigned *depth) {
    Window parent = root, candidate = None;
    unsigned mask = 0;
    for (*depth = 0; *depth < TRASC_FOCUS_PATH_LIMIT; (*depth)++) {
        Window child = None;
        if (!pointer(display, parent, &child, &mask) || !(mask & Button3Mask)) return None;
        if (child == None) return candidate;
        if (child == parent || child == root) return None;
        if (identity(display, child)) {
            /* Duplicate matching ancestors indicate unexpected hierarchy. */
            if (candidate != None) return None;
            candidate = child;
        }
        parent = child;
    }
    return None;
}

int main(int argc, char **argv) {
    (void)argv;
    if (argc != 1) return 2;
    signal(SIGPIPE, SIG_IGN);
    signal(SIGINT, stop_signal); signal(SIGTERM, stop_signal);
    signal(SIGALRM, request_timeout);
    setvbuf(stdout, NULL, _IONBF, 0);
    struct trasc_observe_log log = {.file = stdout};
    char identity_label[64];
    trasc_observe_quote(identity_label, sizeof(identity_label), "EqW-TAKP/eqgame.exe");
    uint64_t start = clock_ms(CLOCK_MONOTONIC), attempts = 0, successes = 0, last_attempt = 0;
    trasc_observe_emit(&log, 0,
        "{\"record\":\"begin\",\"marker\":\"TRASC_TAKP_X_FOCUS_RECOVERY_V1\",\"pid\":%ld,\"monotonic_ms\":%llu,\"epoch_ms\":%llu,\"max_bytes\":%u,\"poll_ms\":100,\"path_limit\":%u,\"request_timeout_seconds\":%u,\"changes_focus\":true,\"warps_grabs_injection_property_writes\":false}",
        (long)getpid(), (unsigned long long)start, (unsigned long long)clock_ms(CLOCK_REALTIME),
        TRASC_OBSERVE_MAX_BYTES, TRASC_FOCUS_PATH_LIMIT, TRASC_FOCUS_REQUEST_TIMEOUT);
    XSetErrorHandler(error_handler);
    request_begin();
    Display *display = XOpenDisplay(NULL);
    request_end();
    if (!display) {
        trasc_observe_emit(&log, 1, "{\"record\":\"end\",\"reason\":\"no_x_display\"}");
        return 3;
    }
    Window root = DefaultRootWindow(display);
    trasc_observe_emit(&log, 0, "{\"record\":\"ready\",\"root\":%lu}", (unsigned long)root);
    int last_state = -1;
    while (!stopping) {
        Window focus = None, child = None, candidate = None;
        unsigned mask = 0, depth = 0;
        int state = 0;
        if (!unowned_focus(display, &focus)) state = 1;
        else if (!pointer(display, root, &child, &mask) || !(mask & Button3Mask)) state = 2;
        else if (!(candidate = candidate_under_pointer(display, root, &depth))) state = 3;
        else {
            /* Recheck focus, physical button and exact path immediately before
             * making the only state-changing request. Bound retries to 500ms. */
            Window checked_focus = None;
            unsigned checked_depth = 0;
            uint64_t time = clock_ms(CLOCK_MONOTONIC);
            if (candidate_under_pointer(display, root, &checked_depth) != candidate) state = 3;
            else if (!unowned_focus(display, &checked_focus)) state = 1;
            else if (!pointer(display, root, &child, &mask) || !(mask & Button3Mask)) state = 2;
            else if (last_attempt && time - last_attempt < 500u) state = 4;
            else if (!stopping) {
                last_attempt = time;
                attempts++;
                unsigned errors_before = xerrors;
                request_begin();
                XSetInputFocus(display, candidate, RevertToParent, CurrentTime);
                XSync(display, False);
                request_end();
                Window after = None;
                int revert = 0;
                request_begin();
                XGetInputFocus(display, &after, &revert);
                request_end();
                int success = after == candidate && xerrors == errors_before;
                if (success) successes++;
                if (!log.full && !log.failed) trasc_observe_emit(&log, 0,
                    "{\"record\":\"focus_repair\",\"t_ms\":%llu,\"before\":%lu,\"candidate\":%lu,\"after\":%lu,\"identity\":\"%s\",\"path_depth\":%u,\"rmb\":true,\"attempt\":%llu,\"success\":%s,\"xerrors\":%u}",
                    (unsigned long long)(time - start), (unsigned long)checked_focus,
                    (unsigned long)candidate, (unsigned long)after, identity_label, checked_depth,
                    (unsigned long long)attempts, success ? "true" : "false", xerrors);
                state = success ? 5 : 6;
            }
        }
        if (state != last_state && !log.full && !log.failed) {
            static const char *states[] = {"candidate", "concrete_focus", "no_rmb", "no_exact_visible_game_under_pointer", "retry_throttled", "focus_restored", "focus_request_failed"};
            trasc_observe_emit(&log, 0,
                "{\"record\":\"gate\",\"t_ms\":%llu,\"state\":\"%s\",\"focus\":%lu,\"buttons_mask\":%u,\"candidate\":%lu,\"xerrors\":%u}",
                (unsigned long long)(clock_ms(CLOCK_MONOTONIC) - start), states[state],
                (unsigned long)focus, mask, (unsigned long)candidate, xerrors);
        }
        last_state = state;
        struct timespec pause = {.tv_nsec = 100000000};
        while (!stopping && nanosleep(&pause, &pause) && errno == EINTR) {}
    }
    trasc_observe_emit(&log, 1,
        "{\"record\":\"end\",\"t_ms\":%llu,\"attempts\":%llu,\"successes\":%llu,\"bytes_before_end\":%zu,\"dropped\":%llu,\"xerrors\":%u}",
        (unsigned long long)(clock_ms(CLOCK_MONOTONIC) - start),
        (unsigned long long)attempts, (unsigned long long)successes, log.bytes,
        (unsigned long long)log.dropped, xerrors);
    request_begin();
    XCloseDisplay(display);
    request_end();
    return 0;
}
