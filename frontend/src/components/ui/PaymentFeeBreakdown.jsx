import { formatCurrency } from "../../utils/formatters";

export function feeQuote(amount, percent, maxFee) {
  const base = Math.round((Number(amount) || 0) * 100);
  const percentageFee = Math.floor((base * Math.round(percent * 100) + 5000) / 10000);
  const fee = maxFee == null ? percentageFee : Math.min(percentageFee, Math.round(maxFee * 100));
  return { amount: base / 100, fee: fee / 100, total: (base + fee) / 100 };
}

export default function PaymentFeeBreakdown({ amount, percent, feeAmount, chargedAmount, maxFee }) {
  const quote = feeQuote(amount, percent, maxFee);
  return <div className="payment-fee-breakdown" aria-label="Payment breakdown">
    <div><span>Original amount</span><strong>{formatCurrency(amount)}</strong></div>
    <div><span>Processing charge ({Number(percent)}%{maxFee != null ? `, maximum ${formatCurrency(maxFee)}` : ""})</span><strong>{formatCurrency(feeAmount ?? quote.fee)}</strong></div>
    <div><span>Total to approve</span><strong>{formatCurrency(chargedAmount ?? quote.total)}</strong></div>
  </div>;
}
