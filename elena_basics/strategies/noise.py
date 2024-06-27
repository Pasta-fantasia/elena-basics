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

    def __init__(self):

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

        balance = self.get_balance()
        if not balance:
            self._logger.error("Cannot get balance")
            return

        data_points = int(max(self.bb_band_length,
                              self.buy_macd_fast, self.buy_macd_fast,
                              self.sell_macd_fast, self.sell_macd_slow,
                              self.sell_band_lenght) + 10)  # make sure we ask the enough data for the indicator
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
        if estimated_close_price > bb_upper_band and sell_macd_h < 0:
            for trade in self.status.active_trades:
                if estimated_close_price > trade.entry_price * (1 + (self.minimal_benefit_to_start_trailing / 100)):
                    # sum trades to sell, create alist of trades to group in the sell order
                    # is any stop loss open? => create a list of orders to cancel

                    total_amount_canceled_orders, canceled_orders = self._cancel_active_orders_with_lower_stop_loss(estimated_close_price)
                    pass

            # if sum_trades>0 =>
            #   if stop loss are open => cancel before sell
            #   create market sell order or a "forced" stop loss?
            #   mark all trade with that exit order
            # check balance before?
            # what if the sell doesn't work

        # BUY LOGIC
        if estimated_close_price < bb_central_band and buy_macd_h > 0:
            self.buy_based_on_budget(balance, estimated_close_price, min_amount, min_cost)


        # TRAILING STOP LOGIC
        self.manage_trailing_stop_losses(data, estimated_close_price, self.band_length, self.band_mult, self.band_low_pct, self.minimal_benefit_to_start_trailing, self.min_price_to_start_trailing)

        return self.status
