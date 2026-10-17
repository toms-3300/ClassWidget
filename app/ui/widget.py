"""普通悬浮窗口；不使用 Explorer 内部桌面挂载机制。"""
from datetime import datetime, timedelta
import logging
import sqlite3
import json
from tzlocal import reload_localzone

from PySide6.QtCore import QPoint, QRect, QSize, QSettings, Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
    QLabel, QMenu, QPushButton, QScrollArea, QSystemTrayIcon, QVBoxLayout, QWidget,
    QMessageBox,
    QSizePolicy,
)
from app.database.store import Store
from app.services.schedule import occurrences, status, teaching_week
from app.ui.manager import CourseManager
from app.ui.reminder_settings import ReminderSettings
from app.services.reminders import ReminderScheduler, countdown_text
from app.services.notifications import WindowsNotifier
from app.services.power import PowerTimeFilter
from app.ui.appearance import DEFAULT_SIZES, fit_geometry, stylesheet, mode_size
from app.ui.course_views import today_view, week_view
from app.ui.window_settings import WindowSettings
from app.ui.settings import SettingsDialog
from app.ui.data_dialog import DataDialog


def make_icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#5579ef"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(4, 4, 56, 56, 14, 14)
    painter.setPen(QColor("white"))
    font = painter.font()
    font.setPixelSize(36)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "课")
    painter.end()
    return QIcon(pixmap)


class DragHeader(QFrame):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.offset = None
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.window.locked:
            self.offset = event.globalPosition().toPoint() - self.window.pos()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self.window.locked and self.offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window.move(event.globalPosition().toPoint() - self.offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.offset = None
        self.window.ensure_visible()
        self.window.save_position()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self,event):
        self.offset = None
        event.ignore()


