"""
Isolator Supervisor — FastAPI-based entry point.

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

import uvicorn
from fastapi import FastAPI

from .api.fastapi_handlers import create_supervisor_api
from .resources.scheduler import NodeBudget
from .supervisor import Supervisor

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"

# Global supervisor instance for dependency injection
app_supervisor = None


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
        from .capabilities.esl_ap import EslApCapability
        supervisor.register_capability("esl_ap", EslApCapability)
    except ImportError as exc:
        logging.warning("Could not load esl_ap module: %s", exc)

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


async def _run(args) -> None:
    global app_supervisor
    
    logger = logging.getLogger(__name__)
    logger.info("Starting Isolator Supervisor with FastAPI")

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
    
    # Set global supervisor for dependency injection
    app_supervisor = supervisor

    _register_capabilities(supervisor)
    await supervisor.start()

    # Create FastAPI app
    app = create_supervisor_api()
    
    # Store supervisor in app state for access
    app.state.supervisor = supervisor

    logger.info("Isolator Supervisor starting on port %d with FastAPI", args.port)

    # Create uvicorn server configuration
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=args.port,
        log_level=args.log_level.lower(),
        loop="asyncio",
        lifespan="on"
    )
    
    server = uvicorn.Server(config)

    # Setup graceful shutdown
    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _handle_signal(signum, _frame):
        logger.info("Received signal %d — shutting down …", signum)
        loop.call_soon_threadsafe(shutdown_event.set)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    # Start server in background task
    server_task = asyncio.create_task(server.serve())
    
    # Wait for shutdown signal
    try:
        await shutdown_event.wait()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    
    logger.info("Shutdown requested")
    
    # Gracefully shutdown server
    server.should_exit = True
    await server_task
    
    # Stop supervisor
    await supervisor.stop()
    
    logger.info("Supervisor stopped")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Isolator Supervisor (FastAPI)",
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