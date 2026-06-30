import sqlite3
import unittest
from datetime import date

from app.progress import build_progress_summary


class ProgressSummaryTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE pages (
                id INTEGER PRIMARY KEY,
                title TEXT,
                parent_id INTEGER,
                weight REAL,
                is_deleted INTEGER DEFAULT 0
            );
            CREATE TABLE blocks (
                id INTEGER PRIMARY KEY,
                page_id INTEGER,
                content TEXT
            );
            """
        )

    def tearDown(self):
        self.conn.close()

    def test_collects_weight_and_nested_running_pages(self):
        self.conn.executemany(
            'INSERT INTO pages (id, title, parent_id, weight) VALUES (?, ?, ?, ?)',
            [
                (1, '2026年6月1日', None, 70.0),
                (2, '朝ラン 5.5km', 1, None),
                (3, '2026年6月15日', None, 68.5),
                (4, '朝ラン ６．０ｋｍ', 3, None),
            ],
        )
        result = build_progress_summary(self.conn, 30, today=date(2026, 6, 30))

        self.assertEqual(result['weight']['latest'], 68.5)
        self.assertEqual(result['weight']['change'], -1.5)
        self.assertEqual(result['running']['total_distance'], 11.5)
        self.assertEqual(result['running']['run_count'], 2)

    def test_collects_running_blocks_and_deduplicates_same_day(self):
        self.conn.executemany(
            'INSERT INTO pages (id, title, parent_id, weight) VALUES (?, ?, ?, ?)',
            [
                (1, '2026年6月29日', None, None),
                (2, '日記', 1, None),
            ],
        )
        self.conn.executemany(
            'INSERT INTO blocks (id, page_id, content) VALUES (?, ?, ?)',
            [
                (1, 1, '🏃 ランニング記録 朝ラン 7km'),
                (2, 2, '🏃 ランニング記録 朝ラン 7km'),
            ],
        )
        result = build_progress_summary(self.conn, 30, today=date(2026, 6, 30))

        self.assertEqual(result['running']['total_distance'], 7.0)
        self.assertEqual(result['running']['run_count'], 1)

    def test_ignores_lap_markers_in_runtrack_post(self):
        self.conn.executemany(
            'INSERT INTO pages (id, title, parent_id, weight) VALUES (?, ?, ?, ?)',
            [
                (1, '2026年6月29日', None, None),
                (2, '日記', 1, None),
            ],
        )
        self.conn.execute(
            'INSERT INTO blocks (id, page_id, content) VALUES (?, ?, ?)',
            (
                1,
                2,
                """🏃 ランニング記録
                📏 距離 : 5.51 km
                🏃 平均ペース: 6'10"/km
                📍 ラップ 1km: 6'13"/km 2km: 6'26"/km""",
            ),
        )

        result = build_progress_summary(self.conn, 30, today=date(2026, 6, 30))

        self.assertEqual(result['running']['total_distance'], 5.5)
        self.assertEqual(result['running']['average_distance'], 5.5)

    def test_prefers_structured_runtrack_distance_over_diary_prose(self):
        self.conn.executemany(
            'INSERT INTO pages (id, title, parent_id, weight) VALUES (?, ?, ?, ?)',
            [
                (1, '2026年6月29日', None, None),
                (2, '日記', 1, None),
            ],
        )
        self.conn.executemany(
            'INSERT INTO blocks (id, page_id, content) VALUES (?, ?, ?)',
            [
                (1, 2, '今日はランニング。予定は5kmだったが6.5km走った。'),
                (2, 2, '🏃 ランニング記録 📏 距離: 6.48 km'),
            ],
        )

        result = build_progress_summary(self.conn, 30, today=date(2026, 6, 30))

        self.assertEqual(result['running']['total_distance'], 6.5)
        self.assertEqual(result['running']['run_count'], 1)

    def test_compares_with_previous_period(self):
        self.conn.executemany(
            'INSERT INTO pages (id, title, parent_id, weight) VALUES (?, ?, ?, ?)',
            [
                (1, '2026年5月20日', None, None),
                (2, '朝ラン 5km', 1, None),
                (3, '2026年6月20日', None, None),
                (4, '朝ラン 10km', 3, None),
            ],
        )
        result = build_progress_summary(self.conn, 30, today=date(2026, 6, 30))

        self.assertEqual(result['running']['previous_total_distance'], 5.0)
        self.assertEqual(result['running']['change_percent'], 100.0)


if __name__ == '__main__':
    unittest.main()
