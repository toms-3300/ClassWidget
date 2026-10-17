"""纵向星期、横向课程卡片；悬停动画不改变周围布局。"""
from datetime import timedelta
from shiboken6 import isValid
from html import escape
from PySide6.QtCore import Qt, QTimer, QEvent, QPoint
from PySide6.QtGui import QFont, QFontMetrics, QPainter, QPalette, QCursor
from PySide6.QtWidgets import QFrame,QHBoxLayout,QLabel,QScrollArea,QVBoxLayout,QWidget,QSizePolicy
from app.services.schedule import occurrences,status
from app.ui.card_hover import HoverOverlay


def label(text,name=None):
    result = QLabel(text)
    result.setTextFormat(Qt.TextFormat.PlainText)
    result.setWordWrap(True)
    if name:
        result.setObjectName(name)
    return result


class CourseNameLabel(QLabel):
    """绘制时按实际宽度缩字，不改变布局；过长名称在最小字号下省略。"""
    def __init__(self,text,name):
        super().__init__(text)
        self.setObjectName(name)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(False)
        self.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)

    def fitted_font(self):
        font = QFont(self.font())
        metrics = QFontMetrics(font)
        size = font.pixelSize() if font.pixelSize()>0 else metrics.height()
        minimum = min(size,9)
        while size>minimum and metrics.horizontalAdvance(self.text())>self.contentsRect().width():
            size -= 1
            font.setPixelSize(size)
            metrics = QFontMetrics(font)
        return font

    def paintEvent(self,event):
        painter = QPainter(self)
        font = self.fitted_font()
        painter.setFont(font)
        painter.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        text = QFontMetrics(font).elidedText(self.text(),Qt.TextElideMode.ElideRight,self.contentsRect().width())
        painter.drawText(self.contentsRect(),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,text)


class CourseRowScroll(QScrollArea):
    """隐藏横向滑条，用滚轮查看溢出的课程；到边缘后交给外层滚动。"""
    def wheelEvent(self,event):
        bar = self.horizontalScrollBar()
        pixel = event.pixelDelta()
        angle = event.angleDelta()
        delta = (pixel.x() or pixel.y()) if not pixel.isNull() else (angle.x() or angle.y()) / 120 * 80
        previous = bar.value()
        bar.setValue(previous-round(delta))
        if bar.value() != previous:
            event.accept()
        else:
            event.ignore()


class CourseCard(QWidget):
    def __init__(self,compact=False):
        super().__init__()
        self.compact = compact
        self.hovered = False
        self.setFixedHeight(48 if compact else 98)
        if compact:
            self.setFixedWidth(132)
        self.surface = QFrame(self)
        self.surface.setObjectName('card')
        self.surface.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.overlay = None
        self.hover_details = ('','','','','')
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName('课程卡片')

    def resizeEvent(self,event):
        self.surface.setGeometry(self.rect().adjusted(4,4,-4,-4))
        if self.overlay is not None:
            self.overlay.dismiss()
        super().resizeEvent(event)

    def animate_hover(self,hovered):
        self.hovered = hovered
        if hovered:
            active = getattr(self.window(),'_active_course_hover',None)
            if active is not None and isValid(active) and active is not self.overlay:
                if active.active and active.expanded_contains(QCursor.pos()) and not self.hasFocus():
                    return
                active.transition(False)
            if self.overlay is None:
                self.overlay = HoverOverlay(self)
            self.window()._active_course_hover = self.overlay
        if self.overlay is not None:
            if hovered and self.overlay.anchor != self.mapTo(self.window(),QPoint()):
                self.overlay.deleteLater()
                self.overlay = HoverOverlay(self)
                self.window()._active_course_hover = self.overlay
            self.overlay.transition(hovered)

    def enterEvent(self,event):
        self.animate_hover(True)
        super().enterEvent(event)

    def leaveEvent(self,event):
        # 覆盖层是鼠标透明的，留给短暂检查判断鼠标是否仍在展开区域。
        if self.overlay is not None:
            QTimer.singleShot(0,self.overlay.check_pointer)
        super().leaveEvent(event)

    def focusInEvent(self,event):
        if event.reason() in (Qt.FocusReason.TabFocusReason,Qt.FocusReason.BacktabFocusReason,Qt.FocusReason.ShortcutFocusReason,Qt.FocusReason.MouseFocusReason):
            self.animate_hover(True)
        super().focusInEvent(event)

    def focusOutEvent(self,event):
        if self.overlay is not None:
            QTimer.singleShot(0,self.overlay.check_pointer)
        super().focusOutEvent(event)

    def event(self,event):
        if event.type()==QEvent.Type.ToolTip:
            return True
        return super().event(event)

    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape and self.overlay is not None:
            self.overlay.dismiss()
            event.accept()
        else:
            super().keyPressEvent(event)

    def hideEvent(self,event):
        if self.overlay is not None:
            self.overlay.dismiss()
        super().hideEvent(event)


