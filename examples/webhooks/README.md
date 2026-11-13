# Webhook receivers

Three equivalent reference receivers. Each one:

1. accepts `POST /webhooks/grosspay` only;
2. checks the sender IP (`136.148.218.118` by default);
3. verifies `signature-v1` against the **raw body** (RSA PKCS#1 v1.5, SHA-256);
4. applies the payment state **idempotently** (duplicates and out-of-order events are safe), booking the player's balance by **`client_amount`** (never `amount_posted` — on payouts it includes the fee);
5. answers `200` on success, `401`/`403` on rejected requests, `503` on internal errors (GrossPay retries).

| Folder | Stack |
|---|---|
| [`node-express`](node-express) | Node.js 18+, Express |
| [`python-flask`](python-flask) | Python 3.10+, Flask, `cryptography` |
| [`php`](php) | PHP 7.4+/8.x, ext-openssl |

The in-memory / JSON-file storage is a stand-in. In production, store the state in your database and apply each event in a transaction with a row lock.

## Run locally with a self-signed test webhook

```bash
# 1. generate your own test key pair (send-test-webhook.sh signs with test_private.pem)
openssl genrsa -out test_private.pem 2048
openssl rsa -in test_private.pem -pubout -out test_public.pem

# 2. start one receiver with that public key, IP check disabled for local tests
cd node-express && npm install && \
  GROSSPAY_WEBHOOK_PUBLIC_KEY_FILE=../test_public.pem GROSSPAY_ALLOWED_IPS='*' node server.js
#   or: cd python-flask && pip install -r requirements.txt && \
#       GROSSPAY_WEBHOOK_PUBLIC_KEY_FILE=../test_public.pem GROSSPAY_ALLOWED_IPS='*' flask --app app run --port 3000
#   or: cd php && GROSSPAY_WEBHOOK_PUBLIC_KEY_FILE=../test_public.pem GROSSPAY_ALLOWED_IPS='*' php -S 127.0.0.1:3000 webhook.php

# 3. in another terminal, play a sequence of events
#    args: <url> <posting_state> [client_amount] [amount_posted] [payment_id] [merchant_ref]
./send-test-webhook.sh http://127.0.0.1:3000/webhooks/grosspay received
./send-test-webhook.sh http://127.0.0.1:3000/webhooks/grosspay posted 1000.00
./send-test-webhook.sh http://127.0.0.1:3000/webhooks/grosspay posted 1000.00   # duplicate → no double credit
./send-test-webhook.sh http://127.0.0.1:3000/webhooks/grosspay queued           # stale → ignored
./send-test-webhook.sh http://127.0.0.1:3000/webhooks/grosspay returned         # credit reversed

# payout of 15000 with a 450 fee: player must be debited 15000 (client_amount), not 15450 (amount_posted)
./send-test-webhook.sh http://127.0.0.1:3000/webhooks/grosspay posted 15000.00 15450.00 01a1b1cc-684c-741b-b37f-5b7cf1981c0c withdraw_bd_0002
```

The Node and Flask receivers expose `GET /debug/ledger` to inspect the result. **Remove it in production.**

For real GrossPay webhooks use your merchant's public key (Test or Production) and keep the IP check enabled.
