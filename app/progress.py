"""体重・ランニング記録を日付ページから集計するヘルパー。"""

import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone


DATE_TITLE_RE = re.compile(r'^(\d{4})年(\d{1,2})月(\d{1,2})日$')
RUNNING_RE = re.compile(r'(?:朝|夜)?ラン(?:ニング)?|running?', re.IGNORECASE)
DISTANCE_RE = re.compile(r'(?<![\d.])(\d+(?:\.\d+)?)\s*(?:km|キロ(?:メートル)?)', re.IGNORECASE)
LABELED_DISTANCE_RE = re.compile(
    r'(?:距離|distance)\s*[:：]?\s*(\d+(?:\.\d+)?)\s*(?:km|キロ(?:メートル)?)',
    re.IGNORECASE,
)


def _normalize_text(value):
    return unicodedata.normalize('NFKC', str(value or '')).strip()


def _date_from_title(title):
    match = DATE_TITLE_RE.match(_normalize_text(title))
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _running_distances(value):
    text = _normalize_text(value)
    if not RUNNING_RE.search(text):
        return []
    # RunTrack の投稿には「距離: 5.5km」の後にラップの
    # 「1km / 2km ...」が並ぶため、それらを走行距離として加算しない。
    labeled = LABELED_DISTANCE_RE.search(text)
    if labeled:
        return [float(labeled.group(1))]
    fallback = DISTANCE_RE.search(text)
    return [float(fallback.group(1))] if fallback else []


def _round(value, digits=1):
    return round(float(value), digits)


def _percent_change(current, previous):
    if previous <= 0:
        return None
    return _round(((current - previous) / previous) * 100)


def _streaks(run_dates, today):
    dates = sorted(set(run_dates))
    if not dates:
        return 0, 0

    best = 1
    current_sequence = 1
    for previous, current in zip(dates, dates[1:]):
        if current == previous + timedelta(days=1):
            current_sequence += 1
            best = max(best, current_sequence)
        else:
            current_sequence = 1

    latest = dates[-1]
    active = current_sequence if latest >= today - timedelta(days=1) else 0
    return active, best


def build_progress_summary(conn, period_days=30, today=None):
    """既存の pages / blocks から成長ダッシュボード用データを作る。"""
    today = today or date.today()
    period_days = period_days if period_days in (30, 90, 365) else 30
    current_start = today - timedelta(days=period_days - 1)
    previous_start = current_start - timedelta(days=period_days)
    previous_end = current_start - timedelta(days=1)

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, title, parent_id, weight
        FROM pages
        WHERE COALESCE(is_deleted, 0) = 0
        """
    )
    pages = [dict(row) for row in cursor.fetchall()]
    page_by_id = {page['id']: page for page in pages}

    date_cache = {}

    def date_for_page(page_id):
        if page_id in date_cache:
            return date_cache[page_id]
        visited = set()
        current_id = page_id
        resolved = None
        while current_id and current_id not in visited:
            visited.add(current_id)
            page = page_by_id.get(current_id)
            if not page:
                break
            resolved = _date_from_title(page.get('title'))
            if resolved:
                break
            current_id = page.get('parent_id')
        for visited_id in visited:
            date_cache[visited_id] = resolved
        return resolved

    weight_by_date = {}
    structured_run_sources = defaultdict(set)
    fallback_run_sources = defaultdict(set)
    structured_running_by_date = defaultdict(float)
    fallback_running_by_date = defaultdict(float)

    def collect_running(page_date, value):
        distances = _running_distances(value)
        if not distances:
            return
        normalized = _normalize_text(value).casefold()
        is_structured = bool(LABELED_DISTANCE_RE.search(normalized))
        sources = structured_run_sources if is_structured else fallback_run_sources
        totals = structured_running_by_date if is_structured else fallback_running_by_date
        source_key = (normalized, tuple(distances))
        if source_key not in sources[page_date]:
            totals[page_date] += sum(distances)
            sources[page_date].add(source_key)

    for page in pages:
        page_date = date_for_page(page['id'])
        if not page_date:
            continue

        if _date_from_title(page.get('title')) == page_date and page.get('weight') is not None:
            try:
                weight_by_date[page_date] = float(page['weight'])
            except (TypeError, ValueError):
                pass

        collect_running(page_date, page.get('title'))

    cursor.execute(
        """
        SELECT page_id, content
        FROM blocks
        WHERE COALESCE(content, '') != ''
        """
    )
    for row in cursor.fetchall():
        page_date = date_for_page(row['page_id'])
        if not page_date:
            continue
        collect_running(page_date, row['content'])

    # RunTrack のような「距離: 5.5km」がある日は、その構造化記録を正とする。
    # 日記本文に書かれた予定距離などとの二重加算を防ぐ。
    running_by_date = dict(fallback_running_by_date)
    running_by_date.update(structured_running_by_date)

    current_weights = [
        {'date': point_date.isoformat(), 'value': _round(value)}
        for point_date, value in sorted(weight_by_date.items())
        if current_start <= point_date <= today
    ]
    all_weights = [
        {'date': point_date.isoformat(), 'value': _round(value)}
        for point_date, value in sorted(weight_by_date.items())
        if previous_start <= point_date <= today
    ]

    current_runs = {
        point_date: distance
        for point_date, distance in running_by_date.items()
        if current_start <= point_date <= today and distance > 0
    }
    previous_runs = {
        point_date: distance
        for point_date, distance in running_by_date.items()
        if previous_start <= point_date <= previous_end and distance > 0
    }
    run_points = [
        {'date': point_date.isoformat(), 'distance': _round(distance)}
        for point_date, distance in sorted(current_runs.items())
    ]

    current_total = sum(current_runs.values())
    previous_total = sum(previous_runs.values())
    active_streak, best_streak = _streaks(current_runs.keys(), today)

    historic_weights = [
        (point_date, value)
        for point_date, value in weight_by_date.items()
        if point_date <= today
    ]
    latest_weight = _round(max(historic_weights)[1]) if historic_weights else None
    weight_change = None
    if len(current_weights) >= 2:
        weight_change = _round(current_weights[-1]['value'] - current_weights[0]['value'])
    elif current_weights and len(all_weights) >= 2:
        weight_change = _round(current_weights[-1]['value'] - all_weights[0]['value'])

    return {
        'period_days': period_days,
        'range': {
            'from': current_start.isoformat(),
            'to': today.isoformat(),
        },
        'weight': {
            'latest': latest_weight,
            'change': weight_change,
            'points': current_weights,
            'context_points': all_weights,
        },
        'running': {
            'total_distance': _round(current_total),
            'previous_total_distance': _round(previous_total),
            'change_percent': _percent_change(current_total, previous_total),
            'run_count': len(current_runs),
            'average_distance': _round(current_total / len(current_runs)) if current_runs else 0,
            'active_streak': active_streak,
            'best_streak': best_streak,
            'points': run_points,
        },
        'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }
