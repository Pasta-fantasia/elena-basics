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

    budget: float

    def init(self, manager: StrategyManager, logger: Logger,
             exchange_manager: ExchangeManager, bot_config: BotConfig, bot_status: BotStatus):

        super().init(manager, logger, exchange_manager, bot_config, bot_status)

        try:
            self.budget = bot_config.config['budget']
        except Exception as err:
            self._logger.error(f"Error initializing Bot config: {err}", error=err)

    def next(self) -> BotStatus:
        self._logger.info('%s strategy: processing next cycle ...', self.name)

        min_amount = self.limit_min_amount()
        if not min_amount:
            # TODO convert to return None and log.error
            raise Exception("Cannot get min_amount")

        estimated_close_price = self.get_estimated_last_close()
        if not estimated_close_price:
            raise Exception("Cannot get_estimated_last_close")

        balance = self.get_balance()
        if not balance:
            raise Exception("Cannot get balance")

        quote_symbol = self.pair.quote
        quote_free = balance.currencies[quote_symbol].free

        if self.budget <= quote_free:
            amount_to_spend = self.budget
        else:
            amount_to_spend = quote_free
        amount_to_buy = amount_to_spend / estimated_close_price
        amount_to_buy = self.amount_to_precision(amount_to_buy)

        if amount_to_buy < min_amount:
            self._logger.error("Not enough balance to buy min_amount. {self.pair.base}, quote_free={quote_free}, "
                               "min_amount={min_amount}, estimated_close_price={estimated_close_price}")
            raise Exception("Not enough balance to buy min_amount. {self.pair.base}, quote_free={quote_free}, "
                            "min_amount={min_amount}, estimated_close_price={estimated_close_price}")

        market_buy_order = self.create_market_buy_order(amount_to_buy)

        if not market_buy_order:
            self._logger.error("Buy order failed!")
            raise Exception("Buy order failed!")

        return self.status
