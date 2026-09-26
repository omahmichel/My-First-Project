import { useEffect, useRef, useState } from 'react';
import { apiRequest } from '../../services/api';
import './tiktok-publisher.css';

const empty = { caption: '', privacy: '', comment: false, duet: false, stitch: false, disclosure: false, ownBrand: false, branded: false, aigc: false, consent: false };
const labels = { SELF_ONLY: 'Only me', PUBLIC_TO_EVERYONE: 'Everyone', MUTUAL_FOLLOW_FRIENDS: 'Friends', FOLLOWER_OF_CREATOR: 'Followers' };
const states = { submitting: 'Submitting — do not resend', processing: 'Processing', published: 'Published', failed: 'Failed', unknown: 'Outcome unknown — check TikTok before another attempt' };
export default function TikTokPublisher({ businessId }) {
  const base = `/businesses/${businessId}/storefront/social/tiktok/`;
  const [open, setOpen] = useState(false), [videos, setVideos] = useState([]), [posts, setPosts] = useState([]);
  const [selected, setSelected] = useState(''), [preview, setPreview] = useState(null), [form, setForm] = useState(empty);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const lock = useRef(false), active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  function change(key, value) { setForm(current => ({ ...current, [key]: value, ...(key !== 'consent' ? { consent: false } : {}) })); }
  async function action(fn) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError('');
    try { await fn(); } catch (e) { if (active.current) setError(e.message); }
    finally { lock.current = false; if (active.current) setBusy(false); }
  }
  async function load() {
    const data = await apiRequest(base + 'videos/');
    if (active.current) { setVideos(data.videos); setPosts(data.posts); }
  }
  function prepare() { action(async () => {
    setPreview(null);
    const data = await apiRequest(base + 'prepare/', { method: 'POST', body: JSON.stringify({ videoId: selected }) });
    if (active.current) { setPreview(data); setForm({ ...empty }); }
  }); }
  function upsert(result) { setPosts(current => [result, ...current.filter(p => p.id !== result.id)]); }
  async function refreshPost(id) {
    const result = await apiRequest(base + `posts/${id}/status/`, { method: 'POST', body: '{}' });
    if (active.current) upsert(result);
  }
  const processingId = posts.find(p => p.status === 'processing')?.id;
  useEffect(() => {
    if (!open || !processingId) return undefined;
    const timer = setInterval(() => { if (!lock.current) action(() => refreshPost(processingId)); }, 15000);
    return () => clearInterval(timer);
  }, [open, processingId]);
  const valid = preview && form.privacy && form.consent && (!form.disclosure || form.ownBrand || form.branded) && !(form.branded && form.privacy === 'SELF_ONLY');
  function publish() { action(async () => {
    const result = await apiRequest(base + `posts/${preview.id}/publish/`, { method: 'POST', body: JSON.stringify(form) });
    if (active.current) { upsert(result); setPreview(null); setForm({ ...empty }); }
  }); }
  return <div className="sf-tiktok-publisher">
    <button type="button" disabled={busy} onClick={() => { setOpen(!open); if (!open) action(load); }}>{open ? 'Close publishing panel' : 'Prepare a TikTok video'}</button>
    {open && <section aria-label="Publish a TikTok video">
      <h4>Post a product video to TikTok</h4>
      <p>Review and approve each post. It may take a few minutes to appear after TikTok processes it.</p>
      <p>During unaudited testing, TikTok requires a private account and Only me visibility. Public posting requires TikTok approval.</p>
      {error && <p role="alert">{error}</p>}
      <fieldset disabled={busy}>
        <label>Product video<select value={selected} onChange={e => { setSelected(e.target.value); setPreview(null); }}><option value="">Choose a video</option>{videos.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}</select></label>
        {!videos.length && <p>Add a video to a product in Inventory, then reopen this panel.</p>}
        <button type="button" disabled={!selected} onClick={prepare}>Load preview and TikTok settings</button>
        {preview && <>
          <p><strong>Posting to {preview.creator.creator_nickname}</strong>{preview.creator.creator_username && ` (@${preview.creator.creator_username})`}</p>
          <video controls playsInline preload="metadata" src={preview.previewUrl} />
          <p>{Math.ceil(preview.duration)} seconds · Maximum {preview.creator.max_video_post_duration_sec} seconds</p>
          <label>Caption<textarea rows={4} maxLength={2200} value={form.caption} onChange={e => change('caption', e.target.value)} /></label>
          <label>Who can view this video?<select value={form.privacy} onChange={e => change('privacy', e.target.value)}><option value="">Choose audience</option>{preview.creator.privacy_level_options.map(value => <option key={value} value={value} disabled={value === 'SELF_ONLY' && form.branded}>{labels[value] || value}</option>)}</select></label>
          {['comment', 'duet', 'stitch'].map(key => <label className="sf-tiktok-check" key={key}><input type="checkbox" disabled={preview.creator[key + '_disabled'] !== false} checked={form[key]} onChange={e => change(key, e.target.checked)} />Allow {key}{preview.creator[key + '_disabled'] !== false ? ' (disabled by TikTok)' : ''}</label>)}
          <label className="sf-tiktok-check"><input type="checkbox" checked={form.disclosure} onChange={e => setForm(f => ({ ...f, disclosure: e.target.checked, ownBrand: false, branded: false, consent: false }))} />Disclose commercial content</label>
          {form.disclosure && <>
            <p>Indicate whether this video promotes your business, another brand, or both.</p>
            <label className="sf-tiktok-check"><input type="checkbox" checked={form.ownBrand} onChange={e => change('ownBrand', e.target.checked)} />Your brand</label>
            <label className="sf-tiktok-check"><input type="checkbox" disabled={form.privacy === 'SELF_ONLY'} checked={form.branded} onChange={e => change('branded', e.target.checked)} />Branded content (another brand / paid partnership)</label>
            {form.privacy === 'SELF_ONLY' && <p>Branded content visibility cannot be private.</p>}
            {(form.ownBrand || form.branded) && <p>Your video will be labeled as “{form.branded ? 'Paid partnership' : 'Promotional content'}”.</p>}
          </>}
          <label className="sf-tiktok-check"><input type="checkbox" checked={form.aigc} onChange={e => change('aigc', e.target.checked)} />This video contains AI-generated content</label>
          <label className="sf-tiktok-check"><input type="checkbox" checked={form.consent} onChange={e => change('consent', e.target.checked)} /><span>I approve sending this video to TikTok. By posting, you agree to TikTok’s {form.branded && <><a href="https://www.tiktok.com/legal/page/global/bc-policy/en" target="_blank" rel="noreferrer">Branded Content Policy</a> and </>}<a href="https://www.tiktok.com/legal/page/global/music-usage-confirmation/en" target="_blank" rel="noreferrer">Music Usage Confirmation</a>.</span></label>
          <button type="button" disabled={!valid} onClick={publish}>{busy ? 'Please wait…' : 'Post to TikTok'}</button>
        </>}
      </fieldset>
      <h4>Recent TikTok attempts</h4>
      <button type="button" disabled={busy} onClick={() => action(load)}>Refresh history</button>
      {!posts.length && <p>No publishing attempts yet.</p>}
      {posts.map(post => <article key={post.id} className="sf-tiktok-attempt"><strong>{states[post.status] || post.status} · {post.accountName}</strong><p>{post.caption}</p><p role="status">{post.message}</p>{post.status === 'processing' && <button type="button" disabled={busy} onClick={() => action(() => refreshPost(post.id))}>Check TikTok status</button>}</article>)}
    </section>}
  </div>;
}
