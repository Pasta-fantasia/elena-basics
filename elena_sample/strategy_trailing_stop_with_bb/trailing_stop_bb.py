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

        '''
            Check model at https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html#header-classes
            asset=(in BTCBUSD, is BTC)
            
            for order in orders:
                check status
                if status==close:
                    update .trades and move the record to closed_trades 
                    notify("SL execute, check your positions")
                    remove it from orders and trades
                else:
                    sum the remaning assets balance (orders can may be "partial")
                
            check asset balance 
            calculare max balance to handle 
            calculate new SL
            
            for order in orders:
                if new SL>order.SL
                    cancel order
                    create a new order with "new SL"
                    
            if "max balance to handle">"sum the remaning assets balance":
                new order size is ("max balance to handle" - "sum the remaning assets balance")
                create a new order with "new SL" for "new order size"
                notify("found more balance and handling it")
            
            
        '''
        return status


