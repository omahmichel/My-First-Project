import NotificationRefresh from "../../components/notifications/NotificationRefresh";
import { useEffect, useState } from 'react';
import { apiRequest } from '../../services/api';

function connectionLabel(channel) {
  if (channel.connectionStatus === 'connected') {
    return channel.accountName ? 'Connected to ' + channel.accountName : 'Connected';
  }
  if (channel.connectionStatus === 'selection_required') return 'Choose a Page';
  if (channel.connectionStatus === 'expired') return 'Connection expired';
  return 'Not connected';
}

function deliveryLabel(job, facebookConnected, instagramConnected) {
  if (job.status === 'cancelled') return 'Cancelled';
  if (job.platform !== 'facebook' && job.platform !== 'instagram') return 'Pending connection';
  if (job.deliveryStatus === 'succeeded') return 'Published';
  if (job.deliveryStatus === 'failed') return 'Failed';
  if (job.deliveryStatus === 'unknown') return 'Outcome unknown';
  if (job.deliveryStatus === 'in_progress') return 'Publishing...';
  if (job.platform === 'instagram') return instagramConnected ? 'Ready for live test' : 'Pending connection';
  return facebookConnected ? 'Ready for live test' : 'Pending connection';
}

export default function ShopSocialPanel({ businessId }) {
  const [channels, setChannels] = useState([]);
  const [jobs, setJobs] = useState(null);
  const [page, setPage] = useState(1);
  const [retry, setRetry] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [facebookPageId, setFacebookPageId] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [publishCandidate, setPublishCandidate] = useState(null);
  const [shopUrl, setShopUrl] = useState('');
  const [shopPath, setShopPath] = useState('');
  const base = '/businesses/' + businessId + '/storefront/social/';

  function applyChannels(nextChannels) {
    setChannels(nextChannels);
    const facebook = nextChannels.find(channel => channel.platform === 'facebook');
    const available = facebook?.availableAccounts || [];
    setFacebookPageId(current =>
      available.some(account => account.id === current)
        ? current
        : (available[0]?.id || '')
    );
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const result = params.get('social');
    if (!result) return;
    const messages = {
      'facebook-connected': 'Facebook Page connected successfully.',
      'facebook-select-page': 'Facebook authorization succeeded. Choose the Page StockFlow should use.',
      'facebook-cancelled': 'Facebook connection was cancelled.',
      'facebook-no-pages': 'Meta did not return a Page that StockFlow can manage.',
      'facebook-error': 'Facebook connection could not be completed. Please try again.',
    };
    if (messages[result]) setMessage(messages[result]);
    params.delete('social');
    const query = params.toString();
    window.history.replaceState({}, '', window.location.pathname + (query ? '?' + query : '') + window.location.hash);
  }, []);

  useEffect(() => {
    if (!publishCandidate) return undefined;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    function onKeyDown(event) {
      if (event.key === 'Escape' && !saving) setPublishCandidate(null);
    }

    window.addEventListener('keydown', onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [publishCandidate, saving]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    Promise.all([apiRequest(base + 'channels/'), apiRequest(base + 'jobs/?page=' + page)])
      .then(([settings, records]) => {
        if (active) {
          applyChannels(settings.channels);
          setShopUrl(settings.shopUrl || '');
          setShopPath(settings.shopPath || '');
          setJobs(records);
        }
      }).catch(problem => { if (active) setError(problem.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [base, page, retry]);

  async function toggle(channel) {
    if (saving) return;
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const result = await apiRequest(base + 'channels/' + channel.platform + '/', {
        method: 'PATCH', body: JSON.stringify({ autoPublish: !channel.autoPublish }),
      });
      applyChannels(result.channels);
      setMessage(channel.autoPublish
        ? channel.label + ' automatic publishing disabled.'
        : channel.label + ' preference saved.');
      setPage(1);
      setRetry(value => value + 1);
    } catch (problem) { setError(problem.message); }
    finally { setSaving(false); }
  }

  async function connectFacebook() {
    if (saving) return;
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const result = await apiRequest(base + 'facebook/connect/');
      if (!result?.authorizeUrl) throw new Error('StockFlow could not start the Meta connection.');
      window.location.assign(result.authorizeUrl);
    } catch (problem) {
      setError(problem.message);
      setSaving(false);
    }
  }

  async function connectInstagram() {
    if (saving) return;
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const result = await apiRequest(base + 'facebook/connect/');
      if (!result?.authorizeUrl) throw new Error('StockFlow could not start the Meta connection.');
      window.location.assign(result.authorizeUrl);
    } catch (problem) {
      setError(problem.message);
      setSaving(false);
    }
  }

  async function selectFacebookPage() {
    if (saving || !facebookPageId) return;
    setSaving(true);
    setError('');
    setMessage('');
    try {
      await apiRequest(base + 'facebook/select-page/', {
        method: 'POST',
        body: JSON.stringify({ pageId: facebookPageId }),
      });
      setMessage('Facebook Page connected successfully.');
      setRetry(value => value + 1);
    } catch (problem) { setError(problem.message); }
    finally { setSaving(false); }
  }

  function requestSocialPublish(job) {
    if (saving || !job?.id) return;
    setError('');
    setMessage('');
    setPublishCandidate(job);
  }

  async function confirmSocialPublish() {
    const job = publishCandidate;
    if (saving || !job?.id) return;

    const isInstagram = job.platform === 'instagram';
    const platformName = isInstagram ? 'Instagram' : 'Facebook';
    const destination = isInstagram
      ? (instagram?.accountName || 'the connected Instagram account')
      : (facebook?.accountName || 'the connected Facebook Page');
    const endpoint = isInstagram ? 'publish-instagram/' : 'publish-facebook/';

    setSaving(true);
    setError('');
    setMessage('');
    try {
      const result = await apiRequest(base + 'jobs/' + job.id + '/' + endpoint, {
        method: 'POST',
        body: JSON.stringify({}),
      });
      if (result?.deliveryStatus === 'succeeded') {
        setMessage('Published ' + job.productName + ' to ' + destination + '.');
      } else {
        setMessage(platformName + ' publishing status updated.');
      }
      setRetry(value => value + 1);
    } catch (problem) {
      setError(problem.message);
      setRetry(value => value + 1);
    } finally {
      setSaving(false);
      setPublishCandidate(null);
    }
  }

  async function copyShopLink() {
    if (!shopUrl) return;
    setError('');
    setMessage('');
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(shopUrl);
      } else {
        const field = document.createElement('textarea');
        field.value = shopUrl;
        field.setAttribute('readonly', '');
        field.style.position = 'fixed';
        field.style.opacity = '0';
        document.body.appendChild(field);
        field.select();
        const copied = document.execCommand('copy');
        document.body.removeChild(field);
        if (!copied) throw new Error('Copy command was not available.');
      }
      setMessage('Public shop link copied. Add it to the Instagram profile Links section.');
    } catch {
      setError('StockFlow could not copy the shop link automatically. Select the link and copy it manually.');
    }
  }

  async function disconnectFacebook() {
    if (saving) return;
    if (!window.confirm('Disconnect this Facebook Page from StockFlow?')) return;
    setSaving(true);
    setError('');
    setMessage('');
    try {
      await apiRequest(base + 'facebook/connection/', { method: 'DELETE' });
      setMessage('Facebook Page disconnected.');
      setRetry(value => value + 1);
    } catch (problem) { setError(problem.message); }
    finally { setSaving(false); }
  }

  const facebook = channels.find(channel => channel.platform === 'facebook');
  const instagram = channels.find(channel => channel.platform === 'instagram');

  return <section className='sf-shop-cart'>
    <h2>Social publishing</h2>
    <p>Choose where StockFlow should prepare social publishing. Facebook live delivery is available; Instagram account connection can now be verified before Instagram delivery is activated.</p>
    <NotificationRefresh><button type='button' disabled={loading || saving} onClick={() => setRetry(value => value + 1)}>Refresh publishing status</button></NotificationRefresh>
    {loading && <p role='status'>Loading social publishing...</p>}
    {error && <p role='alert'>{error}</p>}

    {!loading && <div className='sf-shop-whatsapp-settings'>
      <h3>Public StockFlow shop link</h3>
      {shopUrl ? <>
        <p>Customers who open this link see only this business&apos;s published online shop and published products.</p>
        <label>Shop link
          <input type='url' readOnly value={shopUrl} onFocus={event => event.target.select()} />
        </label>
        <button type='button' disabled={saving} onClick={copyShopLink}>Copy shop link</button>
        <p>Facebook product posts include this link automatically. For Instagram, copy it into the professional account&apos;s profile Links section.</p>
      </> : <>
        <p><strong>Shop path:</strong> {shopPath || 'Not available yet'}</p>
        <p>The permanent customer link will appear here after StockFlow&apos;s public HTTPS web address is configured for hosting. No localhost or temporary tunnel address will be published automatically.</p>
      </>}
    </div>}

    {!loading && facebook && <div className='sf-shop-whatsapp-settings'>
      <h3>Facebook Page</h3>
      <p><strong>{connectionLabel(facebook)}</strong></p>
      {facebook.connectionStatus === 'selection_required' && <>
        <label>Choose Page
          <select value={facebookPageId} onChange={event => setFacebookPageId(event.target.value)}>
            {(facebook.availableAccounts || []).map(account =>
              <option key={account.id} value={account.id}>{account.name}</option>
            )}
          </select>
        </label>
        <button type='button' disabled={saving || !facebookPageId} onClick={selectFacebookPage}>Use this Page</button>
      </>}
      {(facebook.connectionStatus === 'not_connected' || facebook.connectionStatus === 'expired') &&
        <button type='button' disabled={saving} onClick={connectFacebook}>
          {facebook.connectionStatus === 'expired' ? 'Reconnect Facebook' : 'Connect Facebook'}
        </button>}
      {facebook.connectionStatus === 'connected' && <>
        <p>The authorization is stored encrypted on the StockFlow backend. No Meta token is exposed in the browser.</p>
        <button type='button' disabled={saving} onClick={disconnectFacebook}>Disconnect Facebook</button>
      </>}
    </div>}

    {!loading && instagram && <div className='sf-shop-whatsapp-settings'>
      <h3>Instagram Professional Account</h3>
      <p><strong>{connectionLabel(instagram)}</strong></p>
      {(instagram.connectionStatus === 'not_connected' || instagram.connectionStatus === 'expired') && <>
        <p>Connect the Instagram professional account linked to the Facebook Page through the shared Meta authorization.</p>
        <button type='button' disabled={saving} onClick={connectInstagram}>
          {instagram.connectionStatus === 'expired' ? 'Reconnect Instagram' : 'Connect Instagram'}
        </button>
      </>}
      {instagram.connectionStatus === 'connected' && <>
        <p>The Instagram account is linked through the encrypted Meta authorization. Controlled manual publishing is available; automatic dispatch remains off.</p>
      </>}
    </div>}

    <fieldset disabled={loading || saving}>
      <legend>Automatic publishing preferences</legend>
      {channels.map(channel => <label className='sf-shop-toggle' key={channel.platform}>
        <input type='checkbox' checked={channel.autoPublish} onChange={() => toggle(channel)} />
        {channel.label} - {connectionLabel(channel)}
      </label>)}
    </fieldset>

    {message && <p role='status'>{message}</p>}
    {!loading && jobs && <>
      <h3>Publishing records ({jobs.count})</h3>
      <p>Each record represents the latest product details for one channel. Use Publish now for one controlled Facebook or Instagram post. Unknown delivery outcomes are deliberately not retried automatically to prevent duplicate posts.</p>
      {!jobs.results.length ? <p>No publishing records yet.</p> : <div style={{ overflowX: 'auto' }}>
        <table><thead><tr><th scope='col'>Product</th><th scope='col'>Channel</th><th scope='col'>Status</th><th scope='col'>Action</th></tr></thead>
          <tbody>{jobs.results.map(job => {
            const facebookConnected = facebook?.connectionStatus === 'connected' && facebook?.deliveryAvailable;
            const instagramConnected = instagram?.connectionStatus === 'connected' && instagram?.deliveryAvailable;
            const platformConnected = job.platform === 'instagram' ? instagramConnected : facebookConnected;
            const supportedPlatform = job.platform === 'facebook' || job.platform === 'instagram';
            const canPublish = supportedPlatform
              && job.status !== 'cancelled'
              && platformConnected
              && (job.deliveryStatus === 'not_sent' || job.deliveryStatus === 'failed');
            return <tr key={job.id}>
              <td>{job.productName}</td>
              <td>{channels.find(channel => channel.platform === job.platform)?.label || job.platform}</td>
              <td>
                {deliveryLabel(job, facebookConnected, instagramConnected)}
                {job.deliveryError && <small style={{ display: 'block' }}>{job.deliveryError}</small>}
              </td>
              <td>
                {canPublish
                  ? <button type='button' disabled={saving} onClick={() => requestSocialPublish(job)}>
                      {job.deliveryStatus === 'failed' ? 'Retry publish' : 'Publish now'}
                    </button>
                  : <span>-</span>}
              </td>
            </tr>;
          })}</tbody>
        </table>
      </div>}
      <div className='sf-shop-admin-actions'>
        <button type='button' disabled={saving || !jobs.previous} onClick={() => setPage(value => value - 1)}>Previous</button>
        <span>Page {page}</span>
        <button type='button' disabled={saving || !jobs.next} onClick={() => setPage(value => value + 1)}>Next</button>
      </div>
    </>}

    {publishCandidate && <div
      role='presentation'
      onMouseDown={event => {
        if (event.target === event.currentTarget && !saving) setPublishCandidate(null);
      }}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 10000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
        background: 'rgba(3, 28, 26, 0.62)',
        backdropFilter: 'blur(6px)',
      }}
    >
      <div
        role='dialog'
        aria-modal='true'
        aria-labelledby='social-publish-title'
        aria-describedby='social-publish-description'
        style={{
          width: 'min(100%, 520px)',
          overflow: 'hidden',
          borderRadius: '22px',
          background: '#ffffff',
          boxShadow: '0 28px 80px rgba(0, 0, 0, 0.28)',
          border: '1px solid rgba(15, 58, 54, 0.12)',
        }}
      >
        <div style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: '16px',
          padding: '24px 24px 18px',
          borderBottom: '1px solid #e9efed',
        }}>
          <div style={{ display: 'flex', gap: '14px', alignItems: 'center' }}>
            <div aria-hidden='true' style={{
              width: '44px',
              height: '44px',
              flex: '0 0 44px',
              borderRadius: '14px',
              display: 'grid',
              placeItems: 'center',
              background: publishCandidate.platform === 'instagram' ? '#111111' : '#1877f2',
              color: '#ffffff',
              fontSize: publishCandidate.platform === 'instagram' ? '15px' : '27px',
              fontWeight: 800,
              fontFamily: 'Arial, sans-serif',
            }}>{publishCandidate.platform === 'instagram' ? 'IG' : 'f'}</div>
            <div>
              <div style={{
                marginBottom: '4px',
                color: '#637571',
                fontSize: '13px',
                fontWeight: 700,
                letterSpacing: '.04em',
                textTransform: 'uppercase',
              }}>{publishCandidate.platform === 'instagram' ? 'Instagram publishing' : 'Facebook publishing'}</div>
              <h3 id='social-publish-title' style={{
                margin: 0,
                color: '#103b37',
                fontSize: '22px',
                lineHeight: 1.25,
              }}>Publish this product?</h3>
            </div>
          </div>

          <button
            type='button'
            aria-label='Close Facebook publishing confirmation'
            disabled={saving}
            onClick={() => setPublishCandidate(null)}
            style={{
              width: '38px',
              height: '38px',
              border: '1px solid #dce6e3',
              borderRadius: '12px',
              background: '#f7faf9',
              color: '#34504c',
              fontSize: '24px',
              lineHeight: 1,
              cursor: saving ? 'not-allowed' : 'pointer',
            }}
          >×</button>
        </div>

        <div style={{ padding: '22px 24px 8px' }}>
          <div style={{
            padding: '16px',
            borderRadius: '16px',
            background: '#f5f8f7',
            border: '1px solid #e2eae8',
          }}>
            <div style={{ marginBottom: '12px' }}>
              <div style={{ color: '#71817e', fontSize: '13px', marginBottom: '3px' }}>Product</div>
              <strong style={{ color: '#173f3b', fontSize: '17px' }}>{publishCandidate.productName}</strong>
            </div>
            <div>
              <div style={{ color: '#71817e', fontSize: '13px', marginBottom: '3px' }}>Destination</div>
              <strong style={{ color: '#173f3b' }}>
                {publishCandidate.platform === 'instagram'
                  ? (instagram?.accountName || 'Connected Instagram account')
                  : (facebook?.accountName || 'Connected Facebook Page')}
              </strong>
            </div>
          </div>

          <p id='social-publish-description' style={{
            margin: '18px 0 8px',
            color: '#526662',
            lineHeight: 1.55,
          }}>
            This action creates a real post on the connected {publishCandidate.platform === 'instagram' ? 'Instagram account' : 'Facebook Page'}. StockFlow will record the delivery result and Meta post ID after publishing.
          </p>
        </div>

        <div style={{
          display: 'flex',
          justifyContent: 'flex-end',
          gap: '12px',
          padding: '18px 24px 24px',
        }}>
          <button
            type='button'
            disabled={saving}
            onClick={() => setPublishCandidate(null)}
            style={{
              minWidth: '105px',
              padding: '12px 18px',
              border: '1px solid #cedbd8',
              borderRadius: '12px',
              background: '#ffffff',
              color: '#214844',
              fontWeight: 700,
              cursor: saving ? 'not-allowed' : 'pointer',
            }}
          >Cancel</button>
          <button
            type='button'
            autoFocus
            disabled={saving}
            onClick={confirmSocialPublish}
            style={{
              minWidth: '176px',
              padding: '12px 18px',
              border: 0,
              borderRadius: '12px',
              background: '#b9470e',
              color: '#ffffff',
              fontWeight: 800,
              cursor: saving ? 'not-allowed' : 'pointer',
              opacity: saving ? 0.72 : 1,
            }}
          >{saving ? 'Publishing...' : ('Publish to ' + (publishCandidate.platform === 'instagram' ? 'Instagram' : 'Facebook'))}</button>
        </div>
      </div>
    </div>}
  </section>;
}
