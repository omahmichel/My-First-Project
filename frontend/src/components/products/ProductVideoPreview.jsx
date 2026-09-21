import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { apiRequest } from '../../services/api';

export default function ProductVideoPreview({ product, disabled = false }) {
  const [open, setOpen] = useState(false);
  const [src, setSrc] = useState(product.videoUrl || '');
  const [error, setError] = useState('');
  const attempted = useRef(false);

  useEffect(() => {
    setSrc(product.videoUrl || '');
    attempted.current = false;
  }, [product.videoUrl]);

  if (!product.hasVideo || !src) return null;

  async function recover() {
    if (attempted.current) {
      setError('This video preview expired. Refresh the product list and try again.');
      return;
    }
    attempted.current = true;
    try {
      const query = product.branchId
        ? '?branchId=' + encodeURIComponent(product.branchId)
        : '';
      const data = await apiRequest(
        '/businesses/' + product.businessId + '/products/' + product.id + '/' + query,
      );
      if (data.videoUrl) {
        setSrc(data.videoUrl);
        setError('');
        return;
      }
    } catch {
      // Fall through to a readable message.
    }
    setError('The product video could not be loaded.');
  }

  return <>
    <button
      type='button'
      disabled={disabled}
      aria-label={'Preview video for ' + product.name}
      title='Preview product video'
      onClick={event => {
        event.preventDefault();
        event.stopPropagation();
        setError('');
        setOpen(true);
      }}
      style={{
        position: 'absolute',
        zIndex: 3,
        left: '10px',
        bottom: '10px',
        minHeight: '34px',
        padding: '7px 10px',
        border: '1px solid #c8dedb',
        borderRadius: '10px',
        background: '#075d54',
        color: '#fff',
        fontSize: '11px',
        fontWeight: 800,
        boxShadow: '0 2px 6px #0002',
      }}
    >
      ▶ Video
    </button>

    {open && createPortal(
      <div
        role='presentation'
        onClick={() => setOpen(false)}
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 13000,
          display: 'grid',
          placeItems: 'center',
          padding: '18px',
          background: 'rgba(6, 31, 28, .82)',
        }}
      >
        <section
          role='dialog'
          aria-modal='true'
          aria-label={'Video preview for ' + product.name}
          onClick={event => event.stopPropagation()}
          style={{
            width: 'min(720px, 96vw)',
            maxHeight: '92dvh',
            overflow: 'auto',
            padding: '16px',
            borderRadius: '18px',
            background: '#fff',
            boxShadow: '0 24px 80px #0006',
          }}
        >
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
            marginBottom: '12px',
          }}>
            <strong>{product.name}</strong>
            <button type='button' onClick={() => setOpen(false)}>Close</button>
          </div>

          <video
            key={src}
            src={src}
            controls
            playsInline
            preload='metadata'
            onError={recover}
            style={{
              display: 'block',
              width: '100%',
              maxHeight: '72dvh',
              borderRadius: '12px',
              background: '#000',
            }}
          />

          {error && <p role='alert' style={{ color: '#aa3025' }}>{error}</p>}
        </section>
      </div>,
      document.body,
    )}
  </>;
}
