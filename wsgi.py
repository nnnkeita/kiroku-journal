# -*- coding: utf-8 -*-
import sys
import os

# PythonAnywhereの問題を回避：sys.pathをリセット
import builtins
_original_import = builtins.__import__

# venvから標準ライブラリを使う
venv_lib = '/home/nnnkeita/.virtualenvs/kiroku-journal/lib/python3.11'
sys.path = [venv_lib + '/site-packages', '/usr/lib/python3.11', '/usr/local/lib/python3.11']

os.chdir('/home/nnnkeita/kiroku-journal')

# Flask アプリを読み込む
from dotenv import load_dotenv
load_dotenv('/home/nnnkeita/kiroku-journal/config/.env')

from app.flask_app import app
with app.app_context():
    from app.database import init_db
    init_db()

application = app
