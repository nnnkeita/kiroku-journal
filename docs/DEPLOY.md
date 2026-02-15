# SaaS日記アプリ - デプロイガイド

## 開発環境での起動

```bash
# 1. 依存関係インストール
pip install -r requirements.txt

# 2. .envファイル作成
cp .env.example .env
# .envを編集して環境変数を設定

# 3. アプリ起動
python flask_app.py
```

初回アクセスで `/setup` に自動遷移し、ユーザー作成（14日トライアル開始）。

## 本番環境（PythonAnywhere / Heroku / Renderなど）

### 1. 環境変数設定
以下をプラットフォームの環境変数設定で追加:
```
APP_SECRET=ランダムな長い文字列
APP_BASE_URL=https://your-domain.com
AUTH_ENABLED=1
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID=price_...
```

### 2. Stripe Webhook設定
Stripeダッシュボード → Webhooks:
- URL: `https://your-domain.com/webhook/stripe`
- イベント:
  - `checkout.session.completed`
  - `customer.subscription.created`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`

### 3. データベース
SQLiteファイル (`notion.db`) の永続化を確認。

## セキュリティチェックリスト
- [ ] APP_SECRETを強固なランダム文字列に変更
- [ ] HTTPS化（本番環境必須）
- [ ] STRIPE_SECRET_KEYをライブモードに変更
- [ ] Webhook Secretを設定
- [ ] バックアップ自動化
- [ ] 利用規約・プライバシーポリシー設置

## 運用フロー
1. ユーザーが `/setup` でアカウント作成（14日トライアル）
2. トライアル期間中は無料でアプリ利用可能
3. 14日後に `/billing` に誘導される
4. Stripe決済 → Webhook → `subscription_status` が `active` に
5. 解約時も Webhook で `canceled` に自動更新

## トラブルシューティング
- **決済後もアクセスできない**: Webhookが届いているか確認（Stripeダッシュボード）
- **トライアルが終わらない**: `subscription_ends_at` とサーバー時刻（UTC）を確認
- **パスワード再設定メールが届かない**: SMTP設定を確認、未設定時は画面にリンク表示
