# Templates Directory - README

## Purpose

Files in `config/templates/` are **reference and schema documentation only**.  
They are **NOT deployed** to Raspberry Pi nodes.

**Single source of truth**: `config/perimeterControl.conf.yaml`

---

## What This Directory Contains

Each file shows:
- Available configuration options for a service type
- Required vs optional fields
- Default values
- Type constraints (e.g., `gpio_pin` must be integer)

Example:
```yaml
# config/templates/gpio_control.yaml

gpio_control:
  example_instance:
    pins:
      - id: pin_id          # Required
        gpio_pin: 17        # Required, integer
        type: switch        # Required
        friendly_name: ...  # Optional
        active_high: true   # Optional, default: true
```

---

## How Templates Relate to Main Config

### ✅ Correct Workflow

1. **Template shows schema**:
   ```yaml
   # config/templates/gpio_control.yaml
   gpio_control:
     example_instance:
       pins:
         - id: pin_id
           gpio_pin: 17
   ```

2. **Main config has actual data**:
   ```yaml
   # config/perimeterControl.conf.yaml
   services:
     gpio_control:
       relays:
         pins:
           - id: relay1
             gpio_pin: 17
   ```

### ❌ Wrong: Duplicating Data

```yaml
# Bad - Same config in both places
# config/templates/gpio_control.yaml
gpio_control:
  relays:
    pins:
      - id: relay1        # ← Should not be here
        gpio_pin: 17

# config/perimeterControl.conf.yaml
services:
  gpio_control:
    relays:
      pins:
        - id: relay1      # ← Creates sync burden
          gpio_pin: 17
```

---

## When to Update Templates

Update template files **only when**:

1. **Adding a new optional field to schema**
   - Example: New `mode: manual|auto` option for photo booth
   
2. **Changing field constraints**
   - Example: GPIO pin number now supports 0-54 instead of 0-27
   
3. **Improving documentation**
   - Adding comments explaining complex options
   - Clarifying type requirements

**Do NOT** update templates when:
- Configuring your specific Pi (edit `perimeterControl.conf.yaml` instead)
- Adding/removing service instances
- Changing GPIO pins or camera settings

---

## Per-Service Template Descriptions

### gpio_control.yaml

**Shows**:
- All available pin types (switch, light, binary_sensor)
- Optional fields (initial_state, initial_brightness, icon)
- Type constraints (gpio_pin must be integer)

**Use when**:
- Learning what GPIO options exist
- Checking field names before editing main config

---

### photo_booth_config.yaml

**Shows**:
- Available camera configurations
- Optional features (motion_detection, timelapse)
- Output directory structure

---

### network_isolator.conf.yaml

**Shows**:
- Network topology structure (upstream, isolated)
- Device access policies
- Network interface types

---

### ble_gatt_repeater.yaml, esl_config.yaml, wildlife_config.yaml

**Show**:
- Schema for each specialized service
- Available configuration options
- Required vs optional fields

---

## Developer Guidelines

### When Adding a New Service

1. **Create template first**:
   ```bash
   cp config/templates/example.yaml config/templates/my_service.yaml
   ```

2. **Document all schema**:
   - Show required fields with `Required:` comment
   - Show optional fields with defaults
   - Include type constraints (int, string, bool, list)

3. **Add example in comment**:
   ```yaml
   # Real example to add to perimeterControl.conf.yaml:
   # services:
   #   my_service:
   #     instance1:
   #       field1: value1
   ```

4. **Update docs/CONFIG-TEMPLATES-GUIDE.md** with service-specific example

### When Changing Validation Rules

1. Update template to show new constraints
2. Update capability's `validate_config()` method
3. Document breaking changes in CHANGELOG.md

---

## Quick Reference

| Task | File to Edit |
|------|--------------|
| Configure your Pi's GPIO | `config/perimeterControl.conf.yaml` |
| See what GPIO options exist | `config/templates/gpio_control.yaml` |
| Learn multi-instance pattern | `docs/CONFIG-TEMPLATES-GUIDE.md` |
| Understand full schema | `docs/YAML-CONFIGURATION-SCHEMA.md` |
| Check configuration syntax | Run validator in `remote_services/supervisor/config_validator.py` |

---

## FAQ

**Q: Do I need to edit templates?**  
A: No. Edit `config/perimeterControl.conf.yaml` for your configuration.

**Q: When is template outdated?**  
A: When the schema changes (new fields, new types, new constraints).

**Q: Should templates have my actual GPIO pins?**  
A: No. Templates show available options only. Put your pins in the main config.

**Q: How do I validate my config?**  
A: See `docs/CONFIG-TEMPLATES-GUIDE.md` troubleshooting section or run validator module.
