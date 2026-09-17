#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
static unsigned char received[1280*720*4];
static size_t received_size,first_request,chunk_limit;
static int interrupt_once,broken;
static ssize_t capture_send(int fd,const void *data,size_t count,int flags){
    (void)fd;(void)flags;if(!first_request)first_request=count;
    if(interrupt_once){interrupt_once=0;errno=EINTR;return -1;}
    if(broken){errno=EPIPE;return -1;}
    if(chunk_limit&&count>chunk_limit)count=chunk_limit;
    assert(received_size+count<=sizeof(received));memcpy(received+received_size,data,count);received_size+=count;return (ssize_t)count;
}
#define TRASC_SEND capture_send
#include "../native/presentation/transfer.h"
int main(void){
    unsigned char *pixels=malloc(sizeof(received)),*scratch=NULL;size_t capacity=0;uint64_t calls=0;
    assert(pixels);for(size_t i=0;i<sizeof(received);i++)pixels[i]=(unsigned char)(i*17);
    assert(!trasc_send_pixels(0,pixels,1280*4,1280*4,720,&scratch,&capacity,&calls));
    assert(calls==1&&first_request==sizeof(received)&&!scratch&&received_size==sizeof(received)&&!memcmp(received,pixels,sizeof(received)));
    unsigned char padded[]={1,2,3,4,99,99,5,6,7,8,99,99};
    calls=0;received_size=first_request=0;chunk_limit=3;interrupt_once=1;
    assert(!trasc_send_pixels(0,padded,4,6,2,&scratch,&capacity,&calls));
    assert(first_request==8&&calls==4&&received_size==8&&!memcmp(received,(unsigned char[]){1,2,3,4,5,6,7,8},8));
    broken=1;assert(trasc_send_pixels(0,padded,4,6,2,&scratch,&capacity,&calls)==-1);
    assert(trasc_send_pixels(0,padded,8,6,2,&scratch,&capacity,&calls)==-1);
    assert(trasc_send_pixels(0,padded,4,SIZE_MAX,2,&scratch,&capacity,&calls)==-1);
    free(scratch);free(pixels);puts("PASS: one packed 720p payload, padded-row packing, partial writes, EINTR and peer-close handling");return 0;
}
