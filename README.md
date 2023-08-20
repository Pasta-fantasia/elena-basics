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


# Installation for first testing

(venv) elena2@localhost:~$ history 

    8  python3 -m venv venv
    9  source ~/venv/bin/activate
   10  echo "source ~/venv/bin/activate" >> .bashrc

   12  git clone git@github.com:Pasta-fantasia/elena.git
   13  cd elena/
   14  git fetch origin
   15  git branch -a
   16  git switch feature/TODOs
   17  git pull
   18  git config pull.rebase false
   20  pip install -e .
   21  cd ..
   22  git clone git@github.com:Pasta-fantasia/elena-sample.git
   23  cd elena-sample/
   24  pip install -e .
   25  cd
   26  echo "export ELENA_HOME=/......./L_working" >> .bashrc

   30  mkdir /......./L_working
   31  elena
   32  cp elena-sample/local_data/elena_config_example.yaml L_working/elena_config.yaml
   37  joe elena_config.yaml 

   33  joe cron.sh
   34  chmod a+x cron.sh 
   35  crontab -e


