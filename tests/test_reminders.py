from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest
from zoneinfo import ZoneInfo
from app.database.store import Store
from app.services.reminders import ReminderScheduler, countdown_text, next_course, zoned_occurrences
from test_schedule import course

ZONE = ZoneInfo('Asia/Shanghai')


class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'test.db'
        self.store = Store(self.path)
        self.addCleanup(self.store.close)
        self.store.set_semester(date(2026,9,7))
        self.cid = self.store.save(course())
        self.sent = []
        self.scheduler = ReminderScheduler(self.store,lambda items,now,keys: self.sent.append((items,now,keys)))

    def now(self,day=7,hour=7,minute=45):
        return datetime(2026,9,day,hour,minute,tzinfo=ZONE)

    def modify(self,**fields):
        value = self.store.all()[0]
        value.update(fields)
        self.store.save(value)

    def test_normal_and_no_duplicate(self):
        self.assertEqual(self.scheduler.check(self.now(minute=44)),[])
        self.assertEqual(len(self.scheduler.check(self.now())),1)
        self.assertEqual(self.scheduler.check(self.now(minute=46)),[])
        self.assertEqual(len(self.sent),1)
        self.assertEqual(self.store.db.execute('SELECT state FROM reminder_events').fetchone()[0],'submitted')

    def test_odd_week(self):
        value = self.store.all()[0]
        value['slots'][0]['pattern'] = 'odd'
        self.store.save(value)
        self.assertEqual(len(self.scheduler.check(self.now())),1)
        self.assertEqual(self.scheduler.check(self.now(day=14)),[])

    def test_even_week(self):
        value = self.store.all()[0]
        value['slots'][0]['pattern'] = 'even'
        self.store.save(value)
        self.assertEqual(self.scheduler.check(self.now()),[])
        self.assertEqual(len(self.scheduler.check(self.now(day=14))),1)

    def test_specified_week(self):
        value = self.store.all()[0]
        value['slots'][0]['weeks'] = '2,4'
        self.store.save(value)
        self.assertEqual(self.scheduler.check(self.now()),[])
        self.assertEqual(len(self.scheduler.check(self.now(day=14))),1)
        self.assertEqual(self.scheduler.check(self.now(day=21)),[])

    def test_edit_time_recomputes(self):
        value = self.store.all()[0]
        value['slots'][0].update(start='09:00',end='10:00')
        self.store.save(value)
        self.assertEqual(self.scheduler.check(self.now()),[])
        self.assertEqual(len(self.scheduler.check(self.now(hour=8,minute=45))),1)

    def test_delete_no_reminder_and_reused_id(self):
        self.scheduler.check(self.now())
        self.store.delete(self.cid)
        self.assertEqual(self.scheduler.check(self.now(day=14)),[])
        self.store.save(course(name='新课程'))
        self.assertEqual(len(self.scheduler.check(self.now())),1)

    def test_restart_before_and_after_due(self):
        self.scheduler.check(self.now(minute=40))
        self.store.close()
        self.store = Store(self.path)
        self.addCleanup(self.store.close)
        scheduler = ReminderScheduler(self.store,lambda *args: self.sent.append(args))
        self.assertEqual(len(scheduler.check(self.now())),1)
        self.store.close()
        self.store = Store(self.path)
        self.addCleanup(self.store.close)
        scheduler = ReminderScheduler(self.store,lambda *args: self.sent.append(args))
        self.assertEqual(scheduler.check(self.now(minute=46)),[])

    def test_sleep_short_gap_catchup(self):
        self.scheduler.check(self.now(minute=40))
        self.assertEqual(len(self.scheduler.check(self.now(minute=49))),1)

    def test_sleep_old_skipped_and_urgent_catchup(self):
        # 错过 8 分钟且距上课 7 分钟：跳过，后续不会刷屏。
        self.assertEqual(self.scheduler.check(self.now(minute=53)),[])
        self.assertEqual(self.scheduler.check(self.now(minute=56)),[])
        # 另一个上课日，醒来时距开课 4 分钟：补发。
        self.assertEqual(len(self.scheduler.check(self.now(day=14,minute=56))),1)
        self.assertEqual(self.scheduler.check(self.now(day=21,hour=8,minute=1)),[])

    def test_batch_and_disabled(self):
        self.store.save(course(name='英语'))
        self.scheduler.check(self.now())
        self.assertEqual(len(self.sent),1)
        self.assertEqual(len(self.sent[0][0]),2)
        self.store.set_settings({'reminders_enabled':0})
        self.assertEqual(self.scheduler.check(self.now(day=14)),[])

    def test_per_course_and_global_change(self):
        self.modify(reminder_minutes=5)
        self.assertEqual(self.scheduler.check(self.now()),[])
        self.assertEqual(len(self.scheduler.check(self.now(minute=55))),1)
        self.modify(reminder_minutes=None)
        self.store.set_settings({'reminder_minutes':30})
        self.assertEqual(len(self.scheduler.check(self.now(day=14,minute=30))),1)

    def test_title_lead_end_edit_does_not_repeat(self):
        self.scheduler.check(self.now())
        value = self.store.all()[0]
        value.update(name='修改名称',reminder_minutes=10)
        value['slots'][0]['end'] = '10:00'
        self.store.save(value)
        self.assertEqual(self.scheduler.check(self.now(minute=50)),[])

    def test_course_disabled(self):
        self.modify(reminder_enabled=False)
        self.assertEqual(self.scheduler.check(self.now()),[])

    def test_clock_rollback_and_timezone_change(self):
        self.scheduler.check(self.now())
        self.assertEqual(self.scheduler.check(self.now(minute=40)),[])
        self.assertEqual(self.scheduler.check(self.now()),[])
        # 本地课表跟随系统时区，已提醒的同一当地日期不再重复。
        changed = datetime(2026,9,7,7,45,tzinfo=ZoneInfo('Europe/London'))
        self.assertEqual(self.scheduler.check(changed),[])

    def test_cross_midnight_advance(self):
        value = self.store.all()[0]
        value['slots'][0].update(weekday=1,start='00:05',end='01:00')
        self.store.save(value)
        self.assertEqual(len(self.scheduler.check(self.now(hour=23,minute=50))),1)
        self.assertEqual(self.scheduler.check(self.now(day=8,hour=0,minute=0)),[])

    def test_sender_failure_is_persistent(self):
        def fail(*args):
            raise RuntimeError('模拟系统通知失败')
        scheduler = ReminderScheduler(self.store,fail)
        with self.assertRaises(RuntimeError):
            scheduler.check(self.now())
        self.assertEqual(self.store.db.execute('SELECT state FROM reminder_events').fetchone()[0],'failed')
        self.assertEqual(self.scheduler.check(self.now()),[])

    def test_preparation_failure_can_retry_without_claim(self):
        def fail():
            raise RuntimeError('初始化失败')
        scheduler = ReminderScheduler(self.store,lambda *args: None,fail)
        with self.assertRaises(RuntimeError):
            scheduler.check(self.now())
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM reminder_events').fetchone()[0],0)
        self.assertEqual(len(self.scheduler.check(self.now(minute=46))),1)

    def test_claim_before_crash_and_other_connection(self):
        from app.services.reminders import event_key
        item = zoned_occurrences(self.store.all(),date(2026,9,7),self.store.semester(),ZONE)[0]
        with closing(Store(self.path)) as second:
            self.assertTrue(second.claim_event(event_key(item),self.now()))
            self.assertFalse(self.store.claim_event(event_key(item),self.now()))
        self.assertEqual(self.scheduler.check(self.now()),[])

    def test_next_class_full_semester_and_finished(self):
        self.assertIn('15 分钟',countdown_text(self.store.all(),self.store.semester(),self.now()))
        self.assertIn('今天的课程已结束',countdown_text(self.store.all(),self.store.semester(),self.now(hour=10,minute=0)))
        value = self.store.all()[0]
        value['slots'][0]['weeks'] = '20'
        self.store.save(value)
        item = next_course(self.store.all(),self.store.semester(),self.now())
        self.assertEqual(item['start'].date(),date(2027,1,18))

    def test_naive_time_rejected(self):
        with self.assertRaises(ValueError):
            self.scheduler.check(datetime(2026,9,7,7,45))

    def test_dst_gap_and_fold(self):
        value = self.store.all()[0]
        value['slots'][0].update(weekday=6,start='02:30',end='04:00')
        self.assertEqual(zoned_occurrences([value],date(2026,3,8),date(2026,3,2),ZoneInfo('America/New_York')),[])
        value['slots'][0].update(start='01:30',end='02:30')
        items = zoned_occurrences([value],date(2026,11,1),date(2026,10,26),ZoneInfo('America/New_York'))
        self.assertEqual(items[0]['start'].fold,0)
        self.assertEqual(items[0]['start'].utcoffset(),timedelta(hours=-4))


