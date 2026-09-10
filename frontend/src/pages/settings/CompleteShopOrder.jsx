import { useEffect, useRef, useState } from 'react';
import { useStore } from '../../context/StoreContext';
import { apiRequest } from '../../services/api';
import { shopMoney } from '../../services/storefront';

export default function CompleteShopOrder({ businessId, order, disabled, onBusy, onCompleted }) {
  const store = useStore();
  const loaders = useRef(store);
  loaders.current = store;
  const [customerId, setCustomerId] = useState('');
  const [amount, setAmount] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [locked, setLocked] = useState(false);
  const [error, setError] = useState('');
  const attempt = useRef(null);
  const sending = useRef(false);
  const customers = store.customers.filter(customer => String(customer.businessId) === String(businessId) && customer.status !== 'inactive');
  useEffect(() => {
    let active = true;
    Promise.resolve(loaders.current.loadCustomers(businessId)).catch(problem => { if (active) setError(problem.message); });
    return () => { active = false; };
  }, [businessId]);

  async function submit(event) {
    event.preventDefault();
    if (sending.current || disabled) return;
    if (!attempt.current) {
      if (!confirmed) { setError('Confirm cash receipt.'); return; }
      if (Math.round(Number(amount) * 100) !== Math.round(Number(order.total) * 100)) { setError('Enter the exact order total received.'); return; }
      attempt.current = { cashReceived: true, amountReceived: amount };
    }
    sending.current = true;
    setBusy(true);
    setLocked(true);
    onBusy(order.orderId);
    setError('');
    try {
      const result = await apiRequest('/businesses/' + businessId + '/storefront/orders/' + order.orderId + '/complete/', { method: 'POST', body: JSON.stringify(attempt.current) });
      attempt.current = null;
      setLocked(false);
      onBusy('');
      onCompleted(result);
      const current = loaders.current;
      Promise.allSettled([
        Promise.resolve().then(() => current.loadInventory(businessId, current.activeBranchId)),
        Promise.resolve().then(() => current.loadCustomers(businessId)),
        Promise.resolve().then(() => current.loadSales(businessId, current.activeBranchId)),
      ]);
    } catch (problem) {
      if ([400, 401, 403, 404, 405, 415, 429].includes(problem.status)) {
        attempt.current = null;
        setLocked(false);
        onBusy('');
        setError(problem.message);
      } else {
        setError('The result is uncertain. Keep this page open and retry the same completion. Do not record a separate sale.');
      }
    } finally { sending.current = false; setBusy(false); }
  }

  return <form className='sf-shop-complete' onSubmit={submit}>
    <h4>Complete cash sale</h4>
    <p>This records {shopMoney(order.total)} as received, deducts the ordered stock and creates an invoice and receipt.</p>
    <fieldset disabled={disabled || locked || busy}>
      <p>Buyer: <strong>{order.customerName}</strong> — {order.customerPhone}</p>
      <p>StockFlow matches or creates the customer account from this order. Conflicting customer details require review.</p>
      <label>Cash amount received (GHS)<input required type='number' min='0.01' step='0.01' value={amount} onChange={event => setAmount(event.target.value)} /></label>
      <label className='sf-shop-toggle'><input required type='checkbox' checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />I confirm the full cash payment has been received.</label>
    </fieldset>
    {error && <p role='alert'>{error}</p>}
    <button type='submit' disabled={busy || disabled}>{busy ? 'Completing...' : locked ? 'Retry same completion' : 'Complete cash sale'}</button>
  </form>;
}
