from abc import ABC, abstractmethod


class BaseInvoiceParser(ABC):
    @abstractmethod
    def parse(self, text):
        pass