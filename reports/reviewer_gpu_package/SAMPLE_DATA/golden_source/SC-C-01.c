#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct Book {
    char isbn[20];
    char title[128];
    char author[64];
    int available;
} Book;

typedef struct Member {
    int member_id;
    char name[64];
    char email[96];
} Member;

typedef struct Loan {
    int loan_id;
    Book* book;
    Member* member;
    char due_date[16];
} Loan;

Book* book_create(const char* isbn, const char* title, const char* author) {
    Book* b = (Book*)malloc(sizeof(Book));
    strcpy(b->isbn, isbn);
    strcpy(b->title, title);
    strcpy(b->author, author);
    b->available = 1;
    return b;
}

void book_mark_borrowed(Book* book) {
    if (book) book->available = 0;
}

Loan* loan_create(int loan_id, Book* book, Member* member, const char* due) {
    Loan* loan = (Loan*)malloc(sizeof(Loan));
    loan->loan_id = loan_id;
    loan->book = book;
    loan->member = member;
    strcpy(loan->due_date, due);
    return loan;
}
