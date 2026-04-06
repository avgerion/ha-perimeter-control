/**
 * Perimeter Control Panel - Minimal Version
 */

// Define the custom element class without any imports
class PerimeterControlPanel extends HTMLElement {
  private _hass: any;

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
        <button onclick="this.parentElement.parentElement.parentElement.updateEntityCount()">Refresh Entities</button>
        <div id="entity-list" style="margin-top: 16px; max-height: 300px; overflow-y: auto; border: 1px solid #ddd; padding: 8px;"></div>
      </div>
    `;
  }


  // Home Assistant will set this property
  set hass(hass: any) {
    this._hass = hass;
    if (hass) {
      this.updateEntityCount();
      this.updateEntityList();
    }
  }

  get hass() {
    return this._hass;
  }

  // For HA panel compatibility (even if unused)
  setConfig(config: any) {
    // No-op for now
  }

  updateEntityCount() {
    const countElement = this.querySelector('#entity-count') as HTMLElement;
    if (this._hass && this._hass.entities && countElement) {
      const entityCount = Object.keys(this._hass.entities).length;
      const perimeterEntities = Object.keys(this._hass.entities)
        .filter(id => id.includes('perimeter'))
        .length;
      countElement.innerHTML = `${entityCount} total (${perimeterEntities} perimeter-related)`;
    } else if (countElement) {
      countElement.innerHTML = 'No connection';
    }
  }

  updateEntityList() {
    const listElement = this.querySelector('#entity-list') as HTMLElement;
    if (this._hass && this._hass.entities && listElement) {
      const perimeterEntities = Object.keys(this._hass.entities)
        .filter(id => id.includes('perimeter'))
        .slice(0, 10); // Show first 10 only
      
      if (perimeterEntities.length > 0) {
        const entityHtml = perimeterEntities.map(entityId => {
          const entity = this._hass.entities[entityId];
          const state = entity ? entity.state : 'unknown';
          return `<div style="padding: 4px; border-bottom: 1px solid #eee;">
            <strong>${entityId}</strong>: ${state}
          </div>`;
        }).join('');
        listElement.innerHTML = entityHtml;
      } else {
        listElement.innerHTML = '<div style="color: #666;">No perimeter entities found</div>';
      }
    } else if (listElement) {
      listElement.innerHTML = '<div style="color: #666;">No connection to Home Assistant</div>';
    }
  }
}

// Register the custom element when DOM is ready and HA is loaded
function registerPanel() {
  // Define custom element if not already defined
  if (!customElements.get('perimeter-control-panel')) {
    customElements.define('perimeter-control-panel', PerimeterControlPanel);
  }
}

// Wait for DOM and try to register
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', registerPanel);
} else {
  // DOM already loaded
  registerPanel();
}
