"""真实双进程文件锁与窗口恢复请求验证，使用隔离目录。"""
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
from app.services.instance import InstanceGuard

app = QCoreApplication([])
if '--child' in sys.argv:
    guard = InstanceGuard(sys.argv[-1])
    assert not guard.acquire(), 'second instance incorrectly acquired the lock'
    assert guard.notify_existing(), 'could not send restore request'
    guard.close()
    print('SECONDARY: lock denied, restore sent')
else:
    with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as directory:
        guard = InstanceGuard(directory)
        try:
            assert guard.acquire()
            assert not guard.ipc_error,guard.ipc_error
            received = []
            guard.restore_requested.connect(lambda:received.append(True))
            child = subprocess.Popen([sys.executable,__file__,'--child',directory],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            loop = QEventLoop()
            poll = QTimer()
            poll.timeout.connect(lambda:loop.quit() if child.poll() is not None else None)
            poll.start(50)
            QTimer.singleShot(8000,loop.quit)
            loop.exec()
            poll.stop()
            if child.poll() is None:
                child.kill()
            stdout,stderr = child.communicate(timeout=2)
            assert child.returncode == 0, stdout+stderr
            assert received == [True], 'restore request not received exactly once'
        finally:
            guard.close()
        successor = InstanceGuard(directory)
        try:
            assert successor.acquire(), 'lock not released after exit'
        finally:
            successor.close()
    print('PASS: two processes, single instance, restore message, exit lock release')
