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
        for(int i=0;i<256;i++){objects[i].pguid=&GUID_Key;objects[i].dwOfs=i;objects[i].dwType=DIDFT_BUTTON|DIDFT_MAKEINSTANCE(i);objects[i].dwFlags=0;}
        DIDATAFORMAT format={sizeof(DIDATAFORMAT),sizeof(DIOBJECTDATAFORMAT),DIDF_RELAXIS,256,256,objects};
        if(FAILED(IDirectInputDevice8_SetDataFormat(held_keyboard,&format)))return -3;
        if(FAILED(IDirectInputDevice8_SetCooperativeLevel(held_keyboard,window,DISCL_BACKGROUND|DISCL_NONEXCLUSIVE)))return -4;
    }
    BYTE keys[256]={0};IDirectInputDevice8_Acquire(held_keyboard);
    if(FAILED(IDirectInputDevice8_GetDeviceState(held_keyboard,sizeof(keys),keys)))return -5;
    return !!(keys[scan]&0x80);
}
