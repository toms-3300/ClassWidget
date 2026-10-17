"""每次按真实本地时间重新计算，无内存长时间待触发队列。"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from app.services.schedule import occurrences, day_items

UTC = timezone.utc


def zoned_occurrences(courses, day, semester, zone):
    result = []
    for item in occurrences(courses, day, semester):
        valid = True
        for key in ('start','end'):
            naive = item[key]
            aware = naive.replace(tzinfo=zone, fold=0)
            # DST 跳时中不存在的本地时刻不通知；重复时刻选择第一次。
            if aware.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != naive:
                valid = False
            item[key] = aware
        if valid and item['end'].astimezone(UTC) > item['start'].astimezone(UTC):
            result.append(item)
    return result


def event_key(item):
    # 不包含标题、教师、提醒提前量或数据库 slot id，避免普通编辑再次提醒。
    payload = [item['course']['uid'], item['start'].replace(tzinfo=None).isoformat()]
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()


def next_course(courses, semester, now):
    if semester is None:
        return None
    # 完整覆盖支持的 54 教学周，而不是只搜索七天。
    monday = semester - timedelta(days=semester.weekday())
    day = max(now.date(), monday)
    last = monday + timedelta(weeks=54)
    while day < last:
        items = zoned_occurrences(courses, day, semester, now.tzinfo)
        future = [item for item in items if item['start'].astimezone(UTC) > now.astimezone(UTC)]
        if future:
            return min(future, key=lambda item: item['start'].astimezone(UTC))
        day += timedelta(days=1)
    return None


def countdown_text(courses, semester, now):
    if semester is None:
        return '下一节课\n请先设置学期日期'
    item = next_course(courses, semester, now)
    today = day_items(courses, now.date(), semester)
    naive_now = now.replace(tzinfo=None)
    finished = bool(today) and all(o['end'] <= naive_now for o in today)
    prefix = '今天的课程已结束\n' if finished else ''
    if item is None:
        return prefix + '暂无下一节课程'
    minutes = max(1, math.ceil((item['start'].astimezone(UTC) - now.astimezone(UTC)).total_seconds() / 60))
    if minutes < 60:
        remaining = f'{minutes} 分钟'
    elif minutes < 1440:
        remaining = f'{minutes // 60} 小时 {minutes % 60} 分钟'
    else:
        remaining = f'{minutes // 1440} 天 {(minutes % 1440) // 60} 小时'
    course = item['course']
    return prefix + f"下一节：{course['name'][:36]}\n{item['start']:%m/%d %H:%M} · {course['room'] or '未填写地点'}\n距离上课还有 {remaining}"


class ReminderScheduler:
    def __init__(self, store, sender, prepare=None):
        self.store = store
        self.sender = sender
        self.prepare = prepare

    def check(self, now):
        if now.tzinfo is None:
            raise ValueError('提醒调度必须使用带时区的时间。')
        options = self.store.reminder_options()
        semester = self.store.semester()
        if not options['enabled'] or semester is None:
            return []
        current = now.astimezone(UTC)
        courses = [c for c in self.store.all() if c['reminder_enabled']]
        due = []
        # 1–1440 分钟提前量可跨日；昨天的已开始课程仅记录跳过。
        for delta in (-1,0,1):
            for item in zoned_occurrences(courses, now.date() + timedelta(days=delta), semester, now.tzinfo):
                lead = item['course']['reminder_minutes'] or options['minutes']
                start = item['start'].astimezone(UTC)
                planned = start - timedelta(minutes=lead)
                if planned > current:
                    continue
                key = event_key(item)
                late = current - planned
                # 补发：延迟不超过 5 分钟，或尚未开始且 5 分钟内开课。
                eligible = current < start and (late <= timedelta(minutes=5) or start-current <= timedelta(minutes=5))
                if not eligible:
                    self.store.claim_event(key, current, 'skipped')
                elif not self.store.has_event(key):
                    due.append(item)
        if not due:
            return []
        # 初始化/权限错误发生在持久化领取之前，下轮可安全重新尝试。
        if self.prepare:
            self.prepare()
        due = [item for item in due if self.store.claim_event(event_key(item), current)]
        if not due:
            return []
        due.sort(key=lambda item: item['start'].astimezone(UTC))
        keys = [event_key(item) for item in due]
        # 同一轮多个提醒合并为一个系统通知，避免唤醒后刷屏。
        try:
            self.sender(due, now, keys)
        except Exception as error:
            self.store.finish_events(keys,'failed',current,str(error))
            raise
        self.store.finish_events(keys,'submitted',current)
        return keys
