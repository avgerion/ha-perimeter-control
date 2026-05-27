"""
Generic DataManager for supervisor-level data access.
Move dashboard-specific logic to dashboard_web, keep only generic config and device helpers here.
"""
import logging
from pathlib import Path
from typing import Dict, Any
import yaml

logger = logging.getLogger("supervisor.data_manager")

class DataManager:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                logger.debug(f"Loaded config: {len(config.get('devices', []))} devices")
                return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {'devices': [], 'default_policy': {}}

    def reload_config(self):
        logger.info("Reloading configuration...")
        self.config = self._load_config()

    def get_devices(self):
        return self.config.get('devices', [])

    def get_default_policy(self):
        return self.config.get('default_policy', {})
