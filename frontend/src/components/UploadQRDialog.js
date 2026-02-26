/**
 * UploadQRDialog — QR-based receipt upload.
 * Custom modal (no Shadcn Dialog) for full layout control.
 */
import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { api } from '../contexts/AuthContext';
import { QRCodeSVG } from 'qrcode.react';
import { Upload, RefreshCw, Check, Copy, Clock, AlertTriangle, X } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export default function UploadQRDialog({ open, onClose, recordType, recordId }) {
  const [loading, setLoading] = useState(false);
  const [session, setSession] = useState(null);
  const [fileCount, setFileCount] = useState(0);
  const [timeLeft, setTimeLeft] = useState(3600);
  const [expired, setExpired] = useState(false);
  const pollRef = useRef(null);
  const timerRef = useRef(null);

  const uploadUrl = session ? `${window.location.origin}/upload/${session.token}` : '';

  useEffect(() => {
    if (open && recordType && recordId) {
      setExpired(false);
      generateLink();
    }
    return () => { clearInterval(pollRef.current); clearInterval(timerRef.current); };
  }, [open, recordType, recordId]); // eslint-disable-line

  const generateLink = async () => {
    setLoading(true);
    setSession(null);
    setFileCount(0);
    setTimeLeft(3600);
    setExpired(false);
    try {
      const res = await api.post(`${BACKEND_URL}/api/uploads/generate-link`, {
        record_type: recordType, record_id: recordId,
      });
      setSession(res.data);
      clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const r2 = await api.get(`${BACKEND_URL}/api/uploads/record/${recordType}/${recordId}`);
          setFileCount(r2.data.total_files || 0);
        } catch {}
      }, 4000);
      clearInterval(timerRef.current);
      let secs = 3600;
      timerRef.current = setInterval(() => {
        secs -= 1;
        setTimeLeft(secs);
        if (secs <= 0) { clearInterval(timerRef.current); setExpired(true); }
      }, 1000);
    } catch { toast.error('Failed to generate upload link'); }
    setLoading(false);
  };

  const copyLink = () => navigator.clipboard.writeText(uploadUrl).then(() => toast.success('Link copied!'));

  const handleClose = () => {
    clearInterval(pollRef.current);
    clearInterval(timerRef.current);
    setSession(null);
    onClose(fileCount);
  };

  const fmtTime = (s) => {
    const t = Math.max(0, s);
    return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`;
  };

  const php = (n) => '₱' + (parseFloat(n) || 0).toLocaleString('en-PH', { minimumFractionDigits: 2 });
  const summary = session?.record_summary || {};

  if (!open) return null;

  return createPortal(
    /* Overlay */
    <div
      className="fixed inset-0 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.65)', zIndex: 9999 }}
      onClick={(e) => { if (e.target === e.currentTarget) handleClose(); }}
    >
      {/* Modal box */}
      <div
        className="relative bg-white rounded-2xl shadow-2xl w-full overflow-y-auto"
        style={{ maxWidth: '360px', maxHeight: '90vh' }}
      >
        {/* Close button */}
        <button
          onClick={handleClose}
          data-testid="uploadqr-close-x"
          className="absolute top-3 right-3 z-10 w-7 h-7 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center transition-colors"
          aria-label="Close"
        >
          <X size={14} className="text-slate-500" />
        </button>

        {/* Inner padding */}
        <div className="p-5">
          {/* Header */}
          <div className="flex items-center gap-2 mb-4">
            <span className="inline-flex w-8 h-8 rounded-lg bg-[#1A4D2E] items-center justify-center shrink-0">
              <Upload size={15} className="text-white" />
            </span>
            <div>
              <p className="font-semibold text-slate-800 text-sm leading-tight">Upload Receipt / Proof</p>
              <p className="text-[11px] text-slate-400">Scan with phone or copy link</p>
            </div>
          </div>

          {/* Loading */}
          {loading && (
            <div className="flex flex-col items-center justify-center py-10 gap-3">
              <RefreshCw size={26} className="animate-spin text-[#1A4D2E]" />
              <p className="text-sm text-slate-400">Generating link…</p>
            </div>
          )}

          {/* Session content */}
          {!loading && session && (
            <div className="flex flex-col gap-3">
              {/* Record summary */}
              <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5">
                <p className="text-[9px] font-bold uppercase tracking-wider text-slate-400 mb-0.5">
                  {summary.type_label || recordType}
                </p>
                <p className="font-bold text-slate-800 text-sm leading-tight truncate">{summary.title || '—'}</p>
                {summary.description && (
                  <p className="text-[11px] text-slate-500 mt-0.5 truncate">{summary.description}</p>
                )}
                {summary.amount > 0 && (
                  <p className="text-sm font-bold text-[#1A4D2E] font-mono mt-0.5">{php(summary.amount)}</p>
                )}
                {summary.date && <p className="text-[10px] text-slate-400 mt-0.5">{summary.date}</p>}
              </div>

              {/* QR code block */}
              {!expired ? (
                <div className="flex flex-col items-center gap-2 py-2">
                  <div
                    style={{ border: '3px solid #1A4D2E', borderRadius: '12px', padding: '8px', background: '#fff', display: 'inline-block' }}
                  >
                    <QRCodeSVG value={uploadUrl} size={150} level="M" fgColor="#1A4D2E" bgColor="#FFFFFF" />
                  </div>
                  <p className="text-xs text-slate-500 text-center mt-1">Scan with your phone camera</p>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2 py-4">
                  <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center">
                    <AlertTriangle size={18} className="text-amber-600" />
                  </div>
                  <p className="text-sm font-semibold text-amber-700">Link Expired</p>
                  <button
                    onClick={generateLink}
                    className="mt-1 px-4 py-1.5 rounded-lg border border-slate-300 text-xs text-slate-600 hover:bg-slate-50 transition-colors"
                  >
                    Generate New Link
                  </button>
                </div>
              )}

              {/* URL + copy */}
              {!expired && (
                <div className="flex gap-1.5 items-center">
                  <div className="flex-1 min-w-0 bg-slate-100 rounded-lg px-2.5 py-1.5 text-[10px] font-mono text-slate-600 truncate">
                    {uploadUrl}
                  </div>
                  <button
                    onClick={copyLink}
                    className="shrink-0 w-8 h-8 rounded-lg bg-slate-100 hover:bg-slate-200 flex items-center justify-center transition-colors"
                    title="Copy link"
                  >
                    <Copy size={13} className="text-slate-600" />
                  </button>
                </div>
              )}

              {/* Status row */}
              <div className="flex items-center justify-between text-[11px]">
                <span className={`flex items-center gap-1 ${timeLeft < 300 && !expired ? 'text-amber-600' : 'text-slate-400'}`}>
                  <Clock size={11} />
                  {expired ? 'Expired' : `Expires in ${fmtTime(timeLeft)}`}
                </span>
                <span className={`flex items-center gap-1 font-medium ${fileCount > 0 ? 'text-emerald-600' : 'text-slate-400'}`}>
                  {fileCount > 0 && <Check size={11} />}
                  {fileCount} file{fileCount !== 1 ? 's' : ''} uploaded
                </span>
              </div>
            </div>
          )}

          {/* Action button */}
          <button
            onClick={handleClose}
            className={`w-full mt-4 py-2.5 rounded-xl font-medium text-sm transition-colors flex items-center justify-center gap-1.5
              ${fileCount > 0
                ? 'bg-[#1A4D2E] hover:bg-[#14532d] text-white'
                : 'border border-slate-200 text-slate-600 hover:bg-slate-50'
              }`}
          >
            {fileCount > 0
              ? <><Check size={14} /> Done — {fileCount} photo{fileCount !== 1 ? 's' : ''} saved</>
              : 'Close'
            }
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
