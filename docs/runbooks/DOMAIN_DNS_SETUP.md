# Domain + DNS Setup for Netlify (`mojowatson.co.uk`)

## Scope
This runbook covers DNS records for attaching a Netlify-hosted site to a custom domain under `mojowatson.co.uk`, with both recommended and fallback record sets.

Use with:
- `docs/runbooks/NETLIFY_DEPLOYMENT.md`

---

## Inputs you need first
From Netlify Domain management, collect:
1. **Custom hostname** (example: `screening.mojowatson.co.uk`)
2. **Netlify target** (usually `<site-name>.netlify.app`)

---

## Recommended record set (subdomain attach)

For a subdomain (recommended for this project):

| Type | Name/Host | Value/Target | TTL |
|---|---|---|---|
| CNAME | `screening` (or chosen label) | `<site-name>.netlify.app` | 300 |

Notes:
- Replace `screening` with your chosen host label.
- In Cloudflare, start with **Proxy OFF (DNS only)** until Netlify verifies.

---

## Fallback record sets

### Fallback A: Provider requires ALIAS/ANAME (flattening style)

| Type | Name/Host | Value/Target | TTL |
|---|---|---|---|
| ALIAS/ANAME | `@` or specific host | `<site-name>.netlify.app` | 300 |

Use when:
- provider does not allow required CNAME behavior,
- or apex mapping needs flattening.

### Fallback B: Apex/root on providers without ALIAS support

If mapping root `mojowatson.co.uk` directly and ALIAS/ANAME is unavailable:

| Type | Name/Host | Value | TTL |
|---|---|---|---|
| A | `@` | `75.2.60.5` | 300 |
| A | `@` | `99.83.190.102` | 300 |

Also add `www` as:

| Type | Name/Host | Value/Target | TTL |
|---|---|---|---|
| CNAME | `www` | `<site-name>.netlify.app` | 300 |

(Validate current Netlify guidance in the Netlify UI; provider behavior can vary.)

---

## Netlify-side domain attach sequence

1. Netlify → Site → **Domain management** → **Add a domain**.
2. Enter full host (e.g. `screening.mojowatson.co.uk`).
3. Add DNS record(s) at DNS provider per tables above.
4. Return to Netlify and click **Verify DNS configuration**.
5. Wait for certificate provisioning and confirm HTTPS is active.

---

## Verification commands

```bash
dig +short screening.mojowatson.co.uk CNAME
dig +short screening.mojowatson.co.uk A
curl -I https://screening.mojowatson.co.uk/
```

Expected:
- DNS resolves to Netlify target/load balancer,
- HTTPS returns `200` or redirect to explainer page.

---

## Rollback (DNS)

If cutover fails:
1. Restore previous DNS record values.
2. Keep previous host alive until TTL expires.
3. Re-verify service health before retry.

---

## Change control checklist

- [ ] Host label confirmed (e.g. `screening`).
- [ ] Netlify target copied exactly.
- [ ] Correct record type chosen (CNAME vs ALIAS vs A fallback).
- [ ] Proxy/CDN mode disabled during verification (if applicable).
- [ ] HTTPS validated after DNS propagation.
