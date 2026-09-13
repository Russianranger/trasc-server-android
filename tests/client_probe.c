#define COBJMACROS
#include <windows.h>
#include <d3d9.h>
#include <stdio.h>

static void marker(const char *name,const char *value) {
    FILE *out=fopen(name,"w");if(out){fputs(value,out);fclose(out);}
}
static LRESULT CALLBACK window_proc(HWND window,UINT message,WPARAM key,LPARAM data) {
    if(message==WM_KEYDOWN&&key=='T')marker("D:\\probe-key.txt","T");
    if(message==WM_LBUTTONDOWN)marker("D:\\probe-mouse.txt","left");
    if(message==WM_DESTROY){PostQuitMessage(0);return 0;}
    return DefWindowProc(window,message,key,data);
}
int WINAPI WinMain(HINSTANCE instance,HINSTANCE previous,LPSTR command,int show) {
    HMODULE dll=LoadLibraryA("dinput8.dll");
    int (*probe)(void)=dll?(void*)GetProcAddress(dll,"TrascProbe"):NULL;
    if(!probe||probe()!=0x54524153){marker("D:\\probe-error.txt","Native 32-bit DLL did not load");return 1;}
    WNDCLASSA cls={0};cls.lpfnWndProc=window_proc;cls.hInstance=instance;cls.lpszClassName="TrascProbe";
    RegisterClassA(&cls);
    HWND window=CreateWindowA(cls.lpszClassName,"TRASC 32-bit Direct3D/input probe",WS_OVERLAPPEDWINDOW|WS_VISIBLE,
                             0,0,600,400,NULL,NULL,instance,NULL);
    SetForegroundWindow(window);SetFocus(window);
    IDirect3D9 *d3d=Direct3DCreate9(D3D_SDK_VERSION);
    D3DPRESENT_PARAMETERS params={0};params.Windowed=TRUE;params.SwapEffect=D3DSWAPEFFECT_DISCARD;params.hDeviceWindow=window;
    IDirect3DDevice9 *device=NULL;
    if(!d3d||FAILED(IDirect3D9_CreateDevice(d3d,0,D3DDEVTYPE_HAL,window,D3DCREATE_SOFTWARE_VERTEXPROCESSING,&params,&device))) {
        marker("D:\\probe-error.txt","Direct3D9 device creation failed");return 2;
    }
    BOOL ready=FALSE;
    DWORD until=GetTickCount()+120000;
    while(GetTickCount()<until) {
        MSG msg;
        while(PeekMessage(&msg,NULL,0,0,PM_REMOVE)){if(msg.message==WM_QUIT)goto done;TranslateMessage(&msg);DispatchMessage(&msg);}
        HRESULT cleared=IDirect3DDevice9_Clear(device,0,NULL,D3DCLEAR_TARGET,D3DCOLOR_XRGB(24,72,96),1,0);
        HRESULT presented=IDirect3DDevice9_Present(device,NULL,NULL,NULL,NULL);
        if(!ready&&SUCCEEDED(cleared)&&SUCCEEDED(presented)) {
            marker("D:\\probe-result.json","{\"pe32\":true,\"native_dinput8\":true,\"direct3d9\":true}");
            ready=TRUE;
        }
        Sleep(30);
    }
done:
    IDirect3DDevice9_Release(device);IDirect3D9_Release(d3d);return 0;
}
