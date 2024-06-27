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


class DCA_Conditional_Buy_LR_with_TrailingStop(CommonStopLossBudgetControl):
    spend_on_order: float
    lr_buy_longitude: float
    band_length: float
    band_mult: float
    band_low_pct: float
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
            self.lr_buy_longitude = float(bot_config.config['lr_buy_longitude'])
            self.band_length = float(bot_config.config['band_length'])
            self.band_mult = float(bot_config.config['band_mult'])
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
        if angle > 0:
            self.buy_based_on_budget(balance, estimated_close_price, min_amount, min_cost, self.spend_on_order)

        # TRAILING STOP LOGIC
        self.manage_trailing_stop_losses(data, estimated_close_price, self.band_length, self.band_mult, self.band_low_pct, self.minimal_benefit_to_start_trailing, self.min_price_to_start_trailing)

        return self.status
