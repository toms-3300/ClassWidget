"""真实 Qt 动画时间线与覆盖布局回归，不操作用户数据。"""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QFocusEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QWidget,QVBoxLayout
from app.ui.course_views import CourseCard
from app.ui.appearance import stylesheet

app = QApplication.instance() or QApplication([])

class HoverTests(unittest.TestCase):
    def setUp(self):
        self.motion = patch('app.ui.card_hover.reduced_motion',return_value=False)
        self.motion.start()
        from app.ui.card_hover import HoverOverlay
        self.real_check_pointer = HoverOverlay.check_pointer
        self.pointer = patch('app.ui.card_hover.HoverOverlay.check_pointer')
        self.pointer.start()
        self.root = QWidget()
        self.root.resize(420,480)
        self.root.setStyleSheet(stylesheet('light'))
        self.layout = QVBoxLayout(self.root)
        self.card = CourseCard(True)
        self.card.hover_details = ('课程名称','A301','王老师','未开始','08:00–09:40')
        self.layout.addWidget(self.card)
        self.layout.addStretch()
        self.root.show()
        app.processEvents()
        self.card.clearFocus()
        self.card.animate_hover(True)
        self.card.overlay.monitor.stop()

    def tearDown(self):
        self.root.hide()
        self.root.deleteLater()
        app.processEvents()
        self.pointer.stop()
        self.motion.stop()

    def test_simultaneous_scale_fade_and_no_layout_shift(self):
        rect = self.card.geometry()
        overlay = self.card.overlay
        self.assertEqual(overlay.detail_progress,0)
        self.assertEqual(overlay.scale_anim.state(),overlay.scale_anim.State.Running)
        self.assertEqual(overlay.detail_anim.state(),overlay.detail_anim.State.Running)
        QTest.qWait(80)
        self.assertGreater(overlay.scale_progress,0)
        self.assertGreater(overlay.detail_progress,0)
        self.assertLess(overlay.detail_progress,1)
        QTest.qWait(300)
        self.assertEqual(overlay.scale_progress,1)
        self.assertEqual(overlay.detail_progress,1)
        head,detail = overlay.geometry_parts()
        self.assertAlmostEqual(head.width()/overlay.base.width(),1.03)
        self.assertGreater(detail.height(),0)
        self.assertEqual(rect,self.card.geometry())
        self.assertLessEqual(head.united(detail).bottom(),self.root.height()-9)

    def test_fast_reversal_preserves_current_value(self):
        overlay = self.card.overlay
        QTest.qWait(100)
        current = overlay.scale_progress
        details = overlay.detail_progress
        self.card.animate_hover(False)
        self.assertAlmostEqual(overlay.scale_progress,current)
        self.assertAlmostEqual(overlay.detail_progress,details)
        QTest.qWait(20)
        current = overlay.scale_progress
        self.card.animate_hover(True)
        overlay.monitor.stop()
        self.assertAlmostEqual(overlay.scale_progress,current)
        QTest.qWait(360)
        self.assertEqual(overlay.detail_progress,1)
        self.card.animate_hover(False)
        QTest.qWait(320)
        self.assertFalse(overlay.isVisible())

    def test_reduced_motion_still_reveals_details(self):
        self.card.overlay.dismiss()
        with patch('app.ui.card_hover.reduced_motion',return_value=True):
            self.card.animate_hover(True)
            overlay = self.card.overlay
            overlay.monitor.stop()
            self.assertEqual(overlay.detail_progress,1)
            self.assertEqual(overlay.scale_anim.state(),overlay.scale_anim.State.Stopped)
            head,_ = overlay.geometry_parts()
            self.assertEqual(head.width(),overlay.base.width())
            self.card.animate_hover(False)
            self.assertFalse(overlay.isVisible())

    def test_focus_and_escape(self):
        self.card.overlay.dismiss()
        app.sendEvent(self.card,QFocusEvent(QEvent.Type.FocusIn,Qt.FocusReason.TabFocusReason))
        self.assertTrue(self.card.overlay.active)
        self.card.overlay.monitor.stop()
        QTest.keyClick(self.card,Qt.Key.Key_Escape)
        self.assertFalse(self.card.overlay.isVisible())

    def test_long_details_and_bottom_edge(self):
        self.card.hover_details = ('课程'*200,'教室'*100,'教师'*100,'未开始','08:00–09:40')
        overlay = self.card.overlay
        overlay.refresh_document()
        overlay.set_detail(1)
        overlay.set_scale(1)
        head,detail = overlay.geometry_parts()
        self.assertLessEqual(head.united(detail).bottom(),self.root.height()-9)
        self.assertGreater(overlay.doc.size().height(),detail.height())
        self.assertTrue(overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))

    def test_hidden_source_cleans_overlay(self):
        self.card.hide()
        self.assertFalse(self.card.overlay.isVisible())
        self.assertFalse(self.card.overlay.monitor.isActive())

    def test_repeated_enter_does_not_restart(self):
        overlay = self.card.overlay
        QTest.qWait(90)
        time = overlay.scale_anim.currentTime()
        self.card.animate_hover(True)
        self.assertGreaterEqual(overlay.scale_anim.currentTime(),time)

    def test_details_accept_wheel_without_moving_cards(self):
        from PySide6.QtCore import QPoint,QPointF
        from PySide6.QtGui import QWheelEvent
        self.card.hover_details = ('课程'*100,'教室'*100,'教师'*100,'未开始','08:00–09:40')
        overlay = self.card.overlay
        overlay.refresh_document()
        overlay.set_detail(1)
        overlay.set_scale(1)
        _,detail = overlay.geometry_parts()
        local = detail.center()
        global_pos = overlay.mapToGlobal(local.toPoint())
        wheel = QWheelEvent(local,QPointF(global_pos),QPoint(),QPoint(0,-120),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
        original = self.card.geometry()
        self.assertTrue(overlay.eventFilter(self.root,wheel))
        self.assertGreater(overlay.detail_offset,0)
        self.assertEqual(self.card.geometry(),original)

    def test_pointer_stays_in_expanded_details(self):
        from app.ui.card_hover import HoverOverlay
        self.card.clearFocus()
        overlay = self.card.overlay
        overlay.set_scale(1)
        overlay.set_detail(1)
        _,detail = overlay.geometry_parts()
        position = overlay.mapToGlobal(detail.center().toPoint())
        with patch('app.ui.card_hover.QCursor.pos',return_value=position):
            self.real_check_pointer(overlay)
        self.assertTrue(overlay.active)
        self.assertTrue(overlay.expanded_contains(position))
