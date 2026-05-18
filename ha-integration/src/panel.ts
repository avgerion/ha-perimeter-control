/**
 * Perimeter Control Panel - Main integration panel for Home Assistant
 */

import { LitElement, html, css, nothing } from 'lit';
import { property, state } from 'lit/decorators.js';

interface Hass {
  callApi: (method: string, path: string, parameters?: unknown) => Promise<unknown>;
}

interface DeviceSummary {
  entry_id: string;
  title?: string;
  host?: string;
  services?: string[];
  available_services?: string[];
  dashboard_active?: boolean;
  supervisor_active?: boolean;
  deploy_in_progress?: boolean;
  dashboard_urls?: Record<string, string>;
}

export class PerimeterControlPanel extends LitElement {
  private _hass?: Hass;

  @property({ attribute: false })
  get hass(): Hass | undefined {
    return this._hass;
  }

  set hass(value: Hass | undefined) {
    this._hass = value;
    if (value && this.devices.length === 0 && !this.loading) {
      this.runAsync(() => this.refreshDevices());
    }
    this.requestUpdate();
  }

  @state() private devices: DeviceSummary[] = [];
  @state() private loading = false;
  @state() private message = '';
  @state() private error = '';
  @state() private serviceDrafts: Record<string, string[]> = {};
  @state() private savingByEntry: Record<string, boolean> = {};

  static styles = css`
    :host {
      display: block;
      padding: 16px;
      max-width: 1100px;
      margin: 0 auto;
      box-sizing: border-box;
    }

    h1 {
      margin: 0 0 8px;
      font-size: 24px;
      font-weight: 600;
    }

    .sub {
      margin: 0 0 16px;
      color: var(--secondary-text-color);
    }

    .toolbar {
      margin-bottom: 16px;
    }

    button {
      border: 1px solid var(--divider-color);
      border-radius: 6px;
      background: var(--card-background-color);
      color: var(--primary-text-color);
      padding: 8px 12px;
      cursor: pointer;
    }

    button.primary {
      background: var(--primary-color);
      border-color: var(--primary-color);
      color: #fff;
    }

    button:disabled {
      opacity: 0.6;
      cursor: default;
    }

    .msg {
      margin: 8px 0 16px;
      padding: 8px 10px;
      border-radius: 6px;
      font-size: 14px;
    }

    .ok {
      background: #e8f5e9;
      color: #1b5e20;
      border: 1px solid #a5d6a7;
    }

    .err {
      background: #ffebee;
      color: #b71c1c;
      border: 1px solid #ef9a9a;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 14px;
    }

    .card {
      border: 1px solid var(--divider-color);
      border-radius: 10px;
      padding: 14px;
      background: var(--card-background-color);
    }

    .title {
      font-weight: 600;
      margin: 0 0 4px;
    }

    .meta {
      margin: 0 0 8px;
      color: var(--secondary-text-color);
      font-size: 13px;
    }

    .services {
      border-top: 1px dashed var(--divider-color);
      margin-top: 10px;
      padding-top: 10px;
    }

    .svc {
      display: block;
      margin: 4px 0;
      font-size: 14px;
    }

    .card-actions {
      margin-top: 12px;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }

    .loading {
      opacity: 0.8;
    }

    .dashboards {
      border-top: 1px dashed var(--divider-color);
      margin-top: 10px;
      padding-top: 10px;
    }

    .dash-link {
      display: inline-block;
      margin: 3px 6px 3px 0;
      font-size: 13px;
      color: var(--primary-color);
      text-decoration: none;
      border: 1px solid var(--primary-color);
      border-radius: 4px;
      padding: 2px 8px;
    }

    .dash-link:hover {
      opacity: 0.8;
    }
  `;

  protected render() {
    return html`
      <h1>Perimeter Control</h1>
      <p class="sub">Manage installed devices and update enabled service options.</p>
      <div class="toolbar">
        <button @click=${() => this.runAsync(() => this.refreshDevices())}>Refresh Devices</button>
      </div>

      ${this.message ? html`<div class="msg ok">${this.message}</div>` : nothing}
      ${this.error ? html`<div class="msg err">${this.error}</div>` : nothing}
      ${this.loading ? html`<p class="loading">Loading devices...</p>` : nothing}

      ${!this.loading && this.devices.length === 0
        ? html`<p>No devices found. Add a Perimeter Control integration entry first.</p>`
        : nothing}

      <div class="grid">
        ${this.devices.map((device) => this.renderDeviceCard(device))}
      </div>
    `;
  }

