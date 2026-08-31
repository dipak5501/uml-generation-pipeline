package com.example.library;

import java.util.Date;
import java.util.List;

public class Book {
    private String isbn;
    private String title;
    private String author;
    private boolean available;

    public Book(String isbn, String title, String author) {
        this.isbn = isbn;
        this.title = title;
        this.author = author;
        this.available = true;
    }

    public String getTitle() { return title; }
    public boolean isAvailable() { return available; }
    public void markBorrowed() { this.available = false; }
}

public interface Borrowable {
    boolean isAvailable();
    void markBorrowed();
}

public class Member {
    private int memberId;
    private String name;
    private String email;
    private List<Loan> activeLoans;

    public Member(int memberId, String name, String email) {
        this.memberId = memberId;
        this.name = name;
        this.email = email;
    }

    public void borrowBook(Book book) {
        if (book.isAvailable()) {
            book.markBorrowed();
        }
    }
}

public class Loan {
    private int loanId;
    private Book book;
    private Member member;
    private Date dueDate;

    public Loan(int loanId, Book book, Member member, Date dueDate) {
        this.loanId = loanId;
        this.book = book;
        this.member = member;
        this.dueDate = dueDate;
    }
}

public class Librarian extends Member {
    private String deskLocation;

    public Librarian(int memberId, String name, String email, String deskLocation) {
        super(memberId, name, email);
        this.deskLocation = deskLocation;
    }

    public void processLoan(Loan loan) {
        // approve loan
    }
}
