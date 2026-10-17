"""验证今日结束时即时移除与横向七日列。"""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from datetime import date,datetime,timedelta
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication,QLabel,QFrame
from app.database.store import Store
from app.ui.widget import ClassWidget

app = QApplication([])
app.setOrganizationName('ClassWidgetTest')
app.setApplicationName('LayoutSmoke')
class FakeNotifier:
    def show(self,*args):
        pass

with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as directory:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat,QSettings.Scope.UserScope,directory)
    store = Store(Path(directory)/'fixture.db')
    try:
        day = date.today()
        store.set_semester(day)
        for name,weekday,start,end in [('已结束课程',day.weekday(),'07:00','08:00'),('正在上的课',day.weekday(),'08:00','09:00'),('今天未上的课',day.weekday(),'10:00','11:00'),('明天的课',(day.weekday()+1)%7,'08:00','09:00')]:
            store.save(dict(name=name,room='A301',teacher='老师',color='#5579ef',reminder_enabled=False,slots=[dict(weekday=weekday,start=start,end=end,first_week=1,last_week=54,pattern='all',weeks='')]))
        w = ClassWidget(store,FakeNotifier())
        w.show()
        app.processEvents()
        now = datetime.now(w.zone).replace(hour=8,minute=30,second=0)
        w.update_date(now)
        labels = [l.text() for l in w.scroll.widget().findChildren(QLabel)]
        assert '明天的课' not in labels
        assert '正在上的课' in labels and '今天未上的课' in labels and '已结束课程' in labels
        from app.ui.course_views import CourseCard
        cards = w.scroll.widget().findChildren(CourseCard)
        assert [c.property('courseName') for c in cards]==['正在上的课','今天未上的课','已结束课程']
        ended = cards[-1]
        assert ended.findChild(QLabel,'endedCourse').font().strikeOut()
        from PySide6.QtTest import QTest
        normal = cards[0].geometry()
        from unittest.mock import patch
        with patch('app.ui.card_hover.reduced_motion',return_value=False):
            cards[0].animate_hover(True)
            cards[0].overlay.monitor.stop()
            QTest.qWait(380)
            assert cards[0].overlay.scale_progress==1
            assert cards[0].overlay.detail_progress==1
            assert cards[0].geometry()==normal
            cards[0].animate_hover(False)
            QTest.qWait(330)
            assert not cards[0].overlay.isVisible()
        w.update_date(now.replace(hour=9,minute=0))
        cards = w.scroll.widget().findChildren(CourseCard)
        assert [c.property('courseName') for c in cards]==['今天未上的课','已结束课程','正在上的课']
        assert not w.week_bar.isVisible()
        assert all('ClassWidget' not in l.text() for l in w.header.findChildren(QLabel))
        w.view_actions['week'].trigger()
        app.processEvents()
        rows = [f for f in w.scroll.widget().findChildren(QFrame) if f.property('weekday') is not None]
        rows.sort(key=lambda f:f.property('weekday'))
        assert len(rows)==7
        assert all(rows[i].y()<rows[i+1].y() for i in range(6))
        assert len({f.x() for f in rows})==1
        assert w.width()==420 and w.height()==480
        assert w.week_bar.isVisible()
        assert w.week_bar.parentWidget() == w.date_label.parentWidget()
        assert abs(w.week_bar.geometry().center().y()-w.date_label.geometry().center().y())<=2
        assert all(row.height()<=61 for row in rows)
        w.week_buttons[2].click()
        assert w.week_offset==1
        w.week_buttons[0].click()
        assert w.week_offset==0
        w.week_buttons[2].click()
        w.week_buttons[1].click()
        assert w.week_offset==0
        app.processEvents()
        cards = w.scroll.widget().findChildren(CourseCard)
        assert cards
        for card in cards:
            texts = [l.text() for l in card.findChildren(QLabel)]
            assert 'A301' not in texts and '老师' not in texts
            assert 'A301' in card.toolTip() and '老师' in card.toolTip()
            times = [l for l in card.findChildren(QLabel) if l.objectName()=='weekTime']
            assert len(times)==1 and '\n' not in times[0].text() and not times[0].wordWrap()
        for timer in (w.timer,w.reminder_timer,w.geometry_timer,w.screen_timer,w.mode_transition):
            timer.stop()
        app.removeNativeEventFilter(w.power_filter)
        app.screenAdded.disconnect(w.watch_screen)
        app.screenRemoved.disconnect(w.screen_removed)
        w.tray.hide()
        w.hide()
        w.deleteLater()
        app.processEvents()
    finally:
        store.close()
print('PASS: finished courses sorted last with strikeout, hover animation, vertical weekdays, single-line times, clean header')
