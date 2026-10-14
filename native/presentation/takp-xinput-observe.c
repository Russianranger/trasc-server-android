/* Read-only, separate-connection X input observer for TAKP device acceptance.
 * No XTest, cursor warps, focus changes or grabs. Core events can be absent
 * while Wine owns a grab; XI2 raw events are observed independently.
 * Build: cc -std=c11 -O2 -Wall -Wextra -Werror takp-xinput-observe.c -lX11 -ldl
 * Run: DISPLAY=:33 XAUTHORITY=... takp-xinput-observe [1..300 seconds]
 * stdout is bounded JSONL (128 KiB). A private log file is the intended sink.
 */
#define _POSIX_C_SOURCE 200809L
#include <X11/Xlib.h>
#include <X11/Xatom.h>
#include <X11/extensions/XInput2.h>
#include <dlfcn.h>
#include <errno.h>
#include <math.h>
#include <poll.h>
#include <signal.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
#include "observe-log.h"

struct xi_api {
    void *library;
    int opcode, major, minor, ready;
    int (*query_version)(Display *, int *, int *);
    int (*select_events)(Display *, Window, XIEventMask *, int);
    XIDeviceInfo *(*query_device)(Display *, int, int *);
    void (*free_device_info)(XIDeviceInfo *);
    Bool (*get_client_pointer)(Display *, Window, int *);
};
struct event_rate {
    int device, source, kind;
    uint64_t since, seen, sampled;
};
struct observer {
    Display *display;
    struct xi_api xi;
    struct trasc_observe_log log;
    Window root, last_focus;
    Atom pid_atom;
    uint64_t start_ns, last_snapshot, raw_count, core_count, button_count;
    unsigned held_buttons;
    struct event_rate rates[128];
    unsigned rate_count;
};
static volatile sig_atomic_t stopping;
static unsigned xerrors;
static void stop_signal(int value) { (void)value; stopping = 1; }
/* A nonresponsive X server must not leave a diagnostic process indefinitely.
 * Normal completion emits its receipt; a hard timeout is exit status 124. */
static void hard_timeout(int value) { (void)value; _exit(124); }
static int xerror_handler(Display *display, XErrorEvent *event) {
    (void)display; (void)event; xerrors++; return 0;
}
static uint64_t now_ns(void) {
    struct timespec time;
    if (clock_gettime(CLOCK_MONOTONIC, &time)) return 0;
    return (uint64_t)time.tv_sec * 1000000000ull + (uint64_t)time.tv_nsec;
}
static uint64_t epoch_ms(void) {
    struct timespec time;
    if (clock_gettime(CLOCK_REALTIME, &time)) return 0;
    return (uint64_t)time.tv_sec * 1000ull + (uint64_t)time.tv_nsec / 1000000ull;
}
static uint64_t elapsed_ms(const struct observer *observer) {
    return (now_ns() - observer->start_ns) / 1000000ull;
}

static void open_xi(struct observer *observer) {
    struct xi_api *xi = &observer->xi;
    int event, error;
    if (!XQueryExtension(observer->display, "XInputExtension", &xi->opcode, &event, &error)) return;
    xi->library = dlopen("libXi.so.6", RTLD_NOW | RTLD_LOCAL);
    if (!xi->library) return;
    /* POSIX dlsym function pointers: memcpy avoids object/function pointer casts. */
#define LOAD_XI(member, symbol) do { \
    void *address = dlsym(xi->library, symbol); \
    _Static_assert(sizeof(address) == sizeof(xi->member), "dlsym pointer size"); \
    memcpy(&xi->member, &address, sizeof(address)); \
    if (!xi->member) return; \
} while (0)
    LOAD_XI(query_version, "XIQueryVersion");
    LOAD_XI(select_events, "XISelectEvents");
    LOAD_XI(query_device, "XIQueryDevice");
    LOAD_XI(free_device_info, "XIFreeDeviceInfo");
    LOAD_XI(get_client_pointer, "XIGetClientPointer");
#undef LOAD_XI
    /* XI 2.1 changed raw-event delivery during another client's active grab.
     * Announce 2.2 rather than silently behaving like an XI 2.0 observer. */
    xi->major = 2; xi->minor = 2;
    if (xi->query_version(observer->display, &xi->major, &xi->minor) != Success || xi->major < 2) return;
    unsigned char mask[XIMaskLen(XI_LASTEVENT)] = {0};
    XISetMask(mask, XI_RawMotion);
    XISetMask(mask, XI_RawButtonPress);
    XISetMask(mask, XI_RawButtonRelease);
    XIEventMask events = {.deviceid = XIAllMasterDevices, .mask_len = sizeof(mask), .mask = mask};
    if (xi->select_events(observer->display, observer->root, &events, 1) != Success) return;
    XSync(observer->display, False);
    xi->ready = 1;
}

