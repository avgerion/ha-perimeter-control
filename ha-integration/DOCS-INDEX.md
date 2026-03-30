# HA Integration Documentation Index

**Start here to find the right guide for your situation.**

---

## 🚀 I'm about to deploy — where do I start?

**Your exact sequence**:

1. [ROBUSTNESS-SUMMARY.md](ROBUSTNESS-SUMMARY.md) — 2 min read
   - Understand what issues were fixed
   - Overview of all documentation

2. [NETWORK-ARCHITECTURE.md](NETWORK-ARCHITECTURE.md) — 10 min read if single Pi, 20 if multi-Pi
   - Understand the port-sharing architecture
   - Find your Supervisor IP or hostname
   - Decide on IP vs mDNS vs public domain

3. [PRE-DEPLOYMENT-CHECKLIST.md](PRE-DEPLOYMENT-CHECKLIST.md) — 15-30 min, MUST do
   - Work through all 13 sections
   - **Don't skip any section**
   - This prevents 95% of deployment issues

4. [SAFE-DEPLOYMENT.md](SAFE-DEPLOYMENT.md) — Follow phases during actual deployment
   - Phase 1: Deploy to HACS or manual install
   - Phase 2: Verify card loads
   - Phase 3: Test functionality
   - Phase 4: Add more cards (if desired)
   - **Reference Rollback Procedures if something breaks**

5. [SAFETY-ARCHITECTURE.md](SAFETY-ARCHITECTURE.md) — Optional, builds confidence
   - Understand the three-layer protection
   - Learn what can't break even if card fails

---

## 🔍 Something broke — where do I look?

**Your exact sequence**:

1. [DIAGNOSTICS.md](DIAGNOSTICS.md) — START HERE
   - Find your error type (e.g., "Cannot reach API")
   - Follow diagnosis steps (will take 2-5 minutes)
   - See exact commands to run
   - Get quick fix

2. If DIAGNOSTICS.md doesn't solve it:
   - [NETWORK-ARCHITECTURE.md](NETWORK-ARCHITECTURE.md) Troubleshooting section
   - [SAFE-DEPLOYMENT.md](SAFE-DEPLOYMENT.md) Emergency Rollback Procedures

3. If still stuck:
   - Gather info from DIAGNOSTICS.md "When Nothing Else Works"
   - Create GitHub issue with details

---

## 📋 Building Custom Configuration

**Choose your scenario**:

### Single Raspberry Pi (most common)
1. [NETWORK-ARCHITECTURE.md](NETWORK-ARCHITECTURE.md) → "Pattern 1: Single Pi"
2. [example-lovelace-view.yaml](example-lovelace-view.yaml) → Copy single-Pi section
3. [PRE-DEPLOYMENT-CHECKLIST.md](PRE-DEPLOYMENT-CHECKLIST.md) → Section 4.1
4. Follow SAFE-DEPLOYMENT.md phases

### Multiple Pis (Fleet)
1. [NETWORK-ARCHITECTURE.md](NETWORK-ARCHITECTURE.md) → "Pattern 2: Multiple Pis"
2. [example-fleet-card.yaml](example-fleet-card.yaml) → Fleet view setup
3. [example-lovelace-view.yaml](example-lovelace-view.yaml) → Multi-Pi cards section
4. [PRE-DEPLOYMENT-CHECKLIST.md](PRE-DEPLOYMENT-CHECKLIST.md) → Section 4.2
5. Follow SAFE-DEPLOYMENT.md phases

### Remote Access via VPN or Public Domain
1. [NETWORK-ARCHITECTURE.md](NETWORK-ARCHITECTURE.md) → "HTTP vs HTTPS Section"
2. [PRE-DEPLOYMENT-CHECKLIST.md](PRE-DEPLOYMENT-CHECKLIST.md) → Section 8
3. Configure CORS in Supervisor (NETWORK-ARCHITECTURE.md section 6.2)
4. Deploy with HTTPS and certificate

---

## 🛡️ Understanding the Safety Systems

**Want to understand what protects your HA instance?**

1. [SAFETY-ARCHITECTURE.md](SAFETY-ARCHITECTURE.md) — Complete
   - Layer 1: Error Boundary component
   - Layer 2: Safe Loader with timeouts
   - Layer 3: Graceful degradation

2. [src/error-boundary.ts](src/error-boundary.ts) — Component code (170 lines)
3. [src/safe-loader.ts](src/safe-loader.ts) — Component code (280 lines)

---

## 📖 General Documentation

