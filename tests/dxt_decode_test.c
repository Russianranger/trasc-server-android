#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../native/trasc_dxt.h"
int main(void)
{
    uint8_t b[64] = {0}, *p;
    /* Opaque RGB black is not transparent, even in the three-colour mode. */
    memset(b+4,255,4);
    p=trasc_dxt_decode(b,8,1,1,1,1);assert(p && p[0]==0 && p[3]==255);free(p);
    p=trasc_dxt_decode(b,8,1,1,1,2);assert(p && p[0]==0 && p[3]==0);free(p);
    memset(b,0,sizeof(b));b[1]=248; /* RGB565 red */
    p=trasc_dxt_decode(b,8,2,3,1,2);assert(p);
    for(int i=0;i<6;i++)assert(p[i*4]==255 && p[i*4+1]==0 && p[i*4+3]==255);free(p);
    /* DXT3 always interpolates four colours, even with reversed endpoints. */
    memset(b,0,sizeof(b));memset(b,0x88,8);b[11]=248;memset(b+12,0xff,4);
    p=trasc_dxt_decode(b,16,4,4,1,3);assert(p && p[0]==170 && p[3]==136);free(p);
    /* DXT5 endpoints and both alpha interpolation modes. */
    memset(b,0,sizeof(b));b[0]=200;b[1]=100;b[2]=2;b[9]=248;
    p=trasc_dxt_decode(b,16,1,1,1,5);assert(p && p[0]==255 && p[3]==185);free(p);
    b[0]=0;b[1]=200;b[2]=7;
    p=trasc_dxt_decode(b,16,1,1,1,5);assert(p && p[3]==255);free(p);
    b[2]=6;p=trasc_dxt_decode(b,16,1,1,1,5);assert(p && !p[3]);free(p);
    /* Non-square clipped edge blocks, and independent array slices. */
    memset(b,0,sizeof(b));for(int i=0;i<4;i++)b[i*8+1]=i<2?248:7;
    p=trasc_dxt_decode(b,32,5,3,2,2);assert(p);
    assert(p[0]==255 && p[(5*3-1)*4]==255 && p[5*3*4]==0);free(p);
    assert(!trasc_dxt_decode(b,7,4,4,1,2));
    assert(!trasc_dxt_decode(b,64,UINT_MAX,UINT_MAX,UINT_MAX,5));
    assert(!trasc_dxt_decode(b,64,4,4,0,5));
    assert(!trasc_dxt_decode(b,64,4,4,1,9));
    puts("PASS: DXT1 RGB/RGBA, DXT3/5 interpolation/alpha, clipped blocks, slices, bounds");
}
