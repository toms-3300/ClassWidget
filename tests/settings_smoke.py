"""第五阶段设置/数据界面检查，注册表和文件选择器均隔离。"""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from datetime import date
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox
from app.database.store import Store
from app.services.autostart import Autostart,VALUE_NAME
from app.services.data_exchange import export_file
from app.ui.widget import ClassWidget
from app.ui.settings import SettingsDialog
from app.ui.data_dialog import DataDialog
from test_autostart import FakeRegistry
from test_schedule import course

app = QApplication([])
app.setOrganizationName('ClassWidgetTest')
app.setApplicationName('SettingsSmoke')
class FakeNotifier:
    def show(self,*args):
        pass

with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as directory:
    root = Path(directory)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat,QSettings.Scope.UserScope,directory)
    store = Store(root/'current.db')
    try:
        store.set_semester(date.today())
        store.save(course())
        w = ClassWidget(store,FakeNotifier())
        w.show()
        app.processEvents()
        registry = FakeRegistry()
        service = Autostart(registry)
        dialog = SettingsDialog(w,service)
        assert not dialog.startup.isChecked() and registry.writes == 0
        dialog.reject()
        assert registry.writes == 0
        dialog = SettingsDialog(w,service)
        dialog.startup.setChecked(True)
        dialog.hidden.setChecked(True)
        dialog.save()
        assert VALUE_NAME in registry.values
        assert w.settings.value('window/start_hidden',False,type=bool)
        dialog = SettingsDialog(w,service)
        dialog.startup.setChecked(False)
        dialog.save()
        assert VALUE_NAME not in registry.values
        data = DataDialog(w)
        with patch('app.ui.data_dialog.QMessageBox.information'), patch('app.ui.data_dialog.QMessageBox.question',return_value=QMessageBox.StandardButton.Yes):
            csv_path = str(root/'课程.csv')
            with patch('app.ui.data_dialog.QFileDialog.getSaveFileName',return_value=(csv_path,'')):
                data.export_data('csv')
            assert Path(csv_path).exists()
            with patch('app.ui.data_dialog.QFileDialog.getOpenFileName',return_value=(csv_path,'')):
                data.import_data()
            assert len(store.all()) == 1
            backup = str(root/'backup.db')
            with patch('app.ui.data_dialog.QFileDialog.getSaveFileName',return_value=(backup,'')):
                data.backup()
            store.save(course(name='恢复前多余课程'))
            with patch('app.ui.data_dialog.QFileDialog.getOpenFileName',return_value=(backup,'')):
                data.restore()
            assert len(store.all()) == 1
        w.timer.stop()
        w.reminder_timer.stop()
        w.geometry_timer.stop()
        w.screen_timer.stop()
        app.removeNativeEventFilter(w.power_filter)
        app.screenAdded.disconnect(w.watch_screen)
        app.screenRemoved.disconnect(w.screen_removed)
        w.tray.hide()
        w.hide()
        w.deleteLater()
        app.processEvents()
    finally:
        store.close()
print('PASS: settings cancel/save, simulated startup opt-in/disable, hidden startup preference, data dialog export/import/backup/restore')
