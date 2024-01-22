import pathlib
import time
from os import path

from elena.domain.model.bot_config import BotConfig
from elena.domain.model.bot_status import BotStatus, BotBudget
from elena.domain.ports.exchange_manager import ExchangeManager
from elena.domain.ports.logger import Logger
from elena.domain.ports.metrics_manager import MetricsManager
from elena.domain.ports.notifications_manager import NotificationsManager
from elena.domain.ports.strategy_manager import StrategyManager
from elena.domain.services.elena import get_elena_instance
from elena.domain.services.generic_bot import GenericBot

import pandas_ta as ta


class DCA_Conditional_Buy_LR_with_TrailingStop(GenericBot):
    # Strict dates DCA, just buy on a regular basis.

    spend_on_order: float
    lr_buy_longitude: float
    band_length: float
    band_mult: float
    minimal_benefit_to_start_trailing: float

    _logger: Logger
    _metrics_manager: MetricsManager
    _notifications_manager: NotificationsManager

    def _cancel_active_orders_with_lower_stop_loss(self, new_stop_loss: float) -> float:
        # Cancel any active stop order with a limit lower than the new one.
        # return the total amount of canceled orders
        total_amount_canceled_orders = 0
        canceled_orders = []
        for order in self.status.active_orders:
            if new_stop_loss > order.stop_price:
                cancelled_order = self.cancel_order(order.id)
                if cancelled_order:
                    total_amount_canceled_orders = total_amount_canceled_orders + order.amount
                    canceled_orders.append(order.id)
                else:
                    self._logger.error(f"Error canceling order: {order.id}.")
        return total_amount_canceled_orders, canceled_orders

    def init(self, manager: StrategyManager, logger: Logger, metrics_manager: MetricsManager, notifications_manager: NotificationsManager, exchange_manager: ExchangeManager, bot_config: BotConfig, bot_status: BotStatus, ):  # type: ignore
        super().init(manager, logger, metrics_manager, notifications_manager, exchange_manager, bot_config, bot_status,)
        self._logger = logger
        self._metrics_manager = metrics_manager
        self._notifications_manager = notifications_manager

        try:
            self.spend_on_order = bot_config.config['spend_on_order']
            self.lr_buy_longitude = bot_config.config['lr_buy_longitude']
            self.band_length = bot_config.config['band_length']
            self.band_mult = bot_config.config['band_mult']
            self.minimal_benefit_to_start_trailing = bot_config.config['minimal_benefit_to_start_trailing']
        except Exception as err:
            self._logger.error(f"Error initializing Bot config: {err}", error=err)

    def next(self) -> BotStatus:
        self._logger.info('%s strategy: processing next cycle ...', self.name)

        min_amount = self.limit_min_amount()

        min_cost = self.limit_min_cost()
        if not min_cost:
            self._logger.error("Cannot get min_cost")
            return

        estimated_close_price = self.get_estimated_last_close()
        if not estimated_close_price:
            self._logger.error("Cannot get_estimated_last_close")
            return

        balance = self.get_balance()
        if not balance:
            self._logger.error("Cannot get balance")
            return

        data_points = int(max(self.lr_buy_longitude,self.band_length) + 10)  # make sure we ask the enough data for the indicator
        data = self.read_candles(page_size=data_points)

        linreg = ta.linreg(close=data.Close, length=self.lr_buy_longitude, angle=True)
        angle = float(linreg[-1:].iloc[0])  # get the last
        self._metrics_manager.gauge("LR_angle", self.id, angle, ["indicator"])

        # BUY LOGIC
        error_on_buy = False
        if angle > 0:
            quote_symbol = self.pair.quote
            quote_free = balance.currencies[quote_symbol].free

            amount_to_spend = min(self.status.budget.free, self.spend_on_order, quote_free)
            amount_to_buy = amount_to_spend / estimated_close_price
            amount_to_buy = self.amount_to_precision(amount_to_buy)

            if amount_to_buy >= min_amount and amount_to_spend >= min_cost:
                market_buy_order = self.create_market_buy_order(amount_to_buy)
                if not market_buy_order:
                    self._logger.error("Buy order failed!")
                    error_on_buy = True
            else:
                msg = f"Not enough balance to buy min_amount/min_cost. {self.pair.base}, quote_free={quote_free}, min_amount={min_amount}, min_cost={min_cost}, amount_to_spend={amount_to_spend}, free-budget={self.status.budget.free}, estimated_close_price={estimated_close_price}"
                self._logger.warning(msg)
                self._notifications_manager.medium(msg)
                error_on_buy = True


        # TRAILING STOP LOGIC
        # Indicator: Standard Error Bands based on DEMA
        #   new_stop_loss
        sl_dema = ta.dema(close=data.Close, length=self.band_length)
        sl_stdev = ta.stdev(close=data.Close, length=self.band_length)
        sl_lower_band = sl_dema - (self.band_mult * sl_stdev)

        new_stop_loss = float(sl_lower_band[-1:].iloc[0])  # get the last
        self._metrics_manager.gauge("new_stop_loss", self.id, new_stop_loss, ["indicator"])

        #   stop_price
        sl_price_dema = ta.dema(close=data.Low, length=self.band_length)
        sl_price_stdev = ta.stdev(close=data.Low, length=self.band_length)
        sl_price_lower_band = sl_price_dema - (self.band_mult * sl_price_stdev)

        stop_price = float(sl_price_lower_band[-1:].iloc[0])
        self._metrics_manager.gauge("stop_price", self.id, stop_price, ["indicator"])

        # TODO: price and new_stop_loss error conditions
        if stop_price > new_stop_loss:
            self._logger.error(f"price ({stop_price}) should be never higher than new_stop_loss({new_stop_loss})")

        if stop_price < new_stop_loss * 0.8:
            self._logger.error(f"price ({stop_price}) is too far from new_stop_loss({new_stop_loss}) it may happend on test envs.")
            stop_price = new_stop_loss * 0.9

        if new_stop_loss > estimated_close_price:
            self._logger.error(f"new_stop_loss ({new_stop_loss}) should be never higher than last_close({estimated_close_price})")
            new_stop_loss = 0
            stop_price = 0
        # this is a fix for testing

        total_amount_canceled_orders, canceled_orders = self._cancel_active_orders_with_lower_stop_loss(new_stop_loss)
        new_trades_on_limit_amount = 0

        # find trades that get the limit to start trailing stops
        for trade in self.status.active_trades:
            if trade.exit_order_id == '0': # TODO exit_order_id
                if stop_price > trade.entry_price * (1 + (self.minimal_benefit_to_start_trailing / 100)):
                    trade.exit_order_id = "new_grouped_order"
                    new_trades_on_limit_amount = new_trades_on_limit_amount + trade.size

        # create a new stop order with the sum of all canceled orders + the trades that enter the limit
        grouped_amount_canceled_orders_and_new_trades = total_amount_canceled_orders + new_trades_on_limit_amount

        if grouped_amount_canceled_orders_and_new_trades >= self.limit_min_amount():
            new_order = self.stop_loss(amount=grouped_amount_canceled_orders_and_new_trades, stop_price=new_stop_loss, price=stop_price)

            if new_order:
                canceled_orders.append("new_grouped_order")

                # update trades with the new_order_id
                for trade in self.status.active_trades:
                    if trade.exit_order_id in canceled_orders:
                        trade.exit_order_id = new_order.id
                        trade.exit_price = new_stop_loss  # not real until the stop loss really executes.
            else:
                # TODO
                self._logger.error("Can't create stop loss grouped_amount_canceled_orders_and_new_trades ")

        return self.status
