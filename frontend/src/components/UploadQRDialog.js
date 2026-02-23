/**
 * UploadQRDialog — clean, properly stacked layout for QR-based receipt upload.
 * Shows record summary → QR code → link → expiry → file count.
 */
import { useState, useEffect, useRef } from 'react';
import { api } from '../contexts/AuthContext';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
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

  const uploadUrl = session
    ? `${window.location.origin}/upload/${session.token}`
    : '';

  useEffect(() => {
    if (open && recordType && recordId) {
      setExpired(false);
      generateLink();
    }
    return () => {
      clearInterval(pollRef.current);
      clearInterval(timerRef.current);
    };
  }, [open, recordType, recordId]); // eslint-disable-line

  const generateLink = async () => {
    setLoading(true);
    setSession(null);
    setFileCount(0);
    setTimeLeft(3600);
    setExpired(false);
    try {
      const res = await api.post(`${BACKEND_URL}/api/uploads/generate-link`, {
        record_type: recordType,
        record_id: recordId,
      });
      setSession(res.data);
      startPolling();
      startTimer();
    } catch {
      toast.error('Failed to generate upload link');
    }
    setLoading(false);
  };

  const startPolling = () => {
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const res = await api.get(`${BACKEND_URL}/api/uploads/record/${recordType}/${recordId}`);
        setFileCount(res.data.total_files || 0);
      } catch {}
    }, 4000);
  };

  const startTimer = () => {
    clearInterval(timerRef.current);
    let secs = 3600;
    timerRef.current = setInterval(() => {
      secs -= 1;
      setTimeLeft(secs);
      if (secs <= 0) {
        clearInterval(timerRef.current);
        setExpired(true);
      }
    }, 1000);
  };

  const copyLink = () => {
    navigator.clipboard.writeText(uploadUrl).then(() => toast.success('Link copied!'));
  };

  const handleClose = () => {
    clearInterval(pollRef.current);
    clearInterval(timerRef.current);
    setSession(null);
    onClose(fileCount);
  };

  const fmtTime = (s) => {
    const m = Math.floor(Math.max(0, s) / 60);
    const sec = Math.max(0, s) % 60;
    return `${m}:${String(sec).padStart(2, '0')}`;
  };

  const php = (n) => '₱' + (parseFloat(n) || 0).toLocaleString('en-PH', { minimumFractionDigits: 2 });
  const summary = session?.record_summary || {};

  return (
    <Dialog open={open} onOpenChange={() => handleClose()}>
      <DialogContent className="sm:max-w-xs w-[340px] p-0 overflow-hidden">
        {/* Header */}
        <div className="px-4 pt-4 pb-3 border-b border-slate-100 flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-[#1A4D2E] flex items-center justify-center shrink-0">
            <Upload size={15} className="text-white" />
          </div>
          <div className="min-w-0">
            <DialogTitle className="text-sm font-bold text-slate-800 leading-tight" style={{ fontFamily: 'Manrope' }}>
              Upload Receipt / Proof
            </DialogTitle>
            <p className="text-[10px] text-slate-400 leading-tight mt-0.5">Scan QR or share link</p>
          </div>
        </div>

        <div className="p-4 space-y-3">
          {loading ? (
            <div className="flex items-center justify-center py-10">
              <RefreshCw size={22} className="animate-spin text-[#1A4D2E]" />
            </div>
          ) : session ? (
            <>
              {/* Record summary — compact, contained */}
              <div className="rounded-xl bg-slate-50 border border-slate-200 px-3 py-2.5 space-y-0.5">
                <p className="text-[9px] font-bold uppercase tracking-wider text-slate-400">{summary.type_label || recordType}</p>
                <p className="text-sm font-bold text-slate-800 leading-snug truncate">{summary.title || '—'}</p>
                {summary.description && (
                  <p className="text-[11px] text-slate-500 leading-snug truncate">{summary.description}</p>
                )}
                {summary.amount > 0 && (
                  <p className="text-sm font-bold text-[#1A4D2E] font-mono">{php(summary.amount)}</p>
                )}
                {summary.date && (
                  <p className="text-[10px] text-slate-400">{summary.date}</p>
                )}
              </div>

              {/* QR code — centered, properly constrained */}
              {!expired ? (
                <div className="flex flex-col items-center gap-2 py-2">
                  <div className="p-2.5 bg-white border-[3px] border-[#1A4D2E] rounded-xl shadow-sm inline-block">
                    <QRCodeSVG
                      value={uploadUrl}
                      size={160}
                      level="M"
                      fgColor="#1A4D2E"
                      bgColor="#FFFFFF"
                    />
                  </div>
                  <p className="text-[11px] text-center text-slate-500 leading-snug">
                    Scan with your phone camera
                  </p>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2 py-4">
                  <div className="w-12 h-12 rounded-full bg-amber-100 flex items-center justify-center">
                    <AlertTriangle size={22} className="text-amber-600" />
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
                  <button onClick={copyLink}
                    className="shrink-0 w-8 h-8 rounded-lg bg-slate-100 hover:bg-slate-200 flex items-center justify-center transition-colors">
                    <Copy size={13} className="text-slate-600" />
                  </button>
                </div>
              )}

              {/* Status row */}
              <div className="flex items-center justify-between">
                <div className={`flex items-center gap-1 text-[10px] ${timeLeft < 300 && !expired ? 'text-amber-600' : 'text-slate-400'}`}>
                  <Clock size={11} />
                  <span>{expired ? 'Expired' : `Expires in ${fmtTime(timeLeft)}`}</span>
                </div>
                <Badge className={`text-[10px] px-2 py-0.5 ${fileCount > 0 ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                  {fileCount > 0 && <Check size={10} className="inline mr-0.5" />}
                  {fileCount} file{fileCount !== 1 ? 's' : ''} uploaded
                </Badge>
              </div>
            </>
          ) : null}

          {/* Action button */}
          <Button className="w-full h-9" variant={fileCount > 0 ? 'default' : 'outline'}
            onClick={handleClose}
            style={fileCount > 0 ? { backgroundColor: '#1A4D2E' } : {}}>
            {fileCount > 0 ? (
              <><Check size={14} className="mr-1.5 text-white" /><span className="text-white">Done — {fileCount} photo{fileCount !== 1 ? 's' : ''} saved</span></>
            ) : 'Close'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
