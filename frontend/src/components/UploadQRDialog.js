/**
 * UploadQRDialog — generates a QR code for a record.
 * User scans with phone → opens UploadPage → uploads photos.
 * Shows real-time file count via polling.
 */
import { useState, useEffect, useRef } from 'react';
import { api } from '../contexts/AuthContext';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Badge } from './ui/badge';
import { QRCodeSVG } from 'qrcode.react';
import { Upload, RefreshCw, Check, Copy, Clock, X } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export default function UploadQRDialog({ open, onClose, recordType, recordId }) {
  const [loading, setLoading] = useState(false);
  const [session, setSession] = useState(null);
  const [fileCount, setFileCount] = useState(0);
  const [timeLeft, setTimeLeft] = useState(3600);
  const pollRef = useRef(null);
  const timerRef = useRef(null);

  const uploadUrl = session
    ? `${window.location.origin}/upload/${session.token}`
    : '';

  useEffect(() => {
    if (open && recordType && recordId) generateLink();
    return () => { clearInterval(pollRef.current); clearInterval(timerRef.current); };
  }, [open, recordType, recordId]); // eslint-disable-line

  const generateLink = async () => {
    setLoading(true);
    setSession(null);
    setFileCount(0);
    setTimeLeft(3600);
    try {
      const res = await api.post(`${BACKEND_URL}/api/uploads/generate-link`, {
        record_type: recordType,
        record_id: recordId,
      });
      setSession(res.data);
      startPolling(res.data.token);
      startTimer();
    } catch (e) {
      toast.error('Failed to generate upload link');
    }
    setLoading(false);
  };

  const startPolling = (token) => {
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const res = await api.get(`${BACKEND_URL}/api/uploads/record/${recordType}/${recordId}`);
        setFileCount(res.data.total_files || 0);
      } catch {}
    }, 5000);
  };

  const startTimer = () => {
    clearInterval(timerRef.current);
    let secs = 3600;
    timerRef.current = setInterval(() => {
      secs--;
      setTimeLeft(secs);
      if (secs <= 0) clearInterval(timerRef.current);
    }, 1000);
  };

  const copyLink = () => {
    navigator.clipboard.writeText(uploadUrl);
    toast.success('Link copied!');
  };

  const fmtTime = (s) => {
    const m = Math.floor(s / 60), sec = s % 60;
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  const handleClose = () => {
    clearInterval(pollRef.current);
    clearInterval(timerRef.current);
    setSession(null);
    onClose(fileCount);
  };

  return (
    <Dialog open={open} onOpenChange={() => handleClose()}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle style={{ fontFamily: 'Manrope' }} className="flex items-center gap-2">
            <Upload size={18} className="text-[#1A4D2E]" /> Upload Receipt / Proof
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 mt-1">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <RefreshCw size={20} className="animate-spin text-slate-400" />
            </div>
          ) : session ? (
            <>
              {/* Record summary */}
              {session.record_summary && (
                <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs space-y-0.5">
                  <p className="font-semibold text-slate-700">{session.record_summary.type_label}</p>
                  <p className="font-mono text-slate-600">{session.record_summary.title}</p>
                  <p className="text-slate-500">{session.record_summary.description}</p>
                  {session.record_summary.amount > 0 && (
                    <p className="font-bold text-[#1A4D2E]">₱{parseFloat(session.record_summary.amount).toLocaleString('en-PH', { minimumFractionDigits: 2 })}</p>
                  )}
                </div>
              )}

              {/* QR Code */}
              <div className="flex flex-col items-center gap-3 py-2">
                <div className="p-3 bg-white border-2 border-[#1A4D2E] rounded-xl shadow-sm">
                  <QRCodeSVG value={uploadUrl} size={180} level="M"
                    fgColor="#1A4D2E" bgColor="#FFFFFF" />
                </div>
                <p className="text-xs text-center text-slate-500">
                  Scan with your phone camera to open the upload page
                </p>
              </div>

              {/* Link + copy */}
              <div className="flex gap-2">
                <div className="flex-1 bg-slate-50 border border-slate-200 rounded-md px-3 py-2 text-xs text-slate-600 font-mono truncate">
                  {uploadUrl}
                </div>
                <Button size="sm" variant="outline" onClick={copyLink} className="h-9 px-3">
                  <Copy size={13} />
                </Button>
              </div>

              {/* Status row */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-xs text-slate-500">
                  <Clock size={12} />
                  <span>Expires in {fmtTime(timeLeft)}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  {fileCount > 0 && <Check size={13} className="text-emerald-600" />}
                  <Badge className={`text-[10px] ${fileCount > 0 ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                    {fileCount} file{fileCount !== 1 ? 's' : ''} uploaded
                  </Badge>
                </div>
              </div>

              {timeLeft <= 0 && (
                <div className="text-center">
                  <p className="text-xs text-amber-600 mb-2">Link expired. Generate a new one if needed.</p>
                  <Button size="sm" variant="outline" onClick={generateLink}>Generate New Link</Button>
                </div>
              )}
            </>
          ) : null}

          <div className="flex gap-2 pt-1">
            <Button variant="outline" className="flex-1" onClick={handleClose}>
              {fileCount > 0 ? `Done (${fileCount} uploaded)` : 'Close'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
