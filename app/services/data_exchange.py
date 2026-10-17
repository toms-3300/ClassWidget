"""格式校验、原子导入导出与 SQLite 在线备份/课程恢复。"""
from contextlib import closing
import csv
from datetime import date, datetime
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from app.database.store import validate

SLOT_FIELDS = ('weekday','start','end','first_week','last_week','pattern','weeks')
COURSE_FIELDS = ('name','teacher','room','color','reminder_enabled','reminder_minutes')
CSV_FIELDS = ('course_key',) + COURSE_FIELDS + SLOT_FIELDS + ('semester_start',)
MAX_BYTES = 10 * 1024 * 1024


def normalize(value):
    if not isinstance(value,dict):
        raise ValueError('每门课程必须是一个对象。')
    result = {}
    for key in ('name','teacher','room','color'):
        field = value.get(key,'' if key != 'color' else '#5579ef')
        if not isinstance(field,str) or len(field) > 1000:
            raise ValueError(f'{key} 必须是长度不超过 1000 的文本。')
        result[key] = field.strip()
    result['color'] = result['color'].lower()
    enabled = value.get('reminder_enabled',True)
    if type(enabled) is not bool:
        raise ValueError('reminder_enabled 必须为 true 或 false。')
    result['reminder_enabled'] = enabled
    result['reminder_minutes'] = value.get('reminder_minutes')
    slots = value.get('slots')
    if not isinstance(slots,list) or not 1 <= len(slots) <= 100:
        raise ValueError('每门课程必须包含 1–100 个上课时间。')
    result['slots'] = []
    for source in slots:
        if not isinstance(source,dict) or not all(key in source for key in SLOT_FIELDS):
            raise ValueError('上课时间缺少必需字段。')
        slot = {k:source[k] for k in SLOT_FIELDS}
        for key in ('weekday','first_week','last_week'):
            if type(slot[key]) is not int:
                raise ValueError(f'{key} 必须为整数。')
        for key in ('start','end','pattern','weeks'):
            if not isinstance(slot[key],str) or len(slot[key]) > 200:
                raise ValueError(f'{key} 必须为有效文本。')
        result['slots'].append(slot)
    validate(result)
    # 时间顺序和重复安排不影响课程内容指纹。
    unique = {json.dumps(s,sort_keys=True):s for s in result['slots']}
    result['slots'] = [unique[k] for k in sorted(unique)]
    uid = value.get('uid')
    if uid is not None and (not isinstance(uid,str) or not re.fullmatch('[0-9a-f]{32}',uid)):
        raise ValueError('课程 uid 格式无效。')
    result['uid'] = uid
    return result


def fingerprint(course):
    normalized = normalize(dict(course,reminder_enabled=bool(course['reminder_enabled'])))
    normalized.pop('uid')
    return hashlib.sha256(json.dumps(normalized,sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()


def parse_semester(value):
    if value in (None,''):
        return None
    if not isinstance(value,str):
        raise ValueError('学期日期应为 YYYY-MM-DD 文本。')
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError('学期日期格式无效。') from None


def load_file(path):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('导入文件不能超过 10 MB。')
    text = path.read_text(encoding='utf-8-sig')
    if path.suffix.lower() == '.json':
        data = json.loads(text)
        if not isinstance(data,dict) or data.get('format') != 'ClassWidget' or type(data.get('version')) is not int or data.get('version') != 1:
            raise ValueError('这不是受支持的 ClassWidget JSON 文件。')
        courses = data.get('courses')
        semester = parse_semester(data.get('semester_start'))
    elif path.suffix.lower() == '.csv':
        reader = csv.DictReader(io.StringIO(text,newline=''))
        if reader.fieldnames != list(CSV_FIELDS):
            raise ValueError('CSV 表头不正确，请先导出 CSV 作为模板。')
        grouped, semesters = {}, set()
        for number,row in enumerate(reader,2):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f'CSV 第 {number} 行列数不正确。')
            if row['semester_start']:
                semesters.add(row['semester_start'])
            key = row['course_key']
            if not key or row['reminder_enabled'] not in ('0','1'):
                raise ValueError(f'CSV 第 {number} 行课程标识或提醒开关无效。')
            try:
                base = {k:row[k] for k in ('name','teacher','room','color')}
                base.update(reminder_enabled=row['reminder_enabled']=='1',reminder_minutes=int(row['reminder_minutes']) if row['reminder_minutes'] else None)
                slot = {k:row[k] for k in SLOT_FIELDS}
                for field in ('weekday','first_week','last_week'):
                    slot[field] = int(slot[field])
            except ValueError:
                raise ValueError(f'CSV 第 {number} 行数字格式无效。') from None
            if key in grouped:
                if any(grouped[key][k] != base[k] for k in COURSE_FIELDS):
                    raise ValueError(f'CSV 同一 course_key 的课程字段不一致（第 {number} 行）。')
                grouped[key]['slots'].append(slot)
            else:
                grouped[key] = dict(base,uid=key,slots=[slot])
        if len(semesters) > 1:
            raise ValueError('CSV 中出现了多个不同的学期日期。')
        semester = parse_semester(next(iter(semesters),None))
        courses = list(grouped.values())
    else:
        raise ValueError('请选择 .json 或 .csv 文件。')
    if not isinstance(courses,list) or len(courses) > 2000:
        raise ValueError('课程列表无效或超过 2000 门。')
    return [normalize(course) for course in courses], semester


def atomic_write(path,content):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=path.parent,suffix='.tmp')
    try:
        with os.fdopen(handle,'w',encoding='utf-8-sig' if path.suffix.lower()=='.csv' else 'utf-8',newline='') as file:
            file.write(content)
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def export_file(store,path):
    path = Path(path)
    if path.resolve() == store.path.resolve():
        raise ValueError('导出目标不能是正在使用的数据库。')
    courses = [normalize(dict(c,reminder_enabled=bool(c['reminder_enabled']))) for c in store.all()]
    semester = store.semester()
    if path.suffix.lower() == '.json':
        content = json.dumps(dict(format='ClassWidget',version=1,semester_start=semester.isoformat() if semester else None,courses=courses),ensure_ascii=False,indent=2)
    elif path.suffix.lower() == '.csv':
        output = io.StringIO(newline='')
        writer = csv.DictWriter(output,fieldnames=CSV_FIELDS)
        writer.writeheader()
        for course in courses:
            for slot in course['slots']:
                writer.writerow(dict(course_key=course['uid'],**{k:course[k] if k != 'reminder_enabled' else int(course[k]) for k in COURSE_FIELDS},**slot,semester_start=semester.isoformat() if semester else ''))
        content = output.getvalue()
    else:
        raise ValueError('导出文件扩展名必须为 .json 或 .csv。')
    atomic_write(path,content)


