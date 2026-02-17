#!/bin/bash

# PythonAnywhere のデバッグログをSSH経由で確認
echo "🔍 PythonAnywhere のデプロイ状況を確認中..."
echo ""

# SSH 接続してログを確認（パスワード不要の方法は後述）
if [ -f ~/.ssh/id_rsa ] || [ -f ~/.ssh/id_ed25519 ]; then
    echo "📋 .wsgi_debug.log の内容："
    ssh -o ConnectTimeout=5 -o BatchMode=yes nnnkeita@bash.pythonanywhere.com \
        "tail -50 /home/nnnkeita/kiroku-journal/.wsgi_debug.log 2>/dev/null || echo 'ログファイルが見つかりません'"
    
    echo ""
    echo "🔗 現在のGit状態："
    ssh -o ConnectTimeout=5 -o BatchMode=yes nnnkeita@bash.pythonanywhere.com \
        "cd /home/nnnkeita/kiroku-journal && git log --oneline -3 2>/dev/null || echo 'Git情報を取得できません'"
else
    echo "💡 SSH キーの設定が必要です。次のコマンドを実行してください："
    echo ""
    echo "方法1: SSH キーを生成"
    echo "  ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ''"
    echo ""
    echo "方法2: PythonAnywhere でログを確認"
    echo "  https://www.pythonanywhere.com"
    echo "  → Consoles → Bash コンソール"
    echo "  → tail -50 /home/nnnkeita/kiroku-journal/.wsgi_debug.log"
fi
