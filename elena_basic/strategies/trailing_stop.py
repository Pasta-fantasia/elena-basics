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


class TrailingStopLoss(GenericBot):
    # Trailing Stop Loss

    band_length: int
    band_mult: float
    initial_sl_factor: float
    sl_limit_price_factor: float
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

    def _calculate_new_trade_size(self) -> float:
        # do we have any new balance to handle?

        total_managed_asset = 0
        # sum open trades amounts
        for trade in self.status.active_trades:
            self._logger.info(trade)
            total_managed_asset += trade.size

        balance = self.get_balance()

        base_symbol = self.pair.base
        base_total = balance.currencies[base_symbol].total
        base_free = balance.currencies[base_symbol].free
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

        try:
            self.band_length = bot_config.config['band_length']
            self.band_mult = bot_config.config['band_mult']
            self.initial_sl_factor = bot_config.config['initial_sl_factor']
            self.sl_limit_price_factor = bot_config.config['sl_limit_price_factor']
            self.asset_to_manage = bot_config.config['asset_to_manage']
        except Exception as err:
            self._logger.error(f"Error initializing Bot config: {err}", error=err)

    def next(self) -> BotStatus:
        self._logger.info('%s strategy: processing next cycle ...', self.name)

        # (1) is there any free balance to handle?
        new_trade_size = self._calculate_new_trade_size()

        # (2) calculate the new stop loss / stop_price / last_close
        data_points = self.band_length + 10  # make sure we ask the enough data for the indicator
        candles = self.read_candles(page_size=data_points)

        # Indicator: Standard Error Bands based on DEMA
        sl_dema = ta.dema(close=candles.Close, length=self.band_length)
        sl_stdev = ta.stdev(close=candles.Close, length=self.band_length)
        sl_lower_band = sl_dema - (self.band_mult * sl_stdev)

        new_stop_loss = float(sl_lower_band[-1:].iloc[0])  # get the last

        sl_price_dema = ta.dema(close=candles.Low, length=self.band_length)
        sl_price_stdev = ta.stdev(close=candles.Low, length=self.band_length)
        sl_price_lower_band = sl_price_dema - (self.band_mult * sl_price_stdev)

        stop_price = float(sl_price_lower_band[-1:].iloc[0])

        # get the last close as entry price for trade
        last_close = self.get_estimated_last_close()

        # TODO: price and new_stop_loss error conditions
        if stop_price > new_stop_loss:
            self._logger.error(f"price ({stop_price}) should be never higher than new_stop_loss({new_stop_loss})")

        if stop_price < new_stop_loss * 0.8:
            self._logger.error(f"price ({stop_price}) is too far from new_stop_loss({new_stop_loss}) it may happend on test envs.")
            stop_price = new_stop_loss * 0.9

        if new_stop_loss > last_close:
            self._logger.error(f"new_stop_loss ({new_stop_loss}) should be never higher than last_close({last_close})")
        # this is a fix for testing

        # (3) New Trade logic
        detected_new_balance = 'detected new balance to manage'

        exit_order_id = detected_new_balance

        if new_trade_size > 0:
            if self.initial_sl_factor != 0:
                # we have an initial_sl_factor so, we create an order every time we detect new balance
                new_stop_loss_initial_sl_factor = last_close * self.initial_sl_factor
                price_initial_sl_factor = new_stop_loss_initial_sl_factor * (1 - self.sl_limit_price_factor)

                new_order = self.stop_loss(amount=new_trade_size,
                                           stop_price=new_stop_loss_initial_sl_factor,
                                           price=price_initial_sl_factor)
                # TODO: check if new_order is not None
                if new_order:
                    exit_order_id = new_order.id
                else:
                    # TODO
                    self._logger.error("Can't create stop loss new_trade with initial_sl_factor")

            # All Trades start/"born" here...
            self.new_trade_manual(size=new_trade_size, entry_price=new_trade_size,
                                  exit_order_id=exit_order_id, exit_price=new_stop_loss)

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
                if stop_price > trade.entry_price * (1 + self.sl_limit_price_factor):
                    trade.exit_order_id = "new_grouped_order"
                    new_trades_on_limit_amount = new_trades_on_limit_amount + trade.size

        # create a new stop order with the sum of all canceled orders + the trades that enter the limit
        grouped_amount_canceled_orders_and_new_trades = total_amount_canceled_orders + new_trades_on_limit_amount

        if grouped_amount_canceled_orders_and_new_trades >= self.limit_min_amount():
            new_order = self.stop_loss(amount=grouped_amount_canceled_orders_and_new_trades,
                                       stop_price=new_stop_loss, price=stop_price)

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
