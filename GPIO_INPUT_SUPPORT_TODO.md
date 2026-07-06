# GPIO Input Support Implementation TODO

## Phase 1: Core Capability Changes ✅ COMPLETE
- [x] Extend `PinConfig` dataclass with `direction` field (input/output)
- [x] Update `validate_config()` to accept `binary_sensor` type for input pins
- [x] Update `_load_pin_configs()` to parse `direction` field
- [x] Add optional `pull_mode` config field (none/pull_up/pull_down) for inputs
- [x] Update GPIO driver setup to handle input vs output direction

## Phase 2: Driver Enhancement ✅ COMPLETE
- [x] Update `_setup_pin()` to set GPIO direction based on pin type
- [x] Extend `_set_with_raspi_gpio()` to set direction and pull mode for inputs
- [x] Extend `_set_with_sysfs()` to write direction="in" for input pins
- [x] Add GPIO read capability for input pins

## Phase 3: Input State Monitoring ✅ COMPLETE
- [x] Add async polling task to read input pin states
- [x] Create `_read_pin_state()` method (raspi-gpio and sysfs backends)
- [x] Update `_publish_pin_entity()` to handle state from polling
- [x] Add periodic callback to monitor input pin changes

## Phase 4: Entity State Management ✅ COMPLETE
- [x] Remove turn_on/turn_off actions for input entities
- [x] Ensure binary_sensor entities are read-only in HA UI
- [x] Publish input state changes to entity cache

## Phase 5: Configuration & Documentation ✅ COMPLETE
- [x] Update config template with direction and pull_mode examples
- [x] Update YAML schema docs with input pin examples

## Phase 6: Testing 🟡 IN PROGRESS
- [ ] Add validation tests for input config
- [ ] Verify binary_sensor platform receives input entities correctly
- [ ] Test input state propagation through coordinator
- [ ] Verify HA UI shows input states as read-only

## Example Configuration (when complete):
```yaml
services:
  gpio_control:
    relays:
      pins:
        - id: relay1
          gpio_pin: 17
          type: switch
          direction: output
          
    inputs:
      pins:
        - id: button1
          gpio_pin: 23
          type: binary_sensor
          direction: input
          pull_mode: pull_up
          friendly_name: Reset Button
```
