# PythonAnywhereサーバー直接確認ガイド

## 手動でPythonAnywhereのファイルを確認する

### ステップ1: Bash Consoleで状態確認

PythonAnywhereダッシュボード → **Bash console** を開いて以下を実行：

```bash
# 1. 現在のディレクトリ
cd /home/nnnkeita/kiroku-journal
pwd

# 2. Gitの最新コミットを確認
git log --oneline -5

# 3. AIチャット関連が削除されているか確認
echo "=== flask_app.py: /chat ルート確認 ==="
grep -n "/chat\|AIチャット" app/flask_app.py || echo "✅ /chat ルート: 削除済み"

echo ""
echo "=== index.html: AIチャットメニュー確認 ==="
grep -n "AIチャット\|🤖" templates/index.html || echo "✅ AIチャットメニュー: 削除済み"

echo ""
echo "=== chat.html: ファイル確認 ==="
ls -la templates/chat.html 2>/dev/null && echo "❌ chat.html が存在" || echo "✅ chat.html: 削除済み"
```

### ステップ2: ファイルが古い場合は強制更新

```bash
cd /home/nnnkeita/kiroku-journal

# Gitの状態確認
git status

# もし古い場合は強制更新
git fetch origin
git reset --hard origin/main

# 確認
echo "最新コミット:"
git log --oneline -1
```

### ステップ3: Webアプリをリロード

```bash
# PythonAnywhereダッシュボードから:
# 1. Web app タブをクリック
# 2. nnnkeita.pythonanywhere.com をクリック
# 3. Reload ボタン（緑色）をクリック

# または、ダッシュボードでコンソールからキャッシュをクリア
find /home/nnnkeita/kiroku-journal -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find /home/nnnkeita/kiroku-journal -name "*.pyc" -delete 2>/dev/null
echo "✅ キャッシュをクリアしました"
```

### ステップ4: ブラウザで確認

```
https://nnnkeita.pythonanywhere.com
- Cmd+Shift+R で強制リロード（キャッシュクリア）
- 左側メニューにAIチャット🤖がないか確認
```

---

## WSGIのgit pull動作確認

WSGIが実際にgit pullを実行しているか確認：

### エラーログを確認

```bash
# PythonAnywhereダッシュボード → Web app → Log files

# または、コンソールから：
tail -50 /var/log/nnnkeita.pythonanywhere.com.server.log | grep -i "git\|wsgi"

# または、最新ログ
tail -100 /var/log/nnnkeita.pythonanywhere.com.server.log
```

### WSGIファイルの内容確認

```bash
cat /home/nnnkeita/kiroku-journal/wsgi.py | head -30
```

期待される出力：
```
[WSGI] Starting initial git sync...
[WSGI] ✅ Git pull success
```

---

## よくある問題と対応

### 問題1: 「git pullコマンドが見つからない」

```bash
# gitのパスを確認
which git
/usr/bin/git

# WSGIで絶対パスを使用
# wsgi.py 内で git をフルパス指定に変更
```

### 問題2: 「Permission denied」

```bash
# 権限確認
ls -la /home/nnnkeita/kiroku-journal/.git/

# リポジトリの所有者確認
stat /home/nnnkeita/kiroku-journal

# 必要に応じてリセット
cd /home/nnnkeita/kiroku-journal
git config user.email "auto@deploy.local"
git config user.name "Auto Deploy"
```

### 問題3: 「まだAIチャットが表示される」

実行手順：

1. Bash consoleで以下を実行
```bash
cd /home/nnnkeita/kiroku-journal
git pull origin main
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null
```

2. PythonAnywhereダッシュボード → **Web app** → **Reload** クリック

3. ブラウザで Cmd+Shift+R してリロード

---

## デバッグ用：WSGIを修正版で置き换え

もし上記でも反映されない場合は、WSGIを以下のコマンドで確認・修正：

```bash
cd /home/nnnkeita/kiroku-journal

# WSGIファイル確認
cat wsgi.py

# 必要に応じて削除して再作成
rm wsgi.py

# 以下の内容で新規作成
cat > wsgi.py << 'EOF'
import sys
import os
import subprocess

PROJECT_ROOT = '/home/nnnkeita/kiroku-journal'

# Git同期（初回のみ）
if not os.environ.get('WSGI_GIT_SYNCED'):
    try:
        result = subprocess.run(
            ['git', '-C', PROJECT_ROOT, 'pull', 'origin', 'main'],
            capture_output=True,
            text=True,
            timeout=10
        )
        print(f"[WSGI] Git pull: {result.returncode}", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"[WSGI] Git error: {e}", file=sys.stderr, flush=True)
    os.environ['WSGI_GIT_SYNCED'] = '1'

# Flask アプリ
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(f'{PROJECT_ROOT}/config/.env')

from app.flask_app import app
with app.app_context():
    from app.database import init_db
    init_db()

application = app
EOF

# 確認
cat wsgi.py
```

その後 Reload をクリック。

---

実行してください。
