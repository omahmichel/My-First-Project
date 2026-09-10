import { useEffect, useState } from 'react';
import { apiRequest } from '../../services/api';

export default function ShopSocialPanel({ businessId }) {
  const [channels, setChannels] = useState([]);
  const [jobs, setJobs] = useState(null);
  const [page, setPage] = useState(1);
  const [retry, setRetry] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const base = '/businesses/' + businessId + '/storefront/social/';

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    Promise.all([apiRequest(base + 'channels/'), apiRequest(base + 'jobs/?page=' + page)])
      .then(([settings, records]) => {
        if (active) { setChannels(settings.channels); setJobs(records); }
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
      setChannels(result.channels);
      setMessage(channel.autoPublish ? channel.label + ' automatic publishing disabled.' : channel.label + ' preference saved. Products will wait for a working connection.');
      setPage(1);
      setRetry(value => value + 1);
    } catch (problem) { setError(problem.message); }
    finally { setSaving(false); }
  }

  return <section className='sf-shop-cart'>
    <h2>Social publishing</h2>
    <p>Choose where you want StockFlow to publish your products automatically. Enabling a channel prepares your currently published products and future listing saves.</p>
    <p><strong>Account connections are not available yet.</strong> Products remain pending; nothing is sent to social media in this version.</p>
    <button type='button' disabled={loading || saving} onClick={() => setRetry(value => value + 1)}>Refresh publishing status</button>
    {loading && <p role='status'>Loading social publishing...</p>}
    {error && <p role='alert'>{error}</p>}
    <fieldset disabled={loading || saving}>
      <legend>Automatic publishing preferences</legend>
      {channels.map(channel => <label className='sf-shop-toggle' key={channel.platform}>
        <input type='checkbox' checked={channel.autoPublish} onChange={() => toggle(channel)} />
        {channel.label} — Not connected
      </label>)}
    </fieldset>
    {message && <p role='status'>{message}</p>}
    {!loading && jobs && <>
      <h3>Publishing records ({jobs.count})</h3>
      <p>Each record represents the latest product details for one channel. Disabling a channel or unpublishing cancels pending records. Refresh after saving a product or shop setting.</p>
      {!jobs.results.length ? <p>No publishing records yet.</p> : <div style={{ overflowX: 'auto' }}>
        <table><thead><tr><th scope='col'>Product</th><th scope='col'>Channel</th><th scope='col'>Status</th></tr></thead>
          <tbody>{jobs.results.map(job => <tr key={job.id}><td>{job.productName}</td><td>{channels.find(channel => channel.platform === job.platform)?.label || job.platform}</td><td>{job.status === 'cancelled' ? 'Cancelled' : 'Pending connection'}</td></tr>)}</tbody>
        </table>
      </div>}
      <div className='sf-shop-admin-actions'>
        <button type='button' disabled={saving || !jobs.previous} onClick={() => setPage(value => value - 1)}>Previous</button>
        <span>Page {page}</span>
        <button type='button' disabled={saving || !jobs.next} onClick={() => setPage(value => value + 1)}>Next</button>
      </div>
    </>}
  </section>;
}
