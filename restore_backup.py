#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ローカルデータベースを復元
"""

import shutil
import os
from datetime import datetime

base = '/Users/nishiharakeita/kiroku-journal'
db_file = os.path.join(base, 'notion.db')
backup_file = os.path.join(base, 'notion.db.backup_before_morning_restore_20260215_132529')

print("\n⚠️  データベース復元ツール")
print("=" * 60)

# バックアップファイルが存在するか確認
if not os.path.exists(backup_file):
    print(f"❌ バックアップファイルが見つかりません:")
    print(f"   {backup_file}")
    exit(1)

backup_size = os.path.getsize(backup_file) / (1024 * 1024)
print(f"\n✅ バックアップファイル: {backup_file}")
print(f"   サイズ: {backup_size:.2f} MB")

# 現在のDB を確認
if os.path.exists(db_file):
    current_size = os.path.getsize(db_file) / (1024 * 1024)
    print(f"\n現在のデータベース: {db_file}")
    print(f"   サイズ: {current_size:.2f} MB")
    
    # 現在のDBをセーフティバックアップ
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_backup = os.path.join(base, f'backups/emergency_backup_{timestamp}_notion.db')
    os.makedirs(os.path.dirname(safe_backup), exist_ok=True)
    shutil.copy(db_file, safe_backup)
    print(f"   セーフティバックアップ: {safe_backup}")
else:
    print(f"\n現在のデータベース: 存在しません")

# 復元
print(f"\n🔄 復元中...")
shutil.copy(backup_file, db_file)
print(f"✅ 復元完了！")
print(f"\n📝 実施内容:")
print(f"   ✓ 現在のDB をセーフティバックアップ保存")
print(f"   ✓ バックアップから復元")
print(f"\nローカルFlaskアプリを再起動してください:")
print(f"   cd /Users/nishiharakeita/kiroku-journal")
print(f"   python3 run.py")
print("\n" + "=" * 60)
