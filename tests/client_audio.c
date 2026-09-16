#define COBJMACROS
#include <windows.h>
#include <mmsystem.h>
#include <dsound.h>
#include <math.h>
#include <stdio.h>

/* Actual Windows waveOut and DirectSound mixers, not a bypass of Wine audio. */
int main(void) {
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
