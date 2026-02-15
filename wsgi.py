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
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'app'))

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

# WSGI アプリケーション
application = app
