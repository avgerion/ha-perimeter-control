/**
 * Safe Loader Component
 * 
 * Handles async loading of API-dependent components with timeout protection.
 * Guarantees:
 * - Won't hang Home Assistant if Isolator Supervisor API is unreachable
 * - Shows loading state with timeout (default 10 seconds)
 * - Graceful fallback if API doesn't respond
 * - Auto-retry with exponential backoff
 * - Never blocks HA from loading or functioning
 */

import { html, LitElement, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { TemplateResult } from 'lit';

export interface SafeLoaderConfig {
    apiUrl: string;
    timeout?: number; // milliseconds, default 10000
    maxRetries?: number; // default 3
    backoffMultiplier?: number; // default 1.5
    healthCheckPath?: string; // default '/api/v1/services'
}

type LoaderState = 'loading' | 'ready' | 'timeout' | 'error' | 'offline';

@customElement('perimeter-control-safe-loader')
export class SafeLoader extends LitElement {
    @property({ attribute: false }) config?: SafeLoaderConfig;
    @property({ attribute: false }) children?: TemplateResult;

    @state() private state: LoaderState = 'loading';
    @state() private isApiHealthy = false;
    @state() private retryCount = 0;
    @state() private lastError?: string;

    private loadingTimeout?: NodeJS.Timeout;
    private healthCheckAbort?: AbortController;

    connectedCallback() {
        super.connectedCallback();
        this.performHealthCheck();
    }

    disconnectedCallback() {
        super.disconnectedCallback();
        if (this.loadingTimeout) clearTimeout(this.loadingTimeout);
        if (this.healthCheckAbort) this.healthCheckAbort.abort();
    }

    private async performHealthCheck() {
        if (!this.config) {
            this.state = 'error';
            this.lastError = 'No configuration provided';
            return;
        }

        const timeout = this.config.timeout || 10000;
        const healthCheckPath = this.config.healthCheckPath || '/api/v1/services';
        const apiUrl = this.config.apiUrl.replace(/\/$/, ''); // Remove trailing slash

        this.state = 'loading';
        this.healthCheckAbort = new AbortController();

        // Set timeout timer
        const timeoutTimer = setTimeout(() => {
            this.healthCheckAbort?.abort();
            this.state = 'timeout';
            this.lastError = `API did not respond within ${timeout}ms`;
            console.warn(`[Isolator Safe Loader] Health check timeout: ${apiUrl}`);
        }, timeout);

        try {
            const response = await fetch(`${apiUrl}${healthCheckPath}`, {
                method: 'GET',
                signal: this.healthCheckAbort.signal,
                headers: { 'Accept': 'application/json' }
            });

            clearTimeout(timeoutTimer);

            if (response.ok) {
                this.isApiHealthy = true;
                this.state = 'ready';
                this.retryCount = 0;
                console.log('[Isolator Safe Loader] API health check passed:', apiUrl);
            } else {
                throw new Error(`API returned ${response.status}: ${response.statusText}`);
            }
        } catch (error) {
            clearTimeout(timeoutTimer);

            if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
                this.state = 'offline';
                this.lastError = 'Cannot reach Isolator Supervisor API (network error or CORS issue)';
            } else if (error instanceof DOMException && error.name === 'AbortError') {
                // Timeout already handled
            } else {
                this.state = 'error';
                this.lastError = error instanceof Error ? error.message : String(error);
            }

            console.warn('[Isolator Safe Loader] Health check failed:', this.lastError);

            // Schedule retry with exponential backoff
            const maxRetries = this.config.maxRetries || 3;
            if (this.retryCount < maxRetries) {
                const backoffMultiplier = this.config.backoffMultiplier || 1.5;
                const delayMs = Math.min(
                    1000 * Math.pow(backoffMultiplier, this.retryCount),
                    30000 // Cap at 30 seconds
                );
                this.retryCount++;
                console.log(
                    `[Isolator Safe Loader] Retrying in ${delayMs}ms (attempt ${this.retryCount}/${maxRetries})`
                );
                this.loadingTimeout = setTimeout(() => {
                    if (this.isConnected) {
                        this.performHealthCheck();
                    }
                }, delayMs);
            }
        }
    }

    retry = () => {
        this.retryCount = 0;
        this.performHealthCheck();
    };

    protected render() {
        switch (this.state) {
            case 'ready':
                return this.children || nothing;

            case 'loading':
                return this.renderLoading();

            case 'timeout':
                return this.renderTimeout();

            case 'offline':
                return this.renderOffline();

            case 'error':
            default:
                return this.renderError();
        }
    }

    private renderLoading() {
        return html`
      <ha-card>
        <div class="card-content" style="padding: 16px; text-align: center;">
          <div style="font-size: 14px; color: #666;">
            ⏳ Loading Isolator Service Access...
          </div>
          <div style="
            margin-top: 8px;
            width: 24px;
            height: 24px;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #ff5722;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-left: auto;
            margin-right: auto;
          "></div>
          <div style="font-size: 12px; color: #999; margin-top: 8px;">
            Checking Isolator Supervisor API...
          </div>
          <style>
            @keyframes spin {
              0% { transform: rotate(0deg); }
              100% { transform: rotate(360deg); }
            }
          </style>
        </div>
      </ha-card>
    `;
    }

    private renderTimeout() {
        return html`
      <ha-card>
        <div class="card-content" style="padding: 16px;">
          <div style="
            border: 1px solid #ff9800;
            border-radius: 4px;
            padding: 12px;
            background-color: #fff3e0;
            color: #e65100;
          ">
            <div style="font-weight: bold; margin-bottom: 8px;">⏱️ Connection Timeout</div>
            <div style="margin-bottom: 8px;">
              Isolator Supervisor is not responding (timeout after ${this.config?.timeout || 10000}ms).
            </div>

            <div style="margin-top: 8px; font-size: 0.9em;">
              <strong>This could mean:</strong>
              <ul style="margin: 4px 0; padding-left: 20px;">
                <li>Isolator Supervisor is not running</li>
                <li>API URL is incorrect: <code style="background: rgba(0,0,0,0.1); padding: 2px 4px;">${this.config?.apiUrl}</code></li>
                <li>Network connectivity issue</li>
                <li>Supervisor is overloaded</li>
              </ul>
            </div>

            <div style="margin-top: 12px;">
              <button
                @click=${this.retry}
                style="
                  padding: 8px 16px;
                  background-color: #ff9800;
                  color: white;
                  border: none;
                  border-radius: 2px;
                  cursor: pointer;
                  font-weight: bold;
                "
              >
                🔄 Retry Now
              </button>
              <span style="margin-left: 12px; font-size: 0.9em;">
                ${this.retryCount > 0 ? `Will auto-retry...` : ''}
              </span>
            </div>

            <div style="margin-top: 12px; padding: 8px; background: rgba(0,0,0,0.05); border-radius: 2px; font-size: 0.85em;">
              <strong>Your Home Assistant is still working:</strong> This loading card will not affect other integrations or automations.
            </div>
          </div>
        </div>
      </ha-card>
    `;
    }

    private renderOffline() {
        return html`
      <ha-card>
        <div class="card-content" style="padding: 16px;">
          <div style="
            border: 1px solid #f44336;
            border-radius: 4px;
            padding: 12px;
            background-color: #ffebee;
            color: #c62828;
          ">
            <div style="font-weight: bold; margin-bottom: 8px;">🔌 API Offline</div>
            <div style="margin-bottom: 8px;">
              Cannot reach Isolator Supervisor API at <code style="background: rgba(0,0,0,0.1); padding: 2px 4px; word-break: break-all;">${this.config?.apiUrl}</code>
            </div>

            <div style="margin-top: 8px; font-size: 0.9em;">
              <strong>Network error or CORS issue detected.</strong>
              <ul style="margin: 4px 0; padding-left: 20px;">
                <li>Is Isolator Supervisor running on the target device?</li>
                <li>Is the network accessible from Home Assistant?</li>
                <li>Check firewall rules and network isolation</li>
                <li>Verify API URL is correct (HTTP/HTTPS, IP, port)</li>
              </ul>
            </div>

            <div style="
              margin-top: 12px;
              padding: 8px;
              background: #e3f2fd;
              border-radius: 2px;
              font-size: 0.85em;
              color: #1565c0;
            ">
              <strong>Check Home Assistant Logs:</strong>
              <div>Settings → Developer Tools → Logs (search for "Isolator")</div>
            </div>

            <div style="margin-top: 12px;">
              <button
                @click=${this.retry}
                style="
                  padding: 8px 16px;
                  background-color: #f44336;
                  color: white;
                  border: none;
                  border-radius: 2px;
                  cursor: pointer;
                  font-weight: bold;
                "
              >
                🔄 Retry
              </button>
              <span style="margin-left: 12px; font-size: 0.9em;">
                Attempt ${this.retryCount}
              </span>
            </div>

            <div style="margin-top: 12px; padding: 8px; background: rgba(0,0,0,0.05); border-radius: 2px; font-size: 0.85em;">
              ✓ <strong>Your Home Assistant is unaffected:</strong> This card-level failure will not impact other automations, scenes, or integrations.
            </div>
          </div>
        </div>
      </ha-card>
    `;
    }

    private renderError() {
        return html`
      <ha-card>
        <div class="card-content" style="padding: 16px;">
          <div style="
            border: 1px solid #f44336;
            border-radius: 4px;
            padding: 12px;
            background-color: #ffebee;
            color: #c62828;
          ">
            <div style="font-weight: bold; margin-bottom: 8px;">❌ Failed to Load</div>
            <div style="margin-bottom: 8px;">${this.lastError || 'Unknown error'}</div>

            <div style="margin-top: 8px; font-size: 0.9em;">
              <strong>If this persists:</strong>
              <ul style="margin: 4px 0; padding-left: 20px;">
                <li>Check browser console (F12 → Console)</li>
                <li>Verify Isolator Supervisor version matches this integration</li>
                <li>Try removing and re-adding the card</li>
                <li>Disable the card temporarily by removing from YAML</li>
              </ul>
            </div>

            <div style="margin-top: 12px;">
              <button
                @click=${this.retry}
                style="
                  padding: 8px 16px;
                  background-color: #f44336;
                  color: white;
                  border: none;
                  border-radius: 2px;
                  cursor: pointer;
                  font-weight: bold;
                "
              >
                🔄 Retry
              </button>
            </div>

            <div style="margin-top: 12px; padding: 8px; background: rgba(0,0,0,0.05); border-radius: 2px; font-size: 0.85em;">
              ✓ <strong>Home Assistant is protected:</strong> This error is isolated to this card and won't affect your other systems.
            </div>
          </div>
        </div>
      </ha-card>
    `;
    }
}

declare global {
    interface HTMLElementTagNameMap {
        'perimeter-control-safe-loader': SafeLoader;
        'isolator-safe-loader': SafeLoader;
    }
}

@customElement('isolator-safe-loader')
export class IsolatorSafeLoaderAlias extends SafeLoader {
}

declare global {
    interface HTMLElementTagNameMap {
        'perimeter-control-safe-loader': SafeLoader;
        'isolator-safe-loader': SafeLoader;
    }
}
