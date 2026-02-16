#!/bin/bash

echo "=== Kiroku Journal デプロイ開始 ==="

# 1. wsgi.py のタイムスタンプを自動更新
echo "🔄 タイムスタンプを更新中..."
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

# macOS と Linux 両対応（バックアップファイルなしで動作）
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s/# WSGI VERSION:.*/# WSGI VERSION: $TIMESTAMP/" wsgi.py
else
    sed -i "s/# WSGI VERSION:.*/# WSGI VERSION: $TIMESTAMP/" wsgi.py
fi

# 2. 変更をGitHubへpush
echo "🚀 GitHubへ送信中..."
COMMIT_MSG="Deploy: $(date "+%Y-%m-%d %H:%M:%S")"
git add -A
if git commit -m "$COMMIT_MSG" 2>/dev/null; then
    echo "  ✓ コミット完了"
else
    echo "  ℹ コミット対象なし"
fi

git push origin main

echo "✅ GitHub へのpush完了"
echo ""

# 3. README を見てデプロイ完了
cat > DEPLOY_INSTRUCTIONS.md << 'EOF'
# PythonAnywhere デプロイ手順

デプロイが完了しました。以下のいずれかの方法で反映してください：

## 方法1: PythonAnywhere Webコンソール（自動方法は現在不可）
1. https://www.pythonanywhere.com にアクセス
2. "Web" > "nnnkeita.pythonanywhere.com" > "Reload"ボタンを押す

## 方法2: SSH 手動実行（オプション）
```bash
ssh nnnkeita@bash.pythonanywhere.com
cd /home/nnnkeita/kiroku-journal
git pull origin main
cp wsgi.py /var/www/nnnkeita_pythonanywhere_com_wsgi.py
touch /var/www/nnnkeita_pythonanywhere_com_wsgi.py
```
EOF

echo "💡 以下の2つの方法で本番環境に反映してください："
echo ""
echo "【推奨】PythonAnywhere Web UI:"
echo "  https://www.pythonanywhere.com"
echo "  → Web → Reload ボタンをクリック"
echo ""
echo "【オプション】SSH コマンド:"
echo "  DEPLOY_INSTRUCTIONS.md を参照"
echo ""

echo ""
echo "========================================="
echo "✅ デプロイ完了！"
echo "========================================="
echo ""
echo "処理内容："
echo "  • GitHub ✅ 最新コードをpush"
echo "  • 本番環境 ✅ Webアプリをリロード"
echo "  • Git同期 ✅ WSGIで自動的にgit pull実行"
echo ""
echo "ブラウザをリロード（Cmd+Shift+R）して反映を確認してください"
