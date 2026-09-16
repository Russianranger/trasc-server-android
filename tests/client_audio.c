#define COBJMACROS
#include <windows.h>
#include <mmsystem.h>
#include <dsound.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

/* Short positional effects must produce their own PCM, independently of music.
 * Use the legacy mono/8-bit/22050 Hz format as well as deferred 3D settings. */
static int spatial(void) {
    IDirectSound *sound=NULL; IDirectSoundBuffer *primary=NULL,*buffer=NULL;
    IDirectSound3DListener *listener=NULL; IDirectSound3DBuffer *position=NULL;
    HRESULT hr;
    #define CHECK(call,code) do { hr=(call); if(FAILED(hr)){printf("3D failure %d hr=%08lx\n",code,(unsigned long)hr);return code;} } while(0)
    CHECK(DirectSoundCreate(NULL,&sound,NULL),30);
    CHECK(IDirectSound_SetCooperativeLevel(sound,GetDesktopWindow(),DSSCL_PRIORITY),31);
    DSBUFFERDESC desc={0}; desc.dwSize=sizeof(desc); desc.dwFlags=DSBCAPS_PRIMARYBUFFER|DSBCAPS_CTRL3D;
    CHECK(IDirectSound_CreateSoundBuffer(sound,&desc,&primary,NULL),32);
    CHECK(IDirectSoundBuffer_QueryInterface(primary,&IID_IDirectSound3DListener,(void **)&listener),33);
    WAVEFORMATEX format={WAVE_FORMAT_PCM,1,22050,22050,1,8,0};
    desc.dwFlags=DSBCAPS_CTRL3D|DSBCAPS_CTRLVOLUME|DSBCAPS_GLOBALFOCUS;
    desc.dwBufferBytes=11025; desc.lpwfxFormat=&format;
    CHECK(IDirectSound_CreateSoundBuffer(sound,&desc,&buffer,NULL),34);
    CHECK(IDirectSoundBuffer_QueryInterface(buffer,&IID_IDirectSound3DBuffer,(void **)&position),35);
    void *data=NULL; DWORD bytes=0;
    CHECK(IDirectSoundBuffer_Lock(buffer,0,desc.dwBufferBytes,&data,&bytes,NULL,NULL,0),36);
    for(DWORD i=0;i<bytes;i++)((unsigned char *)data)[i]=(unsigned char)(128+sin(i*6.28318530718*523.25/22050)*90);
    CHECK(IDirectSoundBuffer_Unlock(buffer,data,bytes,NULL,0),37);
    CHECK(IDirectSound3DListener_SetPosition(listener,0,0,0,DS3D_DEFERRED),38);
    CHECK(IDirectSound3DListener_SetOrientation(listener,0,0,1,0,1,0,DS3D_DEFERRED),39);
    CHECK(IDirectSound3DBuffer_SetMinDistance(position,1,DS3D_DEFERRED),40);
    CHECK(IDirectSound3DBuffer_SetMaxDistance(position,100,DS3D_DEFERRED),41);
    for(int i=0;i<3;i++) {
        CHECK(IDirectSound3DBuffer_SetPosition(position,(float)(i-1),0,1,DS3D_DEFERRED),42);
        CHECK(IDirectSound3DListener_CommitDeferredSettings(listener),43);
        CHECK(IDirectSoundBuffer_SetCurrentPosition(buffer,0),44);
        CHECK(IDirectSoundBuffer_Play(buffer,0,0,0),45);
        Sleep(800);
        CHECK(IDirectSoundBuffer_Stop(buffer),46);
    }
    IDirectSound3DBuffer_Release(position); IDirectSoundBuffer_Release(buffer);
    IDirectSound3DListener_Release(listener); IDirectSoundBuffer_Release(primary); IDirectSound_Release(sound);
    puts("PASS: three independent mono 8-bit positional effects completed"); return 0;
    #undef CHECK
}

