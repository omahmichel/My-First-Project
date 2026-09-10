import { useEffect, useState } from 'react';
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
  listings.forEach(row => choices.set(String(row.productId), { id: String(row.productId), name: row.name, sku: row.sku }));
  products.forEach(row => choices.set(String(row.id), { id: String(row.id), name: row.name, sku: row.sku }));
  const options = [...choices.values()].sort((a, b) => a.name.localeCompare(b.name));
  const listing = listings.find(row => String(row.productId) === selected);

  return <section className='sf-shop-cart'>
    <h2>Products in your online shop</h2>
    <p>Choose an inventory product and save its public listing. Publishing a product makes it visible when the shop is also published.</p>
    <p>Inventory choices follow your selected workspace branch. Existing shop listings are included too.</p>
    {inventoryLoading && <p role='status'>Loading inventory...</p>}
    {inventoryError && <p role='alert'>{String(inventoryError)}</p>}
    <button type='button' disabled={inventoryLoading} onClick={() => { Promise.resolve(loadInventory(businessId, activeBranchId)).catch(problem => setError(problem.message)); }}>Refresh inventory choices</button>
    {loading ? <p role='status'>Loading published and draft listings...</p> : error ? <div role='alert'><p>{error}</p><button type='button' onClick={() => setRetry(value => value + 1)}>Retry</button></div> : <>
      <p>{listings.filter(row => row.isPublished).length} published listings · {listings.length} saved listings</p>
      <label>Choose a product<select value={selected} onChange={event => setSelected(event.target.value)}><option value=''>Select an inventory product</option>{options.map(product => <option key={product.id} value={product.id}>{product.name} — {product.sku}</option>)}</select></label>
      {!options.length && <p>Add products in All products, then refresh the inventory choices here.</p>}
      {selected && <ListingEditor key={selected} base={base} productId={selected} listing={listing} onSaved={result => setListings(rows => [...rows.filter(row => row.productId !== result.productId), result])} />}
    </>}
  </section>;
}

function ListingEditor({ base, productId, listing, onSaved }) {
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
  return <form onSubmit={save}>
    <fieldset disabled={saving}>
      <label>Public description<textarea rows={4} maxLength={2000} value={description} onChange={event => setDescription(event.target.value)} /></label>
      <label>Product image URL (optional)<input type='url' placeholder='https://example.com/product.jpg' maxLength={1000} value={imageUrl} onChange={event => setImageUrl(event.target.value)} /></label>
      <p>Use an HTTPS image link that customers can open. Prices come from your inventory product.</p>
      <label className='sf-shop-toggle'><input type='checkbox' checked={published} onChange={event => setPublished(event.target.checked)} />Publish this product</label>
      <button type='submit'>{saving ? 'Saving listing...' : 'Save product listing'}</button>
    </fieldset>
    {error && <p role='alert'>{error}</p>}
    {message && <p role='status'>{message}</p>}
  </form>;
}
