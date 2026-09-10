import ShopCart from './ShopCart';
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { publicShopRequest, shopMoney } from '../../services/storefront';
import '../../styles/storefront.css';

export default function ShopPage() {
  const { slug } = useParams();
  return <ShopCatalogue key={slug} slug={slug} />;
}

function ShopCatalogue({ slug }) {
  const [data, setData] = useState(null);
  const [draft, setDraft] = useState('');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const [cart, setCart] = useState([]);
  const [cartLocked, setCartLocked] = useState(false);
  const [cartMessage, setCartMessage] = useState('');
  function addToCart(product) {
    if (cartLocked || !product.inStock) return;
    const existing = cart.find(item => item.productId === product.productId);
    if (!existing && cart.length >= 50) { setCartMessage('You can order up to 50 different products at once.'); return; }
    if (existing && existing.quantity >= Math.min(product.availableQuantity, 10000)) { setCartMessage('You have reached the available quantity for this product.'); return; }
    setCart(rows => existing ? rows.map(item => item.productId === product.productId ? { ...product, quantity: item.quantity + 1 } : item) : [...rows, { ...product, quantity: 1 }]);
    setCartMessage(product.name + ' added to your cart.');
  }

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    const params = new URLSearchParams({ q: query, page: String(page) });
    publicShopRequest(slug, '?' + params.toString(), { signal: controller.signal })
      .then(result => { if (!controller.signal.aborted) setData(result); })
      .catch(problem => { if (!controller.signal.aborted) setError(problem.status === 404 ? 'This shop or catalogue page is unavailable.' : problem.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [slug, query, page, retry]);

  function search(event) {
    event.preventDefault();
    setPage(1);
    setQuery(draft.trim());
  }

  return <main className='sf-shop'>
    <nav className='sf-shop-nav'><Link to='/'>Stock<strong>Flow</strong></Link><span>Discover your local shop</span></nav>
    <header className='sf-shop-hero'>
      <span className='sf-shop-eyebrow'>SHOP LOCAL</span>
      <h1>{data?.shop.name || 'Welcome to the shop'}</h1>
      <p>{data?.shop.introduction || 'Browse products and find what you need.'}</p>
      {data?.shop.contactPhone && <p>Contact: {data.shop.contactPhone}</p>}
    </header>
    <section className='sf-shop-catalogue' aria-label='Product catalogue'>
      <form className='sf-shop-search' onSubmit={search}>
        <label htmlFor='shop-search'>Find a product</label>
        <div><input id='shop-search' value={draft} onChange={event => setDraft(event.target.value)} maxLength={100} placeholder='Search names, categories or design codes' /><button type='submit'>Search</button></div>
      </form>
      {loading ? <p role='status'>Loading products...</p> : error ? <div role='alert'><p>{error}</p><button type='button' onClick={() => setRetry(value => value + 1)}>Try again</button></div> : <>
        <p className='sf-shop-count'>{data?.count || 0} products {query && 'matching your search'}</p>
        {!data?.results.length && <div className='sf-shop-empty'><h2>No products to show</h2><p>{query ? 'Try another name or category.' : 'Check back soon for new listings.'}</p></div>}
        <div className='sf-shop-grid'>{data?.results.map(product => <article className='sf-shop-card' key={product.listingId}>
          <div className='sf-shop-image'>{product.imageUrl ? <img src={product.imageUrl} alt={product.name} loading='lazy' referrerPolicy='no-referrer' onError={event => { event.currentTarget.style.display = 'none'; }} /> : <span>{product.name.slice(0, 1)}</span>}</div>
          <div className='sf-shop-card-body'><small>{product.category}</small><h2>{product.name}</h2>
          {(product.designCode || product.size || product.color) && <p>{[product.designCode, product.size, product.color].filter(Boolean).join(' / ')}</p>}
          <button type='button' disabled={cartLocked || !product.inStock} onClick={() => addToCart(product)}>Add to cart</button>
          <strong className='sf-shop-price'>{shopMoney(product.price)} <small>/ {product.unit}</small></strong>
          <p className={product.inStock ? 'sf-shop-available' : 'sf-shop-unavailable'}>{product.inStock ? 'In stock' : 'Currently unavailable'}</p>
          {product.description && <p className='sf-shop-description'>{product.description}</p>}
          </div></article>)}</div>
        <div className='sf-shop-pagination'><button type='button' disabled={!data?.previous} onClick={() => setPage(value => Math.max(1, value - 1))}>Previous</button><span>Page {page}</span><button type='button' disabled={!data?.next} onClick={() => setPage(value => value + 1)}>Next</button></div>
      </>}
    </section>
    <div className='sf-shop-cart-wrap'><p role='status'>{cartMessage}</p><ShopCart slug={slug} cart={cart} setCart={setCart} locked={cartLocked} setLocked={setCartLocked} /></div>
    <footer className='sf-shop-footer'>Powered by StockFlow</footer>
  </main>;
}
