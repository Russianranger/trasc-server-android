/* CI-only Unix teardown delay, preloaded as x86-64 through Box64. */
#define _POSIX_C_SOURCE 200809L
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <time.h>
#include <unistd.h>

static char report[512];
__attribute__((constructor)) static void prepare_delay(void) {
    const char *path=getenv("TRASC_EXIT_DELAY_REPORT");
    if(path && strlen(path)<sizeof(report)) strcpy(report,path);
    /* The Box64 preload survives Wine's loader restart. Only cmd.exe delays. */
}
__attribute__((destructor)) static void delay_exit(void) {
    char name[16]={0};
    if(!report[0] || prctl(PR_GET_NAME,name,0,0,0) || strcmp(name,"cmd.exe")) return;
    int fd=open(report,O_WRONLY|O_CREAT|O_APPEND,0600);
    if(fd<0) return;
    if(write(fd,"begin\n",6)!=6) { close(fd); return; }
    struct timespec remaining={2,0};
    while(nanosleep(&remaining,&remaining)) {}
    if(write(fd,"done\n",5)!=5) { close(fd); return; }
    close(fd);
}
