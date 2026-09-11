import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Camera, Upload } from 'lucide-react';
import { useStore } from '../../context/StoreContext';
import { apiRequest } from '../../services/api';
import './product-photo.css';

function mobileCameraDevice() {
  return /Android|iPhone|iPad|iPod/i.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
}

function paint(canvas, image, { aspect, zoom, x, y, angle, quarter }) {
  const radians = (angle + quarter * 90) * Math.PI / 180;
  const boundWidth = Math.abs(image.width * Math.cos(radians)) + Math.abs(image.height * Math.sin(radians));
  const boundHeight = Math.abs(image.width * Math.sin(radians)) + Math.abs(image.height * Math.cos(radians));
  const ratio = aspect === 'original' ? boundWidth / boundHeight : Number(aspect);
  canvas.width = ratio >= 1 ? 1800 : Math.round(1800 * ratio);
  canvas.height = ratio >= 1 ? Math.round(1800 / ratio) : 1800;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.save();
  ctx.translate(canvas.width * (0.5 + x / 200), canvas.height * (0.5 + y / 200));
  ctx.rotate(radians);
  const scale = Math.min(canvas.width / boundWidth, canvas.height / boundHeight) * zoom;
  ctx.scale(scale, scale);
  ctx.drawImage(image, -image.width / 2, -image.height / 2);
  ctx.restore();
}

const INITIAL = { aspect: 'original', zoom: 1, x: 0, y: 0, angle: 0, quarter: 0 };

