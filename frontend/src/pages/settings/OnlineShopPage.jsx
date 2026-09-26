import ShopSocialPanel from './ShopSocialPanel';
import ShopOrdersPanel from './ShopOrdersPanel';
import ShopProductsPanel from './ShopProductsPanel';
import { useEffect, useRef, useState } from 'react';
import { useStore } from '../../context/StoreContext';
import { apiRequest } from '../../services/api';
import '../../styles/storefront.css';
import '../../styles/online-shop-workspace.css';

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

  return <section className='sf-shop sf-shop-admin sf-shop-workspace'>
    <header className='sf-shop-workspace-hero'>
      <div><span className='sf-shop-eyebrow'>ONLINE SHOP · MANAGEMENT</span><h1>{business.name}</h1><p>Set up your shop, prepare your catalogue and manage customer orders in one place.</p></div>
      {settings && <span className={'sf-shop-visibility ' + (settings.isPublished ? 'is-live' : '')}>{settings.isPublished ? 'Shop published' : 'Shop unpublished'}</span>}
    </header>
    <div className='sf-shop-workspace-layout'>
      <nav className='sf-shop-section-nav' aria-label='Online shop sections'>
        <p>YOUR SHOP WORKSPACE</p>
        {[
          ['setup', '01', 'Shop settings', 'Branch, contact & visibility'],
          ['link', '02', 'Customer link', 'Open and share your shop'],
          ['products', '03', 'Product catalogue', 'Manage published listings'],
          ['social', '04', 'Social publishing', 'Connections & publishing records'],
          ['orders', '05', 'Customer orders', 'Review and fulfil requests'],
        ].map(([id, number, title, detail]) => (
          id === 'setup' || (settings?.configured && !loading)
            ? <a key={id} href={'#sf-shop-' + id}><span>{number}</span><div><strong>{title}</strong><small>{detail}</small></div></a>
            : <div key={id} className='sf-shop-nav-unavailable'><span>{number}</span><div><strong>{title}</strong><small>Available after shop setup</small></div></div>
        ))}
      </nav>
      <div className='sf-shop-workspace-content'>
        <section id='sf-shop-setup' aria-labelledby='sf-shop-setup-title' className='sf-shop-card-section'>
          <header className='sf-shop-section-heading'><span>01</span><div><h2 id='sf-shop-setup-title'>Shop settings</h2><p>Choose your fulfilment branch and how customers can reach you.</p></div></header>
          {loading ? <p role='status'>Loading shop settings...</p> : <>
            {error && <p role='alert'>{error}</p>}
            {!settings ? <button type='button' onClick={() => setRetry(value => value + 1)}>Retry loading settings</button> : <>
              <form className='sf-shop-cart sf-shop-settings-form' onSubmit={save}>
                <fieldset disabled={saving}>
                  <div className='sf-shop-settings-grid'>
                    <div className='sf-shop-setting-block'>
                      <h3>Shop details</h3>
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
                    </div>
                    <div className='sf-shop-setting-block'>
                      <h3>WhatsApp enquiries</h3>
                      <p>Give customers a direct way to ask about your products.</p>
                      <label>WhatsApp number<input type='tel' maxLength={30} value={form.whatsappPhone} onChange={event => change('whatsappPhone', event.target.value)} placeholder='e.g. 0542777495' /></label>
                      <label className='sf-shop-toggle'><input type='checkbox' checked={form.whatsappEnabled} onChange={event => change('whatsappEnabled', event.target.checked)} />Enable WhatsApp enquiries on my online shop</label>
                      <p>Customers can open a WhatsApp chat with this number from your public shop. This setting does not send automated alerts.</p>
                    </div>
                  </div>
                  <div className='sf-shop-visibility-setting'>
                    <h3>Shop visibility</h3>
                    <label className='sf-shop-toggle'><input type='checkbox' checked={form.isPublished} onChange={event => change('isPublished', event.target.checked)} />Publish this shop</label>
                    <p>Publishing makes your introduction, contact phone and individually published products public. Save below to apply your changes.</p>
                  </div>
                  <div className='sf-shop-save-bar'><span>Changes take effect when you save.</span><button type='submit'>{saving ? 'Saving...' : 'Save shop settings'}</button></div>
                </fieldset>
              </form>
              {message && <p role='status'>{message}</p>}
            </>}
          </>}
        </section>
        {settings?.configured && !loading && <>
          <section id='sf-shop-link' aria-labelledby='sf-shop-link-title' className='sf-shop-card-section'>
            <header className='sf-shop-section-heading'><span>02</span><div><h2 id='sf-shop-link-title'>Your customer link</h2><p>Open your storefront or copy the link to share it.</p></div></header>
            <label className='sf-shop-link-label'>Shop address<input aria-label='Shop link' ref={shopLinkRef} readOnly value={shopUrl} onFocus={event => event.target.select()} /></label>
            <div className='sf-shop-admin-actions'><button type='button' onClick={copyLink}>Copy link</button><a href={shopUrl} target='_blank' rel='noopener noreferrer'>Open shop ↗</a><span role='status'>{copyMessage}</span></div>
            <p>{settings.isPublished ? 'Share this link with customers when your catalogue is ready.' : 'The public page remains unavailable until you publish the shop.'}</p>
            <p className='sf-shop-help-note'>Localhost links work on this computer. A public deployment is needed before customers can open the link on their own devices.</p>
          </section>
          <ShopProductsPanel businessId={business.id} />
          <ShopSocialPanel key={business.id} businessId={business.id} />
          <ShopOrdersPanel businessId={business.id} branches={branches} />
        </>}
      </div>
    </div>
  </section>;
}
