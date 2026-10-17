import unittest
from PySide6.QtCore import QRect
from app.ui.appearance import fit_geometry


class GeometryTests(unittest.TestCase):
    def test_inside_remains(self):
        rect = QRect(100,100,360,480)
        self.assertEqual(fit_geometry(rect,[QRect(0,0,1920,1040)]),rect)

    def test_negative_monitor(self):
        rect = QRect(-1500,100,360,480)
        self.assertEqual(fit_geometry(rect,[QRect(0,0,1920,1040),QRect(-1920,0,1920,1040)]),rect)

    def test_monitor_removed(self):
        fitted = fit_geometry(QRect(-1500,100,360,480),[QRect(0,0,1920,1040)])
        self.assertEqual(fitted.left(),0)
        self.assertTrue(QRect(0,0,1920,1040).contains(fitted))

    def test_straddling_uses_largest_intersection(self):
        fitted = fit_geometry(QRect(1800,100,360,480),[QRect(0,0,1920,1040),QRect(1920,0,1920,1040)])
        self.assertEqual(fitted.left(),1920)

    def test_oversize_and_taskbar(self):
        bounds = QRect(0,40,800,560)
        self.assertEqual(fit_geometry(QRect(500,500,1200,900),[bounds]),bounds)

    def test_no_screens(self):
        rect = QRect(100,100,360,480)
        self.assertEqual(fit_geometry(rect,[]),rect)
