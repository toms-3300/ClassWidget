"""仅用户保存开关时配置当前用户 Run 项；默认不写注册表。"""
from pathlib import Path
import subprocess
import sys

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
VALUE_NAME = 'ClassWidget'


def startup_command(executable=None, entry=None, frozen=None):
    frozen = getattr(sys,'frozen',False) if frozen is None else frozen
    executable = Path(executable or sys.executable)
    if frozen:
        args = [str(executable),'--autostart']
    else:
        pythonw = executable.with_name('pythonw.exe')
        if pythonw.exists():
            executable = pythonw
        args = [str(executable),str(entry or Path(__file__).resolve().parents[2]/'main.py'),'--autostart']
    command = subprocess.list2cmdline(args)
    if len(command) > 260:
        raise ValueError('启动命令超过 Windows Run 项长度限制，请将程序放在较短路径。')
    return command


class Autostart:
    def __init__(self,registry=None):
        if registry is None:
            if sys.platform != 'win32':
                raise RuntimeError('开机自启动仅支持 Windows。')
            import winreg
            registry = winreg
        self.registry = registry

    def current_command(self):
        r = self.registry
        try:
            with r.OpenKey(r.HKEY_CURRENT_USER,RUN_KEY,0,r.KEY_READ) as key:
                value,_ = r.QueryValueEx(key,VALUE_NAME)
                return value
        except FileNotFoundError:
            return None

    def set_enabled(self,enabled):
        r = self.registry
        if enabled:
            command = startup_command()
            with r.CreateKeyEx(r.HKEY_CURRENT_USER,RUN_KEY,0,r.KEY_SET_VALUE) as key:
                r.SetValueEx(key,VALUE_NAME,0,r.REG_SZ,command)
        elif self.current_command() is not None:
            with r.OpenKey(r.HKEY_CURRENT_USER,RUN_KEY,0,r.KEY_SET_VALUE) as key:
                try:
                    r.DeleteValue(key,VALUE_NAME)
                except FileNotFoundError:
                    pass
