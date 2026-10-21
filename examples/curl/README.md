# curl scripts

```bash
cp .env.example .env        # fill in GROSSPAY_API_KEY (test key) and GROSSPAY_CALLBACK_URI
./create-deposit.sh 1000.00                    # → open hosted_url to pay
./create-payout.sh 01712345678 1500.00
./get-state.sh order_bd_1729500000             # payment_id or merchant_ref
./get-balance.sh
./escalate.sh <payment_id> "Paid via bKash, TrxID 9A1B2C3D4E" receipt.jpg
./verify-webhook.sh public.pem body.json "<signature-v1 header value>"
```

`jq` is optional — output is pretty-printed when it's installed. `.env` is git-ignored; never commit real keys.
