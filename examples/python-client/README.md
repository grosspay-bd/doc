# Python client

`grosspay_bd.py` is a small, dependency-light client (only `requests`) that shows the recommended patterns:

- amounts formatted with `Decimal` → `"1000.00"`
- bKash number normalisation (`normalize_bkash`) before payouts
- error envelope → `GrossPayError` with `fault_class`, `code`, `retryable`
- **timeout-safe creation** (`init_safely`): after a network error / `5xx` it looks the payment up by `merchant_ref` and only repeats the POST with the same `merchant_ref` if the payment does not exist — no duplicate payouts

```bash
pip install -r requirements.txt
export GROSSPAY_BASE_URL=https://api-test.grosspayme.com/v1
export GROSSPAY_API_KEY=...    # test key
python example.py
```

Copy the file into your project and adapt logging / persistence to your stack.
