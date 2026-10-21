# 05 · Webhooks (callbacks)

← [Payment status](04-payment-status.md) · Next: [Payment object & lifecycle](06-payment-object.md) →

- [Overview](#overview)
- [Delivery](#delivery)
- [Security: IP allow-list + signature](#security-ip-allow-list--signature)
- [Verifying `signature-v1`](#verifying-signature-v1)
- [How to respond](#how-to-respond)
- [Handler algorithm](#handler-algorithm)
- [Testing webhooks](#testing-webhooks)
- [Troubleshooting](#troubleshooting)

---

## Overview

Every time a payment's state changes, GrossPay sends an HTTP `POST` to the `callback_uri` you passed in `POST /payments/init`.

Webhooks are **the primary source of truth** for payment results. `GET /state` is cached and is meant for recovery and reconciliation only ([why](04-payment-status.md#status-is-cached--webhooks-are-the-source-of-truth)).

## Delivery

| Property | Value |
|---|---|
| Method | `POST` |
| URL | Your `callback_uri` (per payment) |
| Content type | `application/json` |
| Body | The full payment object — identical in structure to `GET /payments/{id}/state` |
| Signature header | `signature-v1` — base64 RSA signature of the raw body (PKCS#1 v1.5, SHA-256) |
| Sender IP | `136.148.218.118` (same for Test and Production) |
| Trigger | Every change of payment state |
| Retries | Until your endpoint answers `2xx` (or `405`, see below) |

### Example request

```http
POST /webhooks/grosspay HTTP/1.1
Host: your-site.com
Content-Type: application/json
signature-v1: k3J9...base64...==

{"payment_id":"01a15cf5-f7c2-78b1-9276-87ea2c018577","hosted_url":"https://...","merchant_ref":"order_bd_0001","posting_state":"posted","amount_posted":"1000.00","client_amount":null,"decline_note":null,"order_amount":"1000.00","order_currency":"BDT","booked_at":"2026-10-21T05:36:26.058Z","posted_at":"2026-10-21T05:41:02.511Z","payee_details":null,"valid_through":null}
```

The same body, formatted for reading:

```json
{
  "payment_id": "01a15cf5-f7c2-78b1-9276-87ea2c018577",
  "hosted_url": "https://...",
  "merchant_ref": "order_bd_0001",
  "posting_state": "posted",
  "amount_posted": "1000.00",
  "client_amount": null,
  "decline_note": null,
  "order_amount": "1000.00",
  "order_currency": "BDT",
  "booked_at": "2026-10-21T05:36:26.058Z",
  "posted_at": "2026-10-21T05:41:02.511Z",
  "payee_details": null,
  "valid_through": null
}
```

> ⚠️ The signature is computed over the **compact body exactly as sent**. The pretty-printed version above would **not** verify.

---

## Security: IP allow-list + signature

Use **both** checks — they protect against different attacks.

1. **IP allow-list.** Accept requests to `callback_uri` only from `136.148.218.118`. If you are behind a load balancer / CDN / reverse proxy, check the *original* client IP (e.g. `X-Forwarded-For` as set by **your** proxy), not the proxy's address.
2. **Signature.** Verify `signature-v1` on every request **before** acting on the body. A request with a missing or invalid signature must not change anything in your system.

Also:

- Serve `callback_uri` over **HTTPS** with a valid certificate.
- Don't put secrets in `callback_uri` query strings — URLs end up in logs.
- Including your own order ID in the path (e.g. `/webhooks/grosspay/order_bd_0001`) is fine, but still look the payment up by the signed body, not by the URL.

---

## Verifying `signature-v1`

| Parameter | Value |
|---|---|
| Algorithm | RSA, PKCS#1 v1.5 padding, SHA-256 (`SHA256withRSA`, `RS256`-style) |
| Signed data | **Raw HTTP request body bytes**, exactly as received — before any JSON parsing |
| Header | `signature-v1`, base64-encoded (standard alphabet) |
| Key | Your merchant **webhook public key** (PEM, `-----BEGIN PUBLIC KEY-----`, SubjectPublicKeyInfo). Test and Production keys differ. |

### The #1 integration bug: verifying a re-serialized body

Most web frameworks parse JSON automatically. If you verify the signature against `JSON.stringify(req.body)` / `json.dumps(data)` / `json_encode($data)`, the bytes differ from what was signed (spacing, key order, number and unicode formatting) and verification fails at random. **Always verify the raw body.**

| Stack | How to get the raw body |
|---|---|
| Node.js / Express | `express.raw({ type: 'application/json' })` on the webhook route → `req.body` is a `Buffer` |
| Node.js / Fastify | `addContentTypeParser('application/json', { parseAs: 'buffer' }, ...)` |
| Python / Flask | `request.get_data()` |
| Python / Django | `request.body` |
| Python / FastAPI | `await request.body()` |
| PHP | `file_get_contents('php://input')` |
| Laravel | `$request->getContent()` |
| Go | `io.ReadAll(r.Body)` |
| Java / Spring | `@RequestBody byte[] body` |

### Shell (openssl) — for manual checks

```bash
# body.json — the raw request body saved as-is; sig.txt — the signature-v1 header value
base64 -d sig.txt > sig.bin
openssl dgst -sha256 -verify public.pem -signature sig.bin body.json
# → Verified OK
```

### Node.js

```js
const crypto = require('crypto');

// rawBody: Buffer of the request body BEFORE JSON.parse
function isValidSignature(rawBody, signatureHeader, publicKeyPem) {
  if (!signatureHeader) return false;
  return crypto.verify(
    'sha256',
    rawBody,
    publicKeyPem,
    Buffer.from(signatureHeader, 'base64'),
  );
}
```

### Python (`cryptography`)

```python
import base64
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

PUBLIC_KEY = serialization.load_pem_public_key(PUBLIC_KEY_PEM.encode())

def is_valid_signature(raw_body: bytes, signature_v1: str | None) -> bool:
    if not signature_v1:
        return False
    try:
        PUBLIC_KEY.verify(base64.b64decode(signature_v1), raw_body,
                          padding.PKCS1v15(), hashes.SHA256())
        return True
    except (InvalidSignature, ValueError):
        return False
```

### PHP

```php
<?php
function isValidSignature(string $rawBody, ?string $signatureHeader, string $publicKeyPem): bool {
    if (!$signatureHeader) return false;
    $signature = base64_decode($signatureHeader, true);
    if ($signature === false) return false;
    return openssl_verify($rawBody, $signature, $publicKeyPem, OPENSSL_ALGO_SHA256) === 1;
}

$raw = file_get_contents('php://input');
$ok  = isValidSignature($raw, $_SERVER['HTTP_SIGNATURE_V1'] ?? null, file_get_contents(__DIR__.'/grosspay_public.pem'));
```

### Go

```go
import (
	"crypto"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/pem"
	"errors"
)

func VerifySignature(rawBody []byte, signatureHeader string, publicKeyPEM []byte) error {
	block, _ := pem.Decode(publicKeyPEM)
	if block == nil {
		return errors.New("invalid PEM")
	}
	pub, err := x509.ParsePKIXPublicKey(block.Bytes)
	if err != nil {
		return err
	}
	rsaPub, ok := pub.(*rsa.PublicKey)
	if !ok {
		return errors.New("not an RSA key")
	}
	sig, err := base64.StdEncoding.DecodeString(signatureHeader)
	if err != nil {
		return err
	}
	digest := sha256.Sum256(rawBody)
	return rsa.VerifyPKCS1v15(rsaPub, crypto.SHA256, digest[:], sig) // nil = valid
}
```

### Java

```java
import java.security.KeyFactory;
import java.security.PublicKey;
import java.security.Signature;
import java.security.spec.X509EncodedKeySpec;
import java.util.Base64;

static boolean isValidSignature(byte[] rawBody, String signatureHeader, String publicKeyPem) throws Exception {
    if (signatureHeader == null) return false;
    String b64 = publicKeyPem.replaceAll("-----(BEGIN|END) PUBLIC KEY-----", "").replaceAll("\\s", "");
    PublicKey key = KeyFactory.getInstance("RSA")
            .generatePublic(new X509EncodedKeySpec(Base64.getDecoder().decode(b64)));
    Signature verifier = Signature.getInstance("SHA256withRSA");
    verifier.initVerify(key);
    verifier.update(rawBody);
    return verifier.verify(Base64.getDecoder().decode(signatureHeader));
}
```

Complete runnable receivers: [`examples/webhooks`](../examples/webhooks) (Node.js/Express, Python/Flask, PHP).

---

## How to respond

| Your HTTP response | How GrossPay treats it |
|---|---|
| **`2xx`** (`200`, `201`, `204`) | Delivered and accepted. No more retries for this event. |
| **`405`** | **You refuse the payment.** Not a technical error — a business decision. |
| Anything else (`4xx` other than `405`, `5xx`, timeout, connection refused, TLS error) | Not delivered → the webhook is **sent again** |

### Choosing the right code

| Situation | Respond |
|---|---|
| Signature valid, state applied (or already applied earlier — duplicate) | `200` |
| Signature valid, but it's an old/out-of-order event you are ignoring | `200` |
| Signature **invalid** or missing, or IP not allowed | `401` / `403` (nothing is changed; if it really was GrossPay, the retry will come) |
| Temporary problem on your side (DB down, lock timeout) | `500` / `503` → GrossPay will retry |
| Payment not found yet (race: webhook came before you saved `payment_id`) | Look it up by `merchant_ref`; if still not found → `503` so it is retried |
| You deliberately do **not** accept this payment | `405` |

> ⚠️ **Never return `405` by accident.** Some frameworks answer `405 Method Not Allowed` automatically when a route is registered for the wrong HTTP method (e.g. `GET` only). That would be read as refusing the payment. Make sure the `callback_uri` route accepts `POST`, and only return `405` from explicit business logic.

### Respond quickly

Persist the event and answer `200` within a few seconds. Heavy work (emails, analytics, bonus calculation) should run asynchronously **after** the state is stored. A slow endpoint causes timeouts → duplicate deliveries.

---

## Handler algorithm

The webhook body contains **absolute** values (the full current state), not differences. Your handler must be **idempotent**: receiving the same webhook twice — or receiving webhooks out of order — must never credit or debit twice.

```text
on POST /webhooks/grosspay:
  1. raw = request raw body
  2. if source IP not allowed            → 403
  3. if !verify(raw, header 'signature-v1') → 401
  4. event = JSON.parse(raw)
  5. BEGIN TRANSACTION
       p = SELECT ... FROM payments
           WHERE payment_id = event.payment_id OR merchant_ref = event.merchant_ref
           FOR UPDATE
       if p not found                     → ROLLBACK, 503 (retry later)
       if (p.posting_state, p.amount_posted) == (event.posting_state, event.amount_posted)
                                          → COMMIT, 200   (duplicate, nothing to do)
       if event is a step BACK to a non-final state (received/queued)
          while p is already final        → COMMIT, 200   (stale, ignore)
       old_booked = booked_amount(p)      // what you have credited/debited so far
       new_booked = booked_amount(event)  // see table below
       apply_ledger_delta(new_booked - old_booked)
       p.posting_state = event.posting_state
       p.amount_posted = event.amount_posted
       save raw event to payment_events (audit log)
     COMMIT
  6. → 200
```

`booked_amount` — how much should be booked for the customer for a given state:

| `posting_state` | Pay-in (debit): customer credited | Pay-out (credit): customer debited |
|---|---|---|
| `received`, `queued` | `0` | `0` final debit (amount still on hold) |
| `posted` | `amount_posted` | `amount_posted` |
| `part_posted` | `amount_posted` | `amount_posted` |
| `unposted` | `0` | `0` (release hold) |
| `returned` | `0` (reverse what was credited) | `0` (give money back) |

With this approach every transition — including `posted → returned` and any later correction of `amount_posted` — is handled by the same code, without special cases.

---

## Testing webhooks

1. **Public inspector.** Use a request bin (e.g. `https://webhook.site/...`) as `callback_uri` in Test to see real payloads and headers.
2. **Local development.** Expose your local server with a tunnel (ngrok, Cloudflare Tunnel) and use the tunnel URL as `callback_uri`. Note that the IP allow-list must still let `136.148.218.118` through.
3. **Unit tests without GrossPay.** Generate your own RSA key pair, sign sample bodies and feed them to your handler:

   ```bash
   openssl genrsa -out test_private.pem 2048
   openssl rsa -in test_private.pem -pubout -out test_public.pem
   printf '%s' '{"payment_id":"test-1","merchant_ref":"order_bd_0001","posting_state":"posted","amount_posted":"1000.00","order_amount":"1000.00","order_currency":"BDT"}' > body.json
   openssl dgst -sha256 -sign test_private.pem body.json | base64 -w0 > sig.txt

   curl -X POST http://localhost:3000/webhooks/grosspay \
     -H "Content-Type: application/json" \
     -H "signature-v1: $(cat sig.txt)" \
     --data-binary @body.json
   ```

   Run your handler with `test_public.pem` for these tests. Use `--data-binary` (not `-d`) so curl sends the bytes unchanged.

4. Cover the scenarios from the [go-live checklist](10-go-live-checklist.md#webhook-scenarios): duplicates, out-of-order delivery, `posted → returned`, invalid signature.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Signature fails on every request | Wrong key (Test vs Production), or verifying re-serialized JSON | Use the key for the right environment; verify raw bytes |
| Signature fails only sometimes | Body re-serialized; or a proxy/WAF modifies the body (adds whitespace, re-encodes unicode) | Verify raw bytes; disable body rewriting on the webhook route |
| `header signature-v1 missing` | Proxy strips unknown headers; or reading the wrong header name | Allow `signature-v1` through; in PHP it is `$_SERVER['HTTP_SIGNATURE_V1']` |
| Same webhook arrives many times | Your endpoint returns non-`2xx` or times out | Return `200` fast; check logs for exceptions |
| Payment refused unexpectedly | Your endpoint returned `405` (often framework default for wrong method) | Allow `POST` on the route; return `405` only on purpose |
| No webhooks at all | Firewall blocks `136.148.218.118`; `callback_uri` not publicly reachable; invalid TLS certificate | Check firewall, DNS, certificate chain; test with a request bin |

Next: [Payment object & lifecycle](06-payment-object.md) →
