"""Windows 唤醒/时间变化通知；周期复算仍是可靠的兜底。"""
import ctypes
from ctypes import wintypes
import sys
from PySide6.QtCore import QAbstractNativeEventFilter, QTimer


class PowerTimeFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def nativeEventFilter(self, event_type, message):
        if sys.platform == 'win32' and bytes(event_type) in (b'windows_generic_MSG',b'windows_dispatcher_MSG'):
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x001E or (msg.message == 0x0218 and msg.wParam in (0x0007,0x0012)) or msg.message == 0x001A:
                QTimer.singleShot(100,self.callback)
        return False,0
