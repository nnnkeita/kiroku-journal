# -*- coding: utf-8 -*-
"""
データベース関連の処理
- DB接続
- テーブル初期化
- 基本的なヘルパー関数
"""
import sqlite3
import os
import json
from typing import Optional

# パス設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)  # kiroku-journal フォルダ

# === 環境判定（ローカルとPythonAnywhereの分離） ===
IS_PYTHONANYWHERE = 'PYTHONANYWHERE_DOMAIN' in os.environ
IS_LOCAL = not IS_PYTHONANYWHERE

# データベースパスを環境で分ける
if IS_PYTHONANYWHERE:
    # PythonAnywhere用：ホームディレクトリ配下に保存
    HOME_DIR = os.path.expanduser('~')
    DATABASE = os.path.join(HOME_DIR, 'kiroku_db', 'notion.db')
else:
    # ローカル開発用：プロジェクト内に保存
    DATABASE = os.path.join(PROJECT_ROOT, 'notion.db')

# PythonAnywhere用データベースディレクトリ作成
if IS_PYTHONANYWHERE:
    db_dir = os.path.dirname(DATABASE)
    os.makedirs(db_dir, exist_ok=True)

def set_database_path(new_path):
    """※管理者用※ データベースパスを上書き（通常は使用しません）
    
    PythonAnywhere でカスタムパスを指定したい場合のみ使用
    app.py的な起動スクリプトの app.app_context() 前に呼び出してください
    """
    global DATABASE
    DATABASE = new_path
    db_dir = os.path.dirname(DATABASE)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

