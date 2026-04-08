#!/usr/bin/env python3
"""
PerimeterControl Deploy Script — HA-Compatible Python Replacement for deploy-dashboard-web.ps1
==============================================================================================

Reads config/services/*.service.yaml to determine which apt packages are needed
(gstreamer, i2c, etc.) and installs ONLY those required by the configured services.
Fixes the chmod bug from the PowerShell script by using --no-same-permissions with
sudo tar extraction instead of a post-extraction find+chmod.

Usage from HA configuration.yaml (shell_command):
    perimetercontrol_deploy: >-
        python3 /config/perimetercontrol-repo/ha-integration/scripts/deploy.py
        --config /config/perimetercontrol-repo/deployment.yaml
        2>&1 | tee /config/perimetercontrol-repo/deploy.log

Usage from command line:
    python3 deploy.py --host 192.168.69.11 --user paul --ssh-key ~/y

Dependencies (standard library only — no pip packages required):
    Python 3.8+, ssh and scp binaries on PATH
"""

import argparse
import base64
import json
import os
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import List, Optional

try:
    import yaml
except ImportError:
    print(json.dumps({"step": "startup", "ok": False,
                      "detail": "PyYAML not installed. Run: python3 -m pip install pyyaml"}), flush=True)
    sys.exit(1)

import subprocess

# ── Configurable Constants ─────────────────────────────────────────────
PERIMETERCONTROL_SUPERVISOR_SERVICE = os.environ.get('PERIMETERCONTROL_SUPERVISOR_SERVICE', 'PerimeterControl-supervisor')
PERIMETERCONTROL_DASHBOARD_SERVICE = os.environ.get('PERIMETERCONTROL_DASHBOARD_SERVICE', 'PerimeterControl-dashboard')
PERIMETERCONTROL_OPT_PATH = os.environ.get('PERIMETERCONTROL_OPT_PATH', '/opt/PerimeterControl')
PERIMETERCONTROL_TMP_PATH = os.environ.get('PERIMETERCONTROL_TMP_PATH', '/tmp')

# ── Repo layout (relative to repo root) ─────────────────────────────────────
WEB_FILES = [
    ("server/web/dashboard.py",   f"{PERIMETERCONTROL_TMP_PATH}/dashboard.py",   "web", "0644"),
    ("server/web/layouts.py",     f"{PERIMETERCONTROL_TMP_PATH}/layouts.py",     "web", "0644"),
    ("server/web/callbacks.py",   f"{PERIMETERCONTROL_TMP_PATH}/callbacks.py",   "web", "0644"),
    ("server/web/data_sources.py",f"{PERIMETERCONTROL_TMP_PATH}/data_sources.py","web", "0644"),
]

SCRIPT_FILES = [
    ("scripts/ble-scanner-v2.py",      f"{PERIMETERCONTROL_TMP_PATH}/ble-scanner-v2.py",      "scripts", "0755"),
    ("scripts/ble-sniffer.py",         f"{PERIMETERCONTROL_TMP_PATH}/ble-sniffer.py",          "scripts", "0755"),
    ("scripts/ble-proxy-profiler.py",  f"{PERIMETERCONTROL_TMP_PATH}/ble-proxy-profiler.py",   "scripts", "0755"),
    ("scripts/ble-gatt-mirror.py",     f"{PERIMETERCONTROL_TMP_PATH}/ble-gatt-mirror.py",      "scripts", "0755"),
    ("scripts/apply-rules.py",         f"{PERIMETERCONTROL_TMP_PATH}/apply-rules.py",          "scripts", "0755"),
    ("scripts/network-topology.py",    f"{PERIMETERCONTROL_TMP_PATH}/network-topology.py",     "scripts", "0755"),
    ("scripts/topology_config.py",     f"{PERIMETERCONTROL_TMP_PATH}/topology_config.py",      "scripts", "0644"),
]

# ── Supervisor pip packages ───────────────────────────────────────────────────
SUPERVISOR_PIP = ["aiohttp", "psutil", "python-json-logger"]

# ── APT tag → package list mapping ───────────────────────────────────────────
# Matches the tags used in config/services/*.service.yaml  system_deps.apt[]
APT_TAG_PACKAGES: dict[str, list[str]] = {
    "gstreamer": [
        "gstreamer1.0-tools",
        "gstreamer1.0-plugins-base",
        "gstreamer1.0-plugins-good",
        "gstreamer1.0-plugins-bad",
        "gstreamer1.0-libav",
        "gstreamer1.0-alsa",
        "python3-gi",
        "python3-gi-cairo",
        "python3-gst-1.0",
        "gir1.2-gst-plugins-base-1.0",
    ],
    "i2c": [
        "i2c-tools",
        "python3-smbus2",
    ],
    "bluetooth": [
        "bluez",
        "python3-dbus",
    ],
}

