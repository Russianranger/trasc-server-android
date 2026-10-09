// Standalone Traditional proxy: system DirectInput plus camera-only post-read.
// No MQ2, detours, executable writes, loading hooks or gameplay modifications.
#define DIRECTINPUT_VERSION 0x0800
#include <windows.h>
#include <dinput.h>
#include <new>
#include "../backend/eq_camera_mouse.h"

extern "C" const char trasc_traditional_camera_marker[] = "TRASC_TRADITIONAL_CAMERA_ONLY_V1";

struct Ansi {
    typedef IDirectInput8A Input; typedef IDirectInputDevice8A Device;
    typedef DIDEVICEOBJECTINSTANCEA Object; typedef DIDEVICEINSTANCEA Instance;
    typedef DIEFFECTINFOA EffectInfo; typedef DIACTIONFORMATA ActionFormat;
    typedef DIDEVICEIMAGEINFOHEADERA ImageInfo; typedef DICONFIGUREDEVICESPARAMSA ConfigureParams;
    typedef LPDIENUMDEVICEOBJECTSCALLBACKA ObjectsCallback;
    typedef LPDIENUMEFFECTSCALLBACKA EffectsCallback;
    typedef LPDIENUMDEVICESCALLBACKA DevicesCallback;
    typedef LPDIENUMDEVICESBYSEMANTICSCBA SemanticsCallback;
    typedef LPCSTR String;
    static const IID &inputIID() { return IID_IDirectInput8A; }
    static const IID &deviceIID() { return IID_IDirectInputDevice8A; }
};
struct Wide {
    typedef IDirectInput8W Input; typedef IDirectInputDevice8W Device;
    typedef DIDEVICEOBJECTINSTANCEW Object; typedef DIDEVICEINSTANCEW Instance;
    typedef DIEFFECTINFOW EffectInfo; typedef DIACTIONFORMATW ActionFormat;
    typedef DIDEVICEIMAGEINFOHEADERW ImageInfo; typedef DICONFIGUREDEVICESPARAMSW ConfigureParams;
    typedef LPDIENUMDEVICEOBJECTSCALLBACKW ObjectsCallback;
    typedef LPDIENUMEFFECTSCALLBACKW EffectsCallback;
    typedef LPDIENUMDEVICESCALLBACKW DevicesCallback;
    typedef LPDIENUMDEVICESBYSEMANTICSCBW SemanticsCallback;
    typedef LPCWSTR String;
    static const IID &inputIID() { return IID_IDirectInput8W; }
    static const IID &deviceIID() { return IID_IDirectInputDevice8W; }
};

