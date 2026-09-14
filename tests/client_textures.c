/* Open PE32 regression fixture: compressed artwork and SM1/2 specular fog. */
#define COBJMACROS
#include <windows.h>
#include <d3d9.h>
#include <d3dx9.h>
#include <stdio.h>
#include <string.h>
static IDirect3DDevice9 *dev;
#define HR(call) do { HRESULT hr=(call); if(FAILED(hr)){printf("FAIL %s %08lx\n",#call,(long)hr);return 40;} } while(0)
static int pixel(unsigned r,unsigned g,unsigned b) {
    IDirect3DSurface9 *rt=NULL,*copy=NULL;D3DLOCKED_RECT lock;
    HR(IDirect3DDevice9_GetRenderTarget(dev,0,&rt));
    HR(IDirect3DDevice9_CreateOffscreenPlainSurface(dev,64,64,D3DFMT_A8R8G8B8,D3DPOOL_SYSTEMMEM,&copy,NULL));
    HR(IDirect3DDevice9_GetRenderTargetData(dev,rt,copy));
    HR(IDirect3DSurface9_LockRect(copy,&lock,NULL,D3DLOCK_READONLY));
    unsigned char *p=(unsigned char*)lock.pBits+32*lock.Pitch+32*4;
    printf("D3D sample RGB %u,%u,%u expected %u,%u,%u\n",p[2],p[1],p[0],r,g,b);fflush(stdout);
    int fail=abs((int)p[2]-(int)r)>3||abs((int)p[1]-(int)g)>3||abs((int)p[0]-(int)b)>3;
    IDirect3DSurface9_UnlockRect(copy);IDirect3DSurface9_Release(copy);IDirect3DSurface9_Release(rt);
    return fail?42:0;
}
static int artwork(void) {
    struct V {float x,y,z,w,u,v;} quad[]={{-.5f,-.5f,0,1,0,0},{63.5f,-.5f,0,1,1,0},{-.5f,63.5f,0,1,0,1},{63.5f,63.5f,0,1,1,1}};
    HR(IDirect3DDevice9_SetFVF(dev,D3DFVF_XYZRHW|D3DFVF_TEX1));
    HR(IDirect3DDevice9_SetTextureStageState(dev,0,D3DTSS_COLOROP,D3DTOP_SELECTARG1));
    HR(IDirect3DDevice9_SetTextureStageState(dev,0,D3DTSS_COLORARG1,D3DTA_TEXTURE));
    HR(IDirect3DDevice9_SetSamplerState(dev,0,D3DSAMP_MINFILTER,D3DTEXF_POINT));
    HR(IDirect3DDevice9_SetSamplerState(dev,0,D3DSAMP_MAGFILTER,D3DTEXF_POINT));
    const D3DFORMAT formats[]={D3DFMT_DXT1,D3DFMT_DXT3,D3DFMT_DXT5};
    for(unsigned k=0;k<3;k++) {
        IDirect3DTexture9 *tex=NULL;D3DLOCKED_RECT lock;
        HR(IDirect3DDevice9_CreateTexture(dev,8,8,1,0,formats[k],D3DPOOL_MANAGED,&tex,NULL));
        HR(IDirect3DTexture9_LockRect(tex,0,&lock,NULL,0));
        unsigned size=k?16:8;
        for(unsigned y=0;y<2;y++)for(unsigned x=0;x<2;x++) {
            unsigned char *p=(unsigned char*)lock.pBits+y*lock.Pitch+x*size;memset(p,0,size);
            if(k==1)memset(p,255,8);if(k==2)p[0]=255;
            p[size-7]=248; /* red RGB565 endpoint */
        }
        HR(IDirect3DTexture9_UnlockRect(tex,0));HR(IDirect3DDevice9_SetTexture(dev,0,(IDirect3DBaseTexture9*)tex));
        HR(IDirect3DDevice9_Clear(dev,0,NULL,D3DCLEAR_TARGET,0xff000000,1,0));
        HR(IDirect3DDevice9_BeginScene(dev));HR(IDirect3DDevice9_DrawPrimitiveUP(dev,D3DPT_TRIANGLESTRIP,2,quad,sizeof(quad[0])));HR(IDirect3DDevice9_EndScene(dev));
        int result=pixel(255,0,0);if(result)return result;
        IDirect3DDevice9_SetTexture(dev,0,NULL);IDirect3DTexture9_Release(tex);
    }
    puts("PASS: D3D9 DXT1/3/5 artwork pixels");return 0;
}
static int specular_shader(const char *version) {
    typedef HRESULT (WINAPI *Assemble)(LPCSTR,UINT,const D3DXMACRO*,ID3DXInclude*,DWORD,ID3DXBuffer**,ID3DXBuffer**);
    HMODULE dll=LoadLibraryA("d3dx9_35.dll");Assemble assemble=dll?(void*)GetProcAddress(dll,"D3DXAssembleShader"):NULL;
    if(!assemble)return 40;
    /* D3D9 requires explicit input declarations even for SM1 bytecode.
     * Without them the shader has no position input and draws no geometry. */
    char source[256];snprintf(source,sizeof(source),"%s\ndcl_position v0\ndcl_color0 v1\ndcl_color1 v2\nmov oPos, v0\nmov oD0, v1\nmov oD1, v2\n",version);
    ID3DXBuffer *code=NULL,*errors=NULL;HR(assemble(source,(UINT)strlen(source),NULL,NULL,0,&code,&errors));
    IDirect3DVertexShader9 *shader=NULL;IDirect3DVertexDeclaration9 *decl=NULL;
    HR(IDirect3DDevice9_CreateVertexShader(dev,code->lpVtbl->GetBufferPointer(code),&shader));
    D3DVERTEXELEMENT9 elements[]={{0,0,D3DDECLTYPE_FLOAT4,D3DDECLMETHOD_DEFAULT,D3DDECLUSAGE_POSITION,0},{0,16,D3DDECLTYPE_D3DCOLOR,D3DDECLMETHOD_DEFAULT,D3DDECLUSAGE_COLOR,0},{0,20,D3DDECLTYPE_D3DCOLOR,D3DDECLMETHOD_DEFAULT,D3DDECLUSAGE_COLOR,1},D3DDECL_END()};
    HR(IDirect3DDevice9_CreateVertexDeclaration(dev,elements,&decl));
    HR(IDirect3DDevice9_SetVertexDeclaration(dev,decl));HR(IDirect3DDevice9_SetVertexShader(dev,shader));
    HR(IDirect3DDevice9_SetTexture(dev,0,NULL));
    HR(IDirect3DDevice9_SetTextureStageState(dev,0,D3DTSS_COLOROP,D3DTOP_SELECTARG1));
    HR(IDirect3DDevice9_SetTextureStageState(dev,0,D3DTSS_COLORARG1,D3DTA_DIFFUSE));
    HR(IDirect3DDevice9_SetRenderState(dev,D3DRS_FOGTABLEMODE,D3DFOG_NONE));
    struct V {float x,y,z,w;DWORD color,specular;} quad[]={{-1,1,.5,1,0xffe08020,0xff000000},{1,1,.5,1,0xffe08020,0xff000000},{-1,-1,.5,1,0xffe08020,0xff000000},{1,-1,.5,1,0xffe08020,0xff000000}};
    HR(IDirect3DDevice9_Clear(dev,0,NULL,D3DCLEAR_TARGET,0xff000000,1,0));
    HR(IDirect3DDevice9_BeginScene(dev));HR(IDirect3DDevice9_DrawPrimitiveUP(dev,D3DPT_TRIANGLESTRIP,2,quad,sizeof(quad[0])));HR(IDirect3DDevice9_EndScene(dev));
    int result=pixel(224,128,32);
    IDirect3DDevice9_SetVertexShader(dev,NULL);IDirect3DVertexShader9_Release(shader);IDirect3DVertexDeclaration9_Release(decl);code->lpVtbl->Release(code);
    printf("%s: %s specular output and implicit fog\n",result?"FAIL":"PASS",version);return result;
}
int WINAPI WinMain(HINSTANCE instance,HINSTANCE prev,LPSTR command,int show) {
    WNDCLASSA cls={0};cls.hInstance=instance;cls.lpszClassName="TrascTextures";cls.lpfnWndProc=DefWindowProcA;RegisterClassA(&cls);
    HWND window=CreateWindowA(cls.lpszClassName,"TRASC texture/shader probe",WS_OVERLAPPEDWINDOW|WS_VISIBLE,0,0,96,96,NULL,NULL,instance,NULL);
    IDirect3D9 *d3d=Direct3DCreate9(D3D_SDK_VERSION);if(!d3d)return 40;
    D3DPRESENT_PARAMETERS params={0};params.Windowed=TRUE;params.SwapEffect=D3DSWAPEFFECT_DISCARD;params.hDeviceWindow=window;
    params.BackBufferWidth=64;params.BackBufferHeight=64;params.BackBufferFormat=D3DFMT_A8R8G8B8;
    HR(IDirect3D9_CreateDevice(d3d,0,D3DDEVTYPE_HAL,window,D3DCREATE_HARDWARE_VERTEXPROCESSING,&params,&dev));
    IDirect3DDevice9_SetRenderState(dev,D3DRS_LIGHTING,FALSE);IDirect3DDevice9_SetRenderState(dev,D3DRS_ZENABLE,FALSE);IDirect3DDevice9_SetRenderState(dev,D3DRS_CULLMODE,D3DCULL_NONE);
    int result=0;if(!strstr(command,"--shader-only"))result=artwork();
    if(!result)result=specular_shader("vs_1_1");if(!result)result=specular_shader("vs_2_0");
    IDirect3DDevice9_Release(dev);IDirect3D9_Release(d3d);DestroyWindow(window);fflush(stdout);return result;
}
