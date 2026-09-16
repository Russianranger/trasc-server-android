# Run in PowerShell on a Windows PC with Visual Studio's v142 14.29 x86 tools
# and Windows 10 SDK installed. No Microsoft files are shipped with TRASC.
param([string]$Output = "$PWD\trasc-msvc-sdk-x86.zip")
$ErrorActionPreference = 'Stop'
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vs = & $vswhere -latest -products '*' -property installationPath
$vc = Get-ChildItem "$vs\VC\Tools\MSVC\14.29.*" -Directory | Sort-Object Name -Descending | Select-Object -First 1
if (!$vc) { throw 'Install MSVC v142 - VS 2019 C++ x64/x86 build tools (14.29) in Visual Studio Installer.' }
$kits = "${env:ProgramFiles(x86)}\Windows Kits\10"
$sdk = Get-ChildItem "$kits\Include" -Directory | Where-Object { Test-Path "$kits\Lib\$($_.Name)\um\x86\kernel32.lib" } | Sort-Object Name -Descending | Select-Object -First 1
if (!$sdk) { throw 'Install the Windows 10 SDK in Visual Studio Installer.' }
$stage = Join-Path $env:TEMP ('trasc-sdk-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path "$stage\include", "$stage\lib" | Out-Null
try {
    Copy-Item "$($vc.FullName)\bin\Hostx64\x86" "$stage\bin" -Recurse
    $redist = Get-Item "$vs\VC\Redist\MSVC\14.29.*\x64\Microsoft.VC142.CRT" -ErrorAction SilentlyContinue | Select-Object -First 1
    if (!$redist) { $redist = Get-Item "$vs\VC\Redist\MSVC\*\x64\Microsoft.VC*.CRT" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1 }
    if ($redist) { Copy-Item "$($redist.FullName)\*.dll" "$stage\bin" -Force }
    Copy-Item "$($vc.FullName)\include" "$stage\include\msvc" -Recurse
    Copy-Item "$($vc.FullName)\lib\x86" "$stage\lib\msvc" -Recurse
    foreach ($name in @('ucrt','shared','um','winrt')) { Copy-Item "$($sdk.FullName)\$name" "$stage\include\$name" -Recurse }
    foreach ($name in @('ucrt','um')) { Copy-Item "$kits\Lib\$($sdk.Name)\$name\x86" "$stage\lib\$name" -Recurse }
    @{format='trasc-msvc-sdk-1';target='x86';msvc_version=$vc.Name;sdk_version=$sdk.Name} | ConvertTo-Json | Set-Content "$stage\sdk.json" -Encoding ascii
    Compress-Archive -Path "$stage\*" -DestinationPath $Output
    Write-Host "SDK saved to $Output. Transfer it to your Android device and choose Import Microsoft SDK ZIP."
} finally { Remove-Item $stage -Recurse -Force }
