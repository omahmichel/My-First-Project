import { useEffect, useState } from 'react';
import { publicShopRequest, resolveShopMediaUrl } from '../../services/storefront';

import ShopMediaActions, { useShopMediaManager } from './ShopMediaActions';

function PromotionVideo({ product, manager, onDeleted }) {
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  return <article style={{ minWidth: 0, border: '1px solid #dce4de', borderRadius: '16px', overflow: 'hidden', background: '#fff' }}>
    {manager && <ShopMediaActions key={manager.userId + ':' + manager.businessId} product={product} manager={manager} kind="video" onDeleted={onDeleted} />}
    <div style={{ background: '#102c24', aspectRatio: '4 / 3', display: 'grid', placeItems: 'center' }}>
      {failed ? <div role="status" style={{ padding: '20px', color: '#fff', textAlign: 'center' }}>
        <p>This video could not play.</p>
        <button type="button" onClick={() => { setFailed(false); setAttempt(value => value + 1); }}>Try again</button>
      </div> : <video
        key={attempt}
        src={resolveShopMediaUrl(product.videoUrl)}
        poster={resolveShopMediaUrl(product.imageUrl) || undefined}
        controls
        playsInline
        preload="none"
        aria-label={'Promotional video: ' + product.name}
        onError={() => setFailed(true)}
        style={{ display: 'block', width: '100%', height: '100%', minHeight: 0, objectFit: 'contain' }}
      />}
    </div>
    <div style={{ padding: '18px' }}>
      <small>{product.category}</small>
      <h3 style={{ margin: '8px 0', overflowWrap: 'anywhere' }}>{product.name}</h3>
      {(product.designCode || product.styleCode || product.size || product.color) && <p style={{ margin: 0 }}>
        {[product.designCode || product.styleCode, product.size, product.color].filter(Boolean).join(' / ')}
      </p>}
      {product.description && <p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{product.description}</p>}
    </div>
  </article>;
}

export default function ShopPromotionVideos({ slug }) {
  const manager = useShopMediaManager(slug);
  const [notice, setNotice] = useState('');
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [retry, setRetry] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    publicShopRequest(slug, '?media=videos&page=' + page, { signal: controller.signal })
      .then(result => { if (!controller.signal.aborted) setData(result); })
      .catch(problem => { if (!controller.signal.aborted) setError(problem.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [slug, page, retry]);
  function onDeleted(product) {
    setNotice('Video deleted successfully. The product and photo are unchanged.');
    setData(current => current ? { ...current, results: current.results.filter(item => item.productId !== product.productId), count: Math.max(0, current.count - 1) } : current);
    setPage(1);
    setRetry(value => value + 1);
  }
  if (!loading && !error && !data?.count && !notice) return null;
  return <section aria-labelledby="shop-promotion-heading" style={{ maxWidth: '1200px', margin: '0 auto', padding: '16px 24px 36px' }}>
    <h2 id="shop-promotion-heading">Videos from this shop</h2>
    <p>Product demonstrations and promotions.</p>
    {notice && <p role="status" style={{ color: '#11664a' }}>{notice}</p>}
    {loading ? <p role="status">Loading videos...</p> : error ? <div role="alert">
      <p>{error}</p><button type="button" onClick={() => setRetry(value => value + 1)}>Try again</button>
    </div> : <>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 280px), 360px))', gap: '24px' }}>
        {data.results.filter(product => product.videoUrl).map(product => <PromotionVideo
          key={product.listingId + ':' + product.videoUrl} product={product} manager={manager} onDeleted={onDeleted}
        />)}
      </div>
      {(data.previous || data.next) && <div className="sf-shop-pagination" aria-label="Video pages">
        <button type="button" disabled={!data.previous} onClick={() => setPage(value => Math.max(1, value - 1))}>Previous videos</button>
        <span>Page {page}</span>
        <button type="button" disabled={!data.next} onClick={() => setPage(value => value + 1)}>Next videos</button>
      </div>}
    </>}
  </section>;
}
