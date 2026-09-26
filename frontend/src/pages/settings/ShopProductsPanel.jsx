import NotificationRefresh from "../../components/notifications/NotificationRefresh";
import { useEffect, useRef, useState } from 'react';
import { useStore } from '../../context/StoreContext';
import { apiRequest } from '../../services/api';

export default function ShopProductsPanel({ businessId }) {
  const { products, inventoryLoading, inventoryError, loadInventory, activeBranchId } = useStore();
  const [listings, setListings] = useState([]);
  const [selected, setSelected] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const base = '/businesses/' + businessId + '/storefront/listings/';
  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError('');
      try {
        const rows = [];
        let page = 1;
        let more = true;
        while (more && active) {
          const result = await apiRequest(base + '?page=' + page);
          rows.push(...result.results);
          more = Boolean(result.next);
          page += 1;
        }
        if (active) setListings(rows);
      } catch (problem) { if (active) setError(problem.message); }
      finally { if (active) setLoading(false); }
    }
    load();
    return () => { active = false; };
  }, [base, retry]);

  const choices = new Map();
  listings.forEach(row => choices.set(String(row.productId), { id: String(row.productId), name: row.name, sku: row.sku, hasVideo: false }));
  products.forEach(row => choices.set(String(row.id), { id: String(row.id), name: row.name, sku: row.sku, hasVideo: Boolean(row.hasVideo) }));
  const options = [...choices.values()].sort((a, b) => a.name.localeCompare(b.name));
  const listing = listings.find(row => String(row.productId) === selected);
  const selectedProduct = choices.get(selected);

  return <section id='sf-shop-products' aria-labelledby='sf-shop-products-title' className='sf-shop-cart sf-shop-card-section'>
    <header className='sf-shop-section-heading'><span>03</span><div><h2 id='sf-shop-products-title'>Product catalogue</h2><p>Prepare listings and choose which products customers can see.</p></div></header>
    <p>Choose an inventory product and save its public listing. Publishing a product makes it visible when the shop is also published.</p>
    <p>Inventory choices follow your selected workspace branch. Existing shop listings are included too.</p>
    {inventoryLoading && <p role='status'>Loading inventory...</p>}
    {inventoryError && <p role='alert'>{String(inventoryError)}</p>}
    <NotificationRefresh><button type='button' disabled={inventoryLoading} onClick={() => { Promise.resolve(loadInventory(businessId, activeBranchId)).catch(problem => setError(problem.message)); }}>Refresh inventory choices</button></NotificationRefresh>
    {loading ? <p role='status'>Loading published and draft listings...</p> : error ? <div role='alert'><p>{error}</p><button type='button' onClick={() => setRetry(value => value + 1)}>Retry</button></div> : <>
      <p className='sf-shop-count-badge'>{listings.filter(row => row.isPublished).length} published listings · {listings.length} saved listings</p>
      <label>Choose a product<select value={selected} onChange={event => setSelected(event.target.value)}><option value=''>Select an inventory product</option>{options.map(product => <option key={product.id} value={product.id}>{product.name} — {product.sku}</option>)}</select></label>
      {!options.length && <p>Add products in All products, then refresh the inventory choices here.</p>}
      {selected && <ListingEditor key={selected} base={base} businessId={businessId} branchId={activeBranchId} productId={selected} product={selectedProduct} listing={listing} onSaved={result => setListings(rows => [...rows.filter(row => row.productId !== result.productId), result])} />}
    </>}
  </section>;
}

