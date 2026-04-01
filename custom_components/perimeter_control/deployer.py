"""Deploy Perimeter Control backend files to a Pi node over SSH.

Mirrors the logic of deploy-dashboard-web.ps1 but as an async Python class,
usable from within Home Assistant or the CLI.

Phases:
  1. preflight  — verify python3, systemd, venv presence
  2. upload     — SCP web/ and scripts/ files to /tmp
  3. install    — atomic install into /opt/isolator via `sudo install`
  4. supervisor — install supervisor package + service unit
  5. restart    — restart systemd services
  6. verify     — poll service health
"""
from __future__ import annotations

import asyncio
import logging
import os
import tarfile
import tempfile
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .const import (
    APT_DEPENDENCY_GROUPS,
    PHASE_INSTALL,
    PHASE_PREFLIGHT,
    PHASE_RESTART,
    PHASE_SUPERVISOR,
    PHASE_UPLOAD,
    PHASE_VERIFY,
    REMOTE_CONF_DIR,
    REMOTE_SCRIPTS_DIR,
    REMOTE_SERVICES_DIR,
    REMOTE_SUPERVISOR_DIR,
    REMOTE_VENV,
    REMOTE_WEB_DIR,
    SYSTEMD_DASHBOARD,
    SYSTEMD_SUPERVISOR,
)
from .service_descriptor import ServiceDescriptor, load_service_descriptors
from .ssh_client import SshClient, SshCommandError

_LOGGER = logging.getLogger(__name__)

# Resolved at runtime relative to this file (inside the HA custom component)
_COMPONENT_DIR = Path(__file__).parent
_SERVER_FILES_DIR = _COMPONENT_DIR / "server_files"
_SUPERVISOR_DIR = _COMPONENT_DIR / "supervisor_files"
_SERVICE_DESCRIPTORS_DIR = _COMPONENT_DIR / "service_descriptors"


@dataclass
class DeployProgress:
    phase: str
    message: str
    percent: int = 0
    error: str | None = None

    @property
    def is_error(self) -> bool:
        return self.error is not None


ProgressCallback = Callable[[DeployProgress], None]


