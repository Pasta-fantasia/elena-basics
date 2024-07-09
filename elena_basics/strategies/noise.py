import pathlib
import time
from os import path

from elena.domain.model.bot_config import BotConfig
from elena.domain.model.bot_status import BotStatus, BotBudget
from elena.domain.model.order import OrderStatusType
from elena.domain.model.order_book import OrderBook
from elena.domain.ports.exchange_manager import ExchangeManager
from elena.domain.ports.logger import Logger
from elena.domain.ports.metrics_manager import MetricsManager
from elena.domain.ports.notifications_manager import NotificationsManager
from elena.domain.ports.strategy_manager import StrategyManager
from elena.domain.services.generic_bot import GenericBot



import numpy as np
import pandas as pd
import pandas_ta as ta

from elena_basics.strategies.common_sl_budget import CommonStopLossBudgetControl


class Noise(CommonStopLossBudgetControl):
    spend_on_order: float
    bb_band_length: float
    bb_band_mult: float

    buy_macd_fast: float
    buy_macd_slow: float
    buy_macd_signal: float

    sell_macd_fast: float
    sell_macd_slow: float
    sell_macd_signal: float

    sell_band_length: float
    sell_band_mult: float
    sell_band_low_pct: float

    minimal_benefit_to_start_trailing: float
    min_price_to_start_trailing: float

    _logger: Logger
    _metrics_manager: MetricsManager
    _notifications_manager: NotificationsManager

    def init(self, manager: StrategyManager, logger: Logger, metrics_manager: MetricsManager, notifications_manager: NotificationsManager, exchange_manager: ExchangeManager, bot_config: BotConfig, bot_status: BotStatus, ):  # type: ignore
        super().init(manager, logger, metrics_manager, notifications_manager, exchange_manager, bot_config, bot_status,)
        self._logger = logger
        self._metrics_manager = metrics_manager
        self._notifications_manager = notifications_manager

        try:
            self.spend_on_order = float(bot_config.config['spend_on_order'])

            self.bb_band_length = float(bot_config.config['bb_band_length'])
            self.bb_band_mult = float(bot_config.config['bb_band_mult'])

            self.buy_macd_fast = float(bot_config.config['buy_macd_fast'])
            self.buy_macd_slow = float(bot_config.config['buy_macd_slow'])
            self.buy_macd_signal = float(bot_config.config['buy_macd_signal'])

            self.sell_macd_fast = float(bot_config.config['sell_macd_fast'])
            self.sell_macd_slow = float(bot_config.config['sell_macd_slow'])
            self.sell_macd_signal = float(bot_config.config['sell_macd_signal'])

            self.sell_band_length = float(bot_config.config['sell_band_length'])
            self.sell_band_mult = float(bot_config.config['sell_band_mult'])
            self.sell_band_low_pct = float(bot_config.config['sell_band_low_pct'])
            if self.sell_band_low_pct <= 0.0:
                raise ValueError('band_low_pct must be > 0.0')

            self.minimal_benefit_to_start_trailing = float(bot_config.config['minimal_benefit_to_start_trailing'])
            if 'min_price_to_start_trailing' in self.bot_config.config:
                self.min_price_to_start_trailing = float(bot_config.config['min_price_to_start_trailing'])
            else:
                self.min_price_to_start_trailing = 0.0
        except Exception as err:
            self._logger.error(f"Error initializing Bot config: {err}", error=err)

    @staticmethod
    def get_macd_histogram(data, p_fast, p_slow, p_signal) -> float:
        macd = ta.macd(close=data.Close, fast=p_fast, slow=p_slow, signal=p_signal)
        return macd[-1:].iloc[0][1]

    def next(self) -> BotStatus:
        self._logger.info('%s strategy: processing next cycle ...', self.name)
        
        # basic initial data
        min_amount = self.limit_min_amount()

        min_cost = self.limit_min_cost()
        if not min_cost:
            self._logger.error("Cannot get min_cost")
            return

        estimated_close_price = self.get_estimated_last_close()
        if not estimated_close_price:
            self._logger.error("Cannot get_estimated_last_close")
            return

        estimated_sell_price = self.get_estimated_sell_price_from_cache()
        if not estimated_sell_price:
            self._logger.error("Cannot estimated_sell_price")
            return

        balance = self.get_balance()
        if not balance:
            self._logger.error("Cannot get balance")
            return

        base_symbol = self.pair.base
        base_free = balance.currencies[base_symbol].free

        # https://github.com/twopirllc/pandas-ta/issues/523
        # In this case, macd aborts further calculation since close.size < slow + signal - 1 (32 < 26 + 9 - 1 = 34)

        data_points = int(max(self.bb_band_length,
                              self.buy_macd_fast, self.buy_macd_slow, self.buy_macd_slow + self.buy_macd_signal,
                              self.sell_macd_fast, self.sell_macd_slow,  self.sell_macd_slow + self.sell_macd_signal,
                              self.sell_band_length) + 10)  # make sure we ask the enough data for the indicator
        data = self.read_candles(page_size=data_points)

        # Indicators calc

        bbands = ta.bbands(close=data.Close, length=self.bb_band_length, std=self.bb_band_mult)

        bb_lower_band = bbands[-1:].iloc[0][0]
        bb_central_band = bbands[-1:].iloc[0][1]
        bb_upper_band = bbands[-1:].iloc[0][2]

        self._metrics_manager.gauge("bb_lower_band", self.id, bb_lower_band, ["indicator"])
        self._metrics_manager.gauge("bb_central_band", self.id, bb_central_band, ["indicator"])
        self._metrics_manager.gauge("bb_upper_band", self.id, bb_upper_band, ["indicator"])

        buy_macd_h = self.get_macd_histogram(data, self.buy_macd_fast, self.buy_macd_slow, self.buy_macd_signal)
        self._metrics_manager.gauge("buy_macd_h", self.id, buy_macd_h, ["indicator"])

        sell_macd_h = self.get_macd_histogram(data, self.sell_macd_fast, self.sell_macd_slow, self.sell_macd_signal)
        self._metrics_manager.gauge("sell_macd_h", self.id, sell_macd_h, ["indicator"])

        # SELL LOGIC
        # if sell condition are met sell any trade with minimal benefit
        if estimated_sell_price > bb_upper_band and sell_macd_h < 0:
            orders_to_cancel = []
            sell_size = 0.0
            trades_to_close = []
            for trade in self.status.active_trades:
                if estimated_sell_price > trade.entry_price * (1 + (self.minimal_benefit_to_start_trailing / 100)):
                    # sum trades to sell, create a list of trades to group in the sell order
                    # is any stop loss open? => create a list of orders to cancel
                    sell_size = sell_size + trade.size
                    trades_to_close.append(trade)
                    if trade.exit_order_id != '0':  # TODO exit_order_id:
                        if trade.exit_order_id not in orders_to_cancel:
                            orders_to_cancel.append(trade.exit_order_id)
                            # TODO: Should be checked OrderType == stop loss?
                            #  - if it's partial?

            if sell_size > 0:
                # verify balance
                max_sell = min(sell_size, base_free)
                if max_sell < sell_size:
                    sale_diff = sell_size - max_sell
                    trade = trades_to_close[0]
                    self._logger.error(f"Selling too much, balance is {max_sell} but trying to sell {sell_size}. Trade ID: {trade.id}, size {trade.size} changed to {trade.size - sale_diff}")
                    trade.size = self.amount_to_precision(trade.size - sale_diff)
                    sell_size = max_sell

                for order_id in orders_to_cancel:
                    cancelled_order = self.cancel_order(order_id)
                    if not cancelled_order:
                        self._logger.error(f"Error canceling order: {order_id}.")

                sell_order = self.create_market_sell_order(sell_size, trades_to_close)

                if sell_order:
                    if sell_order.status == OrderStatusType.closed:
                        sell_estimation_accuracy = sell_order.average - estimated_sell_price
                        self._metrics_manager.gauge("sell_order_average", self.id, sell_order.average, ["indicator"])
                        self._metrics_manager.gauge("sell_estimation_accuracy", self.id, sell_estimation_accuracy, ["indicator"])
                    else:
                        self._logger.error(f"Sell order not closed! Order status = {sell_order.status}")

                else:
                    self._logger.error("Sell order failed!")
                    self._logger.error(f"{sell_order}")


            # if sum_trades>0 =>
            #   if stop loss are open => cancel before sell
            #   create market sell order or a "forced" stop loss?
            #   mark all trade with that exit order
            # check balance before?
            # what if the sell doesn't work

        # BUY LOGIC
        if estimated_close_price < bb_central_band and buy_macd_h > 0:
            self.buy_based_on_budget(balance, estimated_close_price, min_amount, min_cost, self.spend_on_order)


        # TRAILING STOP LOGIC
        self.manage_trailing_stop_losses(data, estimated_close_price, base_free, self.sell_band_length, self.sell_band_mult, self.sell_band_low_pct, self.minimal_benefit_to_start_trailing, self.min_price_to_start_trailing)

        return self.status
