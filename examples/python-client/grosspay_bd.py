"""
Minimal GrossPay Bangladesh client (Python 3.10+, `requests`).

    from grosspay_bd import GrossPayClient, GrossPayError, normalize_wallet

    gp = GrossPayClient(base_url=os.environ["GROSSPAY_BASE_URL"], api_key=os.environ["GROSSPAY_API_KEY"])

    # deposit: wallet (bkash / nagad / rocket / upay), banglaqr (bkash / nagad) or card
    p = gp.create_deposit("1000.00", route_kind="wallet", route_network="nagad",
                          holder_account="01812345678",            # optional
                          merchant_ref="order_bd_0002", holder_ref="user_bd_001",
                          callback_uri="https://your-site.com/webhooks/grosspay",
                          return_uri="https://your-site.com/deposit/finished")
    redirect(p["hosted_url"])

    # payouts
    gp.create_payout("1500.00", wallet_number="01812345678", route_network="nagad", ...)
    gp.create_bank_payout("25000.00", bank_code="<bank_code>", account_number="1234567890123",
                          payee_title="Rahim Uddin", routing_number="123456789", ...)
"""
from __future__ import annotations

import re
import time
from decimal import Decimal
from urllib.parse import quote

import requests

WALLET_RULES = {
    "bkash": re.compile(r"01[3-9]\d{8}"),
    "nagad": re.compile(r"01[3-9]\d{8}"),
    "upay": re.compile(r"01[3-9]\d{8}"),
    "rocket": re.compile(r"01[3-9]\d{9}"),   # mobile number + check digit
}
DEPOSIT_KINDS = {"wallet", "banglaqr", "card"}


def normalize_wallet(value: str, network: str = "bkash") -> str | None:
    """'+880 1712-345678' / '8801712345678' / '01712345678' -> '01712345678'; None if invalid for the network."""
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("880"):
        digits = digits[2:]
    rule = WALLET_RULES.get(network)
    return digits if rule and rule.fullmatch(digits) else None


def normalize_bkash(value: str) -> str | None:
    """Backward-compatible alias for normalize_wallet(value, 'bkash')."""
    return normalize_wallet(value, "bkash")


def fmt_amount(amount: str | int | Decimal) -> str:
    """Decimal-safe formatting to a 2-decimal string: 1000 -> '1000.00'. Refuses to round money."""
    value = Decimal(str(amount))
    if value <= 0 or value != value.quantize(Decimal("0.01")):
        raise ValueError(f"amount must be positive with at most 2 decimals: {amount!r}")
    return str(value.quantize(Decimal("0.01")))


class GrossPayError(Exception):
    def __init__(self, http_status: int, fault: dict | None):
        self.http_status = http_status
        self.fault = fault or {}
        self.fault_class = self.fault.get("class")
        self.code = self.fault.get("code")
        self.at = self.fault.get("at") or []
        super().__init__(f"HTTP {http_status} {self.fault_class}/{self.code}: {self.fault.get('detail')}")

    @property
    def retryable(self) -> bool:
        return self.fault_class == "server" or self.code == "477" or self.http_status >= 500

    @property
    def not_found(self) -> bool:
        return self.http_status == 404

    @property
    def method_not_enabled(self) -> bool:
        """Validation error on route_network: method/network not enabled for the merchant (or missing for bank)."""
        return self.fault_class == "validation" and "route_network" in self.at


