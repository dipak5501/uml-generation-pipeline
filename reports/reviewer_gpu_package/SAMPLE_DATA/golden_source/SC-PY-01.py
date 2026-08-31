from dataclasses import dataclass, field
from typing import List
from datetime import date

@dataclass
class Book:
    isbn: str
    title: str
    author: str
    available: bool = True

    def mark_borrowed(self) -> None:
        self.available = False

class Member:
    def __init__(self, member_id: int, name: str, email: str):
        self.member_id = member_id
        self.name = name
        self.email = email
        self._loans: List[Loan] = []

    def borrow(self, book: Book) -> Loan:
        if not book.available:
            raise ValueError("book not available")
        book.mark_borrowed()
        loan = Loan(len(self._loans) + 1, book, self, date.today())
        self._loans.append(loan)
        return loan

class Loan:
    def __init__(self, loan_id: int, book: Book, member: Member, start: date):
        self.loan_id = loan_id
        self.book = book
        self.member = member
        self.start = start

    def is_overdue(self, today: date) -> bool:
        return (today - self.start).days > 14