function ListingEditor({ base, businessId, branchId, productId, product, listing, onSaved }) {
  const [description, setDescription] = useState(listing?.description || '');
  const [imageUrl, setImageUrl] = useState(listing?.imageUrl || '');
  const [published, setPublished] = useState(listing?.isPublished || false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  async function save(event) {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const result = await apiRequest(base + productId + '/', { method: 'PUT', body: JSON.stringify({ description, imageUrl: imageUrl.trim(), isPublished: published }) });
      onSaved(result);
      setDescription(result.description);
      setImageUrl(result.imageUrl);
      setPublished(result.isPublished);
      setMessage(result.isPublished ? 'Product listing published.' : 'Product listing saved and hidden from the public catalogue.');
    } catch (problem) { setError(problem.message); }
    finally { setSaving(false); }
  }
  return <form className='sf-shop-listing-editor' onSubmit={save}>
    <fieldset disabled={saving}>
      <label>Public description<textarea rows={4} maxLength={2000} value={description} onChange={event => setDescription(event.target.value)} /></label>
      <label>Product image URL (optional)<input type='url' placeholder='https://example.com/product.jpg' maxLength={1000} value={imageUrl} onChange={event => setImageUrl(event.target.value)} /></label>
      <p>Use an HTTPS image link that customers can open. Prices come from your inventory product.</p>
      <SocialVideoControl businessId={businessId} branchId={branchId} productId={productId} initialHasVideo={Boolean(product?.hasVideo)} />
      <label className='sf-shop-toggle'><input type='checkbox' checked={published} onChange={event => setPublished(event.target.checked)} />Publish this product</label>
      <button type='submit'>{saving ? 'Saving listing...' : 'Save product listing'}</button>
    </fieldset>
    {error && <p role='alert'>{error}</p>}
    {message && <p role='status'>{message}</p>}
  </form>;
}


function SocialVideoControl({ businessId, branchId, productId, initialHasVideo }) {
  const { loadInventory } = useStore();
  const inputRef = useRef(null);
  const [hasVideo, setHasVideo] = useState(initialHasVideo);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const url = '/businesses/' + businessId + '/products/' + productId + '/video/';

  async function upload(event) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file || busy) return;
    setError('');
    setMessage('');
    if (file.size > 100 * 1024 * 1024) {
      setError('Choose a video no larger than 100 MB.');
      return;
    }
    setBusy(true);
    try {
      const form = new FormData();
      form.append('video', file);
      if (branchId) form.append('branchId', branchId);
      await apiRequest(url, { method: 'POST', body: form });
      setHasVideo(true);
      Promise.resolve(loadInventory(businessId, branchId)).catch(() => {});
      setMessage('Social video saved. Facebook and Instagram will publish this product as a Reel instead of a photo.');
    } catch (problem) {
      setError(problem.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (busy) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const suffix = branchId ? '?branchId=' + encodeURIComponent(branchId) : '';
      await apiRequest(url + suffix, { method: 'DELETE' });
      setHasVideo(false);
      Promise.resolve(loadInventory(businessId, branchId)).catch(() => {});
      setMessage('Social video removed. Facebook and Instagram will use the product photo again.');
    } catch (problem) {
      setError(problem.message);
    } finally {
      setBusy(false);
    }
  }

  return <div style={{ margin: '14px 0', padding: '14px', border: '1px solid #dfe8e6', borderRadius: '12px' }}>
    <strong>Social video {hasVideo ? '— uploaded' : ''}</strong>
    <p style={{ margin: '7px 0' }}>Optional. Use a vertical 9:16 MP4 or MOV, ideally H.264/AAC and 4–60 seconds. StockFlow uses it for Facebook and Instagram Reels; it does not replace the public shop photo.</p>
    <input ref={inputRef} type='file' accept='video/mp4,video/quicktime,.mp4,.mov' hidden onChange={upload} />
    <div className='sf-shop-admin-actions'>
      <button type='button' disabled={busy} onClick={() => inputRef.current?.click()}>{busy ? 'Working...' : hasVideo ? 'Replace social video' : 'Upload social video'}</button>
      {hasVideo && <button type='button' disabled={busy} onClick={remove}>Remove social video</button>}
    </div>
    {error && <p role='alert'>{error}</p>}
    {message && <p role='status'>{message}</p>}
  </div>;
}
