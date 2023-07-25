from abc import abstractmethod

import pandas as pd


class Strategy:

    def __repr__(self):
        return '<Strategy ' + str(self) + '>'

    def __str__(self):
        attrs = vars(self)  # Obtiene el diccionario de atributos de la instancia
        attributes_str = ",".join(f"{key}={value}" for key, value in attrs.items())
        return f"{self.__class__.__name__}({attributes_str})"

    def __init__(self):
        self.data = pd.DataFrame

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
