# -*- coding: utf-8 -*-
"""
PythonAnywhere 用 WSGI エントリーポイント

PythonAnywhere のコンソールから以下のようにWSGIファイルを設定してください：
- Web app configuration file: /home/<username>/kiroku-journal/wsgi.py

このファイルは PythonAnywhere の Web アプリが起動時に読み込みます。
"""
import sys
import os

# プロジェクトパスを Python パスに追加
# 注意：sys.path は最後に追加して、標準ライブラリの優先度を保つ
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(1, PROJECT_ROOT)  # 0ではなく1に変更
if os.path.join(PROJECT_ROOT, 'app') not in sys.path:
    sys.path.insert(2, os.path.join(PROJECT_ROOT, 'app'))

# .env ファイルの読み込み
from dotenv import load_dotenv
env_path = os.path.join(PROJECT_ROOT, 'config', '.env')
load_dotenv(env_path)

# Flask アプリケーションを初期化
from app.flask_app import app

# データベース初期化
try:
    with app.app_context():
        from app.database import init_db
        init_db()
except Exception as e:
    import sys
    print(f"Warning: Database initialization error: {e}", file=sys.stderr, flush=True)
    import traceback
    traceback.print_exc()

# WSGI アプリケーション - PythonAnywhere が呼び出す
application = app

# デバッグ用：アプリケーション初期化の確認
if __name__ != "__main__":
    import sys
    print(f"[WSGI] Flask app initialized: {app}", file=sys.stderr, flush=True)
    print(f"[WSGI] Config: DEBUG={app.debug}, TESTING={app.testing}", file=sys.stderr, flush=True)
