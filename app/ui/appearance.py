"""窗口外观配置和可测试的多显示器几何修正。"""
from PySide6.QtCore import QPoint, QRect, QSize

DEFAULT_SIZES = {'today': QSize(340,250), 'week': QSize(420,480), 'mini': QSize(280,156)}
MINIMUM_SIZES = dict(DEFAULT_SIZES)


def mode_size(view,remaining=0):
    if view == 'today':
        return QSize(340,150 if not remaining else 136+min(remaining,3)*100)
    return QSize(DEFAULT_SIZES[view])


def fit_geometry(rect, screens):
    """保留负坐标屏幕，选最大相交区域，移除屏幕后回到可见区域。"""
    if not screens:
        return QRect(rect)
    def intersection_area(screen):
        overlap = rect.intersected(screen)
        return max(0,overlap.width()) * max(0,overlap.height())
    target = max(screens, key=intersection_area)
    if intersection_area(target) == 0:
        # screens 顺序以主屏优先，由调用方负责。
        target = screens[0]
    width = min(rect.width(),target.width())
    height = min(rect.height(),target.height())
    x = max(target.left(),min(rect.left(),target.right()-width+1))
    y = max(target.top(),min(rect.top(),target.bottom()-height+1))
    return QRect(QPoint(x,y),QSize(width,height))


def stylesheet(theme):
    dark = theme == 'dark'
    card_edge = '#485570' if dark else '#ccd6e9'
    text, panel, border, card, muted, accent, hover = (
        ('#edf1fb','#191e2b','#30384a','#242c3d','#9ba8c0','#2a3350','#354364') if dark else
        ('#25314b','#f5f7fc','#e4e9f3','#ffffff','#78869f','#e9edfc','#dce4fc')
    )
    return f"""
        QWidget {{ font-family: 'Microsoft YaHei UI', 'Microsoft YaHei'; font-size: 12px; color: {text}; }}
        QFrame#panel {{ background: {panel}; border: 1px solid {border}; border-radius: 20px; }}
        QLabel#title {{ font-size: 15px; font-weight: 600; letter-spacing: 1px; }}
        QLabel#date {{ font-size: 13px; color: {muted}; }}
        QLabel#clock {{ font-size: 22px; font-weight: 600; }}
        QLabel#note {{ color: {muted}; font-size: 11px; }}
        QLabel#courseName {{ font-size: 14px; font-weight: 600; }}
        QLabel#nextCourse {{ background: {accent}; border: 1px solid {border}; border-radius: 14px; padding: 12px; font-size: 12px; }}
        QLabel#miniNext {{ background: transparent; font-size: 12px; padding: 0; }}
        QFrame#weekDay {{ background: {card}; border-radius: 10px; }}
        QFrame#weekDayToday {{ background: {accent}; border: 1px solid #9aacef; border-radius: 10px; }}
        QLabel#weekHeading {{ font-size: 11px; font-weight: 600; padding: 2px; }}
        QLabel#endedCourse {{ color: {muted}; font-size: 12px; }}
        QToolTip {{ background: {card}; color: {text}; border: 1px solid {border}; padding: 14px; border-radius: 10px; font-size: 12px; }}
        QScrollBar:horizontal {{ height: 7px; background: transparent; }}
        QScrollBar::handle:horizontal {{ background: {muted}; border-radius: 3px; min-width: 24px; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}
        QLabel#weekCourse {{ font-size: 11px; font-weight: 600; }}
        QLabel#weekTime {{ color: {muted}; font-size: 10px; }}
        QLabel#countdown {{ color: #7d91ee; font-weight: 600; font-size: 12px; }}
        QFrame#card {{ background: {card}; border: 1px solid {card_edge}; border-right: 2px solid {card_edge}; border-radius: 10px; }}
        QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; }}
        QPushButton {{ border: none; border-radius: 8px; background: {accent}; padding: 6px; }}
        QPushButton#weekNav {{ padding: 0; border-radius: 7px; font-size: 12px; }}
        QPushButton:hover {{ background: {hover}; }}
        QPushButton:disabled {{ color: {muted}; background: {panel}; }}
        QPushButton:checked {{ background: #5c73dd; color: white; }}
        QMenu, QDialog {{ background: {panel}; }}
        QMenu {{ border: 1px solid {border}; padding: 5px; }}
        QMenu::item {{ padding: 7px 20px; }}
        QMenu::item:selected {{ background: {hover}; }}
        QLineEdit, QSpinBox, QTimeEdit, QDateEdit, QComboBox, QListWidget, QTableWidget {{ background: {card}; color: {text}; border: 1px solid {border}; padding: 3px; }}
        QHeaderView::section {{ background: {accent}; color: {text}; padding: 4px; border: 1px solid {border}; }}
        QComboBox QAbstractItemView {{ background: {card}; color: {text}; selection-background-color: {hover}; }}
        QCheckBox, QLabel {{ background: transparent; }}
        QScrollBar:vertical {{ background: transparent; width: 9px; margin: 0; }}
        QScrollBar::handle:vertical {{ background: {muted}; border-radius: 4px; min-height: 24px; }}
        QScrollBar::handle:vertical:hover {{ background: #5579ef; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; border: none; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    """
