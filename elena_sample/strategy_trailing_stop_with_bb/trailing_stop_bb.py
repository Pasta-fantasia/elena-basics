from logging import Logger

from elena.domain.model.bot_config import BotConfig
from elena.domain.model.bot_status import BotStatus
from elena.domain.ports.bot import Bot
from elena.domain.ports.strategy_manager import StrategyManager
from elena.domain.model.exchange import Exchange
from elena.domain.model.time_frame import TimeFrame
from elena.domain.model.trading_pair import TradingPair
from elena.domain.model.trade import Trade
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
        for order in status.active_orders:
            total_managed_asset += order.amount

        # is there any free balance to handle?
        balance = self._manager.get_balance(self._exchange)
        base_symbol = self._bot_config.pair.base
        total = balance.currencies[base_symbol].total
        free = balance.currencies[base_symbol].free
        total_to_manage = self._get_max_asset_to_manage(total)
        new_order_size = round(total_to_manage - total_managed_asset, 8)

        # TODO: new_order_size <- round to asset precision Read: https://docs.ccxt.com/#/README?id=currency-structure
        #       market = exchange.market(symbol)
        if free < new_order_size:
            new_order_size = free

        # calculate the new stop loss
        candles = self._manager.read_candles(self._exchange, self._bot_config.pair, TimeFrame.hour_1)

        # Indicator: Bollinger Bands (BBANDS)
        bbands = ta.bbands(close=candles.Close, length=self.bb_length, std=self.bb_mult)
        bbands_lower_band = bbands[bbands.columns[0]]
        # bbands_upper_band = bbands[bbands.columns[2]]

        new_stop_loss = float(bbands_lower_band[-1:].iloc[0])  # get the last
        price = float(bbands_lower_band[-2:-1].iloc[0])
        if price > new_stop_loss:
            price = new_stop_loss * 0.98  # fix price -2% of new_stop_loss
        last_close = candles[-1:]['Close'].iloc[0]  # get the last close as entry price for trade
        new_stop_loss_initial_sl_factor = last_close * self.initial_sl_factor

        # update active orders
        for order in status.active_orders:
            # verify current stop loss if higher than new_stop_loss if not, cancel/create orders
            # new orders should start at new_stop_loss_initial_sl_factor (if initial_sl_factor !=0)
            # and moved with it until new_stop_loss > trade.entry_price
            new_stop_loss_for_this_order = new_stop_loss
            price_for_this_order = price
            if order.stop_price < new_stop_loss_for_this_order:
                cancelled_order = new_order = self._manager.cancel_order(self._exchange, bot_config=self._bot_config,
                                                                         order_id=order.id)
                new_order = self._manager.stop_loss_limit(self._exchange, bot_config=self._bot_config,
                                                          amount=order.amount, stop_price=new_stop_loss_for_this_order,
                                                          price=price_for_this_order)
                status.active_orders.append(new_order)
                status.archived_orders.remove(order)
                status.archived_orders.append(cancelled_order)
                # trades update

        if new_order_size > 0:
            # check if entry_price is < new_stop_loss
            # for each trade with exit_order_id == 'detected new balance to manage'
            if True:
                new_order = self._manager.stop_loss_limit(self._exchange, bot_config=self._bot_config,
                                                          amount=new_order_size, stop_price=new_stop_loss, price=price)
                status.active_orders.append(new_order)
                exit_order_id = new_order.id
            else:
                exit_order_id = 'detected new balance to manage'

            # trades add
            new_trade = Trade(exchange_id=self._bot_config.exchange_id, bot_id=self._bot_config.id,
                              strategy_id=self._bot_config.strategy_id, pair=self._bot_config.pair,
                              size=new_order_size,
                              entry_order_id='manual', entry_price=last_close,
                              exit_order_id=exit_order_id, exit_price=new_stop_loss,
                              )
            status.active_trades.append(new_trade)

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
