import CompleteShopOrder from './CompleteShopOrder';
import { useEffect, useState } from 'react';
import { apiRequest } from '../../services/api';
import { shopMoney } from '../../services/storefront';

export default function ShopOrdersPanel({ businessId, branches }) {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState('pending');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState('');
  const [retry, setRetry] = useState(0);
  const base = '/businesses/' + businessId + '/storefront/orders/';
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    apiRequest(base + '?status=' + status + '&page=' + page)
      .then(result => { if (active) setData(result); })
      .catch(problem => { if (active) setError(problem.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [base, status, page, retry]);

  async function cancel(order) {
    if (busy || !window.confirm('Cancel this pending order from ' + order.customerName + '? Stock and payments will remain unchanged.')) return;
    setBusy(order.orderId);
    setError('');
    setMessage('');
    try {
      await apiRequest(base + order.orderId + '/cancel/', { method: 'POST', body: JSON.stringify({}) });
      setMessage('Order cancelled.');
      setPage(1);
      setRetry(value => value + 1);
    } catch (problem) { setError(problem.message); }
    finally { setBusy(''); }
  }

  return <section className='sf-shop-cart'>
    <h2>Online orders</h2>
    <p>Review customer requests before arranging payment and fulfilment.</p>
    <label>Order status<select disabled={Boolean(busy)} value={status} onChange={event => { setStatus(event.target.value); setPage(1); setMessage(''); }}><option value='pending'>Pending review</option><option value='completed'>Completed</option><option value='cancelled'>Cancelled</option></select></label>
    <button type='button' disabled={loading || Boolean(busy)} onClick={() => setRetry(value => value + 1)}>Refresh orders</button>
    {message && <p role='status'>{message}</p>}
    {error && <p role='alert'>{error}</p>}
    {loading ? <p role='status'>Loading orders...</p> : !error && <>
      <p>{data?.count || 0} orders</p>
      {data?.results.map(order => <article className='sf-shop-order' key={order.orderId}>
        <h3>{order.customerName} — {shopMoney(order.total)}</h3>
        <p>Reference: {order.orderId}</p>
        <p>Received: {new Date(order.createdAt).toLocaleString()}</p>
        <p>Phone: {order.customerPhone}</p>
        <p>Fulfilment branch: {branches.find(branch => String(branch.id) === order.branchId)?.name || 'Original order branch'}</p>
        <p>Status: {order.status}</p>
        {order.customerNote && <p className='sf-shop-order-note'>Customer note: {order.customerNote}</p>}
        <ul>{order.items.map(item => <li key={item.productId}>{item.name} — {item.quantity} {item.unit}(s) at {shopMoney(item.unitPrice)} each: <strong>{shopMoney(item.total)}</strong></li>)}</ul>
        {order.status === 'pending' && <><p>This request has not yet been recorded as a completed sale.</p><button type='button' disabled={Boolean(busy)} onClick={() => cancel(order)}>{busy === order.orderId ? 'Cancelling...' : 'Cancel order'}</button></>}
        {order.status === 'pending' && <CompleteShopOrder businessId={businessId} order={order} disabled={Boolean(busy) && busy !== order.orderId} onBusy={setBusy} onCompleted={result => { setMessage('Sale completed. Invoice: ' + result.invoiceNumber + ' | Receipt: ' + result.receiptNumber); setPage(1); setRetry(value => value + 1); }} />}
      </article>)}
      <div className='sf-shop-pagination'><button type='button' disabled={!data?.previous || Boolean(busy)} onClick={() => setPage(value => Math.max(1, value - 1))}>Previous</button><span>Page {page}</span><button type='button' disabled={!data?.next || Boolean(busy)} onClick={() => setPage(value => value + 1)}>Next</button></div>
    </>}
  </section>;
}