class Deployer:
    """Deploy backend to a single Pi node."""

    def __init__(
        self,
        client: SshClient,
        selected_services: list[str],
        progress_cb: ProgressCallback | None = None,
    ) -> None:
        self._client = client
        self._selected_services = selected_services
        self._cb = progress_cb or (lambda p: None)

    def _emit(self, phase: str, message: str, percent: int = 0) -> None:
        _LOGGER.debug("[%s] %s", phase, message)
        self._cb(DeployProgress(phase=phase, message=message, percent=percent))

    def _emit_error(self, phase: str, message: str) -> DeployProgress:
        _LOGGER.error("[%s] %s", phase, message)
        p = DeployProgress(phase=phase, message=message, error=message)
        self._cb(p)
        return p

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def async_deploy(self) -> bool:
        """Run all deploy phases. Returns True on success."""
        try:
            await self._phase_preflight()
            await self._phase_upload()
            await self._phase_install()
            await self._phase_supervisor()
            await self._phase_restart()
            await self._phase_verify()
        except SshCommandError as exc:
            self._emit_error(exc.command[:40], str(exc))
            return False
        except Exception as exc:  # noqa: BLE001
            self._emit_error("deploy", f"Unexpected error: {exc}")
            return False
        return True

    # ------------------------------------------------------------------
    # Phase 1: Preflight
    # ------------------------------------------------------------------

    async def _phase_preflight(self) -> None:
        self._emit(PHASE_PREFLIGHT, "Verifying Python interpreter and venv...", 5)
        out = await self._client.async_run(
            "set -e; "
            f"[ -x {REMOTE_VENV}/bin/python3 ] && echo VENV_OK "
            "|| echo VENV_MISSING; "
            f"[ -d {REMOTE_WEB_DIR} ] && echo WEBDIR_OK || echo WEBDIR_MISSING"
        )
        if "VENV_MISSING" in out:
            raise SshCommandError(PHASE_PREFLIGHT, 1, f"venv not found at {REMOTE_VENV}")
        self._emit(PHASE_PREFLIGHT, "Preflight passed", 10)

    # ------------------------------------------------------------------
    # Phase 2: Upload
    # ------------------------------------------------------------------

    async def _phase_upload(self) -> None:
        self._emit(PHASE_UPLOAD, "Uploading server files...", 15)
        web_files = [
            "dashboard.py",
            "layouts.py",
            "callbacks.py",
            "data_sources.py",
        ]
        script_files = [
            "ble-scanner-v2.py",
            "ble-sniffer.py",
            "ble-debug.sh",
            "ble-proxy-profiler.py",
            "ble-gatt-mirror.py",
            "apply-rules.py",
            "network-topology.py",
            "topology_config.py",
        ]
        total = len(web_files) + len(script_files)
        for i, fname in enumerate(web_files + script_files):
            src = _SERVER_FILES_DIR / fname
            if not src.exists():
                _LOGGER.warning("Server file not found, skipping: %s", src)
                continue
            await self._client.async_put_file(src, f"/tmp/{fname}")
            pct = 15 + int(30 * (i + 1) / total)
            self._emit(PHASE_UPLOAD, f"Uploaded {fname}", pct)

    # ------------------------------------------------------------------
    # Phase 3: Install
    # ------------------------------------------------------------------

    async def _phase_install(self) -> None:
        self._emit(PHASE_INSTALL, "Installing files into active directories...", 45)
        install_script = _build_install_script()
        await self._client.async_run_b64(install_script)
        self._emit(PHASE_INSTALL, "Files installed", 55)

    # ------------------------------------------------------------------
    # Phase 4: Supervisor
    # ------------------------------------------------------------------

    async def _phase_supervisor(self) -> None:
        self._emit(PHASE_SUPERVISOR, "Preparing supervisor package...", 57)
        supervisor_src = _SUPERVISOR_DIR
        if not supervisor_src.exists():
            _LOGGER.warning("supervisor_files/ not found in component dir — skipping supervisor phase")
            return

        # Resolve required apt deps from selected service descriptors
        descriptors = load_service_descriptors(
            _SERVICE_DESCRIPTORS_DIR, self._selected_services
        )
        apt_groups: set[str] = set()
        for desc in descriptors:
            apt_groups.update(desc.apt_dependency_groups)

        # Install apt packages first
        for group in sorted(apt_groups):
            pkgs = APT_DEPENDENCY_GROUPS.get(group, [])
            if pkgs:
                pkg_str = " ".join(pkgs)
                self._emit(PHASE_SUPERVISOR, f"Installing apt group: {group}", 60)
                await self._client.async_run(
                    f"DEBIAN_FRONTEND=noninteractive sudo apt-get install -y -qq {pkg_str}"
                )

        # Install pip deps
        self._emit(PHASE_SUPERVISOR, "Installing pip dependencies...", 65)
        await self._client.async_run(
            f"sudo {REMOTE_VENV}/bin/pip install --quiet aiohttp psutil python-json-logger"
        )

        # Pack supervisor/ into tar and upload
        self._emit(PHASE_SUPERVISOR, "Uploading supervisor package...", 68)
        tar_bytes = _pack_directory(supervisor_src, arcname="supervisor")
        await self._client.async_put_bytes(tar_bytes, "/tmp/supervisor.tar.gz")

        # Upload service unit
        service_unit = _COMPONENT_DIR / "isolator-supervisor.service"
        if service_unit.exists():
            await self._client.async_put_file(service_unit, "/tmp/isolator-supervisor.service")

        # Extract + install on remote via b64 script
        sup_install_script = _build_supervisor_install_script()
        await self._client.async_run_b64(sup_install_script)
        self._emit(PHASE_SUPERVISOR, "Supervisor installed", 72)

        # Deploy service descriptors
        await self._deploy_service_descriptors(descriptors)

    async def _deploy_service_descriptors(
        self, descriptors: list[ServiceDescriptor]
    ) -> None:
        if not descriptors:
            return
        self._emit(PHASE_SUPERVISOR, "Deploying service descriptors...", 75)
        await self._client.async_run(f"sudo mkdir -p {REMOTE_SERVICES_DIR}")
        for desc in descriptors:
            fname = f"{desc.id}.service.yaml"
            src = _SERVICE_DESCRIPTORS_DIR / fname
            if not src.exists():
                _LOGGER.warning("Descriptor not found: %s", src)
                continue
            await self._client.async_put_file(src, f"/tmp/{fname}")
            await self._client.async_run(
                f"sudo install -o root -g root -m 0644 /tmp/{fname} {REMOTE_SERVICES_DIR}/{fname}"
            )
        self._emit(PHASE_SUPERVISOR, "Service descriptors deployed", 78)

    # ------------------------------------------------------------------
    # Phase 5: Restart
    # ------------------------------------------------------------------

    async def _phase_restart(self) -> None:
        self._emit(PHASE_RESTART, f"Restarting {SYSTEMD_DASHBOARD}...", 80)
        await self._client.async_run(f"sudo systemctl restart {SYSTEMD_DASHBOARD}")
        await asyncio.sleep(2)

        sup_service_exists = await self._client.async_run(
            f"systemctl list-unit-files {SYSTEMD_SUPERVISOR}.service 2>/dev/null | grep -c {SYSTEMD_SUPERVISOR} || true"
        )
        if sup_service_exists.strip() != "0":
            self._emit(PHASE_RESTART, f"Restarting {SYSTEMD_SUPERVISOR}...", 85)
            await self._client.async_run(f"sudo systemctl restart {SYSTEMD_SUPERVISOR}")
            await asyncio.sleep(2)

    # ------------------------------------------------------------------
    # Phase 6: Verify
    # ------------------------------------------------------------------

    async def _phase_verify(self) -> None:
        self._emit(PHASE_VERIFY, "Verifying service health...", 90)
        out = await self._client.async_run(
            f"systemctl is-active {SYSTEMD_DASHBOARD} || echo INACTIVE"
        )
        if "active" not in out or "INACTIVE" in out:
            raise SshCommandError(
                PHASE_VERIFY, 1, f"{SYSTEMD_DASHBOARD} is not active after deploy"
            )
        self._emit(PHASE_VERIFY, "Deploy complete — dashboard is running", 100)


