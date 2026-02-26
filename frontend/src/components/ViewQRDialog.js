/**
 * ViewQRDialog — generates a "View on Phone" QR for viewing uploaded photos.
 * Separate from UploadQRDialog. Read-only — cannot upload from this QR.
 */
import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { api } from '../contexts/AuthContext';
import { QRCodeSVG } from 'qrcode.react';
import { Smartphone, RefreshCw, Copy, Clock, X, Images } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export default function ViewQRDialog({ open, onClose, recordType, recordId, fileCount = 0 }) {
  const [loading, setLoading] = useState(false);
  const [session, setSession] = useState(null);
  const [timeLeft, setTimeLeft] = useState(3600);
  const [expired, setExpired] = useState(false);

  const viewUrl = session ? `${window.location.origin}/view-receipts/${session.token}` : '';

  useEffect(() => {
    if (open && recordType && recordId) {
      setExpired(false);
      generateToken();
    }
    return () => {};
  }, [open, recordType, recordId]); // eslint-disable-line

  const generateToken = async () => {
    setLoading(true);
    setSession(null);
    setTimeLeft(3600);
    setExpired(false);
    try {
      const res = await api.post(`${BACKEND_URL}/api/uploads/generate-view-token`, {
        record_type: recordType, record_id: recordId,
      });
      setSession(res.data);
      let secs = 3600;
      const t = setInterval(() => {
        secs -= 1;
        setTimeLeft(secs);
        if (secs <= 0) { clearInterval(t); setExpired(true); }
      }, 1000);
    } catch { toast.error('Failed to generate view link'); }
    setLoading(false);
  };

  const copyLink = () => navigator.clipboard.writeText(viewUrl).then(() => toast.success('Link copied!'));

  const fmtTime = (s) => {
    const t = Math.max(0, s);
    return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`;
  };

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.65)', zIndex: 9999 }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="relative bg-white rounded-2xl shadow-2xl w-full overflow-y-auto" style={{ maxWidth: '340px', maxHeight: '90vh' }}>
        <button onClick={onClose} data-testid="viewqr-close-x" className="absolute top-3 right-3 z-10 w-7 h-7 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center">
          <X size={14} className="text-slate-500" />
        </button>

        <div className="p-5">
          {/* Header */}
          <div className="flex items-center gap-2 mb-4">
            <span className="inline-flex w-8 h-8 rounded-lg bg-slate-800 items-center justify-center shrink-0">
              <Smartphone size={15} className="text-white" />
            </span>
            <div>
              <p className="font-semibold text-slate-800 text-sm leading-tight">View Photos on Phone</p>
              <p className="text-[11px] text-slate-400">
                {fileCount > 0 ? `${fileCount} photo${fileCount !== 1 ? 's' : ''} attached` : 'Scan to view receipts'}
              </p>
            </div>
          </div>

          {fileCount === 0 && (
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 mb-4 flex items-center gap-2">
              <Images size={16} className="text-slate-400 shrink-0" />
              <p className="text-xs text-slate-500">No photos uploaded yet. Upload some first, then use this QR to view them on your phone.</p>
            </div>
          )}

          {loading && (
            <div className="flex flex-col items-center py-8 gap-2">
              <RefreshCw size={22} className="animate-spin text-slate-600" />
              <p className="text-xs text-slate-400">Generating link…</p>
            </div>
          )}

          {!loading && session && (
            <div className="flex flex-col gap-3">
              {!expired ? (
                <div className="flex flex-col items-center gap-2 py-1">
                  <div style={{ border: '3px solid #1e293b', borderRadius: '12px', padding: '8px', background: '#fff', display: 'inline-block' }}>
                    <QRCodeSVG value={viewUrl} size={150} level="M" fgColor="#1e293b" bgColor="#FFFFFF" />
                  </div>
                  <p className="text-xs text-slate-500 text-center">Scan to view photos on your phone</p>
                  <p className="text-[10px] text-slate-400 text-center">You can also verify the transaction from your phone</p>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2 py-4">
                  <p className="text-sm font-semibold text-amber-700">Link Expired</p>
                  <button onClick={generateToken} className="px-4 py-1.5 rounded-lg border border-slate-300 text-xs text-slate-600 hover:bg-slate-50">
                    Generate New Link
                  </button>
                </div>
              )}

              {!expired && (
                <div className="flex gap-1.5 items-center">
                  <div className="flex-1 min-w-0 bg-slate-100 rounded-lg px-2.5 py-1.5 text-[10px] font-mono text-slate-600 truncate">{viewUrl}</div>
                  <button onClick={copyLink} className="shrink-0 w-8 h-8 rounded-lg bg-slate-100 hover:bg-slate-200 flex items-center justify-center" title="Copy link">
                    <Copy size={13} className="text-slate-600" />
                  </button>
                </div>
              )}

              <div className="flex items-center justify-between text-[11px]">
                <span className={`flex items-center gap-1 ${timeLeft < 300 && !expired ? 'text-amber-600' : 'text-slate-400'}`}>
                  <Clock size={11} />
                  {expired ? 'Expired' : `Expires in ${fmtTime(timeLeft)}`}
                </span>
                <span className="text-slate-400 text-[10px]">Read-only · No uploads</span>
              </div>
            </div>
          )}

          <button
            onClick={onClose}
            data-testid="viewqr-close-btn"
            className="w-full mt-4 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-600 hover:bg-slate-50 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
