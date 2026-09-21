import { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { MoreVertical, Trash2, X } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { apiRequest } from '../../services/api';
import './shop-media-actions.css';

// Resolve the viewed shop against server-returned memberships, independently
// of whichever business is selected in the private workspace.
export function useShopMediaManager(slug) {
  const { user, isInitializing } = useAuth();
  const [access, setAccess] = useState(null);
  useEffect(() => {
    const controller = new AbortController();
    setAccess(null);
    if (!user?.id || isInitializing) return () => controller.abort();
    apiRequest('/businesses/', { signal: controller.signal }).then(response => {
      if (controller.signal.aborted) return;
      const businesses = Array.isArray(response) ? response : response?.results || [];
      const business = businesses.find(item => item.slug === slug &&
        ['owner', 'manager', 'inventory_clerk'].includes(item.current_user_role) &&
        item.hasSystemAccess === true);
      if (business) setAccess({ businessId: business.id, userId: user.id, slug });
    }).catch(() => { /* Public browsing continues without management controls. */ });
    return () => controller.abort();
  }, [slug, user?.id, isInitializing]);
  return !isInitializing && access?.userId === user?.id && access?.slug === slug ? access : null;
}


export default function ShopMediaActions({ product, manager, kind, onDeleted }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const lock = useRef(false);
  const dialog = useRef(null);
  const menu = useRef(null);
  const titleId = useId();
  const descriptionId = useId();
  const label = kind === 'photo' ? 'photo' : 'video';
  useEffect(() => {
    if (!open || !dialog.current) return;
    dialog.current.showModal();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = previousOverflow; };
  }, [open]);
  function close() {
    if (lock.current) return;
    dialog.current?.close();
    setOpen(false);
    setError('');
    menu.current?.querySelector('summary')?.focus();
  }
  async function remove() {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError('');
    try {
      await apiRequest('/businesses/' + encodeURIComponent(manager.businessId) +
        '/products/' + encodeURIComponent(product.productId) + '/' + label + '/', { method: 'DELETE' });
    } catch (problem) {
      setError(problem.message || 'The ' + label + ' could not be deleted. Please try again.');
      lock.current = false;
      setBusy(false);
      return;
    }
    lock.current = false;
    setBusy(false);
    close();
    onDeleted(product);
  }
  return <>
    <div className="sf-media-actions">
      <details ref={menu} onKeyDown={event => {
        if (event.key === 'Escape') { menu.current.open = false; menu.current.querySelector('summary')?.focus(); }
      }}>
        <summary aria-label={label + ' options for ' + product.name}><MoreVertical size={21} /></summary>
        <button type="button" className="sf-media-delete-option" onClick={() => {
          menu.current.open = false; setError(''); setOpen(true);
        }}><Trash2 size={17} />Delete {label}</button>
      </details>
    </div>
    {open && createPortal(<dialog ref={dialog} className="sf-media-dialog" aria-labelledby={titleId}
      aria-describedby={descriptionId} aria-busy={busy} onCancel={event => { event.preventDefault(); close(); }}>
      <div className="sf-media-dialog-header">
        <span className="sf-media-delete-icon"><Trash2 size={25} /></span>
        <button type="button" className="sf-media-close" aria-label="Close confirmation" disabled={busy} onClick={close}><X size={21} /></button>
      </div>
      <h2 id={titleId}>Delete this {label}?</h2>
      <p className="sf-media-product-name">{product.name}</p>
      <p id={descriptionId}>{label === 'photo'
        ? 'This removes the product photo from StockFlow and the online shop. Your product and video will remain.'
        : 'This removes the uploaded video from StockFlow and the online shop. Your product and photo will remain.'}</p>
      <p className="sf-media-delete-note">You can upload a replacement later.</p>
      {error && <p role="alert" className="sf-media-delete-error">{error}</p>}
      <div className="sf-media-dialog-buttons">
        <button type="button" className="sf-media-cancel" autoFocus disabled={busy} onClick={close}>Keep {label}</button>
        <button type="button" className="sf-media-confirm" disabled={busy} onClick={remove} aria-live="polite">
          {busy ? 'Deleting…' : 'Delete ' + label}
        </button>
      </div>
    </dialog>, document.body)}
  </>;
}
