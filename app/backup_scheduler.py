#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自動バックアップスケジューラー
- 定期的にバックアップを実行
- 古いバックアップを削除
- バックアップの管理
"""

import sqlite3
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
import threading

class BackupScheduler:
    """自動バックアップスケジューラー"""
    
    def __init__(self, db_path, backup_dir, interval_seconds=300, max_backups=100):
        self.db_path = db_path
        self.backup_dir = Path(backup_dir)
        self.interval_seconds = interval_seconds  # デフォルト5分
        self.max_backups = max_backups
        self.last_backup_time = time.time()
        self.thread = None
        self.running = False
    
    def backup_database(self):
        """データベースをJSONテキスト形式でバックアップ"""
        try:
            if not os.path.exists(self.db_path):
                print(f"❌ Database not found: {self.db_path}")
                return False
            
            self.backup_dir.mkdir(exist_ok=True)
            
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # テーブル一覧取得（FTSテーブルを除外）
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' 
                AND name NOT LIKE 'sqlite_%'
                AND name NOT LIKE '%_fts%'
                AND name NOT LIKE '%_config'
                ORDER BY name
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            # バックアップデータ
            backup_data = {
                'timestamp': datetime.now().isoformat(),
                'database': 'notion.db',
                'tables': {}
            }
            
            # 各テーブルをエクスポート
            for table in tables:
                cursor.execute(f'SELECT * FROM {table}')
                rows = cursor.fetchall()
                backup_data['tables'][table] = [dict(row) for row in rows]
            
            conn.close()
            
            # JSONファイルに保存
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = self.backup_dir / f'backup_{timestamp}.json'
            
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            # 最新のバックアップを latest.json にコピー
            latest_file = self.backup_dir / 'latest.json'
            with open(latest_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            # 古いバックアップを削除
            self._cleanup_old_backups()
            
            print(f"✅ Backup created: {backup_file.name} ({self._format_size(backup_file.stat().st_size)})")
            return True
            
        except Exception as e:
            print(f"❌ Backup failed: {e}")
            return False
    
    def _cleanup_old_backups(self):
        """古いバックアップを削除（最新N個を保持）"""
        try:
            backup_files = sorted(self.backup_dir.glob('backup_*.json'), reverse=True)
            
            # 最新ファイルより古いものを削除
            for old_backup in backup_files[self.max_backups:]:
                if old_backup.name != 'latest.json':
                    old_backup.unlink()
                    print(f"  🗑️ Deleted old backup: {old_backup.name}")
        except Exception as e:
            print(f"⚠️ Cleanup failed: {e}")
    
    def _format_size(self, size_bytes):
        """バイト数をKBやMBの単位に変換"""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f}MB"
    
    def should_backup(self):
        """バックアップを実行すべきかチェック"""
        current_time = time.time()
        return current_time - self.last_backup_time > self.interval_seconds
    
    def backup_if_needed(self):
        """必要に応じてバックアップを実行"""
        if self.should_backup():
            success = self.backup_database()
            if success:
                self.last_backup_time = time.time()
            return success
        return False
    
    def start_background_backup(self):
        """バックアップスレッドを開始"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._background_backup_loop, daemon=True)
            self.thread.start()
            # ログは出力しない（重複出力を避けるため）
    
    def _background_backup_loop(self):
        """バックアップ実行ループ"""
        while self.running:
            try:
                self.backup_if_needed()
                time.sleep(10)  # 10秒ごとにチェック
            except Exception as e:
                print(f"⚠️ Background backup error: {e}")
    
    def stop_background_backup(self):
        """バックアップスレッドを停止"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        # ログは出力しない（シャットダウン時のノイズを避けるため）


# グローバルバックアップスケジューラーインスタンス
_backup_scheduler = None

def init_backup_scheduler(app):
    """Flaskアプリにバックアップスケジューラーを初期化"""
    global _backup_scheduler
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'notion.db')
    backup_dir = os.path.join(base_dir, 'backups')
    
    # 300秒（5分）ごとにバックアップ、最新100個を保持
    _backup_scheduler = BackupScheduler(
        db_path=db_path,
        backup_dir=backup_dir,
        interval_seconds=300,
        max_backups=100
    )
    
    # バックアップスレッドを開始
    _backup_scheduler.start_background_backup()
    
    # アプリシャットダウン時にスケジューラを停止
    def shutdown():
        _backup_scheduler.stop_background_backup()
    
    app.teardown_appcontext(lambda exc: shutdown())

def trigger_backup():
    """手動でバックアップをトリガー"""
    global _backup_scheduler
    if _backup_scheduler:
        return _backup_scheduler.backup_database()
    return False
