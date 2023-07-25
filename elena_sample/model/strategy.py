
class Strategy:

    @abstractmethod
    def init(self):
        """
        Initialize the strategy.
        Override this method.
        """
    @abstractmethod
    def next(self):
        """
         Main strategy runtime method, called as each new run
         """

    def order_buy(self):
        pass

    def order_sell(self):
        pass

    def order_stop_loss(self):
        pass
    @property
    def equity(self) -> float:
        """
        Current value = assets(BTC) * price + cash
        :return:
        """
        pass

    @property
    def cash(self) -> float:
        """
        Available cash to buy assets
        :return:
        """
        pass


