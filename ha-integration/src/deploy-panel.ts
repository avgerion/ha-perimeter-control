/**
 * Isolator Deploy Panel
 *
 * Adds a "Deploy to Pi" section to the HA dashboard card.
 * Triggered via HA `shell_command` (configured in configuration.yaml).
 * Shows current services, deploy target, and status.
 *
 * Card YAML example:
 *   type: custom:perimeter-control-card
 *   api_base_url: "http://192.168.69.11:8080"
 *   service_id: photo_booth
 *   show_deploy_panel: true
 *   deploy_command: isolator_deploy   # matches shell_command name in configuration.yaml
 *   pi_host: "192.168.69.11"
 *   services:
 *     - photo_booth
 *     - wildlife_monitor
 */

import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

export interface DeployPanelConfig {
    /** HA shell_command name to call when Deploy is clicked, e.g. "isolator_deploy" */
    deployCommand?: string;
    /** Pi hostname/IP shown to the user (not used functionally) */
    piHost?: string;
    /** Service IDs that will be deployed (shown as chips) */
    services?: string[];
}

type DeployStatus = 'idle' | 'queued' | 'error';

@customElement('perimeter-control-deploy-panel')
export class DeployPanel extends LitElement {
    @property({ attribute: false }) hass?: any;
    @property({ attribute: false }) config?: DeployPanelConfig;

    @state() private _deploying = false;
    @state() private _status: DeployStatus = 'idle';
    @state() private _message = '';

    private async _onDeploy() {
        if (!this.hass) {
            this._setStatus('error', 'No Home Assistant context available.');
            return;
        }
        if (!this.config?.deployCommand) {
            this._setStatus(
                'error',
                'No deploy_command configured. Add deploy_command: isolator_deploy to the card YAML, ' +
                'then add that shell_command to your configuration.yaml.'
            );
            return;
        }

        this._deploying = true;
        this._setStatus('queued', 'Deploy queued — supervisor will restart momentarily.');
        try {
            await this.hass.callService('shell_command', this.config.deployCommand, {});
            // HA shell_command doesn't return output here; user sees results in HA logs / notifications.
            this._setStatus(
                'queued',
                'Deploy command sent. The Supervisor will restart. ' +
                'Check HA logs or the service editor below once it\'s back online.'
            );
        } catch (e: any) {
            this._setStatus(
                'error',
                `Failed to call shell_command.${this.config.deployCommand}: ${e?.message ?? String(e)}. ` +
                'Check that the shell_command is registered in configuration.yaml.'
            );
        } finally {
            this._deploying = false;
        }
    }

    private _setStatus(status: DeployStatus, message: string) {
        this._status = status;
        this._message = message;
    }

    protected render() {
        const host = this.config?.piHost ?? 'Pi';
        const services = this.config?.services ?? [];
        const hasCommand = Boolean(this.config?.deployCommand);

        return html`
            <div class="deploy-panel">
                <div class="panel-header">
                    <span class="panel-title">Deploy to Pi</span>
                    ${hasCommand
                ? html`<span class="cmd-tag">${this.config!.deployCommand}</span>`
                : html`<span class="cmd-tag warn">not configured</span>`}
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
                    title=${hasCommand
                ? `Call shell_command.${this.config!.deployCommand} via HA`
                : 'Configure deploy_command in card YAML first'}
                >
                    ${this._deploying ? html`<span class="spinner"></span> Deploying…` : 'Deploy to Pi'}
                </button>

                ${this._message ? html`
                    <div class="status-msg status-${this._status}">
                        ${this._message}
                    </div>
                ` : ''}

                ${!hasCommand ? html`
                    <details class="setup-hint">
                        <summary>Setup instructions</summary>
                        <ol>
                            <li>Add to <code>configuration.yaml</code>:
                                <pre>shell_command:
  isolator_deploy: &gt;-
    python3 /config/isolator-repo/ha-integration/scripts/deploy.py
    --config /config/isolator-repo/deployment.yaml
    2&gt;&amp;1 | tee /config/isolator-repo/deploy.log</pre>
                            </li>
                            <li>Create <code>/config/isolator-repo/deployment.yaml</code>:
                                <pre>host: 192.168.69.11
user: paul
ssh_key: /config/.ssh/pi_rsa
services:
  - photo_booth</pre>
                            </li>
                            <li>Add <code>deploy_command: isolator_deploy</code> to this card's YAML.</li>
                            <li>Restart Home Assistant and reload the dashboard.</li>
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
        }

        .cmd-tag {
            font-size: 11px;
            padding: 2px 6px;
            border-radius: 10px;
            background: var(--primary-color, #03a9f4);
            color: #fff;
            font-family: monospace;
        }

        .cmd-tag.warn {
            background: var(--warning-color, #ff9800);
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

        .status-queued {
            background: #e3f2fd;
            color: var(--info-color, #0277bd);
            border-left: 3px solid var(--info-color, #0277bd);
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
    interface HTMLElementTagNameMap {
        'perimeter-control-deploy-panel': DeployPanel;
        'isolator-deploy-panel': DeployPanel;
    }
}

@customElement('isolator-deploy-panel')
export class IsolatorDeployPanelAlias extends DeployPanel {
}

declare global {
    interface HTMLElementTagNameMap {
        'perimeter-control-deploy-panel': DeployPanel;
        'isolator-deploy-panel': DeployPanel;
    }
}
