from logging import Logger

from elena.domain.model.bot_config import BotConfig
from elena.domain.model.bot_status import BotStatus
from elena.domain.ports.bot import Bot
from elena.domain.ports.strategy_manager import StrategyManager


class TrailingStopLossBBbuyAfterSleep(Bot):
    # Trailing Stop Loss and Buy always with a sleep

    _manager: StrategyManager
    _logger: Logger
    _name: str

    bb_length: int
    bb_mult: float

    sleep_by: int

    reinvest: float
    stop_loose_changes: int
    cash: float

    def init(self, manager: StrategyManager, logger: Logger):
        self._manager = manager
        self._logger = logger
        self._name = self.__class__.__name__

        # get them from StrategyManager
        self.bb_length = 5
        self.bb_mult = 2

        self.sleep_by = 0

        self.reinvest = 0
        self.stop_loose_changes = 0
        self.cash = 1000
        logger.info("Hello!")

    def next(self, status: BotStatus, bot_config: BotConfig) -> BotStatus:
        self._logger.info('%s strategy: processing next cycle ...', self._name)
        return status


