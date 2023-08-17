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

    @staticmethod
    def _percentage_to_float(percentage):
        percentage = percentage[:-1]  # Remove the percentage symbol
        try:
            float_value = float(percentage) / 100
            return float_value
        except ValueError:
            raise ValueError("Invalid asset_to_manage format, use: 25% or 20.33% for percentages"
                             "or 25 or 3.33 for exact asset quantities.")

    def _get_max_asset_to_manage(self, balance_total: float):
        if self.asset_to_manage.endswith('%'):
            percentage_as_float = self._percentage_to_float(self.asset_to_manage)
            return balance_total * percentage_as_float
        else:
            try:
                float_value = float(self.asset_to_manage)
                return float_value
            except ValueError:
                raise ValueError("Invalid asset_to_manage format, use: 25% or 20.33% for percentages "
                                 "or 25 or 3.33 for exact asset quantities.")

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

        total_managed_asset = 0  # sum open orders amounts

        # is there any free balance to handle?
        balance = self._manager.get_balance(self._exchange)
        base_symbol = self._bot_config.pair.base
        total = balance.currencies[base_symbol].total
        free = balance.currencies[base_symbol].free
        total_to_manage = self._get_max_asset_to_manage(total)
        new_order_size = total_to_manage - total_managed_asset
        if free < new_order_size:
            new_order_size = free

        # calculate the new stop loss
        candles = self._manager.read_candles(self._exchange, self._bot_config.pair, TimeFrame.hour_1)

        # Indicator: Bollinger Bands (BBANDS)
        bbands = ta.bbands(close=candles.Close, length=self.bb_length, std=self.bb_mult)
        bbands_lower_band = bbands[bbands.columns[0]]
        # bbands_upper_band = bbands[bbands.columns[2]]

        new_stop_loss = float(bbands_lower_band[-1:].iloc[0])  # get the last

        # update old orders
        for order in status.orders:
            # verify current stop loss if higher than new_stop_loss if not, update/cancel orders
            # if we cancel orders we should add that balances to new_order_size ?
            # how do we manage trades? to calculate profit
            # also new orders should start at initial_sl_factor
            pass

        if new_order_size > 0:
            new_order = self._manager.stop_loss_market(self._exchange, bot_config=self._bot_config,
                                                       amount=new_order_size, stop_price=new_stop_loss)
            status.orders.append(new_order)
            # trades add

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
