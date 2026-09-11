import ShopSocialPanel from './ShopSocialPanel';
import ShopOrdersPanel from './ShopOrdersPanel';
import ShopProductsPanel from './ShopProductsPanel';
import { useEffect, useRef, useState } from 'react';
import { useStore } from '../../context/StoreContext';
import { apiRequest } from '../../services/api';
import '../../styles/storefront.css';

export default function OnlineShopPage() {
  const { business, branches, branchesLoading, branchesError, loadBranches, activeBranchId } = useStore();
  if (!business?.id) return <p>Select a business first.</p>;
  if (business.currentUserRole !== 'owner') return <p>Only the business owner can manage shop publishing.</p>;
  return <ShopSettings key={business.id} business={business} branches={branches} branchesLoading={branchesLoading} branchesError={branchesError} reloadBranches={() => loadBranches(business.id, activeBranchId)} />;
}

function ShopSettings({ business, branches, branchesLoading, branchesError, reloadBranches }) {
  const [settings, setSettings] = useState(null);
  const [form, setForm] = useState({ branchId: '', introduction: '', contactPhone: '', whatsappEnabled: false, whatsappPhone: '', isPublished: false });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [retry, setRetry] = useState(0);
  const shopLinkRef = useRef(null);
  const [copyMessage, setCopyMessage] = useState('');
  const path = '/businesses/' + business.id + '/storefront/settings/';
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    apiRequest(path).then(result => {
      if (!active) return;
      setSettings(result);
      setForm({ branchId: result.branchId || '', introduction: result.introduction, contactPhone: result.contactPhone, whatsappEnabled: result.whatsappEnabled, whatsappPhone: result.whatsappPhone, isPublished: result.isPublished });
    }).catch(problem => { if (active) setError(problem.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [path, retry]);

  function change(field, value) {
    setForm(current => ({ ...current, [field]: value }));
    setMessage('');
  }

  async function save(event) {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const result = await apiRequest(path, { method: 'PATCH', body: JSON.stringify(form) });
      setSettings(result);
      setForm({ branchId: result.branchId, introduction: result.introduction, contactPhone: result.contactPhone, whatsappEnabled: result.whatsappEnabled, whatsappPhone: result.whatsappPhone, isPublished: result.isPublished });
      setMessage(result.isPublished ? 'Shop published. Only individually published products appear in the catalogue.' : 'Settings saved. Your shop is unpublished.');
    } catch (problem) { setError(problem.message); }
    finally { setSaving(false); }
  }

  const shopUrl = settings ? new URL(settings.shopPath, window.location.origin).href : '';
  async function copyLink() {
    if (!shopUrl) return;
    setCopyMessage('');
    if (window.isSecureContext && navigator.clipboard?.writeText) {
      try { await navigator.clipboard.writeText(shopUrl); setCopyMessage('Shop link copied.'); return; }
      catch { /* Fall back to selecting the visible link. */ }
    }
    const input = shopLinkRef.current;
    if (!input) return;
    input.focus();
    input.select();
    input.setSelectionRange(0, input.value.length);
    let copied = false;
    try { copied = document.execCommand('copy'); } catch {}
    setCopyMessage(copied ? 'Shop link copied.' : 'Link selected. Press Ctrl+C on your laptop, or touch and hold the link and choose Copy on your phone.');
  }

  return <section className='sf-shop sf-shop-admin'>
    <header><span className='sf-shop-eyebrow'>ONLINE SHOP</span><h1>{business.name}</h1><p>Manage the catalogue link customers can use to send orders.</p></header>
    {loading ? <p role='status'>Loading shop settings...</p> : <>
      {error && <p role='alert'>{error}</p>}
      {!settings ? <button type='button' onClick={() => setRetry(value => value + 1)}>Retry loading settings</button> : <>
        <p><strong>{settings.isPublished ? 'Published' : 'Unpublished'}</strong></p>
        <form className='sf-shop-cart' onSubmit={save}>
          <fieldset disabled={saving}>
            <div>
              {branchesLoading && <p role='status'>Loading branches...</p>}
              {branchesError && <p role='alert'>{branchesError}</p>}
              {!branchesLoading && !branches.length && <p>No branches loaded. Reload to try again.</p>}
              <button type='button' disabled={branchesLoading} onClick={() => { setError(''); reloadBranches().catch(problem => setError(problem.message)); }}>Reload branches</button>
            </div>
            <label>Fulfilment branch<select required disabled={branchesLoading} value={form.branchId} onChange={event => change('branchId', event.target.value)}><option value=''>Choose a branch</option>{branches.map(branch => <option key={branch.id} value={branch.id}>{branch.name}</option>)}</select></label>
            <p>New orders use this branch. Existing orders retain their original branch.</p>
            <label>Shop introduction<textarea rows={3} maxLength={500} value={form.introduction} onChange={event => change('introduction', event.target.value)} /></label>
            <label>Public contact phone<input type='tel' maxLength={30} value={form.contactPhone} onChange={event => change('contactPhone', event.target.value)} /></label>
            <div className='sf-shop-whatsapp-settings'>
              <h3>WhatsApp enquiries</h3>
              <label>WhatsApp number<input type='tel' maxLength={30} value={form.whatsappPhone} onChange={event => change('whatsappPhone', event.target.value)} placeholder='e.g. 0542777495' /></label>
              <label className='sf-shop-toggle'><input type='checkbox' checked={form.whatsappEnabled} onChange={event => change('whatsappEnabled', event.target.checked)} />Enable WhatsApp enquiries on my online shop</label>
              <p>This is off by default. When enabled, customers can open a WhatsApp chat with this number from your public shop. This does not enable automated WhatsApp alerts or require Meta API credentials.</p>
            </div>
            <label className='sf-shop-toggle'><input type='checkbox' checked={form.isPublished} onChange={event => change('isPublished', event.target.checked)} />Publish this shop</label>
            <p>Publishing makes your shop introduction, contact phone and published listings publicly accessible.</p>
            <button type='submit'>{saving ? 'Saving...' : 'Save shop settings'}</button>
          </fieldset>
        </form>
        {settings.configured && <div className='sf-shop-cart'><h2>Your shop link</h2><input aria-label='Shop link' ref={shopLinkRef} readOnly value={shopUrl} onFocus={event => event.target.select()} /><div className='sf-shop-admin-actions'><button type='button' onClick={copyLink}>Copy link</button><span role='status'>{copyMessage}</span><a href={shopUrl} target='_blank' rel='noopener noreferrer'>Open shop</a></div><p>{settings.isPublished ? 'Share this link with customers when your catalogue is ready.' : 'The public page remains unavailable until you publish the shop.'}</p><p>Localhost links work on this computer. A public deployment is needed before customers can open the link on their own devices.</p></div>}
      </>}
    </>}
    {settings?.configured && !loading && <ShopSocialPanel key={business.id} businessId={business.id} />}
    {settings?.configured && !loading && <ShopProductsPanel businessId={business.id} />}
    {settings?.configured && !loading && <ShopOrdersPanel businessId={business.id} branches={branches} />}
    {message && <p role='status'>{message}</p>}
  </section>;
}
