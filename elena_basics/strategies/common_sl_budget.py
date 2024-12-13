import pathlib
import time
from os import path
from elena.domain.model.balance import Balance
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


class CommonStopLossBudgetControl(GenericBot):
    _logger: Logger
    _metrics_manager: MetricsManager
    _notifications_manager: NotificationsManager

    def _spent_by_frequency(self, frequency="D", shift=None):
        if len(self.status.active_trades) > 0:
            df = pd.DataFrame([model.dict() for model in self.status.active_trades])
            df['entry_time'] = pd.to_datetime(df['entry_time'], unit='ms', utc=True)
            # https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.Grouper.html
            # https://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html#offset-aliases
            if shift:
                df['entry_time'] = df['entry_time'] + pd.Timedelta(shift)
            return df.groupby(pd.Grouper(key='entry_time', freq=frequency)).agg({'entry_cost': 'sum'})
        else:
            df = pd.DataFrame(
                {
                    "entry_time": [pd.Timestamp.now(tz='UTC')],
                    "entry_cost": [0.0]
                }
            )
            return df

    def _spent_in_current_freq(self, frequency="D", spent_times_shift=None) -> float:
        real_spent_by_frequency = self._spent_by_frequency(frequency, spent_times_shift)

        now = pd.DataFrame(
            {
                "entry_time": [pd.Timestamp.now(tz='UTC')],
                "fake_entry_cost": [0.0]
            }
        )
        if spent_times_shift:
            now['entry_time'] = now['entry_time'] + pd.Timedelta(spent_times_shift)
        fake_spent_by_frequency = now.groupby(pd.Grouper(key='entry_time', freq=frequency)).agg({'fake_entry_cost': 'sum'})
        merged = real_spent_by_frequency.merge(fake_spent_by_frequency, on='entry_time', how='outer')

        spent = merged["entry_cost"][-1:].iloc[0]

        if np.isnan(spent):
            spent = 0.0
        else:
            spent = float(spent)

        return spent

    def budget_left_in_freq(self) -> float:
        if 'spent_times_shift' in self.bot_config.config:
            spent_times_shift = self.bot_config.config['spent_times_shift']
        else:
            spent_times_shift = None

        budget_left = self.status.budget.free
        if 'daily_budget' in self.bot_config.config:
            frequency = "D"
            daily_budget = self.bot_config.config['daily_budget']
            spent = self._spent_in_current_freq(frequency, spent_times_shift)
            daily_budget_left = daily_budget - spent
            budget_left = min(budget_left, daily_budget_left)

        if 'weekly_budget' in self.bot_config.config:
            frequency = "W"
            weekly_budget = self.bot_config.config['weekly_budget']
            spent = self._spent_in_current_freq(frequency, spent_times_shift)
            weekly_budget_left = weekly_budget - spent
            budget_left = min(budget_left, weekly_budget_left)

        if budget_left < 0.0:
            budget_left = 0.0

        return budget_left

    def buy_based_on_budget(self, balance: Balance, estimated_close_price: float, min_amount: float, min_cost: float, spend_on_order: float) -> bool:
        buy_ok = True
        quote_symbol = self.pair.quote
        quote_free = balance.currencies[quote_symbol].free

        amount_to_spend = min(self.budget_left_in_freq(), spend_on_order, quote_free)
        amount_to_buy = amount_to_spend / estimated_close_price
        amount_to_buy = self.amount_to_precision(amount_to_buy)

        if amount_to_buy >= min_amount and amount_to_spend >= min_cost:
            market_buy_order = self.create_market_buy_order(amount_to_buy)
            if not market_buy_order:
                self._logger.error("Buy order failed!")
                buy_ok = False
        else:
            msg = f"Not enough balance to buy min_amount/min_cost. {self.pair.base}, quote_free={quote_free}, min_amount={min_amount}, min_cost={min_cost}, amount_to_spend={amount_to_spend}, free-budget={self.status.budget.free}, estimated_close_price={estimated_close_price}"
            self._logger.warning(msg)
            # self._notifications_manager.medium(msg)
            buy_ok = False

        return buy_ok

    def _cancel_active_orders_with_lower_stop_loss(self, new_stop_loss: float) -> float:
        # Cancel any active stop order with a limit lower than the new one.
        # return the total amount of canceled orders
        total_amount_canceled_orders = 0
        canceled_orders = []
        for order in self.status.active_orders[:]:
            if new_stop_loss > order.stop_price:
                cancelled_order = self.cancel_order(order.id)
                if cancelled_order:
                    total_amount_canceled_orders = total_amount_canceled_orders + order.amount
                    canceled_orders.append(order.id)
                else:
                    self._logger.error(f"Error canceling order: {order.id}.")
        return total_amount_canceled_orders, canceled_orders

    def manage_trailing_stop_losses(self, data: pd.DataFrame, estimated_close_price: float, band_length: float,
                                    band_mult: float, band_low_pct: float, minimal_benefit_to_start_trailing: float,
                                    min_price_to_start_trailing: float):
        # TRAILING STOP LOGIC
        # Indicator: Standard Error Bands based on DEMA
        #   new_stop_loss

        sl_dema = ta.dema(close=data.Close, length=band_length)
        sl_stdev = ta.stdev(close=data.Close, length=band_length)
        sl_lower_band = sl_dema - (band_mult * sl_stdev)

        new_stop_loss = float(sl_lower_band[-1:].iloc[0])  # get the last
        self._metrics_manager.gauge("new_stop_loss", self.id, new_stop_loss, ["indicator"])

        #   stop_price
        stop_price = new_stop_loss * (1 - (band_low_pct / 100))
        self._metrics_manager.gauge("stop_price", self.id, stop_price, ["indicator"])

        if stop_price < new_stop_loss * 0.8:
            self._logger.error(f"price ({stop_price}) is too far from new_stop_loss({new_stop_loss}) it may happend on test envs.")
            new_stop_loss = 0.0
            stop_price = 0.0

        if stop_price >= estimated_close_price:
            self._logger.warning(f"stop_price ({stop_price}) should be never higher than last_close({estimated_close_price})")
            new_stop_loss = 0.0
            stop_price = 0.0

        if new_stop_loss >= estimated_close_price:
            self._logger.warning(f"new_stop_loss ({new_stop_loss}) should be never higher than last_close({estimated_close_price})")
            new_stop_loss = 0.0
            stop_price = 0.0

        total_amount_canceled_orders, canceled_orders = self._cancel_active_orders_with_lower_stop_loss(new_stop_loss)
        new_trades_on_limit_amount = 0

        # find trades with errors
        for trade in self.status.active_trades[:]:
            if trade.exit_order_id == "new_grouped_order":  # TODO: check if it happens again.
                trade.exit_order_id = '0'
                self._logger.warning(f"trade ({trade.id}) had new_grouped_order as exit_order_id setting to 0")

        # find trades that get the limit to start trailing stops
        for trade in self.status.active_trades[:]:
            if trade.exit_order_id == '0':  # TODO exit_order_id
                if stop_price > trade.entry_price * (1 + (minimal_benefit_to_start_trailing / 100)) and stop_price > min_price_to_start_trailing:
                    trade.exit_order_id = "new_grouped_order"
                    new_trades_on_limit_amount = new_trades_on_limit_amount + trade.size

        # create a new stop order with the sum of all canceled orders + the trades that enter the limit
        grouped_amount_canceled_orders_and_new_trades = total_amount_canceled_orders + new_trades_on_limit_amount

        if grouped_amount_canceled_orders_and_new_trades >= self.limit_min_amount():
            # verify balance, it needs to be checked after any cancellation
            base_free = 0

            balance = self.get_balance()
            if not balance:
                self._logger.error("Cannot get balance")
                return

            base_symbol = self.pair.base
            base_free = balance.currencies[base_symbol].free

            # in some cases balance is not available after some time
            retry = 0
            retry_limit = 5

            while total_amount_canceled_orders > base_free and retry < retry_limit:
                self._logger.warning(f"Orders for {total_amount_canceled_orders} were cancelled but balance is {base_free}. Retrying...")
                time.sleep(5)
                balance = self.get_balance()
                if not balance:
                    self._logger.error("Cannot get balance")
                    return

                base_symbol = self.pair.base
                base_free = balance.currencies[base_symbol].free
                retry = retry + 1

            if retry >= retry_limit:
                self._logger.error(f"Orders for {total_amount_canceled_orders} were cancelled but balance is {base_free}, after retrying {retry_limit} times.")
                return

            max_sell = min(grouped_amount_canceled_orders_and_new_trades, base_free)
            if max_sell < grouped_amount_canceled_orders_and_new_trades:
                sale_diff = grouped_amount_canceled_orders_and_new_trades - max_sell
                self._logger.error(f"Stop loss amount is higher than balance. Balance: {max_sell} but trying to sell {grouped_amount_canceled_orders_and_new_trades}.")
                grouped_amount_canceled_orders_and_new_trades = max_sell
            else:
                sale_diff = 0.0

            new_order = self.stop_loss(amount=grouped_amount_canceled_orders_and_new_trades, stop_price=new_stop_loss, price=stop_price)

            if new_order:
                canceled_orders.append("new_grouped_order")

                # update trades with the new_order_id
                for trade in self.status.active_trades[:]:
                    if trade.exit_order_id in canceled_orders:
                        trade.exit_order_id = new_order.id
                        trade.exit_price = new_stop_loss  # not real until the stop loss really executes.
                        if sale_diff > 0:
                            if trade.size >= sale_diff:
                                self._logger.error(f"Trade ID: {trade.id}, size {trade.size} changed to {trade.size - sale_diff}")
                                trade.size = self.amount_to_precision(trade.size - sale_diff)
                                sale_diff = 0.0
                if sale_diff > 0:
                    self._logger.error(f"After checking all trades {sale_diff} was higher than any trade... that's not a rounding problem.")
            else:
                # TODO
                self._logger.error("Can't create stop loss grouped_amount_canceled_orders_and_new_trades ")
                # ensure trade.exit_order_id = "new_grouped_order" is overwritten when stop loss fails
                for trade in self.status.active_trades:
                    if trade.exit_order_id in canceled_orders:
                        self._logger.warning(f"Setting exit_order_id to '0' on {trade.id}")
                        trade.exit_order_id = '0'  # TODO exit_order_id
                        trade.exit_price = 0.0


    def init(self, manager: StrategyManager, logger: Logger, metrics_manager: MetricsManager, notifications_manager: NotificationsManager, exchange_manager: ExchangeManager, bot_config: BotConfig, bot_status: BotStatus, ):  # type: ignore
        super().init(manager, logger, metrics_manager, notifications_manager, exchange_manager, bot_config, bot_status,)

    def next(self) -> BotStatus:
        return self.status
