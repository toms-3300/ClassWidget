from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QHBoxLayout, QLabel, QSlider, QVBoxLayout)


class WindowSettings(QDialog):
    def __init__(self,window):
        super().__init__(window)
        self.setWindowTitle('窗口外观与交互')
        self.resize(400,300)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.theme = QComboBox()
        self.theme.addItems(['浅色','深色'])
        self.theme.setCurrentIndex(int(window.theme == 'dark'))
        form.addRow('主题',self.theme)
        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(35,100)
        self.opacity.setValue(window.opacity_percent)
        self.opacity_text = QLabel(f'{self.opacity.value()}%')
        self.opacity.valueChanged.connect(lambda value: self.opacity_text.setText(f'{value}%'))
        row = QHBoxLayout()
        row.addWidget(self.opacity)
        row.addWidget(self.opacity_text)
        form.addRow('窗口不透明度',row)
        layout.addLayout(form)
        self.topmost = QCheckBox('始终置顶')
        self.topmost.setChecked(window.topmost)
        self.locked = QCheckBox('锁定位置与顶部隐藏按钮')
        self.locked.setChecked(window.locked)
        layout.addWidget(self.topmost)
        layout.addWidget(self.locked)
        note = QLabel('100% 可关闭窗口半透明效果。各模式尺寸由程序固定控制，今日模式会随剩余课程收缩。显示模式只能通过系统托盘切换。')
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('保存')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self):
        return dict(theme=['light','dark'][self.theme.currentIndex()],opacity=self.opacity.value(),topmost=self.topmost.isChecked(),locked=self.locked.isChecked())
