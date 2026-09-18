"""Canonical entity types."""
from __future__ import annotations

from enum import Enum


class EntityType(str, Enum):
    ORGANIZATION = "organization"
    PERSON = "person"  # only as part of an authorized attack surface; minimized
    DOMAIN = "domain"
    HOST = "host"
    IP = "ip"
    NETBLOCK = "netblock"
    SERVICE = "service"
    EMAIL = "email"
    PHONE = "phone"
    CREDENTIAL = "credential"  # hash/exposure reference; never plaintext
    SOCIAL_PROFILE = "social_profile"
    LOCATION = "location"
    CERTIFICATE = "certificate"
    FINDING = "finding"
