# Elena Sample Code

1. Create your elena_config.yaml from local_data/elena_config_example
2. Set your ELENA_HOME to the folder you put that elena_config.yaml 


To create Test API
https://testnet.binance.vision/
https://www.binance.com/en/support/faq/how-to-test-my-functions-on-binance-testnet-ab78f9a1b8824cf0a106b4229c76496d



While debugging on binance.py
self.cancel_all_orders('BTC/USDT')

TODOs moved out from code

        # _exchange = self._get_exchange(bot_config.exchange_id)
        # TODO: always send time frame... add in config
        # _candles = self._exchange_manager.read_candles(_exchange, bot_config.pair)
        # TODO: _order_book is only necessary if we are going to put an order
        # _order_book = self._exchange_manager.read_order_book(_exchange, bot_config.pair)
        # TODO: _balance is only necessary if we are going to put an order
        # _balance = self._exchange_manager.get_balance(_exchange)
        # TODO:
        # - we should read the order status of our orders (the bot orders).
        # - store the orders on completed trade if some are closed (raise event?)
        # - call an abstract method next()? that is implemented on child class
        # - how do we inject/instantiate that class from a .yaml...
        # - do we need a "bt.init()" on the derivative class? => maybe not.
        # - how do we get the new orders?
        # - since time frame is in the config we can run the bots/run next only when the last execution - now()
        #    is greater than timeframe
        # - take profit? or freeze a part even reinvesting? =>> No, that's on the Strategy code by the user.
        # - move cash between bots?

        # TODO self._bot_manager.run() ?
        # - save any status

