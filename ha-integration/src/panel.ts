/**
 * Perimeter Control Panel - Simple Test Version
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

  static styles = css
    :host {
      display: block;
      padding: 16px;
      max-width: 1200px;
      margin: 0 auto;
      background: var(--card-background-color);
      color: var(--primary-text-color);
    }
    
    .test-card {
      background: var(--card-background-color);
      border-radius: 8px;
      padding: 24px;
      border: 1px solid var(--divider-color);
      text-align: center;
    }
    
    h1 {
      color: var(--primary-color);
      margin-bottom: 16px;
    }
  ;

  render() {
    const entityCount = this.hass ? Object.keys(this.hass.entities || {}).length : 0;
    
    return html
      <div class="test-card">
        <h1>🎉 Panel Test</h1>
        <p>Entities: </p>
      </div>
    ;
  }
}
