"""
Photo Booth service-specific callbacks.
Move all logic from photo_booth_bokeh_dashboard.py or callbacks.py that is specific to photo_booth here.
"""

from datetime import datetime


def _camera_rows(data_manager):
    rows = data_manager.get_entities_with_state("photo_booth", entity_type="camera")
    normalized = []
    for row in rows:
        attrs = row.get("attributes", {}) if isinstance(row, dict) else {}
        image_url = attrs.get("image_url") or attrs.get("snapshot_url") or ""
        normalized.append(
            {
                "friendly_name": row.get("friendly_name") or row.get("id") or "camera",
                "state": str(row.get("state") or "unknown"),
                "image_url": str(image_url),
            }
        )
    return normalized

def setup_photo_booth_callbacks(doc, data_manager):
    def _update_camera_widgets() -> None:
        cameras = _camera_rows(data_manager)
        if not cameras:
            doc.camera_source.data = {"friendly_name": [], "state": [], "image_url": []}
            doc.camera_status_div.text = "<p style='color:#e67e22;'>No photo booth camera entities reported by supervisor.</p>"
            return

        doc.camera_source.data = {
            "friendly_name": [c["friendly_name"] for c in cameras],
            "state": [c["state"] for c in cameras],
            "image_url": [c["image_url"] for c in cameras],
        }

        first_image_url = next((c["image_url"] for c in cameras if c["image_url"]), "")
        if first_image_url:
            separator = "&" if "?" in first_image_url else "?"
            cache_busted = f"{first_image_url}{separator}ts={int(datetime.utcnow().timestamp())}"
            doc.photo_source.data = {"url": [cache_busted], "x": [0], "y": [0], "w": [400], "h": [300]}

        active = sum(1 for c in cameras if c["state"].lower() not in {"offline", "unavailable", "disconnected", "stopped"})
        doc.camera_status_div.text = (
            f"<p>Camera service status: <b>{active}/{len(cameras)}</b> online | "
            f"Last refresh: {datetime.utcnow().strftime('%H:%M:%S')} UTC</p>"
        )

    def _capture_photo() -> None:
        ok, message = data_manager.capture_photo("photo_booth")
        color = "#27ae60" if ok else "#c0392b"
        doc.camera_status_div.text = f"<p style='color:{color};'>{message}</p>"
        _update_camera_widgets()

    doc.capture_button.on_click(_capture_photo)
    doc.add_periodic_callback(_update_camera_widgets, 5000)
    _update_camera_widgets()
