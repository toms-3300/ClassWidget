"""第四阶段界面检查；可用 QT_QPA_PLATFORM=windows 做原生平台验证。"""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys
from pathlib import Path
import tempfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QPoint, QRect, QSize, QSettings, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from app.database.store import Store
from app.ui.widget import ClassWidget
from app.ui.window_settings import WindowSettings

app = QApplication([])
app.setOrganizationName('ClassWidgetTest')
app.setApplicationName('WindowSmoke')
class FakeNotifier:
    def show(self,*args):
        pass
    def test(self):
        pass

def shutdown(window):
    window.timer.stop()
    window.reminder_timer.stop()
    window.geometry_timer.stop()
    window.screen_timer.stop()
    app.removeNativeEventFilter(window.power_filter)
    app.screenAdded.disconnect(window.watch_screen)
    app.screenRemoved.disconnect(window.screen_removed)
    window.tray.hide()
    window.hide()
    window.deleteLater()
    app.processEvents()

with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as directory:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat,QSettings.Scope.UserScope,directory)
    store = Store(Path(directory)/'test.db')
    try:
        w = ClassWidget(store,FakeNotifier())
        w.show()
        app.processEvents()
        assert w.windowFlags() & Qt.WindowType.Tool
        assert all('贴附' not in action.text() and '测试' not in action.text() for action in w.menu.actions())
        assert not hasattr(w,'grip')
        assert not any(a.text()=='显示模式' for a in w.menu.actions())
        assert any(a.text()=='显示模式' for a in w.tray_menu.actions())
        for locked in (False,True):
            w.set_locked(locked)
            for mode in ('today','mini','week'):
                w.view_actions[mode].trigger()
                assert w.view == mode
                assert w.minimumSize()==w.maximumSize()==w.size()
                original = w.size()
                w.resize(999,999)
                assert w.size()==original
        w.set_view('mini')
        app.processEvents()
        assert not w.scroll.isVisible()
        assert ':' in w.date_label.text()
        assert w.size()==QSize(280,156)
        double = QMouseEvent(QMouseEvent.Type.MouseButtonDblClick,QPoint(5,5),QPoint(100,100),Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
        w.header.mouseDoubleClickEvent(double)
        assert w.view=='mini'
        w.set_view('today')
        w.apply_appearance('dark',70,True,True)
        assert not w.hide_button.isEnabled()
        w.hide_button.click()
        assert w.isVisible()
        assert '#191e2b' in w.styleSheet()
        assert abs(w.windowOpacity()-.7)<.01
        assert w.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
        press = QMouseEvent(QMouseEvent.Type.MouseButtonPress,QPoint(5,5),QPoint(100,100),Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
        w.header.mousePressEvent(press)
        assert w.header.offset is None
        w.set_locked(False)
        assert w.hide_button.isEnabled()
        w.hide_button.click()
        if w.tray.isSystemTrayAvailable():
            assert not w.isVisible()
        else:
            assert w.isMinimized()
        w.restore_window()
        w.header.mousePressEvent(press)
        assert w.header.offset is not None
        w.header.offset = None
        dialog = WindowSettings(w)
        assert dialog.value() == dict(theme='dark',opacity=70,locked=False,topmost=True)
        with patch.object(w,'available_areas',return_value=[QRect(0,0,800,600)]):
            w.move(-1000,100)
            w.screen_layout_changed()
            assert QRect(0,0,800,600).contains(w.geometry())
        w.set_view('mini')
        w.set_locked(True)
        w.save_position()
        saved_size = w.size()
        w.hide()
        w.set_topmost(False)
        assert not w.isVisible()
        shutdown(w)
        restored = ClassWidget(store,FakeNotifier())
        assert restored.view == 'mini' and restored.size() == saved_size
        assert restored.theme == 'dark' and restored.opacity_percent == 70 and not restored.topmost
        assert restored.locked and not restored.hide_button.isEnabled()
        restored.set_topmost(True)
        assert not restored.isVisible()
        restored.restore_window()
        assert restored.isVisible()
        shutdown(restored)
    finally:
        store.close()
print('PASS: fixed sizes in every mode/lock state, tray-only switching, no double-click switch, appearance and restart restore')
