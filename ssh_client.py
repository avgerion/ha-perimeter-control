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
        connect_timeout: float = 30.0,
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
                    host=self._host,
                    port=self._port,
                    username=self._user,
                    client_keys=[key],
                    known_hosts=None,   # TODO: accept-on-first-connect, store fingerprint
                    keepalive_interval=30,  # Send keepalive every 30 seconds
                    keepalive_count_max=3,  # Allow 3 missed keepalives before disconnect
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
        """Run preflight checks; return parsed NodeInfo dict. If preflight fails, run diagnostics."""
        conn = await self._connect()
        # First, run a simple echo test and log output
        try:
            proc = await conn.create_process("echo test")
            echo_stdout, echo_stderr = await proc.communicate()
            echo_exit_status = proc.exit_status
        except Exception as exc:
            _LOGGER.warning("SSH echo test failed: %r", exc)
            raise SshPreflightError(f"Echo test failed: {exc}") from exc
        _LOGGER.debug("SSH echo test completed")

        try:
            proc = await conn.create_process(_PREFLIGHT_SCRIPT)
            stdout, stderr = await proc.communicate()
            exit_status = proc.exit_status
        except Exception as exc:
            _LOGGER.warning("SSH preflight failed: %r", exc)
            raise SshPreflightError(f"Preflight script failed: {exc}") from exc
        _LOGGER.debug("SSH preflight completed")

        if "DONE" not in (stdout or ""):
            # Run diagnostics if preflight fails
            diag_results = await self._run_diagnostics(conn)
            _LOGGER.debug("SSH diagnostics completed: %r", diag_results)
            raise SshPreflightError(
                f"Preflight script did not complete. stdout={stdout!r} | diagnostics={diag_results!r}"
            )

        info = NodeInfo()
        for line in (stdout or "").splitlines():
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

    async def _run_diagnostics(self, conn) -> dict:
        """Run a series of SSH commands using multiple methods to diagnose remote execution issues."""
        import traceback
        import shlex
        commands = [
            "echo DIAG1:hello",
            "whoami",
            "uname -a",
            "id",
            "pwd",
            "ls -l /tmp",
            "ls -l /",
            "cat /etc/os-release || cat /etc/issue",
            "which python3",
            "python3 --version",
            "echo $SHELL",
            "env | sort | grep -E 'SHELL|USER|HOME|PATH'",
            "ls -l $HOME",
            "ps aux | head -5",
            "df -h",
            "uptime",
            "date",
            "echo DIAG2:done"
        ]
        results = {}
        for cmd in commands:
            results[cmd] = {}
            # Method 1: Standard run
            try:
                res = await conn.run(cmd, check=False)
                if getattr(res, "stdout", None) is None and getattr(res, "stderr", None) is None:
                    _LOGGER.debug("asyncssh.run returned None for stdout/stderr (environment issue)")
                results[cmd]["run"] = {
                    "stdout": getattr(res, "stdout", None),
                    "stderr": getattr(res, "stderr", None),
                    "exit_status": getattr(res, "exit_status", None),
                    "type": str(type(res)),
                }
            except Exception as exc:
                results[cmd]["run"] = {"error": str(exc), "traceback": traceback.format_exc()}
            # Method 2: run with PTY
            try:
                res = await conn.run(cmd, check=False, term_type="xterm")
                if getattr(res, "stdout", None) is None and getattr(res, "stderr", None) is None:
                    _LOGGER.debug("asyncssh.run with pty=True returned None (environment issue)")
                results[cmd]["run_pty"] = {
                    "stdout": getattr(res, "stdout", None),
                    "stderr": getattr(res, "stderr", None),
                    "exit_status": getattr(res, "exit_status", None),
                    "type": str(type(res)),
                }
            except Exception as exc:
                results[cmd]["run_pty"] = {"error": str(exc), "traceback": traceback.format_exc()}
            # Method 3: run with bash -c (fixed quote)
            try:
                res = await conn.run(f"bash -c {shlex.quote(cmd)}", check=False)
                results[cmd]["run_bash_c"] = {
                    "stdout": getattr(res, "stdout", None),
                    "stderr": getattr(res, "stderr", None),
                    "exit_status": getattr(res, "exit_status", None),
                    "type": str(type(res)),
                }
            except Exception as exc:
                results[cmd]["run_bash_c"] = {"error": str(exc), "traceback": traceback.format_exc()}
            # Method 4: create_process (recommended)
            try:
                proc = await conn.create_process(cmd)
                stdout, stderr = await proc.communicate()
                results[cmd]["create_process"] = {
                    "stdout": stdout,
                    "stderr": stderr,
                    "exit_status": proc.exit_status,
                    "type": str(type(proc)),
                }
            except Exception as exc:
                results[cmd]["create_process"] = {"error": str(exc), "traceback": traceback.format_exc()}
        return results

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    async def async_run(self, script: str, *, sudo: bool = False) -> str:
        """Run a shell script on the remote host; return stdout. Uses create_process for reliability. Raises SshCommandError on failure."""
        import shlex
        conn = await self._connect()
        if sudo:
            script = f"sudo bash -c {shlex.quote(script)}"
        _LOGGER.debug("Executing SSH command: %s", script[:100] + ("..." if len(script) > 100 else ""))
        # Try once, and if the SSH connection was closed mid-run, attempt
        # to reconnect and retry a single time to mitigate transient drops.
        last_exc = None
        for attempt in range(2):
            try:
                conn = await self._connect()
                proc = await conn.create_process(script)
                stdout, stderr = await proc.communicate()
                exit_status = proc.exit_status
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                _LOGGER.warning("SSH command execution attempt %d failed: %r", attempt + 1, exc)
                # Close existing connection object and retry once
                try:
                    await self.async_close()
                except Exception:
                    pass
                # Short backoff before retry
                if attempt == 0:
                    await asyncio.sleep(0.5)
                continue
        if last_exc is not None:
            raise SshCommandError(script[:80], 1, str(last_exc)) from last_exc
        _LOGGER.debug("SSH command completed")
        if exit_status != 0:
            raise SshCommandError(script[:80], exit_status, stderr or "")
        return stdout or ""

    async def async_run_b64(self, script: str) -> str:
        """Base64-encode a multi-line script and execute it safely via `base64 -d | bash`.

        Avoids all quoting/escaping hazards with complex scripts containing {}, $(), etc.
        """
        import base64
        encoded = base64.b64encode(
            script.replace("\r\n", "\n").encode()
        ).decode()
        conn = await self._connect()
        try:
            proc = await conn.create_process(f"echo '{encoded}' | base64 -d | bash")
            stdout, stderr = await proc.communicate()
            exit_status = proc.exit_status
        except Exception as exc:
            _LOGGER.warning("SSH base64 script execution failed: %r", exc)
            raise SshCommandError("<b64 script>", 1, str(exc)) from exc
        if exit_status != 0:
            raise SshCommandError("<b64 script>", exit_status, stderr or "")
        return stdout or ""

    # ------------------------------------------------------------------
    # File upload
    # ------------------------------------------------------------------

    async def async_put_file(self, local_path: str | Path, remote_path: str) -> None:
        """Upload a single file via SFTP."""
        conn = await self._connect()
        try:
            async with conn.start_sftp_client() as sftp:
                # Create a BytesIO buffer from file content
                local_path = Path(local_path)
                file_data = await asyncio.to_thread(local_path.read_bytes)
                
                # Write to remote using SFTP write operations
                async with sftp.open(remote_path, 'wb') as remote_file:
                    await remote_file.write(file_data)
        except asyncssh.Error as exc:
            raise SshCommandError(f"put {local_path}", 1, str(exc)) from exc

    async def async_put_bytes(self, data: bytes, remote_path: str) -> None:
        """Upload bytes as a file (useful for in-memory content)."""
        conn = await self._connect()
        try:
            async with conn.start_sftp_client() as sftp:
                # Write bytes directly to remote file
                async with sftp.open(remote_path, 'wb') as remote_file:
                    await remote_file.write(data)
        except asyncssh.Error as exc:
            raise SshCommandError(f"put bytes to {remote_path}", 1, str(exc)) from exc