static void device_inventory(struct observer *observer) {
    if (!observer->xi.ready) return;
    int count = 0;
    XIDeviceInfo *devices = observer->xi.query_device(observer->display, XIAllDevices, &count);
    if (!devices || count < 0) return;
    for (int i = 0; i < count && i < 128 && !observer->log.full; i++) {
        XIDeviceInfo *device = &devices[i];
        char name[512];
        trasc_observe_quote(name, sizeof(name), device->name);
        trasc_observe_emit(&observer->log, 0,
            "{\"record\":\"device\",\"t_ms\":%llu,\"deviceid\":%d,\"attachment\":%d,\"use\":%d,\"enabled\":%s,\"name\":\"%s\",\"classes\":%d}",
            (unsigned long long)elapsed_ms(observer), device->deviceid, device->attachment,
            device->use, device->enabled ? "true" : "false", name, device->num_classes);
        for (int j = 0; j < device->num_classes && j < 64 && !observer->log.full; j++) {
            XIAnyClassInfo *info = device->classes[j];
            if (!info || info->type != XIValuatorClass) continue;
            XIValuatorClassInfo *valuator = (XIValuatorClassInfo *)info;
            char minimum[32], maximum[32], current[32];
            if (isfinite(valuator->min)) snprintf(minimum, sizeof(minimum), "%.9g", valuator->min);
            else strcpy(minimum, "null");
            if (isfinite(valuator->max)) snprintf(maximum, sizeof(maximum), "%.9g", valuator->max);
            else strcpy(maximum, "null");
            if (isfinite(valuator->value)) snprintf(current, sizeof(current), "%.9g", valuator->value);
            else strcpy(current, "null");
            trasc_observe_emit(&observer->log, 0,
                "{\"record\":\"valuator\",\"t_ms\":%llu,\"deviceid\":%d,\"sourceid\":%d,\"axis\":%d,\"label\":%lu,\"mode\":%d,\"mode_name\":\"%s\",\"min\":%s,\"max\":%s,\"value\":%s,\"resolution\":%d}",
                (unsigned long long)elapsed_ms(observer), device->deviceid, info->sourceid,
                valuator->number, (unsigned long)valuator->label, valuator->mode,
                valuator->mode == XIModeRelative ? "relative" : valuator->mode == XIModeAbsolute ? "absolute" : "unknown",
                minimum, maximum, current, valuator->resolution);
        }
    }
    if (count > 128) trasc_observe_emit(&observer->log, 0,
        "{\"record\":\"inventory_limit\",\"devices\":%d,\"reported\":128}", count);
    observer->xi.free_device_info(devices);
}

static unsigned long window_pid(struct observer *observer, Window window) {
    if (!observer->pid_atom) return 0;
    Atom type = None;
    int format = 0;
    unsigned long count = 0, after = 0, pid = 0;
    unsigned char *data = NULL;
    if (XGetWindowProperty(observer->display, window, observer->pid_atom, 0, 1,
                           False, XA_CARDINAL, &type, &format, &count, &after, &data) == Success &&
        type == XA_CARDINAL && format == 32 && count == 1 && data) pid = *(unsigned long *)data;
    if (data) XFree(data);
    return pid;
}

/* Each selection belongs only to this observer connection. Motion/focus masks
 * are nonexclusive; no other client's selection or grab is replaced. */
static void select_core_window(struct observer *observer, Window window) {
    if (window == None || window == PointerRoot) return;
    XSelectInput(observer->display, window, PointerMotionMask | FocusChangeMask | StructureNotifyMask);
}
static void focus_ancestry(struct observer *observer, Window focus) {
    if (focus == None || focus == PointerRoot) return;
    Window window = focus;
    for (unsigned depth = 0; depth < 16; depth++) {
        Window root = None, parent = None, *children = NULL;
        unsigned count = 0;
        if (!XQueryTree(observer->display, window, &root, &parent, &children, &count)) break;
        if (children) XFree(children);
        select_core_window(observer, window);
        trasc_observe_emit(&observer->log, 0,
            "{\"record\":\"focus_ancestor\",\"t_ms\":%llu,\"depth\":%u,\"window\":%lu,\"parent\":%lu,\"root\":%lu,\"pid\":%lu}",
            (unsigned long long)elapsed_ms(observer), depth, (unsigned long)window,
            (unsigned long)parent, (unsigned long)root, window_pid(observer, window));
        if (window == root || parent == None || parent == window || observer->log.full) break;
        window = parent;
    }
}

