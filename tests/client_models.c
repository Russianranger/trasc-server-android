#define COBJMACROS
#include <windows.h>
#include <d3d9.h>
#include <d3dx9.h>
#include <stdio.h>
#include <string.h>

typedef HRESULT (WINAPI *CreateSet)(LPCSTR,DOUBLE,D3DXPLAYBACK_TYPE,UINT,UINT,const D3DXKEY_CALLBACK*,ID3DXKeyframedAnimationSet**);
typedef HRESULT (WINAPI *CreateMesh)(DWORD,DWORD,DWORD,DWORD,IDirect3DDevice9*,ID3DXMesh**);
typedef HRESULT (WINAPI *CreateSkin)(DWORD,DWORD,DWORD,ID3DXSkinInfo**);
static ID3DXMesh *model;
static ID3DXKeyframedAnimationSet *animation;

static void marker(const char *name,const char *value) {
    // Readers use existence as readiness; never expose an empty/partial result.
    char temporary[MAX_PATH];
    if(snprintf(temporary,sizeof(temporary),"%s.tmp",name)>=(int)sizeof(temporary))ExitProcess(90);
    FILE *out=fopen(temporary,"w");
    if(!out||fputs(value,out)==EOF||fclose(out)!=0)ExitProcess(90);
    if(!MoveFileExA(temporary,name,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))ExitProcess(91);
}
static void identity(D3DXMATRIX *m){memset(m,0,sizeof(*m));m->_11=m->_22=m->_33=m->_44=1;}
static int failed(const char *step,HRESULT hr) {
    printf("MODEL %s HRESULT=%08lx\n",step,(unsigned long)hr);fflush(stdout);
    return hr==E_NOTIMPL?31:32;
}
static int load_model(const char *name,IDirect3DDevice9 *device) {
    HMODULE dll=LoadLibraryA(name);
    CreateSet create_set=dll?(void*)GetProcAddress(dll,"D3DXCreateKeyframedAnimationSet"):NULL;
    CreateMesh create_mesh=dll?(void*)GetProcAddress(dll,"D3DXCreateMeshFVF"):NULL;
    CreateSkin create_skin=dll?(void*)GetProcAddress(dll,"D3DXCreateSkinInfoFVF"):NULL;
    if(!create_set||!create_mesh||!create_skin)return failed(name,E_FAIL);
    ID3DXKeyframedAnimationSet *set=NULL;
    HRESULT hr=create_set("walk",1.0,D3DXPLAY_LOOP,1,0,NULL,&set);
    if(FAILED(hr))return failed("CreateKeyframedAnimationSet",hr);
    D3DXKEY_VECTOR3 scale[2]={{0,{1,1,1}},{1,{1,1,1}}};
    D3DXKEY_QUATERNION rotation[2]={{0,{0,0,0,1}},{1,{0,0,0,1}}};
    D3DXKEY_VECTOR3 translation[2]={{0,{-0.3f,0,0}},{1,{0.3f,0,0}}};
    DWORD index=99;
    hr=set->lpVtbl->RegisterAnimationSRTKeys(set,"root",2,2,2,scale,rotation,translation,&index);
    if(FAILED(hr))return failed("RegisterAnimationSRTKeys",hr);
    D3DXVECTOR3 s,t;D3DXQUATERNION q;
    hr=set->lpVtbl->GetSRT(set,0.5,0,&s,&q,&t);
    if(FAILED(hr)||index!=0||t.x<-.01f||t.x>.01f)return failed("GetSRT",FAILED(hr)?hr:E_FAIL);
    ID3DXBuffer *compressed=NULL;
    hr=set->lpVtbl->Compress(set,0,0.1f,NULL,&compressed);
    if(FAILED(hr)||!compressed)return failed("Compress",FAILED(hr)?hr:E_FAIL);
    compressed->lpVtbl->Release(compressed);
    ID3DXMesh *mesh=NULL,*blended=NULL;
    DWORD fvf=D3DFVF_XYZ|D3DFVF_NORMAL|D3DFVF_DIFFUSE;
    hr=create_mesh(1,3,D3DXMESH_MANAGED,fvf,device,&mesh);
    if(FAILED(hr))return failed("CreateMesh",hr);
    struct Vertex {float x,y,z,nx,ny,nz;DWORD color;};
    struct Vertex vertices[3]={{-.5f,-.5f,.5f,0,0,-1,0xffe08020},{0,.5f,.5f,0,0,-1,0xffe08020},{.5f,-.5f,.5f,0,0,-1,0xffe08020}};
    void *data=NULL;WORD indices[3]={0,1,2};DWORD *attributes=NULL;
    if(FAILED(mesh->lpVtbl->LockVertexBuffer(mesh,0,&data)))return 32;
    memcpy(data,vertices,sizeof(vertices));mesh->lpVtbl->UnlockVertexBuffer(mesh);
    if(FAILED(mesh->lpVtbl->LockIndexBuffer(mesh,0,&data)))return 32;
    memcpy(data,indices,sizeof(indices));mesh->lpVtbl->UnlockIndexBuffer(mesh);
    if(FAILED(mesh->lpVtbl->LockAttributeBuffer(mesh,0,&attributes)))return 32;
    attributes[0]=0;mesh->lpVtbl->UnlockAttributeBuffer(mesh);
    ID3DXSkinInfo *skin=NULL;hr=create_skin(3,fvf,1,&skin);
    if(FAILED(hr))return failed("CreateSkin",hr);
    DWORD ids[3]={0,1,2};float weights[3]={1,1,1};D3DXMATRIX offset;identity(&offset);
    skin->lpVtbl->SetBoneName(skin,0,"root");skin->lpVtbl->SetBoneOffsetMatrix(skin,0,&offset);
    hr=skin->lpVtbl->SetBoneInfluence(skin,0,3,ids,weights);
    if(FAILED(hr))return failed("SetBoneInfluence",hr);
    DWORD adjacency[3]={0xffffffff,0xffffffff,0xffffffff},influences=0,combinations=0;
    ID3DXBuffer *table=NULL;
    hr=skin->lpVtbl->ConvertToIndexedBlendedMesh(skin,mesh,D3DXMESH_MANAGED,1,adjacency,NULL,NULL,NULL,&influences,&combinations,&table,&blended);
    if(FAILED(hr)||!blended||!combinations)return failed("ConvertToIndexedBlendedMesh",FAILED(hr)?hr:E_FAIL);
    if(table)table->lpVtbl->Release(table);skin->lpVtbl->Release(skin);mesh->lpVtbl->Release(mesh);
    if(model)model->lpVtbl->Release(model);
    if(animation)animation->lpVtbl->Release(animation);
    model=blended;animation=set;
    printf("PASS: %s animation registration, sampling, compression and skinned mesh conversion\n",name);fflush(stdout);
    return 0;
}
static LRESULT CALLBACK procedure(HWND window,UINT message,WPARAM w,LPARAM l) {
    if(message==WM_DESTROY){PostQuitMessage(0);return 0;}return DefWindowProc(window,message,w,l);
}
int WINAPI WinMain(HINSTANCE instance,HINSTANCE previous,LPSTR command,int show) {
    WNDCLASSA cls={0};cls.hInstance=instance;cls.lpszClassName="TrascModels";cls.lpfnWndProc=procedure;RegisterClassA(&cls);
    HWND window=CreateWindowA(cls.lpszClassName,"TRASC animated model probe",WS_OVERLAPPEDWINDOW|WS_VISIBLE,0,0,600,400,NULL,NULL,instance,NULL);
    SetForegroundWindow(window);
    IDirect3D9 *d3d=Direct3DCreate9(D3D_SDK_VERSION);IDirect3DDevice9 *device=NULL;
    D3DPRESENT_PARAMETERS params={0};params.Windowed=TRUE;params.SwapEffect=D3DSWAPEFFECT_DISCARD;params.hDeviceWindow=window;
    if(!d3d||FAILED(IDirect3D9_CreateDevice(d3d,0,D3DDEVTYPE_HAL,window,D3DCREATE_SOFTWARE_VERTEXPROCESSING,&params,&device)))return 32;
    int result=load_model("d3dx9_30.dll",device);if(result)return result;
    result=load_model("d3dx9_35.dll",device);if(result)return result;
    if(strstr(command,"--once"))return 0;
    D3DXMATRIX matrix;identity(&matrix);
    IDirect3DDevice9_SetTransform(device,D3DTS_VIEW,(D3DMATRIX*)&matrix);
    IDirect3DDevice9_SetTransform(device,D3DTS_PROJECTION,(D3DMATRIX*)&matrix);
    IDirect3DDevice9_SetRenderState(device,D3DRS_LIGHTING,FALSE);
    IDirect3DDevice9_SetRenderState(device,D3DRS_CULLMODE,D3DCULL_NONE);
    IDirect3DDevice9_SetRenderState(device,D3DRS_INDEXEDVERTEXBLENDENABLE,TRUE);
    IDirect3DDevice9_SetRenderState(device,D3DRS_VERTEXBLEND,D3DVBF_0WEIGHTS);
    DWORD start=GetTickCount();BOOL ready=FALSE;
    while(GetTickCount()-start<30000 && GetFileAttributesA("D:\\model-stop.txt")==INVALID_FILE_ATTRIBUTES) {
        MSG msg;while(PeekMessage(&msg,NULL,0,0,PM_REMOVE)){if(msg.message==WM_QUIT)goto done;TranslateMessage(&msg);DispatchMessage(&msg);}
        D3DXVECTOR3 scale,translation;D3DXQUATERNION rotation;
        if(FAILED(animation->lpVtbl->GetSRT(animation,(GetTickCount()-start)%1000/1000.0,0,&scale,&rotation,&translation)))return 32;
        identity(&matrix);matrix._41=translation.x;
        IDirect3DDevice9_SetTransform(device,D3DTS_WORLD,(D3DMATRIX*)&matrix);
        IDirect3DDevice9_Clear(device,0,NULL,D3DCLEAR_TARGET,0xff184860,1,0);
        IDirect3DDevice9_BeginScene(device);IDirect3DDevice9_SetFVF(device,model->lpVtbl->GetFVF(model));
        HRESULT drawn=model->lpVtbl->DrawSubset(model,0);IDirect3DDevice9_EndScene(device);
        HRESULT presented=IDirect3DDevice9_Present(device,NULL,NULL,NULL,NULL);
        if(!ready&&SUCCEEDED(drawn)&&SUCCEEDED(presented)){marker("D:\\model-ready.json","{\"model_functions\":true,\"drawn\":true}");ready=TRUE;}
        Sleep(30);
    }
done:
    model->lpVtbl->Release(model);animation->lpVtbl->Release(animation);IDirect3DDevice9_Release(device);IDirect3D9_Release(d3d);
    return 0;
}
