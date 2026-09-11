import { useEffect, useRef, useState } from 'react';
import { apiRequest } from '../../services/api';

export default function ProductPhotoThumbnail({ product }) {
  const [src, setSrc] = useState(product.imageUrl);
  const [failed, setFailed] = useState(false);
  const active = useRef(true);
  const attempted = useRef(false);

  useEffect(() => {
    active.current = true;
    return () => { active.current = false; };
  }, []);

  async function recover() {
    // One authenticated renewal per mounted thumbnail; never loop on a missing file.
    if (attempted.current || !src || !src.includes('preview=')) {
      setFailed(true);
      return;
    }
    attempted.current = true;
    setFailed(true);
    try {
      const query = product.branchId ? '?branchId=' + encodeURIComponent(product.branchId) : '';
      const data = await apiRequest('/businesses/' + product.businessId + '/products/' + product.id + '/' + query);
      if (!active.current) return;
      if (data.imageUrl && data.imageUrl !== src) {
        setSrc(data.imageUrl);
        setFailed(false);
      }
    } catch {
      // A missing file, lost access or network error leaves the design-code placeholder.
      if (active.current) setFailed(true);
    }
  }

  if (failed || !src) return null;
  return <img src={src} alt={product.name} loading='lazy' onError={recover} />;
}
