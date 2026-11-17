import React, { useEffect, useRef, useState } from "react";
import "../styles/stockflow-install.css";

// Capture the browser event before React mounts, including on slower devices.
let installPrompt = null;
let installedThisVisit = false;
const subscribers = new Set();
const notify = () => subscribers.forEach((fn) => fn());
const capture = (event) => {
  event.preventDefault();
  installPrompt = event;
  notify();
};
const installed = () => {
  installedThisVisit = true;
  installPrompt = null;
  notify();
};
window.addEventListener("beforeinstallprompt", capture);
window.addEventListener("appinstalled", installed);
if (import.meta.hot) import.meta.hot.dispose(() => {
  window.removeEventListener("beforeinstallprompt", capture);
  window.removeEventListener("appinstalled", installed);
});
const standalone = () => window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;

export default function StockFlowInstall() {
  const [, refresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const dialog = useRef(null);
  const trigger = useRef(null);
  useEffect(() => {
    const update = () => refresh((n) => n + 1);
    const media = window.matchMedia("(display-mode: standalone)");
    subscribers.add(update);
    media.addEventListener("change", update);
    update();
    return () => { subscribers.delete(update); media.removeEventListener("change", update); };
  }, []);

  const close = () => { dialog.current?.close(); trigger.current?.focus(); };
  const install = async () => {
    if (!installPrompt || busy) return;
    const prompt = installPrompt;
    installPrompt = null;
    setBusy(true);
    setMessage("");
    try {
      await prompt.prompt();
      const choice = await prompt.userChoice;
      if (choice.outcome === "accepted") close();
      else { setMessage("Installation was cancelled. You can install later using your browser menu."); dialog.current?.showModal(); }
    } catch {
      setMessage("The installation prompt is unavailable. Use the steps below."); dialog.current?.showModal();
    } finally { setBusy(false); notify(); }
  };

  if (standalone() || installedThisVisit) return null;
  const appleMobile = /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const android = /Android/.test(navigator.userAgent);
  const edge = /Edg\//.test(navigator.userAgent);
  const safari = /Safari/.test(navigator.userAgent) && !/Chrome|Chromium|Edg/.test(navigator.userAgent);
  return (
    <div className="sf-install-ui">
      <button ref={trigger} type="button" className="sf-install-trigger" aria-haspopup="dialog"
        onClick={() => { setMessage(""); if (installPrompt) install(); else dialog.current?.showModal(); }} disabled={busy}>
        <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5" /></svg>
        {busy ? "Opening installer…" : "Install StockFlow"}
      </button>
      <dialog ref={dialog} className="sf-install-dialog" aria-labelledby="sf-install-title" aria-describedby="sf-install-description"
        onCancel={close} onClick={(event) => { if (event.target === dialog.current) close(); }}>
        <div className="sf-install-content">
          <div className="sf-install-heading"><h2 id="sf-install-title">Install StockFlow</h2><button type="button" onClick={close} aria-label="Close installation instructions" autoFocus>×</button></div>
          <p id="sf-install-description">Keep StockFlow on your home screen or desktop for quick access. An internet connection is required to manage your business.</p>
          {installPrompt && <button type="button" className="sf-install-now" onClick={install} disabled={busy}>{busy ? "Opening installer…" : "Install now"}</button>}
          <p role="status">{message}</p>
          <ol>
            {appleMobile ? <><li>Open StockFlow in Safari.</li><li>Tap Share, then Add to Home Screen.</li><li>Confirm Add.</li></> : android ? <><li>Open StockFlow in Chrome.</li><li>Tap the three-dot menu, then Install app or Add to Home screen.</li><li>Follow the installation instructions.</li></> : edge ? <><li>Open the three-dot menu in Edge.</li><li>Select Apps, then Install this site as an app.</li><li>Confirm Install.</li></> : safari ? <><li>Open the File menu in Safari.</li><li>Choose Add to Dock, if available.</li><li>Confirm Add.</li></> : <><li>Open StockFlow in Google Chrome.</li><li>Open the three-dot menu, then Cast, save, and share.</li><li>Choose Install page as app, then Install.</li></>}
          </ol>
          <p>If StockFlow is already installed, open it from your device’s apps.</p>
          <button type="button" className="sf-install-done" onClick={close}>Done</button>
        </div>
      </dialog>
    </div>
  );
}
