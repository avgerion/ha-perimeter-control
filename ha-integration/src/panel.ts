/**
 * Perimeter Control Panel - Minimal Version
 */

// Define the custom element class without any imports
class PerimeterControlPanel extends HTMLElement {
  private hass: any;

  constructor() {
    super();
    this.innerHTML = `
      <style>
        :host {
          display: block;
          padding: 20px;
          font-family: var(--primary-font-family, sans-serif);
          color: var(--primary-text-color, #333);
        }
        .panel {
          max-width: 800px;
          margin: 0 auto;
          background: var(--card-background-color, #fff);
          padding: 24px;
          border-radius: 8px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
          color: var(--primary-color, #1976d2);
          margin-bottom: 16px;
        }
        .status {
          background: #e8f5e8;
          padding: 12px;
          border-radius: 4px;
          margin-bottom: 16px;
        }
        button {
          background: var(--primary-color, #1976d2);
          color: white;
          border: none;
          padding: 8px 16px;
          border-radius: 4px;
          cursor: pointer;
          margin-right: 8px;
        }
      </style>
      <div class="panel">
        <h1>🛡️ Perimeter Control</h1>
        <div class="status">
          <strong>Status:</strong> Panel loaded successfully<br>
          <strong>Entities:</strong> <span id="entity-count">Loading...</span><br>
          <strong>Time:</strong> <span id="current-time">${new Date().toLocaleString()}</span>
        </div>
        <button onclick="window.location.reload()">Refresh</button>
        <button onclick="this.getRootNode().host.updateEntityCount()">Update Count</button>
      </div>
    `;
  }

  set _hass(hass: any) {
    this.hass = hass;
    this.updateEntityCount();
  }

  updateEntityCount() {
    const countElement = this.querySelector('#entity-count') as HTMLElement;
    if (this.hass && this.hass.entities && countElement) {
      const entityCount = Object.keys(this.hass.entities).length;
      const perimeterEntities = Object.keys(this.hass.entities)
        .filter(id => id.includes('perimeter'))
        .length;
      countElement.innerHTML = `${entityCount} total (${perimeterEntities} perimeter-related)`;
    }
  }
}

// Register the custom element
customElements.define('perimeter-control-panel', PerimeterControlPanel);
