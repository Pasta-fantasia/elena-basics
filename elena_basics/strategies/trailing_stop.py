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


# noinspection DuplicatedCode
class TrailingStopLoss(GenericBot):
    # Trailing Stop Loss

    band_length: int
    band_mult: float
    band_low_pct: float
    minimal_benefit_to_start_trailing: float
    min_price_to_start_trailing: float

    asset_to_manage: str

    _logger: Logger
    _metrics_manager: MetricsManager
    _notifications_manager: NotificationsManager

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

    def _calculate_new_trade_size(self) -> float:
        # do we have any new balance to handle?

        total_managed_asset = 0
        # sum open trades amounts
        for trade in self.status.active_trades:
            self._logger.info(trade)
            total_managed_asset += trade.size

        balance = self.get_balance()

        base_symbol = self.pair.base
        if base_symbol in balance.currencies:
            base_total = balance.currencies[base_symbol].total
            base_free = balance.currencies[base_symbol].free
        else:
            base_total = 0.0
            base_free = 0.0
        total_to_manage = self._get_max_asset_to_manage(base_total)
        new_trade_size = total_to_manage - total_managed_asset

        if base_free < new_trade_size:
            new_trade_size = base_free

        min_amount = self.limit_min_amount()
        if new_trade_size < min_amount:
            new_trade_size = 0

        return new_trade_size

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
            self.band_length = float(bot_config.config['band_length'])
            self.band_mult = float(bot_config.config['band_mult'])
            self.asset_to_manage = str(bot_config.config['asset_to_manage'])  # asset_to_manage can be a number or a %
            self.band_low_pct = float(bot_config.config['band_low_pct'])
            if self.band_low_pct <= 0.0:
                raise ValueError('band_low_pct must be > 0.0')
            self.minimal_benefit_to_start_trailing = float(bot_config.config['minimal_benefit_to_start_trailing'])
            if 'min_price_to_start_trailing' in self.bot_config.config:
                self.min_price_to_start_trailing = float(bot_config.config['min_price_to_start_trailing'])
            else:
                self.min_price_to_start_trailing = 0.0

        except Exception as err:
            self._logger.error(f"Error initializing Bot config: {err}", error=err)

    def next(self) -> BotStatus:
        self._logger.info('%s strategy: processing next cycle ...', self.name)

        # (1) is there any free balance to handle?
        new_trade_size = self._calculate_new_trade_size()

        estimated_close_price = self.get_estimated_last_close()
        if not estimated_close_price:
            self._logger.error("Cannot get_estimated_last_close")
            return

        # (2) calculate the new stop loss / stop_price / last_close
        data_points = self.band_length + 10  # make sure we ask the enough data for the indicator
        candles = self.read_candles(page_size=data_points)

        # Indicator: Standard Error Bands based on DEMA
        #   new_stop_loss
        sl_dema = ta.dema(close=candles.Close, length=self.band_length)
        sl_stdev = ta.stdev(close=candles.Close, length=self.band_length)
        sl_lower_band = sl_dema - (self.band_mult * sl_stdev)

        new_stop_loss = float(sl_lower_band[-1:].iloc[0])  # get the last
        self._metrics_manager.gauge("new_stop_loss", self.id, new_stop_loss, ["indicator"])

        #   stop_price
        stop_price = new_stop_loss * (1 - (self.band_low_pct / 100))
        self._metrics_manager.gauge("stop_price", self.id, stop_price, ["indicator"])

        if stop_price < new_stop_loss * 0.8:
            self._logger.error(f"price ({stop_price}) is too far from new_stop_loss({new_stop_loss}) it may happend on test envs.")
            new_stop_loss = 0
            stop_price = 0

        if new_stop_loss > estimated_close_price:
            self._logger.warning(f"new_stop_loss ({new_stop_loss}) should be never higher than last_close({estimated_close_price})")
            new_stop_loss = 0
            stop_price = 0

        # (3) New Trade logic
        detected_new_balance = 'detected new balance to manage'

        exit_order_id = detected_new_balance

        if new_trade_size > 0:
            # All Trades start/"born" here...
            self.new_trade_manual(size=new_trade_size, entry_price=estimated_close_price, exit_order_id=exit_order_id, exit_price=new_stop_loss)

        # (4) OLD Trades logic & cancelled orders

        # trades are open every time a new balance is detected
        # loop over trades and create sl orders for that trades that are detected_new_balance
        #  and have a new_stop_loss/stop_price over the entry_price
        # Create only one order and add total_amount_canceled_orders

        total_amount_canceled_orders, canceled_orders = self._cancel_active_orders_with_lower_stop_loss(new_stop_loss)
        new_trades_on_limit_amount = 0

        # find trades that get the limit to start trailing stops
        for trade in self.status.active_trades:
            if trade.exit_order_id == detected_new_balance:
                if stop_price > trade.entry_price * (1 + (self.minimal_benefit_to_start_trailing/100)) and stop_price > self.min_price_to_start_trailing:
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
