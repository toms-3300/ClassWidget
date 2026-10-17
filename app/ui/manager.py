"""第二阶段课程管理与学期设置对话框。"""
from datetime import date
import sqlite3
from PySide6.QtCore import QDate, QTime
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDateEdit,
    QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QMessageBox, QPushButton, QSpinBox, QTableWidget,
    QTimeEdit, QVBoxLayout)
from app.database.store import validate
from app.services.schedule import conflicts


class CourseEditor(QDialog):
    def __init__(self, store, course=None, parent=None):
        super().__init__(parent)
        self.store = store
        self.course = course
        self.color = course['color'] if course else '#5579ef'
        self.setWindowTitle('编辑课程' if course else '添加课程')
        self.resize(850, 420)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(course['name'] if course else '')
        self.teacher = QLineEdit(course['teacher'] if course else '')
        self.room = QLineEdit(course['room'] if course else '')
        form.addRow('课程名称 *', self.name)
        form.addRow('任课教师', self.teacher)
        form.addRow('上课地点', self.room)
        self.color_button = QPushButton(self.color)
        self.color_button.clicked.connect(self.choose_color)
        form.addRow('课程颜色', self.color_button)
        self.reminder = QCheckBox('开启上课提醒')
        self.reminder.setChecked(bool(course['reminder_enabled']) if course else True)
        form.addRow(self.reminder)
        self.override = QCheckBox('使用单独的提前时间（未勾选则使用全局默认）')
        self.override.setChecked(course is not None and course.get('reminder_minutes') is not None)
        self.reminder_minutes = QSpinBox()
        self.reminder_minutes.setRange(1,1440)
        self.reminder_minutes.setSuffix(' 分钟')
        self.reminder_minutes.setValue((course.get('reminder_minutes') if course else None) or store.reminder_options()['minutes'])
        self.reminder_minutes.setEnabled(self.override.isChecked())
        self.override.toggled.connect(self.reminder_minutes.setEnabled)
        form.addRow(self.override)
        form.addRow('单独提前时间',self.reminder_minutes)
        layout.addLayout(form)
        layout.addWidget(QLabel('每行是一个上课时间；结束早于开始表示次日结束。指定周次优先于单双周规则。'))
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(['星期','开始','结束','开始周','结束周','规则','指定周次','操作'])
        for i, width in enumerate([80,85,85,65,65,80,170,60]):
            self.table.setColumnWidth(i, width)
        layout.addWidget(self.table)
        add = QPushButton('＋ 添加上课时间')
        add.clicked.connect(lambda: self.add_slot())
        layout.addWidget(add)
        for slot in course['slots'] if course else [None]:
            self.add_slot(slot)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('保存')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def choose_color(self):
        color = QColorDialog.getColor(QColor(self.color), self, '选择课程颜色')
        if color.isValid():
            self.color = color.name()
            self.color_button.setText(self.color)

    def add_slot(self, slot=None):
        slot = slot or dict(weekday=0, start='08:00', end='09:40', first_week=1, last_week=20, pattern='all', weeks='')
        row = self.table.rowCount()
        self.table.insertRow(row)
        weekday = QComboBox()
        weekday.addItems(['周' + w for w in '一二三四五六日'])
        weekday.setCurrentIndex(slot['weekday'])
        widgets = [weekday]
        for key in ('start','end'):
            widget = QTimeEdit(QTime.fromString(slot[key], 'HH:mm'))
            widget.setDisplayFormat('HH:mm')
            widgets.append(widget)
        for key in ('first_week','last_week'):
            widget = QSpinBox()
            widget.setRange(1,54)
            widget.setValue(slot[key])
            widgets.append(widget)
        pattern = QComboBox()
        pattern.addItems(['每周','单周','双周'])
        pattern.setCurrentIndex(['all','odd','even'].index(slot['pattern']))
        widgets.extend([pattern, QLineEdit(slot['weeks'])])
        delete = QPushButton('移除')
        delete.clicked.connect(lambda: self.remove_slot(delete))
        widgets.append(delete)
        for col, widget in enumerate(widgets):
            self.table.setCellWidget(row, col, widget)

    def remove_slot(self, button):
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row,7) is button:
                self.table.removeRow(row)
                break

    def value(self):
        slots = []
        for row in range(self.table.rowCount()):
            w = [self.table.cellWidget(row,c) for c in range(7)]
            slots.append(dict(weekday=w[0].currentIndex(), start=w[1].time().toString('HH:mm'), end=w[2].time().toString('HH:mm'), first_week=w[3].value(), last_week=w[4].value(), pattern=['all','odd','even'][w[5].currentIndex()], weeks=w[6].text().strip()))
        return dict(id=self.course['id'] if self.course else None, name=self.name.text(), teacher=self.teacher.text(), room=self.room.text(), color=self.color, reminder_enabled=self.reminder.isChecked(), reminder_minutes=self.reminder_minutes.value() if self.override.isChecked() else None, slots=slots)

    def save(self):
        try:
            course = self.value()
            validate(course)
            semester = self.store.semester()
            if semester is None:
                raise ValueError('请先设置学期开始日期。')
            overlapping = conflicts(course, self.store.all(), semester)
            if overlapping and QMessageBox.question(self, '时间冲突', '与以下课程存在时间重叠：\n' + '、'.join(overlapping) + '\n仍要保存特殊安排吗？', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return
            self.store.save(course)
        except (ValueError, sqlite3.Error) as error:
            QMessageBox.warning(self, '无法保存', str(error))
            return
        self.accept()


class CourseManager(QDialog):
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle('课程管理与学期设置')
        self.resize(500,480)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('学期开始日期所在的星期一为第 1 教学周起点。'))
        row = QHBoxLayout()
        semester = store.semester() or date.today()
        self.semester = QDateEdit(QDate(semester.year, semester.month, semester.day))
        self.semester.setCalendarPopup(True)
        self.semester.setDisplayFormat('yyyy-MM-dd')
        row.addWidget(self.semester)
        save = QPushButton('保存学期日期')
        save.clicked.connect(self.save_semester)
        row.addWidget(save)
        layout.addLayout(row)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _: self.edit())
        layout.addWidget(self.list)
        row = QHBoxLayout()
        for label, callback in [('添加课程',self.add),('编辑选中',self.edit),('删除选中',self.delete)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        database_label = QLabel(f'数据库：{store.path}')
        database_label.setWordWrap(True)
        layout.addWidget(database_label)
        close = QPushButton('完成')
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        self.refresh()

    def refresh(self):
        self.courses = self.store.all()
        self.list.clear()
        for course in self.courses:
            self.list.addItem(f"{course['name']} · {course['room'] or '未填写地点'} · {len(course['slots'])} 个时间安排")

    def save_semester(self):
        try:
            self.store.set_semester(self.semester.date().toPython())
        except sqlite3.Error as error:
            QMessageBox.warning(self, '无法保存', str(error))
            return
        QMessageBox.information(self, '已保存', '学期开始日期已保存。')

    def add(self):
        if not self.store.semester():
            QMessageBox.information(self, '先设置学期', '请先点击“保存学期日期”，再添加课程。')
            return
        CourseEditor(self.store, parent=self).exec()
        self.refresh()

    def edit(self):
        index = self.list.currentRow()
        if index < 0:
            return
        CourseEditor(self.store, self.courses[index], self).exec()
        self.refresh()

    def delete(self):
        index = self.list.currentRow()
        if index < 0:
            return
        if QMessageBox.question(self, '确认删除', f"删除“{self.courses[index]['name']}”及其全部上课时间？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            try:
                self.store.delete(self.courses[index]['id'])
            except sqlite3.Error as error:
                QMessageBox.warning(self, '无法删除', str(error))
            self.refresh()