static void snapshot(struct observer *observer) {
    Window focus = None, root = None, child = None;
    int revert = 0, root_x = 0, root_y = 0, window_x = 0, window_y = 0;
    unsigned mask = 0;
    XGetInputFocus(observer->display, &focus, &revert);
    Bool pointer_ok = XQueryPointer(observer->display, observer->root, &root, &child,
                                    &root_x, &root_y, &window_x, &window_y, &mask);
    if (pointer_ok) observer->held_buttons = mask & (Button1Mask | Button3Mask);
    int client_pointer = -1, focus_pointer = -1;
    Bool client_ok = False, focus_ok = False;
    if (observer->xi.ready) {
        client_ok = observer->xi.get_client_pointer(observer->display, None, &client_pointer);
        if (focus != None && focus != PointerRoot)
            focus_ok = observer->xi.get_client_pointer(observer->display, focus, &focus_pointer);
    }
    /* Startup/menu telemetry must leave space for the first held-look test.
     * Keep polling while idle records are suppressed; button/focus changes
     * and a later held phase still produce records within the overall cap. */
    if (observer->held_buttons || focus != observer->last_focus || observer->log.bytes < 32768u)
        trasc_observe_emit(&observer->log, 0,
        "{\"record\":\"snapshot\",\"t_ms\":%llu,\"focus\":%lu,\"revert\":%d,\"pointer_ok\":%s,\"root\":%lu,\"child\":%lu,\"x\":%d,\"y\":%d,\"buttons_mask\":%u,\"observer_pointer\":%d,\"observer_pointer_ok\":%s,\"focus_client_pointer\":%d,\"focus_client_pointer_ok\":%s,\"xerrors\":%u}",
        (unsigned long long)elapsed_ms(observer), (unsigned long)focus, revert,
        pointer_ok ? "true" : "false", (unsigned long)root, (unsigned long)child,
        root_x, root_y, mask, client_pointer, client_ok ? "true" : "false",
        focus_pointer, focus_ok ? "true" : "false", xerrors);
    if (focus != observer->last_focus) {
        focus_ancestry(observer, focus);
        observer->last_focus = focus;
    }
    select_core_window(observer, child);
    observer->last_snapshot = elapsed_ms(observer);
}

static struct event_rate *sample_rate(struct observer *observer, int kind, int device, int source) {
    struct event_rate *rate = NULL;
    for (unsigned i = 0; i < observer->rate_count; i++) {
        struct event_rate *candidate = &observer->rates[i];
        if (candidate->kind == kind && candidate->device == device && candidate->source == source) {
            rate = candidate; break;
        }
    }
    if (!rate) {
        if (observer->rate_count == 128) return NULL;
        rate = &observer->rates[observer->rate_count++];
        rate->kind = kind; rate->device = device; rate->source = source;
    }
    rate->seen++;
    uint64_t time = elapsed_ms(observer), interval = observer->held_buttons ? 200u : 1000u;
    if (rate->sampled && time - rate->since < interval) return NULL;
    rate->since = time; rate->sampled++;
    return rate;
}

