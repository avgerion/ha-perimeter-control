/**
 * Isolator Fleet View — Multi-Pi Network Management Dashboard
 * 
 * Displays all Isolator Supervisor nodes in a network:
 * - Node status, features, and hardware inventory
 * - Service list with status and access profile editor
 * - Onboarding workflow for new Pi nodes
 * 
 * API endpoints:
 * - GET /api/v1/node/features
 * - GET /api/v1/services
 * - PUT /api/v1/services/{id}/access
 */

import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import './service-access-editor';

interface NodeFeatures {
    cameras: any[];
    ble_adapters: any[];
    gpio: { chips: any[]; available: boolean };
    i2c: { buses: any[]; available: boolean };
    spi: { devices: any[]; available: boolean };
    audio: { cards: any[]; available: boolean };
    uart: { ports: any[]; available: boolean };
    pwm: { chips: any[]; available: boolean };
    hardware_config: { dt_overlays: string[]; dt_params: Record<string, string> };
    gstreamer: { available: boolean; version: string | null; key_elements: string[] };
    storage: any[];
}

interface Service {
    id: string;
    name: string;
    version: string;
    descriptor_file: string;
    runtime: string;
    config_file: string;
}

interface NodeInfo {
    url: string;
    name: string;
    status: 'online' | 'offline' | 'connecting';
    features?: NodeFeatures;
    services?: Service[];
    lastUpdate?: number;
    error?: string;
}

@customElement('perimeter-control-fleet-view')
export class FleetView extends LitElement {
    @property({ type: Array }) nodes: NodeInfo[] = [];
    @property({ type: Boolean }) autoRefresh = true;
    @property({ type: Number }) refreshInterval = 30000; // 30 seconds

    @state() private selectedNode: NodeInfo | null = null;
    @state() private selectedService: Service | null = null;
    @state() private loading = false;
    @state() private error: string | null = null;

    private refreshTimer?: number;

    connectedCallback() {
        super.connectedCallback();
        if (this.autoRefresh) {
            this.startAutoRefresh();
        }
    }

    disconnectedCallback() {
        super.disconnectedCallback();
        this.stopAutoRefresh();
    }

    private startAutoRefresh() {
        this.refreshTimer = window.setInterval(() => {
            this.refreshAllNodes();
        }, this.refreshInterval);
    }

