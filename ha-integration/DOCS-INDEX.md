# HA Integration Documentation Index

**Start here to find the right guide for your situation.**

---

## 🚀 I want to install the integration — where do I start?

**Your exact sequence**:

1. [QUICKSTART.md](QUICKSTART.md) — 5 min setup
   - Quick installation via HACS or manual
   - Add Pi device via HA UI
   - Basic verification steps

2. [README.md](README.md) — Complete overview
   - Full feature list and capabilities
   - Installation options
   - Usage examples and automation

3. [PRE-DEPLOYMENT-CHECKLIST.md](PRE-DEPLOYMENT-CHECKLIST.md) — 15-20 min verification
   - Verify HA prerequisites 
   - Check Pi device requirements
   - Network connectivity validation
   - **Recommended before setup**

4. [INTEGRATION.md](INTEGRATION.md) — Technical deep dive
   - Architecture and data flow
   - Service registration details  
   - API integration specifics
   - Development information

---

## 🔧 I want to configure/manage Pi devices

**Your options**:

1. **Via HA Interface** (Recommended):
   - Use "Perimeter Control" panel in HA sidebar
   - Access deploy, start/stop, configuration functions
   - Real-time device status and service management

2. **Via HA Services**:
   - Developer Tools → Services → `perimeter_control.*`
   - Use in automations and scripts
   - Available services: deploy, start_capability, stop_capability, etc.

3. **Manual SSH** (Advanced):
   - Direct SSH to Pi devices
   - Manual supervisor API calls
   - Use when integration troubleshooting needed

---

## 🔍 Something's not working — where do I look?

**Your exact sequence**:

1. [DIAGNOSTICS.md](DIAGNOSTICS.md) — START HERE
   - Common integration issues
   - Step-by-step troubleshooting  
   - Connection and service problems

2. [INTEGRATION.md](INTEGRATION.md) — Technical troubleshooting
   - Check logging configuration
   - Verify SSH connectivity
   - API communication debugging

3. **HA Built-in Tools**:
   - Settings → System → Logs (search "perimeter")
   - Developer Tools → Services (test `perimeter_control.*`)
   - Settings → Devices & Services → Perimeter Control (device status)

4. If still stuck:
   - Gather info from DIAGNOSTICS.md "When Nothing Else Works"
   - Create GitHub issue with details

---

## 📚 I want to understand the architecture

**Background reading**:

1. [INTEGRATION.md](INTEGRATION.md) — Integration architecture
   - How HA communicates with Pi devices
   - Service registration and entity creation
   - Frontend panel and static asset serving

2. [NETWORK-ARCHITECTURE.md](NETWORK-ARCHITECTURE.md) — Network design
   - Pi supervisor API structure
   - Multi-device communication patterns
   - Security and isolation concepts

3. [SAFETY-ARCHITECTURE.md](SAFETY-ARCHITECTURE.md) — Safety design
   - Error handling and recovery
   - Integration failure isolation
   - Rollback and debugging capabilities

---

## 📋 Managing Multiple Pi Devices

**Scaling to multiple devices**:

### Single Pi Setup (most common)
1. Add one Pi device via integration setup
2. Use "Perimeter Control" panel to manage
3. Deploy and manage services via HA interface

### Multiple Pi Fleet Management
1. Add each Pi as separate integration instance
2. Each Pi appears as separate device in HA
3. Use automations to coordinate across devices
4. Monitor all devices through single HA interface

### Example Multi-Pi Automation
```yaml
# Deploy to all Pi devices
automation:
  - trigger:
      platform: time
      at: "02:00:00"
    action:
      service: perimeter_control.deploy
      data:
        force: true
```

---

## 🚀 Advanced Usage

**Power user guides**:

- **Automation Integration**: Use `perimeter_control.*` services in automations  
- **Service Orchestration**: Coordinate multiple capabilities across devices
- **Custom Deployment**: Direct supervisor API usage for custom capabilities
- **Fleet Monitoring**: Monitor multiple Pi devices from single HA dashboard

**Development**:
- [Frontend build process](README.md#development)
- [Service registration](INTEGRATION.md#service-registration)  
- [Entity creation patterns](INTEGRATION.md#entity-creation)
- [Custom frontend components](../ha-integration/src/)

---

## 🛡️ Understanding the Safety Systems

**Integration reliability features**:

1. [SAFETY-ARCHITECTURE.md](SAFETY-ARCHITECTURE.md) — Complete safety overview
   - Error isolation and recovery
   - Connection timeout handling  
   - Graceful degradation patterns

2. **Built-in Protections**:
   - SSH connection timeouts and retries
   - API error handling and exponential backoff
   - Integration failure isolation (won't break HA)
   - Automatic entity cleanup on device disconnect

---

## 📖 Reference Documentation

| Document | Purpose | Read Time |
|----------|---------|-----------|
| [README.md](README.md) | Complete feature overview | 5 min |
| [QUICKSTART.md](QUICKSTART.md) | Installation walkthrough | 5 min |
| [INTEGRATION.md](INTEGRATION.md) | Technical architecture | 15 min |
| [PRE-DEPLOYMENT-CHECKLIST.md](PRE-DEPLOYMENT-CHECKLIST.md) | Setup verification | 20 min |
| [DIAGNOSTICS.md](DIAGNOSTICS.md) | Troubleshooting guide | As needed |
| [NETWORK-ARCHITECTURE.md](NETWORK-ARCHITECTURE.md) | Network design | 10 min |
| [SAFETY-ARCHITECTURE.md](SAFETY-ARCHITECTURE.md) | Safety systems | 10 min |

---

## 💡 Quick Navigation

- **Just getting started?** → [QUICKSTART.md](QUICKSTART.md)
- **Installation issues?** → [DIAGNOSTICS.md](DIAGNOSTICS.md)  
- **Want technical details?** → [INTEGRATION.md](INTEGRATION.md)
- **Setting up automation?** → [README.md](README.md#service-automation-examples)
- **Managing multiple Pis?** → [Multiple Pi Fleet Management](#multiple-pi-fleet-management)