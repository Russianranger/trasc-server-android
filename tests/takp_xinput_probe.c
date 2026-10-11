/* Compile the production TRASCIN1 parser and XFlush pipeline unchanged.
 * The probe owns only its X connection and private fixture socket. */
#define _POSIX_C_SOURCE 200809L
#include <X11/Xlib.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/stat.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <stdint.h>
#include <signal.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include "../native/presentation/input.h"

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "Usage: takp-xinput-probe socket\n");
        return 2;
    }
    signal(SIGPIPE, SIG_IGN);
    return input_server(argv[1]);
}
