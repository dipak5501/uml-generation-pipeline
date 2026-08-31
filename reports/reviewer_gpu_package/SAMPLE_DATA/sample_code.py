"""Sample source code for code → UML demos."""

class User:
    def __init__(self, user_id: int, email: str):
        self.user_id = user_id
        self.email = email

    def authenticate(self, password: str) -> bool:
        return bool(password)


class Order:
    def __init__(self, order_id: int, user: User):
        self.order_id = order_id
        self.user = user
        self.items = []

    def add_item(self, item: "OrderItem") -> None:
        self.items.append(item)

    def total(self) -> float:
        return sum(i.price for i in self.items)


class OrderItem:
    def __init__(self, sku: str, price: float):
        self.sku = sku
        self.price = price


class PaymentService:
    def charge(self, order: Order, amount: float) -> bool:
        return amount > 0 and order.user is not None


def checkout(user: User, items: list) -> Order:
    order = Order(1, user)
    for item in items:
        order.add_item(item)
    ok = PaymentService().charge(order, order.total())
    if not ok:
        raise RuntimeError("payment failed")
    return order
