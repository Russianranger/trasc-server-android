#define COBJMACROS
#define DIRECTINPUT_VERSION 0x0800
#include <windows.h>
#include <dinput.h>

// Our own proxy fixture: reproduce the modified client's absolute system-DLL
// load during DllMain, then actually create DirectInput keyboard/mouse devices.
static HMODULE system_dinput;
BOOL WINAPI DllMain(HINSTANCE instance,DWORD reason,LPVOID reserved) {
    if(reason==DLL_PROCESS_ATTACH) {
        WCHAR path[MAX_PATH];UINT size=GetSystemDirectoryW(path,MAX_PATH);
        if(size&&size<MAX_PATH-13) {
            lstrcatW(path,L"\\dinput8.dll");system_dinput=LoadLibraryW(path);
        }
    }
    return TRUE;
}
__declspec(dllexport) int TrascProbe(void) {
    typedef HRESULT (WINAPI *CreateInput)(HINSTANCE,DWORD,REFIID,LPVOID*,LPUNKNOWN);
    CreateInput create=system_dinput?(void*)GetProcAddress(system_dinput,"DirectInput8Create"):NULL;
    IDirectInput8A *input=NULL;IDirectInputDevice8A *keyboard=NULL,*mouse=NULL;
    if(!create||FAILED(create(GetModuleHandle(NULL),DIRECTINPUT_VERSION,&IID_IDirectInput8A,(void**)&input,NULL)))return 0;
    HRESULT keys=IDirectInput8_CreateDevice(input,&GUID_SysKeyboard,&keyboard,NULL);
    HRESULT pointer=IDirectInput8_CreateDevice(input,&GUID_SysMouse,&mouse,NULL);
    if(keyboard)IDirectInputDevice8_Release(keyboard);
    if(mouse)IDirectInputDevice8_Release(mouse);
    IDirectInput8_Release(input);
    return SUCCEEDED(keys)&&SUCCEEDED(pointer)?0x54524153:0;
}

static IDirectInput8A *held_input;
static IDirectInputDevice8A *held_keyboard;
__declspec(dllexport) int TrascHeldKey(HWND window,int scan) {
    if(!held_keyboard) {
        typedef HRESULT (WINAPI *CreateInput)(HINSTANCE,DWORD,REFIID,LPVOID*,LPUNKNOWN);
        CreateInput create=system_dinput?(void*)GetProcAddress(system_dinput,"DirectInput8Create"):NULL;
        if(!create||FAILED(create(GetModuleHandle(NULL),DIRECTINPUT_VERSION,&IID_IDirectInput8A,(void**)&held_input,NULL)))return -1;
        if(FAILED(IDirectInput8_CreateDevice(held_input,&GUID_SysKeyboard,&held_keyboard,NULL)))return -2;
        DIOBJECTDATAFORMAT objects[256];
        for(int i=0;i<256;i++){objects[i].pguid=&GUID_Key;objects[i].dwOfs=i;objects[i].dwType=DIDFT_OPTIONAL|DIDFT_BUTTON|DIDFT_MAKEINSTANCE(i);objects[i].dwFlags=0;}
        DIDATAFORMAT format={sizeof(DIDATAFORMAT),sizeof(DIOBJECTDATAFORMAT),DIDF_RELAXIS,256,256,objects};
        if(FAILED(IDirectInputDevice8_SetDataFormat(held_keyboard,&format)))return -3;
        if(FAILED(IDirectInputDevice8_SetCooperativeLevel(held_keyboard,window,DISCL_BACKGROUND|DISCL_NONEXCLUSIVE)))return -4;
    }
    BYTE keys[256]={0};IDirectInputDevice8_Acquire(held_keyboard);
    if(FAILED(IDirectInputDevice8_GetDeviceState(held_keyboard,sizeof(keys),keys)))return -5;
    return !!(keys[scan]&0x80);
}

static IDirectInputDevice8A *relative_mouse;
void TrascCameraRead(void *, HRESULT, void *);
__declspec(dllexport) int TrascMouseDelta(HWND window,LONG *dx,LONG *buffered) {
    if(!relative_mouse){
        if(!held_input)return -1;
        if(FAILED(IDirectInput8_CreateDevice(held_input,&GUID_SysMouse,&relative_mouse,NULL)))return -2;
        DIOBJECTDATAFORMAT objects[11]={0};
        const GUID *axes[]={&GUID_XAxis,&GUID_YAxis,&GUID_ZAxis};
        for(int i=0;i<3;i++){objects[i].pguid=axes[i];objects[i].dwOfs=i*4;objects[i].dwType=DIDFT_RELAXIS|DIDFT_MAKEINSTANCE(i);}
        for(int i=0;i<8;i++){objects[i+3].pguid=&GUID_Button;objects[i+3].dwOfs=12+i;objects[i+3].dwType=DIDFT_OPTIONAL|DIDFT_BUTTON|DIDFT_MAKEINSTANCE(i);}
        DIDATAFORMAT format={sizeof(DIDATAFORMAT),sizeof(DIOBJECTDATAFORMAT),DIDF_RELAXIS,sizeof(DIMOUSESTATE2),11,objects};
        if(FAILED(IDirectInputDevice8_SetDataFormat(relative_mouse,&format)))return -3;
        DIPROPDWORD size={{sizeof(DIPROPDWORD),sizeof(DIPROPHEADER),0,DIPH_DEVICE},512};
        if(FAILED(IDirectInputDevice8_SetProperty(relative_mouse,DIPROP_BUFFERSIZE,&size.diph)))return -6;
        if(FAILED(IDirectInputDevice8_SetCooperativeLevel(relative_mouse,window,DISCL_FOREGROUND|DISCL_NONEXCLUSIVE)))return -4;
    }
    DIMOUSESTATE2 state={0};IDirectInputDevice8_Acquire(relative_mouse);
    HRESULT polled=IDirectInputDevice8_GetDeviceState(relative_mouse,sizeof(state),&state);
    if(FAILED(polled))return -5;
    TrascCameraRead(relative_mouse,polled,&state);
    *dx=state.lX;*buffered=0;
    DIDEVICEOBJECTDATA events[512];DWORD count=512;
    HRESULT result=IDirectInputDevice8_GetDeviceData(relative_mouse,sizeof(events[0]),events,&count,0);
    if(FAILED(result)||result==DI_BUFFEROVERFLOW)return -7;
    for(DWORD i=0;i<count;i++)if(events[i].dwOfs==DIMOFS_X)*buffered+=(LONG)events[i].dwData;
    return 0;
}
