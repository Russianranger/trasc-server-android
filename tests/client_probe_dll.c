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
