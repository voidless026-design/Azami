"""Passive OSINT collectors. All are keyed to authorized assets and hit official
sources / public APIs with short timeouts and defensive error handling."""
from __future__ import annotations

import asyncio

import httpx

from azami.entities.canonical import EntityType
from azami.osint.base import Collector, RawRecord

_HTTP_TIMEOUT = httpx.Timeout(15.0, connect=8.0)
_UA = "Azami-Recon/0.1 (authorized security assessment)"


class DNSCollector(Collector):
    name = "dns"
    produces = [EntityType.DOMAIN, EntityType.IP]
    applies_to = {"domain"}

    async def collect(self, value: str, kind: str) -> list[RawRecord]:
        return await asyncio.to_thread(self._resolve, value)

    def _resolve(self, domain: str) -> list[RawRecord]:
        import dns.resolver

        resolver = dns.resolver.Resolver()
        resolver.lifetime = 8.0
        resolver.timeout = 4.0
        fields: dict = {}
        records: list[RawRecord] = []
        for rtype in ("A", "AAAA", "MX", "NS", "TXT", "CNAME"):
            try:
                answers = resolver.resolve(domain, rtype)
            except Exception:
                continue
            values = [r.to_text().strip('"') for r in answers]
            fields[rtype.lower()] = values
            if rtype in ("A", "AAAA"):
                for ip in values:
                    records.append(
                        RawRecord(EntityType.IP, ip, {"ip": ip, "resolved_from": domain})
                    )
        records.insert(0, RawRecord(EntityType.DOMAIN, domain, {"domain": domain, **fields}))
        return records


class RDAPCollector(Collector):
    name = "rdap"
    produces = [EntityType.DOMAIN, EntityType.IP, EntityType.ORGANIZATION]
    applies_to = {"domain", "ip"}

    async def collect(self, value: str, kind: str) -> list[RawRecord]:
        path = "domain" if kind == "domain" else "ip"
        url = f"https://rdap.org/{path}/{value}"
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, headers={"User-Agent": _UA}) as c:
            resp = await c.get(url, follow_redirects=True)
            if resp.status_code != 200:
                return []
            data = resp.json()
        fields: dict = {"handle": data.get("handle")}
        for ev in data.get("events", []):
            action = ev.get("eventAction", "").replace(" ", "_")
            if action:
                fields[f"event_{action}"] = ev.get("eventDate")
        records: list[RawRecord] = []
        org = _rdap_registrant(data)
        if org:
            fields["registrant_org"] = org
            records.append(RawRecord(EntityType.ORGANIZATION, org, {"name": org, "via": "rdap"}))
        etype = EntityType.DOMAIN if kind == "domain" else EntityType.IP
        key = "domain" if kind == "domain" else "ip"
        records.insert(0, RawRecord(etype, value, {key: value, **fields}))
        return records


def _rdap_registrant(data: dict) -> str | None:
    for ent in data.get("entities", []):
        roles = ent.get("roles", [])
        if "registrant" in roles or "administrative" in roles:
            for item in ent.get("vcardArray", [[], []])[1]:
                if item and item[0] == "fn":
                    return item[3]
    return None


class CrtShCollector(Collector):
    name = "crtsh"
    produces = [EntityType.HOST, EntityType.DOMAIN]
    applies_to = {"domain"}

    async def collect(self, value: str, kind: str) -> list[RawRecord]:
        url = f"https://crt.sh/?q=%25.{value}&output=json"
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, headers={"User-Agent": _UA}) as c:
            resp = await c.get(url)
            if resp.status_code != 200:
                return []
            try:
                data = resp.json()
            except Exception:
                return []
        hosts: set[str] = set()
        for row in data:
            for name in str(row.get("name_value", "")).splitlines():
                name = name.strip().lstrip("*.").lower()
                if name and "@" not in name and name.endswith(value):
                    hosts.add(name)
        records = [
            RawRecord(EntityType.HOST, h, {"host": h, "via": "crtsh"}) for h in sorted(hosts)
        ]
        records.insert(
            0, RawRecord(EntityType.DOMAIN, value, {"domain": value, "subdomains": sorted(hosts)})
        )
        return records


class GeoIPCollector(Collector):
    name = "geoip"
    produces = [EntityType.LOCATION, EntityType.IP]
    applies_to = {"ip"}

    async def collect(self, value: str, kind: str) -> list[RawRecord]:
        url = f"https://ipapi.co/{value}/json/"
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, headers={"User-Agent": _UA}) as c:
            resp = await c.get(url)
            if resp.status_code != 200:
                return []
            data = resp.json()
        if data.get("error"):
            return []
        loc = {
            "city": data.get("city"),
            "region": data.get("region"),
            "country": data.get("country_name"),
            "lat": data.get("latitude"),
            "lon": data.get("longitude"),
            "org": data.get("org"),
        }
        loc_key = f"{loc.get('city')},{loc.get('region')},{loc.get('country')}"
        return [
            RawRecord(
                EntityType.IP, value, {"ip": value, "geo": loc_key, "asn_org": loc.get("org")}
            ),
            RawRecord(EntityType.LOCATION, loc_key, loc),
        ]


class BreachCollector(Collector):
    name = "breach"
    produces = [EntityType.CREDENTIAL]
    applies_to = {"email", "domain"}
    enabled = False  # requires an API key (AZAMI_HIBP_API_KEY); report-only

    async def collect(self, value: str, kind: str) -> list[RawRecord]:
        # Intentionally reports exposure only; never retrieves or reuses credentials.
        return []