def get_db():
    """データベース接続を取得"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """データベーステーブルを初期化"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT DEFAULT '',
        icon TEXT DEFAULT '📄',
        cover_image TEXT DEFAULT '', 
        parent_id INTEGER,
        position REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (parent_id) REFERENCES pages(id) ON DELETE CASCADE
    )
    ''')
    try:
        cursor.execute("ALTER TABLE pages ADD COLUMN cover_image TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    
    # 新機能用カラム追加
    try:
        cursor.execute("ALTER TABLE pages ADD COLUMN is_pinned BOOLEAN DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE pages ADD COLUMN is_deleted BOOLEAN DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    
    # ブロック用の折りたたみカラム
    try:
        cursor.execute("ALTER TABLE blocks ADD COLUMN collapsed BOOLEAN DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    
    # トグルブロック用の詳細内容カラム
    try:
        cursor.execute("ALTER TABLE blocks ADD COLUMN details TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    
    # position を REAL に変更（既存インデックスの衝突を防ぐ）
    try:
        cursor.execute("ALTER TABLE pages ADD COLUMN position_new REAL DEFAULT 0.0")
        cursor.execute("UPDATE pages SET position_new = CAST(position AS REAL) * 1000.0")
        cursor.execute("ALTER TABLE pages DROP COLUMN position")
        cursor.execute("ALTER TABLE pages RENAME COLUMN position_new TO position")
    except sqlite3.OperationalError:
        pass
    
    # props JSON カラムをブロックに追加
    try:
        cursor.execute("ALTER TABLE blocks ADD COLUMN props TEXT DEFAULT '{}'")
    except sqlite3.OperationalError:
        pass
    
    # ムード（感情）カラムを追加
    try:
        cursor.execute("ALTER TABLE pages ADD COLUMN mood INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    
    # 感謝日記カラムを追加
    try:
        cursor.execute("ALTER TABLE pages ADD COLUMN gratitude_text TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS blocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        page_id INTEGER NOT NULL,
        type TEXT DEFAULT 'text',
        content TEXT DEFAULT '',
        checked BOOLEAN DEFAULT 0,
        position REAL DEFAULT 0.0,
        collapsed BOOLEAN DEFAULT 0,
        details TEXT DEFAULT '',
        props TEXT DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (page_id) REFERENCES pages(id) ON DELETE CASCADE
    )
    ''')
    cursor.execute('CREATE VIRTUAL TABLE IF NOT EXISTS blocks_fts USING fts5(title, content, content=blocks, content_rowid=id)')
    cursor.execute('CREATE TRIGGER IF NOT EXISTS blocks_ai AFTER INSERT ON blocks BEGIN INSERT INTO blocks_fts(rowid, title, content) VALUES (new.id, (SELECT title FROM pages WHERE id = new.page_id), new.content); END;')
    cursor.execute('CREATE TRIGGER IF NOT EXISTS blocks_ad AFTER DELETE ON blocks BEGIN INSERT INTO blocks_fts(blocks_fts, rowid, title, content) VALUES("delete", old.id, (SELECT title FROM pages WHERE id = old.page_id), old.content); END;')
    cursor.execute('CREATE TRIGGER IF NOT EXISTS blocks_au AFTER UPDATE ON blocks BEGIN INSERT INTO blocks_fts(blocks_fts, rowid, title, content) VALUES("delete", old.id, (SELECT title FROM pages WHERE id = old.page_id), old.content); INSERT INTO blocks_fts(rowid, title, content) VALUES (new.id, (SELECT title FROM pages WHERE id = new.page_id), new.content); END;')
    
    # パフォーマンス改善用インデックス
    try:
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pages_parent_position ON pages(parent_id, position, is_deleted)')
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pages_is_deleted ON pages(is_deleted)')
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_blocks_page_position ON blocks(page_id, position)')
    except sqlite3.OperationalError:
        pass
    
    # テンプレート用テーブル
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        icon TEXT DEFAULT '📋',
        description TEXT DEFAULT '',
        content_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # ユーザー認証用テーブル
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 課金情報カラム追加
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN stripe_customer_id TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN subscription_status TEXT DEFAULT 'inactive'")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN subscription_ends_at TIMESTAMP")
    except sqlite3.OperationalError:
        pass

    # パスワード再設定トークン
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS password_reset_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token TEXT NOT NULL UNIQUE,
        expires_at TIMESTAMP NOT NULL,
        used BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')

    # HealthPlanetトークン
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS healthplanet_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        access_token TEXT NOT NULL,
        refresh_token TEXT,
        expires_at TIMESTAMP,
        scope TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # デフォルトテンプレートを初期化
    try:
        cursor.execute('SELECT COUNT(*) FROM templates')
        if cursor.fetchone()[0] == 0:
            # 感謝日記テンプレート
            gratitude_template = {
                'title': '感謝日記',
                'blocks': [
                    {'type': 'h1', 'content': '感謝日記', 'position': 1000},
                    {'type': 'text', 'content': '今日感謝したことを3つ書きましょう。', 'position': 2000},
                    {'type': 'text', 'content': '1. ', 'position': 3000},
                    {'type': 'text', 'content': '2. ', 'position': 4000},
                    {'type': 'text', 'content': '3. ', 'position': 5000},
                ]
            }
            
            # PDCA日報テンプレート
            pdca_template = {
                'title': 'PDCA日報',
                'blocks': [
                    {'type': 'h1', 'content': 'PDCA日報', 'position': 1000},
                    {'type': 'h2', 'content': '計画（Plan）', 'position': 2000},
                    {'type': 'text', 'content': '', 'position': 3000},
                    {'type': 'h2', 'content': '実行（Do）', 'position': 4000},
                    {'type': 'text', 'content': '', 'position': 5000},
                    {'type': 'h2', 'content': '確認（Check）', 'position': 6000},
                    {'type': 'text', 'content': '', 'position': 7000},
                    {'type': 'h2', 'content': '改善（Act）', 'position': 8000},
                    {'type': 'text', 'content': '', 'position': 9000},
                ]
            }
            
            # 5行日記テンプレート
            five_line_template = {
                'title': '5行日記',
                'blocks': [
                    {'type': 'h1', 'content': '5行日記', 'position': 1000},
                    {'type': 'text', 'content': '1. 今日起きたこと：', 'position': 2000},
                    {'type': 'text', 'content': '2. その時の気持ち：', 'position': 3000},
                    {'type': 'text', 'content': '3. その出来事の意味：', 'position': 4000},
                    {'type': 'text', 'content': '4. その経験から学んだこと：', 'position': 5000},
                    {'type': 'text', 'content': '5. 明日への決意：', 'position': 6000},
                ]
            }
            
            templates_data = [
                ('感謝日記', '🙏', '毎日の感謝を記録するテンプレート', gratitude_template),
                ('PDCA日報', '📊', 'Plan-Do-Check-Actフレームワーク', pdca_template),
                ('5行日記', '📖', '1日の出来事を5行で整理するテンプレート', five_line_template),
            ]
            
            for name, icon, desc, content in templates_data:
                cursor.execute(
                    'INSERT INTO templates (name, icon, description, content_json) VALUES (?, ?, ?, ?)',
                    (name, icon, desc, json.dumps(content, ensure_ascii=False))
                )
            
            conn.commit()
    except Exception as e:
        pass
    
    conn.commit()
    conn.close()

def get_healthplanet_token() -> Optional[sqlite3.Row]:
    """HealthPlanetのトークンを取得"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM healthplanet_tokens ORDER BY id DESC LIMIT 1')
    row = cursor.fetchone()
    conn.close()
    return row

def save_healthplanet_token(access_token: str, refresh_token: Optional[str] = None,
                            expires_at: Optional[str] = None, scope: Optional[str] = None) -> None:
    """HealthPlanetのトークンを保存（最新1件のみ保持）"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM healthplanet_tokens')
    cursor.execute(
        'INSERT INTO healthplanet_tokens (access_token, refresh_token, expires_at, scope) VALUES (?, ?, ?, ?)',
        (access_token, refresh_token, expires_at, scope)
    )
    conn.commit()
    conn.close()

