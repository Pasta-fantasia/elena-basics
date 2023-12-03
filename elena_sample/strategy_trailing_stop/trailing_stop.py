import pathlib
from logging import Logger

from elena.domain.model.time_frame import TimeFrame
from elena.domain.model.bot_config import BotConfig
from elena.domain.model.trade import Trade
from elena.domain.model.bot_status import BotStatus

from elena.domain.ports.logger import Logger
from elena.domain.ports.strategy_manager import StrategyManager

from elena.domain.services.elena import Elena
from elena.domain.services.generic_bot import GenericBot

from elena.adapters.bot_manager.local_bot_manager import LocalBotManager
from elena.adapters.config.local_config_reader import LocalConfigReader
from elena.adapters.logger.local_logger import LocalLogger

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

    def _calculate_new_trade_size(self, status: BotStatus) -> float:
        # do we have any new balance to handle?

        total_managed_asset = 0
        # sum open trades amounts
        for trade in status.active_trades:
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

    def _cancel_active_orders_with_lower_stop_loss(self, status: BotStatus, new_stop_loss: float) -> float:
        # Cancel any active stop order with a limit lower than the new one.
        # return the total amount of canceled orders
        total_amount_canceled_orders = 0
        for order in status.active_orders:
            if new_stop_loss > order.stop_price:
                cancelled_order = self.cancel_order(order.id)
                if cancelled_order:
                    total_amount_canceled_orders = total_amount_canceled_orders + order.amount
                else:
                    self._logger.error(f"Error canceling order: {order.id}.")
        return total_amount_canceled_orders

    def init(self, manager: StrategyManager, logger: Logger, bot_config: BotConfig):  # type: ignore
        super().init(manager, logger, bot_config)

        try:
            self.band_length = bot_config.config['band_length']
            self.band_mult = bot_config.config['band_mult']
            self.initial_sl_factor = bot_config.config['initial_sl_factor']
            self.sl_limit_price_factor = bot_config.config['sl_limit_price_factor']
            self.asset_to_manage = bot_config.config['asset_to_manage']
        except Exception as err:
            self._logger.error(f"Error initializing Bot config: {err}", error=err)

    def next(self, status: BotStatus) -> BotStatus:
        self._logger.info('%s strategy: processing next cycle ...', self.name)

        # (1) is there any free balance to handle?
        new_trade_size = self._calculate_new_trade_size(status)

        # (2) calculate the new stop loss
        data_points = self.band_length + 10  # make sure we ask the enough data for the indicator
        candles = self.read_candles(data_points)

        # Indicator: Standard Error Bands based on DEMA
        dema = ta.dema(close=candles.Close, length=self.band_length)
        stdev = ta.stdev(close=candles.Close, length=self.band_length)
        lower_band = dema - (self.band_mult * stdev)

        new_stop_loss = float(lower_band[-1:].iloc[0])  # get the last
        price = float(lower_band[-2:-1].iloc[0])

        # get the last close as entry price for trade
        # TODO: use ticker... in 1d time frame the entry is yesterday's close!
        last_close = candles[-1:]['Close'].iloc[0]

        new_stop_loss_initial_sl_factor = last_close * self.initial_sl_factor

        # TODO: price and new_stop_loss correction
        if price > new_stop_loss:
            price = new_stop_loss * 0.995  # TODO: Think how to do it
            self._logger.error(f"price ({price}) should be never higher than new_stop_loss({new_stop_loss})")

        if new_stop_loss > last_close:
            new_stop_loss = new_stop_loss_initial_sl_factor
            self._logger.error(f"new_stop_loss ({new_stop_loss}) should be never higher than last_close({last_close})")
        # this is a fix for testing

        # TODO: Verify Bot is doing it right and remove.
        # correct precisions for exchange
        new_stop_loss = self.price_to_precision(new_stop_loss)
        new_stop_loss_initial_sl_factor = self.price_to_precision(new_stop_loss_initial_sl_factor)
        price = self.price_to_precision(price)
        new_trade_size = self.amount_to_precision(new_trade_size)

        # (3) New Trade logic
        detected_new_balance = 'detected new balance to manage'

        if new_trade_size > 0:
            if self.initial_sl_factor != 0:
                # we have an initial_sl_factor so, we create an order every time we detect new balance
                price_initial_sl_factor = new_stop_loss_initial_sl_factor * (1 - self.sl_limit_price_factor)

                new_order = self.stop_loss_limit(amount=new_trade_size,
                                                 stop_price=new_stop_loss_initial_sl_factor,
                                                 price=price_initial_sl_factor)
                status.active_orders.append(new_order)
                exit_order_id = new_order.id
            else:
                exit_order_id = detected_new_balance

            # All Trades start/"born" here...
            new_trade = Trade(exchange_id=self.config.exchange_id, bot_id=self.config.id,
                              strategy_id=self.config.strategy_id, pair=self.config.pair,
                              size=new_trade_size,
                              entry_order_id='manual', entry_price=last_close,
                              exit_order_id=exit_order_id, exit_price=new_stop_loss,
                              )
            status.active_trades.append(new_trade)

        # (4) OLD Trades logic

        # trades are open every time a new balance is detected
        # loop over trades and create sl orders for that trades that are detected_new_balance
        #  and have a new_stop_loss over the entry_price
        # Create only one order and add total_amount_canceled_orders

        total_amount_canceled_orders = self._cancel_active_orders_with_lower_stop_loss(status, new_stop_loss)

        for trade in status.active_trades:
            if trade.exit_order_id == detected_new_balance:
                amount = trade.size
                if new_stop_loss > trade.entry_price * (1 + self.sl_limit_price_factor):
                    new_stop_loss_for_this_order = new_stop_loss
                    price_for_this_order = price

                    new_order = self.stop_loss_limit(amount=amount,
                                                     stop_price=new_stop_loss_for_this_order,
                                                     price=price_for_this_order)
                    status.active_orders.append(new_order)
                    trade.exit_order_id = new_order.id

        return status
