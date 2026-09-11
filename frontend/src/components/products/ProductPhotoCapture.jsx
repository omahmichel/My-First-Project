import { createContext, useContext, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Camera, Upload } from 'lucide-react';
import { useStore } from '../../context/StoreContext';
import { apiRequest } from '../../services/api';
import './product-photo.css';

function mobileCameraDevice() {
  return /Android|iPhone|iPad|iPod/i.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
}

function paint(canvas, image, { aspect, zoom, x, y, angle, quarter }, size = 720) {
  const radians = (angle + quarter * 90) * Math.PI / 180;
  const boundWidth = Math.abs(image.width * Math.cos(radians)) + Math.abs(image.height * Math.sin(radians));
  const boundHeight = Math.abs(image.width * Math.sin(radians)) + Math.abs(image.height * Math.cos(radians));
  const ratio = aspect === 'original' ? boundWidth / boundHeight : Number(aspect);
  const width = Math.max(1, ratio >= 1 ? size : Math.round(size * ratio));
  const height = Math.max(1, ratio >= 1 ? Math.round(size / ratio) : size);
  if (canvas.width !== width) canvas.width = width;
  if (canvas.height !== height) canvas.height = height;
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

function ProductPhotoEditor({ product, initialFile, onDismiss, onNotice }) {
  const { business, activeBranchId, loadInventory } = useStore();
  const cameraRef = useRef(null);
  const fileRef = useRef(null);
  const dialogRef = useRef(null);
  const canvasRef = useRef(null);
  const alive = useRef(true);
  const working = useRef(false);
  const editorWanted = useRef(false);
  const photoUrl = useRef(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [image, setImage] = useState(null);
  const [edit, setEdit] = useState(INITIAL);

  const mobile = mobileCameraDevice();
  const allowed = ['owner', 'manager', 'inventory_clerk'].includes(business?.currentUserRole);
  const base = '/businesses/' + business?.id + '/products/' + product.id + '/photo/';

  function releasePhoto() {
    if (photoUrl.current) URL.revokeObjectURL(photoUrl.current);
    photoUrl.current = null;
  }

  function closeEditor() {
    editorWanted.current = false;
    setOpen(false);
    setImage(null);
    releasePhoto();
    onDismiss();
  }

  function keepEditorOpen() {
    const dialog = dialogRef.current;
    if (alive.current && editorWanted.current && dialog?.isConnected && !dialog.open) {
      dialog.showModal();
    }
  }

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      if (photoUrl.current) URL.revokeObjectURL(photoUrl.current);
      photoUrl.current = null;
    };
  }, []);
  useEffect(() => {
    if (open) keepEditorOpen();
  }, [open]);
  useEffect(() => {
    if (!open || !image) return;
    const frame = requestAnimationFrame(() => {
      if (!canvasRef.current) return;
      try { paint(canvasRef.current, image, edit); }
      catch { setError('Could not draw the preview. Retake the photo or choose another image.'); }
    });
    return () => cancelAnimationFrame(frame);
  }, [open, image, edit]);

  useEffect(() => {
    // A session is owned by the page, independently of the selected product card.
    preparePhoto(initialFile);
  }, [initialFile]);

  function selectPhoto(event) {
    const file = event.target.files?.[0];
    event.target.value = '';
    preparePhoto(file);
  }

  async function preparePhoto(file) {
    if (!file || working.current) return;
    editorWanted.current = true;
    setOpen(true);
    setError('');

    setImage(null);
    releasePhoto();
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
      if (alive.current && editorWanted.current) {
        photoUrl.current = url;
        url = null; // Keep the source alive throughout cropping, including mobile redraws.
        setImage(loaded);
        setEdit(INITIAL);
      }
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
      // Render the current controls directly; a pending preview frame cannot affect upload.
      const output = document.createElement('canvas');
      paint(output, image, edit, 1800);
      const blob = await new Promise(resolve => output.toBlob(resolve, 'image/jpeg', 0.92));
      output.width = output.height = 1;
      if (!blob) throw new Error('The photo could not be prepared. Please try again.');
      const form = new FormData();
      form.append('image', blob, 'product.jpg');
      if (activeBranchId) form.append('branchId', activeBranchId);
      await apiRequest(base, { method: 'POST', body: form });
      if (alive.current) { closeEditor(); onNotice('Photo saved.'); }
      try { await loadInventory(business.id, activeBranchId); }
      catch { onNotice('Photo saved. Refresh inventory to see it.'); }
    } catch (problem) { if (alive.current) setError(problem.message); }
    finally { working.current = false; if (alive.current) setBusy(false); }
  }

  if (!allowed) return null;
  return <>
    {open && createPortal(<dialog ref={dialogRef} className='sf-photo-dialog'
      aria-labelledby={'photo-title-' + product.id}
      onCancel={event => { event.preventDefault(); event.stopPropagation(); }}
      onClose={keepEditorOpen}>
    <input ref={cameraRef} type='file' accept='image/*' capture='environment' hidden onChange={selectPhoto} />
    <input ref={fileRef} type='file' accept='image/*,.heic,.heif' hidden onChange={selectPhoto} />
      <header><h2 id={'photo-title-' + product.id}>Product photo</h2><p>{product.name}{product.designCode ? ' · Design ' + product.designCode : ''}</p></header>
      <p>Frame the whole product, straighten it if needed, then tap Use photo &amp; upload. Take your time; tap Cancel to discard.</p>
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
        <button type='button' disabled={busy} onClick={closeEditor}>Cancel</button>
        <button type='button' className='sf-photo-confirm' disabled={busy || !image} onClick={upload}>Use photo &amp; upload</button>
      </footer>
    </dialog>, document.body)}
  </>;
}

