/**
 * Service Access Editor — Reusable Home Assistant Card for editing access profiles
 * 
 * Allows users to edit access_profile fields (mode, port, tls_mode, auth_mode, exposure_scope)
 * for services on a remote Isolator Supervisor API. Embeds in service cards in the HA fleet view.
 * 
 * API endpoint: PUT /api/v1/services/{service_id}/access
 */

import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { ifDefined } from 'lit/directives/if-defined.js';

interface AccessProfile {
    mode: 'isolated' | 'upstream' | 'passthrough';
    bind_address: string;
    port: number;
    tls_mode: 'disabled' | 'self_signed' | 'external' | 'custom';
    cert_file?: string;
    key_file?: string;
    auth_mode: 'none' | 'token' | 'oauth2' | 'mTLS';
    allowed_origins: string[];
    exposure_scope: 'local_only' | 'lan_only' | 'wan_limited' | 'wan_full';
}

interface ServiceInfo {
    id: string;
    name: string;
    version: string;
    descriptor_file: string;
    config_file: string;
}

@customElement('perimeter-control-service-access-editor')
export class ServiceAccessEditor extends LitElement {
    @property({ type: String }) apiBaseUrl = 'http://localhost:8080'; // Supervisor API URL
    @property({ type: String }) serviceId: string = '';
    @property({ type: Object }) service?: ServiceInfo;

    @state() private accessProfile: AccessProfile | null = null;
    @state() private loading = true;
    @state() private saving = false;
    @state() private error: string | null = null;
    @state() private successMessage: string | null = null;

    static styles = css`
    :host {
      display: block;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen,
        Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
      --primary-color: #03a9f4;
      --error-color: #f44336;
      --success-color: #4caf50;
    }

    .container {
      padding: 16px;
      background: linear-gradient(135deg, #fafafa 0%, #f5f5f5 100%);
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }

    .header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 16px;
    }

    .header h3 {
      margin: 0;
      font-size: 16px;
      font-weight: 600;
      color: #212121;
    }

    .status-badge {
      display: inline-block;
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: 600;
    }

    .status-badge.loading {
      background: #e3f2fd;
      color: #1976d2;
    }

    .status-badge.ready {
      background: #e8f5e9;
      color: #388e3c;
    }

    .form-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-bottom: 16px;
    }

    .form-group {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .form-group.full {
      grid-column: 1 / -1;
    }

    label {
      font-size: 12px;
      font-weight: 600;
      color: #666;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    input,
    select,
    textarea {
      padding: 8px 12px;
      border: 1px solid #ddd;
      border-radius: 4px;
      font-family: inherit;
      font-size: 13px;
      background: white;
      color: #212121;
      transition: border-color 0.2s, box-shadow 0.2s;
    }

    input:focus,
    select:focus,
    textarea:focus {
      outline: none;
      border-color: var(--primary-color);
      box-shadow: 0 0 0 2px rgba(3, 169, 244, 0.1);
    }

    input:disabled,
    select:disabled {
      background: #f5f5f5;
      color: #999;
      cursor: not-allowed;
    }

    .field-hint {
      font-size: 11px;
      color: #999;
      margin-top: 2px;
    }

    .info-box {
      padding: 8px 12px;
      border-radius: 4px;
      font-size: 12px;
      margin-bottom: 12px;
    }

    .info-box.error {
      background: #ffebee;
      color: #c62828;
      border-left: 3px solid var(--error-color);
    }

    .info-box.success {
      background: #e8f5e9;
      color: #2e7d32;
      border-left: 3px solid var(--success-color);
    }

    .info-box.loading {
      background: #e3f2fd;
      color: #1565c0;
      border-left: 3px solid var(--primary-color);
    }

    .actions {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
    }

    button {
      padding: 8px 16px;
      border: none;
      border-radius: 4px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .btn-save {
      background: var(--primary-color);
      color: white;
    }

    .btn-save:hover:not(:disabled) {
      background: #0288d1;
      box-shadow: 0 2px 8px rgba(3, 169, 244, 0.3);
    }

    .btn-cancel {
      background: #e0e0e0;
      color: #212121;
    }

    .btn-cancel:hover:not(:disabled) {
      background: #d0d0d0;
    }

    button:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }

    .origins-list {
      padding: 8px;
      background: white;
      border: 1px solid #ddd;
      border-radius: 4px;
      margin-top: 4px;
      font-size: 12px;
      max-height: 120px;
      overflow-y: auto;
    }

    .origin-item {
      display: flex;
      align-items: center;
      gap: 4px;
      padding: 4px;
      margin-bottom: 2px;
    }

    .origin-item button {
      padding: 2px 6px;
      font-size: 11px;
      background: #ffcdd2;
      color: #c62828;
    }

    .origin-item button:hover {
      background: #ef5350;
      color: white;
    }

    .spinner {
      display: inline-block;
      width: 14px;
      height: 14px;
      border: 2px solid #e0e0e0;
      border-top-color: var(--primary-color);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }

    @keyframes spin {
      to {
        transform: rotate(360deg);
      }
    }
  `;

