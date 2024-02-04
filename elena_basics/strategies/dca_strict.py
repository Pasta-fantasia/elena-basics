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


class DCA_Strict(GenericBot):
    # Strict dates DCA, just buy on a regular basis.

    spend_on_order: float

    _logger: Logger
    _metrics_manager: MetricsManager
    _notifications_manager: NotificationsManager

    def init(self, manager: StrategyManager, logger: Logger, metrics_manager: MetricsManager, notifications_manager: NotificationsManager, exchange_manager: ExchangeManager, bot_config: BotConfig, bot_status: BotStatus, ):  # type: ignore
        super().init(manager, logger, metrics_manager, notifications_manager, exchange_manager, bot_config, bot_status,)
        self._logger = logger
        self._metrics_manager = metrics_manager
        self._notifications_manager = notifications_manager

        try:
            self.spend_on_order = bot_config.config['spend_on_order']
        except Exception as err:
            self._logger.error(f"Error initializing Bot config: {err}", error=err)

    def next(self) -> BotStatus:
        self._logger.info('%s strategy: processing next cycle ...', self.name)

        min_amount = self.limit_min_amount()
        if not min_amount:
            self._logger.error("Cannot get min_amount")
            return

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

        quote_symbol = self.pair.quote
        quote_free = balance.currencies[quote_symbol].free

        amount_to_spend = min(self.status.budget.free, self.spend_on_order, quote_free)
        amount_to_buy = amount_to_spend / estimated_close_price
        amount_to_buy = self.amount_to_precision(amount_to_buy)

        if amount_to_buy < min_amount or amount_to_spend < min_cost:
            msg = f"Not enough balance to buy min_amount/min_cost. {self.pair.base}, quote_free={quote_free}, min_amount={min_amount}, min_cost={min_cost}, amount_to_spend={amount_to_spend}, free-budget={self.status.budget.free}, estimated_close_price={estimated_close_price}"
            self._logger.warning(msg)
            self._notifications_manager.medium(msg)
            return

        market_buy_order = self.create_market_buy_order(amount_to_buy)

        if not market_buy_order:
            self._logger.error("Buy order failed!")
            return

        return self.status