static void raw_motion(struct observer *observer, const XIRawEvent *event) {
    observer->raw_count++;
    if (!observer->held_buttons && observer->log.bytes >= 32768u) return;
    struct event_rate *rate = sample_rate(observer, XI_RawMotion, event->deviceid, event->sourceid);
    if (!rate) return;
    char values[2048] = "";
    size_t used = 0;
    unsigned packed = 0, emitted = 0;
    if (event->valuators.mask_len >= 0 && event->valuators.mask_len <= 512 && event->valuators.mask &&
        event->valuators.values && event->raw_values) {
        for (int axis = 0; axis < event->valuators.mask_len * 8; axis++) {
            if (!XIMaskIsSet(event->valuators.mask, axis)) continue;
            double value = event->valuators.values[packed], raw = event->raw_values[packed++];
            if (emitted >= 16) continue;
            char cooked_text[32], raw_text[32];
            if (isfinite(value)) snprintf(cooked_text, sizeof(cooked_text), "%.9g", value);
            else strcpy(cooked_text, "null");
            if (isfinite(raw)) snprintf(raw_text, sizeof(raw_text), "%.9g", raw);
            else strcpy(raw_text, "null");
            int written = snprintf(values + used, sizeof(values) - used, "%s[%d,%s,%s]",
                                   emitted ? "," : "", axis, cooked_text, raw_text);
            if (written < 0 || (size_t)written >= sizeof(values) - used) break;
            used += (size_t)written; emitted++;
        }
    }
    trasc_observe_emit(&observer->log, 0,
        "{\"record\":\"raw_motion\",\"t_ms\":%llu,\"server_ms\":%lu,\"deviceid\":%d,\"sourceid\":%d,\"flags\":%d,\"held_mask\":%u,\"seen\":%llu,\"sampled\":%llu,\"axis_value_raw\":[%s],\"axes_total\":%u}",
        (unsigned long long)elapsed_ms(observer), (unsigned long)event->time,
        event->deviceid, event->sourceid, event->flags, observer->held_buttons,
        (unsigned long long)rate->seen, (unsigned long long)rate->sampled, values, packed);
}
static void raw_button(struct observer *observer, const XIRawEvent *event) {
    observer->button_count++;
    unsigned mask = event->detail == 1 ? Button1Mask : event->detail == 3 ? Button3Mask : 0;
    if (event->evtype == XI_RawButtonPress) observer->held_buttons |= mask;
    else observer->held_buttons &= ~mask;
    trasc_observe_emit(&observer->log, 0,
        "{\"record\":\"raw_button\",\"t_ms\":%llu,\"server_ms\":%lu,\"deviceid\":%d,\"sourceid\":%d,\"button\":%d,\"down\":%s,\"held_mask\":%u}",
        (unsigned long long)elapsed_ms(observer), (unsigned long)event->time,
        event->deviceid, event->sourceid, event->detail,
        event->evtype == XI_RawButtonPress ? "true" : "false", observer->held_buttons);
}
static void core_motion(struct observer *observer, const XMotionEvent *event) {
    observer->core_count++;
    observer->held_buttons = event->state & (Button1Mask | Button3Mask);
    if (!observer->held_buttons && observer->log.bytes >= 32768u) return;
    struct event_rate *rate = sample_rate(observer, MotionNotify, 0, 0);
    if (!rate) return;
    trasc_observe_emit(&observer->log, 0,
        "{\"record\":\"core_motion\",\"t_ms\":%llu,\"server_ms\":%lu,\"serial\":%lu,\"window\":%lu,\"root\":%lu,\"subwindow\":%lu,\"root_x\":%d,\"root_y\":%d,\"window_x\":%d,\"window_y\":%d,\"state\":%u,\"same_screen\":%s,\"send_event\":%s,\"seen\":%llu}",
        (unsigned long long)elapsed_ms(observer), (unsigned long)event->time, event->serial,
        (unsigned long)event->window, (unsigned long)event->root, (unsigned long)event->subwindow,
        event->x_root, event->y_root, event->x, event->y, event->state,
        event->same_screen ? "true" : "false", event->send_event ? "true" : "false",
        (unsigned long long)rate->seen);
}
static void consume_event(struct observer *observer, XEvent *event) {
    if (event->type == GenericEvent && observer->xi.ready && event->xcookie.extension == observer->xi.opcode) {
        if (!XGetEventData(observer->display, &event->xcookie)) return;
        if (event->xcookie.data) {
            const XIRawEvent *raw = event->xcookie.data;
            if (event->xcookie.evtype == XI_RawMotion) raw_motion(observer, raw);
            else if (event->xcookie.evtype == XI_RawButtonPress || event->xcookie.evtype == XI_RawButtonRelease)
                raw_button(observer, raw);
        }
        XFreeEventData(observer->display, &event->xcookie);
    } else if (event->type == MotionNotify) core_motion(observer, &event->xmotion);
    else if (event->type == FocusIn || event->type == FocusOut) {
        trasc_observe_emit(&observer->log, 0,
            "{\"record\":\"core_focus\",\"t_ms\":%llu,\"window\":%lu,\"in\":%s,\"mode\":%d,\"detail\":%d}",
            (unsigned long long)elapsed_ms(observer), (unsigned long)event->xfocus.window,
            event->type == FocusIn ? "true" : "false", event->xfocus.mode, event->xfocus.detail);
        snapshot(observer);
    }
}

