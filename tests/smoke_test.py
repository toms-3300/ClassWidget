"""离屏结构验证，不代替真实 Windows 鼠标/托盘验收。"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings, QPoint
from PySide6.QtWidgets import QApplication, QLabel, QSystemTrayIcon
from app.ui.widget import ClassWidget
from app.database.store import Store
from app.ui.manager import CourseEditor, CourseManager
from app.ui.reminder_settings import ReminderSettings
from datetime import date, datetime

app = QApplication([])
app.setOrganizationName("ClassWidgetTest")
app.setApplicationName("SmokeTest")
with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as directory:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, directory)
    store = Store(Path(directory) / 'test.db')
    class FakeNotifier:
        def show(self, items, now, keys):
            pass
        def test(self):
            pass
    window = ClassWidget(store,FakeNotifier())
    assert window.size().width() == 340 and window.minimumSize() == window.maximumSize()
    assert any('添加课程' in label.text() for label in window.findChildren(QLabel))
    store.set_semester(date.today())
    store.save(dict(name='高等数学',teacher='张老师',room='A301',color='#5579ef',reminder_enabled=True,slots=[dict(weekday=date.today().weekday(),start='08:00',end='09:40',first_week=1,last_week=20,pattern='all',weeks='')]))
    window.update_date(datetime.now(window.zone).replace(hour=7,minute=0,second=0))
    assert any(label.text() == "高等数学" for label in window.findChildren(QLabel))
    assert not window.next_label.isVisible() and not window.next_label.text()
    reminder_settings = ReminderSettings(store)
    reminder_settings.presets.setCurrentIndex(1)
    assert reminder_settings.minutes.value() == 5
    editor_override = CourseEditor(store,store.all()[0])
    editor_override.override.setChecked(True)
    editor_override.reminder_minutes.setValue(10)
    assert editor_override.value()['reminder_minutes'] == 10
    window.set_view('week')
    assert any('周日' in label.text() for label in window.findChildren(QLabel))
    window.shift_week(1)
    assert window.week_offset == 1
    window.current_week()
    window.set_view('today')
    editor = CourseEditor(store,store.all()[0])
    assert editor.value()['name'] == '高等数学'
    editor.add_slot()
    assert len(editor.value()['slots']) == 2
    editor.remove_slot(editor.table.cellWidget(1,7))
    assert len(editor.value()['slots']) == 1
    manager = CourseManager(store)
    assert manager.list.count() == 1
    window.move(100, 100)
    window.save_position()
    assert window.settings.value("window/position", type=QPoint) == QPoint(100, 100)
    window.show()
    app.processEvents()
    with patch.object(QSystemTrayIcon, "isSystemTrayAvailable", return_value=True):
        window.close()
    assert not window.isVisible()
    window.restore_window()
    assert window.isVisible()
    window.tray.hide()
    window.timer.stop()
    window.reminder_timer.stop()
    app.removeNativeEventFilter(window.power_filter)
    window.hide()
    window.deleteLater()
    app.processEvents()
    store.close()
print("PASS: 今日/周视图、管理界面、多时间编辑、位置持久化、关闭隐藏、恢复显示")