export default function ProductPhotoCapture({ product, disabled = false }) {
  const { business, activeBranchId, loadInventory } = useStore();
  const cameraRef = useRef(null);
  const fileRef = useRef(null);
  const dialogRef = useRef(null);
  const canvasRef = useRef(null);
  const alive = useRef(true);
  const working = useRef(false);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [image, setImage] = useState(null);
  const [edit, setEdit] = useState(INITIAL);
  const [message, setMessage] = useState('');
  const mobile = mobileCameraDevice();
  const allowed = ['owner', 'manager', 'inventory_clerk'].includes(business?.currentUserRole);
  const base = '/businesses/' + business?.id + '/products/' + product.id + '/photo/';

  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => {
    if (open && dialogRef.current && !dialogRef.current.open) dialogRef.current.showModal();
  }, [open]);
  useEffect(() => { if (open && image && canvasRef.current) paint(canvasRef.current, image, edit); }, [open, image, edit]);

  async function selectPhoto(event) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file || working.current) return;
    setOpen(true);
    setError('');
    setMessage('');
    setImage(null);
    if (file.size > 20 * 1024 * 1024) { setError('Choose a photo no larger than 20 MB.'); return; }
    working.current = true;
    setBusy(true);
    let url;
    try {
      const form = new FormData();
      form.append('image', file);
      if (activeBranchId) form.append('branchId', activeBranchId);
      // Server converts HEIC and strips metadata; preparation never saves a product photo.
      const blob = await apiRequest(base + 'prepare/', { method: 'POST', body: form, responseType: 'blob' });
      url = URL.createObjectURL(blob);
      const loaded = new Image();
      await new Promise((resolve, reject) => {
        loaded.onload = resolve;
        loaded.onerror = () => reject(new Error('Could not preview this photo. Try a JPEG image.'));
        loaded.src = url;
      });
      if (alive.current) { setImage(loaded); setEdit(INITIAL); }
    } catch (problem) { if (alive.current) setError(problem.message); }
    finally {
      if (url) URL.revokeObjectURL(url);
      working.current = false;
      if (alive.current) setBusy(false);
    }
  }

  async function upload() {
    if (!image || working.current) return;
    working.current = true;
    setBusy(true);
    setError('');
    try {
      const blob = await new Promise(resolve => canvasRef.current.toBlob(resolve, 'image/jpeg', 0.92));
      if (!blob) throw new Error('The photo could not be prepared. Please try again.');
      const form = new FormData();
      form.append('image', blob, 'product.jpg');
      if (activeBranchId) form.append('branchId', activeBranchId);
      await apiRequest(base, { method: 'POST', body: form });
      if (alive.current) { setOpen(false); setImage(null); setMessage('Photo saved.'); }
      try { await loadInventory(business.id, activeBranchId); }
      catch { if (alive.current) setMessage('Photo saved. Refresh inventory to see it.'); }
    } catch (problem) { if (alive.current) setError(problem.message); }
    finally { working.current = false; if (alive.current) setBusy(false); }
  }

  if (!allowed) return null;
  return <>
    <button type='button' className='sf-photo-trigger' disabled={disabled || busy}
      title={mobile ? 'Take product photo' : 'Upload product photo'}
      aria-label={(mobile ? 'Take photo of ' : 'Upload photo for ') + product.name}
      onClick={event => { event.stopPropagation(); (mobile ? cameraRef : fileRef).current.click(); }}>
      {mobile ? <Camera size={18} /> : <Upload size={18} />}
    </button>
    {!open && <>
    <input ref={cameraRef} type='file' accept='image/*' capture='environment' hidden onChange={selectPhoto} />
    <input ref={fileRef} type='file' accept='image/*,.heic,.heif' hidden onChange={selectPhoto} />
    </>}
    {message && <span className='sf-photo-saved' role='status'>{message}</span>}
    {open && createPortal(<dialog ref={dialogRef} className='sf-photo-dialog'
      aria-labelledby={'photo-title-' + product.id}
      onCancel={event => { event.preventDefault(); if (!working.current) { setOpen(false); setImage(null); } }}>
    <input ref={cameraRef} type='file' accept='image/*' capture='environment' hidden onChange={selectPhoto} />
    <input ref={fileRef} type='file' accept='image/*,.heic,.heif' hidden onChange={selectPhoto} />
      <header><h2 id={'photo-title-' + product.id}>Product photo</h2><p>{product.name}{product.designCode ? ' · Design ' + product.designCode : ''}</p></header>
      <p>Frame the whole product, straighten it if needed, then tap Use photo &amp; upload.</p>
      {busy && <p role='status'>Preparing or uploading your photo...</p>}
      {error && <p role='alert' className='sf-photo-error'>{error}</p>}
      {image && <>
        <canvas ref={canvasRef} className='sf-photo-preview' aria-label='Preview of the photo that will be saved' />
        <fieldset disabled={busy} className='sf-photo-controls'>
          <label>Crop shape<select value={edit.aspect} onChange={e => setEdit(v => ({ ...v, aspect: e.target.value }))}>
            <option value='original'>Full photo</option><option value='1'>Square</option><option value='0.8'>Portrait</option><option value='1.333333'>Landscape</option>
          </select></label>
          <label>Zoom<input type='range' min='1' max='3' step='0.01' value={edit.zoom} onChange={e => setEdit(v => ({ ...v, zoom: Number(e.target.value) }))} /></label>
          <label>Move left / right<input type='range' min='-100' max='100' value={edit.x} onChange={e => setEdit(v => ({ ...v, x: Number(e.target.value) }))} /></label>
          <label>Move up / down<input type='range' min='-100' max='100' value={edit.y} onChange={e => setEdit(v => ({ ...v, y: Number(e.target.value) }))} /></label>
          <label>Straighten ({edit.angle}°)<input type='range' min='-15' max='15' step='0.5' value={edit.angle} onChange={e => setEdit(v => ({ ...v, angle: Number(e.target.value) }))} /></label>
          <button type='button' onClick={() => setEdit(v => ({ ...v, quarter: (v.quarter + 1) % 4 }))}>Rotate 90°</button>
          <button type='button' onClick={() => setEdit(INITIAL)}>Reset crop</button>
        </fieldset>
        <p>This replaces the product photo in sales and its online listing. It does not change the product's publishing setting.</p>
      </>}
      <footer>
        {mobile && <button type='button' disabled={busy} onClick={() => cameraRef.current.click()}>Retake photo</button>}
        <button type='button' disabled={busy} onClick={() => fileRef.current.click()}>Upload from device</button>
        <button type='button' disabled={busy} onClick={() => { setOpen(false); setImage(null); }}>Cancel</button>
        <button type='button' className='sf-photo-confirm' disabled={busy || !image} onClick={upload}>Use photo &amp; upload</button>
      </footer>
    </dialog>, document.body)}
  </>;
}