class GrossPayClient:
    def __init__(self, base_url: str, api_key: str, timeout: tuple[float, float] = (10, 30)):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {api_key}"})

    # ---- low level -----------------------------------------------------------
    def _request(self, method: str, path: str, **kwargs) -> dict:
        resp = self.session.request(method, f"{self.base_url}{path}", timeout=self.timeout, **kwargs)
        try:
            data = resp.json()
        except ValueError:
            data = {}
        if resp.ok and data.get("ok") is not False:
            return data
        raise GrossPayError(resp.status_code, data.get("fault"))

    # ---- payments ------------------------------------------------------------
    def create_deposit(self, amount, *, merchant_ref: str, holder_ref: str, callback_uri: str,
                       return_uri: str, route_kind: str = "wallet", route_network: str | None = "bkash",
                       holder_account: str | None = None, holder_name: str | None = None) -> dict:
        if route_kind not in DEPOSIT_KINDS:
            raise ValueError(f"route_kind for deposits must be one of {sorted(DEPOSIT_KINDS)}")
        body = {
            "order_amount": fmt_amount(amount),
            "order_currency": "BDT",
            "intent": "debit",
            "route_kind": route_kind,
            "merchant_ref": merchant_ref,
            "holder_ref": holder_ref,
            "callback_uri": callback_uri,
            "return_uri": return_uri,
        }
        if route_kind != "card" and route_network:
            body["route_network"] = route_network
        if holder_account:
            normalized = normalize_wallet(holder_account, route_network or "bkash")
            if not normalized:
                raise ValueError(f"invalid {route_network} number for holder_account: {holder_account!r}")
            body["holder_account"] = normalized
        if holder_name:
            body["holder_name"] = holder_name
        return self.init_safely(body)

    def create_payout(self, amount, *, wallet_number: str, merchant_ref: str, holder_ref: str,
                      callback_uri: str, route_network: str = "bkash", payee_title: str | None = None) -> dict:
        """Payout to a mobile wallet (bkash / nagad / rocket / upay)."""
        wallet = normalize_wallet(wallet_number, route_network)
        if not wallet:
            raise ValueError(f"invalid {route_network} number: {wallet_number!r}")
        details = {"wallet_number": wallet}
        if payee_title:
            details["payee_title"] = payee_title
        return self.init_safely({
            "order_amount": fmt_amount(amount),
            "order_currency": "BDT",
            "intent": "credit",
            "route_kind": "wallet",
            "route_network": route_network,
            "merchant_ref": merchant_ref,
            "holder_ref": holder_ref,
            "callback_uri": callback_uri,
            "credit_details": details,
        })

    def create_bank_payout(self, amount, *, bank_code: str, account_number: str, payee_title: str,
                           merchant_ref: str, holder_ref: str, callback_uri: str,
                           routing_number: str | None = None, branch_name: str | None = None) -> dict:
        """Payout to a bank account. May stay `queued` until the next business day (BEFTN) — never re-send."""
        account = re.sub(r"\s", "", account_number or "")
        if not account.isdigit():
            raise ValueError("account_number must contain digits only")
        if not payee_title:
            raise ValueError("payee_title is required for bank payouts")
        details = {"account_number": account, "payee_title": payee_title}
        if routing_number:
            if not re.fullmatch(r"\d{9}", routing_number):
                raise ValueError("routing_number must be 9 digits")
            details["routing_number"] = routing_number
        if branch_name:
            details["branch_name"] = branch_name
        return self.init_safely({
            "order_amount": fmt_amount(amount),
            "order_currency": "BDT",
            "intent": "credit",
            "route_kind": "bank",
            "route_network": bank_code,
            "merchant_ref": merchant_ref,
            "holder_ref": holder_ref,
            "callback_uri": callback_uri,
            "credit_details": details,
        })

    def init_safely(self, body: dict, attempts: int = 3) -> dict:
        """POST /payments/init with timeout-safe retries (never creates a duplicate).

        On a network error / 5xx, first look the payment up by merchant_ref; repeat the
        POST with the SAME merchant_ref only if the payment does not exist.
        """
        ref = body["merchant_ref"]
        for attempt in range(1, attempts + 1):
            try:
                return self._request("POST", "/payments/init", json=body)
            except (requests.ConnectionError, requests.Timeout):
                pass
            except GrossPayError as e:
                if not e.retryable:
                    raise
            # unknown outcome -> check whether the payment was created
            try:
                return self.get_state(ref)
            except GrossPayError as e:
                if not e.not_found:
                    raise
            except (requests.ConnectionError, requests.Timeout):
                pass
            time.sleep(min(2 ** attempt, 30))
        raise RuntimeError(f"could not create payment {ref} after {attempts} attempts; check state later")

    def get_state(self, payment_id_or_merchant_ref: str) -> dict:
        return self._request("GET", f"/payments/{quote(payment_id_or_merchant_ref, safe='')}/state")

    # ---- other ---------------------------------------------------------------
    def balance(self) -> dict:
        return self._request("GET", "/partner/ledger_balance")

    def escalate(self, payment_id: str, files: list[str], comment: str | None = None) -> dict:
        if not 1 <= len(files) <= 3:
            raise ValueError("attach 1 to 3 files")
        handles = [open(f, "rb") for f in files]
        try:
            multipart = {f"file{i}": h for i, h in enumerate(handles, start=1)}
            data = {"comment": comment} if comment else None
            return self._request("POST", f"/payments/{payment_id}/escalate", files=multipart, data=data)
        finally:
            for h in handles:
                h.close()
