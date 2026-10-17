from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from app.database.store import Store
from app.services.data_exchange import (backup_database, export_file, import_courses,
    load_file, normalize, read_backup, restore_courses, fingerprint)
from test_schedule import course


class DataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root/'current.db')
        self.addCleanup(self.store.close)
        self.store.set_semester(date(2026,9,7))
        value = course()
        value['slots'].append(dict(value['slots'][0],weekday=2))
        self.store.save(value)

    def other_store(self):
        other = Store(self.root/'other.db')
        self.addCleanup(other.close)
        return other

    def test_json_roundtrip_and_repeat_import(self):
        path = self.root/'课程.json'
        export_file(self.store,path)
        courses,semester = load_file(path)
        self.assertEqual(len(courses[0]['slots']),2)
        other = self.other_store()
        self.assertEqual(import_courses(other,courses,semester),(1,0))
        self.assertEqual(other.semester(),date(2026,9,7))
        self.assertEqual(fingerprint(other.all()[0]),fingerprint(self.store.all()[0]))
        self.assertEqual(import_courses(other,courses,semester),(0,1))

    def test_csv_roundtrip_chinese_multiline_and_quotes(self):
        value = self.store.all()[0]
        value.update(name='数学, "实验"',room='教学楼\nA301',reminder_minutes=10)
        self.store.save(value)
        path = self.root/'课程.csv'
        export_file(self.store,path)
        self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'))
        courses,semester = load_file(path)
        other = self.other_store()
        import_courses(other,courses,semester)
        self.assertEqual(other.all()[0]['room'],'教学楼\nA301')
        self.assertEqual(other.all()[0]['reminder_minutes'],10)
        self.assertEqual(len(other.all()[0]['slots']),2)

    def test_duplicate_content_without_uid_and_slot_order(self):
        value = normalize(dict(self.store.all()[0],reminder_enabled=True))
        value['uid'] = None
        value['slots'].reverse()
        value['slots'].append(deepcopy(value['slots'][0]))
        self.assertEqual(import_courses(self.store,[value]),(0,1))

    def test_same_uid_does_not_overwrite_edited_course(self):
        value = normalize(dict(self.store.all()[0],reminder_enabled=True))
        value['name'] = '外部修改名称'
        self.assertEqual(import_courses(self.store,[value]),(0,1))
        self.assertEqual(self.store.all()[0]['name'],'高等数学')

    def test_import_preserves_existing_semester(self):
        self.assertEqual(import_courses(self.store,[],date(2027,2,1)),(0,0))
        self.assertEqual(self.store.semester(),date(2026,9,7))

    def test_invalid_file_and_fields(self):
        path = self.root/'invalid.json'
        path.write_text('{"format":"other"}',encoding='utf-8')
        with self.assertRaises(ValueError):
            load_file(path)
        for field,value in [('name',123),('reminder_enabled',1),('reminder_minutes',0),('uid','bad')]:
            with self.subTest(field=field):
                invalid = course(**{field:value})
                with self.assertRaises(ValueError):
                    normalize(invalid)
        invalid = course()
        invalid['slots'][0]['weekday'] = True
        with self.assertRaises(ValueError):
            normalize(invalid)

    def test_csv_headers_and_inconsistent_group(self):
        path = self.root/'bad.csv'
        path.write_text('name,start\n数学,08:00',encoding='utf-8')
        with self.assertRaises(ValueError):
            load_file(path)
        export_file(self.store,path)
        text = path.read_text(encoding='utf-8-sig')
        lines = text.splitlines()
        lines[-1] = lines[-1].replace('高等数学','不同名称')
        path.write_text('\n'.join(lines),encoding='utf-8')
        with self.assertRaises(ValueError):
            load_file(path)

    def test_validation_happens_before_writes(self):
        original = self.store.all()
        with self.assertRaises(ValueError):
            import_courses(self.store,[course(name='可导入'),course(name='')])
        self.assertEqual(self.store.all(),original)

    def test_transaction_failure_rolls_back_every_course(self):
        original = self.store.all()
        real_save = self.store.save
        calls = []
        def fail_second(value,commit=True):
            calls.append(value)
            if len(calls)==2:
                raise sqlite3.OperationalError('模拟磁盘写入失败')
            return real_save(value,commit=commit)
        with patch.object(self.store,'save',side_effect=fail_second):
            with self.assertRaises(sqlite3.Error):
                import_courses(self.store,[course(name='第一门'),course(name='第二门')])
        self.assertEqual(self.store.all(),original)

    def test_backup_restore_with_safety_and_history(self):
        path = self.root/'backup.db'
        backup_database(self.store,path)
        original_uid = self.store.all()[0]['uid']
        self.store.delete(self.store.all()[0]['id'])
        self.store.save(course(name='恢复前课程'))
        self.store.claim_event('already-notified',datetime(2026,9,7))
        self.store.set_settings({'reminder_minutes':30})
        count,safety = restore_courses(self.store,path)
        self.assertEqual(count,1)
        self.assertTrue(safety.exists())
        self.assertEqual(self.store.all()[0]['uid'],original_uid)
        self.assertTrue(self.store.has_event('already-notified'))
        self.assertEqual(self.store.reminder_options()['minutes'],30)
        self.assertEqual(read_backup(safety)[0][0]['name'],'恢复前课程')

    def test_invalid_backup_does_not_modify_current(self):
        path = self.root/'broken.db'
        path.write_bytes(b'not sqlite')
        original = self.store.all()
        with self.assertRaises((sqlite3.Error,ValueError)):
            restore_courses(self.store,path)
        self.assertEqual(self.store.all(),original)

    def test_restore_failure_rolls_back_current(self):
        path = self.root/'backup.db'
        backup_database(self.store,path)
        self.store.save(course(name='新增课程'))
        original = self.store.all()
        with patch.object(self.store,'save',side_effect=sqlite3.OperationalError('模拟恢复失败')):
            with self.assertRaises(sqlite3.Error):
                restore_courses(self.store,path)
        self.assertEqual(self.store.all(),original)

    def test_cannot_overwrite_live_database(self):
        with self.assertRaises(ValueError):
            backup_database(self.store,self.store.path)
        with self.assertRaises(ValueError):
            export_file(self.store,self.store.path)
