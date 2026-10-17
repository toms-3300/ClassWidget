"""用隔离数据生成界面预览；不触碰真实课程和用户设置。"""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys
from datetime import date
from pathlib import Path
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from unittest.mock import patch
from app.ui.course_views import CourseCard
from app.database.store import Store
from app.ui.widget import ClassWidget

root = Path(__file__).resolve().parents[1]
output = root / '.artifacts'
output.mkdir(exist_ok=True)
app = QApplication([])
app.setOrganizationName('ClassWidgetPreview')
app.setApplicationName('Preview')
class FakeNotifier:
    def show(self,*args):
        pass

with tempfile.TemporaryDirectory(dir=root) as directory:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat,QSettings.Scope.UserScope,directory)
    store = Store(Path(directory)/'preview.db')
    try:
        store.set_semester(date.today())
        for name,start,end,color,room in [('高等数学','08:00','09:40','#5579ef','教学楼 A301'),('大学英语','10:00','11:40','#28a58b','教学楼 B205'),('程序设计基础','14:00','15:40','#a06ae0','实验楼 C102')]:
            store.save(dict(name=name,teacher='张老师',room=room,color=color,reminder_enabled=False,slots=[dict(weekday=weekday,start=start,end=end,first_week=1,last_week=20,pattern='all',weeks='') for weekday in range(5)]))
        widget = ClassWidget(store,FakeNotifier())
        widget.show()
        for mode,theme in [('today','light'),('mini','dark'),('week','dark')]:
            widget.set_view(mode)
            widget.apply_appearance(theme,100,False,False)
            app.processEvents()
            widget.grab().save(str(output/f'{mode}-{theme}.png'))
            cards = widget.scroll.widget().findChildren(CourseCard) if mode != 'mini' else []
            if cards:
                with patch('app.ui.card_hover.reduced_motion',return_value=False), patch('app.ui.card_hover.HoverOverlay.check_pointer'):
                    cards[0].animate_hover(True)
                    cards[0].overlay.monitor.stop()
                    QTest.qWait(400)
                    widget.grab().save(str(output/f'{mode}-{theme}-hover.png'))
                    cards[0].overlay.dismiss()
        widget.timer.stop()
        widget.reminder_timer.stop()
        widget.geometry_timer.stop()
        widget.screen_timer.stop()
        app.removeNativeEventFilter(widget.power_filter)
        app.screenAdded.disconnect(widget.watch_screen)
        app.screenRemoved.disconnect(widget.screen_removed)
        widget.tray.hide()
        widget.hide()
        widget.deleteLater()
        app.processEvents()
    finally:
        store.close()
print('Previews:',output)
