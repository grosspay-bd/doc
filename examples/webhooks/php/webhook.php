<?php
/**
 * GrossPay webhook receiver — plain PHP (7.4+ / 8.x, ext-openssl, ext-json)
 *
 * Local test:
 *   GROSSPAY_WEBHOOK_PUBLIC_KEY_FILE=../../../keys/sandbox-test-merchant.test.pem \
 *   GROSSPAY_ALLOWED_IPS='*' php -S 127.0.0.1:3000 webhook.php
 *
 * Production: point your callback_uri route at this file (nginx/Apache), keep the
 * public key outside the web root, and replace the JSON-file "db" with your database
 * (apply the event inside a transaction with SELECT ... FOR UPDATE).
 */
declare(strict_types=1);

const FINAL_STATES     = ['posted', 'part_posted', 'unposted', 'returned'];
const NON_FINAL_STATES = ['received', 'queued'];

function respond(int $code): void {
    http_response_code($code);
    exit;
}

function verifySignature(string $rawBody, ?string $signatureHeader, string $publicKeyPem): bool {
    if (!$signatureHeader) return false;
    $signature = base64_decode($signatureHeader, true);
    if ($signature === false) return false;
    return openssl_verify($rawBody, $signature, $publicKeyPem, OPENSSL_ALGO_SHA256) === 1;
}

/** Decimal string -> integer minor units ("1000.00" -> 100000). Never use float for money. */
function toCents(?string $amount): int {
    if ($amount === null || $amount === '') return 0;
    $parts = explode('.', $amount, 2);
    $frac  = substr(($parts[1] ?? '') . '00', 0, 2);
    return (int)$parts[0] * 100 + (int)$frac;
}

function targetCents(array $e): int {
    return in_array($e['posting_state'] ?? null, ['posted', 'part_posted'], true)
        ? toCents($e['amount_posted'] ?? null)
        : 0;
}

/** Idempotent, order-tolerant state application. */
function applyEvent(array $e, array &$db): string {
    $pid = $e['payment_id'];
    $cur = $db['payments'][$pid] ?? ['posting_state' => null, 'amount_posted' => null, 'booked_cents' => 0];

    if ($cur['posting_state'] === ($e['posting_state'] ?? null)
        && $cur['amount_posted'] === ($e['amount_posted'] ?? null)) {
        return 'duplicate';
    }
    if (in_array($cur['posting_state'], FINAL_STATES, true)
        && in_array($e['posting_state'] ?? null, NON_FINAL_STATES, true)) {
        return 'stale (step back to non-final state ignored)';
    }

    $delta = targetCents($e) - $cur['booked_cents'];
    if ($delta !== 0) {
        // Pay-in: +delta to customer balance. Pay-out: delta is the final debit.
        $db['ledger'][] = ['payment_id' => $pid, 'merchant_ref' => $e['merchant_ref'] ?? null, 'delta_cents' => $delta];
    }
    $db['payments'][$pid] = [
        'posting_state' => $e['posting_state'] ?? null,
        'amount_posted' => $e['amount_posted'] ?? null,
        'booked_cents'  => $cur['booked_cents'] + $delta,
    ];
    return sprintf('applied %s -> %s, delta %d', $cur['posting_state'] ?? '-', $e['posting_state'] ?? '-', $delta);
}

// ---- request handling -------------------------------------------------------
$path = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH);
if ($path !== '/webhooks/grosspay') respond(404);
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') respond(404); // never 405 here: 405 = "merchant refuses payment"

$allowed = array_map('trim', explode(',', getenv('GROSSPAY_ALLOWED_IPS') ?: '136.148.218.118'));
$ip = $_SERVER['REMOTE_ADDR'] ?? '';
if (!in_array('*', $allowed, true) && !in_array($ip, $allowed, true)) {
    error_log("grosspay: rejected webhook from $ip");
    respond(403);
}

$raw = file_get_contents('php://input');               // raw bytes — verify BEFORE json_decode
$publicKey = file_get_contents(getenv('GROSSPAY_WEBHOOK_PUBLIC_KEY_FILE'));
if ($raw === false || $publicKey === false
    || !verifySignature($raw, $_SERVER['HTTP_SIGNATURE_V1'] ?? null, $publicKey)) {
    error_log('grosspay: invalid signature');
    respond(401);
}

$event = json_decode($raw, true);
if (!is_array($event) || empty($event['payment_id'])) respond(400);

try {
    $dbFile = sys_get_temp_dir() . '/grosspay_example_db.json';
    $fh = fopen($dbFile, 'c+');
    flock($fh, LOCK_EX);
    $db = json_decode(stream_get_contents($fh) ?: '', true) ?: ['payments' => [], 'ledger' => []];
    $result = applyEvent($event, $db);
    ftruncate($fh, 0); rewind($fh);
    fwrite($fh, json_encode($db));
    flock($fh, LOCK_UN); fclose($fh);
    error_log("grosspay: [{$event['payment_id']}] " . ($event['merchant_ref'] ?? '') . ": $result");
} catch (Throwable $t) {
    error_log('grosspay: processing failed: ' . $t->getMessage());
    respond(503); // GrossPay will retry
}

respond(200);