static int legacy_math(void) {
    /* Keep the intermediate on the x87 stack: 32-bit float loses the +1.
     * This is a math contract, not a reproduction of the proprietary label. */
    float large=16777216.0f,one=1.0f; double result=0;
    unsigned short original,precise;
    __asm__ volatile("fnstcw %0" : "=m"(original));
    precise=(original & ~0x0300u)|0x0200u;
    __asm__ volatile("fldcw %0" : : "m"(precise));
    for(int i=0;i<10000;i++) {
        __asm__ volatile("flds %1; fadds %2; fsubs %1; fstpl %0" : "=m"(result) : "m"(large),"m"(one) : "st");
        if(result!=1.0) {printf("x87 retained intermediate: %.17g expected 1\n",result);return 50;}
    }
    __asm__ volatile("fldcw %0" : : "m"(original));
    puts("PASS: legacy x87 double intermediates retained");return 0;
}

/* Actual Windows waveOut and DirectSound mixers, not a bypass of Wine audio. */
int main(int argc,char **argv) {
    if(argc>1 && !strcmp(argv[1],"--spatial"))return spatial();
    if(argc>1 && !strcmp(argv[1],"--legacy-math"))return legacy_math();
    WAVEFORMATEX mono = {WAVE_FORMAT_PCM,1,22050,44100,2,16,0};
    short samples[11025];
    for (int i=0;i<11025;i++) samples[i]=(short)(sin(i*6.28318530718*440/22050)*12000);
    HWAVEOUT wave; MMRESULT result=waveOutOpen(&wave,WAVE_MAPPER,&mono,0,0,CALLBACK_NULL);
    if(result){printf("waveOutOpen=%u\n",result);return 10;}
    WAVEHDR header={0};header.lpData=(char *)samples;header.dwBufferLength=sizeof(samples);
    if(waveOutPrepareHeader(wave,&header,sizeof(header))||waveOutWrite(wave,&header,sizeof(header)))return 11;
    DWORD deadline=GetTickCount()+5000;
    while(!(header.dwFlags&WHDR_DONE)&&GetTickCount()<deadline)Sleep(10);
    if(!(header.dwFlags&WHDR_DONE))return 12;
    waveOutUnprepareHeader(wave,&header,sizeof(header));waveOutClose(wave);
    IDirectSound *sound=NULL;IDirectSoundBuffer *buffer=NULL;
    if(FAILED(DirectSoundCreate(NULL,&sound,NULL)))return 20;
    if(FAILED(IDirectSound_SetCooperativeLevel(sound,GetDesktopWindow(),DSSCL_NORMAL)))return 21;
    WAVEFORMATEX stereo={WAVE_FORMAT_PCM,2,48000,192000,4,16,0};
    DSBUFFERDESC desc={0};desc.dwSize=sizeof(desc);desc.dwBufferBytes=48000*4/2;desc.lpwfxFormat=&stereo;desc.dwFlags=DSBCAPS_GLOBALFOCUS;
    if(FAILED(IDirectSound_CreateSoundBuffer(sound,&desc,&buffer,NULL)))return 22;
    void *data=NULL;DWORD bytes=0;
    if(FAILED(IDirectSoundBuffer_Lock(buffer,0,desc.dwBufferBytes,&data,&bytes,NULL,NULL,0)))return 23;
    for(DWORD i=0;i<bytes/4;i++){((short *)data)[i*2]=(short)(sin(i*6.28318530718*660/48000)*12000);((short *)data)[i*2+1]=(short)(sin(i*6.28318530718*880/48000)*12000);}
    IDirectSoundBuffer_Unlock(buffer,data,bytes,NULL,0);
    if(FAILED(IDirectSoundBuffer_Play(buffer,0,0,0)))return 24;
    Sleep(800);IDirectSoundBuffer_Stop(buffer);IDirectSoundBuffer_Release(buffer);IDirectSound_Release(sound);
    puts("PASS: Windows mono waveOut and stereo DirectSound playback completed");return 0;
}