class MigrationTests(unittest.TestCase):
    def test_v1_upgrade_preserves_data_and_backup(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as directory:
            path = Path(directory) / 'v1.db'
            with closing(sqlite3.connect(path)) as db:
                db.executescript("""
                    CREATE TABLE courses (id INTEGER PRIMARY KEY, name TEXT NOT NULL, teacher TEXT NOT NULL, room TEXT NOT NULL, color TEXT NOT NULL, reminder_enabled INTEGER NOT NULL DEFAULT 1);
                    CREATE TABLE slots (id INTEGER PRIMARY KEY, course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE, weekday INTEGER NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL, first_week INTEGER NOT NULL, last_week INTEGER NOT NULL, pattern TEXT NOT NULL, weeks TEXT NOT NULL);
                    CREATE TABLE settings (key TEXT PRIMARY KEY,value TEXT NOT NULL);
                    INSERT INTO courses VALUES (1,'历史课程','教师','A301','#5579ef',1);
                    INSERT INTO slots VALUES (1,1,0,'08:00','09:00',1,20,'all','');
                    INSERT INTO settings VALUES ('semester','2026-09-07');
                    PRAGMA user_version=1;
                """)
            with closing(Store(path)) as store:
                self.assertEqual(store.all()[0]['name'],'历史课程')
                self.assertTrue(store.all()[0]['uid'])
                self.assertIsNone(store.all()[0]['reminder_minutes'])
                self.assertEqual(len(store.all()[0]['slots']),1)
                self.assertEqual(store.semester(),date(2026,9,7))
            with closing(sqlite3.connect(str(path)+'.v1.bak')) as backup:
                self.assertEqual(backup.execute('PRAGMA user_version').fetchone()[0],1)
            with closing(Store(path)) as reopened:
                self.assertEqual(reopened.db.execute('PRAGMA user_version').fetchone()[0],2)