# ------------------------------------------------------------------
# Script builders
# ------------------------------------------------------------------

def _build_install_script() -> str:
    """Build the remote install script for Phase 3."""
    web_files = [
        ("dashboard.py", REMOTE_WEB_DIR, "0644"),
        ("layouts.py", REMOTE_WEB_DIR, "0644"),
        ("callbacks.py", REMOTE_WEB_DIR, "0644"),
        ("data_sources.py", REMOTE_WEB_DIR, "0644"),
    ]
    script_files = [
        ("ble-scanner-v2.py", REMOTE_SCRIPTS_DIR, "0755"),
        ("ble-sniffer.py", REMOTE_SCRIPTS_DIR, "0755"),
        ("ble-debug.sh", REMOTE_SCRIPTS_DIR, "0755"),
        ("ble-proxy-profiler.py", REMOTE_SCRIPTS_DIR, "0755"),
        ("ble-gatt-mirror.py", REMOTE_SCRIPTS_DIR, "0755"),
        ("apply-rules.py", REMOTE_SCRIPTS_DIR, "0755"),
        ("network-topology.py", REMOTE_SCRIPTS_DIR, "0755"),
        ("topology_config.py", REMOTE_SCRIPTS_DIR, "0644"),
    ]
    lines = ["set -e"]
    for fname, dest, mode in web_files + script_files:
        lines.append(
            f"[ -f /tmp/{fname} ] && sudo install -o root -g root -m {mode} "
            f"/tmp/{fname} {dest}/{fname} || true"
        )
    lines.append("echo INSTALL_OK")
    return "\n".join(lines)


def _build_supervisor_install_script() -> str:
    return f"""set -e
sudo cp -a {REMOTE_SUPERVISOR_DIR} /tmp/isolator-supervisor-backup 2>/dev/null || true
cd /tmp
rm -rf /tmp/supervisor
tar --no-same-permissions --no-same-owner -xzf /tmp/supervisor.tar.gz
sudo mkdir -p {REMOTE_SUPERVISOR_DIR}
sudo cp -r /tmp/supervisor/. {REMOTE_SUPERVISOR_DIR}/
sudo chown -R root:root {REMOTE_SUPERVISOR_DIR}
sudo find {REMOTE_SUPERVISOR_DIR} -type f -exec chmod 644 {{}} +
sudo find {REMOTE_SUPERVISOR_DIR} -type d -exec chmod 755 {{}} +
[ -f /tmp/isolator-supervisor.service ] && \
  sudo install -o root -g root -m 0644 /tmp/isolator-supervisor.service \
  /etc/systemd/system/isolator-supervisor.service && \
  sudo systemctl daemon-reload && \
  sudo systemctl enable isolator-supervisor.service || true
echo SUPERVISOR_INSTALLED
"""


def _pack_directory(src_dir: Path, arcname: str) -> bytes:
    """Pack a directory into an in-memory .tar.gz and return the bytes."""
    import asyncio
    def _do_pack():
        buf = tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024)
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            tar.add(str(src_dir), arcname=arcname)
        buf.seek(0)
        return buf.read()
    return asyncio.get_event_loop().run_until_complete(
        asyncio.get_event_loop().run_in_executor(None, _do_pack)
    )