def import_courses(store,courses,semester=None):
    courses = [normalize(c) for c in courses]
    existing = store.all()
    hashes = {fingerprint(c) for c in existing}
    uids = {c['uid'] for c in existing}
    added,skipped = 0,0
    with store.db:
        store.db.execute('BEGIN IMMEDIATE')
        for course in courses:
            digest = fingerprint(course)
            if digest in hashes or (course['uid'] and course['uid'] in uids):
                skipped += 1
                continue
            cid = store.save(course,commit=False)
            if course['uid']:
                store.db.execute('UPDATE courses SET uid=? WHERE id=?',(course['uid'],cid))
                uids.add(course['uid'])
            hashes.add(digest)
            added += 1
        # 只在尚未配置学期时采用导入日期，不覆盖已有学期。
        if semester is not None and store.semester() is None:
            store.db.execute('INSERT INTO settings VALUES (?,?)',('semester',semester.isoformat()))
    return added,skipped


def backup_database(store,path):
    path = Path(path)
    if path.resolve() == store.path.resolve():
        raise ValueError('不能用数据库自身作为备份目标。')
    handle,temp = tempfile.mkstemp(dir=path.parent,suffix='.db.tmp')
    os.close(handle)
    try:
        with closing(sqlite3.connect(temp)) as destination:
            store.db.backup(destination)
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def read_backup(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > 100 * 1024 * 1024:
        raise ValueError('备份文件不存在或超过 100 MB。')
    # mode=ro 不修改不可信备份，不执行备份内的视图、触发器或升级脚本。
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA trusted_schema=OFF')
        if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('数据库备份损坏。')
        version = db.execute('PRAGMA user_version').fetchone()[0]
        if version not in (1,2):
            raise ValueError('备份数据库版本不支持。')
        objects = {r['name']:r['type'] for r in db.execute('SELECT name,type FROM sqlite_master')}
        if any(objects.get(table) != 'table' for table in ('courses','slots','settings')):
            raise ValueError('备份缺少有效课程表结构。')
        rows = db.execute('SELECT * FROM courses LIMIT 2001').fetchall()
        if len(rows)>2000:
            raise ValueError('备份课程数超过上限。')
        courses = []
        for row in rows:
            value = dict(row)
            if value['reminder_enabled'] not in (0,1):
                raise ValueError('备份提醒开关无效。')
            value['reminder_enabled'] = bool(value['reminder_enabled'])
            value['slots'] = [dict(r) for r in db.execute('SELECT * FROM slots WHERE course_id=? LIMIT 101',(value['id'],))]
            courses.append(normalize(value))
        semester = db.execute("SELECT value FROM settings WHERE key='semester'").fetchone()
        return courses,parse_semester(semester[0] if semester else None)


def restore_courses(store,path):
    courses,semester = read_backup(path)
    safety = store.path.with_name('before-restore-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.db')
    backup_database(store,safety)
    # 恢复只替换课程及学期；保留当前提醒历史/全局偏好，避免回滚后重复提醒。
    with store.db:
        store.db.execute('BEGIN IMMEDIATE')
        store.db.execute('DELETE FROM courses')
        seen = set()
        for course in courses:
            if course['uid'] and course['uid'] in seen:
                raise ValueError('备份存在重复课程标识。')
            cid = store.save(course,commit=False)
            if course['uid']:
                seen.add(course['uid'])
                store.db.execute('UPDATE courses SET uid=? WHERE id=?',(course['uid'],cid))
        store.db.execute("DELETE FROM settings WHERE key='semester'")
        if semester:
            store.db.execute('INSERT INTO settings VALUES (?,?)',('semester',semester.isoformat()))
    return len(courses),safety