  private renderDeviceCard(device: DeviceSummary) {
    const available = Array.isArray(device.available_services) ? device.available_services : [];
    const selected = new Set(this.serviceDrafts[device.entry_id] || device.services || []);
    const saving = !!this.savingByEntry[device.entry_id];

    return html`
      <div class="card">
        <p class="title">${device.title || 'Perimeter Device'}</p>
        <p class="meta">Host: ${device.host || 'unknown'}</p>
        <p class="meta">
          Dashboard: ${device.dashboard_active ? 'online' : 'offline'} |
          Supervisor: ${device.supervisor_active ? 'online' : 'offline'}
        </p>

        <div class="services">
          <strong>Enabled services</strong>
          ${available.length
        ? available.map(
          (serviceId) => html`
                  <label class="svc">
                    <input
                      type="checkbox"
                      .checked=${selected.has(serviceId)}
                      @change=${(ev: Event) =>
              this.toggleService(device.entry_id, serviceId, (ev.currentTarget as HTMLInputElement).checked)}
                    />
                    ${serviceId}
                  </label>
                `,
        )
        : html`<p class="meta">No service options available.</p>`}
        </div>

        <div class="card-actions">
          <button
            class="primary"
            ?disabled=${saving}
            @click=${() => this.runAsync(() => this.saveServices(device.entry_id))}
          >
            ${saving ? 'Saving...' : 'Save Services'}
          </button>
          <button
            ?disabled=${!!device.deploy_in_progress}
            @click=${() => this.runAsync(() => this.deployDevice(device.entry_id))}
          >
            ${device.deploy_in_progress ? 'Deploying...' : 'Deploy Device'}
          </button>
        </div>

        ${this.renderDashboardLinks(device)}
      </div>
    `;
  }

  private renderDashboardLinks(device: DeviceSummary) {
    const urls = device.dashboard_urls ?? {};
    const entries = Object.entries(urls).filter(([, url]) => !!url);
    if (!entries.length) {
      return nothing;
    }
    return html`
      <div class="dashboards">
        <strong>Dashboards</strong><br />
        ${entries.map(
      ([serviceId, url]) =>
        html`<a class="dash-link" href=${url} target="_blank" rel="noopener noreferrer"
              >${serviceId}</a
            >`,
    )}
      </div>
    `;
  }

  private async api(method: string, path: string, body?: unknown): Promise<unknown> {
    if (!this._hass) {
      throw new Error('Home Assistant is not available');
    }
    return this._hass.callApi(method, path, body);
  }

  private isAbortLikeError(err: unknown): boolean {
    if (!err || typeof err !== 'object') {
      return false;
    }
    const withFields = err as { name?: unknown; message?: unknown };
    const name = String(withFields.name ?? '');
    const message = String(withFields.message ?? '');
    return name === 'AbortError' || message.includes('Transition was skipped');
  }

  private runAsync(fn: () => Promise<void>): void {
    Promise.resolve()
      .then(fn)
      .catch((err) => {
        if (this.isAbortLikeError(err)) {
          return;
        }
        this.error = `Unexpected error: ${this.toErrorMessage(err)}`;
        this.message = '';
      });
  }

  private toErrorMessage(err: unknown): string {
    if (err instanceof Error) {
      return err.message;
    }
    return String(err);
  }

  private async refreshDevices(): Promise<void> {
    this.loading = true;
    this.error = '';
    this.message = '';

    try {
      const result = await this.api('GET', 'perimeter_control/devices');
      const devices = Array.isArray(result) ? (result as DeviceSummary[]) : [];
      this.devices = devices;

      const nextDrafts: Record<string, string[]> = {};
      for (const device of devices) {
        nextDrafts[device.entry_id] = [...(device.services || [])];
      }
      this.serviceDrafts = nextDrafts;
    } catch (err) {
      if (this.isAbortLikeError(err)) {
        return;
      }
      this.error = `Failed to load devices: ${this.toErrorMessage(err)}`;
    } finally {
      this.loading = false;
    }
  }

  private toggleService(entryId: string, serviceId: string, checked: boolean): void {
    const selected = new Set(this.serviceDrafts[entryId] || []);
    if (checked) {
      selected.add(serviceId);
    } else {
      selected.delete(serviceId);
    }

    this.serviceDrafts = {
      ...this.serviceDrafts,
      [entryId]: Array.from(selected),
    };
  }

  private async saveServices(entryId: string): Promise<void> {
    const selected = [...(this.serviceDrafts[entryId] || [])];
    if (!selected.length) {
      this.error = 'Select at least one service before saving.';
      this.message = '';
      return;
    }

    this.savingByEntry = { ...this.savingByEntry, [entryId]: true };
    this.error = '';
    this.message = '';

    try {
      await this.api('POST', `perimeter_control/${entryId}/services`, { services: selected });
      this.message = 'Service options updated successfully.';
      await this.refreshDevices();
    } catch (err) {
      if (this.isAbortLikeError(err)) {
        return;
      }
      this.error = `Failed to save service options: ${this.toErrorMessage(err)}`;
    } finally {
      this.savingByEntry = { ...this.savingByEntry, [entryId]: false };
    }
  }

  private async deployDevice(entryId: string): Promise<void> {
    this.error = '';
    this.message = '';

    try {
      await this.api('POST', `perimeter_control/${entryId}/deploy`, {});
      this.message = 'Deploy queued.';
      await this.refreshDevices();
    } catch (err) {
      if (this.isAbortLikeError(err)) {
        return;
      }
      this.error = `Failed to queue deploy: ${this.toErrorMessage(err)}`;
    }
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'perimeter-control-panel': PerimeterControlPanel;
  }
}

if (!customElements.get('perimeter-control-panel')) {
  customElements.define('perimeter-control-panel', PerimeterControlPanel);
}
