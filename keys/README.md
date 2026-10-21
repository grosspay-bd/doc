# Webhook public keys — shared sandbox merchant

These are the webhook **public** keys of the shared test merchant **GrossPay Test BD**. Use them to verify `signature-v1` on webhooks sent for that sandbox account only.

| File | Environment |
|---|---|
| [`sandbox-test-merchant.test.pem`](sandbox-test-merchant.test.pem) | Test — `api-test.grosspayme.com` |
| [`sandbox-test-merchant.production.pem`](sandbox-test-merchant.production.pem) | Production — `api.grosspayme.com` |

Format: PEM, `-----BEGIN PUBLIC KEY-----` (SubjectPublicKeyInfo), RSA 2048.

> **Your own merchant account has its own key**, issued together with your API key. Webhooks for your account will **not** verify with the keys in this folder.

Check a key file:

```bash
openssl pkey -pubin -in sandbox-test-merchant.test.pem -noout -text | head -1
# Public-Key: (2048 bit)
```
