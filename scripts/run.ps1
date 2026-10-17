$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    throw '请先按 README.md 创建虚拟环境并安装依赖。'
}
& '.\.venv\Scripts\python.exe' main.py
