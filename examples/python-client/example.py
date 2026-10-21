"""Run against the Test environment:
    pip install requests
    export GROSSPAY_BASE_URL=https://api-test.grosspayme.com/v1
    export GROSSPAY_API_KEY=...            # your TEST key
    python example.py
"""
import os
import time

from grosspay_bd import GrossPayClient, GrossPayError

gp = GrossPayClient(os.environ["GROSSPAY_BASE_URL"], os.environ["GROSSPAY_API_KEY"])
callback = os.environ.get("GROSSPAY_CALLBACK_URI", "https://webhook.site/your-uuid")

print("balance:", gp.balance())

ref = f"order_bd_{int(time.time())}"
try:
    deposit = gp.create_deposit(
        "1000.00", merchant_ref=ref, holder_ref="user_bd_001",
        callback_uri=callback, return_uri="https://your-site.com/deposit/finished",
    )
    print("open to pay:", deposit["hosted_url"])
    print("state by merchant_ref:", gp.get_state(ref)["posting_state"])
except GrossPayError as e:
    if e.code == "470":
        print("customer already has an active payment")
    elif e.code in ("475", "476"):
        print("amount outside allowed range")
    else:
        raise
