"""教学周、课程实例和跨天时间计算（本地墙上时间）。"""
from datetime import date, datetime, timedelta


def teaching_week(day, semester):
    monday = semester - timedelta(days=semester.weekday())
    return (day - monday).days // 7 + 1


def active(slot, week):
    if not slot['first_week'] <= week <= slot['last_week']:
        return False
    specified = slot['weeks']
    if specified:
        return week in {int(w) for w in specified.split(',')}
    return slot['pattern'] == 'all' or (slot['pattern'] == 'odd' and week % 2 == 1) or (slot['pattern'] == 'even' and week % 2 == 0)


def occurrences(courses, day, semester):
    result = []
    for course in courses:
        for slot in course['slots']:
            if slot['weekday'] != day.weekday() or not active(slot, teaching_week(day, semester)):
                continue
            start = datetime.fromisoformat(f"{day}T{slot['start']}")
            end = datetime.fromisoformat(f"{day}T{slot['end']}")
            if end <= start:
                end += timedelta(days=1)
            result.append(dict(course=course, slot=slot, start=start, end=end))
    return sorted(result, key=lambda item: item['start'])


def day_items(courses, day, semester):
    # 今日包含前一天开始、今天尚未结束的跨夜课。
    previous = [o for o in occurrences(courses, day - timedelta(days=1), semester) if o['end'].date() == day and o['end'].time().isoformat() != '00:00:00']
    return previous + occurrences(courses, day, semester)


def remaining_today(courses, semester, now):
    """仅本日开始且尚未结束的课程；包含正在上的课。"""
    if semester is None:
        return []
    return [item for item in occurrences(courses,now.date(),semester) if item['end'] > now]


def status(item, now):
    if now >= item['end']:
        return '已结束'
    if now >= item['start']:
        return '正在上课'
    if item['start'] - now <= timedelta(minutes=15):
        return '即将开始'
    return '未开始'


def conflicts(candidate, courses, semester):
    """枚举有效教学周，检测自身与其他课程的跨夜重叠。"""
    monday = semester - timedelta(days=semester.weekday())
    others = [c for c in courses if c['id'] != candidate.get('id')]
    existing = []
    proposed = []
    for offset in range(54 * 7):
        day = monday + timedelta(days=offset)
        proposed.extend(occurrences([candidate], day, semester))
        existing.extend(occurrences(others, day, semester))
    names = set()
    for i, item in enumerate(proposed):
        for other in existing + proposed[:i]:
            if item['start'] < other['end'] and other['start'] < item['end']:
                names.add(other['course']['name'])
    return sorted(names)
