import ShopMediaActions, { useShopMediaManager } from './ShopMediaActions';
import ShopCart from './ShopCart';
import ShopProductMedia from './ShopProductMedia';
import ShopPromotionVideos from './ShopPromotionVideos';
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { publicShopRequest, shopMoney } from '../../services/storefront';
import '../../styles/storefront.css';

// StockFlow business-controlled WhatsApp enquiries v1.
function whatsappPhone(value) {
  let digits = String(value || '').replace(/\D/g, '');
  if (digits.startsWith('00')) digits = digits.slice(2);
  if (digits.length === 10 && digits.startsWith('0')) {
    digits = '233' + digits.slice(1);
  } else if (digits.length === 9) {
    digits = '233' + digits;
  }
  if (digits.length < 8 || digits.length > 15 || digits.startsWith('0')) return '';
  return digits;
}

function whatsappHref(phone, message) {
  const digits = whatsappPhone(phone);
  return digits ? 'https://wa.me/' + digits + '?text=' + encodeURIComponent(message) : '';
}

export default function ShopPage() {
  const { slug } = useParams();
  return <ShopCatalogue key={slug} slug={slug} />;
}

function ShopCatalogue({ slug }) {
  const manager = useShopMediaManager(slug);
  const [mediaNotice, setMediaNotice] = useState('');
  function photoDeleted() {
    setMediaNotice('Photo deleted successfully. The product and video are unchanged.');
    setRetry(value => value + 1);
  }
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

  const shopName = data?.shop.name || 'this shop';
  const whatsappEnabled = Boolean(data?.shop.whatsappEnabled && whatsappPhone(data?.shop.whatsappPhone));
  const shopWhatsappHref = whatsappEnabled
    ? whatsappHref(
        data.shop.whatsappPhone,
        'Hello ' + shopName + ', I am viewing your StockFlow online shop and would like to make an enquiry. ' + window.location.href,
      )
    : '';

  return <main className='sf-shop'>
    <nav className='sf-shop-nav'><Link to='/'>Stock<strong>Flow</strong></Link><span>Discover your local shop</span></nav>
    <header className='sf-shop-hero'>
      <span className='sf-shop-eyebrow'>SHOP LOCAL</span>
      <h1>{data?.shop.name || 'Welcome to the shop'}</h1>
      <p>{data?.shop.introduction || 'Browse products and find what you need.'}</p>
      {data?.shop.contactPhone && <p>Contact: {data.shop.contactPhone}</p>}
      {shopWhatsappHref && <a className='sf-shop-whatsapp' href={shopWhatsappHref} target='_blank' rel='noopener noreferrer'>Chat on WhatsApp</a>}
    </header>
    <section className='sf-shop-catalogue' aria-label='Product catalogue'>
      <form className='sf-shop-search' onSubmit={search}>
        <label htmlFor='shop-search'>Find a product</label>
        <div><input id='shop-search' value={draft} onChange={event => setDraft(event.target.value)} maxLength={100} placeholder='Search names, categories or design codes' /><button type='submit'>Search</button></div>
      </form>
      {mediaNotice && <p role='status'>{mediaNotice}</p>}
      {loading ? <p role='status'>Loading products...</p> : error ? <div role='alert'><p>{error}</p><button type='button' onClick={() => setRetry(value => value + 1)}>Try again</button></div> : <>
        <p className='sf-shop-count'>{data?.count || 0} products {query && 'matching your search'}</p>
        {!data?.results.length && <div className='sf-shop-empty'><h2>No products to show</h2><p>{query ? 'Try another name or category.' : 'Check back soon for new listings.'}</p></div>}
        <div className='sf-shop-grid'>{data?.results.map(product => <article className='sf-shop-card' key={product.listingId}>
          {manager && product.imageUrl && <ShopMediaActions
            key={manager.userId + ':' + manager.businessId} product={product} manager={manager} kind="photo" onDeleted={photoDeleted} />}
          <ShopProductMedia key={product.listingId + ':' + (product.videoUrl || '') + ':' + (product.imageUrl || '')} product={product} />
          <div className='sf-shop-card-body'><small>{product.category}</small><h2>{product.name}</h2>
          {(product.designCode || product.size || product.color) && <p>{[product.designCode, product.size, product.color].filter(Boolean).join(' / ')}</p>}
          <button type='button' disabled={cartLocked || !product.inStock} onClick={() => addToCart(product)}>Add to cart</button>
          {whatsappEnabled && <a
            className='sf-shop-whatsapp sf-shop-whatsapp-product'
            href={whatsappHref(
              data.shop.whatsappPhone,
              'Hello ' + shopName + ', I am interested in ' + product.name
                + (product.designCode ? ' (Design ' + product.designCode + ')' : '')
                + ' listed at ' + shopMoney(product.price) + ' on your StockFlow shop. ' + window.location.href,
            )}
            target='_blank'
            rel='noopener noreferrer'
          aria-label='Ask on WhatsApp'
            title='Ask on WhatsApp'
          >
            <svg
              className='sf-shop-whatsapp-icon'
              viewBox='0 0 24 24'
              aria-hidden='true'
              focusable='false'
            >
              <path
                fill='currentColor'
                d='M12 2a9.2 9.2 0 0 0-7.9 13.9L3 22l6.2-1.6A9.2 9.2 0 1 0 12 2Zm0 16.7a7.4 7.4 0 0 1-3.8-1l-.4-.2-2.7.7.7-2.6-.3-.4A7.4 7.4 0 1 1 12 18.7Zm4.1-5.5c-.2-.1-1.3-.6-1.5-.7-.2-.1-.4-.1-.6.1-.2.2-.6.7-.8.9-.1.2-.3.2-.5.1-1.4-.7-2.4-1.3-3.3-2.9-.2-.3.2-.3.6-1.1.1-.2 0-.4 0-.5l-.7-1.7c-.2-.4-.4-.4-.6-.4h-.5c-.2 0-.5.1-.7.3-.2.2-1 1-1 2.4s1 2.8 1.2 3c.1.2 2 3.1 4.9 4.3.7.3 1.2.5 1.6.6.7.2 1.3.2 1.8.1.6-.1 1.8-.7 2-1.4.3-.7.3-1.3.2-1.4-.1-.1-.2-.2-.5-.3Z'
              />
            </svg>
          </a>}
          <strong className='sf-shop-price'>{shopMoney(product.price)} <small>/ {product.unit}</small></strong>
          <p className={product.inStock ? 'sf-shop-available' : 'sf-shop-unavailable'}>{product.inStock ? 'In stock' : 'Currently unavailable'}</p>
          {product.description && <p className='sf-shop-description'>{product.description}</p>}
          </div></article>)}</div>
        <div className='sf-shop-pagination'><button type='button' disabled={!data?.previous} onClick={() => setPage(value => Math.max(1, value - 1))}>Previous</button><span>Page {page}</span><button type='button' disabled={!data?.next} onClick={() => setPage(value => value + 1)}>Next</button></div>
      </>}
    </section>
    {!loading && !error && <ShopPromotionVideos slug={slug} />}
    <div className='sf-shop-cart-wrap'><p role='status'>{cartMessage}</p><ShopCart slug={slug} cart={cart} setCart={setCart} locked={cartLocked} setLocked={setCartLocked} /></div>
    <footer className='sf-shop-footer'>Powered by StockFlow</footer>
  </main>;
}
