// Run with an x86 Windows compiler. Exercises the production proxy wrappers
// against Windows system DirectInput, without enabling game-state recentering.
#define TRASC_CAMERA_PROXY_FIXTURE
#include "../native/traditional_camera_proxy.cpp"
#include <assert.h>
#include <stdio.h>

template<class Traits> void verifyInput() {
    typename Traits::Input *real = NULL;
    assert(SUCCEEDED(factory(GetModuleHandleW(NULL), DIRECTINPUT_VERSION,
        Traits::inputIID(), reinterpret_cast<void **>(&real), NULL)) && real);
    auto input = new CameraInput<Traits>(real);
    void *same = NULL;
    assert(SUCCEEDED(input->QueryInterface(Traits::inputIID(), &same)) && same == input);
    static_cast<typename Traits::Input *>(same)->Release();
    assert(SUCCEEDED(input->QueryInterface(IID_IUnknown, &same)) && same == input);
    static_cast<IUnknown *>(same)->Release();
    assert(input->QueryInterface(IID_IUnknown, NULL) == E_POINTER);
    typename Traits::Device *keyboard = NULL, *mouse = NULL;
    assert(SUCCEEDED(input->CreateDevice(GUID_SysKeyboard, &keyboard, NULL)) && keyboard);
    assert(SUCCEEDED(input->CreateDevice(GUID_SysMouse, &mouse, NULL)) && mouse);
    DIDEVCAPS caps = {}; caps.dwSize = sizeof(caps);
    assert(SUCCEEDED(keyboard->GetCapabilities(&caps)) && GET_DIDEVICE_TYPE(caps.dwDevType) == DI8DEVTYPE_KEYBOARD);
    caps.dwSize = sizeof(caps);
    assert(SUCCEEDED(mouse->GetCapabilities(&caps)) && GET_DIDEVICE_TYPE(caps.dwDevType) == DI8DEVTYPE_MOUSE);
    assert(SUCCEEDED(mouse->QueryInterface(Traits::deviceIID(), &same)) && same == mouse);
    static_cast<typename Traits::Device *>(same)->Release();
    assert(SUCCEEDED(mouse->QueryInterface(IID_IUnknown, &same)) && same == mouse);
    static_cast<IUnknown *>(same)->Release();
    BYTE keyboardState[256]; memset(keyboardState, 0x5a, sizeof(keyboardState));
    HRESULT keys = keyboard->GetDeviceState(sizeof(keyboardState), keyboardState);
    assert(FAILED(keys)); // No Acquire: the keyboard remains entirely native.
    DIMOUSESTATE2 state; memset(&state, 0x5a, sizeof(state));
    DIMOUSESTATE2 nativeState = state;
    auto systemMouse = static_cast<CameraDevice<Traits> *>(mouse)->sourceForFixture();
    HRESULT nativeResult = systemMouse->GetDeviceState(sizeof(nativeState), &nativeState);
    POINT position = {}; GetCursorPos(&position);
    HRESULT result = mouse->GetDeviceState(sizeof(state), &state);
    assert(FAILED(result) && result == nativeResult);
    assert(!memcmp(&state, &nativeState, sizeof(state))); // Preserve whatever bytes native input delivers, even on error.
    POINT after = {}; GetCursorPos(&after);
    assert(position.x == after.x && position.y == after.y);
    assert(FAILED(mouse->GetDeviceState(0, NULL)));
    typename Traits::Device *missing = NULL;
    const GUID missingGUID = {};
    assert(FAILED(input->CreateDevice(missingGUID, &missing, NULL)) && !missing);
    mouse->Release(); keyboard->Release();
    assert(input->Release() == 0);
}

int main() {
    assert(loadSystemInput());
    SetEnvironmentVariableA(trasc_camera::marker, "1");
    verifyInput<Ansi>(); verifyInput<Wide>();
    // Actual exported entry also preserves the direct system result when
    // this fixture executable fails the strict supported-client guard.
    IDirectInput8A *native = NULL;
    assert(SUCCEEDED(DirectInput8Create(GetModuleHandleW(NULL), DIRECTINPUT_VERSION,
        IID_IDirectInput8A, reinterpret_cast<void **>(&native), NULL)) && native);
    native->Release();
    assert(FAILED(DirectInput8Create(GetModuleHandleW(NULL), DIRECTINPUT_VERSION,
        IID_IDirectInput8A, NULL, NULL)));
    puts("PASS: ANSI/Unicode input, native keyboard, mouse wrapper, COM identity/refcounts, failure bytes, no cursor warp and unsupported-executable delegation");
}
