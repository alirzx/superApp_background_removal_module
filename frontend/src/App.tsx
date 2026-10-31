import { useCallback, useEffect, useRef, useState } from 'react';

type Status = 'idle' | 'working' | 'done' | 'error';
type Mode = 'remove-background' | 'mask';
const MAX_BYTES = 10 * 1024 * 1024;

function humanSize(size: number): string { return `${(size / 1024 / 1024).toFixed(2)} MB`; }

function App() {
  const [source, setSource] = useState<File | null>(null);
  const [sourceUrl, setSourceUrl] = useState<string | null>(null);
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [resultBlob, setResultBlob] = useState<Blob | null>(null);
  const [status, setStatus] = useState<Status>('idle');
  const [message, setMessage] = useState('');
  const [mode, setMode] = useState<Mode>('remove-background');
  const [blur, setBlur] = useState(0);
  const [background, setBackground] = useState('#ffffff');
  const [busyDrag, setBusyDrag] = useState(false);
  const [inferenceMs, setInferenceMs] = useState<string | null>(null);
  const [apiStatus, setApiStatus] = useState('در حال بررسی');
  const pickerRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const getStatus = async () => {
      try {
        const resp = await fetch('/api/health/ready', { cache: 'no-store' });
        setApiStatus(resp.ok ? 'سرویس آماده است' : 'مدل هنوز آماده نیست');
      } catch { setApiStatus('ارتباط با API برقرار نیست'); }
    };
    void getStatus();
    const timer = window.setInterval(() => void getStatus(), 15000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    return () => { abortRef.current?.abort(); };
  }, []);

  useEffect(() => {
    return () => { if (sourceUrl) URL.revokeObjectURL(sourceUrl); };
  }, [sourceUrl]);
  useEffect(() => {
    return () => { if (resultUrl) URL.revokeObjectURL(resultUrl); };
  }, [resultUrl]);

  const receiveFile = useCallback((file: File) => {
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) { setMessage('فقط فرمت‌های PNG، JPEG و WebP پشتیبانی می‌شوند.'); setStatus('error'); return; }
    if (file.size > MAX_BYTES) { setMessage('حداکثر حجم تصویر ۱۰ مگابایت است.'); setStatus('error'); return; }
    abortRef.current?.abort();
    setSource(file);
    setSourceUrl(URL.createObjectURL(file));
    setResultUrl(null);
    setResultBlob(null);
    setInferenceMs(null);
    setStatus('idle');
    setMessage('تصویر آماده پردازش است.');
  }, []);

  async function processImage() {
    if (!source || status === 'working') return;
    const controller = new AbortController();
    abortRef.current = controller;
    setStatus('working'); setMessage('در حال جداسازی سوژه با پردازنده مرکزی...'); setInferenceMs(null);
    const payload = new FormData();
    payload.append('file', source);
    payload.append('blur', String(blur));
    try {
      const response = await fetch(`/api/v1/${mode}`, { method: 'POST', body: payload, signal: controller.signal });
      if (!response.ok) {
        let detail = `خطای سرویس (${response.status})`;
        try { const data: { detail?: string } = await response.json(); detail = data.detail || detail; } catch { /* API errors can be HTML */ }
        throw new Error(detail);
      }
      const result = await response.blob();
      setResultBlob(result); setResultUrl(URL.createObjectURL(result));
      setInferenceMs(response.headers.get('X-Inference-Ms'));
      setStatus('done'); setMessage('پردازش با موفقیت انجام شد.');
    } catch (err) {
      if (controller.signal.aborted) return;
      setStatus('error'); setMessage(err instanceof Error ? err.message : 'خطای ناشناخته');
    } finally { if (abortRef.current === controller) abortRef.current = null; }
  }

  function downloadResult() {
    if (!resultBlob) return;
    const url = URL.createObjectURL(resultBlob);
    const link = document.createElement('a');
    link.href = url; link.download = mode === 'mask' ? 'birefnet-mask.png' : 'background-removed.png';
    link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  const hasResult = Boolean(resultUrl);
  return (
    <div className="app-shell">
      <div className="ambient ambient-a" /><div className="ambient ambient-b" />
      <header className="topbar container">
        <a className="brand" href="/" aria-label="بازگشت به خانه"><span className="brand-mark">◈</span><span><strong>BiRefNet <em>Lite</em></strong><small>AI Image Studio</small></span></a>
        <div className="service-state"><i className={apiStatus.includes('آماده') ? 'online' : 'offline'} />{apiStatus}</div>
      </header>
      <main className="container">
        <section className="intro">
          <div className="eyebrow">CPU-ONLY • LOCAL INFERENCE • PRIVACY-FIRST</div>
          <h1>حذف پس‌زمینه، <span>با دقت هوش مصنوعی</span></h1>
          <p>تصویر خود را بارگذاری کنید تا سوژه با مدل BiRefNet Lite از پس‌زمینه جدا شود. همه پردازش‌ها در سرور شما انجام می‌شود.</p>
        </section>
        <div className="workspace">
          <aside className="panel control-panel">
            <div className="section-heading"><span className="step">۰۱</span><div><h2>تصویر ورودی</h2><p>برای شروع یک فایل انتخاب کنید</p></div></div>
            <input ref={pickerRef} type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" onChange={event => { if (event.target.files?.[0]) receiveFile(event.target.files[0]); event.target.value = ''; }} />
            <div className={`dropzone ${busyDrag ? 'dragging' : ''}`} role="button" tabIndex={0}
              onClick={() => pickerRef.current?.click()}
              onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') {event.preventDefault(); pickerRef.current?.click();} }}
              onDragOver={(event) => { event.preventDefault(); setBusyDrag(true); }}
              onDragLeave={(event) => { event.preventDefault(); setBusyDrag(false); }}
              onDrop={(event) => { event.preventDefault(); setBusyDrag(false); if (event.dataTransfer.files[0]) receiveFile(event.dataTransfer.files[0]); }}>
              <span className="upload-symbol">↥</span>
              <strong>رها کنید یا برای انتخاب کلیک کنید</strong>
              <small>PNG / JPG / WEBP • تا ۱۰ مگابایت</small>
            </div>
            {source && <div className="selected-file"><div className="file-icon">▧</div><div><strong dir="auto">{source.name}</strong><small>{humanSize(source.size)}</small></div><span className="selected-check">✓</span></div>}
            <div className="separator" />
            <div className="section-heading"><span className="step">۰۲</span><div><h2>تنظیمات خروجی</h2><p>حالت مورد نظر را انتخاب کنید</p></div></div>
            <div className="segmented" role="group" aria-label="نوع خروجی"><button className={mode === 'remove-background' ? 'active' : ''} onClick={() => setMode('remove-background')}>تصویر شفاف</button><button className={mode === 'mask' ? 'active' : ''} onClick={() => setMode('mask')}>ماسک خاکستری</button></div>
            <label className="range-label" htmlFor="blur">نرمی لبه <strong>{blur.toFixed(1)}</strong></label>
            <input id="blur" className="range" type="range" min="0" max="3" step="0.5" value={blur} onChange={event => setBlur(Number(event.target.value))} />
            <button className="primary-button" onClick={() => void processImage()} disabled={!source || status === 'working'}>{status === 'working' ? <><span className="spinner" /> در حال پردازش...</> : <>✦ حذف پس‌زمینه</>}</button>
            <div className={`feedback ${status}`} role="status">{message || 'اطلاعات تصویر در سرور ذخیره نمی‌شود.'}</div>
          </aside>
          <section className="panel preview-panel">
            <div className="preview-top"><div><span className="pill">PREVIEW</span><h2>پیش‌نمایش تصویر</h2></div>{inferenceMs && <span className="inference-time" dir="ltr">CPU inference {inferenceMs} ms</span>}</div>
            <div className="preview-grid">
              <div className="preview-item"><div className="preview-label">تصویر اصلی <span>BEFORE</span></div><div className="image-stage original-stage">{sourceUrl ? <img src={sourceUrl} alt="تصویر اصلی" /> : <EmptyState label="تصویر اصلی اینجا نمایش داده می‌شود" />}</div></div>
              <div className="preview-item"><div className="preview-label">خروجی <span>AFTER</span></div><div className="image-stage checker" style={{backgroundColor: background}}>{resultUrl ? <img src={resultUrl} alt="خروجی حذف پس‌زمینه" /> : <EmptyState label="پس از پردازش، نتیجه را اینجا می‌بینید" />}{status === 'working' && <div className="working-overlay"><span className="spinner large" /><span>در حال پردازش تصویر</span></div>}</div></div>
            </div>
            <div className="preview-bottom"><div className="color-settings"><label htmlFor="bgColor">رنگ زمینه پیش‌نمایش</label><input id="bgColor" type="color" value={background} onChange={event => setBackground(event.target.value)} /></div><button className="download-button" disabled={!hasResult} onClick={downloadResult}>↓ دریافت PNG</button></div>
          </section>
        </div>
        <footer className="footer"><span>BiRefNet Lite • ONNX Runtime • FastAPI • React</span><span>اجرا روی CPU • بدون ارسال تصویر به سرویس‌های خارجی</span></footer>
      </main>
    </div>
  );
}

function EmptyState({ label }: { label: string }) { return <div className="empty-state"><div className="empty-art">◧</div><span>{label}</span></div>; }
export default App;
