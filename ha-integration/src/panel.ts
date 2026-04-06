
/**
 * Perimeter Control Panel - Main integration panel for Home Assistant
 */

import { html, LitElement, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

interface HassEntity {
  entity_id: string;
  state: string;
  attributes: any;
}

interface Hass {
  entities: Record<string, HassEntity>;
  callService: (domain: string, service: string, data?: any) => Promise<any>;
}

@customElement('perimeter-control-panel')
export class PerimeterControlPanel extends LitElement {
  @property({ attribute: false }) hass?: Hass;
  @property({ state: true }) errorMessage: string | null = null;
  @property({ state: true }) errorStack: string | null = null;
  @property({ state: true }) private isInitialized = false;

  constructor() {
    super();
    // Only handle errors specifically from our panel, not global errors
    // Global error handlers can interfere with HA's internal operations
  }

  protected firstUpdated() {
    // Mark as initialized after first render
    this.isInitialized = true;
  }

  private handleError(error: Error): void {
    console.error('Panel Error:', error);
    this.errorMessage = error.message || 'Unknown error occurred';
    this.errorStack = error.stack || 'No stack trace available';
  }

  static styles = css`
    :host {
      display: block;
      padding: 16px;
      max-width: 1200px;
      margin: 0 auto;
    }

    .header {
      border-bottom: 1px solid var(--divider-color, #e0e0e0);
      padding-bottom: 16px;
      margin-bottom: 24px;
    }

    .header h1 {
      margin: 0;
      font-size: 24px;
      font-weight: 400;
      color: var(--primary-text-color);
    }

    .header p {
      margin: 8px 0 0 0;
      color: var(--secondary-text-color);
    }

    .devices-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
      gap: 16px;
    }

    .device-card {
      background: var(--card-background-color);
      border-radius: 8px;
      padding: 16px;
      border: 1px solid var(--divider-color);
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    .device-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
    }

    .device-icon {
      width: 32px;
      height: 32px;
      background: var(--primary-color);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
    }

    .device-info h3 {
      margin: 0;
      font-size: 16px;
      font-weight: 500;
    }

    .device-info p {
      margin: 4px 0 0 0;
      font-size: 14px;
      color: var(--secondary-text-color);
    }

    .entities-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 8px;
      margin-top: 12px;
    }

    .entity-card {
      background: var(--card-background-color, #fafafa);
      border-radius: 4px;
      padding: 8px;
      border: 1px solid var(--divider-color);
      font-size: 12px;
    }

    .entity-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 4px;
    }

    .entity-name {
      font-weight: 500;
      font-size: 11px;
    }

    .entity-capability {
      font-size: 10px;
      color: var(--secondary-text-color);
      margin-bottom: 4px;
    }

    .entity-status {
      padding: 1px 6px;
      border-radius: 8px;
      font-size: 10px;
      font-weight: 500;
    }

    .entity-actions {
      margin-top: 6px;
    }

    .entity-actions .action-btn {
      padding: 4px 8px;
      font-size: 10px;
      margin-right: 4px;
    }

    .dashboard-links {
      background: var(--primary-color);
      color: white;
    }

    .dashboard-links .entity-name {
      color: white;
    }

    .dashboard-links .entity-status {
      background: rgba(255,255,255,0.2);
      color: white;
    }

    .actions {
      margin-top: 24px;
      padding-top: 16px;
      border-top: 1px solid var(--divider-color);
    }

    .actions h2 {
      margin: 0 0 16px 0;
      font-size: 18px;
      font-weight: 500;
    }

    .action-buttons {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }

    .action-btn {
      padding: 8px 16px;
      border: 1px solid var(--primary-color);
      background: var(--primary-color);
      color: white;
      border-radius: 4px;
      cursor: pointer;
      font-size: 14px;
      transition: all 0.2s;
    }

    .action-btn:hover {
      background: var(--primary-color);
      opacity: 0.9;
    }

    .action-btn.secondary {
      background: transparent;
      color: var(--primary-color);
    }

    .action-btn.secondary:hover {
      background: var(--primary-color);
      color: white;
    }

    .error-display {
      background: #ffebee;
      border: 1px solid #f44336;
      border-radius: 4px;
      padding: 16px;
      margin: 16px 0;
      color: #c62828;
    }

    .error-title {
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
    }

    .error-message {
      margin-bottom: 12px;
      font-family: monospace;
      font-size: 14px;
    }

    .error-stack {
      white-space: pre-wrap;
      font-family: monospace;
      font-size: 12px;
      background: #fff;
      border: 1px solid #ddd;
      border-radius: 4px;
      padding: 8px;
      max-height: 200px;
      overflow-y: auto;
      margin-top: 8px;
    }

    .error-actions {
      display: flex;
      gap: 8px;
      margin-top: 12px;
    }

    .error-btn {
      padding: 6px 12px;
      border: 1px solid #f44336;
      background: #f44336;
      color: white;
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
    }

    .error-btn:hover {
      background: #d32f2f;
    }

    .error-btn.secondary {
      background: transparent;
      color: #f44336;
    }

    .error-btn.secondary:hover {
      background: #ffebee;
    }

    .no-devices {
      text-align: center;
      padding: 48px 16px;
      color: var(--secondary-text-color);
    }

    .no-devices h2 {
      color: var(--primary-text-color);
      margin-bottom: 8px;
    }

    .status-unknown { background: #e0e0e0; color: #666; }
    .status-active { background: #c8e6c9; color: #2e7d32; }
    .status-inactive { background: #ffcdd2; color: #c62828; }
    .status-available { background: #e1f5fe; color: #0277bd; }
    .status-running { background: #c8e6c9; color: #2e7d32; }
    .status-stopped { background: #ffcdd2; color: #c62828; }
  `;

  render() {
    // Early return with loading state if HA isn't ready yet
    if (!this.hass || !this.isInitialized) {
      return html`
        <div style="padding: 16px; text-align: center;">
          <p>Loading Home Assistant connection...</p>
        </div>
      `;
    }

    // Show error display if there's an error
    if (this.errorMessage) {
      return this.renderError();
    }

    try {
      // Defensive check - ensure entities object exists
      if (!this.hass.entities) {
        return html`
          <div style="padding: 16px; text-align: center;">
            <p>Waiting for Home Assistant entities...</p>
          </div>
        `;
      }

      const devices = this.getPerimeterControlDevices();
      
      return html`
        <div class="header">
          <h1>Perimeter Control</h1>
          <p>Manage your edge devices and services</p>
        </div>

        <div class="debug-info" style="background: #f5f5f5; padding: 8px; margin: 8px 0; border-radius: 4px; font-size: 12px;">
          <strong>Debug:</strong> Found ${devices.length} devices, ${this.hass ? Object.keys(this.hass.entities).length : 0} total entities
        </div>

        ${devices.length === 0 ? this.renderNoDevices() : this.renderDevices(devices)}

        <div class="actions">
          <h2>Global Actions</h2>
          <div class="action-buttons">
            <button class="action-btn" @click=${() => this.safeAction(this.deployAll)}>
              Deploy All Devices
            </button>
            <button class="action-btn secondary" @click=${() => this.safeAction(this.reloadConfig)}>
              Reload Configurations
            </button>
            <button class="action-btn secondary" @click=${() => this.safeAction(this.refreshDevices)}>
              Refresh Device Info
            </button>
          </div>
        </div>
      `;
      
    } catch (error: any) {
      console.error('[Panel] Error in render:', error);
      this.handleError(error instanceof Error ? error : new Error(String(error)));
      return this.renderError();
    }
  }

  private renderError() {
    return html`
      <div class="error-display">
        <div class="error-title">
          <span>⚠️</span>
          <span>Perimeter Control Panel Error</span>
        </div>
        <div class="error-message">
          ${this.errorMessage}
        </div>
        ${this.errorStack ? html`
          <details>
            <summary style="cursor: pointer; margin-bottom: 8px;">Show stack trace</summary>
            <div class="error-stack">${this.errorStack}</div>
          </details>
        ` : ''}
        <div class="error-actions">
          <button class="error-btn" @click=${this.clearError}>
            Clear Error
          </button>
          <button class="error-btn secondary" @click=${this.reloadPanel}>
            Reload Panel
          </button>
        </div>
      </div>
    `;
  }

  private clearError(): void {
    this.errorMessage = null;
    this.errorStack = null;
  }

  private reloadPanel(): void {
    this.clearError();
    // Force a re-render by requesting an update
    this.requestUpdate();
  }

  private async safeAction(action: () => Promise<void>): Promise<void> {
    try {
      await action();
    } catch (error) {
      this.handleError(error instanceof Error ? error : new Error(String(error)));
    }
  }

  private getPerimeterControlDevices() {
    try {
      // Defensive check - ensure HA and entities exist
      if (!this.hass || !this.hass.entities) {
        return [];
      }

      // Get all entities - be generic about detection
      const entities = Object.values(this.hass.entities || {});
      
      // Filter for entities from our integration - look for our integration attributes
      const integrationEntities = entities.filter(entity => {
        try {
          const hasCapabilityId = entity.attributes?.capability_id || entity.attributes?.capability;
          const hasIntegrationDomain = entity.entity_id.includes('perimeter_control');
          const hasSupervisorAttributes = entity.attributes?.device || entity.attributes?.friendly_name;
          
          // Accept entities that have integration markers or supervisor-style attributes  
          return hasCapabilityId || hasIntegrationDomain || 
                 (hasSupervisorAttributes && (entity.entity_id.includes('camera') || 
                                            entity.entity_id.includes('sensor') ||
                                            entity.entity_id.includes('button') ||
                                            entity.entity_id.includes('binary_sensor')));
        } catch (e) {
          console.warn('Error filtering entity:', entity.entity_id, e);
          return false;
        }
      });

      if (integrationEntities.length === 0) {
        return [];
      }

    // Group entities by device/capability rather than hardcoded patterns
    const deviceGroups = this.groupEntitiesByDevice(integrationEntities);
    
    return Object.entries(deviceGroups).map(([deviceKey, entities]) => {
      const deviceName = this.getDeviceNameFromEntities(entities);
      const deviceHost = this.getDeviceHostFromEntities(entities);
      
      return {
        name: deviceName,
        host: deviceHost,
        entities: entities,
        status: this.getDeviceStatus(entities),
        capabilities: this.getDeviceCapabilities(entities)
      };
    });
    } catch (error) {
      console.error('Error getting Perimeter Control devices:', error);
      // Return empty array on error to prevent panel crash
      return [];
    }
  }
  
  private groupEntitiesByDevice(entities: HassEntity[]) {
    const groups: Record<string, HassEntity[]> = {};
    
    entities.forEach(entity => {
      // Get device key from various sources
      let deviceKey = 'default';
      
      // Try to get device info
      const deviceInfo = entity.attributes?.device_info;
      if (deviceInfo?.name) {
        deviceKey = deviceInfo.name;
      } else if (deviceInfo?.identifiers) {
        deviceKey = deviceInfo.identifiers[0]?.[1] || deviceKey;
      }
      // Fallback to capability grouping
      else if (entity.attributes?.capability_id) {
        deviceKey = entity.attributes.capability_id;
      }
      // Fallback to host extraction
      else if (entity.attributes?.host) {
        deviceKey = entity.attributes.host;
      }
      // Last resort - extract from entity ID pattern
      else {
        const parts = entity.entity_id.split('.');
        if (parts.length > 1) {
          const idParts = parts[1].split('_');
          if (idParts.length > 2) {
            deviceKey = idParts.slice(0, -1).join('_');
          }
        }
      }
      
      if (!groups[deviceKey]) groups[deviceKey] = [];
      groups[deviceKey].push(entity);
    });
    
    return groups;
  }
  
  private getDeviceNameFromEntities(entities: HassEntity[]): string {
    // Try device_info first
    for (const entity of entities) {
      const deviceName = entity.attributes?.device_info?.name;
      if (deviceName) return deviceName;
    }
    
    // Try capability name
    for (const entity of entities) {
      const capability = entity.attributes?.capability_id || entity.attributes?.capability;
      if (capability) return capability.replace('_', ' ').replace(/\b\w/g, (c: string) => c.toUpperCase());
    }
    
    // Fallback to first entity's friendly name or ID
    const firstEntity = entities[0];
    return firstEntity?.attributes?.friendly_name || 
           firstEntity?.entity_id.split('.')[1].replace(/_/g, ' ') ||
           'Unknown Device';
  }
  
  private getDeviceHostFromEntities(entities: HassEntity[]): string | null {
    // Look for host in attributes
    for (const entity of entities) {
      const host = entity.attributes?.host;
      if (host) return host;
    }
    
    // Look for device info with host
    for (const entity of entities) {
      const deviceInfo = entity.attributes?.device_info;
      if (deviceInfo?.configuration_url) {
        try {
          const url = new URL(deviceInfo.configuration_url);
          return url.hostname;
        } catch {}
      }
    }
    
    // Default fallback
    return '192.168.50.47';
  }
  
  private getDeviceCapabilities(entities: HassEntity[]): string[] {
    const capabilities = new Set<string>();
    entities.forEach(entity => {
      const cap = entity.attributes?.capability_id || entity.attributes?.capability;
      if (cap) capabilities.add(cap);
    });
    return Array.from(capabilities);
  }

  private getDeviceStatus(entities: HassEntity[]) {
    // Check if any entities are active/available
    const activeCount = entities.filter(e => {
      const entityType = e.entity_id.split('.')[0];
      switch (entityType) {
        case 'binary_sensor':
          return e.state === 'on';
        case 'camera':
          return e.state !== 'unavailable';
        case 'sensor':
          return e.state !== 'unknown' && e.state !== 'unavailable';
        default:
          return e.state !== 'unavailable';
      }
    }).length;
    
    return activeCount > 0 ? 'connected' : 'disconnected';
  }

  private renderNoDevices() {
    const entityList = this.hass ? Object.keys(this.hass.entities) : [];
    return html`
      <div class="no-devices">
        <h2>No Perimeter Control devices found</h2>
        <p>Add a Pi device by going to Settings → Devices & Services → Add Integration</p>
        
        <details style="margin-top: 16px; text-align: left;">
          <summary>Debug: All entities (${entityList.length})</summary>
          <div style="max-height: 200px; overflow-y: auto; font-family: monospace; font-size: 11px; margin: 8px 0;">
            ${entityList.map(id => html`<div>${id}</div>`)}
          </div>
        </details>
      </div>
    `;
  }

  private renderDevices(devices: any[]) {
    return html`
      <div class="devices-grid">
        ${devices.map(device => html`
          <div class="device-card">
            <div class="device-header">
              <div class="device-icon">π</div>
              <div class="device-info">
                <h3>${device.name}</h3>
                <p>Host: ${device.host}</p>
                <p>Status: ${device.status}</p>
                ${device.capabilities?.length > 0 ? html`
                  <p>Capabilities: ${device.capabilities.join(', ')}</p>
                ` : ''}
              </div>
            </div>
            
            <div class="entities-grid">
              ${device.entities.map((entity: HassEntity) => this.renderGenericEntity(entity))}
              ${device.host ? this.renderDashboardLinks(device.host, device.capabilities) : ''}
            </div>
          </div>
        `)}
      </div>
    `;
  }
  
  private renderGenericEntity(entity: HassEntity) {
    const entityType = entity.entity_id.split('.')[0];
    const friendlyName = entity.attributes?.friendly_name || 
                        entity.entity_id.split('.')[1].replace(/_/g, ' ');
    const capability = entity.attributes?.capability_id || entity.attributes?.capability;
    
    return html`
      <div class="entity-card">
        <div class="entity-header">
          <div class="entity-name">${friendlyName}</div>
          <div class="entity-status status-${this.getEntityStatusClass(entity)}">
            ${this.getEntityDisplayValue(entity)}
          </div>
        </div>
        
        ${capability ? html`<div class="entity-capability">${capability}</div>` : ''}
        ${this.renderEntityActions(entity, entityType)}
      </div>
    `;
  }
  
  private getEntityStatusClass(entity: HassEntity): string {
    const entityType = entity.entity_id.split('.')[0];
    
    switch (entityType) {
      case 'binary_sensor':
        return entity.state === 'on' ? 'active' : 'inactive';
      case 'camera':
        return entity.state !== 'unavailable' ? 'active' : 'inactive';
      case 'sensor':
        return entity.state !== 'unknown' && entity.state !== 'unavailable' ? 'active' : 'inactive';
      case 'button':
        return 'available';
      default:
        return entity.state === 'unavailable' ? 'inactive' : 'active';
    }
  }
  
  private getEntityDisplayValue(entity: HassEntity): string {
    const entityType = entity.entity_id.split('.')[0];
    
    switch (entityType) {
      case 'binary_sensor':
        return entity.state === 'on' ? 'Active' : 'Inactive';
      case 'camera':
        return entity.state !== 'unavailable' ? 'Streaming' : 'Offline';
      case 'sensor':
        const unit = entity.attributes?.unit_of_measurement;
        return unit ? `${entity.state} ${unit}` : entity.state;
      case 'button':
        return 'Ready';
      default:
        return entity.state;
    }
  }

  private renderEntityActions(entity: HassEntity, entityType: string) {
    switch (entityType) {
      case 'button':
        return html`
          <div class="entity-actions">
            <button class="action-btn" @click=${() => this.callEntityService(entity.entity_id, 'press')}>
              Press
            </button>
          </div>
        `;
      case 'camera':
        return html`
          <div class="entity-actions">
            <button class="action-btn" @click=${() => this.showCameraEntity(entity.entity_id)}>
              📷 View
            </button>
          </div>
        `;
      case 'binary_sensor':
      case 'sensor':
        return html`
          <div class="entity-actions">
            <button class="action-btn secondary" @click=${() => this.showEntityInfo(entity.entity_id)}>
              ℹ️ Details
            </button>
          </div>
        `;
      default:
        return html`
          <div class="entity-actions">
            <button class="action-btn secondary" @click=${() => this.showEntityInfo(entity.entity_id)}>
              View
            </button>
          </div>
        `;
    }
  }
  
  private renderDashboardLinks(host: string, capabilities: string[] = []) {
    return html`
      <div class="entity-card dashboard-links">
        <div class="entity-header">
          <div class="entity-name">Web Dashboards</div>
          <div class="entity-status status-available">available</div>
        </div>
        
        <div class="entity-actions" style="display: flex; gap: 4px; flex-wrap: wrap;">
          <button class="action-btn" @click=${() => this.openDashboard(host, 8080)} style="font-size: 11px; padding: 4px 8px;">
            🌐 API
          </button>
          
          ${capabilities.map(cap => html`
            <button class="action-btn secondary" @click=${() => this.openCapabilityDashboard(host, cap)} style="font-size: 11px; padding: 4px 8px;">
              📊 ${cap}
            </button>
          `)}
        </div>
      </div>
    `;
  }

  private openDashboard(host: string, port: number) {
    const url = `http://${host}:${port}`;
    window.open(url, '_blank');
  }

  private async callEntityService(entityId: string, action: string) {
    try {
      const domain = entityId.split('.')[0];
      await this.hass?.callService(domain, action, { entity_id: entityId });
    } catch (error) {
      console.error(`Failed to call ${action} on ${entityId}:`, error);
    }
  }

  private showCameraEntity(entityId: string) {
    const event = new CustomEvent('hass-more-info', {
      detail: { entityId },
      bubbles: true,
      composed: true
    });
    this.dispatchEvent(event);
  }
  
  private showEntityInfo(entityId: string) {
    const event = new CustomEvent('hass-more-info', {
      detail: { entityId },
      bubbles: true,
      composed: true
    });
    this.dispatchEvent(event);
  }
  
  private openCapabilityDashboard(host: string, capability: string) {
    const capabilityPorts: Record<string, number> = {
      'photo_booth': 8093,
      'wildlife_monitor': 8094,
      'ble_gatt_repeater': 8091,
      'network_isolator': 5006
    };
    
    const port = capabilityPorts[capability] || 3000;
    const url = `http://${host}:${port}`;
    window.open(url, '_blank');
  }

  private async deployAll() {
    await this.hass?.callService('perimeter_control', 'deploy', { force: true });
  }

  private async reloadConfig() {
    await this.hass?.callService('perimeter_control', 'reload_config', {});
  }

  private async refreshDevices() {
    await this.hass?.callService('perimeter_control', 'get_device_info', {});
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'perimeter-control-panel': PerimeterControlPanel;
}
}