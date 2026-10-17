import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from app.database.store import Store, validate
from app.services.schedule import active, conflicts, day_items, occurrences, status, teaching_week


def course(**changes):
    value = dict(id=None, name='高等数学', teacher='张老师', room='A301', color='#5579ef', reminder_enabled=True,
                 slots=[dict(weekday=0, start='08:00', end='09:40', first_week=1, last_week=20, pattern='all', weeks='')])
    value.update(changes)
    return value


class ScheduleTests(unittest.TestCase):
    def test_week_boundary(self):
        semester = date(2026,9,2)
        self.assertEqual(teaching_week(date(2026,8,31), semester),1)
        self.assertEqual(teaching_week(date(2026,9,7), semester),2)
        self.assertEqual(teaching_week(date(2026,8,30), semester),0)

    def test_patterns_and_specified(self):
        slot = course()['slots'][0]
        slot['pattern'] = 'odd'
        self.assertTrue(active(slot,1))
        self.assertFalse(active(slot,2))
        slot['pattern'] = 'even'
        self.assertTrue(active(slot,2))
        self.assertFalse(active(slot,1))
        slot['weeks'] = '1,4'
        self.assertTrue(active(slot,1))
        self.assertTrue(active(slot,4))
        self.assertFalse(active(slot,2))
        self.assertFalse(active(slot,21))

    def test_validation(self):
        value = course()
        value['slots'][0]['weeks'] = '3，1,3'
        validate(value)
        self.assertEqual(value['slots'][0]['weeks'], '1,3')
        value['slots'][0]['weeks'] = '21'
        with self.assertRaises(ValueError):
            validate(value)
        value = course(name=' ')
        with self.assertRaises(ValueError):
            validate(value)

    def test_cross_day_and_status(self):
        value = course()
        value['slots'][0].update(start='23:00', end='01:00')
        items = day_items([value],date(2026,9,8),date(2026,9,7))
        self.assertEqual(len(items),1)
        self.assertEqual(status(items[0],datetime(2026,9,8,0,30)),'正在上课')
        item = occurrences([course()],date(2026,9,7),date(2026,9,7))[0]
        for hour, minute, expected in [(7,0,'未开始'),(7,45,'即将开始'),(8,0,'正在上课'),(9,40,'已结束')]:
            self.assertEqual(status(item,datetime(2026,9,7,hour,minute)),expected)

    def test_conflict_rules_cross_day_and_self(self):
        first = course(id=1)
        other = course(id=2, name='英语')
        self.assertEqual(conflicts(first,[other],date(2026,9,7)),['英语'])
        other['slots'][0]['start'] = '09:40'
        other['slots'][0]['end'] = '10:00'
        self.assertEqual(conflicts(first,[other],date(2026,9,7)),[])
        first['slots'][0]['pattern'] = 'odd'
        other['slots'][0].update(start='08:00',pattern='even')
        self.assertEqual(conflicts(first,[other],date(2026,9,7)),[])
        first['slots'][0].update(start='23:00',end='01:00',pattern='all')
        other['slots'][0].update(weekday=1,start='00:30',end='02:00',pattern='all')
        self.assertEqual(conflicts(first,[other],date(2026,9,7)),['英语'])
        self.assertEqual(conflicts(first,[first],date(2026,9,7)),[])
        first['slots'].append(dict(first['slots'][0]))
        self.assertEqual(conflicts(first,[],date(2026,9,7)),['高等数学'])

    def test_database_crud_restart_and_cascade(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as directory:
            path = Path(directory) / 'test.db'
            store = Store(path)
            self.assertIsNone(store.semester())
            store.set_semester(date(2026,9,7))
            value = course()
            value['slots'].append(dict(value['slots'][0],weekday=2))
            cid = store.save(value)
            store.close()
            store = Store(path)
            self.assertEqual(store.semester(),date(2026,9,7))
            stored = store.all()[0]
            self.assertEqual(len(stored['slots']),2)
            stored['name'] = '修改后的数学'
            stored['slots'][0]['start'] = '07:00'
            store.save(stored)
            self.assertEqual(store.all()[0]['name'],'修改后的数学')
            self.assertEqual(store.all()[0]['slots'][0]['start'],'07:00')
            store.delete(cid)
            self.assertEqual(store.all(),[])
            self.assertEqual(store.db.execute('SELECT COUNT(*) FROM slots').fetchone()[0],0)
            self.assertEqual(store.db.execute('PRAGMA user_version').fetchone()[0],2)
            store.close()


if __name__ == '__main__':
    unittest.main()
