from datetime import date,datetime
import unittest
from app.services.schedule import remaining_today
from app.ui.appearance import mode_size
from test_schedule import course


class TodayTests(unittest.TestCase):
    def test_only_today_unfinished_including_current(self):
        value = course()
        value['slots'] = [dict(value['slots'][0],weekday=0,start=start,end=end) for start,end in [('08:00','09:00'),('10:00','11:00'),('14:00','15:00')]]
        value['slots'].append(dict(value['slots'][0],weekday=1,start='09:00',end='10:00'))
        items = remaining_today([value],date(2026,9,7),datetime(2026,9,7,10,30))
        self.assertEqual([i['start'].strftime('%H:%M') for i in items],['10:00','14:00'])

    def test_end_boundary_removes_course_and_no_tomorrow(self):
        value = course()
        value['slots'][0].update(start='08:00',end='09:00')
        self.assertEqual(remaining_today([value],date(2026,9,7),datetime(2026,9,7,9)),[])
        self.assertEqual(remaining_today([value],date(2026,9,7),datetime(2026,9,8,7)),[])

    def test_previous_day_overnight_not_shown(self):
        value = course()
        value['slots'][0].update(start='23:00',end='02:00')
        self.assertEqual(remaining_today([value],date(2026,9,7),datetime(2026,9,8,1)),[])
        self.assertEqual(len(remaining_today([value],date(2026,9,7),datetime(2026,9,7,23,30))),1)

    def test_unconfigured(self):
        self.assertEqual(remaining_today([course()],None,datetime(2026,9,7,7)),[])

    def test_automatic_compaction_and_wide_week(self):
        self.assertLess(mode_size('today',0).height(),mode_size('today',1).height())
        self.assertLess(mode_size('today',1).height(),mode_size('today',3).height())
        self.assertEqual(mode_size('today',3),mode_size('today',12))
        self.assertLess(mode_size('week').width(),mode_size('week').height())
