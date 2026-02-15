#!/bin/bash

# PythonAnywhereで直接実行するスクリプト
# PythonAnywhereダッシュボード → Bash console にコピー＆ペースト

echo "========================================="
echo "PythonAnywhere 強制同期スクリプト"
echo "========================================="
echo ""

cd /home/nnnkeita/kiroku-journal

# 1. 現在のファイル状態確認
echo "📋 現在のファイル状態:"
echo "-----------------------------------------"
echo "最新コミット:"
git log --oneline -1
echo ""
echo "Git status:"
git status
echo ""

# 2. 最新コードを強制取得
echo "🔄 GitHubから最新コードを取得中..."
git fetch origin
git reset --hard origin/main
echo "✅ 完了"
echo ""

# 3. AIチャット削除確認
echo "✓ AIチャット削除確認:"
echo "-----------------------------------------"

echo "  • flask_app.py内の /chat ルート:"
if grep -q "/chat" app/flask_app.py; then
    echo "    ❌ まだ存在しています"
else
    echo "    ✅ 削除済み"
fi

echo "  • index.html内のAIチャットメニュー:"
if grep -q "AIチャット" templates/index.html; then
    echo "    ❌ まだ存在しています"
else
    echo "    ✅ 削除済み"
fi

echo "  • chat.html ファイル:"
if [ -f "templates/chat.html" ]; then
    echo "    ❌ ファイルが存在しています"
else
    echo "    ✅ 削除済み"
fi
echo ""

# 4. キャッシュクリア
echo "🧹 Pythonキャッシュをクリア中..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null
echo "✅ 完了"
echo ""

# 5. 仮想環境確認
echo "🔍 仮想環境確認:"
echo "-----------------------------------------"
source ~/.virtualenvs/kiroku-journal/bin/activate
python --version
pip list | grep Flask
echo ""

# 6. Webアプリをリロード
echo "⚠️  次のステップ:"
echo "-----------------------------------------"
echo "1. PythonAnywhereダッシュボード → Web app"
echo "2. nnnkeita.pythonanywhere.com をクリック"
echo "3. Reload ボタン（緑色）をクリック"
echo ""
echo "4. ブラウザをリロード"
echo "   https://nnnkeita.pythonanywhere.com"
echo "   Cmd+Shift+R (強制リロード)"
echo ""

echo "========================================="
echo "✅ 同期完了！"
echo "========================================="
