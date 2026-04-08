/**
 * Perimeter Control Deploy Panel
 *
 * Calls the perimeter_control HA custom component REST API to deploy
 * backend files to the Pi over SSH. No shell_command configuration needed.
 *
 * Card YAML example:
 *   type: custom:perimeter-control-card
 *   api_base_url: "http://192.168.69.11:8080"
 *   service_id: photo_booth
 *   show_deploy_panel: true
 *   entry_id: abc123   # config entry ID from the perimeter_control integration
 */

import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

export interface DeployPanelConfig {
    /** Config entry ID from the perimeter_control integration (shown in HA device page) */
    entryId?: string;
    /** Pi hostname/IP shown to the user (display only) */
    piHost?: string;
    /** Service IDs shown as info chips */
    services?: string[];
}

interface ProgressEntry {
    phase: string;
    message: string;
    percent: number;
    error: string | null;
}

interface DeployStatus {
    dashboard_active: boolean;
    supervisor_active: boolean;
    deploy_in_progress: boolean;
    deploy_log: ProgressEntry[];
}

@customElement('perimeter-control-deploy-panel')
export class DeployPanel extends LitElement {
    @property({ attribute: false }) hass?: any;
    @property({ attribute: false }) config?: DeployPanelConfig;

    @state() private _deploying = false;
    @state() private _error = '';
    @state() private _log: ProgressEntry[] = [];
    @state() private _dashboardActive: boolean | null = null;
    @state() private _supervisorActive: boolean | null = null;

    private _pollTimer: ReturnType<typeof setInterval> | null = null;

    override disconnectedCallback() {
        super.disconnectedCallback();
        this._stopPolling();
    }

    private _apiBase(): string {
        return '/api/perimeter_control';
    }

