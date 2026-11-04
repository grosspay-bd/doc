# curl scripts

```bash
cp .env.example .env        # fill in GROSSPAY_API_KEY (test key) and GROSSPAY_CALLBACK_URI
./create-deposit.sh 1000.00                    # bKash → open hosted_url to pay
ROUTE_NETWORK=nagad HOLDER_ACCOUNT=01812345678 ./create-deposit.sh 1000.00   # Nagad + holder_account
ROUTE_KIND=banglaqr ROUTE_NETWORK=bkash ./create-deposit.sh 1000.00          # BanglaQR
ROUTE_KIND=card ./create-deposit.sh 1000.00                                  # card
./create-payout.sh 01712345678 1500.00                                       # bKash payout
ROUTE_NETWORK=nagad ./create-payout.sh 01812345678 1500.00                   # Nagad payout
./create-payout-bank.sh <bank_code> 1234567890123 "Rahim Uddin" 123456789    # bank payout
./get-state.sh order_bd_1729500000             # payment_id or merchant_ref
./get-balance.sh
./escalate.sh <payment_id> "Paid via bKash, TrxID 9A1B2C3D4E" receipt.jpg
./verify-webhook.sh public.pem body.json "<signature-v1 header value>"
```

`jq` is optional — output is pretty-printed when it's installed. `.env` is git-ignored; never commit real keys.
