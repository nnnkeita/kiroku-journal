#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
毎日自動バックアップスクリプト
launchd から毎日00:00に実行される
"""

import sqlite3
import json
import os
import sys
from datetime import datetime
from pathlib import Path

def backup_database():
    """データベースをJSONテキスト形式でバックアップ"""
    
    # パス設定
    base_dir = Path(__file__).parent
    db_path = base_dir / 'notion.db'
    backup_dir = base_dir / 'backups'
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    # バックアップディレクトリ作成
    backup_dir.mkdir(exist_ok=True)
    
    try:
        # データベース接続
        conn = sqlite3.connect(str(db_path))
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
        backup_file = backup_dir / f'backup_{timestamp}.json'
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        # ファイルサイズ
        file_size = backup_file.stat().st_size / 1024
        
        # 最新のバックアップを latest.json にコピー
        latest_file = backup_dir / 'latest.json'
        with open(latest_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        # ログ出力（launchd経由で実行されるため、ログファイルに記録）
        log_file = base_dir / 'backups' / 'daily_backup.log'
        with open(log_file, 'a', encoding='utf-8') as log:
            log.write(f"[{datetime.now().isoformat()}] ✅ Backup created: {backup_file.name} ({file_size:.1f}KB)\n")
        
        # 古いバックアップを削除（最新30個を保持）
        cleanup_old_backups(backup_dir, max_backups=30)
        
        print(f"✅ Backup created: {backup_file.name}")
        return True
        
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        # エラーログも記録
        log_file = base_dir / 'backups' / 'daily_backup.log'
        with open(log_file, 'a', encoding='utf-8') as log:
            log.write(f"[{datetime.now().isoformat()}] ❌ Backup failed: {e}\n")
        return False

def cleanup_old_backups(backup_dir, max_backups=30):
    """古いバックアップを削除（最新N個を保持）"""
    try:
        backup_files = sorted(backup_dir.glob('backup_*.json'), reverse=True)
        
        # 最新ファイルより古いものを削除
        for old_backup in backup_files[max_backups:]:
            old_backup.unlink()
            log_file = backup_dir / 'daily_backup.log'
            with open(log_file, 'a', encoding='utf-8') as log:
                log.write(f"[{datetime.now().isoformat()}]   🗑️ Deleted old backup: {old_backup.name}\n")
    except Exception as e:
        print(f"⚠️ Cleanup failed: {e}")

if __name__ == '__main__':
    success = backup_database()
    sys.exit(0 if success else 1)