    private stopAutoRefresh() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
        }
    }

    async refreshAllNodes() {
        for (const node of this.nodes) {
            await this.loadNodeFeatures(node);
            await this.loadNodeServices(node);
        }
    }

    async loadNodeFeatures(node: NodeInfo) {
        try {
            node.status = 'connecting';
            const response = await fetch(`${node.url}/api/v1/node/features?timeout=10`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            node.features = data.node_features;
            node.status = 'online';
            node.lastUpdate = Date.now();
            node.error = undefined;
        } catch (err) {
            node.status = 'offline';
            node.error = err instanceof Error ? err.message : 'Unknown error';
        }
        this.requestUpdate();
    }

    async loadNodeServices(node: NodeInfo) {
        try {
            const response = await fetch(`${node.url}/api/v1/services?timeout=5`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            node.services = data.services || [];
        } catch (err) {
            node.services = [];
        }
        this.requestUpdate();
    }

    private selectNode(node: NodeInfo) {
        this.selectedNode = node;
        this.selectedService = null;
    }

    private selectService(service: Service) {
        this.selectedService = service;
    }

    static styles = css`
    :host {
      display: block;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      --primary: #0288d1;
      --success: #4caf50;
      --warning: #ff9800;
      --error: #f44336;
    }

    .container {
      display: grid;
      grid-template-columns: 300px 1fr;
      gap: 20px;
      padding: 20px;
      background: #fafafa;
      min-height: 100vh;
    }

    .sidebar {
      background: white;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
      display: flex;
      flex-direction: column;
      overflow-y: auto;
    }

    .main {
      background: white;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
      padding: 20px;
      overflow-y: auto;
    }

    .sidebar-header {
      padding: 16px;
      border-bottom: 1px solid #e0e0e0;
      font-weight: 600;
      color: var(--primary);
    }

    .node-list {
      flex: 1;
      overflow-y: auto;
    }

    .node-item {
      padding: 12px 16px;
      border-bottom: 1px solid #f0f0f0;
      cursor: pointer;
      transition: background 0.2s;
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
    }

    .node-item:hover {
      background: #f5f5f5;
    }

    .node-item.selected {
      background: #e3f2fd;
      border-left: 3px solid var(--primary);
    }

    .node-status {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      flex-shrink: 0;
    }

    .node-status.online {
      background: var(--success);
      box-shadow: 0 0 6px rgba(76, 175, 80, 0.6);
    }

    .node-status.offline {
      background: #ccc;
    }

    .node-status.connecting {
      background: var(--warning);
      animation: pulse 1s infinite;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.6; }
    }

    .main-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 20px;
      padding-bottom: 16px;
      border-bottom: 1px solid #e0e0e0;
    }

    .main-header h2 {
      margin: 0;
      font-size: 20px;
      color: #212121;
    }

    .refresh-btn {
      padding: 8px 12px;
      background: var(--primary);
      color: white;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
      font-weight: 600;
    }

    .refresh-btn:hover {
      background: #0277bd;
    }

    .tabs {
      display: flex;
      gap: 8px;
      margin-bottom: 16px;
      border-bottom: 1px solid #e0e0e0;
    }

    .tab {
      padding: 8px 12px;
      cursor: pointer;
      border: none;
      background: none;
      color: #666;
      font-weight: 600;
      font-size: 13px;
      border-bottom: 2px solid transparent;
      transition: all 0.2s;
    }

    .tab.active {
      color: var(--primary);
      border-bottom-color: var(--primary);
    }

    .tab:hover {
      color: var(--primary);
    }

    .content {
      display: none;
    }

    .content.active {
      display: block;
    }

    .features-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 12px;
    }

    .feature-card {
      border: 1px solid #e0e0e0;
      border-radius: 4px;
      padding: 12px;
      background: #f9f9f9;
    }

    .feature-card h4 {
      margin: 0 0 8px 0;
      font-size: 12px;
      font-weight: 600;
      color: #212121;
      text-transform: uppercase;
    }

    .feature-value {
      font-size: 13px;
      color: var(--primary);
      font-family: monospace;
    }

    .feature-list {
      font-size: 12px;
      color: #666;
      margin: 0;
      padding-left: 16px;
    }

    .feature-list li {
      margin: 4px 0;
    }

    .service-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .service-item {
      padding: 12px;
      border: 1px solid #e0e0e0;
      border-radius: 4px;
      cursor: pointer;
      transition: all 0.2s;
    }

    .service-item:hover {
      background: #f9f9f9;
      border-color: var(--primary);
    }

    .service-item.selected {
      background: #e3f2fd;
      border-color: var(--primary);
    }

    .service-name {
      font-weight: 600;
      color: #212121;
      font-size: 13px;
    }

    .service-meta {
      font-size: 11px;
      color: #999;
      margin-top: 4px;
    }

    .placeholder {
      text-align: center;
      padding: 40px 20px;
      color: #999;
    }

    .placeholder-icon {
      font-size: 48px;
      margin-bottom: 16px;
      opacity: 0.3;
    }

    .error-box {
      background: #ffebee;
      border: 1px solid #ef5350;
      border-radius: 4px;
      padding: 12px;
      color: #c62828;
      font-size: 12px;
      margin-bottom: 16px;
    }

    @media (max-width: 768px) {
      .container {
        grid-template-columns: 1fr;
      }

      .sidebar {
        max-height: 200px;
      }
    }
  `;

    protected render() {
        return html`
      <div class="container">
        <!-- Sidebar: Node List -->
        <div class="sidebar">
          <div class="sidebar-header">
            🔗 Isolator Fleet
            <div style="font-size: 11px; font-weight: normal; color: #999; margin-top: 4px;">
              ${this.nodes.length} node${this.nodes.length !== 1 ? 's' : ''}
            </div>
          </div>
          <div class="node-list">
            ${this.nodes.length === 0
                ? html`<div class="placeholder" style="padding: 20px;"><div>No nodes configured</div></div>`
                : repeat(
                    this.nodes,
                    (n) => n.url,
                    (node) => html`
                    <div
                      class="node-item ${this.selectedNode?.url === node.url ? 'selected' : ''}"
                      @click=${() => this.selectNode(node)}
                    >
                      <div class="node-status ${node.status}"></div>
                      <div style="flex: 1; overflow: hidden;">
                        <div style="font-weight: 600; text-overflow: ellipsis; overflow: hidden;">
                          ${node.name}
                        </div>
                        <div style="font-size: 11px; color: #999; text-overflow: ellipsis; overflow: hidden;">
                          ${node.url}
                        </div>
                      </div>
                    </div>
                  `
                )}
          </div>
        </div>

        <!-- Main Content -->
        <div class="main">
          ${this.selectedNode
                ? html`
                <div class="main-header">
                  <div>
                    <h2>${this.selectedNode.name}</h2>
                    <div style="font-size: 12px; color: #999; margin-top: 4px;">
                      Status: <strong>${this.selectedNode.status}</strong>
                      ${this.selectedNode.lastUpdate
                        ? ` • Updated: ${new Date(this.selectedNode.lastUpdate).toLocaleTimeString()}`
                        : ''}
                    </div>
                  </div>
                  <button class="refresh-btn" @click=${() => this.loadNodeFeatures(this.selectedNode!)}>
                    ⟳ Refresh
                  </button>
                </div>

                ${this.selectedNode.error
                        ? html`<div class="error-box">${this.selectedNode.error}</div>`
                        : ''}

                <div class="tabs">
                  <button
                    class="tab ${!this.selectedService ? 'active' : ''}"
                    @click=${() => this.selectService(null)}
                  >
                    Features
                  </button>
                  <button
                    class="tab ${this.selectedService ? 'active' : ''}"
                    @click=${() => { }}
                  >
                    Services (${this.selectedNode.services?.length || 0})
                  </button>
                </div>

                ${!this.selectedService
                        ? this.renderFeatures(this.selectedNode)
                        : this.renderServices(this.selectedNode)}
              `
                : html`
                <div class="placeholder">
                  <div class="placeholder-icon">🛰️</div>
                  <div>Select a node to view details</div>
                </div>
              `}
        </div>
      </div>
    `;
    }

    private renderFeatures(node: NodeInfo) {
        if (!node.features) {
            return html`<div class="placeholder">Loading features...</div>`;
        }

        const f = node.features;

        return html`
      <div class="content active">
        <div class="features-grid">
          <div class="feature-card">
            <h4>🎥 Cameras</h4>
            <div class="feature-value">${f.cameras.length} found</div>
          </div>

          <div class="feature-card">
            <h4>📡 BLE Adapters</h4>
            <div class="feature-value">${f.ble_adapters.length} found</div>
            ${f.ble_adapters.length > 0
                ? html`<ul class="feature-list">
                  ${f.ble_adapters.map((a) => html`<li>${a.device}</li>`)}
                </ul>`
                : ''}
          </div>

          <div class="feature-card">
            <h4>⚡ GPIO</h4>
            <div class="feature-value">${f.gpio.available ? '✓ Available' : '✗ Unavailable'}</div>
            ${f.gpio.chips.length > 0
                ? html`<div style="font-size: 11px; color: #666; margin-top: 4px;">
                  ${f.gpio.chips.length} chip${f.gpio.chips.length !== 1 ? 's' : ''}
                </div>`
                : ''}
          </div>

          <div class="feature-card">
            <h4>I²C</h4>
            <div class="feature-value">${f.i2c.available ? '✓ Available' : '✗ Unavailable'}</div>
            ${f.i2c.buses.length > 0
                ? html`<div style="font-size: 11px; color: #666; margin-top: 4px;">
                  ${f.i2c.buses.length} bus${f.i2c.buses.length !== 1 ? 'es' : ''}
                </div>`
                : ''}
          </div>

          <div class="feature-card">
            <h4>🔊 Audio</h4>
            <div class="feature-value">${f.audio.available ? '✓ Available' : '✗ Unavailable'}</div>
            ${f.audio.cards.length > 0
                ? html`<ul class="feature-list">
                  ${f.audio.cards.map((c) => html`<li>${c.name}</li>`)}
                </ul>`
                : ''}
          </div>

          <div class="feature-card">
            <h4>📡 UART</h4>
            <div class="feature-value">${f.uart.available ? '✓ Available' : '✗ Unavailable'}</div>
            ${f.uart.ports.length > 0
                ? html`<ul class="feature-list">
                  ${f.uart.ports.map((p) => html`<li>${p.device}</li>`)}
                </ul>`
                : ''}
          </div>

          <div class="feature-card">
            <h4>🎬 GStreamer</h4>
            <div class="feature-value">
              ${f.gstreamer.available ? '✓ ' + (f.gstreamer.version || '?') : '✗ Not available'}
            </div>
          </div>

          <div class="feature-card">
            <h4>💾 Storage</h4>
            <div class="feature-value">${f.storage.length > 0 ? f.storage[0].size : 'Unknown'}</div>
            ${f.storage.length > 0
                ? html`<div style="font-size: 11px; color: #666; margin-top: 4px;">
                  Used: ${f.storage[0].used}
                </div>`
                : ''}
          </div>

          ${Object.keys(f.hardware_config.dt_params).length > 0
                ? html`
                <div class="feature-card" style="grid-column: 1 / -1;">
                  <h4>⚙️ Device Tree Parameters</h4>
                  <ul class="feature-list">
                    ${Object.entries(f.hardware_config.dt_params).map(
                    ([k, v]) => html`<li><strong>${k}</strong> = ${v}</li>`
                )}
                  </ul>
                </div>
              `
                : ''}
        </div>
      </div>
    `;
    }

    private renderServices(node: NodeInfo) {
        if (!node.services) {
            return html`<div class="placeholder">Loading services...</div>`;
        }

        if (node.services.length === 0) {
            return html`<div class="placeholder">No services found</div>`;
        }

        return html`
      <div class="content active">
        <div class="service-list">
          ${node.services.map(
            (service) => html`
              <div class="service-item ${this.selectedService?.id === service.id ? 'selected' : ''}">
                <div class="service-name">${service.name}</div>
                <div class="service-meta">
                  ID: <code>${service.id}</code> • v${service.version} • ${service.runtime}
                </div>
              </div>

              ${this.selectedService?.id === service.id
                    ? html`
                    <perimeter-control-service-access-editor
                      apiBaseUrl=${node.url}
                      serviceId=${service.id}
                    ></perimeter-control-service-access-editor>
                  `
                    : ''}
            `
        )}
        </div>
      </div>
    `;
    }
}

declare global {
    interface HTMLElementTagNameMap {
        'perimeter-control-fleet-view': FleetView;
        'isolator-fleet-view': FleetView;
    }
}

@customElement('isolator-fleet-view')
export class IsolatorFleetViewAlias extends FleetView {
}

declare global {
    interface HTMLElementTagNameMap {
        'perimeter-control-fleet-view': FleetView;
        'isolator-fleet-view': FleetView;
    }
}
