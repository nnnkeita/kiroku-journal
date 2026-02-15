#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ローカル Kiroku-Journal 診断スクリプト
"""

import sqlite3
import os
import sys

def diagnose():
    print("\n🔍 ローカルFlaskアプリ診断")
    print("=" * 60)
    
    # パス
    base_dir = "/Users/nishiharakeita/kiroku-journal"
    db_path = os.path.join(base_dir, "notion.db")
    app_path = os.path.join(base_dir, "app/flask_app.py")
    
    # 1. ディレクトリ確認
    print("\n1️⃣  ディレクトリ構造:")
    print(f"   プロジェクト: {base_dir}")
    print(f"   存在: {'✅' if os.path.isdir(base_dir) else '❌'}")
    print(f"   Flask: {app_path}")
    print(f"   存在: {'✅' if os.path.exists(app_path) else '❌'}")
    
    # 2. DB確認
    print(f"\n2️⃣  データベース:")
    print(f"   パス: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"   ❌ DBファイルが見つかりません")
        
        # バックアップの確認
        backup_files = [f for f in os.listdir(base_dir) if f.startswith('notion.db')]
        if backup_files:
            print(f"   ⚠️  見つかったファイル: {backup_files}")
        return False
    
    size_mb = os.path.getsize(db_path) / (1024 * 1024)
    print(f"   サイズ: {size_mb:.2f} MB ✅")
    
    # 3. DB接続テスト
    print(f"\n3️⃣  DB接続テスト:")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 整合性チェック
        cursor.execute("PRAGMA integrity_check")
        integrity = cursor.fetchone()[0]
        
        if integrity == 'ok':
            print(f"   整合性: ✅")
        else:
            print(f"   整合性: ⚠️  {integrity}")
        
        # テーブル一覧
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        table_names = [t[0] for t in tables]
        
        print(f"   テーブル数: {len(tables)}")
        print(f"   テーブル: {', '.join(table_names)}")
        
        # 4. 日記データ確認
        print(f"\n4️⃣  日記データ:")
        
        if 'entries' in table_names:
            cursor.execute("SELECT COUNT(*) FROM entries")
            entry_count = cursor.fetchone()[0]
            print(f"   エントリ数: {entry_count}")
            
            if entry_count > 0:
                print(f"   ✅ 日記データがあります")
                
                # 最新のエントリを確認
                cursor.execute("""
                    SELECT id, created_at, title 
                    FROM entries 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """)
                latest = cursor.fetchone()
                if latest:
                    entry_id, created_at, title = latest
                    print(f"   最新: {created_at} - {title[:50]}")
            else:
                print(f"   ❌ 日記データが空です")
        else:
            print(f"   ❌ entries テーブルがありません")
        
        # 5. ユーザーアカウント確認
        print(f"\n5️⃣  ユーザーアカウント:")
        
        if 'users' in table_names:
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            print(f"   ユーザー数: {user_count}")
            
            if user_count > 0:
                cursor.execute("SELECT id, username FROM users LIMIT 3")
                users = cursor.fetchall()
                for uid, username in users:
                    print(f"     - {username} (ID: {uid})")
        else:
            print(f"   ℹ️  users テーブルがありません")
        
        conn.close()
        
        print(f"\n✅ DB検査完了")
        return True
        
    except Exception as e:
        print(f"   ❌ DB接続エラー: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = diagnose()
    sys.exit(0 if success else 1)
