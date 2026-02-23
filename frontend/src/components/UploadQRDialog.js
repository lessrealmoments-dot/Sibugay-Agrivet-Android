/**
 * UploadQRDialog — QR-based receipt upload.
 * Uses Shadcn Dialog properly — no layout fighting.
 */
import { useState, useEffect, useRef } from 'react';
import { api } from '../contexts/AuthContext';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { QRCodeSVG } from 'qrcode.react';
import { Upload, RefreshCw, Check, Copy, Clock, AlertTriangle } from 'lucide-react';
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

  return (
    <Dialog open={open} onOpenChange={() => handleClose()}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader className="pb-0">
          <DialogTitle className="flex items-center gap-2 text-base">
            <span className="inline-flex w-7 h-7 rounded-lg bg-[#1A4D2E] items-center justify-center shrink-0">
              <Upload size={14} className="text-white" />
            </span>
            Upload Receipt / Proof
          </DialogTitle>
          <p className="text-xs text-slate-400 ml-9">Scan with phone or copy link</p>
        </DialogHeader>

        {/* ── Content ── */}
        {loading && (
          <div className="flex justify-center py-8">
            <RefreshCw size={24} className="animate-spin text-[#1A4D2E]" />
          </div>
        )}

        {!loading && session && (
          <div className="space-y-3">
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

            {/* QR code — w-full + items-center ensures true centering */}
            {!expired ? (
              <div className="w-full flex flex-col items-center gap-2 py-1">
                <div className="border-[3px] border-[#1A4D2E] rounded-xl p-2 bg-white shadow-sm">
                  <QRCodeSVG value={uploadUrl} size={130} level="M" fgColor="#1A4D2E" bgColor="#FFFFFF" />
                </div>
                <p className="text-xs text-slate-500 text-center">Scan with your phone camera</p>
              </div>
            ) : (
              <div className="w-full flex flex-col items-center gap-2 py-4">
                <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center">
                  <AlertTriangle size={18} className="text-amber-600" />
                </div>
                <p className="text-sm font-semibold text-amber-700">Link Expired</p>
                <Button size="sm" variant="outline" onClick={generateLink} className="h-8 text-xs">
                  Generate New Link
                </Button>
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
        <Button
          className={`w-full mt-1 ${fileCount > 0 ? 'bg-[#1A4D2E] hover:bg-[#14532d] text-white' : ''}`}
          variant={fileCount > 0 ? 'default' : 'outline'}
          onClick={handleClose}
        >
          {fileCount > 0
            ? <><Check size={14} className="mr-1.5" /> Done — {fileCount} photo{fileCount !== 1 ? 's' : ''} saved</>
            : 'Close'
          }
        </Button>
      </DialogContent>
    </Dialog>
  );
}
