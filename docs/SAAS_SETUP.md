# SaaS運用セットアップ

## 1. 必須の環境変数
`.env.example` を参考にして `.env` を作成してください。

必須:
- `APP_SECRET`
- `APP_BASE_URL`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_ID`

任意（メール再設定）:
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM`

## 2. Stripe設定
- 商品/価格（サブスク）を作成し、Price ID を取得
- Webhookエンドポイント: `/webhook/stripe`
- 送信イベント:
  - `checkout.session.completed`
  - `customer.subscription.created`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`

## 3. 動作確認の流れ
1. 初回アクセスで `/setup` に進み、ユーザー作成（14日トライアル開始）
2. `/billing` から決済
3. Webhook受信後に `subscription_status` が `active` になる

## 4. ステータス一覧
- `trialing`: トライアル中
- `active`: 有料
- `inactive`: 無効/期限切れ
- `canceled`: 解約
