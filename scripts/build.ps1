$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
 $buildOriginalPath = $env:PATH
try {
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    $env:CLASSWIDGET_CONSOLE = '0'
    & '.\.venv\Scripts\python.exe' -m PyInstaller --noconfirm ClassWidget.spec
} finally {
    $env:PATH = $buildOriginalPath
}
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
Copy-Item -LiteralPath '使用说明.md' -Destination 'dist\ClassWidget\使用说明.md'
Copy-Item -LiteralPath 'THIRD_PARTY_NOTICES.md' -Destination 'dist\ClassWidget\THIRD_PARTY_NOTICES.md'
& '.\.venv\Scripts\python.exe' scripts\collect_licenses.py
if ($LASTEXITCODE -ne 0) { throw 'License collection failed.' }
Write-Output 'Build completed: dist\ClassWidget\ClassWidget.exe'
