"""Thin Paystack client: initialize, verify, webhook signature check.

Amounts are in subunits (KES × 100).
"""
import hashlib
import hmac

import requests
from django.conf import settings

API = "https://api.paystack.co"
TIMEOUT = 20


class PaystackError(Exception):
    pass


def _headers():
    if not settings.PAYSTACK_SECRET_KEY:
        raise PaystackError("PAYSTACK_SECRET_KEY is not configured")
    return {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}", "Content-Type": "application/json"}


def initialize(*, email: str, amount_subunits: int, reference: str, callback_url: str, metadata: dict) -> str:
    """Create a transaction and return the hosted checkout URL."""
    resp = requests.post(
        f"{API}/transaction/initialize",
        json={
            "email": email,
            "amount": amount_subunits,
            "currency": "KES",
            "reference": reference,
            "callback_url": callback_url,
            "channels": ["mobile_money", "card"],
            "metadata": metadata,
        },
        headers=_headers(),
        timeout=TIMEOUT,
    )
    body = resp.json()
    if resp.status_code != 200 or not body.get("status"):
        raise PaystackError(body.get("message", "Could not start payment"))
    return body["data"]["authorization_url"]


def verify(reference: str) -> dict:
    """Server-side truth for a transaction. Never trust the browser redirect alone."""
    resp = requests.get(f"{API}/transaction/verify/{reference}", headers=_headers(), timeout=TIMEOUT)
    body = resp.json()
    if resp.status_code != 200 or not body.get("status"):
        raise PaystackError(body.get("message", "Could not verify payment"))
    return body["data"]


def valid_signature(raw_body: bytes, signature: str) -> bool:
    expected = hmac.new(settings.PAYSTACK_SECRET_KEY.encode(), raw_body, hashlib.sha512).hexdigest()
    return bool(signature) and hmac.compare_digest(expected, signature)
