class PerimeterControlPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._hass = null;
    this._devices = [];
    this._loading = false;
    this._message = '';
    this._error = '';
    this._serviceDrafts = {};
    this._saving = {};
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._devices.length && !this._loading) {
      this._refreshDevices();
    }
    this._render();
  }

  get hass() {
    return this._hass;
  }

  async _api(method, path, body) {
    if (!this._hass) {
      throw new Error('Home Assistant is not available');
    }
    return this._hass.callApi(method, path, body);
  }

  async _refreshDevices() {
    this._loading = true;
    this._error = '';
    this._message = '';
    this._render();

    try {
      const devices = await this._api('GET', 'perimeter_control/devices');
      this._devices = Array.isArray(devices) ? devices : [];
      this._serviceDrafts = {};
      for (const device of this._devices) {
        this._serviceDrafts[device.entry_id] = new Set(device.services || []);
      }
    } catch (err) {
      this._error = `Failed to load devices: ${err?.message || err}`;
    } finally {
      this._loading = false;
      this._render();
    }
  }

  _toggleService(entryId, serviceId, checked) {
    const draft = this._serviceDrafts[entryId] || new Set();
    if (checked) {
      draft.add(serviceId);
    } else {
      draft.delete(serviceId);
    }
    this._serviceDrafts[entryId] = draft;
    this._render();
  }

  async _saveServices(entryId) {
    const selected = Array.from(this._serviceDrafts[entryId] || []);
    if (!selected.length) {
      this._error = 'Select at least one service before saving.';
      this._message = '';
      this._render();
      return;
    }

    this._saving[entryId] = true;
    this._error = '';
    this._message = '';
    this._render();

    try {
      await this._api('POST', `perimeter_control/${entryId}/services`, { services: selected });
      const device = this._devices.find((d) => d.entry_id === entryId);
      if (device) {
        device.services = selected;
      }
      this._message = 'Service options updated successfully.';
      await this._refreshDevices();
    } catch (err) {
      this._error = `Failed to save service options: ${err?.message || err}`;
    } finally {
      this._saving[entryId] = false;
      this._render();
    }
  }

  async _deployDevice(entryId) {
    try {
      await this._api('POST', `perimeter_control/${entryId}/deploy`, {});
      this._message = 'Deploy queued.';
      this._error = '';
      this._render();
    } catch (err) {
      this._error = `Failed to queue deploy: ${err?.message || err}`;
      this._message = '';
      this._render();
    }
  }

  _render() {
    const style = `
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
    `;

    const loadingHtml = this._loading ? '<p class="loading">Loading devices...</p>' : '';
    const noDevicesHtml = !this._loading && !this._devices.length
      ? '<p>No devices found. Add a Perimeter Control integration entry first.</p>'
      : '';

    const cardsHtml = this._devices.map((device) => {
      const available = Array.isArray(device.available_services) ? device.available_services : [];
      const selected = this._serviceDrafts[device.entry_id] || new Set(device.services || []);
      const svcHtml = available.map((serviceId) => {
        const checked = selected.has(serviceId) ? 'checked' : '';
        return `
          <label class="svc">
            <input
              type="checkbox"
              data-action="toggle-service"
              data-entry-id="${device.entry_id}"
              data-service-id="${serviceId}"
              ${checked}
            />
            ${serviceId}
          </label>
        `;
      }).join('');

      const saving = !!this._saving[device.entry_id];
      return `
        <div class="card">
          <p class="title">${device.title || 'Perimeter Device'}</p>
          <p class="meta">Host: ${device.host || 'unknown'}</p>
          <p class="meta">Dashboard: ${device.dashboard_active ? 'online' : 'offline'} | Supervisor: ${device.supervisor_active ? 'online' : 'offline'}</p>

          <div class="services">
            <strong>Enabled services</strong>
            ${svcHtml || '<p class="meta">No service options available.</p>'}
          </div>

          <div class="card-actions">
            <button
              class="primary"
              data-action="save-services"
              data-entry-id="${device.entry_id}"
              ${saving ? 'disabled' : ''}
            >
              ${saving ? 'Saving...' : 'Save Services'}
            </button>
            <button
              data-action="deploy-device"
              data-entry-id="${device.entry_id}"
            >
              Deploy Device
            </button>
          </div>
        </div>
      `;
    }).join('');

    const messageHtml = this._message ? `<div class="msg ok">${this._message}</div>` : '';
    const errorHtml = this._error ? `<div class="msg err">${this._error}</div>` : '';

    this.shadowRoot.innerHTML = `
      <style>${style}</style>
      <h1>Perimeter Control</h1>
      <p class="sub">Manage installed devices and update enabled service options.</p>
      <div class="toolbar">
        <button data-action="refresh">Refresh Devices</button>
      </div>
      ${messageHtml}
      ${errorHtml}
      ${loadingHtml}
      ${noDevicesHtml}
      <div class="grid">${cardsHtml}</div>
    `;

    this._wireEvents();
  }

  _wireEvents() {
    this.shadowRoot.querySelectorAll('[data-action="refresh"]').forEach((el) => {
      el.addEventListener('click', () => this._refreshDevices());
    });

    this.shadowRoot.querySelectorAll('[data-action="toggle-service"]').forEach((el) => {
      el.addEventListener('change', (ev) => {
        const entryId = ev.currentTarget.dataset.entryId;
        const serviceId = ev.currentTarget.dataset.serviceId;
        this._toggleService(entryId, serviceId, ev.currentTarget.checked);
      });
    });

    this.shadowRoot.querySelectorAll('[data-action="save-services"]').forEach((el) => {
      el.addEventListener('click', (ev) => {
        const entryId = ev.currentTarget.dataset.entryId;
        this._saveServices(entryId);
      });
    });

    this.shadowRoot.querySelectorAll('[data-action="deploy-device"]').forEach((el) => {
      el.addEventListener('click', (ev) => {
        const entryId = ev.currentTarget.dataset.entryId;
        this._deployDevice(entryId);
      });
    });
  }
}

customElements.define('perimeter-control-panel', PerimeterControlPanel);
