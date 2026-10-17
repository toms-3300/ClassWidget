"""课程卡片覆盖动画；只在展开期间工作，不修改列表布局。"""
import ctypes
import sys
from html import escape
from PySide6.QtCore import Qt, QPoint, QPointF, QRectF, QTimer, QVariantAnimation, QEasingCurve, QEvent
from PySide6.QtGui import QColor, QCursor, QPainter, QTextDocument
from PySide6.QtWidgets import QApplication, QWidget


def reduced_motion():
    """只读取 Windows 客户区动画偏好；查询失败时保守地关闭动态效果。"""
    if sys.platform != 'win32':
        return False
    value = ctypes.c_int()
    try:
        ok = ctypes.windll.user32.SystemParametersInfoW(0x1042,0,ctypes.byref(value),0)
        return not ok or not value.value
    except (OSError,AttributeError):
        return True


def ease_out():
    curve = QEasingCurve(QEasingCurve.Type.BezierSpline)
    curve.addCubicBezierSegment(QPointF(.22,1),QPointF(.36,1),QPointF(1,1))
    return curve


class HoverOverlay(QWidget):
    def __init__(self,card):
        super().__init__(card.window())
        self.card = card
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setGeometry(self.parentWidget().rect())
        self.scale_progress = 0.
        self.detail_progress = 0.
        self.detail_offset = 0.
        self.active = False
        self.doc = QTextDocument(self)
        self.doc.setDocumentMargin(0)
        self.snapshot = card.surface.grab()
        self.anchor = card.mapTo(self.parentWidget(),QPoint())
        self.base = QRectF(card.surface.geometry().translated(self.anchor))
        self.scale_anim = QVariantAnimation(self)
        self.detail_anim = QVariantAnimation(self)
        for animation in (self.scale_anim,self.detail_anim):
            animation.setEasingCurve(ease_out())
        self.scale_anim.valueChanged.connect(self.set_scale)
        self.detail_anim.valueChanged.connect(self.set_detail)
        self.scale_anim.finished.connect(self.finish_if_closed)
        self.detail_anim.finished.connect(self.finish_if_closed)
        self.monitor = QTimer(self)
        self.monitor.setInterval(35)
        self.monitor.timeout.connect(self.check_pointer)
        QApplication.instance().installEventFilter(self)
        card.destroyed.connect(self.deleteLater)
        self.hide()

    def refresh_document(self):
        card = self.card
        self.snapshot = card.surface.grab()
        self.detail_offset = 0.
        dark = getattr(card.window(),'theme','light')=='dark'
        self.background = QColor('#242c3d' if dark else '#ffffff')
        self.edge = QColor(card.property('courseColor') or '#5579ef')
        color = '#d7dfef' if dark else '#46536d'
        title,room,teacher,state,time = card.hover_details
        self.doc.setDefaultFont(card.font())
        full_title = f'<b>{escape(title)}</b><br/>' if len(title)>8 else ''
        self.doc.setHtml(f'<div style="color:{color};font-size:11px">{full_title}教室 · {escape(room)}<br/>教师 · {escape(teacher)}<br/>{escape(state)}</div>')
        self.doc.setTextWidth(max(40,self.base.width()*1.03-20))

    def animate_to(self,animation,current,target,duration):
        animation.stop()
        if self.instant:
            if animation is self.scale_anim:
                self.set_scale(target)
            else:
                self.set_detail(target)
            return
        animation.setDuration(max(1,round(duration*abs(target-current))))
        animation.setStartValue(current)
        animation.setEndValue(target)
        animation.start()

    def transition(self,active):
        if active == self.active:
            return
        self.active = active
        self.instant = reduced_motion()
        if active:
            self.refresh_document()
            self.show()
            self.raise_()
            self.monitor.start()
        self.animate_to(self.scale_anim,self.scale_progress,1. if active else 0.,250)
        # 同一帧启动放大与详情淡入，继续从当前值反向，避免先放大再弹出。
        self.animate_to(self.detail_anim,self.detail_progress,1. if active else 0.,280)
        self.finish_if_closed()

    def set_scale(self,value):
        self.scale_progress = float(value)
        self.update()

    def set_detail(self,value):
        self.detail_progress = float(value)
        self.update()

    def geometry_parts(self):
        # 展开内容优先向下，靠近底部时整体向上夹紧到小组件内。
        p = self.scale_progress if not getattr(self,'instant',False) else 0.
        head = QRectF(self.base)
        head.setWidth(self.base.width()*(1+.03*p))
        head.setHeight(self.base.height()*(1+.03*p))
        head.moveCenter(self.base.center())
        maximum = max(30,self.height()-head.height()-28)
        detail_height = min(self.doc.size().height()+10,maximum)
        total = head.height()+detail_height*self.detail_progress
        x = max(10,min(head.x(),self.width()-head.width()-10))
        y = max(10,min(head.y(),self.height()-total-10))
        head.moveTopLeft(QPointF(x,y))
        detail = QRectF(x,y+head.height(),head.width(),detail_height*self.detail_progress)
        return head,detail

    def paintEvent(self,event):
        head,detail = self.geometry_parts()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        body = head.united(detail)
        # 小面积圆角阴影，无需为整个桌面窗口重新计算图形特效。
        for spread in range(7,0,-1):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(10,18,38,round((2+self.scale_progress*2)*(8-spread)/7)))
            painter.drawRoundedRect(body.adjusted(-spread,-spread/2,spread,spread),11,11)
        painter.setBrush(self.background)
        painter.setPen(self.edge)
        painter.drawRoundedRect(body,10,10)
        painter.drawPixmap(head,self.snapshot,QRectF(self.snapshot.rect()))
        if detail.height()>0:
            painter.save()
            painter.setClipRect(detail.adjusted(6,0,-6,-3))
            painter.setOpacity(self.detail_progress)
            offset = 0 if getattr(self,'instant',False) else 8*(1-self.detail_progress)
            painter.translate(detail.x()+10,detail.y()+4+offset-self.detail_offset)
            self.doc.drawContents(painter)
            painter.restore()

    def expanded_contains(self,global_point):
        head,detail = self.geometry_parts()
        return head.united(detail).contains(QPointF(self.mapFromGlobal(global_point)))

    def check_pointer(self):
        card = self.card
        if not card.isVisible() or card.mapTo(self.parentWidget(),QPoint())!=self.anchor or self.parentWidget().size()!=self.size():
            self.dismiss()
            return
        keep = card.rect().contains(card.mapFromGlobal(QCursor.pos())) or self.expanded_contains(QCursor.pos()) or card.hasFocus()
        if not keep and self.active:
            card.hovered = False
            self.transition(False)

    def eventFilter(self,obj,event):
        if self.isVisible() and event.type()==QEvent.Type.Wheel:
            head,detail = self.geometry_parts()
            if detail.contains(QPointF(self.mapFromGlobal(event.globalPosition().toPoint()))):
                delta = event.pixelDelta().y() or event.angleDelta().y()/120*35
                maximum = max(0,self.doc.size().height()+10-detail.height())
                self.detail_offset = max(0,min(maximum,self.detail_offset-delta))
                self.update()
                event.accept()
                return True
        return False

    def finish_if_closed(self):
        if not self.active and self.scale_progress<=.001 and self.detail_progress<=.001:
            self.hide()
            self.monitor.stop()

    def dismiss(self):
        self.scale_anim.stop()
        self.detail_anim.stop()
        self.monitor.stop()
        self.active = False
        self.scale_progress = self.detail_progress = 0.
        self.hide()