// Keep the working editor outside the filtered/reloaded product grid.
const PhotoSessionContext = createContext(null);

function PhotoSessionHost({ children }) {
  const [session, setSession] = useState(null);
  const [notice, setNotice] = useState('');
  const { business } = useStore();
  const allowed = ['owner', 'manager', 'inventory_clerk'].includes(business?.currentUserRole);
  return <PhotoSessionContext.Provider value={(product, file) => {
    if (!file || session || !allowed) return;
    setNotice('');
    setSession({ product: { ...product }, file });
  }}>
    {children}
    {notice && <p role='status' className='form-alert'>{notice}</p>}
    {session && allowed && <ProductPhotoEditor
      product={session.product} initialFile={session.file}
      onDismiss={() => setSession(null)} onNotice={setNotice} />}
  </PhotoSessionContext.Provider>;
}

export function ProductPhotoSessionProvider({ children }) {
  const { business, activeBranchId } = useStore();
  // Switching workspace intentionally ends editing to prevent cross-business uploads.
  return <PhotoSessionHost key={String(business?.id) + ':' + String(activeBranchId)}>
    {children}
  </PhotoSessionHost>;
}

export default function ProductPhotoCapture({ product, disabled = false }) {
  const startSession = useContext(PhotoSessionContext);
  const { business } = useStore();
  const fileRef = useRef(null);
  const mobile = mobileCameraDevice();
  const allowed = ['owner', 'manager', 'inventory_clerk'].includes(business?.currentUserRole);
  if (!allowed) return null;
  return <>
    <button type='button' className='sf-photo-trigger' disabled={disabled || !startSession}
      title={mobile ? 'Take product photo' : 'Upload product photo'}
      aria-label={(mobile ? 'Take photo of ' : 'Upload photo for ') + product.name}
      onClick={event => { event.stopPropagation(); fileRef.current.click(); }}>
      {mobile ? <Camera size={18} /> : <Upload size={18} />}
    </button>
    <input ref={fileRef} type='file' accept='image/*,.heic,.heif'
      capture={mobile ? 'environment' : undefined} hidden
      onChange={event => {
        const file = event.target.files?.[0];
        event.target.value = '';
        if (file) startSession(product, file);
      }} />
  </>;
}