template<class Traits> class CameraDevice final : public Traits::Device {
    typename Traits::Device *real;
    LONG references = 1;
public:
    explicit CameraDevice(typename Traits::Device *value) : real(value) {}
#ifdef TRASC_CAMERA_PROXY_FIXTURE
    typename Traits::Device *sourceForFixture() { return real; }
#endif
    HRESULT WINAPI QueryInterface(REFIID iid, void **out) override {
        if (!out) return E_POINTER;
        if (IsEqualGUID(iid, IID_IUnknown) || IsEqualGUID(iid, Traits::deviceIID())) {
            *out = static_cast<typename Traits::Device *>(this); AddRef(); return S_OK;
        }
        return real->QueryInterface(iid, out);
    }
    ULONG WINAPI AddRef() override { real->AddRef(); return InterlockedIncrement(&references); }
    ULONG WINAPI Release() override {
        ULONG count = InterlockedDecrement(&references); real->Release();
        if (!count) delete this;
        return count;
    }
    HRESULT WINAPI GetCapabilities(LPDIDEVCAPS p) override { return real->GetCapabilities(p); }
    HRESULT WINAPI EnumObjects(typename Traits::ObjectsCallback c, LPVOID p, DWORD f) override { return real->EnumObjects(c,p,f); }
    HRESULT WINAPI GetProperty(REFGUID g, LPDIPROPHEADER p) override { return real->GetProperty(g,p); }
    HRESULT WINAPI SetProperty(REFGUID g, LPCDIPROPHEADER p) override { return real->SetProperty(g,p); }
    HRESULT WINAPI Acquire() override { return real->Acquire(); }
    HRESULT WINAPI Unacquire() override { return real->Unacquire(); }
    HRESULT WINAPI GetDeviceState(DWORD size, LPVOID data) override {
        HRESULT result = real->GetDeviceState(size, data);
        trasc_camera::afterRead(real, result, size, data);
        return result;
    }
    HRESULT WINAPI GetDeviceData(DWORD size, LPDIDEVICEOBJECTDATA data, LPDWORD count, DWORD flags) override { return real->GetDeviceData(size,data,count,flags); }
    HRESULT WINAPI SetDataFormat(LPCDIDATAFORMAT format) override { return real->SetDataFormat(format); }
    HRESULT WINAPI SetEventNotification(HANDLE event) override { return real->SetEventNotification(event); }
    HRESULT WINAPI SetCooperativeLevel(HWND window, DWORD flags) override { return real->SetCooperativeLevel(window,flags); }
    HRESULT WINAPI GetObjectInfo(typename Traits::Object *info, DWORD object, DWORD flags) override { return real->GetObjectInfo(info,object,flags); }
    HRESULT WINAPI GetDeviceInfo(typename Traits::Instance *info) override { return real->GetDeviceInfo(info); }
    HRESULT WINAPI RunControlPanel(HWND window, DWORD flags) override { return real->RunControlPanel(window,flags); }
    HRESULT WINAPI Initialize(HINSTANCE instance, DWORD version, REFGUID guid) override { return real->Initialize(instance,version,guid); }
    HRESULT WINAPI CreateEffect(REFGUID guid, LPCDIEFFECT effect, LPDIRECTINPUTEFFECT *out, LPUNKNOWN outer) override { return real->CreateEffect(guid,effect,out,outer); }
    HRESULT WINAPI EnumEffects(typename Traits::EffectsCallback c, LPVOID p, DWORD f) override { return real->EnumEffects(c,p,f); }
    HRESULT WINAPI GetEffectInfo(typename Traits::EffectInfo *info, REFGUID guid) override { return real->GetEffectInfo(info,guid); }
    HRESULT WINAPI GetForceFeedbackState(LPDWORD state) override { return real->GetForceFeedbackState(state); }
    HRESULT WINAPI SendForceFeedbackCommand(DWORD command) override { return real->SendForceFeedbackCommand(command); }
    HRESULT WINAPI EnumCreatedEffectObjects(LPDIENUMCREATEDEFFECTOBJECTSCALLBACK c, LPVOID p, DWORD f) override { return real->EnumCreatedEffectObjects(c,p,f); }
    HRESULT WINAPI Escape(LPDIEFFESCAPE escape) override { return real->Escape(escape); }
    HRESULT WINAPI Poll() override { return real->Poll(); }
    HRESULT WINAPI SendDeviceData(DWORD size, LPCDIDEVICEOBJECTDATA data, LPDWORD count, DWORD flags) override { return real->SendDeviceData(size,data,count,flags); }
    HRESULT WINAPI EnumEffectsInFile(typename Traits::String path, LPDIENUMEFFECTSINFILECALLBACK c, LPVOID p, DWORD f) override { return real->EnumEffectsInFile(path,c,p,f); }
    HRESULT WINAPI WriteEffectToFile(typename Traits::String path, DWORD count, LPDIFILEEFFECT effects, DWORD flags) override { return real->WriteEffectToFile(path,count,effects,flags); }
    HRESULT WINAPI BuildActionMap(typename Traits::ActionFormat *format, typename Traits::String user, DWORD flags) override { return real->BuildActionMap(format,user,flags); }
    HRESULT WINAPI SetActionMap(typename Traits::ActionFormat *format, typename Traits::String user, DWORD flags) override { return real->SetActionMap(format,user,flags); }
    HRESULT WINAPI GetImageInfo(typename Traits::ImageInfo *info) override { return real->GetImageInfo(info); }
};

template<class Traits> class CameraInput final : public Traits::Input {
    typename Traits::Input *real;
    LONG references = 1;
public:
    explicit CameraInput(typename Traits::Input *value) : real(value) {}
    HRESULT WINAPI QueryInterface(REFIID iid, void **out) override {
        if (!out) return E_POINTER;
        if (IsEqualGUID(iid, IID_IUnknown) || IsEqualGUID(iid, Traits::inputIID())) {
            *out = static_cast<typename Traits::Input *>(this); AddRef(); return S_OK;
        }
        return real->QueryInterface(iid, out);
    }
    ULONG WINAPI AddRef() override { real->AddRef(); return InterlockedIncrement(&references); }
    ULONG WINAPI Release() override {
        ULONG count = InterlockedDecrement(&references); real->Release();
        if (!count) delete this;
        return count;
    }
    HRESULT WINAPI CreateDevice(REFGUID guid, typename Traits::Device **out, LPUNKNOWN outer) override {
        HRESULT result = real->CreateDevice(guid, out, outer);
        if (SUCCEEDED(result) && out && *out && !outer && IsEqualGUID(guid, GUID_SysMouse)) {
            auto wrapped = new(std::nothrow) CameraDevice<Traits>(*out);
            if (wrapped) *out = wrapped;
        }
        return result;
    }
    HRESULT WINAPI EnumDevices(DWORD type, typename Traits::DevicesCallback c, LPVOID p, DWORD f) override { return real->EnumDevices(type,c,p,f); }
    HRESULT WINAPI GetDeviceStatus(REFGUID guid) override { return real->GetDeviceStatus(guid); }
    HRESULT WINAPI RunControlPanel(HWND window, DWORD flags) override { return real->RunControlPanel(window,flags); }
    HRESULT WINAPI Initialize(HINSTANCE instance, DWORD version) override { return real->Initialize(instance,version); }
    HRESULT WINAPI FindDevice(REFGUID guid, typename Traits::String name, LPGUID out) override { return real->FindDevice(guid,name,out); }
    HRESULT WINAPI EnumDevicesBySemantics(typename Traits::String user, typename Traits::ActionFormat *format, typename Traits::SemanticsCallback c, LPVOID p, DWORD f) override { return real->EnumDevicesBySemantics(user,format,c,p,f); }
    HRESULT WINAPI ConfigureDevices(LPDICONFIGUREDEVICESCALLBACK c, typename Traits::ConfigureParams *params, DWORD f, LPVOID p) override { return real->ConfigureDevices(c,params,f,p); }
};

