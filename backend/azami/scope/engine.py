"""The Scope Engine — the single, unavoidable gate in front of every target/action.

`ScopeEngine.check(target, action)` is called by every collector, tool wrapper, and playbook
step. There is no bypass and no force flag. Exclusions always win; canonicalization happens
before matching; the time window and blackout windows are enforced.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timezone

import yaml

from azami.scope.canonical import (
    CanonicalTarget,
    TargetKind,
    canonicalize,
    domain_matches,
    ip_in_range,
)
from azami.scope.schema import Action, AssetClass, Scope
from azami.scope.signature import SignatureError, verify_ed25519

_WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    asset_class: str | None = None
    intrusive: bool = False
    constraints: dict = field(default_factory=dict)

    def __str__(self) -> str:
        return f"allow ({self.asset_class})" if self.allowed else f"deny: {self.reason}"


class ScopeLoadError(Exception):
    pass


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _parse_hhmm(text: str) -> time:
    text = text.strip().rstrip("Zz")
    hh, mm = text.split(":")
    return time(int(hh), int(mm), tzinfo=timezone.utc)


def load_scope(scope_text: str, *, allow_unsigned: bool, signature_b64: str | None = None):
    """Parse + validate + verify a scope file.

    Returns (Scope, signature_verified). Raises ScopeLoadError on parse/validation failure
    and SignatureError when a signature is present but invalid, or required but missing.
    """
    try:
        data = yaml.safe_load(scope_text)
    except yaml.YAMLError as exc:
        raise ScopeLoadError(f"invalid YAML/JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ScopeLoadError("scope file must be a mapping")

    try:
        scope = Scope.model_validate(data)
    except Exception as exc:  # pydantic ValidationError
        raise ScopeLoadError(f"scope schema validation failed: {exc}") from exc

    pubkey = scope.integrity.authorizer_pubkey
    signature_verified = False
    if signature_b64 and pubkey:
        # verify_ed25519 raises SignatureError on failure (propagated to caller).
        verify_ed25519(scope_text.encode("utf-8"), signature_b64, pubkey)
        signature_verified = True
    elif not allow_unsigned:
        raise SignatureError(
            "scope is unsigned or missing a public key, and unsigned scopes are not allowed"
        )

    return scope, signature_verified


class ScopeEngine:
    """Holds one loaded scope and answers allow/deny for (target, action)."""

    def __init__(self, scope: Scope, signature_verified: bool = False):
        self.scope = scope
        self.signature_verified = signature_verified

    # -- time -----------------------------------------------------------------
    def _within_window(self, now: datetime) -> bool:
        return _aware(self.scope.time_window.not_before) <= now <= _aware(
            self.scope.time_window.not_after
        )

    def _in_blackout(self, now: datetime) -> bool:
        for bw in self.scope.time_window.blackout_windows:
            days = {_WEEKDAYS.get(d.strip().lower()[:3], -1) for d in bw.days}
            if now.weekday() not in days:
                continue
            start, end = _parse_hhmm(bw.start), _parse_hhmm(bw.end)
            if start <= now.timetz() < end:
                return True
        return False

    # -- matching -------------------------------------------------------------
    @staticmethod
    def _matches(ct: CanonicalTarget, *, domains, ip_ranges, hosts) -> bool:
        if ct.kind is TargetKind.IP:
            if ct.value in {h.strip().lower() for h in hosts}:
                return True
            return any(ip_in_range(ct.value, cidr) for cidr in ip_ranges)
        # domain
        if ct.value in {h.strip().lower() for h in hosts}:
            return True
        return any(domain_matches(p, ct.value) for p in domains)

    def _matching_classes(self, ct: CanonicalTarget) -> list[AssetClass]:
        out: list[AssetClass] = []
        for cls in self.scope.in_scope:
            hosts = list(cls.hosts) + [canonicalize(u).value for u in cls.urls]
            if self._matches(ct, domains=cls.domains, ip_ranges=cls.ip_ranges, hosts=hosts):
                out.append(cls)
        return out

    def _excluded(self, ct: CanonicalTarget) -> bool:
        oos = self.scope.out_of_scope
        return self._matches(ct, domains=oos.domains, ip_ranges=oos.ip_ranges, hosts=oos.hosts)

    # -- the decision ---------------------------------------------------------
    def check(self, target: str, action: Action, *, now: datetime | None = None) -> Decision:
        now = now or datetime.now(timezone.utc)
        ct = canonicalize(target)

        # 1. Exclusions always win, checked first.
        if self._excluded(ct):
            return Decision(False, "excluded (out of scope)")

        # 2. Time window applies to all actions.
        if not self._within_window(now):
            return Decision(False, "outside authorized time window")

        # 3. Blackout windows deny everything except passive observation.
        if action is not Action.PASSIVE and self._in_blackout(now):
            return Decision(False, "blackout window (active actions paused)")

        # 4. Must fall inside at least one in-scope asset class.
        matches = self._matching_classes(ct)
        if not matches:
            return Decision(False, "not in scope")

        # 5. Grants are additive across matching classes: allow if ANY matching class grants
        #    the action (a specific grant is not shadowed by a broader wildcard class).
        granting = [c for c in matches if c.allowed_actions.grants(action)]
        if not granting:
            return Decision(
                False, f"action '{action.value}' not authorized for asset '{matches[0].name}'"
            )
        cls = granting[0]

        intrusive = action.value in ("active_testing", "exploitation")
        return Decision(
            True,
            "allowed",
            asset_class=cls.name,
            intrusive=intrusive,
            constraints=self.scope.constraints.model_dump(),
        )
