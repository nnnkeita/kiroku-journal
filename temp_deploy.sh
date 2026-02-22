#!/bin/bash
echo "🔄 PythonAnywhere サーバーにアクセス中..."
ssh nnnkeita@bash.pythonanywhere.com << 'REMOTE'
echo "📥 最新コードを取得..."
cd /home/nnnkeita/kiroku-journal
git pull origin main

echo "📋 現在のコミットを確認..."
git log --oneline -1

echo "🔄 WSGIファイルを更新..."
cp wsgi.py /var/www/nnnkeita_pythonanywhere_com_wsgi.py
touch /var/www/nnnkeita_pythonanywhere_com_wsgi.py

echo "✅ デプロイ完了！"
REMOTE
