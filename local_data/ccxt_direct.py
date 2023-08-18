import ccxt

# to operate directly over the exchange

apiKey = ''
secret = ''

exchange = ccxt.binance({
    'apiKey': apiKey,
    'secret': secret,
    'options': {
         'defaultType': 'spot',  # // spot, future, margin
    },
})

exchange.set_sandbox_mode(True)  # enable sandbox mode

symbol = 'BTC/USDT'
market = exchange.market(symbol)

exchange.cancel_all_orders(symbol)

balance = exchange.fetch_balance()
balance_USDT = balance[market['quote']]

type = 'market'
side = 'buy'
amount = 1


exchange.verbose = True
create_order = exchange.create_order(symbol, type, side, amount)

