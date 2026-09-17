#include "../native/presentation/frame.h"
#include <assert.h>
#include <stdio.h>
int main(void){
    uint32_t h[]={TRASC_MAGIC,1280,720,5120,123,4,3686400,1};assert(trasc_frame_valid(h));
    h[1]=0;assert(!trasc_frame_valid(h));h[1]=1280;h[6]--;assert(!trasc_frame_valid(h));h[6]++;h[3]=0;assert(!trasc_frame_valid(h));
    uint32_t pixels[]={0x00184860,0x00ff0000,0x0000ff00,0x000000ff},out[6]={0};out[0]=out[5]=0xfeedface;
    trasc_bgra_rgba(out+1,pixels,4);assert(out[0]==0xfeedface&&out[5]==0xfeedface);
    assert(out[1]==0xff604818&&out[2]==0xff0000ff&&out[3]==0xff00ff00&&out[4]==0xffff0000);
    puts("PASS: bounded native frame headers, RGBA colors, opaque alpha and row bounds");return 0;
}
