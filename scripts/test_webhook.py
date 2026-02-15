#!/usr/bin/env python
"""
Webhook テスト用スクリプト
Flask の Webhook エンドポイントに直接テストイベントを送信
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

import requests
import json
import stripe

# Stripe Webhook Secret を取得
WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')
FLASK_URL = 'http://localhost:5000/webhook/stripe'

# テストイベントデータを作成
test_event = {
    'id': 'evt_test_webhook',
    'object': 'event',
    'api_version': '2026-01-28.clover',
    'created': 1234567890,
    'type': 'checkout.session.completed',
    'data': {
        'object': {
            'id': 'cs_test_123456',
            'object': 'checkout.session',
            'customer': 'cus_test_123456',
            'payment_status': 'paid',
            'status': 'complete'
        }
    }
}

print(f"[TEST] Flask endpoint: {FLASK_URL}")
print(f"[TEST] Webhook Secret set: {bool(WEBHOOK_SECRET)}")
print(f"[TEST] Sending test event: {test_event['type']}")

payload = json.dumps(test_event)

if WEBHOOK_SECRET:
    # Stripe の署名を作成
    import hmac
    import hashlib
    timestamp = int(test_event['created'])
    signed_content = f'{timestamp}.{payload}'
    signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        signed_content.encode(),
        hashlib.sha256
    ).hexdigest()
    header = f't={timestamp},v1={signature}'
else:
    header = None

headers = {
    'Content-Type': 'application/json',
}

if header:
    headers['Stripe-Signature'] = header
    print(f"[TEST] Signature header: {header[:50]}...")
else:
    print("[TEST] No signature (WEBHOOK_SECRET not set)")

try:
    response = requests.post(FLASK_URL, data=payload, headers=headers, timeout=5)
    print(f"[TEST] Response status: {response.status_code}")
    print(f"[TEST] Response body: {response.text}")
except Exception as e:
    print(f"[ERROR] Request failed: {e}")
