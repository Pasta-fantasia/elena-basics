from elena_sample.model.strategy import Strategy


class TrailingStopLossBBbuyAfterSleep(Strategy):
    # Trailing Stop Loss and Buy always with a sleep

    def __init__(self):
        self.bb_length = 5
        self.bb_mult = 2

        self.sleep_by = 0

        self.reinvest = 0
        self.stop_loose_changes = 0
        # read-only self.cash = 1000

