# 0.1.9
- fix: [ERROR] Error creating stop loss: binance Stop price would trigger immediately

# 0.1.8
- fix: Possible problem with moving stop losses coming from multiple trades. (DCA)

# 0.1.7
- fix: [ERROR] Error creating stop loss: binance Stop price would trigger immediately. Review exit #22
- fix: [ERROR] Error canceling order: new_grouped_order. #23

# 0.1.6
- fix: [ERROR] Error creating stop loss: binance Stop price would trigger immediately.

# 0.1.5
- fix: [ERROR] Can't create stop loss grouped_amount_canceled_orders_and_new_trades #16. Cancel, balance check, sells.

# 0.1.4
- fix: [ERROR] Can't create stop loss grouped_amount_canceled_orders_and_new_trades #16. Balance check before sells.

# 0.1.3
- fix: [ERROR] Can't create stop loss grouped_amount_canceled_orders_and_new_trades #16

# 0.1.2
- fix: [ERROR] Error creating market sell order: binance Account has insufficient balance for requested action. #14

# 0.1.1
- fix: insufficient data_point for macd indicator

# 0.1.0

feat: 
- NoiseTrader v0 [noise.py](elena_basics%2Fstrategies%2Fnoise.py)
- Base class for common budget and trailing stop code [common_sl_budget.py](elena_basics%2Fstrategies%2Fcommon_sl_budget.py)

# 0.0.17

fix:
- logger.error to warning on new_stop_loss higher than last_close

# 0.0.16

fix:
- strategies.yaml enabled

docs:
- strategies.yaml comments


# 0.0.15

fix:
- module name

# 0.0.14

feat: 
- new stop_price calc
- min_price_to_start_trailing
- spent_by_frequency

fix:
- module name