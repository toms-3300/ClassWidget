"""Windows WinRT Toast，独立 AUMID 与当前用户开始菜单快捷方式。"""
import ctypes
from datetime import timezone
import math
import logging
from pathlib import Path
import subprocess
import sys
from PySide6.QtCore import QObject, Signal

AUMID = 'ClassWidget.Desktop.CourseSchedule'


def register_identity():
    if sys.platform != 'win32':
        raise RuntimeError('原生通知仅支持 Windows 10/11。')
    import winreg
    import pythoncom
    from win32com.shell import shell, shellcon
    from win32com.propsys import propsys
    from win32com.propsys.pscon import PKEY_AppUserModel_ID
    set_id = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
    set_id.argtypes = [ctypes.c_wchar_p]
    set_id.restype = ctypes.c_long
    result = set_id(AUMID)
    if result != 0:
        raise OSError(f'设置应用标识失败：HRESULT {result}')
    # 按 Windows-Toasts 文档注册专属名称，不借用 PowerShell/其他应用标识。
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf'Software\Classes\AppUserModelId\{AUMID}') as key:
        winreg.SetValueEx(key,'DisplayName',0,winreg.REG_SZ,'ClassWidget 课程表')
    programs = Path(shell.SHGetFolderPath(0, shellcon.CSIDL_PROGRAMS, None, 0))
    programs.mkdir(parents=True, exist_ok=True)
    link_path = programs / 'ClassWidget 课程表.lnk'
    link = pythoncom.CoCreateInstance(shell.CLSID_ShellLink,None,pythoncom.CLSCTX_INPROC_SERVER,shell.IID_IShellLink)
    if getattr(sys,'frozen',False):
        executable, arguments = sys.executable, ''
    else:
        executable = str(Path(sys.executable).with_name('pythonw.exe'))
        if not Path(executable).exists():
            executable = sys.executable
        arguments = subprocess.list2cmdline([str(Path(__file__).resolve().parents[2] / 'main.py')])
    link.SetPath(executable)
    link.SetArguments(arguments)
    link.SetWorkingDirectory(str(Path(executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[2]))
    link.SetDescription('ClassWidget 桌面课程表（不是开机自启动）')
    property_store = link.QueryInterface(propsys.IID_IPropertyStore)
    property_store.SetValue(PKEY_AppUserModel_ID, propsys.PROPVARIANTType(AUMID,pythoncom.VT_LPWSTR))
    property_store.Commit()
    link.QueryInterface(pythoncom.IID_IPersistFile).Save(str(link_path),True)
    return link_path


class WindowsNotifier(QObject):
    failed = Signal(object, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.toaster = None

    def ensure_ready(self):
        if self.toaster is None:
            from windows_toasts import InteractableWindowsToaster
            register_identity()
            self.toaster = InteractableWindowsToaster('ClassWidget', notifierAUMID=AUMID)
        from winrt.windows.ui.notifications import NotificationSetting
        try:
            setting = self.toaster.toastNotifier.setting
        except OSError as error:
            # 部分未打包应用首次发送前查询 setting 返回 E_ELEMENTNOTFOUND。
            # 不把“查询不到状态”视为成功或禁用，仍通过真实 show() 检验提交。
            if error.winerror != -2147023728:
                raise
            logging.warning('Windows 通知状态暂不可查询：%s',error)
            return
        if setting != NotificationSetting.ENABLED:
            raise RuntimeError('Windows 已禁用本应用通知，请检查系统通知设置。')

    def show(self, items, now, keys):
        self.ensure_ready()
        from windows_toasts import Toast
        details = []
        for item in items[:3]:
            course = item['course']
            minutes = max(1,math.ceil((item['start'].astimezone(timezone.utc)-now.astimezone(timezone.utc)).total_seconds()/60))
            details.append(f"{course['name'][:50]}\n{item['start']:%H:%M} 开始 · 地点：{course['room'] or '未填写'}\n距离上课还有 {minutes} 分钟")
        if len(items) > 3:
            details.append(f'另有 {len(items)-3} 个上课安排，请打开课程表查看。')
        toast = Toast(['即将上课','\n\n'.join(details)], expiration_time=min(i['start'] for i in items).astimezone(timezone.utc), group='courses')
        toast.on_failed = lambda event: self.failed.emit(keys, str(event.error_code))
        self.toaster.show_toast(toast)