def clear_healthplanet_token() -> None:
    """HealthPlanetのトークンを削除"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM healthplanet_tokens')
    conn.commit()
    conn.close()

def get_user_count() -> int:
    """登録ユーザー数を取得"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    count = cursor.fetchone()[0]
    conn.close()
    return int(count or 0)

def get_user_by_username(username: str) -> Optional[sqlite3.Row]:
    """ユーザー名でユーザー取得"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    row = cursor.fetchone()
    conn.close()
    return row

def get_user_by_id(user_id: int) -> Optional[sqlite3.Row]:
    """ユーザーIDでユーザー取得"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def create_user(username: str, password_hash: str) -> int:
    """ユーザー作成"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO users (username, password_hash) VALUES (?, ?)',
        (username, password_hash)
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return int(user_id)

def update_user_password(user_id: int, password_hash: str) -> None:
    """パスワード更新"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, user_id))
    conn.commit()
    conn.close()

def set_password_reset_token(user_id: int, token: str, expires_at: str) -> None:
    """パスワード再設定トークン登録"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (?, ?, ?)',
        (user_id, token, expires_at)
    )
    conn.commit()
    conn.close()

def get_password_reset_token(token: str) -> Optional[sqlite3.Row]:
    """トークン取得"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM password_reset_tokens WHERE token = ?', (token,))
    row = cursor.fetchone()
    conn.close()
    return row

def mark_password_reset_token_used(token: str) -> None:
    """トークン使用済み"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE password_reset_tokens SET used = 1 WHERE token = ?', (token,))
    conn.commit()
    conn.close()

def update_user_stripe_customer(user_id: int, customer_id: str) -> None:
    """Stripe顧客ID更新"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET stripe_customer_id = ? WHERE id = ?', (customer_id, user_id))
    conn.commit()
    conn.close()

def get_user_by_stripe_customer(customer_id: str) -> Optional[sqlite3.Row]:
    """Stripe顧客IDでユーザー取得"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE stripe_customer_id = ?', (customer_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_user_subscription(user_id: int, status: str, ends_at: Optional[str] = None) -> None:
    """サブスク状態更新"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE users SET subscription_status = ?, subscription_ends_at = ? WHERE id = ?',
        (status, ends_at, user_id)
    )
    conn.commit()
    conn.close()

def get_next_position(cursor, parent_id):
    """次のposition値を計算（1000刻み方式）"""
    if parent_id:
        cursor.execute('SELECT MAX(position) FROM pages WHERE parent_id = ?', (parent_id,))
    else:
        cursor.execute('SELECT MAX(position) FROM pages WHERE parent_id IS NULL')
    max_pos = cursor.fetchone()[0]
    if max_pos is None:
        return 1000.0
    return max_pos + 1000.0

def get_block_next_position(cursor, page_id):
    """ブロックの次のposition値を計算"""
    cursor.execute('SELECT MAX(position) FROM blocks WHERE page_id = ?', (page_id,))
    max_pos = cursor.fetchone()[0]
    if max_pos is None:
        return 1000.0
    return max_pos + 1000.0

def mark_tree_deleted(cursor, page_id, is_deleted=True):
    """ページとその全子ページを再帰的に削除フラグ変更（soft delete）"""
    cursor.execute('UPDATE pages SET is_deleted = ? WHERE id = ?', (1 if is_deleted else 0, page_id))
    cursor.execute('SELECT id FROM pages WHERE parent_id = ?', (page_id,))
    for row in cursor.fetchall():
        mark_tree_deleted(cursor, row['id'], is_deleted)

def hard_delete_tree(cursor, page_id):
    """ページとその全子ページを再帰的に完全削除（hard delete）"""
    cursor.execute('SELECT id FROM pages WHERE parent_id = ?', (page_id,))
    for row in cursor.fetchall():
        hard_delete_tree(cursor, row['id'])
    cursor.execute('DELETE FROM pages WHERE id = ?', (page_id,))

