import { useState } from 'react';
import { resolveShopMediaUrl } from '../../services/storefront';

export default function ShopProductMedia({ product }) {
  const [photoFailed, setPhotoFailed] = useState(false);
  const photo = resolveShopMediaUrl(product.imageUrl);
  return <div className="sf-shop-image">
    {photo && !photoFailed ? <img
      src={photo}
      alt={product.name}
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setPhotoFailed(true)}
    /> : <span>{product.name.slice(0, 1)}</span>}
  </div>;
}