    private async _fetchAuth(path: string, init?: RequestInit): Promise<Response> {
        const token = this.hass?.auth?.data?.access_token ?? '';
        return fetch(path, {
            ...init,
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
                ...(init?.headers ?? {}),
            },
        });
    }

    private async _onDeploy() {
        const entryId = this.config?.entryId;
        if (!this.hass) {
            this._error = 'No Home Assistant context available.';
            return;
        }
        if (!entryId) {
            this._error = 'entry_id not configured. Add entry_id to the card YAML (find it on the device page in Settings → Devices).';
            return;
        }

        this._error = '';
        this._log = [];
        this._deploying = true;

        try {
            const res = await this._fetchAuth(
                `${this._apiBase()}/${entryId}/deploy`,
                { method: 'POST' }
            );
            if (!res.ok) {
                const body = await res.json().catch(() => ({}));
                this._error = body.message ?? `Deploy request failed (${res.status})`;
                this._deploying = false;
                return;
            }
            this._startPolling(entryId);
        } catch (e: any) {
            this._error = `Network error: ${e?.message ?? String(e)}`;
            this._deploying = false;
        }
    }

    private _startPolling(entryId: string) {
        this._stopPolling();
        this._pollTimer = setInterval(() => this._poll(entryId), 1500);
    }

    private _stopPolling() {
        if (this._pollTimer !== null) {
            clearInterval(this._pollTimer);
            this._pollTimer = null;
        }
    }

    private async _poll(entryId: string) {
        try {
            const res = await this._fetchAuth(`${this._apiBase()}/${entryId}/status`);
            if (!res.ok) return;
            const status: DeployStatus = await res.json();
            this._log = status.deploy_log;
            this._dashboardActive = status.dashboard_active;
            this._supervisorActive = status.supervisor_active;
            if (!status.deploy_in_progress) {
                this._deploying = false;
                this._stopPolling();
            }
        } catch {
            // transient — keep polling
        }
    }

    protected render() {
        const host = this.config?.piHost ?? 'Pi';
        const services = this.config?.services ?? [];
        const hasEntryId = Boolean(this.config?.entryId);
        const lastEntry = this._log[this._log.length - 1];
        const percent = lastEntry?.percent ?? 0;
        const hasError = this._log.some(e => e.error) || Boolean(this._error);

        return html`
            <div class="deploy-panel">
                <div class="panel-header">
                    <span class="panel-title">Deploy to Pi</span>
                    <span class="status-dot ${this._dashboardActive ? 'dot-ok' : this._dashboardActive === null ? 'dot-unknown' : 'dot-err'}"
                          title="Dashboard service: ${this._dashboardActive ? 'active' : 'inactive'}"></span>
                </div>

                <div class="info-row">
                    <span class="info-label">Target</span>
                    <span class="info-value">${host}</span>
                </div>

                ${services.length > 0 ? html`
                    <div class="info-row top-align">
                        <span class="info-label">Services</span>
                        <div class="chips">
                            ${services.map(s => html`<span class="chip">${s}</span>`)}
                        </div>
                    </div>
                ` : ''}

                <button
                    class="deploy-btn"
                    @click=${this._onDeploy}
                    ?disabled=${this._deploying}
                >
                    ${this._deploying
                ? html`<span class="spinner"></span> Deploying…`
                : 'Deploy to Pi'}
                </button>

                ${this._deploying ? html`
                    <div class="progress-bar-wrap">
                        <div class="progress-bar" style="width:${percent}%"></div>
                    </div>
                ` : ''}

                ${this._error ? html`
                    <div class="status-msg status-error">${this._error}</div>
                ` : ''}

                ${this._log.length > 0 ? html`
                    <div class="log ${hasError ? 'log-error' : ''}">
                        ${this._log.map(e => html`
                            <div class="log-row ${e.error ? 'log-row-error' : ''}">
                                <span class="log-phase">${e.phase}</span>
                                <span class="log-msg">${e.error ?? e.message}</span>
                            </div>
                        `)}
                    </div>
                ` : ''}

                ${!hasEntryId ? html`
                    <details class="setup-hint">
                        <summary>Setup instructions</summary>
                        <ol>
                            <li>Install the <strong>Perimeter Control</strong> integration via HACS or manually copy <code>*.py, manifest.json</code> to <code>/config/custom_components/perimeter_control/</code>.</li>
                            <li>In HA go to <strong>Settings → Devices &amp; Services → Add Integration</strong> and search for <em>Perimeter Control</em>.</li>
                            <li>Complete the Add Device wizard (host, SSH key, services).</li>
                            <li>Copy the entry ID from the device page and add <code>entry_id: &lt;id&gt;</code> to this card's YAML.</li>
                        </ol>
                    </details>
                ` : ''}
            </div>
        `;
    }

    static styles = css`
        :host {
            display: block;
        }

        .deploy-panel {
            padding: 12px 16px;
            border: 1px solid var(--divider-color, #e0e0e0);
            border-radius: 8px;
            background: var(--card-background-color, #fff);
            margin-top: 8px;
        }

        .panel-header {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 10px;
        }

        .panel-title {
            font-weight: 600;
            font-size: 14px;
            color: var(--primary-text-color);
            flex: 1;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            flex-shrink: 0;
        }
        .dot-ok      { background: var(--success-color, #43a047); }
        .dot-err     { background: var(--error-color,   #e53935); }
        .dot-unknown { background: var(--disabled-color, #bdbdbd); }

        .progress-bar-wrap {
            height: 3px;
            background: var(--divider-color, #e0e0e0);
            border-radius: 2px;
            margin: 8px 0 4px;
            overflow: hidden;
        }
        .progress-bar {
            height: 100%;
            background: var(--primary-color, #03a9f4);
            border-radius: 2px;
            transition: width 0.4s ease;
        }

        .log {
            margin-top: 8px;
            font-size: 11px;
            font-family: monospace;
            background: var(--code-background-color, #f5f5f5);
            border-radius: 4px;
            padding: 6px 8px;
            max-height: 140px;
            overflow-y: auto;
        }
        .log-error {
            border-left: 3px solid var(--error-color, #e53935);
        }
        .log-row {
            display: flex;
            gap: 6px;
            line-height: 1.6;
            color: var(--primary-text-color);
        }
        .log-row-error {
            color: var(--error-color, #c62828);
        }
        .log-phase {
            color: var(--secondary-text-color, #888);
            min-width: 72px;
            flex-shrink: 0;
        }

        .info-row {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 6px;
            font-size: 13px;
        }

        .info-row.top-align {
            align-items: flex-start;
        }

        .info-label {
            color: var(--secondary-text-color, #757575);
            min-width: 56px;
            flex-shrink: 0;
        }

        .info-value {
            color: var(--primary-text-color);
            font-family: monospace;
            font-size: 12px;
        }

        .chips {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
        }

        .chip {
            background: var(--primary-color, #03a9f4);
            color: #fff;
            border-radius: 10px;
            padding: 2px 8px;
            font-size: 11px;
        }

        .deploy-btn {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            width: 100%;
            margin-top: 10px;
            padding: 8px 16px;
            background: var(--primary-color, #03a9f4);
            color: #fff;
            border: none;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: opacity 0.15s;
        }

        .deploy-btn:disabled {
            background: var(--disabled-color, #bdbdbd);
            cursor: default;
            opacity: 0.6;
        }

        .deploy-btn:not(:disabled):hover {
            opacity: 0.88;
        }

        .spinner {
            display: inline-block;
            width: 12px;
            height: 12px;
            border: 2px solid rgba(255,255,255,0.4);
            border-top-color: #fff;
            border-radius: 50%;
            animation: spin 0.7s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .status-msg {
            margin-top: 8px;
            padding: 8px 10px;
            border-radius: 4px;
            font-size: 12px;
            line-height: 1.5;
        }

        .status-error {
            background: #ffebee;
            color: var(--error-color, #c62828);
            border-left: 3px solid var(--error-color, #c62828);
        }

        .setup-hint {
            margin-top: 10px;
            font-size: 12px;
            color: var(--secondary-text-color, #555);
        }

        .setup-hint summary {
            cursor: pointer;
            font-weight: 500;
            color: var(--primary-color, #03a9f4);
            user-select: none;
        }

        .setup-hint ol {
            margin: 8px 0 0 16px;
            padding: 0;
            line-height: 1.8;
        }

        pre {
            background: var(--code-background-color, #f5f5f5);
            border-radius: 4px;
            padding: 6px 8px;
            margin: 4px 0;
            font-size: 11px;
            overflow-x: auto;
            white-space: pre-wrap;
        }

        code {
            background: rgba(0, 0, 0, 0.06);
            border-radius: 3px;
            padding: 1px 4px;
            font-family: monospace;
            font-size: 11px;
        }
    `;
}

declare global {

    // ─── Configurable Constants ─────────────────────────────────────────────
    const ISOLATOR_DEPLOY_PANEL_TAG = (window as any).PERIMETERCONTROL_DEPLOY_PANEL_TAG || 'perimeter-control-deploy-panel';

    @customElement(ISOLATOR_DEPLOY_PANEL_TAG)
    export class PerimeterControlDeployPanelAlias extends DeployPanel { }

    declare global {
        interface HTMLElementTagNameMap {
            'perimeter-control-deploy-panel': DeployPanel;
            [typeof ISOLATOR_DEPLOY_PANEL_TAG]: DeployPanel;
        }
    }
