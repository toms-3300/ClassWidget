from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QLabel, QSpinBox, QVBoxLayout)
import sqlite3


class ReminderSettings(QDialog):
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle('上课提醒设置')
        self.resize(380,260)
        layout = QVBoxLayout(self)
        options = store.reminder_options()
        self.enabled = QCheckBox('开启上课提醒')
        self.enabled.setChecked(options['enabled'])
        layout.addWidget(self.enabled)
        form = QFormLayout()
        self.presets = QComboBox()
        self.presets.addItems(['自定义','提前 5 分钟','提前 10 分钟','提前 15 分钟','提前 30 分钟'])
        self.minutes = QSpinBox()
        self.minutes.setRange(1,1440)
        self.minutes.setSuffix(' 分钟')
        self.minutes.setValue(options['minutes'])
        self.presets.currentIndexChanged.connect(self.apply_preset)
        form.addRow('快捷选择',self.presets)
        form.addRow('默认提前时间',self.minutes)
        layout.addLayout(form)
        info = QLabel('单门课程可覆盖默认提前时间。休眠、关机或完全退出时，程序不能准时提醒。Windows 勿扰模式可能隐藏弹窗。')
        info.setWordWrap(True)
        layout.addWidget(info)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('保存')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply_preset(self,index):
        if index:
            self.minutes.setValue([0,5,10,15,30][index])

    def save(self):
        from PySide6.QtWidgets import QMessageBox
        try:
            self.store.set_settings(dict(reminders_enabled=int(self.enabled.isChecked()),reminder_minutes=self.minutes.value()))
        except sqlite3.Error as error:
            QMessageBox.warning(self,'无法保存',str(error))
            return
        self.accept()
