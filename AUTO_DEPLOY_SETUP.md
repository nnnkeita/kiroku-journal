# 自動デプロイ セットアップガイド

このガイドでは、GitHubへのpushから自動的にPythonAnywhereが更新される仕組みを設定します。

## 必須ステップ

### Step 1: PythonAnywhere API トークンを取得

1. https://www.pythonanywhere.com/account/#api_token でログイン
2. **API Token** をコピー

### Step 2: GitHub Secret に登録

1. GitHub リポジトリ → **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret** をクリック
3. 以下の情報を入力：
   - **Name**: `PYTHONANYWHERE_API_TOKEN`
   - **Secret**: 上記で取得したトークンをペースト
4. **Add secret** をクリック

### Step 3: 自動デプロイの確認

- このセットアップ後、`git push origin main` すると自動的にPythonAnywhereがリロードされます
- GitHub → **Actions** タブで実行状況を確認できます

---

## オプション: PythonAnywhereでの自動git pull設定

PythonAnywhereで定期的にgit pullを実行するには：

### Cronjobの設定

1. PythonAnywhereダッシュボード → **Web** → **Console** を開く
2. 以下を実行：
```bash
chmod +x /home/nnnkeita/kiroku-journal/scripts/auto-deploy.sh
```

3. **Tasks** セクションで新しいcronjobを追加
4. スケジュール: `0 * * * * /home/nnnkeita/kiroku-journal/scripts/auto-deploy.sh`
   - 毎時間の00分に実行

---

## 動作確認

### 自動デプロイが動作しているか確認

1. GitHub で何か小さな変更を加えて commit & push
2. GitHub → **Actions** タブで実行ログを確認
3. 数秒後、ブラウザで https://nnnkeita.pythonanywhere.com をリロード
4. 変更が反映されているか確認

### トラブルシューティング

**GitHub Actionsが失敗する場合：**

- GitHub → **Settings** → **Secrets and variables** → **Actions** で `PYTHONANYWHERE_API_TOKEN` が正しく設定されているか確認

**PythonAnywhereが更新されない場合：**

1. 手動リロード: https://www.pythonanywhere.com/dashboards/nnnkeita → **Web** タブ → **Reload** ボタン
2. ログ確認: `tail -50 /home/nnnkeita/kiroku-journal/.deploy.log`

---

## 技術詳細

### 自動デプロイのフロー

```
User pushes to GitHub main branch
           ↓
GitHub Actions workflow triggers
           ↓
API request to PythonAnywhere reload endpoint
           ↓
PythonAnywhere web app restarts with latest code
           ↓
Browser reload → changes visible
```

### 対応ファイル

- `.github/workflows/deploy.yml` - シンプル版（リロードのみ）
- `.github/workflows/deploy-full.yml` - 詳細版（ログ付き）
- `scripts/auto-deploy.sh` - PythonAnywhereの自動git pull用
