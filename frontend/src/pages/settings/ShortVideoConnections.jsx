import { useEffect, useRef, useState } from 'react';
import { apiRequest } from '../../services/api';

export default function ShortVideoConnections({ businessId }) {
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [disconnect, setDisconnect] = useState(null);
  const finished = useRef(null);
  const dialog = useRef(null);
  const base = '/businesses/' + businessId + '/storefront/social/';
  async function load() {
    const values = await Promise.all(['tiktok', 'snapchat'].map(provider => apiRequest(base + provider + '/connection/')));
    setRows(values);
  }
  useEffect(() => {
    let active = true;
    const params = new URLSearchParams(window.location.search);
    const provider = params.get('sfProvider'), requestId = params.get('sfRequest');
    async function start() {
      try {
        if (requestId && ['tiktok', 'snapchat'].includes(provider) && params.get('sfBusiness') === businessId && !finished.current) {
          const cancelled = params.get('sfResult') === 'cancelled';
          for (const key of ['sfProvider', 'sfRequest', 'sfBusiness', 'sfResult']) params.delete(key);
          window.history.replaceState({}, '', window.location.pathname + (params.size ? '?' + params.toString() : '') + window.location.hash);
          setBusy(provider);
          finished.current = cancelled
            ? Promise.resolve('Connection cancelled.')
            : apiRequest(base + provider + '/finish/', { method: 'POST', body: JSON.stringify({ requestId }) })
                .then(() => 'Account connected and verified. Publishing is not enabled yet.');
        }
        if (finished.current) {
          const resultMessage = await finished.current;
          if (active) setMessage(resultMessage);
        }
        const values = await Promise.all(['tiktok', 'snapchat'].map(item => apiRequest(base + item + '/connection/')));
        if (active) setRows(values);
      } catch (problem) { if (active) setError(problem.message); }
      finally { if (active) setBusy(''); }
    }
    start();
    return () => { active = false; };
  }, [businessId]);
  useEffect(() => { if (disconnect) dialog.current?.showModal(); }, [disconnect]);
  async function run(provider, action) {
    if (busy) return;
    setBusy(provider); setError(''); setMessage('');
    try {
      if (action === 'connect') {
        const result = await apiRequest(base + provider + '/connect/', { method: 'POST', body: '{}' });
        const target = new URL(result.authorizeUrl);
        const expected = provider === 'tiktok' ? 'www.tiktok.com' : 'accounts.snapchat.com';
        if (target.protocol !== 'https:' || target.hostname !== expected) throw new Error('The provider connection address is invalid.');
        window.location.assign(target.href);
        return;
      }
      await apiRequest(base + provider + '/connection/', { method: action === 'disconnect' ? 'DELETE' : 'POST', ...(action === 'disconnect' ? {} : { body: '{}' }) });
      setDisconnect(null);
      setMessage(action === 'disconnect' ? 'Account disconnected from StockFlow.' : 'Account connection verified.');
      await load();
    } catch (problem) { setError(problem.message); }
    finally { setBusy(''); }
  }
  return <section aria-label="TikTok and Snapchat connections" style={{ margin: '24px 0' }}>
    {error && <p role="alert">{error}</p>}
    {message && <p role="status">{message}</p>}
    {!rows.length && <button type="button" disabled={Boolean(busy)} onClick={() => load().catch(problem => setError(problem.message))}>Load account connections</button>}
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(min(100%,280px),1fr))', gap: '16px' }}>
      {rows.map(row => <article key={row.platform} style={{ border: '1px solid #dce6df', borderRadius: '18px', padding: '22px', background: '#fff' }}>
        <h3>{row.platform === 'tiktok' ? 'TikTok' : 'Snapchat'}</h3>
        <p><strong>{row.connectionStatus === 'connected' ? 'Connected to ' + row.accountName : row.connectionStatus === 'expired' ? 'Connection needs renewal' : 'Not connected'}</strong></p>
        {!row.configured && <p>Account connections are being set up. Please check back soon.</p>}
        <p>{row.message}</p>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          {row.configured && <button type="button" disabled={Boolean(busy)} onClick={() => run(row.platform, 'connect')}>
            {busy === row.platform ? 'Please wait…' : row.connectionStatus === 'not_connected' ? 'Connect account' : 'Reconnect'}
          </button>}
          {row.connectionStatus !== 'not_connected' && <>
            {row.configured && <button type="button" disabled={Boolean(busy)} onClick={() => run(row.platform, 'verify')}>Verify connection</button>}
            <button type="button" disabled={Boolean(busy)} onClick={() => setDisconnect(row.platform)}>Disconnect</button>
          </>}
        </div>
      </article>)}
    </div>
    {disconnect && <dialog ref={dialog} onCancel={event => { event.preventDefault(); if (!busy) setDisconnect(null); }} style={{ border: '1px solid #dce6df', borderRadius: '22px', padding: '28px', maxWidth: '420px', width: 'calc(100% - 40px)' }}>
      <h3>Disconnect {disconnect === 'tiktok' ? 'TikTok' : 'Snapchat'}?</h3>
      <p>This removes the connection from StockFlow. Your existing social posts remain.</p>
      <button type="button" disabled={Boolean(busy)} onClick={() => setDisconnect(null)}>Keep connection</button>{' '}
      <button type="button" disabled={Boolean(busy)} onClick={() => run(disconnect, 'disconnect')}>Disconnect</button>
      {error && <p role="alert">{error}</p>}
    </dialog>}
  </section>;
}
