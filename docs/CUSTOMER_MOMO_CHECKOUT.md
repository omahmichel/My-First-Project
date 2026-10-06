# Customer-owned MoMo checkout

New Sale (including an initial MoMo part-payment) creates a Paystack-hosted payment link restricted to mobile_money. Share that link with the customer to open on their own phone. StockFlow's owner-facing authentication endpoint rejects OTP/PIN input. Customers enter any provider-required code directly on Paystack and approve on their phone.

The checkout includes the original sale amount plus the existing 1.3% fee capped at GHS20. Subscription pricing and bank settlement configuration are unchanged. Link creation does not complete a sale. StockFlow verifies reference, amount, currency, channel and Paystack mode before finalization and queues the existing merchant payout once.

## Install and verify

1. Apply the installer from the project root, then run migrations.
2. Run the checkout/authentication tests and frontend build listed by the installer.
3. Restart Django and refresh the frontend on laptop and phone.
4. Before trying payment, use TEST credentials while the Starter Business payout restriction remains unresolved. Never paste keys into chat.
5. Create a fresh MoMo sale, confirm the displayed amount, copy the customer payment link and open it on the customer phone. Use Paystack's test details. The owner must never request a customer's code or PIN.
6. Keep the payment-status modal open: it checks every 15 seconds. Manual Check payment status also works. Verify success completes the sale once and updates stock once.

The clipboard button can fall back to selecting the link on insecure LAN HTTP. Copy it manually if browser clipboard permissions prevent copying. Link sharing is manual; no SMS or WhatsApp message is sent automatically. This version provides a link, not a QR code.

The customer link is hosted by Paystack and is reachable independently of localhost. Production must still provide a public HTTPS webhook URL with signature verification and the existing reservation cleanup job; local polling is not a replacement for webhook setup. Test the layout on laptop and phone after installation.

## Existing and late payments

Historical payment records and the unpaid GHS2 merchant payout are retained. Old direct-charge attempts do not get converted into new charges. Check their status before starting a fresh sale. OTP entry is no longer available through the merchant API.

Hosted checkout may initially appear abandoned while the customer has not opened it. StockFlow retains its reservation until expiry. A link can outlive the local reservation: do not reuse an expired link. If payment is verified after a sale closed, StockFlow records the received funds with gateway_charge_status=requires_review, retains the closed sale, and does not deduct released stock or queue a payout. An operator must review fulfillment/refund; no automatic refund is issued.

This installer does not change credentials, initiate payments, send transfers, configure scheduled jobs or solve Paystack's Starter Business restriction. Merchant payouts still require the appropriate Paystack account approval.
