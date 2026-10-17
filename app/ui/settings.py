"""统一设置入口；自启动更改仅发生在用户点击保存后。"""
import logging
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QLabel,
    QMessageBox, QPushButton, QVBoxLayout)
from app.services.autostart import Autostart, startup_command


class SettingsDialog(QDialog):
    def __init__(self,window,autostart=None):
        super().__init__(window)
        self.window = window
        self.setWindowTitle('ClassWidget 设置')
        self.resize(430,400)
        layout = QVBoxLayout(self)
        for title,callback in [('课程与学期',window.manage_courses),('提醒设置',window.open_reminder_settings),('窗口外观与交互',window.open_window_settings),('数据导入导出与备份',window.open_data_dialog)]:
            button = QPushButton(title)
            button.clicked.connect(callback)
            layout.addWidget(button)
        self.autostart = autostart
        self.original_command = None
        self.startup = QCheckBox('登录 Windows 后自动启动（默认关闭）')
        try:
            self.autostart = self.autostart or Autostart()
            self.original_command = self.autostart.current_command()
            self.startup.setChecked(self.original_command is not None)
        except (OSError,RuntimeError) as error:
            self.startup.setEnabled(False)
            warning = QLabel('无法读取自启动设置：'+str(error))
            warning.setWordWrap(True)
            layout.addWidget(warning)
        layout.addWidget(self.startup)
        self.hidden = QCheckBox('自动启动时隐藏到托盘')
        self.hidden.setChecked(window.settings.value('window/start_hidden',False,type=bool))
        layout.addWidget(self.hidden)
        note = QLabel('手动启动会显示窗口。自启动恢复上次模式、大小、位置和外观；只有保存此开关才会改变本应用的启动设置。Windows 可能延迟登录启动，任务管理器中禁用启动项也会阻止启动。')
        note.setWordWrap(True)
        layout.addWidget(note)
        info = QLabel(f'数据目录：{window.store.path.parent}')
        info.setWordWrap(True)
        layout.addWidget(info)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('保存')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self):
        try:
            if self.startup.isEnabled():
                enabled = self.startup.isChecked()
                if enabled:
                    # 保存已开启的开关也更新移动后的程序路径。
                    expected = startup_command()
                    if self.original_command != expected:
                        self.autostart.set_enabled(True)
                elif self.original_command is not None:
                    self.autostart.set_enabled(False)
            self.window.settings.setValue('window/start_hidden',self.hidden.isChecked())
            self.window.settings.sync()
        except (OSError,ValueError,RuntimeError) as error:
            logging.exception('自启动设置保存失败')
            QMessageBox.warning(self,'设置保存失败',str(error))
            return
        self.accept()
