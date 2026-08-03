"""
Photo Booth service-specific callbacks.
Move all logic from photo_booth_bokeh_dashboard.py or callbacks.py that is specific to photo_booth here.
"""

from datetime import datetime


def _get_stream_url(data_manager):
    """Get camera stream URL, converting localhost to actual supervisor host if needed."""
    rows = data_manager.get_entities_with_state("photo_booth", entity_type="camera")
    for row in rows:
        attrs = row.get("attributes", {}) if isinstance(row, dict) else {}
        stream_url = attrs.get("stream_url")
        
        if not stream_url:
            continue
        
        # Rewrite localhost URLs to actual supervisor host
        # Stream is on a different port (8100) than Supervisor API (8080), so we need to:
        # 1. Extract the host from supervisor_api_url
        # 2. Replace localhost with that host
        if isinstance(stream_url, str) and "localhost" in stream_url:
            supervisor_url = data_manager.supervisor_api_url
            # Extract host from supervisor URL
            # supervisor_url is like http://192.168.50.47:8080/api/v1
            try:
                from urllib.parse import urlparse
                parsed = urlparse(supervisor_url)
                supervisor_host = parsed.hostname or "localhost"
                # Replace localhost with actual supervisor host
                stream_url = stream_url.replace("localhost", supervisor_host)
            except Exception:
                pass  # Keep original URL on error
        
        return stream_url
    
    return None
    
    return None


def setup_photo_booth_callbacks(doc, data_manager):
    """Setup callbacks for photo booth dashboard with live streaming."""
    
    def _update_stream() -> None:
        """Update stream URL and camera status."""
        try:
            stream_url = _get_stream_url(data_manager)
            if stream_url:
                # Update the stream image src via JavaScript injection
                doc.stream_div.text = f"""
                <img id='camera-stream' 
                     src='{stream_url}' 
                     style='max-width:100%; height:auto; border:1px solid #ccc;' 
                     alt='Camera stream' />
                """
                doc.camera_status_div.text = "<p style='color:#27ae60;'>🟢 Streaming active</p>"
            else:
                doc.stream_div.text = "<p style='color:#e67e22; padding:20px;'>No active camera stream</p>"
                doc.camera_status_div.text = "<p style='color:#e67e22;'>No photo booth camera entities reported by supervisor.</p>"
        except Exception as e:
            doc.camera_status_div.text = f"<p style='color:#c0392b;'>Stream error: {e}</p>"
    
    def _capture_photo() -> None:
        """Capture a single photo snapshot."""
        ok, message = data_manager.capture_photo("photo_booth")
        color = "#27ae60" if ok else "#c0392b"
        doc.camera_status_div.text = f"<p style='color:{color};'>{message}</p>"
    
    doc.capture_button.on_click(_capture_photo)
    _update_stream()  # Initialize stream on load
