"""
Isolator Supervisor — entry point.

Usage
-----
    python -m supervisor [options]

Options
-------
    --config   PATH   Config directory          (default: /opt/isolator/config)
    --state    PATH   State directory           (default: /opt/isolator/state)
    --port     INT    REST API listener port    (default: 8080)
    --log-level STR   Logging level             (default: INFO)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

import tornado.ioloop

from .api.handlers import make_app
from .resources.scheduler import NodeBudget
from .supervisor import Supervisor

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=LOG_FORMAT,
        stream=sys.stdout,
    )


def _register_capabilities(supervisor: Supervisor) -> None:
    """Import and register all available capability module classes."""
    try:
        from .capabilities.network_isolation import NetworkIsolationCapability
        supervisor.register_capability("network_isolation", NetworkIsolationCapability)
    except ImportError as exc:
        logging.warning("Could not load network_isolation module: %s", exc)

    try:
        from .capabilities.ble_gatt_repeater import BleGattRepeaterCapability
        supervisor.register_capability("ble_gatt_repeater", BleGattRepeaterCapability)
    except ImportError as exc:
        logging.warning("Could not load ble_gatt_repeater module: %s", exc)
        
    try:
        from .capabilities.photo_booth import PhotoBoothCapability
        supervisor.register_capability("photo_booth", PhotoBoothCapability)
    except ImportError as exc:
        logging.warning("Could not load photo_booth module: %s", exc)

    try:
        from .capabilities.wildlife_monitor import WildlifeMonitorCapability
        supervisor.register_capability("wildlife_monitor", WildlifeMonitorCapability)
    except ImportError as exc:
        logging.warning("Could not load wildlife_monitor module: %s", exc)

    # Future capabilities registered here:
    #   from .capabilities.pawr_esl_advertiser import PawrEslAdvertiserCapability
    #   supervisor.register_capability("pawr_esl_advertiser", PawrEslAdvertiserCapability)


async def _run(args: argparse.Namespace) -> None:
    logger = logging.getLogger(__name__)

    Path(args.config).mkdir(parents=True, exist_ok=True)
    Path(args.state).mkdir(parents=True, exist_ok=True)

    budget = NodeBudget(
        cpu_cores=float(args.cpu_cores),
        memory_mb=int(args.memory_mb),
        disk_mb=int(args.disk_mb),
    )

    supervisor = Supervisor(
        config_dir=args.config,
        state_dir=args.state,
        budget=budget,
    )

    _register_capabilities(supervisor)
    await supervisor.start()

    app = make_app(supervisor)
    app.listen(args.port)
    logger.info("Isolator Supervisor listening on port %d", args.port)

    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _handle_signal(signum, _frame):
        logger.info("Received signal %d — shutting down …", signum)
        loop.call_soon_threadsafe(shutdown_event.set)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    await shutdown_event.wait()

    logger.info("Shutdown requested")
    await supervisor.stop()
    tornado.ioloop.IOLoop.current().stop()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Isolator Supervisor",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config",     default="/opt/isolator/config", help="Config directory")
    parser.add_argument("--state",      default="/opt/isolator/state",  help="State directory")
    parser.add_argument("--port",       type=int, default=8080,         help="REST API port")
    parser.add_argument("--log-level",  default="INFO",                 help="Logging level")
    parser.add_argument("--cpu-cores",  type=float, default=4.0,        help="Node CPU budget (cores)")
    parser.add_argument("--memory-mb",  type=int,   default=6000,       help="Node memory budget (MB)")
    parser.add_argument("--disk-mb",    type=int,   default=50000,      help="Node disk budget (MB)")
    args = parser.parse_args()

    _setup_logging(args.log_level)
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