def get_or_create_inbox():
    """'あとで調べる'ページを取得、なければ作成"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM pages WHERE title = ? AND parent_id IS NULL LIMIT 1', ('🔖 あとで調べる',))
    inbox = cursor.fetchone()
    if not inbox:
        cursor.execute('SELECT MAX(position) FROM pages WHERE parent_id IS NULL')
        max_pos = cursor.fetchone()[0]
        new_pos = (max_pos if max_pos is not None else -1) + 1
        cursor.execute('INSERT INTO pages (title, icon, parent_id, position) VALUES (?, ?, ?, ?)',
                       ('🔖 あとで調べる', '🔖', None, new_pos))
        inbox_id = cursor.lastrowid
        cursor.execute("INSERT INTO blocks (page_id, type, content, position) VALUES (?, 'text', '', ?)",
                       (inbox_id, 1000.0))
        conn.commit()
        cursor.execute('SELECT * FROM pages WHERE id = ?', (inbox_id,))
        inbox = cursor.fetchone()
    conn.close()
    return dict(inbox) if inbox else None

def get_or_create_knowledge_base():
    """'知識の宝庫'ページを取得、なければ作成"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM pages WHERE title = ? AND parent_id IS NULL LIMIT 1', ('📚 知識の宝庫',))
    knowledge = cursor.fetchone()
    if not knowledge:
        cursor.execute('SELECT MAX(position) FROM pages WHERE parent_id IS NULL')
        max_pos = cursor.fetchone()[0]
        new_pos = (max_pos if max_pos is not None else -1) + 1
        cursor.execute('INSERT INTO pages (title, icon, parent_id, position) VALUES (?, ?, ?, ?)',
                       ('📚 知識の宝庫', '📚', None, new_pos))
        knowledge_id = cursor.lastrowid
        cursor.execute("INSERT INTO blocks (page_id, type, content, position) VALUES (?, 'text', '', ?)",
                       (knowledge_id, 1000.0))
        conn.commit()
        cursor.execute('SELECT * FROM pages WHERE id = ?', (knowledge_id,))
        knowledge = cursor.fetchone()
    conn.close()
    return dict(knowledge) if knowledge else None

def get_or_create_finished():
    """'読了'ページを取得、なければ作成"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM pages WHERE title = ? AND parent_id IS NULL LIMIT 1', ('📚 読了',))
    finished = cursor.fetchone()
    if not finished:
        cursor.execute('SELECT MAX(position) FROM pages WHERE parent_id IS NULL')
        max_pos = cursor.fetchone()[0]
        new_pos = (max_pos if max_pos is not None else -1) + 1
        cursor.execute('INSERT INTO pages (title, icon, parent_id, position) VALUES (?, ?, ?, ?)',
                       ('📚 読了', '📚', None, new_pos))
        finished_id = cursor.lastrowid

        children = [
            {
                'title': '読了した本',
                'icon': '✅',
                'blocks': [
                    {'type': 'h1', 'content': '読了した本'},
                    {'type': 'text', 'content': ''},
                ]
            },
            {
                'title': '日々の感想',
                'icon': '📝',
                'blocks': [
                    {'type': 'h1', 'content': '日々の感想'},
                    {'type': 'text', 'content': ''},
                ]
            }
        ]

        for i, child in enumerate(children):
            cursor.execute('INSERT INTO pages (title, icon, parent_id, position) VALUES (?, ?, ?, ?)',
                           (child['title'], child['icon'], finished_id, (i + 1) * 1000.0))
            child_id = cursor.lastrowid
            for j, block in enumerate(child['blocks']):
                cursor.execute(
                    'INSERT INTO blocks (page_id, type, content, position) VALUES (?, ?, ?, ?)',
                    (child_id, block.get('type', 'text'), block.get('content', ''), (j + 1) * 1000.0)
                )

        conn.commit()
        cursor.execute('SELECT * FROM pages WHERE id = ?', (finished_id,))
        finished = cursor.fetchone()
    else:
        finished_id = finished['id']
        cursor.execute('SELECT title FROM pages WHERE parent_id = ? AND is_deleted = 0', (finished_id,))
        existing_titles = {row['title'] for row in cursor.fetchall()}

        children = [
            {
                'title': '読了した本',
                'icon': '✅',
                'blocks': [
                    {'type': 'h1', 'content': '読了した本'},
                    {'type': 'text', 'content': ''},
                ]
            },
            {
                'title': '日々の感想',
                'icon': '📝',
                'blocks': [
                    {'type': 'h1', 'content': '日々の感想'},
                    {'type': 'text', 'content': ''},
                ]
            }
        ]

        next_pos = get_next_position(cursor, finished_id)
        for child in children:
            if child['title'] in existing_titles:
                continue
            cursor.execute('INSERT INTO pages (title, icon, parent_id, position) VALUES (?, ?, ?, ?)',
                           (child['title'], child['icon'], finished_id, next_pos))
            child_id = cursor.lastrowid
            next_pos += 1000.0
            for j, block in enumerate(child['blocks']):
                cursor.execute(
                    'INSERT INTO blocks (page_id, type, content, position) VALUES (?, ?, ?, ?)',
                    (child_id, block.get('type', 'text'), block.get('content', ''), (j + 1) * 1000.0)
                )
        conn.commit()

    conn.close()
    return dict(finished) if finished else None