    async connectedCallback() {
        super.connectedCallback();
        if (this.serviceId) {
            await this.loadAccessProfile();
        }
    }

    async loadAccessProfile() {
        this.loading = true;
        this.error = null;
        try {
            const url = `${this.apiBaseUrl}/api/v1/services/${this.serviceId}/access`;
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`API returned ${response.status}: ${response.statusText}`);
            }
            const data = await response.json();
            this.accessProfile = data.access_profile;
        } catch (err) {
            this.error = err instanceof Error ? err.message : 'Failed to load access profile';
        } finally {
            this.loading = false;
        }
    }

    private async saveAccessProfile() {
        if (!this.accessProfile) return;

        this.saving = true;
        this.error = null;
        this.successMessage = null;

        try {
            const url = `${this.apiBaseUrl}/api/v1/services/${this.serviceId}/access`;
            const response = await fetch(url, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.accessProfile),
            });

            if (!response.ok) {
                const errorBody = await response.text();
                throw new Error(`API returned ${response.status}: ${errorBody || response.statusText}`);
            }

            this.successMessage = 'Access profile updated successfully!';
            setTimeout(() => { this.successMessage = null; }, 3000);
        } catch (err) {
            this.error = err instanceof Error ? err.message : 'Failed to save access profile';
        } finally {
            this.saving = false;
        }
    }

    private updateField(field: keyof AccessProfile, value: any) {
        if (!this.accessProfile) return;
        this.accessProfile = { ...this.accessProfile, [field]: value };
    }

    private addOrigin(origin: string) {
        if (!this.accessProfile || !origin.trim()) return;
        const newOrigins = [...(this.accessProfile.allowed_origins || [])];
        if (!newOrigins.includes(origin)) {
            newOrigins.push(origin);
            this.updateField('allowed_origins', newOrigins);
        }
    }

    private removeOrigin(index: number) {
        if (!this.accessProfile) return;
        const newOrigins = this.accessProfile.allowed_origins.filter((_, i) => i !== index);
        this.updateField('allowed_origins', newOrigins);
    }

    protected render() {
        if (this.loading) {
            return html`
        <div class="container">
          <div class="info-box loading">
            <span class="spinner"></span> Loading access profile...
          </div>
        </div>
      `;
        }

        if (this.error) {
            return html`
        <div class="container">
          <div class="info-box error">${this.error}</div>
          <div class="actions">
            <button class="btn-cancel" @click=${() => this.loadAccessProfile()}>
              Retry
            </button>
          </div>
        </div>
      `;
        }

        if (!this.accessProfile) {
            return html`<div class="container">No access profile available</div>`;
        }

        return html`
      <div class="container">
        <div class="header">
          <h3>${this.service?.name || this.serviceId}</h3>
          <span class="status-badge ready">Ready</span>
        </div>

        ${this.successMessage
                ? html` <div class="info-box success">${this.successMessage}</div> `
                : ''}
        ${this.error ? html` <div class="info-box error">${this.error}</div> ` : ''}

        <div class="form-grid">
          <!-- Mode -->
          <div class="form-group">
            <label>Access Mode</label>
            <select
              .value=${this.accessProfile.mode}
              @change=${(e: Event) => this.updateField('mode', (e.target as HTMLSelectElement).value)}
              ?disabled=${this.saving}
            >
              <option value="isolated">Isolated (No upstream)</option>
              <option value="upstream">Upstream (Forward to origin)</option>
              <option value="passthrough">Passthrough (Direct proxy)</option>
            </select>
            <div class="field-hint">How this service connects to clients and upstreams</div>
          </div>

          <!-- Port -->
          <div class="form-group">
            <label>Port</label>
            <input
              type="number"
              .value=${this.accessProfile.port}
              @change=${(e: Event) => this.updateField('port', parseInt((e.target as HTMLInputElement).value))}
              ?disabled=${this.saving}
              min="1"
              max="65535"
            />
            <div class="field-hint">Service listen port</div>
          </div>

          <!-- Bind Address -->
          <div class="form-group">
            <label>Bind Address</label>
            <input
              type="text"
              .value=${this.accessProfile.bind_address}
              @change=${(e: Event) => this.updateField('bind_address', (e.target as HTMLInputElement).value)}
              ?disabled=${this.saving}
              placeholder="0.0.0.0 or ::1"
            />
            <div class="field-hint">Leave empty for all interfaces</div>
          </div>

          <!-- TLS Mode -->
          <div class="form-group">
            <label>TLS Mode</label>
            <select
              .value=${this.accessProfile.tls_mode}
              @change=${(e: Event) => this.updateField('tls_mode', (e.target as HTMLSelectElement).value)}
              ?disabled=${this.saving}
            >
              <option value="disabled">Disabled (HTTP only)</option>
              <option value="self_signed">Self-signed Certificate</option>
              <option value="external">External CA</option>
              <option value="custom">Custom Certificate</option>
            </select>
            <div class="field-hint">Transport layer security</div>
          </div>

          <!-- Auth Mode -->
          <div class="form-group">
            <label>Authentication</label>
            <select
              .value=${this.accessProfile.auth_mode}
              @change=${(e: Event) => this.updateField('auth_mode', (e.target as HTMLSelectElement).value)}
              ?disabled=${this.saving}
            >
              <option value="none">None (Public)</option>
              <option value="token">Token-based</option>
              <option value="oauth2">OAuth 2.0</option>
              <option value="mTLS">mTLS (Certificate)</option>
            </select>
            <div class="field-hint">Service-level authentication</div>
          </div>

          <!-- Exposure Scope -->
          <div class="form-group">
            <label>Exposure Scope</label>
            <select
              .value=${this.accessProfile.exposure_scope}
              @change=${(e: Event) => this.updateField('exposure_scope', (e.target as HTMLSelectElement).value)}
              ?disabled=${this.saving}
            >
              <option value="local_only">Localhost Only</option>
              <option value="lan_only">LAN Only</option>
              <option value="wan_limited">WAN (Rate-limited)</option>
              <option value="wan_full">WAN (Full)</option>
            </select>
            <div class="field-hint">Geographic scope of allowed clients</div>
          </div>

          <!-- Allowed Origins -->
          <div class="form-group full">
            <label>Allowed CORS Origins</label>
            <textarea
              ?disabled=${this.saving}
              placeholder="https://example.com (one per line)"
              @blur=${(e: Event) => {
                const value = (e.target as HTMLTextAreaElement).value.trim();
                if (value) {
                    this.addOrigin(value);
                    (e.target as HTMLTextAreaElement).value = '';
                }
            }}
              rows="2"
            ></textarea>
            ${this.accessProfile.allowed_origins.length > 0
                ? html`
                  <div class="origins-list">
                    ${this.accessProfile.allowed_origins.map((origin, idx) => html`
                      <div class="origin-item">
                        <span>${origin}</span>
                        <button
                          type="button"
                          @click=${() => this.removeOrigin(idx)}
                          ?disabled=${this.saving}
                        >
                          ✕
                        </button>
                      </div>
                    `)}
                  </div>
                `
                : ''}
          </div>
        </div>

        <div class="actions">
          <button
            class="btn-cancel"
            @click=${() => this.loadAccessProfile()}
            ?disabled=${this.saving}
          >
            Cancel
          </button>
          <button
            class="btn-save"
            @click=${() => this.saveAccessProfile()}
            ?disabled=${this.saving}
          >
            ${this.saving ? html`<span class="spinner"></span> Saving...` : 'Save Changes'}
          </button>
        </div>
      </div>
    `;
    }
}

declare global {
    interface HTMLElementTagNameMap {
        'perimeter-control-service-access-editor': ServiceAccessEditor;
        'isolator-service-access-editor': ServiceAccessEditor;
    }
}

@customElement('isolator-service-access-editor')
export class IsolatorServiceAccessEditorAlias extends ServiceAccessEditor {
}

declare global {
    interface HTMLElementTagNameMap {
        'perimeter-control-service-access-editor': ServiceAccessEditor;
        'isolator-service-access-editor': ServiceAccessEditor;
    }
}
