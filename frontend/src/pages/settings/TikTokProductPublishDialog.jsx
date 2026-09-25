import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { apiRequest } from '../../services/api';

const PRIVACY_LABELS = {
  PUBLIC_TO_EVERYONE: 'Everyone',
  MUTUAL_FOLLOW_FRIENDS: 'Friends',
  FOLLOWER_OF_CREATOR: 'Followers',
  SELF_ONLY: 'Only me',
};

export default function TikTokProductPublishDialog({ businessId, job, accountName, onClose, onSubmitted }) {
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [creator, setCreator] = useState(null);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [privacy, setPrivacy] = useState('');
  const [allowComments, setAllowComments] = useState(false);
  const [autoAddMusic, setAutoAddMusic] = useState(false);
  const [disclosure, setDisclosure] = useState(false);
  const [ownBrand, setOwnBrand] = useState(false);
  const [branded, setBranded] = useState(false);
  const [consent, setConsent] = useState(false);
  const [photoUrl, setPhotoUrl] = useState('');
  const [photoReady, setPhotoReady] = useState(false);
  const [photoFailed, setPhotoFailed] = useState(false);
  const [progress, setProgress] = useState('');
  const publishing = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  useEffect(() => { setConsent(false); }, [title, description, privacy, allowComments, autoAddMusic, disclosure, ownBrand, branded]);
  const base = '/businesses/' + businessId + '/storefront/social/jobs/' + job.id + '/';

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    setCreator(null);
    setPhotoUrl('');
    setPhotoReady(false);
    setPhotoFailed(false);
    setPrivacy('');
    setAllowComments(false);
    setAutoAddMusic(false);
    setDisclosure(false);
    setOwnBrand(false);
    setBranded(false);
    setConsent(false);
    apiRequest(base + 'prepare-tiktok/', { method: 'POST', body: JSON.stringify({}) })
      .then(result => {
        if (!active) return;
        setPhotoUrl(result.photoUrl || '');
        setCreator(result.creator || null);
        setTitle(result.title || '');
        setDescription(result.description || '');
      })
      .catch(problem => { if (active) setError(problem.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [base]);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    function onKeyDown(event) {
      if (event.key === 'Escape' && !busy) onClose();
    }
    window.addEventListener('keydown', onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [busy, onClose]);

  const disclosureValid = !disclosure || ownBrand || branded;
  const brandedPrivacyValid = !(branded && privacy === 'SELF_ONLY');
  const canPublish = !loading && !busy && creator && photoReady && !photoFailed && privacy && consent && disclosureValid && brandedPrivacyValid;

  async function publish() {
    if (!canPublish || publishing.current) return;
    publishing.current = true;
    setProgress('Submitting to TikTok...');
    setBusy(true);
    setError('');
    try {
      const result = await apiRequest(base + 'publish-tiktok/', {
        method: 'POST',
        body: JSON.stringify({
          title,
          description,
          privacy,
          allowComments,
          autoAddMusic,
          disclosure,
          ownBrand,
          branded,
          consent,
        }),
      });
      if (mounted.current) onSubmitted(result);
    } catch (problem) {
      publishing.current = false;
      if (mounted.current) { setError(problem.message); setBusy(false); setProgress(''); }
    }
  }

  return createPortal(
    <div
    className='sf-tiktok-overlay'
    role='presentation'
    onMouseDown={event => { if (event.target === event.currentTarget && !busy) onClose(); }}
    style={{
      position: 'fixed', inset: 0, zIndex: 10020, display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '20px', background: 'rgba(3, 28, 26, 0.68)', backdropFilter: 'blur(6px)',
    }}
  >
    <section
      className='sf-tiktok-product-dialog'
      role='dialog'
      aria-modal='true'
      aria-labelledby='tiktok-product-publish-title'
      style={{
        width: 'min(100%, 620px)', maxHeight: 'calc(100vh - 40px)', overflowY: 'auto',
        borderRadius: '22px', background: '#fff', boxShadow: '0 28px 80px rgba(0,0,0,.3)',
        border: '1px solid rgba(15,58,54,.12)',
      }}
      onMouseDown={event => event.stopPropagation()}
    >
      <style>{`
        .sf-tiktok-product-dialog, .sf-tiktok-product-dialog * { box-sizing: border-box; }
        .sf-tiktok-product-dialog {
          display: flex !important; flex-direction: column !important;
          width: min(100%, 620px) !important;
          max-height: calc(100dvh - 24px) !important; overflow: hidden !important;
          border-radius: 16px !important; font-size: 14px !important;
          line-height: 1.4 !important; color: #163c37;
        }
        .sf-tiktok-product-dialog > header {
          flex: 0 0 auto; padding: 12px 18px !important; gap: 12px !important;
          align-items: center; background: #f5faf8;
        }
        .sf-tiktok-product-dialog h3 { font-size: 19px !important; line-height: 1.25 !important; }
        .sf-tiktok-product-dialog > header button {
          width: 34px !important; min-width: 34px !important; height: 34px !important;
          padding: 0 !important; border: 1px solid #d8e4df; border-radius: 8px;
          background: white; color: #163c37; font-size: 24px; cursor: pointer;
        }
        .sf-tiktok-product-dialog > .sf-tiktok-body {
          flex: 1 1 auto; min-height: 0; overflow-y: auto;
          overscroll-behavior: contain; padding: 12px 18px !important;
        }
        .sf-tiktok-product-dialog p { margin: 0 0 10px !important; font-size: 13px !important; line-height: 1.45 !important; }
        .sf-tiktok-product-dialog label {
          display: block; margin: 0 0 8px !important;
          font-size: 14px !important; line-height: 1.4 !important; text-align: left;
        }
        .sf-tiktok-product-dialog input:not([type="checkbox"]),
        .sf-tiktok-product-dialog select, .sf-tiktok-product-dialog textarea {
          display: block; width: 100% !important; margin: 4px 0 0 !important;
          padding: 8px 10px !important; min-height: 38px !important;
          border: 1px solid #cbdcd5 !important; border-radius: 8px !important;
          font-family: inherit !important; font-size: 14px !important;
          line-height: 1.4 !important; color: #163c37; background: #fff;
        }
        .sf-tiktok-product-dialog textarea { height: 88px !important; min-height: 70px !important; resize: vertical; }
        .sf-tiktok-product-dialog small { display: block; font-size: 12px !important; line-height: 1.4 !important; color: #566f68; margin: 3px 0 8px; }
        .sf-tiktok-product-dialog label.sf-tiktok-product-check {
          display: grid !important; grid-template-columns: 18px minmax(0, 1fr);
          align-items: start; column-gap: 9px; padding: 5px 0 !important;
          margin: 0 !important; min-height: 32px; cursor: pointer;
        }
        .sf-tiktok-product-dialog label.sf-tiktok-product-check input[type="checkbox"] {
          appearance: auto !important; position: static !important; display: block !important;
          width: 18px !important; height: 18px !important;
          min-width: 18px !important; min-height: 18px !important;
          max-width: 18px !important; max-height: 18px !important;
          margin: 1px 0 0 !important; padding: 0 !important;
          transform: none !important; box-shadow: none !important; accent-color: #17685b;
        }
        .sf-tiktok-product-dialog .sf-tiktok-disclosure {
          margin: 8px 0 !important; padding: 7px 10px !important;
          border-radius: 9px !important; background: #f7faf8;
        }
        .sf-tiktok-product-dialog .sf-tiktok-processing {
          margin: 8px 0 0 !important; font-size: 12px !important; color: #566f68;
        }
        .sf-tiktok-product-dialog > footer {
          flex: 0 0 auto; padding: 10px 18px !important; gap: 8px !important; background: #fff;
        }
        .sf-tiktok-product-dialog > footer button {
          min-height: 40px !important; padding: 8px 14px !important;
          border: 1px solid #cadbd3; border-radius: 8px !important;
          background: #fff; color: #163c37; font: inherit; font-weight: 600; cursor: pointer;
        }
        .sf-tiktok-product-dialog > footer button:last-child { background: #17685b; color: #fff; border-color: #17685b; }
        .sf-tiktok-product-dialog button:disabled { opacity: .5; cursor: not-allowed; }
        .sf-tiktok-product-dialog :is(input, textarea, select, button):focus-visible {
          outline: 2px solid #17685b !important; outline-offset: 2px;
        }
        @media (max-width: 480px) {
          .sf-tiktok-overlay { padding: 8px !important; }
          .sf-tiktok-product-dialog { max-height: calc(100dvh - 16px) !important; }
          .sf-tiktok-product-dialog > header, .sf-tiktok-product-dialog > footer,
          .sf-tiktok-product-dialog > .sf-tiktok-body { padding-left: 12px !important; padding-right: 12px !important; }
          .sf-tiktok-product-dialog input:not([type="checkbox"]),
          .sf-tiktok-product-dialog select, .sf-tiktok-product-dialog textarea { font-size: 16px !important; }
        }

        .sf-tiktok-product-dialog .sf-tiktok-fields { border: 0; margin: 0; padding: 0; min-width: 0; }
        .sf-tiktok-product-dialog .sf-tiktok-preview { margin: 0 0 10px; padding: 8px; border: 1px solid #dce7e1; border-radius: 8px; background: #f7faf8; }
        .sf-tiktok-product-dialog .sf-tiktok-preview figcaption { font-size: 12px; font-weight: 600; margin-bottom: 6px; }
        .sf-tiktok-product-dialog .sf-tiktok-preview img { display: block; width: 100%; height: 130px; object-fit: contain; }
        .sf-tiktok-product-dialog a { color: #17685b; text-decoration: underline; }
        .sf-tiktok-product-dialog input:disabled { opacity: .45; cursor: not-allowed; }
      `}</style>
      <header style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', padding: '22px 24px', borderBottom: '1px solid #e9efed' }}>
        <div>
          <div style={{ color: '#637571', fontSize: '13px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '.04em' }}>TikTok product publishing</div>
          <h3 id='tiktok-product-publish-title' style={{ margin: '5px 0 0', color: '#103b37' }}>Publish {job.productName}?</h3>
        </div>
        <button type='button' aria-label='Close TikTok publishing' disabled={busy} onClick={onClose}>×</button>
      </header>

      <div className="sf-tiktok-body" style={{ padding: '22px 24px' }}>
        {loading && <p role='status'>Loading the latest TikTok creator settings...</p>}
        {error && <p role='alert'>{error}</p>}
        {busy && <p role='status'>{progress}</p>}
        {!loading && creator && <fieldset disabled={busy} className='sf-tiktok-fields'>
          <p><strong>Destination:</strong> {creator.nickname || accountName || 'Connected TikTok account'}{creator.username ? ' (@' + creator.username + ')' : ''}</p>
          <p>TikTok requires you to review and choose the post settings immediately before publishing. The product photo itself is sent without StockFlow watermarks or promotional overlays.</p>


          <figure className='sf-tiktok-preview'>
            <figcaption>Photo to publish</figcaption>
            {photoUrl && !photoFailed && <img src={photoUrl} alt={'Product photo: ' + job.productName}
              referrerPolicy='no-referrer'
              onLoad={() => { setPhotoReady(true); setPhotoFailed(false); }}
              onError={() => { setPhotoReady(false); setPhotoFailed(true); }} />}
            {(!photoUrl || photoFailed) && <p role='alert'>The photo preview could not load. Close this window, check the connection, and reopen it before publishing.</p>}
            {photoUrl && !photoFailed && !photoReady && <p role='status'>Loading photo preview...</p>}
          </figure>

          <label>Title
            <input value={title} maxLength={90} onChange={event => setTitle(event.target.value)} />
          </label>

          <label>Description
            <textarea value={description} maxLength={4000} rows={5} onChange={event => setDescription(event.target.value)} />
          </label>

          <label>Audience
            <select value={privacy} onChange={event => setPrivacy(event.target.value)}>
              <option value=''>Choose an audience</option>
              {(creator.privacyOptions || []).map(option => <option
                key={option}
                value={option}
                disabled={branded && option === 'SELF_ONLY'}
                title={branded && option === 'SELF_ONLY' ? 'Branded content visibility cannot be set to private.' : undefined}
              >{PRIVACY_LABELS[option] || option}</option>)}
            </select>
          </label>
          <small>TikTok requires you to choose the audience yourself; StockFlow does not preselect it.</small>

          <label className="sf-tiktok-product-check" style={{ display: 'block', marginTop: '16px' }}>
            <input
              type='checkbox'
              checked={allowComments}
              disabled={creator.commentDisabled}
              onChange={event => setAllowComments(event.target.checked)}
            />{' '}
            Allow comments
          </label>
          {creator.commentDisabled && <small>TikTok has disabled comments for this account.</small>}

          <label className="sf-tiktok-product-check" style={{ display: 'block', marginTop: '12px' }}>
            <input type='checkbox' checked={autoAddMusic} onChange={event => setAutoAddMusic(event.target.checked)} />{' '}
            Let TikTok automatically add recommended music
          </label>

          <div className="sf-tiktok-disclosure" style={{ marginTop: '18px', padding: '14px', border: '1px solid #e0e8e6', borderRadius: '14px' }}>
            <label className="sf-tiktok-product-check" style={{ display: 'block' }}>
              <input
                type='checkbox'
                checked={disclosure}
                onChange={event => {
                  const checked = event.target.checked;
                  setDisclosure(checked);
                  if (!checked) { setOwnBrand(false); setBranded(false); }
                }}
              />{' '}
              Content disclosure: this post promotes a brand, product, or service
            </label>
            {disclosure && <div style={{ margin: '10px 0 0 22px' }}>
              <label className="sf-tiktok-product-check" style={{ display: 'block' }}>
                <input type='checkbox' checked={ownBrand} onChange={event => setOwnBrand(event.target.checked)} />{' '}
                Your brand / your own business
              </label>
              <label className="sf-tiktok-product-check" style={{ display: 'block', marginTop: '8px' }}>
                <input
                  type='checkbox'
                  checked={branded}
                  disabled={privacy === 'SELF_ONLY'}
                  onChange={event => setBranded(event.target.checked)}
                />{' '}
                Branded content / paid partnership
              </label>
              {!disclosureValid && <small role='alert'>Choose at least one commercial-content type.</small>}
              {ownBrand && !branded && <small style={{ display: 'block' }}>Your photo will be labeled as &apos;Promotional content&apos;.</small>}
              {branded && <small style={{ display: 'block' }}>Your photo will be labeled as &apos;Paid partnership&apos;.</small>}
              {privacy === 'SELF_ONLY' && <small>Branded content visibility cannot be set to private.</small>}
            </div>}
          </div>

          <label className="sf-tiktok-product-check" style={{ display: 'block', marginTop: '18px', fontWeight: 700 }}>
            <input type='checkbox' checked={consent} onChange={event => setConsent(event.target.checked)} />{' '}
            <span>By posting, you agree to TikTok&apos;s{' '}
              {branded && <><a href='https://www.tiktok.com/legal/page/global/bc-policy/en' target='_blank' rel='noopener noreferrer'>Branded Content Policy</a> and{' '}</>}
              <a href='https://www.tiktok.com/legal/page/global/music-usage-confirmation/en' target='_blank' rel='noopener noreferrer'>Music Usage Confirmation</a>.
            </span>
          </label>

          <p className="sf-tiktok-processing" style={{ marginTop: '16px' }}>After submission, TikTok may take a few minutes to process the post. StockFlow will keep the TikTok tracking ID so you can check the final status without creating a duplicate post.</p>
        </fieldset>}
      </div>

      <footer style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', padding: '18px 24px 24px', borderTop: '1px solid #edf1f0' }}>
        <button type='button' disabled={busy} onClick={onClose}>Cancel</button>
        <button type='button' disabled={!canPublish} title={!disclosureValid ? 'Indicate whether this content promotes your business, a third party, or both.' : undefined} onClick={publish}>{busy ? 'Publishing...' : 'Publish to TikTok'}</button>
      </footer>
    </section>
    </div>,
    document.body
  );
}
