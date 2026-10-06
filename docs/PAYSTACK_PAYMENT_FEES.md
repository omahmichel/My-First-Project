# StockFlow payment fees

Agreed 30 September 2026:
- StockFlow subscriptions: add 2.5% to the subscription price. The current GHS 150 / 40-day plan totals GHS 153.75.
- Customer Paystack Mobile Money payments: add 1.3% to the amount being paid, capped at GHS 20 per payment. GHS 100 totals GHS 101.30; GHS 220 totals GHS 222.86.
- Each business is owed its full original payment amount. The surcharge is not sales income, invoice credit, or a deduction from the merchant payout.
- Cash and manually recorded bank transfers have no new StockFlow surcharge.

## Implementation
The backend owns the rates and rounds the surcharge to pesewas using decimal ROUND_HALF_UP. Each new gateway payment stores its fee percentage and fee amount. Verification compares Paystack's reference, gross amount, currency and other existing validation fields before granting value. A repeated request reuses its original payment rather than adding another surcharge.

SubscriptionPayment.amount remains the base price; amount_subunit is the full amount charged. Payment.amount remains the amount credited to the sale/debt and owed to the merchant. charged_amount is the base plus the stored surcharge. API responses expose feePercent, feeAmount and chargedAmount.

The migrations give older records zero fee. Existing pending payments must still verify at their originally requested amount; paid records are not repriced. Main forms show the base price only. A final confirmation dialog shows the fee and gross total before starting checkout or a Mobile Money prompt. The subscription dialog obtains its quote from the backend without creating a payment or contacting Paystack. The pending-payment dialog uses stored server amounts.

The current UI offers Paystack Mobile Money for New Sale. Existing backend debt-payment endpoints also apply the 1.3% fee, but this update does not enable the currently disabled debt-payment UI or introduce a new public-shop checkout.

## Receiving accounts and live verification
The existing Paystack client uses PAYMENT_GATEWAY_SECRET_KEY on the backend. Subscription payments use that Paystack account's settlement destination: configure and verify the StockFlow/developer receiving bank account or wallet in Paystack. This update does not set, inspect, or change the actual destination in Paystack.

Merchant payouts use the business's active default Mobile Money receiving account and its Paystack recipient. Confirm the correct masked number, owner and network in business payment settings and its connection status. Merely saving an account is not proof that a transfer has succeeded. The existing payout worker and signed transfer webhooks complete the payout lifecycle. This implementation does not add bank-account merchant payouts or split settlement.

Paystack's published Ghana processing price checked on 30 September 2026 is 1.95% of the gross collected amount. Separate transfers are priced separately (GHS 1 to Mobile Money; GHS 8 to bank accounts). Therefore a 1.3% customer surcharge is less than the processing fee even before this code's separate payout cost. The cap can increase StockFlow's shortfall on large payments. StockFlow must fund the processing shortfall, transfer balance and those additional costs; do not subtract them from the business's proceeds or silently increase the customer's rate. Automatic settlements and API transfers are different operations.

Before live use:
1. Apply migrations, run the listed tests and frontend build, then restart Django.
2. Test a subscription and a Mobile Money sale in Paystack test mode; check exact base, fee and gross amounts on laptop and phone.
3. Confirm invalid amount verification fails and retries do not duplicate value.
4. Confirm the business payout equals the base amount and the transfer reaches the intended account.
5. Confirm the StockFlow settlement destination, funded transfer balance, worker scheduling and externally reachable signed webhook endpoint. A local LAN URL cannot receive provider webhooks from the internet.
6. Confirm Paystack is not independently passing processing fees on top of the already increased charge.

No live charges or transfers were initiated during development. Do not share secret keys or full account details in chat.

Sources:
- https://paystack.com/gh/pricing
- https://paystack.com/docs/api/charge/
- https://paystack.com/docs/payments/split-payments/
