# Changelog

## 2026-10-21

- Initial release of the Bangladesh (BDT · bKash) integration guide.
- Endpoints: `POST /payments/init` (debit / credit), `GET /payments/{id}/state`, `GET /partner/ledger_balance`, `POST /payments/{payment_id}/escalate`.
- Webhooks signed with RSA-SHA256 (`signature-v1`), sender IP `136.148.218.118`.
- OpenAPI 3.0 specification, Postman collection, curl scripts, webhook receivers (Node.js, Python, PHP), Python client.
