"""SQLite v2：课程、时间安排、设置与持久化提醒事件。"""
import os
import re
import sqlite3
import uuid
from contextlib import nullcontext
from datetime import date
from pathlib import Path


def default_path():
    root = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    return root / 'ClassWidget' / 'classwidget.db'


def validate(course):
    minutes = course.get('reminder_minutes')
    if minutes is not None and (type(minutes) is not int or not 1 <= minutes <= 1440):
        raise ValueError('提醒提前时间必须为 1–1440 分钟。')
    if not course['name'].strip():
        raise ValueError('请输入课程名称。')
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', course['color']):
        raise ValueError('课程颜色格式无效。')
    if not course['slots']:
        raise ValueError('至少添加一个上课时间。')
    for slot in course['slots']:
        if not 0 <= slot['weekday'] <= 6 or not 1 <= slot['first_week'] <= slot['last_week'] <= 54:
            raise ValueError('星期或教学周范围无效（1–54 周）。')
        for key in ('start', 'end'):
            if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', slot[key]):
                raise ValueError('时间必须使用 HH:mm 格式。')
        if slot['start'] == slot['end']:
            raise ValueError('开始和结束时间不能相同。')
        if slot['pattern'] not in ('all', 'odd', 'even'):
            raise ValueError('周次规则无效。')
        if slot['weeks']:
            try:
                weeks = sorted({int(w.strip()) for w in slot['weeks'].replace('，', ',').split(',')})
            except ValueError:
                raise ValueError('指定周次请输入逗号分隔的数字，例如 1,3,5。') from None
            if any(w < slot['first_week'] or w > slot['last_week'] for w in weeks):
                raise ValueError('指定周次必须在开始与结束教学周内。')
            slot['weeks'] = ','.join(map(str, weeks))


class Store:
    def __init__(self, path=None):
        self.path = Path(path) if path else default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        version = self.db.execute('PRAGMA user_version').fetchone()[0]
        if version > 2:
            self.db.close()
            raise RuntimeError('数据库来自更新版本，请使用新版 ClassWidget。')
        if version == 0:
            with self.db:
                self.db.execute('CREATE TABLE courses (id INTEGER PRIMARY KEY, name TEXT NOT NULL, teacher TEXT NOT NULL, room TEXT NOT NULL, color TEXT NOT NULL, reminder_enabled INTEGER NOT NULL DEFAULT 1)')
                self.db.execute('CREATE TABLE slots (id INTEGER PRIMARY KEY, course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE, weekday INTEGER NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL, first_week INTEGER NOT NULL, last_week INTEGER NOT NULL, pattern TEXT NOT NULL, weeks TEXT NOT NULL)')
                self.db.execute('CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
                self.db.execute('PRAGMA user_version=1')
        if version < 2:
            # 升级之前保留第二阶段完整数据库，绝不覆盖已有备份。
            if version == 1:
                backup_path = self.path.with_name(self.path.name + '.v1.bak')
                if not backup_path.exists():
                    backup = sqlite3.connect(backup_path)
                    try:
                        self.db.backup(backup)
                    finally:
                        backup.close()
            with self.db:
                self.db.execute('BEGIN IMMEDIATE')
                self.db.execute('ALTER TABLE courses ADD COLUMN uid TEXT')
                self.db.execute('UPDATE courses SET uid=lower(hex(randomblob(16)))')
                self.db.execute('CREATE UNIQUE INDEX courses_uid ON courses(uid)')
                self.db.execute('ALTER TABLE courses ADD COLUMN reminder_minutes INTEGER')
                self.db.execute('CREATE TABLE reminder_events (event_key TEXT PRIMARY KEY, state TEXT NOT NULL, recorded_at TEXT NOT NULL, error TEXT NOT NULL DEFAULT \'\')')
                self.db.execute('PRAGMA user_version=2')

    def get_setting(self, key, default):
        row = self.db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return row[0] if row else default

    def set_settings(self, values):
        with self.db:
            self.db.executemany('INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', [(k,str(v)) for k,v in values.items()])

    def reminder_options(self):
        return dict(enabled=self.get_setting('reminders_enabled','1') == '1', minutes=int(self.get_setting('reminder_minutes','15')))

    def claim_event(self, key, now, state='claimed'):
        with self.db:
            cursor = self.db.execute('INSERT OR IGNORE INTO reminder_events(event_key,state,recorded_at) VALUES (?,?,?)', (key,state,now.isoformat()))
        return cursor.rowcount == 1

    def has_event(self,key):
        return self.db.execute('SELECT 1 FROM reminder_events WHERE event_key=?',(key,)).fetchone() is not None

    def finish_events(self, keys, state, now, error=''):
        with self.db:
            self.db.executemany('UPDATE reminder_events SET state=?,recorded_at=?,error=? WHERE event_key=?', [(state,now.isoformat(),error[:1000],key) for key in keys])

    def semester(self):
        row = self.db.execute("SELECT value FROM settings WHERE key='semester'").fetchone()
        return date.fromisoformat(row[0]) if row else None

    def set_semester(self, day):
        with self.db:
            self.db.execute("INSERT INTO settings VALUES ('semester', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (day.isoformat(),))

    def all(self):
        courses = [dict(row) for row in self.db.execute('SELECT * FROM courses ORDER BY name,id')]
        for course in courses:
            course['slots'] = [dict(row) for row in self.db.execute('SELECT * FROM slots WHERE course_id=? ORDER BY weekday,start', (course['id'],))]
        return courses

    def save(self, course, commit=True):
        validate(course)
        fields = (course['name'].strip(), course['teacher'].strip(), course['room'].strip(), course['color'], int(course['reminder_enabled']), course.get('reminder_minutes'))
        with self.db if commit else nullcontext():
            if course.get('id') is None:
                cid = self.db.execute('INSERT INTO courses(name,teacher,room,color,reminder_enabled,reminder_minutes,uid) VALUES (?,?,?,?,?,?,?)', fields + (uuid.uuid4().hex,)).lastrowid
            else:
                cid = course['id']
                cursor = self.db.execute('UPDATE courses SET name=?,teacher=?,room=?,color=?,reminder_enabled=?,reminder_minutes=? WHERE id=?', fields + (cid,))
                if cursor.rowcount != 1:
                    raise ValueError('课程已不存在，请刷新列表。')
                self.db.execute('DELETE FROM slots WHERE course_id=?', (cid,))
            for slot in course['slots']:
                self.db.execute('INSERT INTO slots(course_id,weekday,start,end,first_week,last_week,pattern,weeks) VALUES (?,?,?,?,?,?,?,?)', (cid,) + tuple(slot[k] for k in ('weekday','start','end','first_week','last_week','pattern','weeks')))
        return cid

    def delete(self, cid):
        with self.db:
            self.db.execute('DELETE FROM courses WHERE id=?', (cid,))

    def close(self):
        self.db.close()