# Script to symlink system PyGObject into the PerimeterControl venv (needed for GStreamer)
_PYGOBJECT_LINK = f"""\
GI_SRC=$(python3 -c \"import gi,os; print(os.path.dirname(gi.__file__))\" 2>/dev/null)
VENV_SITE=$(sudo {PERIMETERCONTROL_OPT_PATH}/venv/bin/python3 -c \"import site; print(site.getsitepackages()[0])\")
[ -n \"$GI_SRC\" ] && [ ! -e \"$VENV_SITE/gi\" ] && sudo ln -sf \"$GI_SRC\" \"$VENV_SITE/gi\"
echo GI_LINK_OK
"""


# ── Logging ───────────────────────────────────────────────────────────────────
def _log(step: str, ok: bool, detail: str = "") -> None:
    msg: dict = {"step": step, "ok": ok}
    if detail:
        msg["detail"] = detail
    print(json.dumps(msg), flush=True)


def _abort(step: str, detail: str = "") -> None:
    _log(step, False, detail)
    sys.exit(1)


# ── SSH / SCP helpers ─────────────────────────────────────────────────────────
def _ssh(host: str, user: str, key: str, cmd: str) -> tuple[int, str, str]:
    result = subprocess.run(
        [
            "ssh",
            "-i", key,
            "-o", "StrictHostKeyChecking=no",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=15",
            f"{user}@{host}",
            cmd,
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def _scp(host: str, user: str, key: str, local: str, remote: str) -> tuple[int, str, str]:
    result = subprocess.run(
        [
            "scp",
            "-i", key,
            "-o", "StrictHostKeyChecking=no",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=15",
            local,
            f"{user}@{host}:{remote}",
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


# ── Service descriptor parsing ────────────────────────────────────────────────
def _load_descriptors(services_dir: Path, svc_filter: Optional[List[str]]) -> list[dict]:
    """Load *.service.yaml files; filter to svc_filter if provided."""
    descriptors = []
    if not services_dir.is_dir():
        return descriptors
    for sf in sorted(services_dir.glob("*.service.yaml")):
        try:
            with open(sf) as fh:
                d = yaml.safe_load(fh)
            if not isinstance(d, dict):
                continue
            svc_id = d.get("metadata", {}).get("id") or sf.stem.replace(".service", "")
            if svc_filter is None or svc_id in svc_filter:
                descriptors.append(d)
        except yaml.YAMLError:
            pass
    return descriptors


def _collect_apt_tags(descriptors: list[dict]) -> set[str]:
    tags: set[str] = set()
    for d in descriptors:
        apt_deps = d.get("spec", {}).get("system_deps", {}).get("apt", []) or []
        for dep in apt_deps:
            tag = str(dep).split("#")[0].strip()
            if tag:
                tags.add(tag)
    return tags


def _resolve_apt_packages(tags: set[str]) -> list[str]:
    pkgs: set[str] = set()
    for tag in tags:
        pkgs.update(APT_TAG_PACKAGES.get(tag, [tag]))
    return sorted(pkgs)


# ── Supervisor pack ────────────────────────────────────────────────────────────
def _pack_supervisor(supervisor_dir: Path) -> str:
    tmp = tempfile.NamedTemporaryFile(
        suffix=".tar.gz", prefix="isolator-supervisor-", delete=False
    )
    tmp.close()
    with tarfile.open(tmp.name, "w:gz") as tar:
        tar.add(str(supervisor_dir), arcname="supervisor")
    return tmp.name


# ── Main deploy logic ─────────────────────────────────────────────────────────
def deploy(
    host: str,
    user: str,
    ssh_key: str,
    repo_root: Path,
    *,
    supervisor_port: int = 8080,
    svc_filter: Optional[List[str]] = None,
    no_restart: bool = False,
    skip_supervisor: bool = False,
    sync_config: bool = False,
) -> None:

    _log("deploy", True, f"Starting deploy to {user}@{host} (services: {svc_filter or 'all'})")

    # ── 1. Verify local files ────────────────────────────────────────────
    missing = [
        str(repo_root / rel)
        for rel, *_ in WEB_FILES
        if not (repo_root / rel).exists()
    ]
    if missing:
        _abort("local file check", f"Missing: {', '.join(missing)}")
    _log("local file check", True)

    # ── 2. Read service descriptors → determine apt deps ─────────────────
    services_dir = repo_root / "config" / "services"
    descriptors = _load_descriptors(services_dir, svc_filter)
    apt_tags = _collect_apt_tags(descriptors)
    apt_packages = _resolve_apt_packages(apt_tags)
    need_gstreamer = "gstreamer" in apt_tags
    _log(
        "service descriptors",
        True,
        f"{len(descriptors)} loaded; apt tags: {sorted(apt_tags) or 'none'}"
    )

    # ── 3. SSH connection test ───────────────────────────────────────────
    rc, out, err = _ssh(host, user, ssh_key, "echo CONN_OK")
    if rc != 0 or "CONN_OK" not in out:
        _abort("ssh connection", err.strip() or f"exit {rc}")
    _log("ssh connection", True, f"{user}@{host}")

    # ── 4. Preflight: check Python interpreter ───────────────────────────
    rc, out, _ = _ssh(
        host, user, ssh_key,
        f"py=$(systemctl status {PERIMETERCONTROL_DASHBOARD_SERVICE} --no-pager 2>/dev/null"
        f" | grep -oE '{PERIMETERCONTROL_OPT_PATH}/[^ ]*python3' | head -n 1);"
        " if [ -z \"$py\" ]; then echo PY_NOT_FOUND; elif [ -x \"$py\" ]; then echo PY_OK:$py;"
        " else echo PY_NOT_EXEC:$py; fi",
    )
    _log("preflight: python", True, out.strip() or "(fresh install — OK)")

    # ── 5. Resolve active deploy directory ───────────────────────────────
    rc, out, _ = _ssh(
        host, user, ssh_key,
        f"d=$(systemctl status {PERIMETERCONTROL_DASHBOARD_SERVICE} --no-pager 2>/dev/null"
        f" | grep -oE '{PERIMETERCONTROL_OPT_PATH}/[^ ]*dashboard\\.py' | head -n 1);"
        f" if [ -n \"$d\" ]; then dirname \"$d\"; else echo {PERIMETERCONTROL_OPT_PATH}/web; fi",
    )
    active_dir = out.strip()
    if not active_dir.startswith(f"{PERIMETERCONTROL_OPT_PATH}/"):
        active_dir = f"{PERIMETERCONTROL_OPT_PATH}/web"
    _log("resolve active dir", True, active_dir)

    # ── 6. Create remote backup ──────────────────────────────────────────
    backup_tag = time.strftime("%Y%m%d_%H%M%S")
    backup_dir = f"/tmp/network-isolator-dashboard-backup-{backup_tag}"
    web_names = " ".join(Path(r).name for r, *_ in WEB_FILES)
    script_names = " ".join(Path(r).name for r, *_ in SCRIPT_FILES)
    backup_cmd = (
        f"sudo mkdir -p {backup_dir}; "
        f"for f in {web_names}; do"
        f"  [ -f {active_dir}/$f ] && sudo cp -a {active_dir}/$f {backup_dir}/$f 2>/dev/null || true; "
        f"done; "
        f"for f in {script_names}; do"
        f"  [ -f /opt/network-isolator/scripts/$f ] && sudo cp -a /opt/network-isolator/scripts/$f {backup_dir}/$f 2>/dev/null || true; "
        f"done"
    )
    rc, _, err = _ssh(host, user, ssh_key, backup_cmd)
    _log("backup", rc == 0, f"{backup_dir}" if rc == 0 else err.strip())

    # ── 7. Upload files ───────────────────────────────────────────────────
    all_files = WEB_FILES + SCRIPT_FILES
    upload_errors = []
    for rel, tmp_path, _dest, _mode in all_files:
        local_f = repo_root / rel
        if not local_f.exists():
            continue
        rc, _, err = _scp(host, user, ssh_key, str(local_f), tmp_path)
        if rc != 0:
            upload_errors.append(f"{local_f.name}: {err.strip()}")
    if upload_errors:
        _abort("upload files", "; ".join(upload_errors))
    _log("upload files", True, f"{len(all_files)} files")

    # ── 8. Install files via sudo install (sets permissions atomically) ──
    rc, _, _ = _ssh(
        host, user, ssh_key,
        f"sudo mkdir -p {active_dir} /opt/network-isolator/scripts"
    )
    install_cmds = []
    for rel, tmp_path, dest, mode in all_files:
        local_f = repo_root / rel
        if not local_f.exists():
            continue
        remote_dest = (
            f"{active_dir}/{local_f.name}" if dest == "web"
            else f"/opt/network-isolator/scripts/{local_f.name}"
        )
        install_cmds.append(
            f"sudo install -o root -g root -m {mode} {tmp_path} {remote_dest}"
        )
    rc, _, err = _ssh(host, user, ssh_key, "set -e; " + "; ".join(install_cmds))
    if rc != 0:
        _abort("install files", err.strip())
    _log("install files", True)

    # ── 9. Sync config (optional) ────────────────────────────────────────
    if sync_config:
        conf_src = repo_root / "config" / "network-isolator.conf.yaml"
        if conf_src.exists():
            rc, _, err = _scp(host, user, ssh_key, str(conf_src), "/tmp/network-isolator.conf.yaml")
            if rc == 0:
                rc, _, err = _ssh(
                    host, user, ssh_key,
                    "set -e; sudo mkdir -p /mnt/network-isolator/conf; "
                    "sudo install -o root -g root -m 0644 /tmp/network-isolator.conf.yaml "
                    "/mnt/network-isolator/conf/network-isolator.conf.yaml",
                )
            _log("sync config", rc == 0, err.strip() if rc != 0 else "")
        else:
            _log("sync config", False, f"Not found: {conf_src}")

    # ── 10. Restart dashboard (with rollback on failure) ─────────────────
    if not no_restart:
        _ssh(host, user, ssh_key, "sudo systemctl restart network-isolator-dashboard")
        time.sleep(2)
        rc, _, _ = _ssh(host, user, ssh_key, "sudo systemctl is-active network-isolator-dashboard")
        if rc != 0:
            _log("restart dashboard", False, "Service unhealthy — rolling back")
            # Build rollback using backup copies
            rollback_parts = []
            for rel, _, dest, mode in all_files:
                fname = Path(rel).name
                bk = f"{backup_dir}/{fname}"
                target = (
                    f"{active_dir}/{fname}" if dest == "web"
                    else f"/opt/network-isolator/scripts/{fname}"
                )
                rollback_parts.append(
                    f"[ -f {bk} ] && sudo install -o root -g root -m {mode} {bk} {target} || true"
                )
            rollback_cmd = "; ".join(rollback_parts) + "; sudo systemctl restart network-isolator-dashboard"
            _ssh(host, user, ssh_key, rollback_cmd)
            _log("rollback dashboard", True)
            sys.exit(1)
        _log("restart dashboard", True)
    else:
        _log("restart dashboard", True, "skipped (--no-restart)")

    # ── 11. Phase 2: Supervisor package ──────────────────────────────────
    if skip_supervisor:
        _log("supervisor phase", True, "skipped (--skip-supervisor)")
        _log("deploy complete", True, f"Dashboard live at {active_dir}")
        return

    supervisor_dir = repo_root / "supervisor"
    supervisor_svc = repo_root / "server" / "network-isolator-supervisor.service"

    if not supervisor_dir.is_dir():
        _log("supervisor phase", True, "supervisor/ not found locally — skipping")
        _log("deploy complete", True)
        return

    if not supervisor_svc.exists():
        _abort("supervisor phase", f"Missing service file: {supervisor_svc}")

    # Pack and upload
    tar_tmp = _pack_supervisor(supervisor_dir)
    try:
        rc, _, err = _scp(host, user, ssh_key, tar_tmp, "/tmp/supervisor.tar.gz")
        if rc != 0:
            _abort("upload supervisor.tar.gz", err.strip())
        _log("upload supervisor.tar.gz", True)

        rc, _, err = _scp(host, user, ssh_key, str(supervisor_svc), "/tmp/network-isolator-supervisor.service")
        if rc != 0:
            _abort("upload supervisor.service", err.strip())
        _log("upload supervisor.service", True)

        # Backup existing supervisor
           _ssh(host, user, ssh_key,
               "sudo cp -a /opt/network-isolator/supervisor /tmp/network-isolator-supervisor-backup 2>/dev/null; true")

        # Extract with sudo + --no-same-permissions so tar sets permissions respecting umask.
        # This avoids the 'chmod: Operation not permitted' bug from the PowerShell script
        # where a post-extraction find+chmod ran without sudo elevation on the chmod subprocess.
        sup_extract = (
            "set -e; "
            "cd /tmp && rm -rf /tmp/supervisor && "
            "sudo tar -xzf /tmp/supervisor.tar.gz "
            "  --no-same-owner --no-same-permissions --mode='u=rw,go=r,a+X' && "
            "sudo mkdir -p /opt/network-isolator/supervisor && "
            "sudo cp -a /tmp/supervisor/. /opt/network-isolator/supervisor/ && "
            "sudo chown -R root:root /opt/network-isolator/supervisor && "
            "echo SUPERVISOR_INSTALLED"
        )
        rc, out, err = _ssh(host, user, ssh_key, sup_extract)
        if rc != 0 or "SUPERVISOR_INSTALLED" not in out:
            _abort("install supervisor", err.strip() or out.strip())
        _log("install supervisor", True)

        # Install systemd service unit
        rc, out, err = _ssh(
            host, user, ssh_key,
            "set -e; "
            "sudo install -o root -g root -m 0644 /tmp/network-isolator-supervisor.service "
            "  /etc/systemd/system/network-isolator-supervisor.service && "
            "sudo systemctl daemon-reload && "
            "sudo systemctl enable network-isolator-supervisor.service && "
            "echo SERVICE_UNIT_OK",
        )
        _log("install supervisor.service", rc == 0 and "SERVICE_UNIT_OK" in out,
             err.strip() if rc != 0 else "")

        # Pip install into venv
        pkgs = " ".join(SUPERVISOR_PIP)
        rc, out, err = _ssh(
            host, user, ssh_key,
            f"set -e; sudo /opt/network-isolator/venv/bin/pip install --quiet {pkgs} && echo PIP_OK",
        )
        _log("pip install supervisor deps", rc == 0 and "PIP_OK" in out,
             err.strip() if rc != 0 else "")

        # Apt install — only packages required by configured service descriptors
        if apt_packages:
            _log("apt packages needed", True, " ".join(apt_packages))
            apt_list = " ".join(apt_packages)
            rc, out, err = _ssh(
                host, user, ssh_key,
                f"DEBIAN_FRONTEND=noninteractive sudo apt-get install -y -qq {apt_list} "
                f"2>/dev/null && echo APT_OK",
            )
            _log("apt install", rc == 0 and "APT_OK" in out, err.strip() if rc != 0 else "")

            if need_gstreamer and (rc == 0 or "APT_OK" in out):
                gi_b64 = base64.b64encode(_PYGOBJECT_LINK.encode()).decode()
                rc2, out2, _ = _ssh(
                    host, user, ssh_key,
                    f"echo '{gi_b64}' | base64 -d | bash",
                )
                gi_ok = rc2 == 0 or "GI_LINK_OK" in out2
                _log("link PyGObject into venv", gi_ok,
                     "already linked or venv uses system-site-packages" if not gi_ok else "")
        else:
            _log("apt install", True, "no service requires extra apt packages")

        # Ensure runtime directories exist
        rc, _, err = _ssh(
            host, user, ssh_key,
            "sudo mkdir -p /opt/network-isolator/state /var/log/network-isolator /mnt/network-isolator/conf && echo DIRS_OK",
        )
        _log("runtime directories", rc == 0, err.strip() if rc != 0 else "")

        # Deploy service descriptors to /mnt/isolator/conf/services/
        if services_dir.is_dir():
            svc_yamls = sorted(services_dir.glob("*.service.yaml"))
            if svc_filter:
                svc_yamls = [
                    f for f in svc_yamls
                    if f.stem.replace(".service", "") in svc_filter
                ]
            if svc_yamls:
                _ssh(host, user, ssh_key, "sudo mkdir -p /mnt/network-isolator/conf/services")
                deployed = 0
                for sf in svc_yamls:
                    rc, _, err = _scp(host, user, ssh_key, str(sf), f"/tmp/{sf.name}")
                    if rc == 0:
                        rc, _, err = _ssh(
                            host, user, ssh_key,
                            f"sudo install -o root -g root -m 0644 /tmp/{sf.name} "
                            f"/mnt/network-isolator/conf/services/{sf.name}",
                        )
                    if rc == 0:
                        deployed += 1
                    else:
                        _log(f"deploy {sf.name}", False, err.strip())
                _log("service descriptors deployed", True, f"{deployed}/{len(svc_yamls)} files")

                # Validate descriptors on Pi
                rc, out, _ = _ssh(
                    host, user, ssh_key,
                    "sudo /opt/network-isolator/venv/bin/python3 "
                    "/opt/network-isolator/supervisor/resources/validate-service-descriptors.py "
                    "--dir /mnt/network-isolator/conf/services 2>/dev/null; echo VALIDATE_DONE",
                )
                _log("validate descriptors", "VALIDATE_DONE" in out,
                     out.strip() if "VALIDATE_DONE" not in out else "")

        # Restart supervisor
        if not no_restart:
            _ssh(host, user, ssh_key, "sudo systemctl restart network-isolator-supervisor")
            time.sleep(3)
            rc, _, _ = _ssh(host, user, ssh_key, "sudo systemctl is-active network-isolator-supervisor")
            _log("restart supervisor", rc == 0)
        else:
            _log("restart supervisor", True, "skipped (--no-restart)")

    finally:
        Path(tar_tmp).unlink(missing_ok=True)

    _log("deploy complete", True,
         f"Dashboard: {active_dir}, Supervisor port: {supervisor_port}")


# ── CLI entry point ───────────────────────────────────────────────────────────
def main() -> None:
    p = argparse.ArgumentParser(
        description="Network Isolator deploy script — cross-platform replacement for deploy-dashboard-web.ps1"
    )
    p.add_argument("--config", metavar="FILE",
                   help="YAML deployment config file (all flags below can also live here)")
    p.add_argument("--host", metavar="IP",
                   help="Pi hostname or IP address")
    p.add_argument("--user", metavar="USER", default="",
                   help="SSH user (default: paul)")
    p.add_argument("--ssh-key", metavar="FILE",
                   help="Path to SSH private key")
    p.add_argument("--supervisor-port", metavar="PORT", type=int,
                   help="Supervisor API port (default: 8080)")
    p.add_argument("--services", metavar="S1,S2",
                   help="Comma-separated service IDs to include (default: all descriptors)")
    p.add_argument("--repo-dir", metavar="DIR",
                   help="Repo root directory (default: three levels above this script)")
    p.add_argument("--no-restart", action="store_true",
                   help="Skip service restarts after deploying")
    p.add_argument("--skip-supervisor", action="store_true",
                   help="Skip Phase 2 supervisor package deploy")
    p.add_argument("--sync-config", action="store_true",
                   help="Push config/network-isolator.conf.yaml to Pi runtime path")
    args = p.parse_args()

    # Load YAML config file if provided
    file_cfg: dict = {}
    if args.config:
        try:
            with open(args.config) as fh:
                file_cfg = yaml.safe_load(fh) or {}
        except FileNotFoundError:
            _abort("load config", f"Config file not found: {args.config}")
        except yaml.YAMLError as e:
            _abort("load config", str(e))

    # CLI args take precedence over config file
    host = args.host or file_cfg.get("host") or ""
    user = args.user or file_cfg.get("user") or "paul"
    ssh_key = args.ssh_key or file_cfg.get("ssh_key") or file_cfg.get("ssh_key_path") or ""
    supervisor_port = args.supervisor_port or file_cfg.get("supervisor_port") or 8080
    no_restart = args.no_restart or bool(file_cfg.get("no_restart"))
    skip_supervisor = args.skip_supervisor or bool(file_cfg.get("skip_supervisor"))
    sync_config = args.sync_config or bool(file_cfg.get("sync_config"))

    svc_filter: Optional[List[str]] = None
    if args.services:
        svc_filter = [s.strip() for s in args.services.split(",") if s.strip()]
    elif file_cfg.get("services"):
        svc_filter = list(file_cfg["services"])

    if not host:
        _abort("config check", "--host is required (or set 'host:' in config file)")
    if not ssh_key:
        _abort("config check", "--ssh-key is required (or set 'ssh_key:' in config file)")
    if not os.path.exists(ssh_key):
        _abort("config check", f"SSH key file not found: {ssh_key}")

    # Resolve repo root: script lives at <repo>/ha-integration/scripts/deploy.py
    if args.repo_dir:
        repo_root = Path(args.repo_dir).resolve()
    elif file_cfg.get("repo_dir"):
        repo_root = Path(str(file_cfg["repo_dir"])).resolve()
    else:
        repo_root = Path(__file__).resolve().parent.parent.parent

    _log("config", True,
         f"repo={repo_root}  host={user}@{host}  services={svc_filter or 'all'}")

    deploy(
        host=host,
        user=user,
        ssh_key=ssh_key,
        repo_root=repo_root,
        supervisor_port=supervisor_port,
        svc_filter=svc_filter,
        no_restart=no_restart,
        skip_supervisor=skip_supervisor,
        sync_config=sync_config,
    )


if __name__ == "__main__":
    main()
