$ErrorActionPreference = 'Stop'
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$installation = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (!$installation) { throw 'A Visual Studio C++ installation is required' }
$vcvars = Join-Path $installation 'VC\Auxiliary\Build\vcvars32.bat'
$commands = @(
  ('call "' + $vcvars + '"'),
  'cl /nologo /EHsc /std:c++14 /W4 tests\traditional_camera_proxy.cpp /Fe:camera-proxy-test.exe /link user32.lib dxguid.lib',
  'camera-proxy-test.exe',
  'cl /nologo /EHsc /std:c++14 /W4 tests\camera_mouse_state.cpp /Fe:camera-state-test.exe /link user32.lib',
  'camera-state-test.exe'
)
& cmd.exe /d /s /c ($commands -join ' && ')
if ($LASTEXITCODE -ne 0) { throw 'Traditional camera proxy or state fixture failed' }
