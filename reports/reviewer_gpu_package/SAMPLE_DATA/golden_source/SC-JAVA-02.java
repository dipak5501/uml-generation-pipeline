package com.example.payments;

public interface PaymentProcessor {
    boolean authorize(double amount, String currency);
    String capture(String authorizationId);
    void refund(String transactionId, double amount);
}

public class CreditCardProcessor implements PaymentProcessor {
    private String merchantId;
    private String apiKey;

    public CreditCardProcessor(String merchantId, String apiKey) {
        this.merchantId = merchantId;
        this.apiKey = apiKey;
    }

    @Override
    public boolean authorize(double amount, String currency) {
        return amount > 0;
    }

    @Override
    public String capture(String authorizationId) {
        return "txn-cc-" + authorizationId;
    }

    @Override
    public void refund(String transactionId, double amount) {
        // refund via card network
    }
}

public class PayPalProcessor implements PaymentProcessor {
    private String clientId;
    private String secret;

    public PayPalProcessor(String clientId, String secret) {
        this.clientId = clientId;
        this.secret = secret;
    }

    @Override
    public boolean authorize(double amount, String currency) {
        return amount <= 10000;
    }

    @Override
    public String capture(String authorizationId) {
        return "txn-pp-" + authorizationId;
    }

    @Override
    public void refund(String transactionId, double amount) {
        // refund via PayPal API
    }
}
