from elena_sample.model.strategy import Strategy


class TrailingStopLossBBbuyAfterSleep(Strategy):
    # Trailing Stop Loss and Buy always with a sleep

    def __init__(self):
        self.bb_lenght = 5
        self.bb_mult = 5

        self.sleep_by = 0

        self.reinvest = 0
        self.stop_loose_changes = 0
        # self.cash = 1000

