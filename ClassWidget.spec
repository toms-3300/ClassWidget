# Windows x64 onedir 构建。显式收集动态 WinRT 扩展和时区数据库。
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
import os
console_build = os.environ.get('CLASSWIDGET_CONSOLE') == '1'
build_name = 'ClassWidgetDebug' if console_build else 'ClassWidget'

hidden = collect_submodules('winrt') + [
    'winrt.windows.ui.notifications', 'winrt.windows.foundation',
    'winrt.windows.foundation.collections', 'winrt.windows.data.xml.dom',
    'win32com.shell.shell', 'win32com.shell.shellcon',
    'win32com.propsys.propsys', 'win32com.propsys.pscon',
]
a = Analysis(['main.py'], pathex=[SPECPATH],
    binaries=[], datas=collect_data_files('tzdata'), hiddenimports=hidden,
    hookspath=[], runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore','PySide6.QtWebEngineWidgets','PySide6.QtWebEngineQuick',
              'PySide6.QtQml','PySide6.QtQuick','PySide6.QtQuickWidgets','PySide6.QtPdf','PySide6.QtPdfWidgets'],
    noarchive=False)
# Qt 6.12 在 Windows 使用系统 ICU。避免构建主机 PATH 中 Poppler 的
# 同名 ICU 78 被误收集，覆盖系统未加版本后缀的 ICU 接口。
a.binaries = [entry for entry in a.binaries if entry[0].lower() not in ('icuuc.dll','icudt78.dll')]
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name=build_name,
    debug=False,strip=False,upx=False,console=console_build,
    icon=str(SPECPATH)+'/assets/classwidget.ico')
coll = COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name=build_name)
