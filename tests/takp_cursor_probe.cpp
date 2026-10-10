// Open Wine/Xvnc fixture: cached cursor race plus real polled and buffered
// DirectInput during v1 recenter and v2 raw look. No game code/assets.
#define DIRECTINPUT_VERSION 0x0800
#include <windows.h>
#include <dinput.h>
#include <cstdio>
#include <cstring>
#include "../native/takp_camera_recenter.h"

static IDirectInputDevice8A* mouse;
static HWND game_window;
static volatile LONG mode=0; // free=0, v1 warp=1, v2 clip=2, exit=-1
static LONG totals[4],buttons;
static CRITICAL_SECTION clip_lock;
static trasc_takp_camera::LookClip clip;
static bool get_clip(trasc_takp_camera::Rect& value) {
    RECT rect;if(!GetClipCursor(&rect))return false;
    value={rect.left,rect.top,rect.right,rect.bottom};return true;
}
static bool set_clip(const trasc_takp_camera::Rect& value) {
    RECT rect={value.left,value.top,value.right,value.bottom};return ClipCursor(&rect)!=0;
}
static void release_clip(){EnterCriticalSection(&clip_lock);clip.release(get_clip,set_clip);LeaveCriticalSection(&clip_lock);}
static void hold_clip(){EnterCriticalSection(&clip_lock);clip.hold(400,300,{0,0,800,600},get_clip,set_clip);LeaveCriticalSection(&clip_lock);}
static LRESULT CALLBACK window_proc(HWND window,UINT message,WPARAM wparam,LPARAM lparam) {
    if(message==WM_RBUTTONUP||message==WM_KILLFOCUS||(message==WM_ACTIVATEAPP&&!wparam)||
       (message==WM_SIZE&&wparam==SIZE_MINIMIZED)||message==WM_CLOSE||message==WM_DESTROY) release_clip();
    return DefWindowProcA(window,message,wparam,lparam);
}
static DWORD WINAPI input_frame(void*) {
    while(mode>=0) {
        if(mode==2 && GetForegroundWindow()==game_window && !IsIconic(game_window) && (GetAsyncKeyState(VK_RBUTTON)&0x8000))hold_clip();else release_clip();
        DIMOUSESTATE2 state={};mouse->Acquire();
        if(SUCCEEDED(mouse->GetDeviceState(sizeof(state),&state))) {
            InterlockedExchangeAdd(totals,state.lX);InterlockedExchangeAdd(totals+1,state.lY);
            InterlockedExchange(&buttons,state.rgbButtons[1]!=0);
        }
        DIDEVICEOBJECTDATA events[256];DWORD count=256;
        HRESULT hr=mouse->GetDeviceData(sizeof(events[0]),events,&count,0);
        if(hr==DIERR_NOTACQUIRED||hr==DIERR_INPUTLOST)count=0; // expected foreground loss
        else if(FAILED(hr)||hr==DI_BUFFEROVERFLOW)ExitProcess(21);
        for(DWORD i=0;i<count;i++) {
            if(events[i].dwOfs==DIMOFS_X)InterlockedExchangeAdd(totals+2,(LONG)events[i].dwData);
            if(events[i].dwOfs==DIMOFS_Y)InterlockedExchangeAdd(totals+3,(LONG)events[i].dwData);
        }
        if(mode==1 && (GetAsyncKeyState(VK_RBUTTON)&0x8000))trasc_takp_camera::legacy_center(400,300,0,800,[](int x,int y){return SetCursorPos(x,y);});
        Sleep(5);
    }
    release_clip();return 0;
}
static void result(const char *value) {
    FILE *file=std::fopen("D:\\reply.tmp","wb");if(!file)ExitProcess(12);
    std::fputs(value,file);std::fclose(file);
    if(!MoveFileExA("D:\\reply.tmp","D:\\reply.txt",MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))ExitProcess(13);
}
int WINAPI WinMain(HINSTANCE instance,HINSTANCE,LPSTR,int) {
    InitializeCriticalSection(&clip_lock);
    WNDCLASSA cls={};cls.lpfnWndProc=window_proc;cls.hInstance=instance;cls.lpszClassName="TrascCursorProbe";
    if(!RegisterClassA(&cls))return 10;
    HWND window=CreateWindowA(cls.lpszClassName,"TAKP relative camera fixture",WS_POPUP|WS_VISIBLE,
                             0,0,800,600,nullptr,nullptr,instance,nullptr);
    if(!window || !GetProcAddress(GetModuleHandleW(L"ntdll.dll"),"wine_get_version"))return 11;
    game_window=window;SetForegroundWindow(window);SetFocus(window);
    for(int i=0;i<30;i++){MSG message;while(PeekMessage(&message,nullptr,0,0,PM_REMOVE)){TranslateMessage(&message);DispatchMessage(&message);}Sleep(10);}
    SetCursorPos(400,300);result("ready");
    bool pump=false;HANDLE worker=nullptr;
    DWORD until=GetTickCount()+240000;
    while(GetTickCount()<until) {
        if(pump){MSG message;while(PeekMessage(&message,nullptr,0,0,PM_REMOVE)){TranslateMessage(&message);DispatchMessage(&message);}}
        FILE *file=std::fopen("D:\\command.txt","rb");
        if(!file){Sleep(1);continue;}
        char command[128]={};std::fgets(command,sizeof(command),file);std::fclose(file);
        DeleteFileA("D:\\command.txt");
        if(!std::strncmp(command,"quit",4)) {
            mode=-1;if(worker)WaitForSingleObject(worker,5000);release_clip();result(command);return 0;
        }
        if(!std::strncmp(command,"legacy",6))SetCursorPos(400,300);
        else if(!std::strncmp(command,"fixed",5))
            trasc_takp_camera::legacy_center(400,300,0,800,[](int x,int y){return SetCursorPos(x,y);});
        else if(!std::strncmp(command,"input",5)) {
            IDirectInput8A* input=nullptr;
            if(FAILED(DirectInput8Create(instance,0x0800,IID_IDirectInput8A,(void**)&input,nullptr))||
               FAILED(input->CreateDevice(GUID_SysMouse,&mouse,nullptr))||FAILED(mouse->SetDataFormat(&c_dfDIMouse2))||
               FAILED(mouse->SetCooperativeLevel(window,DISCL_FOREGROUND|DISCL_NONEXCLUSIVE)))return 16;
            DIPROPDWORD size={{sizeof(DIPROPDWORD),sizeof(DIPROPHEADER),0,DIPH_DEVICE},4096};
            if(FAILED(mouse->SetProperty(DIPROP_BUFFERSIZE,&size.diph)))return 17;
            pump=true;worker=CreateThread(nullptr,0,input_frame,nullptr,0,nullptr);if(!worker)return 18;
        }
        else if(!std::strncmp(command,"warp",4))mode=1;
        else if(!std::strncmp(command,"raw",3))mode=2;
        else if(!std::strncmp(command,"free",4)) {mode=0;release_clip();}
        else if(!std::strncmp(command,"focus",5)){SetForegroundWindow(window);SetFocus(window);}
        else if(!std::strncmp(command,"blur",4)){ShowWindow(window,SW_MINIMIZE);release_clip();}
        else if(!std::strncmp(command,"resume",6)){ShowWindow(window,SW_RESTORE);SetForegroundWindow(window);SetFocus(window);}
        else if(!std::strncmp(command,"sample",6)) {
            POINT point;RECT current;GetCursorPos(&point);GetClipCursor(&current);
            char reply[320];std::sprintf(reply,"%s %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %d %d %d",command,
                totals[0],totals[1],totals[2],totals[3],buttons,point.x,point.y,current.left,current.top,current.right,current.bottom,
                GetForegroundWindow()==window,GetFocus()==window,!IsIconic(window));
            result(reply);continue;
        }
        else return 14;
        result(command);
    }
    mode=-1;return 15;
}
