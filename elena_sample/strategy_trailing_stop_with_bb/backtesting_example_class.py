class Moving_Stop_Loss_BB_buy_After_Sleep(Strategy):
    # Moving Stop Loss and Buy always with a sleep

    bb_lenght = 4320
    bb_mult = 1.5
    intial_sl_factor = 0.9

    sleep_by = 0

    reinvest = 0
    stop_loose_changes = 0
    cash = 1000

    def bbands_formula(self, data):
        # https://greyhoundanalytics.com/blog/custom-indicators-in-backtestingpy/
        bbands = ta.bbands(close=data.Close.s, length=self.bb_lenght, std=self.bb_mult)
        # bbands = ta.kc(high=data.High.s , low=data.Low.s, close = data.Close.s, length=self.bb_lenght, std=self.bb_mult )
        return bbands.to_numpy().T[0:3]

    def calculate_size(self):
        if self.reinvest == 1:
            size = int((self.equity / self.data.Close[-1]) * 0.99)
            # print(f"buy no limit {size} = {self.equity} / {self.data.Close[-1]} ")
        else:
            size = int((self.cash / self.data.Close[-1]) * 0.99)
            # print(f"buy with limit {size} = {self.cash} / {self.data.Close[-1]}")
        return size

    def should_sleep(self):
        if len(self.closed_trades) > 0:
            last_trade_exit_time = self.closed_trades[-1].exit_time
            # print('last_trade_exit_time',last_trade_exit_time)

            current_time_stamp = self.data.index[-1]
            # print('current_time_stamp',current_time_stamp)

            time_stamp_difference = (current_time_stamp - last_trade_exit_time).total_seconds() / 60
            # print('time_stamp_difference',time_stamp_difference)

            sleep = (time_stamp_difference < self.sleep_by)
            # print('sleep',sleep)

            return sleep
        else:
            return False  # if no trades no sleeps

    def init(self):
        # self.min_candel = self.I(self.MinCandel, self.data.Low, int(self.stop_min))
        self.bbands = self.I(self.bbands_formula, self.data)
        # self.lr_buy = self.I(self.LR, self.data)
        self.current_stop_loss = 0
        self.cash = self.equity

    def next(self):
        lower_band = self.bbands[0]
        upper_band = self.bbands[2]

        new_stop = lower_band[-1]

        if not self.position:
            if not self.should_sleep():
                self.current_stop_loss = new_stop * self.intial_sl_factor
                size = self.calculate_size()
                self.buy(size=size, sl=self.current_stop_loss)
                self.sleep_by = random.random() * 7 * 24 * 60

        elif new_stop > self.current_stop_loss and new_stop > self.trades[0].entry_price * 1.001:
            old_stop = self.trades[0].sl
            self.trades[0].sl = new_stop
            self.current_stop_loss = new_stop
            self.stop_loose_changes = self.stop_loose_changes + 1
            # print(f"I'm recreating the stop loss {old_stop}, new: {new_stop}. Entry price {self.trades[0].entry_price}")