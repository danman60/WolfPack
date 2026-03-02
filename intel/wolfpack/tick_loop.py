"""Tick loop orchestrator — runs intelligence cycles on a 5-minute cadence.

Usage:
    python -m wolfpack.tick_loop [--interval 300] [--exchange hyperliquid] [--symbols BTC,ETH]
"""

import argparse
import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("wolfpack.tick_loop")


class TickLoop:
    """Runs the full intelligence pipeline on a fixed cadence."""

    def __init__(
        self,
        interval_seconds: int = 300,
        exchange: str = "hyperliquid",
        symbols: list[str] | None = None,
    ):
        self.interval = interval_seconds
        self.exchange = exchange
        self.symbols = symbols or ["BTC"]
        self._running = False
        self._cycle_count = 0

    async def start(self) -> None:
        """Start the tick loop. Runs until stopped."""
        self._running = True
        logger.info(
            f"Tick loop starting: interval={self.interval}s, "
            f"exchange={self.exchange}, symbols={self.symbols}"
        )

        while self._running:
            cycle_start = datetime.now(timezone.utc)
            self._cycle_count += 1

            logger.info(f"=== Cycle #{self._cycle_count} started at {cycle_start.isoformat()} ===")

            for symbol in self.symbols:
                if not self._running:
                    break
                try:
                    await self._run_cycle(symbol)
                except Exception as e:
                    logger.error(f"Cycle #{self._cycle_count} failed for {symbol}: {e}", exc_info=True)

            elapsed = (datetime.now(timezone.utc) - cycle_start).total_seconds()
            sleep_time = max(0, self.interval - elapsed)

            logger.info(
                f"=== Cycle #{self._cycle_count} finished in {elapsed:.1f}s, "
                f"sleeping {sleep_time:.1f}s ==="
            )

            if sleep_time > 0 and self._running:
                await asyncio.sleep(sleep_time)

    def stop(self) -> None:
        """Signal the loop to stop after the current cycle."""
        logger.info("Tick loop stopping...")
        self._running = False

    async def _run_cycle(self, symbol: str) -> None:
        """Run one full intelligence cycle for a symbol."""
        # Import here to avoid circular imports and allow lazy init
        from wolfpack.api import _run_full_cycle

        logger.info(f"Running intelligence cycle for {symbol} on {self.exchange}...")
        await _run_full_cycle(self.exchange, symbol)
        logger.info(f"Intelligence cycle complete for {symbol}")


def main() -> None:
    parser = argparse.ArgumentParser(description="WolfPack Tick Loop")
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Interval between cycles in seconds (default: 300)",
    )
    parser.add_argument(
        "--exchange",
        type=str,
        default="hyperliquid",
        help="Exchange to use (default: hyperliquid)",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default="BTC",
        help="Comma-separated list of symbols (default: BTC)",
    )
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",")]
    loop = TickLoop(
        interval_seconds=args.interval,
        exchange=args.exchange,
        symbols=symbols,
    )

    # Handle graceful shutdown
    def shutdown_handler(sig: int, frame: object) -> None:
        loop.stop()

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        asyncio.run(loop.start())
    except KeyboardInterrupt:
        logger.info("Tick loop interrupted")
        sys.exit(0)


if __name__ == "__main__":
    main()
