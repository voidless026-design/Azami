"""Normalization, confidence, and entity resolution (dedup + corroboration)."""
from __future__ import annotations

from azami.entities import service
from azami.entities.canonical import EntityType
from azami.entities.confidence import corroborate, source_weight
from azami.entities.normalize import (
    canonical_field,
    email_domain,
    normalize_domain,
    normalize_ip,
    normalize_phone,
)


def test_field_mapping_unifies_names():
    assert canonical_field("Mobile Phone Number") == "phone"
    assert canonical_field("Cell Number") == "phone"
    assert canonical_field("E-Mail") == "email"


def test_phone_e164():
    assert normalize_phone("+1 (415) 555-2671") == "+14155552671"
    assert normalize_phone("(415) 555-2671", region="US") == "+14155552671"
    assert normalize_phone("not a phone") is None


def test_domain_and_ip_normalization():
    assert normalize_domain("HTTPS://API.Example.com/path") == "api.example.com"
    assert normalize_ip("2001:0DB8:0000:0000:0000:0000:0000:0001") == "2001:db8::1"
    assert normalize_ip("nope") is None
    assert email_domain("Alice@Example.COM") == "example.com"


def test_confidence_corroboration_increases():
    base = source_weight("dns")  # 0.85
    boosted = corroborate(base, source_weight("rdap"))
    assert boosted > base and boosted <= 1.0


def test_entity_dedup_and_merge(db):
    e1 = service.upsert_entity(
        db,
        engagement_id="ENG",
        entity_type=EntityType.IP,
        dedup_key="203.0.113.10",
        fields={"ip": "203.0.113.10"},
        source="dns",
    )
    e2 = service.upsert_entity(
        db,
        engagement_id="ENG",
        entity_type=EntityType.IP,
        dedup_key="203.0.113.10",
        fields={"asn_org": "Example Corp"},
        source="geoip",
    )
    assert e1.id == e2.id  # same entity
    assert e2.fields["ip"] == "203.0.113.10" and e2.fields["asn_org"] == "Example Corp"
    assert e2.confidence > source_weight("dns")  # corroborated upward
    assert len(e2.assertions) == 2


def test_graph_links_domain_to_ip(db):
    service.upsert_entity(
        db, engagement_id="ENG", entity_type=EntityType.DOMAIN, dedup_key="example.com",
        fields={"a": ["203.0.113.10"]}, source="dns",
    )
    service.upsert_entity(
        db, engagement_id="ENG", entity_type=EntityType.IP, dedup_key="203.0.113.10",
        fields={"ip": "203.0.113.10"}, source="dns",
    )
    g = service.build_graph(db, "ENG")
    assert len(g["nodes"]) == 2 and len(g["edges"]) == 1
