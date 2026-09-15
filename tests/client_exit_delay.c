/* CI-only native exit delay. Loaded only inside the disposable test container. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

static __thread int delayed;
__attribute__((destructor)) static void delay_exit(void) {
    const char *report=getenv("TRASC_EXIT_DELAY_REPORT");
    char name[32]={0};
    if(delayed || !report) return;
    int fd=open("/proc/self/comm",O_RDONLY);
    if(fd<0) return;
    ssize_t count=read(fd,name,sizeof(name)-1);close(fd);
    if(count<0 || strcmp(name,"cmd.exe\n")) return;
    delayed=1;
    fd=open(report,O_WRONLY|O_CREAT|O_APPEND,0644);
    if(fd<0) return;
    if(write(fd,"begin\n",6)!=6) { close(fd); return; }
    struct timespec remaining={2,0};
    while(nanosleep(&remaining,&remaining) && errno==EINTR) {}
    if(write(fd,"done\n",5)!=5) { close(fd); return; }
    close(fd);
}

__attribute__((noreturn)) void _exit(int status) {
    delay_exit();
    syscall(SYS_exit_group,status);
    __builtin_unreachable();
}
__attribute__((noreturn)) void _Exit(int status) { _exit(status); }
__attribute__((noreturn)) void exit(int status) {
    void (*real_exit)(int)=dlsym(RTLD_NEXT,"exit");
    delay_exit();
    if(real_exit) real_exit(status);
    _exit(status);
}