| Document | When to Read | Time |
|----------|--------------|------|
| [README.md](README.md) | First time, overview | 10 min |
| [QUICKSTART.md](QUICKSTART.md) | Quick install walkthrough | 5 min |
| [NETWORK-ARCHITECTURE.md](NETWORK-ARCHITECTURE.md) | Before deployment, multi-Pi setup | 10-20 min |
| [PRE-DEPLOYMENT-CHECKLIST.md](PRE-DEPLOYMENT-CHECKLIST.md) | **MUST do before HA deployment** | 15-30 min |
| [SAFE-DEPLOYMENT.md](SAFE-DEPLOYMENT.md) | During actual HA deployment | 20-30 min |
| [SAFETY-ARCHITECTURE.md](SAFETY-ARCHITECTURE.md) | Want to understand protection | 15 min |
| [DIAGNOSTICS.md](DIAGNOSTICS.md) | If something breaks | 5-10 min |
| [ROBUSTNESS-SUMMARY.md](ROBUSTNESS-SUMMARY.md) | Overview of what was fixed | 5 min |

---

## 💡 Quick Reference

### Find Supervisor IP
```bash
ssh pi@<your-pi-ip>
hostname -I
# Use output in api_base_url
```

### Verify API Works
```bash
curl http://<pi-ip>:8080/api/v1/services
# Should return JSON
```

### Required YAML Fields
```yaml
- type: custom:perimeter-control-card
  service_id: photo_booth             # ← Required (from curl above)
  api_base_url: "http://192.168.69.11:8080"  # ← Required
  api_timeout_ms: 10000               # Optional, default 10000
  enable_error_details: false         # Optional, for debugging
```

### Common Errors & Quick Fixes

| Error | Solution |
|-------|----------|
| "Cannot reach API" | Check IP, run `curl http://<ip>:8080/api/v1/services`, check firewall |
| "Connection Timeout" | Network slow? Increase `api_timeout_ms: 20000` |
| "CORS error" | HA and Pi on different machines? Configure CORS on Supervisor |
| "Invalid Configuration" | Run YAML validator at yamllint.com, check syntax |
| "Card renders but no data" | Wrong `service_id`? Check curl response for exact names |

---

## 🎯 Decision Tree

```
Start here
    ↓
Have you read README.md?
    ├─ No → Read README.md (10 min)
    └─ Yes ↓
    
Ready to deploy?
    ├─ No, setting up first → Run through examples, customize
    │   ├─ Single Pi? → See example-lovelace-view.yaml
    │   └─ Multi-Pi? → See example-fleet-card.yaml
    │
    └─ Yes ↓
    
Run PRE-DEPLOYMENT-CHECKLIST.md (MUST DO)
    ├─ Found issue? → Fix it, repeat checklist
    └─ All ✅? ↓
    
Follow SAFE-DEPLOYMENT.md phases
    ├─ Something breaks? → Go to DIAGNOSTICS.md
    │   ├─ Still broken? → Check NETWORK-ARCHITECTURE.md
    │   └─ Create GitHub issue with debug info
    │
    └─ Success! ✅
```

---

## 🚨 Critical Path for Single HA Instance

**These are non-negotiable if you have ONE HA instance:**

1. ✅ Backup configuration.yaml before deployment
2. ✅ Read SAFETY-ARCHITECTURE.md to understand protection layers
3. ✅ Run full PRE-DEPLOYMENT-CHECKLIST.md (all 13 sections)
4. ✅ Deploy incrementally (one card at a time)
5. ✅ Monitor logs first week
6. ✅ Keep DIAGNOSTICS.md bookmarked
7. ✅ All rollback procedures verified BEFORE deployment

**If you skip any of these, you risk breaking your home automation. Don't skip.**

---

## 📞 Getting Help

**Before creating an issue, provide**:

1. Output of: `curl http://<pi-ip>:8080/api/v1/services`
2. Browser console errors (F12 → Console)
3. HA logs snippet (Settings → Developer Tools → Logs)
4. Your network setup (single Pi, multi-Pi, VPN, etc.)
5. Supervisor version: `ssh pi@<ip> cat /opt/isolator/VERSION`
6. HA version: Settings → System → About

**Send debug output to**:
https://github.com/isolator/isolator/issues

---

## 📚 Related Docs in Repo

- Supervisor docs: `/docs/`
- Supervisor deployment: `/scripts/deploy-dashboard-web.ps1`
- API reference: Generated by Supervisor (`/api/v1/docs`)
- Service descriptors: `/server/`

---

## ✨ You're Ready!

- ✅ Architecture understood
- ✅ Safety systems in place
- ✅ Documentation comprehensive
- ✅ Diagnostics available
- ✅ Rollback procedures ready

**Deploy with confidence.** Your home automation is protected. 🛡️🚀

