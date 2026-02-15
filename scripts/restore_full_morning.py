#!/usr/bin/env python3
import json
import sqlite3
import os
import shutil
from datetime import datetime
import sys

# kiroku-journal に移動
project_root = '/Users/nishiharakeita/kiroku-journal'
os.chdir(project_root)

backup_file = os.path.join(project_root, 'backups/backup_20260215_131148.json')
db_file = os.path.join(project_root, 'notion.db')

print(f"📋 最新バックアップから復元: {backup_file}")
with open(backup_file, 'r', encoding='utf-8') as f:
    backup_data = json.load(f)

# Old DB をバックアップ
if os.path.exists(db_file):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_file}.backup_before_morning_restore_{ts}"
    shutil.copy2(db_file, backup_path)
    print(f"💾 Old DB backed up: {backup_path}")

# DB を削除
if os.path.exists(db_file):
    os.remove(db_file)
    print(f"🗑️  Old DB removed")

# スキーマ初期化
print(f"🔄 Initializing database schema...")
sys.path.insert(0, os.path.join(project_root, 'app'))
from database import init_db
init_db()
print(f"✅ Schema created")

# データ復元
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

print(f"📥 Restoring data from morning backup...")
for table_name in ['pages', 'blocks', 'templates', 'users', 'password_reset_tokens', 'healthplanet_tokens']:
    records = backup_data.get('tables', {}).get(table_name, [])
    
    if not records:
        print(f"  • {table_name}: 0 rows")
        continue
    
    # 有効なカラムを取得
    cursor.execute(f"PRAGMA table_info({table_name})")
    current_columns = {row[1] for row in cursor.fetchall()}
    
    first_record = records[0]
    valid_columns = [col for col in first_record.keys() if col in current_columns]
    
    if not valid_columns:
        print(f"  • {table_name}: no matching columns")
        continue
    
    # データクリア
    cursor.execute(f"DELETE FROM {table_name}")
    
    # データ挿入
    columns_str = ', '.join(valid_columns)
    placeholders = ', '.join(['?'] * len(valid_columns))
    insert_sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
    
    values_list = [tuple(record.get(col) for col in valid_columns) for record in records]
    cursor.executemany(insert_sql, values_list)
    
    print(f"  • {table_name}: {len(records)} rows ✅")

conn.commit()
conn.close()

# 確認
conn = sqlite3.connect(db_file)
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM pages')
pages = cursor.fetchone()[0]
cursor.execute('SELECT COUNT(*) FROM blocks')
blocks = cursor.fetchone()[0]
conn.close()

print(f"\n✅ Complete restoration!")
print(f"  Pages: {pages}")
print(f"  Blocks: {blocks}")
