#define _POSIX_C_SOURCE 200809L
#include "frame.h"
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/extensions/XShm.h>
#include <X11/extensions/Xfixes.h>
#include <sys/ipc.h>
#include <sys/shm.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/stat.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <signal.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <sys/time.h>
static int xerror;
static int error_handler(Display *d,XErrorEvent *e){(void)d;xerror=e->error_code;return 0;}
static uint64_t now_ns(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (uint64_t)t.tv_sec*1000000000+t.tv_nsec;}
static int send_all(int fd,const void *buf,size_t n){const char *p=buf;while(n){ssize_t k=send(fd,p,n,MSG_NOSIGNAL);if(k<0&&errno==EINTR)continue;if(k<=0)return -1;p+=k;n-=(size_t)k;}return 0;}
static void cursor(Display *d,XImage *image){
    XFixesCursorImage *c=XFixesGetCursorImage(d);if(!c)return;
    int left=(int)c->x-c->xhot,top=(int)c->y-c->yhot;
    for(unsigned y=0;y<c->height;y++)for(unsigned x=0;x<c->width;x++){
        int px=left+(int)x,py=top+(int)y;if(px<0||py<0||px>=image->width||py>=image->height)continue;
        uint32_t p=(uint32_t)c->pixels[y*c->width+x],alpha=p>>24;if(!alpha)continue;
        uint32_t *dst=(uint32_t *)(image->data+py*image->bytes_per_line)+px,v=*dst,result=0;
        for(unsigned shift=0;shift<24;shift+=8){unsigned value=((p>>shift)&255)+(((v>>shift)&255)*(255-alpha)+127)/255;result|=(value>255?255:value)<<shift;}
        *dst=result;
    }XFree(c);
}
int main(int argc,char **argv){
    if(argc!=3){fprintf(stderr,"Usage: x11-frame-bridge socket fps\n");return 2;}
    int fps=atoi(argv[2]);if(fps!=30&&fps!=60)return 2;
    signal(SIGPIPE,SIG_IGN);XSetErrorHandler(error_handler);
    Display *d=XOpenDisplay(NULL);if(!d){fprintf(stderr,"No X display\n");return 3;}
    int fixes_event,fixes_error;if(!XFixesQueryExtension(d,&fixes_event,&fixes_error)){fprintf(stderr,"XFixes cursor capture required\n");return 3;}
    struct sockaddr_un addr={.sun_family=AF_UNIX};if(strlen(argv[1])>=sizeof(addr.sun_path))return 2;strcpy(addr.sun_path,argv[1]);
    int listener=socket(AF_UNIX,SOCK_STREAM,0);if(listener<0)return 4;
    umask(0077);unlink(argv[1]);if(bind(listener,(struct sockaddr *)&addr,sizeof(addr))||listen(listener,1))return 4;
    uint32_t sequence=0;fprintf(stderr,"TRASC native Surface bridge ready, cap=%d; X11 readback retained\n",fps);fflush(stderr);
    for(;;){
        int fd=accept(listener,NULL,NULL);if(fd<0){if(errno==EINTR)continue;break;}
        struct timeval timeout={.tv_sec=5};setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout));
        XImage *image=NULL;XShmSegmentInfo shm={.shmid=-1};int shared=0,lastw=0,lasth=0;uint64_t last=0;
        unsigned char request;
        while(recv(fd,&request,1,0)==1&&request==1){
            uint64_t elapsed=now_ns()-last,interval=1000000000u/(unsigned)fps;
            if(last&&elapsed<interval){struct timespec wait={.tv_nsec=(long)(interval-elapsed)};nanosleep(&wait,NULL);}last=now_ns();
            XWindowAttributes a;if(!XGetWindowAttributes(d,DefaultRootWindow(d),&a))break;
            uint32_t header[8]={TRASC_MAGIC,(uint32_t)a.width,(uint32_t)a.height,(uint32_t)a.width*4,0,++sequence,(uint32_t)a.width*a.height*4,0};
            if(!trasc_frame_valid(header))break;
            if(image&&(a.width!=lastw||a.height!=lasth)){if(shared){XShmDetach(d,&shm);XSync(d,False);shmdt(shm.shmaddr);image->data=NULL;}XDestroyImage(image);image=NULL;shared=0;}
            if(!image){
                lastw=a.width;lasth=a.height;xerror=0;
                if(XShmQueryExtension(d)){
                    image=XShmCreateImage(d,a.visual,(unsigned)a.depth,ZPixmap,NULL,&shm,(unsigned)a.width,(unsigned)a.height);
                    if(image){shm.shmid=shmget(IPC_PRIVATE,(size_t)image->bytes_per_line*image->height,IPC_CREAT|0600);
                        if(shm.shmid>=0){shm.shmaddr=shmat(shm.shmid,NULL,0);shm.readOnly=False;
                            if(shm.shmaddr!=(char *)-1){image->data=shm.shmaddr;shared=XShmAttach(d,&shm);XSync(d,False);if(xerror)shared=0;if(!shared){shmdt(shm.shmaddr);image->data=NULL;}}
                            shmctl(shm.shmid,IPC_RMID,NULL);
                        }
                        if(!shared){image->data=NULL;XDestroyImage(image);image=NULL;}
                    }
                }
            }
            uint64_t capture=now_ns();xerror=0;
            if(shared){if(!XShmGetImage(d,DefaultRootWindow(d),image,0,0,AllPlanes))break;}
            else {if(image)XDestroyImage(image);image=XGetImage(d,DefaultRootWindow(d),0,0,(unsigned)a.width,(unsigned)a.height,AllPlanes,ZPixmap);}
            if(!image||xerror||image->bits_per_pixel!=32||image->byte_order!=LSBFirst||image->red_mask!=0xff0000||image->green_mask!=0xff00||image->blue_mask!=0xff)break;
            cursor(d,image);if(xerror)break;
            header[4]=(uint32_t)((now_ns()-capture)/1000);header[7]=(uint32_t)shared;
            uint32_t wire[8];for(int i=0;i<8;i++)wire[i]=htonl(header[i]);
            if(send_all(fd,wire,sizeof(wire)))break;
            int failed=0;for(int y=0;y<a.height;y++)if(send_all(fd,image->data+y*image->bytes_per_line,(size_t)a.width*4)){failed=1;break;}if(failed)break;
        }
        if(image){if(shared){XShmDetach(d,&shm);XSync(d,False);shmdt(shm.shmaddr);image->data=NULL;}XDestroyImage(image);}
        close(fd);
    }
    close(listener);unlink(argv[1]);XCloseDisplay(d);return 0;
}