typedef HRESULT (WINAPI *InputFactory)(HINSTANCE,DWORD,REFIID,LPVOID*,LPUNKNOWN);
static HMODULE systemInput = NULL;
static InputFactory factory = NULL;
static bool loadSystemInput() {
    static const bool loaded = []() {
        WCHAR path[MAX_PATH] = {};
        UINT length = GetSystemDirectoryW(path, MAX_PATH);
        if (!length || length >= MAX_PATH-13) return false;
        lstrcatW(path, L"\\dinput8.dll");
        systemInput = LoadLibraryW(path);
        if (!systemInput) return false;
        factory = reinterpret_cast<InputFactory>(GetProcAddress(systemInput,"DirectInput8Create"));
        return factory != NULL;
    }();
    return loaded;
}

extern "C" HRESULT WINAPI DirectInput8Create(HINSTANCE instance, DWORD version, REFIID iid, LPVOID *out, LPUNKNOWN outer) {
    if (!loadSystemInput()) return E_FAIL;
    HRESULT result = factory(instance, version, iid, out, outer);
    char enabled[4] = {};
    const BYTE *image = reinterpret_cast<const BYTE *>(GetModuleHandleW(NULL));
    bool allowed = GetEnvironmentVariableA(trasc_camera::marker, enabled, sizeof(enabled)) == 1 && enabled[0] == '1'
        && GetProcAddress(GetModuleHandleW(L"ntdll.dll"), "wine_get_version") && trasc_camera::supported(image);
    if (SUCCEEDED(result) && out && *out && !outer && allowed) {
        if (IsEqualGUID(iid, IID_IDirectInput8A)) {
            auto wrapped = new(std::nothrow) CameraInput<Ansi>(static_cast<IDirectInput8A *>(*out));
            if (wrapped) *out = wrapped;
        } else if (IsEqualGUID(iid, IID_IDirectInput8W)) {
            auto wrapped = new(std::nothrow) CameraInput<Wide>(static_cast<IDirectInput8W *>(*out));
            if (wrapped) *out = wrapped;
        }
    }
    return result;
}

extern "C" HRESULT WINAPI DllCanUnloadNow() { return S_FALSE; }
extern "C" HRESULT WINAPI DllGetClassObject(REFCLSID clsid, REFIID iid, LPVOID *out) {
    if (!loadSystemInput()) return E_FAIL;
    typedef HRESULT (WINAPI *Function)(REFCLSID,REFIID,LPVOID*);
    auto call = reinterpret_cast<Function>(GetProcAddress(systemInput,"DllGetClassObject"));
    return call ? call(clsid,iid,out) : CLASS_E_CLASSNOTAVAILABLE;
}
extern "C" HRESULT WINAPI DllRegisterServer() {
    if (!loadSystemInput()) return E_FAIL;
    auto call = reinterpret_cast<HRESULT (WINAPI *)(void)>(GetProcAddress(systemInput,"DllRegisterServer"));
    return call ? call() : E_FAIL;
}
extern "C" HRESULT WINAPI DllUnregisterServer() {
    if (!loadSystemInput()) return E_FAIL;
    auto call = reinterpret_cast<HRESULT (WINAPI *)(void)>(GetProcAddress(systemInput,"DllUnregisterServer"));
    return call ? call() : E_FAIL;
}

#ifndef TRASC_CAMERA_PROXY_FIXTURE
BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) DisableThreadLibraryCalls(instance);
    return TRUE;
}
#endif
