# Domain + DNS Setup (Compendium + Shared LAB strategy)

## Scope
This runbook covers DNS records for:
1. Netlify-hosted compendium site under `ojwatson.co.uk`.
2. Shared LAB hostname strategy (pointing to Render or another LAB host).

Use with:
- `docs/runbooks/NETLIFY_DEPLOYMENT.md`
- `DEPLOY_CHECKLIST.md`

---

## Inputs you need first

From Netlify Domain management:
1. **Compendium hostname** (example: `asys.ojwatson.co.uk`)
2. **Netlify target** (usually `<site-name>.netlify.app`)

From LAB hosting provider (e.g., Render):
3. **Shared LAB hostname** (example: `lab.ojwatson.co.uk`)
4. **LAB provider target** (Render default hostname or CNAME target)

---

## Recommended record set (subdomains)

### A) Compendium site on Netlify

| Type | Name/Host | Value/Target | TTL |
|---|---|---|---|
| CNAME | `asys` | `<site-name>.netlify.app` | 300 |

### B) Shared LAB gateway hostname

| Type | Name/Host | Value/Target | TTL |
|---|---|---|---|
| CNAME | `lab` | `<render-service>.onrender.com` (or provider equivalent) | 300 |

Notes:
- In Cloudflare, start with **Proxy OFF (DNS only)** during verification.
- Point project-specific legacy LAB hosts (if retained) to old endpoints until decommission complete.

---

## Fallback record sets

### Fallback A: Provider requires ALIAS/ANAME

| Type | Name/Host | Value/Target | TTL |
|---|---|---|---|
| ALIAS/ANAME | `@` or specific host | provider target | 300 |

### Fallback B: Apex/root without ALIAS support (Netlify)

| Type | Name/Host | Value | TTL |
|---|---|---|---|
| A | `@` | `75.2.60.5` | 300 |
| A | `@` | `99.83.190.102` | 300 |

And optionally:

| Type | Name/Host | Value/Target | TTL |
|---|---|---|---|
| CNAME | `www` | `<site-name>.netlify.app` | 300 |

---

## Attach + verify sequence

1. Add compendium domain in Netlify (`asys.ojwatson.co.uk`).
2. Add DNS CNAME record for `asys`.
3. Verify Netlify domain and wait for certificate provisioning.
4. Add LAB DNS CNAME (e.g., `lab`) to your LAB provider target.
5. Validate LAB TLS on provider side.
6. Update `app/data/compendium_catalog.json` URLs to match live domains.
7. Redeploy static site.

---

## Verification commands

```bash
dig +short asys.ojwatson.co.uk CNAME
dig +short lab.ojwatson.co.uk CNAME
curl -I https://asys.ojwatson.co.uk/
curl -I https://lab.ojwatson.co.uk/
```

Expected:
- DNS resolves to intended targets,
- HTTPS succeeds,
- compendium and LAB endpoints are reachable.

---

## Rollback (DNS)

If cutover fails:
1. Restore previous DNS record values.
2. Keep previous host active until TTL expires.
3. Re-verify health before retry.

---

## Change control checklist

- [ ] Compendium host label confirmed (e.g. `asys`).
- [ ] Shared LAB host label confirmed (e.g. `lab`).
- [ ] Correct CNAME/ALIAS/A records chosen.
- [ ] Proxy/CDN mode disabled during verification (if applicable).
- [ ] HTTPS validated for both compendium + LAB endpoints.
