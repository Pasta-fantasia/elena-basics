from logging import Logger

from elena.domain.model.bot_config import BotConfig
from elena.domain.model.bot_status import BotStatus
from elena.domain.ports.bot import Bot
from elena.domain.ports.strategy_manager import StrategyManager
from elena.domain.model.exchange import Exchange
from elena.domain.model.time_frame import TimeFrame
from elena.domain.model.trading_pair import TradingPair
import pandas_ta as ta


class TrailingStopLossBB(Bot):
    # Trailing Stop Loss using BB

    _manager: StrategyManager
    _logger: Logger
    _name: str
    _bot_config: BotConfig
    _exchange: Exchange

    bb_length: int
    bb_mult: float
    initial_sl_factor: float
    asset_to_manage: str

    stop_loose_changes: int

    def init(self, manager: StrategyManager, logger: Logger, bot_config: BotConfig):
        self._manager = manager
        self._logger = logger
        self._name = self.__class__.__name__
        self._bot_config = bot_config
        self._exchange = self._manager.get_exchange(self._bot_config.exchange_id)

        try:
            self.bb_length = bot_config.config['bb_length']
            self.bb_mult = bot_config.config['bb_mult']
            self.initial_sl_factor = bot_config.config['initial_sl_factor']
            self.asset_to_manage = bot_config.config['asset_to_manage']
            # TODO [Pere] Is there some magic trick to do it? We can keep BotConfig as is, but...
        except Exception as err:
            logger.error('Error initializing Bot config')
            logger.error(f"Unexpected {err=}, {type(err)=}")
            # TODO [Pere] Should we raise it? _get_bot_instance

    def next(self, status: BotStatus) -> BotStatus:
        self._logger.info('%s strategy: processing next cycle ...', self._name)

        balance = self._manager.get_balance(self._exchange)
        self._logger.info(balance)
        candles = self._manager.read_candles(self._exchange, self._bot_config.pair, TimeFrame.hour_1)
        bbands = ta.bbands(close=candles.Close, length=self.bb_length, std=self.bb_mult)

        lower_band = bbands[bbands.columns[0]]
        upper_band = bbands[bbands.columns[2]]

        new_stop = float(lower_band[-1:].iloc[0])

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
            
            notify_on_order_status_change can be a property ser on Strategy.init... not a bot parameter
            
        '''
        return status


