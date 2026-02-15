# PythonAnywhereデプロイ確認ガイド

## 問題：ローカル変更がPythonAnywhereに反映されない

このガイドはPythonAnywhereのダッシュボードで問題を診断するものです。

## 確認ステップ1：Webアプリの設定を確認

1. https://www.pythonanywhere.com/dashboards/nnnkeita にログイン
2. **Web app** タブを開く
3. **nnnkeita.pythonanywhere.com** をクリック

### 確認項目：

#### a) Working directory（作業ディレクトリ）
```
期待値: /home/nnnkeita/kiroku-journal
```

#### b) Python version
```
期待値: 3.8 以上
```

#### c) WSGI configuration file のパス
```
期待値: /home/nnnkeita/kiroku-journal/wsgi.py
または: /home/nnnkeita/kiroku-journal/app/wsgi.py
```

---

## 確認ステップ2：コンソールでファイルを確認

1. ダッシュボードの **Bash console** を開く
2. 以下のコマンドを実行：

```bash
# 1. リポジトリの確認
cd /home/nnnkeita/kiroku-journal
pwd

# 2. GitHubからの最新コミットを確認
git log --oneline -3

# 3. AIチャット削除が反映されているか確認
grep -r "AIチャット" templates/ || echo "✅ AIチャット: 削除済み"
grep -r "/chat" app/flask_app.py || echo "✅ /chatルート: 削除済み"
ls -la templates/chat.html 2>/dev/null && echo "⚠️ chat.html が存在" || echo "✅ chat.html: 削除済み"

# 4. 仮想環境の確認
cat /home/nnnkeita/.virtualenvs/nnnkeita_venv/pyvenv.cfg 2>/dev/null | head -3
```

---

## 確認ステップ3：手動でGitを更新

コンソールで以下を実行（コードが古い場合）：

```bash
cd /home/nnnkeita/kiroku-journal

# 最新のコミットを確認
git remote -v

# 強制的に最新を取得
git fetch origin
git reset --hard origin/main

# 確認
git log --oneline -1
```

---

## 確認ステップ4：Webアプリのリロード

1. ダッシュボード → **Web app** → **Reload** ボタン（緑）をクリック
2. コンソールでリロード状態を監視：
```bash
tail -f /var/log/nnnkeita.pythonanywhere.com.server.log
```

---

## 確認ステップ5：ブラウザで確認

1. https://nnnkeita.pythonanywhere.com にアクセス
2. ブラウザをリロード（**Cmd+Shift+R** - キャッシュクリア）
3. 左側メニューに「AIチャット」がないか確認

### 実装例：
```python
# ローカル（改善後）
# /chat ルートが削除されている
# AIチャットメニュー項目がない

# PythonAnywhere（未反映の場合）
# /chat ルートが残っている
# AIチャットメニュー項目が表示される
```

---

## よくある問題と解決方法

### 問題1：「それでも変わらない」

**原因**：PythonAnywhereの.pyc（コンパイル済みファイル）キャッシュ

**解決方法**：
```bash
cd /home/nnnkeita/kiroku-journal
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null
```

その後、Webアプリをリロード。

---

### 問題2：「エラーが出ている」

**原因**：Python依存パッケージの不整合

**解決方法**：
```bash
cd /home/nnnkeita/kiroku-journal
source ~/.virtualenvs/nnnkeita_venv/bin/activate
pip install -r requirements.txt --upgrade
```

---

### 問題3：「WSGIエラーが表示される」

**原因**：WSGIファイルの設定が古い

**確認**：
```bash
cat /home/nnnkeita/kiroku-journal/wsgi.py
# 最後の行が以下であることを確認
# from app.flask_app import app
```

---

## デプロイの標準手順

### ローカル（開発マシン）
```bash
cd /Users/nishiharakeita/kiroku-journal

# 1. 変更を確認
git status

# 2. コミット
git add .
git commit -m "説明"

# 3. push
git push origin main

# 4. デプロイスクリプト実行
./deploy_with_git_pull.sh
```

### PythonAnywhere（本番環境）
デプロイスクリプトが自動で実行します：
1. ✅ Webアプリをリロード
2. ⚠️ git pullは手動（Bash consoleで実行）

---

## API統合できない場合の代替手順

```bash
# ローカル
git push origin main

# PythonAnywhereダッシュボード
# 1. Web app → Reload
# 2. または Bash console で:
cd /home/nnnkeita/kiroku-journal && git pull && curl -X POST -H "Authorization: Token YOUR_TOKEN" https://www.pythonanywhere.com/api/v0/user/nnnkeita/webapps/nnnkeita.pythonanywhere.com/reload/
```

---

## 参考
- PythonAnywhere公式ドキュメント: https://help.pythonanywhere.com
- Gitの基本: https://git-scm.com/doc
