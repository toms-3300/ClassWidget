"""ClassWidget 应用入口。"""
import sys
import sqlite3
import logging
from logging.handlers import RotatingFileHandler
from app.database.store import default_path
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon
from app.ui.widget import ClassWidget
from app.services.instance import InstanceGuard


def main():
    app = QApplication(sys.argv)
    app.setOrganizationName("ClassWidget")
    app.setApplicationName("ClassWidget")
    app.setQuitOnLastWindowClosed(False)
    guard = None
    try:
        guard = InstanceGuard(default_path().parent)
        if not guard.acquire():
            if '--autostart' not in sys.argv and not guard.notify_existing():
                QMessageBox.information(None,'ClassWidget 已在运行','请通过托盘“课”图标恢复窗口。如果刚启动，请稍等再试。')
            return 0
        log_dir = default_path().parent / 'logs'
        log_dir.mkdir(parents=True,exist_ok=True)
        logging.basicConfig(level=logging.INFO, handlers=[RotatingFileHandler(log_dir / 'classwidget.log',maxBytes=500000,backupCount=2,encoding='utf-8')],format='%(asctime)s %(levelname)s %(message)s')
        if guard.ipc_error:
            logging.warning('恢复窗口通信不可用，单实例锁仍有效：%s',guard.ipc_error)
        window = ClassWidget()
        guard.restore_requested.connect(window.restore_window)
        app.aboutToQuit.connect(guard.close)
    except (sqlite3.Error, OSError, RuntimeError, ValueError) as error:
        if guard:
            guard.close()
        QMessageBox.critical(None, '无法启动 ClassWidget', f'启动失败：\n{error}')
        return 1
    def report_exception(kind,error,trace):
        logging.critical('未处理的界面异常',exc_info=(kind,error,trace))
        QMessageBox.critical(window,'操作发生异常',f'{error}\n错误详情已保存到日志，请反馈给开发者。')
    sys.excepthook = report_exception
    start_hidden = '--autostart' in sys.argv and window.settings.value('window/start_hidden',False,type=bool) and QSystemTrayIcon.isSystemTrayAvailable()
    if not start_hidden:
        window.show()
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.warning(window, "系统托盘不可用", "当前环境没有系统托盘。请通过窗口右键菜单退出程序。")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
