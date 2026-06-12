from __future__ import annotations

import base64
import hashlib
import hmac
import time
from dataclasses import dataclass


class WebhookVerificationError(ValueError):
    pass


@dataclass(frozen=True)
class WebhookHeaders:
    webhook_id: str | None
    webhook_timestamp: str | None
    webhook_signature: str | None
    x_webhook_timestamp: str | None
    x_webhook_signature: str | None


def verify_webhook_signature(
    *,
    body: bytes,
    secret: str,
    headers: WebhookHeaders,
    max_age_seconds: int = 300,
) -> None:
    if not secret.strip():
        raise WebhookVerificationError("Linq webhook secret is not configured.")

    if _verify_standard_webhooks(body=body, secret=secret, headers=headers, max_age_seconds=max_age_seconds):
        return
    if _verify_legacy_webhook(body=body, secret=secret, headers=headers, max_age_seconds=max_age_seconds):
        return

    raise WebhookVerificationError("Invalid Linq webhook signature.")


def _verify_standard_webhooks(
    *,
    body: bytes,
    secret: str,
    headers: WebhookHeaders,
    max_age_seconds: int,
) -> bool:
    if not headers.webhook_id or not headers.webhook_timestamp or not headers.webhook_signature:
        return False

    _reject_stale_timestamp(headers.webhook_timestamp, max_age_seconds)

    signed_content = f"{headers.webhook_id}.{headers.webhook_timestamp}.".encode("ascii") + body
    key = _decode_standard_webhook_secret(secret)
    expected = base64.b64encode(hmac.new(key, signed_content, hashlib.sha256).digest()).decode("ascii")

    for candidate in _signature_candidates(headers.webhook_signature):
        if hmac.compare_digest(expected, candidate):
            return True
    return False


def _verify_legacy_webhook(
    *,
    body: bytes,
    secret: str,
    headers: WebhookHeaders,
    max_age_seconds: int,
) -> bool:
    timestamp = headers.x_webhook_timestamp or headers.webhook_timestamp
    signature = headers.x_webhook_signature or headers.webhook_signature
    if not timestamp or not signature:
        return False

    _reject_stale_timestamp(timestamp, max_age_seconds)

    message = f"{timestamp}.".encode("utf-8") + body
    expected = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    for candidate in _signature_candidates(signature):
        if hmac.compare_digest(expected, candidate):
            return True
    return False


def _decode_standard_webhook_secret(secret: str) -> bytes:
    normalized = secret.strip()
    if normalized.startswith("whsec_"):
        normalized = normalized[len("whsec_") :]
    return base64.b64decode(normalized + "=" * (-len(normalized) % 4))


def _signature_candidates(signature_header: str) -> list[str]:
    values = [part.strip() for part in signature_header.split(",") if part.strip()]
    candidates: list[str] = []
    for value in values:
        if value.startswith("v1,"):
            candidates.append(value[3:])
        else:
            candidates.append(value)
    return candidates


def _reject_stale_timestamp(timestamp: str, max_age_seconds: int) -> None:
    try:
        sent_at = int(timestamp)
    except ValueError as exc:
        raise WebhookVerificationError("Invalid webhook timestamp.") from exc

    now = int(time.time())
    if abs(now - sent_at) > max_age_seconds:
        raise WebhookVerificationError("Webhook timestamp is too old.")
