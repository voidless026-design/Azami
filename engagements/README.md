# Engagements

Rules-of-engagement (RoE) / scope definitions for authorized security testing.

## `scope.example.yaml`

A template for a real penetration test or red team engagement. Copy it per
engagement and fill in every `<PLACEHOLDER>`.

**Nothing in this directory is authorization to test anything.** Testing may
begin only when:

1. All placeholders are replaced with real, agreed values.
2. The client's authorizing contact has signed the `signatures` block and can
   demonstrate ownership of / authority over every in-scope asset.
3. The provider's engagement lead has countersigned.
4. Any third-party infrastructure owners (cloud, hosting, SaaS) have been
   notified or approved where their terms require it.

### Design principles

- **Everything not listed as in-scope is out of scope.**
- **High-impact techniques are opt-in.** DoS, social engineering of real staff,
  physical intrusion, destructive actions, and exfiltration of real data all
  default to `false` and require explicit written approval.
- **Real data is protected.** Encountered PII is not copied; synthetic markers
  are used to prove access.
- **Either party can stop testing at any time** via the emergency-stop contacts.
- **Scope changes require re-approval** and a version bump before taking effect.

### Usage

```
cp engagements/scope.example.yaml engagements/<engagement-id>.yaml
# fill in placeholders, get signatures, set status: approved
```
