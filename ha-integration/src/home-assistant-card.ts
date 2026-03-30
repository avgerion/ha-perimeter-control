/**
 * Home Assistant Custom Card Wrapper for Service Access Editor
 * 
 * This wraps the Lit component for Home Assistant's custom card system with safety
 * mechanisms to protect against integration failures:
 * - Error boundary catches crashes, prevents propagation to HA
 * - Safe loader handles API timeouts gracefully
 * - Never blocks HA from loading or functioning
 * 
 * Install this repository as a custom card via https://github.com/hacs/frontend/wiki/Installation
 */

import { html, LitElement } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import './service-access-editor';
import './error-boundary';
import './safe-loader';
import './deploy-panel';

interface CardConfig {
    type: string;
    api_base_url?: string;
    service_id: string;
    service_name?: string;
    service_version?: string;
    theme?: string;
    api_timeout_ms?: number;       // default 10000
    enable_error_details?: boolean; // default false, set true for testing
    // Deploy panel
    show_deploy_panel?: boolean;   // default false
    deploy_command?: string;       // HA shell_command name e.g. "isolator_deploy"
    pi_host?: string;              // display only — shown in deploy panel
    services?: string[];           // service IDs to deploy (shown as chips)
}

@customElement('perimeter-control-card')
export class ServiceAccessCard extends LitElement {
    @property({ attribute: false }) hass?: any; // Home Assistant object
    @property({ attribute: false }) config?: CardConfig;

    // Prevent card being rendered in edit mode
    setConfig(config: CardConfig) {
        if (!config.service_id) {
            throw new Error('service_id is required');
        }
        this.config = config;
    }

    getConfigElement() {
        // Return the config editor element if available
        // For now, return a placeholder
        return html`
      <div style="padding: 16px;">
        <p>Edit the YAML configuration directly to configure this card.</p>
        <p><strong>Required:</strong> <code>service_id</code></p>
        <p><strong>Optional:</strong></p>
        <ul>
          <li><code>api_base_url</code> - default: <code>http://localhost:8080</code></li>
          <li><code>api_timeout_ms</code> - default: <code>10000</code> (ms)</li>
          <li><code>enable_error_details</code> - default: <code>false</code></li>
          <li><code>show_deploy_panel</code> - show Deploy to Pi panel (default: <code>false</code>)</li>
          <li><code>deploy_command</code> - HA shell_command name e.g. <code>isolator_deploy</code></li>
          <li><code>pi_host</code> - Pi address shown in deploy panel</li>
          <li><code>services</code> - list of service IDs to deploy</li>
        </ul>
      </div>
    `;
    }

    static getStubConfig() {
        return {
            type: 'custom:perimeter-control-card',
            service_id: 'photo_booth',
            api_base_url: 'http://localhost:8080',
        };
    }

    protected render() {
        if (!this.config) {
            return html`<div>Configure this card</div>`;
        }

        const apiBaseUrl = this.config.api_base_url || 'http://localhost:8080';
        const apiTimeoutMs = this.config.api_timeout_ms || 10000;
        const enableErrorDetails = this.config.enable_error_details || false;
        const showDeployPanel = this.config.show_deploy_panel || false;

        return html`
      ${showDeployPanel ? html`
        <perimeter-control-deploy-panel
          .hass=${this.hass}
          .config=${{
                    deployCommand: this.config.deploy_command,
                    piHost: this.config.pi_host || apiBaseUrl,
                    services: this.config.services || []
                }}
        ></perimeter-control-deploy-panel>
      ` : ''}
      <perimeter-control-error-boundary
        .config=${{
                title: 'Perimeter Control',
                fallbackMessage: 'Failed to load Perimeter Control. Check browser console for details.',
                showDetails: enableErrorDetails
            }
            }
      >
        <perimeter-control-safe-loader
          .config=${{
                apiUrl: apiBaseUrl,
                timeout: apiTimeoutMs,
                healthCheckPath: '/api/v1/services'
            }
            }
        >
          <perimeter-control-service-access-editor
            .apiBaseUrl=${apiBaseUrl}
            .serviceId=${this.config.service_id}
          ></perimeter-control-service-access-editor>
        </perimeter-control-safe-loader>
      </perimeter-control-error-boundary>
    `;
    }
}

@customElement('isolator-service-access-card')
export class IsolatorServiceAccessCardAlias extends ServiceAccessCard {
}

declare global {
    interface HTMLElementTagNameMap {
        'perimeter-control-card': ServiceAccessCard;
        'isolator-service-access-card': ServiceAccessCard;
    }
}

// Export card metadata for Home Assistant
(window as any).customCards = (window as any).customCards || [];
(window as any).customCards.push({
    type: 'perimeter-control-card',
    name: 'Perimeter Control',
    description: 'Control Isolator edge node access, fleet state, and deploy operations',
    preview: false,
    documentationURL:
        'https://github.com/isolator/isolator#ha-integration',
});

(window as any).customCards.push({
    type: 'isolator-service-access-card',
    name: 'Perimeter Control (Legacy Type Alias)',
    description: 'Backward-compatible alias. Prefer custom:perimeter-control-card.',
    preview: false,
    documentationURL:
        'https://github.com/isolator/isolator#ha-integration',
});
