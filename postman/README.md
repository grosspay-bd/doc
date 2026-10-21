# Postman

1. **Import** all three files into Postman (*File → Import*):
   - `GrossPay-BD.postman_collection.json`
   - `GrossPay-BD-Test.postman_environment.json`
   - `GrossPay-BD-Production.postman_environment.json`
2. Select the **GrossPay BD — Test** environment and paste your test API key into `apiKey` (it's marked *secret*; don't export environments with real keys into Git).
3. Set `callbackUri` to your webhook endpoint or a request-bin URL to watch webhooks.
4. Run **Payments → Create pay-in (debit)**. The collection stores `paymentId` / `merchantRef` automatically, so **Get state** requests work right after.

`merchant_ref` is generated per request (`order_bd_<timestamp>` / `withdraw_bd_<timestamp>`) to avoid accidental duplicates.

Alternatively import [`../openapi/openapi.yaml`](../openapi/openapi.yaml) directly — Postman builds a collection from the OpenAPI spec.
