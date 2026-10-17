# 第三方组件

ClassWidget 使用 Python、PySide6/Qt、SQLite、Windows-Toasts、pywin32、PyWinRT、tzlocal、tzdata，并由 PyInstaller 打包。

PySide6/Qt 为 LGPL/GPL/商业多重许可；本发行使用开源发行物。PyInstaller 有针对生成程序的许可证例外。各组件版权归原作者，详见发行文件夹 licenses 下的原始许可及 Qt 的许可文件。

未修改第三方库源代码。发行采用动态库目录形式，保留各组件原始许可。重新分发或商业使用前应核查对应版本的许可义务。

Qt 与 PySide6 使用 LGPLv3 开源发行物。用户可以替换 `_internal` 中接口兼容的 Qt/PySide 动态库，用于调试库修改；本项目不限制这种修改及调试。许可证原文见 licenses/LGPL-3.0-only.txt 和 licenses/GPL-3.0-only.txt。

上游源代码：https://code.qt.io/qt/qtbase.git/ 、https://code.qt.io/pyside/pyside-setup.git/ （本次使用 6.12.0），PyWinRT：https://github.com/pywinrt/pywinrt （3.2.1）。应用源码、构建脚本及测试已在项目工作区交付。
