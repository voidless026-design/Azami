"""The most important suite in the project: prove the gate lets in only what it should."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from azami.scope.engine import ScopeEngine
from azami.scope.schema import Action, Scope

NOW = datetime(2026, 9, 20, 6, 0, tzinfo=timezone.utc)  # a Sunday, outside the blackout


def make_scope() -> Scope:
    return Scope.model_validate(
        {
            "schema_version": 1,
            "engagement": {
                "id": "ENG-TEST",
                "client_name": "Example Corp",
                "assessing_org": "Test Firm",
                "authorization_ref": "SOW-1",
            },
            "time_window": {
                "not_before": "2026-09-15T00:00:00Z",
                "not_after": "2026-09-30T23:59:59Z",
                "blackout_windows": [
                    {"days": ["Mon", "Tue", "Wed", "Thu", "Fri"], "start": "13:00Z", "end": "21:00Z"}
                ],
            },
            "in_scope": [
                {
                    "name": "web",
                    "domains": ["example.com", "*.example.com"],
                    "allowed_actions": {"passive": True, "active_scan": True},
                },
                {
                    "name": "net",
                    "ip_ranges": ["203.0.113.0/24"],
                    "allowed_actions": {"passive": True, "active_scan": True},
                },
                {
                    "name": "cred-test",
                    "hosts": ["staging.example.com"],
                    "allowed_actions": {
                        "passive": True,
                        "active_scan": True,
                        "active_testing": True,
                    },
                },
            ],
            "out_of_scope": {
                "hosts": ["payments.example.com"],
                "ip_ranges": ["203.0.113.200/29"],
            },
            "constraints": {"max_scan_rate_pps": 500},
        }
    )


@pytest.fixture
def engine() -> ScopeEngine:
    return ScopeEngine(make_scope(), signature_verified=True)


def test_in_scope_passive_allowed(engine):
    d = engine.check("example.com", Action.PASSIVE, now=NOW)
    assert d.allowed and d.asset_class == "web"


def test_wildcard_subdomain_allowed(engine):
    assert engine.check("api.example.com", Action.ACTIVE_SCAN, now=NOW).allowed


def test_bare_domain_not_matched_by_wildcard_only():
    scope = make_scope()
    scope.in_scope[0].domains = ["*.example.com"]  # wildcard only
    e = ScopeEngine(scope)
    assert not e.check("example.com", Action.PASSIVE, now=NOW).allowed
    assert e.check("a.example.com", Action.PASSIVE, now=NOW).allowed


def test_out_of_scope_denied(engine):
    d = engine.check("notexample.org", Action.PASSIVE, now=NOW)
    assert not d.allowed and d.reason == "not in scope"


def test_exclusion_beats_inclusion(engine):
    # payments.example.com matches *.example.com but is explicitly excluded.
    d = engine.check("payments.example.com", Action.ACTIVE_SCAN, now=NOW)
    assert not d.allowed and "excluded" in d.reason


def test_ip_in_range_allowed(engine):
    assert engine.check("203.0.113.10", Action.ACTIVE_SCAN, now=NOW).allowed


def test_excluded_ip_within_range_denied(engine):
    # .200/29 covers .200-.207 and is excluded even though .0/24 is in scope.
    assert not engine.check("203.0.113.201", Action.ACTIVE_SCAN, now=NOW).allowed


def test_action_not_granted_denied(engine):
    # 'web' does not grant active_testing.
    d = engine.check("example.com", Action.ACTIVE_TESTING, now=NOW)
    assert not d.allowed and "not authorized" in d.reason


def test_intrusive_flag_set(engine):
    d = engine.check("staging.example.com", Action.ACTIVE_TESTING, now=NOW)
    assert d.allowed and d.intrusive


def test_outside_time_window_denied(engine):
    later = datetime(2026, 10, 5, 6, 0, tzinfo=timezone.utc)
    assert not engine.check("example.com", Action.PASSIVE, now=later).allowed


def test_blackout_denies_active_but_allows_passive(engine):
    # Monday 14:00Z is inside the blackout.
    monday_1400 = datetime(2026, 9, 21, 14, 0, tzinfo=timezone.utc)
    assert not engine.check("example.com", Action.ACTIVE_SCAN, now=monday_1400).allowed
    assert engine.check("example.com", Action.PASSIVE, now=monday_1400).allowed


def test_url_and_case_normalized(engine):
    assert engine.check("HTTPS://API.Example.com/login", Action.ACTIVE_SCAN, now=NOW).allowed