def ordered_items(items,now):
    return sorted(items,key=lambda item:(item['end']<=now,item['start']))


def course_card(item,now,compact=False):
    course = item['course']
    card = CourseCard(compact)
    card.setProperty('courseName',course['name'])
    card.setProperty('courseColor',course['color'])
    ended = item['end']<=now
    card.setProperty('ended',ended)
    surface = card.surface
    surface.setProperty('ended',ended)
    surface.setStyleSheet(f"QFrame#card {{ border-left: 3px solid {course['color']}; border-right: 3px solid {course['color']}; }}")
    layout = QVBoxLayout(surface)
    layout.setContentsMargins(8,2,6,2) if compact else layout.setContentsMargins(10,7,8,7)
    layout.setSpacing(0 if compact else 3)
    name = CourseNameLabel(course['name'],'weekCourse' if compact else 'courseName')
    name.setMaximumHeight(20)
    font = name.font()
    font.setStrikeOut(ended)
    name.setFont(font)
    if ended:
        name.setObjectName('endedCourse')
    layout.addWidget(name)
    text = f"{item['start']:%H:%M}–{item['end']:%H:%M}"
    if item['start'].date()!=item['end'].date():
        text += ' 次日'
    time = label(text,'weekTime' if compact else 'note')
    time.setWordWrap(False)
    layout.addWidget(time)
    state = label(status(item,now),'note')
    if compact:
        state.setParent(surface)
        state.hide()
    else:
        bottom = QHBoxLayout()
        room = label(course['room'] or '地点待定','note')
        room.setMaximumHeight(18)
        bottom.addWidget(room,1)
        bottom.addWidget(state)
        layout.addLayout(bottom)
    title = escape(course['name'])
    room = escape(course['room'] or '地点待定')
    teacher = escape(course['teacher'] or '教师待定')
    card.setToolTip(f'<b>{title}</b><br/><br/>{text}<br/>教室 · {room}<br/>教师 · {teacher}<br/><br/>{status(item,now)}')
    card.hover_details = (course['name'],course['room'] or '地点待定',course['teacher'] or '教师待定',status(item,now),text)
    card.setAccessibleName(course['name'])
    card.setAccessibleDescription(f'{text}，{course["room"]}，{course["teacher"]}，{status(item,now)}')
    return card,(state,item)


def today_view(items,now,configured):
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(0,0,0,0)
    layout.setSpacing(2)
    states = []
    if not items:
        layout.addWidget(label('今天没有课程' if configured else '右键“课程管理与学期设置”添加课程','note'))
    for item in ordered_items(items,now):
        card,state = course_card(item,now)
        layout.addWidget(card)
        states.append(state)
    layout.addStretch()
    return content,states


def week_view(courses,semester,monday,now):
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(0,0,0,0)
    layout.setSpacing(4)
    states = []
    # 保持星期顺序；每一天内部待上课程在前，已结束课程在后。
    for index in range(7):
        day = monday+timedelta(days=index)
        row = QFrame()
        row.setObjectName('weekDayToday' if day == now.date() else 'weekDay')
        row.setProperty('weekday',index)
        box = QHBoxLayout(row)
        box.setContentsMargins(3,1,3,1)
        box.setSpacing(4)
        heading = label(f"周{'一二三四五六日'[index]}\n{day:%m/%d}",'weekHeading')
        heading.setFixedWidth(43)
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(heading)
        scroll = CourseRowScroll()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setMinimumSize(0,0)
        scroll.setFixedHeight(48)
        scroll.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        stack = QHBoxLayout(inner)
        stack.setContentsMargins(0,0,0,0)
        stack.setSpacing(2)
        items = ordered_items(occurrences(courses,day,semester),now) if semester else []
        if not items:
            scroll.setFixedHeight(34)
            stack.addWidget(label('当天无课','note'))
        for item in items:
            card,state = course_card(item,now,compact=True)
            stack.addWidget(card)
            states.append(state)
        stack.addStretch()
        scroll.setWidget(inner)
        box.addWidget(scroll,1)
        layout.addWidget(row)
    layout.addStretch()
    return content,states
