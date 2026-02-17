#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kiroku Journal - エントリーポイント

このスクリプトから Flask アプリを起動します
"""
import sys
import os

# プロジェクトルートを Python パスに追加
sys.path.insert(0, os.path.dirname(__file__))

# Flask アプリを起動
if __name__ == '__main__':
    from app.flask_app import app
    
    HOST = '127.0.0.1'
    PORT = 5000
    
    print(f"🚀 Kiroku Journal が起動しました")
    print(f"📱 アクセスURL: http://{HOST}:{PORT}")
    print(f"🛑 停止するには Ctrl+C を押してください")
    
    # run.py から直接実行時
    import webbrowser
    from threading import Timer
    
    def open_browser():
        webbrowser.open_new(f'http://{HOST}:{PORT}/')
    
    Timer(1.5, open_browser).start()
    app.run(host=HOST, port=PORT, debug=False)
