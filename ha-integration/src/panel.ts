/**
 * Perimeter Control Panel - Main integration panel for Home Assistant
 * 
 * This is the main management interface that appears in the HA sidebar.
 * It provides device management, service control, and deployment capabilities.
 */

import { html, LitElement, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import './error-boundary';
import './safe-loader';

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
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }

    .device-card {
      background: var(--card-background-color, white);
      border-radius: 8px;
      border: 1px solid var(--divider-color, #e0e0e0);
      padding: 16px;
    }

    .device-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 12px;
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

    .services-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 12px;
      margin-top: 16px;
    }

    .service-card {
      background: var(--secondary-background-color);
      border-radius: 6px;
      padding: 12px;
      border: 1px solid var(--divider-color);
    }

    .service-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }

    .service-name {
      font-weight: 500;
      font-size: 14px;
    }

    .service-status {
      padding: 2px 8px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 500;
    }

    .status-unknown { background: #e0e0e0; color: #666; }
    .status-running { background: #c8e6c9; color: #2e7d32; }
    .status-stopped { background: #ffcdd2; color: #c62828; }

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

    .no-devices {
      text-align: center;
      padding: 48px 16px;
      color: var(--secondary-text-color);
    }

    .no-devices h2 {
      color: var(--primary-text-color);
      margin-bottom: 8px;
    }
  `;

  render() {
    if (!this.hass) {
      return html`<div>Loading...</div>`;
    }

    // Find Perimeter Control devices and entities
    const devices = this.getPerimeterControlDevices();

    return html`
      <error-boundary>
        <div class="header">
          <h1>Perimeter Control</h1>
          <p>Manage your Isolator Pi edge nodes and distributed services</p>
        </div>

        ${devices.length === 0 ? this.renderNoDevices() : this.renderDevices(devices)}

        <div class="actions">
          <h2>Global Actions</h2>
          <div class="action-buttons">
            <button class="action-btn" @click=${this.deployAll}>
              Deploy All Devices
            </button>
            <button class="action-btn secondary" @click=${this.reloadConfig}>
              Reload All Configurations
            </button>
            <button class="action-btn secondary" @click=${this.getDeviceInfo}>
              Refresh Device Info
            </button>
          </div>
        </div>
      </error-boundary>
    `;
  }

  private getPerimeterControlDevices() {
    // Look for entities from perimeter_control integration
    const entities = Object.values(this.hass?.entities || {});
    const perimeterEntities = entities.filter(entity =>
      entity.entity_id.startsWith('sensor.perimeter_control_') ||
      entity.entity_id.startsWith('binary_sensor.perimeter_control_') ||
      entity.entity_id.startsWith('button.perimeter_control_') ||
      entity.entity_id.startsWith('camera.perimeter_control_')
    );

    // TEMPORARY FIX: If no entities with perimeter_control_ prefix found,
    // check if we have supervisor entities (these will be from our fixed coordinator)
    if (perimeterEntities.length === 0) {
      // Look for any entities that might be from our integration
      const allEntities = entities.filter(entity => {
        const id = entity.entity_id;
        return id.includes('photo_booth') ||
          id.includes('wildlife_monitor') ||
          id.includes('camera') ||
          id.includes('dashboard');
      });

      if (allEntities.length > 0) {
        return [{
          name: 'Perimeter Control Node',
          host: '192.168.50.47',  // TODO: Extract from entity attributes
          entities: allEntities,
          status: this.getDeviceStatus(allEntities)
        }];
      }
    }

    // Group by device (extract device name from entity_id)
    const deviceMap: Record<string, any[]> = {};
    perimeterEntities.forEach(entity => {
      const parts = entity.entity_id.split('_');
      if (parts.length > 3) {
        const deviceName = parts.slice(2, -1).join('_'); // Extract device name
        if (!deviceMap[deviceName]) deviceMap[deviceName] = [];
        deviceMap[deviceName].push(entity);
      }
    });

    return Object.entries(deviceMap).map(([name, entities]) => ({
      name,
      host: entities[0]?.attributes?.host || name,
      entities,
      status: this.getDeviceStatus(entities)
    }));
  }

  private getDeviceStatus(entities: HassEntity[]) {
    // Check if any connectivity sensor shows "on" (connected)
    const connected = entities.some(e =>
      e.entity_id.includes('connected') && e.state === 'on'
    );
    return connected ? 'connected' : 'disconnected';
  }

  private renderNoDevices() {
    return html`
      <div class="no-devices">
        <h2>No Perimeter Control devices found</h2>
        <p>Add a Pi device by going to Settings → Devices & Services → Add Integration</p>
        <p>Search for "Perimeter Control" and follow the setup instructions</p>
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
              </div>
            </div>
            
            <div class="services-grid">
              ${device.entities.map((entity: HassEntity) => html`
                <div class="service-card">
                  <div class="service-header">
                    <div class="service-name">${this.getServiceName(entity)}</div>
                    <div class="service-status status-${this.getServiceStatus(entity)}">
                      ${this.getServiceStatus(entity)}
                    </div>
                  </div>
                  ${this.renderEntityActions(entity)}
                </div>
              `)}
              ${device.host ? html`
                <div class="service-card">
                  <div class="service-header">
                    <div class="service-name">Web Dashboard</div>
                    <div class="service-status status-running">available</div>
                  </div>
                  <div style="margin-top: 8px;">
                    <button 
                      class="action-btn" 
                      @click=${() => this.openDashboard(device.host, 8080)}
                      style="padding: 6px 12px; font-size: 12px;"
                    >
                      🌐 Open Supervisor API
                    </button>
                    <button 
                      class="action-btn secondary" 
                      @click=${() => this.openDashboard(device.host, 3000)}
                      style="padding: 6px 12px; font-size: 12px; margin-left: 4px;"
                    >
                      📊 Open Dashboard
                    </button>
                  </div>
                </div>
              ` : ''}
            </div>
          </div>
        `)}
      </div>
    `;
  }

  private getServiceName(entity: HassEntity) {
    return entity.attributes?.friendly_name ||
      entity.entity_id.split('.')[1].replace(/_/g, ' ');
  }

  private getServiceStatus(entity: HassEntity) {
    if (entity.entity_id.includes('sensor')) {
      // For numeric sensors, show the value
      return entity.state !== 'unknown' ? entity.state : 'unknown';
    }
    if (entity.entity_id.includes('binary_sensor')) {
      return entity.state === 'on' ? 'active' : 'inactive';
    }
    if (entity.entity_id.includes('camera')) {
      return entity.state !== 'unavailable' ? 'active' : 'inactive';
    }
    return entity.state || 'unknown';
  }

  private renderEntityActions(entity: HassEntity) {
    if (entity.entity_id.includes('button')) {
      return html`
                <div style="margin-top: 8px;">
                    <button 
                        class="action-btn" 
                        @click=${() => this.callEntityService(entity.entity_id, 'press')}
                        style="padding: 6px 12px; font-size: 12px;"
                    >
                        Press ${this.getServiceName(entity)}
                    </button>
                </div>
            `;
    }
    if (entity.entity_id.includes('camera')) {
      return html`
                <div style="margin-top: 8px;">
                    <button 
                        class="action-btn secondary" 
                        @click=${() => this.showCameraEntity(entity.entity_id)}
                        style="padding: 6px 12px; font-size: 12px;"
                    >
                        📷 View Camera
                    </button>
                </div>
            `;
    }
    return '';
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
    // Create a Home Assistant more-info dialog for the camera
    const event = new CustomEvent('hass-more-info', {
      detail: { entityId },
      bubbles: true,
      composed: true
    });
    this.dispatchEvent(event);
  }

  private async deployAll() {
    try {
      await this.hass?.callService('perimeter_control', 'deploy', { force: true });
    } catch (error) {
      console.error('Deploy failed:', error);
    }
  }

  private async reloadConfig() {
    try {
      await this.hass?.callService('perimeter_control', 'reload_config', {});
    } catch (error) {
      console.error('Reload config failed:', error);
    }
  }

  private async getDeviceInfo() {
    try {
      await this.hass?.callService('perimeter_control', 'get_device_info', {});
    } catch (error) {
      console.error('Get device info failed:', error);
    }
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'perimeter-control-panel': PerimeterControlPanel;
  }
}