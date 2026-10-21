/**
 * GrossPay webhook receiver — Node.js + Express
 *
 *   npm install
 *   GROSSPAY_WEBHOOK_PUBLIC_KEY_FILE=../../../keys/sandbox-test-merchant.test.pem node server.js
 *
 * Env:
 *   GROSSPAY_WEBHOOK_PUBLIC_KEY_FILE  path to the PEM public key (required)
 *   GROSSPAY_ALLOWED_IPS              comma-separated, default 136.148.218.118 ("*" disables the check, tests only)
 *   TRUST_PROXY                       Express "trust proxy" setting if you run behind a load balancer
 *   PORT                              default 3000
 *
 * The in-memory "db" below stands in for your database. In production, wrap
 * applyEvent() in a DB transaction with a row lock (SELECT ... FOR UPDATE).
 */
'use strict';

const crypto = require('crypto');
const fs = require('fs');
const express = require('express');

const PUBLIC_KEY = fs.readFileSync(process.env.GROSSPAY_WEBHOOK_PUBLIC_KEY_FILE, 'utf8');
const ALLOWED_IPS = (process.env.GROSSPAY_ALLOWED_IPS || '136.148.218.118').split(',').map((s) => s.trim());
const PORT = Number(process.env.PORT || 3000);

const FINAL = new Set(['posted', 'part_posted', 'unposted', 'returned']);
const NON_FINAL = new Set(['received', 'queued']);

// ---- stand-in for your database -------------------------------------------
const db = new Map(); // key: payment_id -> { posting_state, amount_posted, booked_cents }
const ledger = [];    // ledger entries written by applyEvent()

// ---- helpers ---------------------------------------------------------------
function verifySignature(rawBody, signatureHeader) {
  if (!signatureHeader) return false;
  try {
    return crypto.verify('sha256', rawBody, PUBLIC_KEY, Buffer.from(signatureHeader, 'base64'));
  } catch {
    return false;
  }
}

/** "1000.00" -> 100000 (integer minor units; never use floats for money) */
function toCents(amount) {
  if (amount === null || amount === undefined) return 0;
  const [whole, frac = ''] = String(amount).split('.');
  return Number(whole) * 100 + Number((frac + '00').slice(0, 2)) * (whole.startsWith('-') ? -1 : 1);
}

/** How much should be booked for this payment in its current state. */
function targetCents(event) {
  return event.posting_state === 'posted' || event.posting_state === 'part_posted'
    ? toCents(event.amount_posted)
    : 0;
}

/** Idempotent, order-tolerant state application. Returns a short description. */
function applyEvent(event) {
  const current = db.get(event.payment_id) || { posting_state: null, amount_posted: null, booked_cents: 0 };

  if (current.posting_state === event.posting_state && current.amount_posted === (event.amount_posted ?? null)) {
    return 'duplicate';
  }
  if (FINAL.has(current.posting_state) && NON_FINAL.has(event.posting_state)) {
    return 'stale (step back to non-final state ignored)';
  }

  const delta = targetCents(event) - current.booked_cents;
  if (delta !== 0) {
    // Pay-in: +delta to the customer's balance. Pay-out: delta is the final debit (release/return the rest).
    ledger.push({ payment_id: event.payment_id, merchant_ref: event.merchant_ref, delta_cents: delta });
  }
  db.set(event.payment_id, {
    posting_state: event.posting_state,
    amount_posted: event.amount_posted ?? null,
    booked_cents: current.booked_cents + delta,
  });
  return `applied ${current.posting_state ?? '∅'} → ${event.posting_state}, delta ${delta / 100}`;
}

// ---- app -------------------------------------------------------------------
const app = express();
if (process.env.TRUST_PROXY) app.set('trust proxy', process.env.TRUST_PROXY);

// IMPORTANT: raw body parser on this route only — the signature covers raw bytes.
app.post('/webhooks/grosspay', express.raw({ type: '*/*', limit: '1mb' }), (req, res) => {
  const ip = (req.ip || '').replace(/^::ffff:/, '');
  if (!ALLOWED_IPS.includes('*') && !ALLOWED_IPS.includes(ip)) {
    console.warn(`rejected webhook from ${ip}`);
    return res.sendStatus(403);
  }

  const raw = req.body; // Buffer
  if (!Buffer.isBuffer(raw) || !verifySignature(raw, req.get('signature-v1'))) {
    console.warn('invalid signature');
    return res.sendStatus(401);
  }

  let event;
  try {
    event = JSON.parse(raw.toString('utf8'));
  } catch {
    return res.sendStatus(400);
  }

  try {
    const result = applyEvent(event);
    console.log(`[${event.payment_id}] ${event.merchant_ref}: ${result}`);
    return res.sendStatus(200);
  } catch (err) {
    console.error('processing failed', err);
    return res.sendStatus(503); // GrossPay will retry
  }
});

// Debug endpoint for local testing only — remove in production.
app.get('/debug/ledger', (_req, res) => res.json({ payments: Object.fromEntries(db), ledger }));

if (require.main === module) {
  app.listen(PORT, () => console.log(`GrossPay webhook receiver on :${PORT}/webhooks/grosspay`));
}

module.exports = { app, applyEvent, toCents, verifySignature };
