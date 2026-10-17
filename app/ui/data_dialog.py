from pathlib import Path
import logging
from PySide6.QtWidgets import (QDialog, QFileDialog, QLabel, QMessageBox,
    QPushButton, QVBoxLayout)
from app.services.data_exchange import (load_file, import_courses, export_file,
    backup_database, read_backup, restore_courses)


class DataDialog(QDialog):
    def __init__(self,window):
        super().__init__(window)
        self.window = window
        self.store = window.store
        self.setWindowTitle('课程数据与备份')
        self.resize(420,360)
        layout = QVBoxLayout(self)
        note = QLabel('导入会添加新课程并跳过重复课程，不覆盖已有课程。恢复备份会替换课程和学期，操作前自动备份当前数据库。')
        note.setWordWrap(True)
        layout.addWidget(note)
        for title,callback in [('导入 JSON / CSV',self.import_data),('导出 JSON',lambda:self.export_data('json')),('导出 CSV',lambda:self.export_data('csv')),('备份数据库',self.backup),('从数据库备份恢复课程',self.restore)]:
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False,fn=callback:self.perform(fn))
            layout.addWidget(button)
        done = QPushButton('完成')
        done.clicked.connect(self.accept)
        layout.addWidget(done)

    def perform(self,callback):
        try:
            callback()
        except Exception as error:
            logging.exception('数据操作失败')
            QMessageBox.warning(self,'操作失败',str(error))

    def import_data(self):
        path,_ = QFileDialog.getOpenFileName(self,'选择课程文件','','课程文件 (*.json *.csv)')
        if not path:
            return
        courses,semester = load_file(path)
        note = f'文件包含 {len(courses)} 门课程。将跳过重复课程，保留已有学期设置。\n导入可能包含时间重叠安排，请导入后检查周视图。\n是否导入？'
        if QMessageBox.question(self,'确认导入',note,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        added,skipped = import_courses(self.store,courses,semester)
        self.window.check_reminders()
        QMessageBox.information(self,'导入完成',f'新增 {added} 门，跳过重复 {skipped} 门。')

    def export_data(self,extension):
        path,_ = QFileDialog.getSaveFileName(self,'导出课程',f'ClassWidget课程.{extension}',f'{extension.upper()} 文件 (*.{extension})')
        if not path:
            return
        if not Path(path).suffix:
            path += '.'+extension
        export_file(self.store,path)
        QMessageBox.information(self,'导出完成',path)

    def backup(self):
        path,_ = QFileDialog.getSaveFileName(self,'备份数据库','ClassWidget备份.db','SQLite 备份 (*.db)')
        if not path:
            return
        if not Path(path).suffix:
            path += '.db'
        backup_database(self.store,path)
        QMessageBox.information(self,'备份完成',path)

    def restore(self):
        path,_ = QFileDialog.getOpenFileName(self,'选择数据库备份','','数据库备份 (*.db *.bak)')
        if not path:
            return
        courses,_ = read_backup(path)
        note = f'备份包含 {len(courses)} 门课程。\n将替换当前全部课程和学期，当前数据会先自动备份。\n提醒历史与当前全局设置会保留。确定恢复吗？'
        if QMessageBox.question(self,'确认恢复',note,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        count,safety = restore_courses(self.store,path)
        self.window.check_reminders()
        QMessageBox.information(self,'恢复完成',f'已恢复 {count} 门课程。\n恢复前备份：{safety}')