int main(int argc, char **argv) {
    unsigned seconds = 300;
    if (argc == 2) {
        char *end = NULL;
        errno = 0;
        unsigned long parsed = strtoul(argv[1], &end, 10);
        if (errno || !end || *end || !parsed || parsed > 300) return 2;
        seconds = (unsigned)parsed;
    } else if (argc != 1) return 2;
    signal(SIGPIPE, SIG_IGN);
    signal(SIGINT, stop_signal); signal(SIGTERM, stop_signal); signal(SIGALRM, hard_timeout);
    setvbuf(stdout, NULL, _IONBF, 0);
    struct observer observer = {.log = {.file = stdout}, .last_focus = (Window)-1, .start_ns = now_ns()};
    /* Allow normal deadline polling and connection teardown one second to
     * finish; the hard limit also covers XOpenDisplay and XCloseDisplay. */
    alarm(seconds + 1u);
    trasc_observe_emit(&observer.log, 0,
        "{\"record\":\"begin\",\"marker\":\"TRASC_TAKP_XINPUT_OBSERVE_V1\",\"pid\":%ld,\"monotonic_ms\":%llu,\"epoch_ms\":%llu,\"max_seconds\":%u,\"hard_timeout_seconds\":%u,\"max_bytes\":%u,\"held_sample_ms\":200,\"idle_sample_ms\":1000,\"idle_byte_soft_limit\":32768,\"core_delivery\":\"may_be_absent_under_another_client_grab\",\"changes_focus_or_pointer\":false}",
        (long)getpid(), (unsigned long long)(observer.start_ns / 1000000ull),
        (unsigned long long)epoch_ms(), seconds, seconds + 1u, TRASC_OBSERVE_MAX_BYTES);
    XSetErrorHandler(xerror_handler);
    observer.display = XOpenDisplay(NULL);
    if (!observer.display) {
        trasc_observe_emit(&observer.log, 1, "{\"record\":\"end\",\"reason\":\"no_x_display\"}");
        return 3;
    }
    observer.root = DefaultRootWindow(observer.display);
    observer.pid_atom = XInternAtom(observer.display, "_NET_WM_PID", True);
    select_core_window(&observer, observer.root);
    open_xi(&observer);
    trasc_observe_emit(&observer.log, 0,
        "{\"record\":\"extension\",\"xi2\":%s,\"opcode\":%d,\"major\":%d,\"minor\":%d,\"requested_major\":2,\"requested_minor\":2,\"raw_grab_delivery_supported\":%s,\"xerrors\":%u}",
        observer.xi.ready ? "true" : "false", observer.xi.opcode, observer.xi.major, observer.xi.minor,
        observer.xi.ready && (observer.xi.major > 2 || observer.xi.minor >= 1) ? "true" : "false", xerrors);
    device_inventory(&observer);
    snapshot(&observer);
    while (!stopping && !observer.log.full && !observer.log.failed && elapsed_ms(&observer) < (uint64_t)seconds * 1000u) {
        unsigned drained = 0;
        while (XPending(observer.display) && drained++ < 512 && !observer.log.full && !stopping) {
            XEvent event;
            XNextEvent(observer.display, &event);
            consume_event(&observer, &event);
        }
        if (elapsed_ms(&observer) - observer.last_snapshot >= 1000u) snapshot(&observer);
        struct pollfd descriptor = {.fd = ConnectionNumber(observer.display), .events = POLLIN};
        int result = poll(&descriptor, 1, 100);
        if (result < 0 && errno != EINTR) break;
        if (result > 0 && descriptor.revents & (POLLERR | POLLHUP | POLLNVAL)) break;
    }
    trasc_observe_emit(&observer.log, 1,
        "{\"record\":\"end\",\"t_ms\":%llu,\"reason\":\"%s\",\"bytes_before_end\":%zu,\"records_before_end\":%llu,\"dropped\":%llu,\"raw_seen\":%llu,\"core_seen\":%llu,\"buttons_seen\":%llu,\"xerrors\":%u,\"sampling_is_not_complete_event_capture\":true}",
        (unsigned long long)elapsed_ms(&observer), stopping ? "signal" : observer.log.full ? "byte_limit" : observer.log.failed ? "write_failure" : "duration_or_connection_end",
        observer.log.bytes, (unsigned long long)observer.log.records, (unsigned long long)observer.log.dropped,
        (unsigned long long)observer.raw_count, (unsigned long long)observer.core_count,
        (unsigned long long)observer.button_count, xerrors);
    XCloseDisplay(observer.display);
    if (observer.xi.library) dlclose(observer.xi.library);
    alarm(0);
    return observer.log.failed ? 4 : 0;
}
