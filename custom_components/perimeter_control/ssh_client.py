"""Async SSH client wrapper (asyncssh) for Perimeter Control.

Handles:
- Connection / preflight check
- File upload (SCP)
- Remote command execution
- Structured error types
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import asyncssh

_LOGGER = logging.getLogger(__name__)

# Preflight checks run on the remote node
_PREFLIGHT_SCRIPT = r"""
set -e
echo "HOSTNAME:$(hostname)"
echo "ARCH:$(uname -m)"
echo "PY3:$(python3 --version 2>&1 | awk '{print $2}')"
# Detect hardware capabilities
[ -e /dev/video0 ] && echo "FEATURE:camera" || true
[ -d /sys/class/bluetooth ] && echo "FEATURE:bluetooth" || true
python3 -c "import smbus2" 2>/dev/null && echo "FEATURE:i2c" || true
# Check systemd
systemctl --version >/dev/null 2>&1 && echo "SYSTEMD:ok" || echo "SYSTEMD:missing"
echo "DONE"
"""


class SshConnectionError(Exception):
    """Could not establish SSH connection."""


class SshPreflightError(Exception):
    """Node failed preflight checks (missing systemd, python, etc.)."""


class SshCommandError(Exception):
    """Remote command returned non-zero exit code."""

    def __init__(self, command: str, exit_status: int, stderr: str) -> None:
        self.command = command
        self.exit_status = exit_status
        self.stderr = stderr
        super().__init__(f"Command failed (exit {exit_status}): {stderr[:200]}")


@dataclass
class NodeInfo:
    hostname: str = ""
    arch: str = ""
    python: str = ""
    features: list[str] = field(default_factory=list)
    has_systemd: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "hostname": self.hostname,
            "arch": self.arch,
            "python": self.python,
            "features": self.features,
            "has_systemd": self.has_systemd,
        }


class SshClient:
    """Async SSH client for a single Pi node."""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        private_key: str,
        connect_timeout: float = 15.0,
    ) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._private_key = private_key
        self._connect_timeout = connect_timeout
        self._conn: asyncssh.SSHClientConnection | None = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def _connect(self) -> asyncssh.SSHClientConnection:
        """Open (or reuse) the SSH connection."""
        if self._conn is not None:
            return self._conn
        try:
            key = asyncssh.import_private_key(self._private_key)
            self._conn = await asyncio.wait_for(
                asyncssh.connect(
                    self._host,
                    port=self._port,
                    username=self._user,
                    client_keys=[key],
                    known_hosts=None,   # TODO: accept-on-first-connect, store fingerprint
                ),
                timeout=self._connect_timeout,
            )
        except (OSError, asyncssh.Error, asyncio.TimeoutError) as exc:
            raise SshConnectionError(str(exc)) from exc
        return self._conn

    async def async_close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            await self._conn.wait_closed()
            self._conn = None

    # ------------------------------------------------------------------
    # Preflight
    # ------------------------------------------------------------------

    async def async_preflight(self) -> dict[str, Any]:
        """Run preflight checks; return parsed NodeInfo dict."""
        conn = await self._connect()
        result = await conn.run(_PREFLIGHT_SCRIPT, check=False)

        if "DONE" not in result.stdout:
            raise SshPreflightError(
                f"Preflight script did not complete. stdout={result.stdout!r}"
            )

        info = NodeInfo()
        for line in result.stdout.splitlines():
            if line.startswith("HOSTNAME:"):
                info.hostname = line.split(":", 1)[1]
            elif line.startswith("ARCH:"):
                info.arch = line.split(":", 1)[1]
            elif line.startswith("PY3:"):
                info.python = line.split(":", 1)[1]
            elif line.startswith("FEATURE:"):
                info.features.append(line.split(":", 1)[1])
            elif line.startswith("SYSTEMD:"):
                info.has_systemd = line.split(":", 1)[1] == "ok"

        if not info.has_systemd:
            raise SshPreflightError("Remote host does not have systemd")
        if not info.python:
            raise SshPreflightError("python3 not found on remote host")

        return info.to_dict()

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    async def async_run(self, script: str, *, sudo: bool = False) -> str:
        """Run a shell script on the remote host; return stdout. Raises SshCommandError on failure."""
        conn = await self._connect()
        if sudo:
            script = f"sudo bash -c {asyncssh.quote(script)}"
        result = await conn.run(script, check=False)
        if result.exit_status != 0:
            raise SshCommandError(script[:80], result.exit_status, result.stderr or "")
        return result.stdout

    async def async_run_b64(self, script: str) -> str:
        """Base64-encode a multi-line script and execute it safely via `base64 -d | bash`.

        Avoids all quoting/escaping hazards with complex scripts containing {}, $(), etc.
        """
        import base64
        encoded = base64.b64encode(
            script.replace("\r\n", "\n").encode()
        ).decode()
        conn = await self._connect()
        result = await conn.run(
            f"echo '{encoded}' | base64 -d | bash", check=False
        )
        if result.exit_status != 0:
            raise SshCommandError("<b64 script>", result.exit_status, result.stderr or "")
        return result.stdout

    # ------------------------------------------------------------------
    # File upload
    # ------------------------------------------------------------------

    async def async_put_file(self, local_path: str | Path, remote_path: str) -> None:
        """Upload a single file via SCP."""
        conn = await self._connect()
        try:
            async with conn.start_sftp_client() as sftp:
                await sftp.put(str(local_path), remote_path)
        except asyncssh.Error as exc:
            raise SshCommandError(f"put {local_path}", 1, str(exc)) from exc

    async def async_put_bytes(self, data: bytes, remote_path: str) -> None:
        """Upload bytes as a file (useful for in-memory content)."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            await self.async_put_file(tmp_path, remote_path)
        finally:
            os.unlink(tmp_path)
