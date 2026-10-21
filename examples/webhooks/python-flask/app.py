"""
GrossPay webhook receiver — Python + Flask

    pip install -r requirements.txt
    GROSSPAY_WEBHOOK_PUBLIC_KEY_FILE=../../../keys/sandbox-test-merchant.test.pem flask --app app run --port 3000

Env:
    GROSSPAY_WEBHOOK_PUBLIC_KEY_FILE  path to the PEM public key (required)
    GROSSPAY_ALLOWED_IPS              comma-separated, default 136.148.218.118 ("*" disables, tests only)

The in-memory DB stands in for your database. In production run apply_event()
inside a transaction with a row lock (SELECT ... FOR UPDATE).
If you are behind a reverse proxy, wrap the app with werkzeug's ProxyFix so
request.remote_addr is the real client IP.
"""
import base64
import json
import logging
import os
from decimal import Decimal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from flask import Flask, abort, jsonify, request

log = logging.getLogger("grosspay")
logging.basicConfig(level=logging.INFO)

with open(os.environ["GROSSPAY_WEBHOOK_PUBLIC_KEY_FILE"], "rb") as fh:
    PUBLIC_KEY = serialization.load_pem_public_key(fh.read())

ALLOWED_IPS = {ip.strip() for ip in os.environ.get("GROSSPAY_ALLOWED_IPS", "136.148.218.118").split(",")}
FINAL = {"posted", "part_posted", "unposted", "returned"}
NON_FINAL = {"received", "queued"}

# ---- stand-in for your database ---------------------------------------------
DB: dict[str, dict] = {}   # payment_id -> {posting_state, amount_posted, booked}
LEDGER: list[dict] = []


def verify_signature(raw_body: bytes, signature_v1: str | None) -> bool:
    if not signature_v1:
        return False
    try:
        PUBLIC_KEY.verify(base64.b64decode(signature_v1), raw_body, padding.PKCS1v15(), hashes.SHA256())
        return True
    except (InvalidSignature, ValueError):
        return False


def target_amount(event: dict) -> Decimal:
    """What should be booked for this payment in its current state."""
    if event.get("posting_state") in ("posted", "part_posted"):
        return Decimal(event.get("amount_posted") or "0")
    return Decimal("0")


def apply_event(event: dict) -> str:
    """Idempotent, order-tolerant state application."""
    pid = event["payment_id"]
    cur = DB.get(pid, {"posting_state": None, "amount_posted": None, "booked": Decimal("0")})

    if cur["posting_state"] == event.get("posting_state") and cur["amount_posted"] == event.get("amount_posted"):
        return "duplicate"
    if cur["posting_state"] in FINAL and event.get("posting_state") in NON_FINAL:
        return "stale (step back to non-final state ignored)"

    delta = target_amount(event) - cur["booked"]
    if delta != 0:
        # Pay-in: +delta to customer balance. Pay-out: delta is the final debit.
        LEDGER.append({"payment_id": pid, "merchant_ref": event.get("merchant_ref"), "delta": str(delta)})
    DB[pid] = {
        "posting_state": event.get("posting_state"),
        "amount_posted": event.get("amount_posted"),
        "booked": cur["booked"] + delta,
    }
    return f"applied {cur['posting_state']} -> {event.get('posting_state')}, delta {delta}"


app = Flask(__name__)


@app.post("/webhooks/grosspay")
def grosspay_webhook():
    if "*" not in ALLOWED_IPS and request.remote_addr not in ALLOWED_IPS:
        log.warning("rejected webhook from %s", request.remote_addr)
        abort(403)

    raw = request.get_data(cache=False)  # raw bytes — do NOT use request.json for verification
    if not verify_signature(raw, request.headers.get("signature-v1")):
        log.warning("invalid signature")
        abort(401)

    try:
        event = json.loads(raw)
    except ValueError:
        abort(400)

    try:
        result = apply_event(event)
    except Exception:  # noqa: BLE001
        log.exception("processing failed")
        return "", 503  # GrossPay will retry

    log.info("[%s] %s: %s", event.get("payment_id"), event.get("merchant_ref"), result)
    return "", 200


@app.route("/webhooks/grosspay", methods=["GET", "PUT", "PATCH", "DELETE"])
def grosspay_webhook_other_methods():
    # Flask would answer 405 by default — and 405 means "merchant refuses the payment".
    return "", 404


@app.get("/debug/ledger")  # local testing only — remove in production
def debug_ledger():
    return jsonify(payments={k: {**v, "booked": str(v["booked"])} for k, v in DB.items()}, ledger=LEDGER)
