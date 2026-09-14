#define COBJMACROS
#include <windows.h>
#include <d3d9.h>
#include <stdio.h>
#include <string.h>

// ROF2 is a sizeable legacy PE32 image; exercise its low-address allocation class.
static volatile unsigned char legacy_image[20*1024*1024];

static void marker(const char *name,const char *value) {
    // Readers use existence as readiness; never expose an empty/partial result.
    char temporary[MAX_PATH];
    if(snprintf(temporary,sizeof(temporary),"%s.tmp",name)>=(int)sizeof(temporary))ExitProcess(90);
    FILE *out=fopen(temporary,"w");
    if(!out||fputs(value,out)==EOF||fclose(out)!=0)ExitProcess(90);
    if(!MoveFileExA(temporary,name,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))ExitProcess(91);
}
static LRESULT CALLBACK window_proc(HWND window,UINT message,WPARAM key,LPARAM data) {
    if(message==WM_KEYDOWN&&key=='T')marker("D:\\probe-key.txt","T");
    if(message==WM_LBUTTONDOWN)marker("D:\\probe-mouse.txt","left");
    if(message==WM_DESTROY){PostQuitMessage(0);return 0;}
    return DefWindowProc(window,message,key,data);
}
int WINAPI WinMain(HINSTANCE instance,HINSTANCE previous,LPSTR command,int show) {
    legacy_image[sizeof(legacy_image)-1]=1;
    HMODULE dll=LoadLibraryA("dinput8.dll");
    int (*probe)(void)=dll?(void*)GetProcAddress(dll,"TrascProbe"):NULL;
    BOOL input_ready=probe&&probe()==0x54524153;
    if(strstr(command,"--check-directinput"))return input_ready?0:23;
    if(!input_ready){marker("D:\\probe-error.txt","Native proxy could not create keyboard/mouse through system DirectInput8");return 1;}
    // Match the routine debug-string exceptions dominating the Thor's trace.
    // This is an open workload, not a ROF2 frame-rate benchmark.
    if(strstr(command,"--check-debug-output")) {
        for(int i=0;i<512;i++)OutputDebugStringA("[TRASC probe] routine asset-loading diagnostic");
        return 0;
    }
    LoadLibraryA("d3dx9_30.dll");LoadLibraryA("d3dx9_35.dll");
    int (*held_key)(HWND,int)=(void*)GetProcAddress(dll,"TrascHeldKey");
    BOOL saw_hold=FALSE;int previous_held=-99;
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
            marker("D:\\probe-result.json","{\"pe32\":true,\"native_dinput8\":true,\"system_directinput\":true,\"direct3d9\":true}");
            ready=TRUE;
        }
        if(held_key) {
            int held=held_key(window,0x11); // DIK_W, polled like game movement.
            if(held!=previous_held){printf("DirectInput W state: %d\n",held);fflush(stdout);previous_held=held;}
            if(held==1){saw_hold=TRUE;marker("D:\\probe-held-key.txt","W held");}
            if(saw_hold&&held==0)marker("D:\\probe-released-key.txt","W released");
        }
        Sleep(30);
    }
done:
    IDirect3DDevice9_Release(device);IDirect3D9_Release(d3d);return 0;
}