class ClassWidget(QWidget):
    def __init__(self, store=None, notifier=None):
        super().__init__()
        self.store = store if store is not None else Store()
        self.view = 'today'
        self.week_offset = 0
        self.settings = QSettings()
        self.settings.remove('window/desktop_enabled')
        # 旧版外观偏好迁移：首次升级时关闭置顶并重设迷你尺寸。
        if not self.settings.value('window/redesign_v1',False,type=bool):
            self.settings.setValue('window/topmost',False)
            self.settings.setValue('window/size/mini',DEFAULT_SIZES['mini'])
            self.settings.setValue('window/redesign_v1',True)
        self._render_signature = None
        self._render_count = 0
        self._today_count = 0
        self.mode_transition = QPropertyAnimation(self,b'windowOpacity',self)
        self.mode_transition.setDuration(140)
        self.mode_transition.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._switching = True
        self._ready = False
        self._last_expanded = self.settings.value('window/expanded_view','today')
        if self._last_expanded not in ('today','week'):
            self._last_expanded = 'today'
        self.locked = self.settings.value('window/locked',False,type=bool)
        self.topmost = self.settings.value('window/topmost',False,type=bool)
        self.theme = self.settings.value('window/theme','light')
        if self.theme not in ('light','dark'):
            self.theme = 'light'
        try:
            self.opacity_percent = max(35,min(100,int(self.settings.value('window/opacity',100))))
        except (TypeError,ValueError):
            self.opacity_percent = 100
        for mode in DEFAULT_SIZES:
            self.settings.remove(f'window/size/{mode}')
        self.geometry_timer = QTimer(self)
        self.geometry_timer.setSingleShot(True)
        self.geometry_timer.timeout.connect(self.save_position)
        self.screen_timer = QTimer(self)
        self.screen_timer.setSingleShot(True)
        self.screen_timer.timeout.connect(self.screen_layout_changed)
        self._watched_screens = set()
        self.zone = reload_localzone()
        self.notification_error = ''
        self.notifier = notifier if notifier is not None else WindowsNotifier(self)
        if hasattr(self.notifier,'failed'):
            self.notifier.failed.connect(self.notification_failed, Qt.ConnectionType.QueuedConnection)
        self.scheduler = ReminderScheduler(self.store,self.notifier.show,getattr(self.notifier,'ensure_ready',None))
        self.setWindowTitle("ClassWidget 课程表")
        flags = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
        if self.topmost:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.resize(360, 480)

        self.setWindowOpacity(self.opacity_percent / 100)
        icon = make_icon()
        self.setWindowIcon(icon)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        panel = QFrame()
        self.panel = panel
        panel.setObjectName("panel")
        outer.addWidget(panel)
        shadow = QGraphicsDropShadowEffect(panel)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(30, 40, 70, 55))
        panel.setGraphicsEffect(shadow)
        layout = QVBoxLayout(panel)
        self.panel_layout = layout
        layout.setContentsMargins(18, 14, 18, 16)
        layout.setSpacing(12)
        header = DragHeader(self)
        self.header = header
        row = QHBoxLayout(header)
        row.setContentsMargins(0, 0, 0, 0)
        title = QLabel("课程表")
        title.setObjectName("title")
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        row.addWidget(title)
        row.addStretch()
        hide = QPushButton("—")
        self.hide_button = hide
        hide.setToolTip("隐藏到系统托盘")
        hide.setFixedSize(26, 26)
        hide.clicked.connect(self.hide_to_tray)
        row.addWidget(hide)
        layout.addWidget(header)
        self.date_label = QLabel()
        self.date_label.setObjectName("date")
        date_row = QHBoxLayout()
        date_row.addWidget(self.date_label)
        self.mini_remaining = QLabel()
        self.mini_remaining.setTextFormat(Qt.TextFormat.PlainText)
        self.mini_remaining.setObjectName('countdown')
        self.mini_remaining.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        date_row.addWidget(self.mini_remaining)
        self.mini_remaining.hide()
        layout.addLayout(date_row)
        self.next_label = QLabel()
        self.next_label.setTextFormat(Qt.TextFormat.PlainText)
        self.next_label.setWordWrap(True)
        self.next_label.setObjectName('nextCourse')
        layout.addWidget(self.next_label)
        self.week_bar = QWidget()
        navigation = QHBoxLayout(self.week_bar)
        navigation.setContentsMargins(0,0,0,0)
        self.week_bar.setFixedWidth(90)
        navigation.setSpacing(3)
        self.week_buttons = []
        for text,tooltip,width,callback in [('‹','上一周',24,lambda:self.shift_week(-1)),('本周','返回本周',36,self.current_week),('›','下一周',24,lambda:self.shift_week(1))]:
            button = QPushButton(text)
            button.setObjectName('weekNav')
            button.setToolTip(tooltip)
            button.setFixedSize(width,24)
            button.clicked.connect(callback)
            navigation.addWidget(button)
            self.week_buttons.append(button)
        date_row.addWidget(self.week_bar)
        self.week_bar.hide()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMinimumSize(0,0)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Ignored)
        self.scroll = scroll
        layout.addWidget(scroll, 1)
        footer = QLabel("拖动顶部移动 · 托盘切换模式")
        self.footer = footer
        footer.setObjectName("note")
        bottom = QHBoxLayout()
        bottom.addWidget(footer,1)
        layout.addLayout(bottom)
        self.setStyleSheet(stylesheet(self.theme))
        self.menu = QMenu(self)
        self.menu.addAction("打开课程表", self.restore_window)
        self.menu.addAction("显示 / 隐藏小组件", self.toggle_visible)
        self.menu.addAction("课程管理与学期设置", self.manage_courses)
        self.menu.addAction('查看下一节课',self.show_next_course)
        self.reminder_action = self.menu.addAction('开启提醒')
        self.reminder_action.setCheckable(True)
        self.reminder_action.setChecked(self.store.reminder_options()['enabled'])
        self.reminder_action.triggered.connect(self.toggle_reminders)
        self.menu.addAction('提醒设置',self.open_reminder_settings)
        self.lock_action = self.menu.addAction('锁定位置')
        self.lock_action.setCheckable(True)
        self.lock_action.setChecked(self.locked)
        self.lock_action.triggered.connect(self.set_locked)
        self.topmost_action = self.menu.addAction('始终置顶')
        self.topmost_action.setCheckable(True)
        self.topmost_action.setChecked(self.topmost)
        self.topmost_action.triggered.connect(self.set_topmost)
        self.menu.addAction('窗口外观与交互',self.open_window_settings)
        self.menu.addAction('数据导入导出与备份',self.open_data_dialog)
        self.menu.addAction('设置',self.open_settings)
        self.menu.addSeparator()
        self.menu.addAction("退出软件", self.quit_app)
        self.tray_menu = QMenu(self)
        self.view_actions = {}
        for index,action in enumerate(self.menu.actions()):
            self.tray_menu.addAction(action)
            if index == 1:
                view_menu = self.tray_menu.addMenu('显示模式')
                for name,mode in [('今日模式','today'),('迷你模式','mini'),('周视图','week')]:
                    view_action = view_menu.addAction(name)
                    view_action.setCheckable(True)
                    view_action.triggered.connect(lambda checked=False,view=mode:self.set_view(view))
                    self.view_actions[mode] = view_action
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("ClassWidget · 课程表")
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self.tray_activated)
        self.tray.show()
        self.update_date()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_date)
        self.timer.start(60000)
        self.reminder_timer = QTimer(self)
        self.reminder_timer.timeout.connect(self.check_reminders)
        self.reminder_timer.start(20000)
        self.power_filter = PowerTimeFilter(self.check_reminders)
        QApplication.instance().installNativeEventFilter(self.power_filter)
        QTimer.singleShot(0,self.check_reminders)
        self._switching = False
        saved_view = self.settings.value('window/view','today')
        if saved_view not in DEFAULT_SIZES:
            saved_view = 'today'
        self.set_view(saved_view,remember=False)
        self.restore_position()
        self._ready = True
        self.update_lock_cursor()
        app = QApplication.instance()
        app.screenAdded.connect(self.watch_screen)
        app.screenRemoved.connect(self.screen_removed)
        for screen in app.screens():
            self.watch_screen(screen)
        self.bind_screen_window()

    def update_date(self,now=None):
        now = now or datetime.now(self.zone)
        local_now = now.replace(tzinfo=None)
        self.date_label.setToolTip('')
        weekday = '一二三四五六日'[now.weekday()]
        semester = self.store.semester()
        courses = self.store.all()
        week = teaching_week(now.date(),semester) if semester else None
        week_label = '未设置学期' if week is None else ('学期未开始' if week < 1 else f'第{week}周')
        if self.view == 'today':
            self.next_label.setText('')
            self.next_label.setToolTip('')
            self.date_label.setText(f'{now:%m月%d日} 周{weekday} · {week_label}')
            self.render_courses(local_now)
        elif self.view == 'week':
            monday = now.date()-timedelta(days=now.weekday())+timedelta(weeks=self.week_offset)
            shown = teaching_week(monday,semester) if semester else None
            label = '未设置学期' if shown is None else ('学期开始前' if shown < 1 else f'第{shown}教学周')
            self.date_label.setText(label)
            self.date_label.setToolTip(f'{monday:%Y/%m/%d} — {monday+timedelta(days=6):%Y/%m/%d}')
            self.render_courses(local_now)
        else:
            self.date_label.setText(f'{now:%H:%M}')
            summary = countdown_text(courses,semester,now)
            lines = summary.splitlines()
            next_line = next((line for line in lines if line.startswith('下一节：')),None)
            if next_line:
                index = lines.index(next_line)
                details = lines[index+1].split(' · ',1)
                self.next_label.setText(next_line.replace('下一节：','',1)[:18]+'\n'+details[0].split(' ',1)[-1]+' · '+(details[1][:13] if len(details)>1 else ''))
                self.mini_remaining.setText(lines[-1].replace('距离上课还有 ','').replace(' 分钟','分').replace(' 小时','小时'))
            else:
                self.next_label.setText(lines[-1])
                self.mini_remaining.setText('暂无安排')
            self.next_label.setToolTip(summary)
        self.apply_mode_size()

    def check_reminders(self):
        try:
            self.zone = reload_localzone()
            self.scheduler.check(datetime.now(self.zone))
            self.update_date()
        except Exception as error:
            logging.exception('提醒检查失败')
            self.notification_error = str(error)
            self.tray.setToolTip('ClassWidget · 提醒异常，请打开提醒设置检查')

    def notification_failed(self,keys,error):
        self.notification_error = 'Windows 通知失败：' + error
        logging.error('%s',self.notification_error)
        if keys:
            try:
                self.store.finish_events(keys,'failed',datetime.now(self.zone),error)
            except sqlite3.Error:
                logging.exception('通知失败状态保存失败')
        self.tray.setToolTip('ClassWidget · 通知失败，请检查系统通知设置')

    def open_reminder_settings(self):
        if self.notification_error:
            QMessageBox.warning(self,'最近一次提醒异常',self.notification_error)
        ReminderSettings(self.store,self).exec()
        self.reminder_action.setChecked(self.store.reminder_options()['enabled'])
        self.check_reminders()

    def toggle_reminders(self,checked):
        try:
            self.store.set_settings({'reminders_enabled':int(checked)})
        except sqlite3.Error as error:
            self.reminder_action.setChecked(not checked)
            QMessageBox.warning(self,'无法保存',str(error))
        self.check_reminders()

    def show_next_course(self):
        QMessageBox.information(self,'下一节课',countdown_text(self.store.all(),self.store.semester(),datetime.now(self.zone)))

    def set_view(self,view,remember=True):
        if view not in DEFAULT_SIZES:
            return
        animate = self._ready and self.isVisible() and self.view != view
        self.mode_transition.stop()
        self._switching = True
        self.view = view
        for mode,action in self.view_actions.items():
            action.setChecked(mode == view)
        self.scroll.setVisible(view != 'mini')
        self.footer.setVisible(view == 'today')
        self.week_bar.setVisible(view == 'week')
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.mini_remaining.setVisible(view == 'mini')
        self.next_label.setVisible(view == 'mini')
        self.panel_layout.setContentsMargins(14,10,14,10) if view == 'mini' else self.panel_layout.setContentsMargins(16,14,16,14)
        self.panel_layout.setSpacing(5 if view == 'mini' else 8)
        self.next_label.setObjectName('miniNext')
        self.date_label.setObjectName('clock' if view == 'mini' else 'date')
        for widget in (self.next_label,self.date_label):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        self.update_date()
        self._switching = False
        if self._ready:
            self.save_position()
        if animate:
            opacity = self.opacity_percent/100
            self.mode_transition.setStartValue(opacity*.9)
            self.mode_transition.setEndValue(opacity)
            self.mode_transition.start()

    def apply_mode_size(self):
        preferred = mode_size(self.view,self._today_count)
        rect = fit_geometry(QRect(self.pos(),preferred),self.available_areas())
        self.setFixedSize(rect.size())
        if self.pos()!=rect.topLeft():
            self.move(rect.topLeft())

    def update_lock_cursor(self):
        self.header.setCursor(Qt.CursorShape.ArrowCursor if self.locked else Qt.CursorShape.SizeAllCursor)
        self.header.offset = None
        self.hide_button.setEnabled(not self.locked)
        self.hide_button.setToolTip('位置已锁定，解锁后可隐藏；也可通过托盘菜单隐藏' if self.locked else '隐藏到系统托盘')

    def set_locked(self,locked):
        self.locked = bool(locked)
        self.lock_action.setChecked(self.locked)
        self.update_lock_cursor()
        self.save_position()

    def set_topmost(self,topmost):
        if self.topmost == bool(topmost):
            return
        self.topmost = bool(topmost)
        self.topmost_action.setChecked(self.topmost)
        geometry = self.geometry()
        visible, minimized = self.isVisible(), self.isMinimized()
        self._switching = True
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,self.topmost)
        self.bind_screen_window()
        self.setGeometry(geometry)
        if visible:
            self.showMinimized() if minimized else self.show()
        self.ensure_visible()
        self._switching = False
        self.save_position()

    def apply_appearance(self,theme,opacity,locked,topmost):
        self.mode_transition.stop()
        self.theme = theme if theme in ('light','dark') else 'light'
        self.opacity_percent = max(35,min(100,int(opacity)))
        self.setStyleSheet(stylesheet(self.theme))
        self.setWindowOpacity(self.opacity_percent / 100)
        self.set_locked(locked)
        self.set_topmost(topmost)
        self.save_position()

    def open_window_settings(self):
        dialog = WindowSettings(self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            self.apply_appearance(**dialog.value())

    def open_settings(self):
        SettingsDialog(self).exec()

    def open_data_dialog(self):
        DataDialog(self).exec()

    def shift_week(self, amount):
        self.week_offset += amount
        self.update_date()

    def current_week(self):
        self.week_offset = 0
        self.update_date()

    def manage_courses(self):
        CourseManager(self.store, self).exec()
        self.check_reminders()

    def render_courses(self,now):
        semester = self.store.semester()
        courses = self.store.all()
        items = occurrences(courses,now.date(),semester) if self.view == 'today' and semester else []
        self._today_count = len(items)
        visible = tuple((o['course']['id'],o['start'],o['end']) for o in items)
        monday = now.date()-timedelta(days=now.weekday())+timedelta(weeks=self.week_offset)
        days = [now.date()] if self.view == 'today' else [monday+timedelta(days=d) for d in range(7)]
        boundaries = tuple((o['start'],o['end'],status(o,now)) for day in days for o in (occurrences(courses,day,semester) if semester else []))
        signature = (self.view,self.week_offset,now.date(),semester,json.dumps(courses,sort_keys=True,ensure_ascii=False),visible,boundaries)
        if signature == self._render_signature:
            for label,item in self._status_labels:
                label.setText(status(item,now))
            return
        same_page = self._render_signature is not None and self._render_signature[:3] == signature[:3]
        scroll_position = self.scroll.verticalScrollBar().value() if same_page else 0
        self._render_signature = signature
        self._render_count += 1
        if self.view == 'today':
            content,self._status_labels = today_view(items,now,semester is not None)
        else:
            monday = now.date()-timedelta(days=now.weekday())+timedelta(weeks=self.week_offset)
            content,self._status_labels = week_view(courses,semester,monday,now)
        old = self.scroll.takeWidget()
        if old:
            old.deleteLater()
        self.scroll.setWidget(content)
        self.scroll.verticalScrollBar().setValue(scroll_position)

    def restore_position(self):
        areas = self.available_areas()
        if not areas:
            return
        area = areas[0]
        fallback = QPoint(area.right() - self.width() - 24, area.top() + 40)
        try:
            point = self.settings.value("window/position", fallback, type=QPoint)
        except (TypeError,ValueError):
            point = fallback
        self.move(point)
        self.ensure_visible()

    def available_areas(self):
        screens = QApplication.screens()
        primary = QApplication.primaryScreen()
        ordered = ([primary] if primary else []) + [s for s in screens if s is not primary]
        return [screen.availableGeometry() for screen in ordered]

    def ensure_visible(self):
        if not self.isMinimized():
            self.apply_mode_size()

    def watch_screen(self,screen):
        if screen not in self._watched_screens:
            self._watched_screens.add(screen)
            screen.availableGeometryChanged.connect(self.schedule_screen_check)
            screen.geometryChanged.connect(self.schedule_screen_check)
            screen.logicalDotsPerInchChanged.connect(self.schedule_screen_check)
        self.schedule_screen_check()

    def screen_removed(self,screen):
        self._watched_screens.discard(screen)
        self.schedule_screen_check()

    def bind_screen_window(self):
        self.winId()
        handle = self.windowHandle()
        if getattr(self,'_screen_window',None) is not handle:
            self._screen_window = handle
            handle.screenChanged.connect(self.schedule_screen_check)

    def schedule_screen_check(self,*args):
        self.screen_timer.start(150)

    def screen_layout_changed(self):
        self.ensure_visible()
        self.save_position()

    def moveEvent(self,event):
        super().moveEvent(event)
        if getattr(self,'_ready',False) and not self._switching and not self.isMinimized():
            self.geometry_timer.start(250)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if getattr(self,'_ready',False) and not self._switching and not self.isMinimized():
            self.geometry_timer.start(250)

    def save_position(self):
        if not self._ready or self._switching or self.isMinimized():
            return
        self.settings.setValue("window/position", self.pos())
        self.settings.setValue('window/view',self.view)
        self.settings.setValue('window/expanded_view',self._last_expanded)
        self.settings.setValue('window/opacity',self.opacity_percent)
        self.settings.setValue('window/theme',self.theme)
        self.settings.setValue('window/topmost',self.topmost)
        self.settings.setValue('window/locked',self.locked)
        self.settings.sync()

    def restore_window(self):
        self.restore_position()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def hide_to_tray(self):
        self.save_position()
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.hide()
        else:
            self.showMinimized()

    def toggle_visible(self):
        self.hide_to_tray() if self.isVisible() else self.restore_window()

    def tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.restore_window()

    def contextMenuEvent(self, event):
        self.menu.exec(event.globalPos())

    def closeEvent(self, event):
        self.hide_to_tray()
        event.ignore()

    def quit_app(self):
        self.mode_transition.stop()
        self.geometry_timer.stop()
        self.screen_timer.stop()
        app = QApplication.instance()
        app.screenAdded.disconnect(self.watch_screen)
        app.screenRemoved.disconnect(self.screen_removed)
        self.timer.stop()
        self.reminder_timer.stop()
        QApplication.instance().removeNativeEventFilter(self.power_filter)
        self.save_position()
        self.tray.hide()
        self.store.close()
        QApplication.quit()
