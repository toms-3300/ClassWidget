"""从软件外部验证正式 EXE 原生样式，产品不包含测试入口。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import win32con
import win32api
import win32gui
import win32process

exe = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
report = {'passed':False,'executable':str(exe)}
with tempfile.TemporaryDirectory(dir=output.parent) as directory:
    env = dict(os.environ,LOCALAPPDATA=directory)
    process = subprocess.Popen([str(exe)],env=env)
    hwnd = None
    try:
        for _ in range(100):
            windows = []
            def callback(handle,_):
                if win32process.GetWindowThreadProcessId(handle)[1] == process.pid and win32gui.GetWindowText(handle)=='ClassWidget 课程表':
                    windows.append(handle)
            win32gui.EnumWindows(callback,None)
            if windows:
                hwnd = windows[0]
                break
            if process.poll() is not None:
                raise RuntimeError('EXE exited before showing its widget')
            time.sleep(.1)
        if hwnd is None:
            raise RuntimeError('widget not found')
        style = win32gui.GetWindowLong(hwnd,win32con.GWL_EXSTYLE)
        report['tool_window'] = bool(style&win32con.WS_EX_TOOLWINDOW)
        report['no_app_window'] = not bool(style&win32con.WS_EX_APPWINDOW)
        report['no_desktop_parent'] = win32gui.GetParent(hwnd)==0
        report['visible'] = bool(win32gui.IsWindowVisible(hwnd))
        report['passed'] = all(report[k] for k in ('tool_window','no_app_window','no_desktop_parent','visible'))
    except Exception as error:
        report['error'] = str(error)
    finally:
        if hwnd:
            thread = win32process.GetWindowThreadProcessId(hwnd)[0]
            win32api.PostThreadMessage(thread,win32con.WM_QUIT,0,0)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
raise SystemExit(0 if report['passed'] else 1)
