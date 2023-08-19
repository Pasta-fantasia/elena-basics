# to operate directly with the exchange
from decouple import AutoConfig
from decouple import config
import ccxt


config = AutoConfig(' ') # https://github.com/henriquebastos/python-decouple/issues/116

apiKey = config('apiKey')
secret = config('secret')

exchange = ccxt.binance({
    'apiKey': apiKey,
    'secret': secret,
    'options': {
         'defaultType': 'spot',  # // spot, future, margin
    },
})

exchange.set_sandbox_mode(True)  # enable sandbox mode

symbol = 'BTC/USDT'
balance = exchange.fetch_balance()
market = exchange.market(symbol)

open_orders = exchange.fetch_open_orders(symbol)

# exchange.cancel_all_orders(symbol)
# o22 = exchange.fetch_order('6836222',symbol)

balance_USDT = balance[market['quote']]

# buy 1 BTC, it's needed when the stop orders are triggered
type = 'market'
side = 'buy'
amount = 1

exchange.verbose = True
create_order = exchange.create_order(symbol, type, side, amount)

