/**
 * Error Boundary Component
 * 
 * Wraps components to catch errors gracefully without crashing Home Assistant.
 * If a child component throws an error, this renders a safe fallback and logs to console.
 * 
 * Safety guarantees:
 * - No errors propagate to HA parent (LitElement lifecycle protection)
 * - User can still access HA even if Perimeter Control integration fails
 * - Easy retry mechanism for transient failures
 * - Console warnings for debugging without breaking UI
 */

import { html, LitElement, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { TemplateResult } from 'lit';

export interface ErrorBoundaryConfig {
    title?: string;
    fallbackMessage?: string;
    showDetails?: boolean;
    onError?: (error: Error, retry: () => void) => void;
}

@customElement('perimeter-control-error-boundary')
export class ErrorBoundary extends LitElement {
    @property({ attribute: false }) config?: ErrorBoundaryConfig;
    @state() private hasError = false;
    @state() private error?: Error;
    @state() private errorCount = 0;

    // Map of child render functions to catch
    private childRender?: () => TemplateResult;

    constructor() {
        super();
        // Override error handler to catch unhandled rejections in children
        this.addEventListener('error', (e) => this.handleError(e as ErrorEvent), true);
    }

    connectedCallback() {
        super.connectedCallback();
        // Listen for unhandled promise rejections in this element tree
        window.addEventListener('unhandledrejection', this.handleUnhandledRejection);
    }

    disconnectedCallback() {
        super.disconnectedCallback();
        window.removeEventListener('unhandledrejection', this.handleUnhandledRejection);
    }

    private handleUnhandledRejection = (event: PromiseRejectionEvent) => {
        // Only handle if this error originated from our subtree
        if (this.contains(event.target as Node)) {
            this.handleError(new Error(`Promise rejection: ${event.reason}`));
            event.preventDefault();
        }
    };

    private handleError = (event: ErrorEvent | Error) => {
        const error = event instanceof ErrorEvent ? event.error : event;
        this.errorCount++;

        if (!error) {
            return;
        }

        this.hasError = true;
        this.error = error;

        // Log to console for debugging
        console.error(
            `[Isolator Error Boundary] Component crashed (attempt #${this.errorCount}):`,
            error.message,
            error.stack
        );

        // Call user's error handler if provided
        if (this.config?.onError) {
            this.config.onError(error, () => this.retry());
        }
    };

    retry = () => {
        this.hasError = false;
        this.error = undefined;
        this.requestUpdate();
    };

    setChildRender(fn: () => TemplateResult) {
        this.childRender = fn;
        this.requestUpdate();
    }

    protected render() {
        if (this.hasError) {
            return this.renderErrorFallback();
        }

        if (this.childRender) {
            try {
                return this.childRender();
            } catch (error) {
                this.handleError(error instanceof Error ? error : new Error(String(error)));
                return this.renderErrorFallback();
            }
        }

        return nothing;
    }

    private renderErrorFallback() {
        const title = this.config?.title || 'Perimeter Control';
        const message = this.config?.fallbackMessage || 'Failed to load integration';
        const showDetails = this.config?.showDetails !== false;

        return html`
      <ha-card>
        <div class="card-content" style="padding: 16px;">
          <div style="
            border: 1px solid #ff5722;
            border-radius: 4px;
            padding: 12px;
            background-color: #ffebee;
            color: #c62828;
          ">
            <div style="font-weight: bold; margin-bottom: 8px;">⚠️ ${title}</div>
            <div style="margin-bottom: 8px;">${message}</div>
            
            ${showDetails && this.error
                ? html`
                <details style="margin-top: 8px; font-size: 0.9em; color: #d32f2f;">
                  <summary style="cursor: pointer; user-select: none;">Error details</summary>
                  <pre style="
                    margin: 8px 0 0 0;
                    padding: 8px;
                    background: rgba(0,0,0,0.05);
                    border-radius: 2px;
                    overflow-x: auto;
                    font-size: 0.85em;
                  ">${this.error.message}
${this.error.stack || 'No stack trace available'}</pre>
                </details>
              `
                : nothing
            }

            <div style="margin-top: 12px;">
              <button
                @click=${this.retry}
                style="
                  padding: 8px 16px;
                  background-color: #ff5722;
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
                Attempt ${this.errorCount}
                ${this.errorCount > 3 ? ' - Consider checking Home Assistant logs' : ''}
              </span>
            </div>

            <div style="margin-top: 12px; font-size: 0.85em; opacity: 0.7;">
              <strong>Troubleshooting steps:</strong>
              <ul style="margin: 4px 0; padding-left: 20px;">
                <li>Check your browser console for errors (F12 → Console tab)</li>
                <li>Verify Isolator Supervisor is running at the configured API URL</li>
                <li>Check your Home Assistant logs for related errors</li>
                <li>If problem persists, disable this card by removing it from your YAML configuration</li>
              </ul>
            </div>
          </div>
        </div>
      </ha-card>
    `;
    }

    static getStyles() {
        return `
      :host {
        display: block;
      }
      
      ha-card {
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-radius: 4px;
      }
    `;
    }
}

@customElement('isolator-error-boundary')
export class IsolatorErrorBoundaryAlias extends ErrorBoundary {
}

declare global {
    interface HTMLElementTagNameMap {
        'perimeter-control-error-boundary': ErrorBoundary;
        'isolator-error-boundary': ErrorBoundary;
    }
}
