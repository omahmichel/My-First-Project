import { useEffect, useRef, useState } from 'react';
import { publicShopRequest, shopMoney } from '../../services/storefront';


function CartQuantity({ item, onQuantity }) {
  const [draft, setDraft] = useState(String(item.quantity));
  const editing = useRef(false);
  const maximum = Math.min(item.availableQuantity, 10000);

  useEffect(() => {
    if (!editing.current) setDraft(String(item.quantity));
  }, [item.quantity]);

  function change(value) {
    setDraft(value);
    const number = Number(value);
    if (value.trim() && Number.isInteger(number) && number >= 1 && number <= maximum) {
      onQuantity(item.productId, number);
    }
  }

  function finish() {
    editing.current = false;
    const number = Number(draft);
    const next = draft.trim() && Number.isInteger(number) && number >= 1
      ? Math.min(number, maximum)
      : item.quantity;
    setDraft(String(next));
    onQuantity(item.productId, next);
  }

  return <label>Quantity<input type='number' inputMode='numeric' required
    aria-label={'Quantity for ' + item.name}
    min='1' max={maximum} step='1' value={draft}
    onFocus={() => { editing.current = true; }}
    onChange={event => change(event.target.value)}
    onBlur={finish} /></label>;
}

export default function ShopCart({ slug, cart, setCart, locked, setLocked }) {
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [receipt, setReceipt] = useState(null);
  const attempt = useRef(null);
  const sending = useRef(false);
  const total = cart.reduce((sum, item) => sum + Math.round(Number(item.price) * 100) * item.quantity, 0) / 100;

  function quantity(productId, value) {
    const number = Number(value);
    if (!Number.isInteger(number) || number < 1) return;
    setCart(rows => rows.map(item => item.productId === productId ? { ...item, quantity: Math.min(number, item.availableQuantity, 10000) } : item));
  }

  async function submit(event) {
    event.preventDefault();
    if (sending.current) return;
    sending.current = true;
    setBusy(true);
    setError('');
    try {
      if (!attempt.current) {
        attempt.current = {
          idempotencyKey: crypto.randomUUID(),
          customerName: name.trim(),
          customerPhone: phone.trim(),
          customerNote: note.trim(),
          items: cart.map(item => ({ productId: item.productId, quantity: item.quantity })),
        };
      }
      setLocked(true);
      const result = await publicShopRequest(slug, 'orders/', { method: 'POST', body: JSON.stringify(attempt.current) });
      setReceipt(result);
      setCart([]);
      setName('');
      setPhone('');
      setNote('');
      attempt.current = null;
      setLocked(false);
    } catch (problem) {
      const rejected = [400, 401, 403, 404, 405, 415, 429].includes(problem.status);
      if (rejected || !attempt.current) {
        attempt.current = null;
        setLocked(false);
        setError(problem.message);
      } else {
        setError('We could not confirm the result. Keep this page open and retry the same order to avoid a duplicate.');
      }
    } finally {
      sending.current = false;
      setBusy(false);
    }
  }

  return <section className='sf-shop-cart' aria-label='Your order'>
    {receipt && <div className='sf-shop-confirmation' role='status'><h2>Order received</h2><p>Reference: {receipt.orderId}</p><p>Total: {shopMoney(receipt.total)}</p><p>The shop will review your request. No payment has been collected and stock is not reserved.</p></div>}
    <h2>Your cart ({cart.reduce((sum, item) => sum + item.quantity, 0)})</h2>
    {!cart.length ? <p>Add products to prepare an order.</p> : <form onSubmit={submit}>
      <fieldset disabled={locked || busy}>
        {cart.map(item => <div className='sf-shop-cart-line' key={item.productId}>
          <div><strong>{item.name}</strong><p>{shopMoney(item.price)} / {item.unit}</p></div>
          <div className='sf-shop-cart-actions'>
            <CartQuantity item={item} onQuantity={quantity} />
            <button type='button' onClick={() => setCart(rows => rows.filter(row => row.productId !== item.productId))}>Remove</button>
          </div>
        </div>)}
        <p><strong>Estimated total: {shopMoney(total)}</strong></p>
        <p>The shop confirms availability. The final order total uses current shop prices.</p>
        <label>Your name<input required maxLength={180} autoComplete='name' value={name} onChange={event => setName(event.target.value)} /></label>
        <label>Contact phone<input required type='tel' maxLength={30} autoComplete='tel' value={phone} onChange={event => setPhone(event.target.value)} /></label>
        <label>Note for the shop (optional)<textarea maxLength={1000} rows={3} value={note} onChange={event => setNote(event.target.value)} /></label>
        <p>Your name, phone number and note will be shared with this shop to handle your order.</p>
      </fieldset>
      {error && <p role='alert'>{error}</p>}
      <button type='submit' disabled={busy}>{busy ? 'Submitting...' : locked ? 'Retry same order' : 'Send order for review'}</button>
    </form>}
  </section>;
}
