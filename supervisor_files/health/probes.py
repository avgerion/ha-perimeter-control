"""
Health probe evaluator.

Three probe types:
  process  – check a systemd unit or PID file
  exec     – run a shell command and check exit code
  http     – HTTP GET and check status code

Results are recorded in the state DB; consecutive failures accumulate on the
capability row.  Once max_consecutive_failures is reached the capability is
marked 'degraded' so the reconciliation loop can decide to restart or alert.
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class HealthProbeEvaluator:
    def __init__(self, db, max_consecutive_failures: int = 3) -> None:
        self.db = db
        self.max_consecutive_failures = max_consecutive_failures

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_probe(self, cap_id: str, capability_module) -> str:
        """
        Run a single health probe for *capability_module* and record the
        result in the DB.

        Returns "ok" | "failed" | "timeout" | "error".
        """
        probe_config = capability_module.get_health_probe()
        if not probe_config:
            return "ok"

        probe_type = probe_config.get("type", "process")
        t0 = time.monotonic()
        result = "ok"
        output: Optional[str] = None

        try:
            if probe_type == "process":
                result, output = await self._check_process(probe_config)
            elif probe_type == "exec":
                result, output = await self._check_exec(probe_config)
            elif probe_type == "http":
                result, output = await self._check_http(probe_config)
            else:
                logger.warning("Unknown probe type '%s' for %s; skipping", probe_type, cap_id)
                result = "ok"

        except asyncio.TimeoutError:
            result = "timeout"
            output = f"Timed out after {probe_config.get('timeout_sec', 5)}s"
        except Exception as exc:
            result = "error"
            output = str(exc)

        duration_ms = int((time.monotonic() - t0) * 1000)

        self.db.record_health_probe(
            cap_id,
            probe_type,
            probe_config.get("target", probe_config.get("unit", "")),
            result,
            output,
            duration_ms,
        )

        # Check failure threshold
        cap = self.db.get_capability(cap_id)
        if cap and cap.get("consecutive_failures", 0) >= self.max_consecutive_failures:
            if cap.get("status") not in ("degraded", "failed"):
                logger.warning(
                    "%s exceeded max consecutive failures (%d); marking degraded",
                    cap_id,
                    self.max_consecutive_failures,
                )
                self.db.update_capability_status(cap_id, "degraded")

        return result

    # ------------------------------------------------------------------
    # Probe implementations
    # ------------------------------------------------------------------

    async def _check_process(self, config: Dict) -> Tuple[str, str]:
        """Check a systemd unit or PID file is alive."""
        unit = config.get("unit")
        pid_file = config.get("pid_file")
        timeout = config.get("timeout_sec", 5)

        if unit:
            proc = await asyncio.create_subprocess_exec(
                "systemctl", "is-active", "--quiet", unit,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                rc = await asyncio.wait_for(proc.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                raise
            label = f"systemctl is-active {unit}"
            return ("ok" if rc == 0 else "failed", f"{label}: rc={rc}")

        if pid_file:
            import os
            try:
                with open(pid_file) as f:
                    pid = int(f.read().strip())
                os.kill(pid, 0)  # signal 0 = existence check
                return "ok", f"PID {pid} alive"
            except (FileNotFoundError, ValueError):
                return "failed", f"PID file missing or invalid: {pid_file}"
            except ProcessLookupError:
                return "failed", "Process not found"
            except PermissionError:
                # Process exists but owned by another user — that's fine
                return "ok", "PID exists (permission check only)"

        return "ok", "No probe target configured"

    async def _check_exec(self, config: Dict) -> Tuple[str, str]:
        """Run a shell command; check exit code."""
        command = config.get("command", "true")
        expected_rc = config.get("expected_rc", 0)
        timeout = config.get("timeout_sec", 10)

        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise

        combined = (stdout.decode(errors="replace") + stderr.decode(errors="replace")).strip()
        output = combined[:500]  # cap for DB storage
        if proc.returncode == expected_rc:
            return "ok", output
        return "failed", f"rc={proc.returncode}: {output}"

    async def _check_http(self, config: Dict) -> Tuple[str, str]:
        """HTTP GET; check expected status code."""
        try:
            import aiohttp
        except ImportError:
            logger.warning("aiohttp not installed; HTTP health probes unavailable")
            return "ok", "aiohttp not installed (skipped)"

        url = config.get("url", "http://localhost/health")
        expected_status = config.get("expected_status", 200)
        timeout = config.get("timeout_sec", 5)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=timeout)
                ) as resp:
                    if resp.status == expected_status:
                        return "ok", f"HTTP {resp.status}"
                    return "failed", f"HTTP {resp.status} (expected {expected_status})"
        except aiohttp.ClientError as exc:
            return "failed", str(exc)
