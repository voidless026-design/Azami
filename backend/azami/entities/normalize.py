"""Value normalization to canonical forms.

This is the answer to "how does 'Mobile Phone Number' from one source and 'Cell Number' from
another become the same field": callers map raw field names to canonical field names, and the
values pass through these normalizers so they land in one canonical representation.
"""
from __future__ import annotations

import ipaddress
import re

import phonenumbers

from azami.scope.canonical import canonicalize

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_domain(host: str) -> str:
    return canonicalize(host).value


def normalize_ip(ip: str) -> str | None:
    try:
        return str(ipaddress.ip_address(ip.strip()))
    except ValueError:
        return None


def normalize_email(email: str) -> str | None:
    e = email.strip().lower()
    if not _EMAIL_RE.match(e):
        return None
    return e


def email_domain(email: str) -> str | None:
    e = normalize_email(email)
    return e.split("@", 1)[1] if e else None


def normalize_phone(raw: str, region: str | None = None) -> str | None:
    """Return an E.164 string, or None if it can't be parsed as a valid number."""
    try:
        num = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(num):
        return None
    return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)


# Canonical field-name mapping: raw source field -> canonical field.
FIELD_MAP = {
    "cell": "phone",
    "cell number": "phone",
    "mobile": "phone",
    "mobile phone number": "phone",
    "telephone": "phone",
    "tel": "phone",
    "landline": "phone",
    "e-mail": "email",
    "email address": "email",
    "mail": "email",
    "full name": "name",
    "fullname": "name",
    "organisation": "org",
    "organization": "org",
    "company": "org",
    "ip address": "ip",
    "ipaddr": "ip",
}


def canonical_field(name: str) -> str:
    return FIELD_MAP.get(name.strip().lower(), name.strip().lower())
