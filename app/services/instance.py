"""文件锁保证单实例，局域套接字通知已有窗口恢复。"""
import hashlib
from pathlib import Path
from PySide6.QtCore import QObject, QLockFile, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class InstanceGuard(QObject):
    restore_requested = Signal()

    def __init__(self,directory,parent=None):
        super().__init__(parent)
        directory = Path(directory)
        directory.mkdir(parents=True,exist_ok=True)
        self.name = 'ClassWidget-'+hashlib.sha256(str(directory.resolve()).lower().encode()).hexdigest()[:24]
        self.lock = QLockFile(str(directory/'classwidget.lock'))
        self.lock.setStaleLockTime(0)
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.sockets = set()
        self.primary = False
        self.ipc_error = ''

    def acquire(self):
        if not self.lock.tryLock(0):
            if self.lock.error() != QLockFile.LockError.LockFailedError:
                raise OSError('无法创建实例锁，请检查用户数据目录权限。')
            return False
        self.primary = True
        if not self.server.listen(self.name):
            # 单实例文件锁仍有效；通信受限制时可通过托盘恢复。
            self.ipc_error = self.server.errorString()
            return True
        self.server.newConnection.connect(self.accept_connections)
        return True

    def notify_existing(self):
        socket = QLocalSocket()
        socket.connectToServer(self.name)
        if not socket.waitForConnected(1500):
            return False
        socket.write(b'restore\n')
        socket.waitForBytesWritten(500)
        acknowledged = socket.waitForReadyRead(1500) and bytes(socket.readAll()) == b'ok\n'
        socket.disconnectFromServer()
        return acknowledged

    def accept_connections(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            self.sockets.add(socket)
            socket.readyRead.connect(lambda s=socket:self.read_request(s))
            socket.disconnected.connect(lambda s=socket:self.dispose_socket(s))
            QTimer.singleShot(2000,socket.abort)
            if socket.bytesAvailable():
                self.read_request(socket)

    def read_request(self,socket):
        data = (socket.property('request_buffer') or b'') + bytes(socket.readAll())
        if len(data)>128:
            socket.abort()
            return
        socket.setProperty('request_buffer',data)
        if b'\n' not in data:
            return
        if data == b'restore\n':
            self.restore_requested.emit()
            socket.write(b'ok\n')
            socket.flush()
        socket.disconnectFromServer()

    def dispose_socket(self,socket):
        self.sockets.discard(socket)
        socket.deleteLater()

    def close(self):
        self.server.close()
        for socket in list(self.sockets):
            socket.abort()
        if self.primary:
            self.lock.unlock()
            self.primary = False
