/**
 * ReceiptUploadInline — Inline file upload widget for forms.
 * Supports both direct desktop upload AND QR-based phone upload.
 * Used in: PO creation (mandatory), Branch Transfer receive (mandatory), Expense (optional).
 */
import { useState, useRef, useCallback, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { api } from '../contexts/AuthContext';
import { QRCodeSVG } from 'qrcode.react';
import { Upload, X, ImageIcon, RefreshCw, Check, Camera, AlertTriangle, Smartphone, Copy, Clock, ChevronDown, ChevronUp } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const MAX_FILES = 10;
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

export default function ReceiptUploadInline({
  required = false,
  label = 'Receipt / Proof Photos',
  recordType = 'purchase_order',
  recordSummary = null,   // { type_label, title, description, amount, date } for QR page
  onUploaded,             // callback({ sessionId, fileCount, files })
  compact = false,        // compact mode for smaller forms
}) {
  const [files, setFiles] = useState([]);       // { id, name, preview, size }
  const [uploading, setUploading] = useState(false);
  const [sessionId, setSessionId] = useState(null);

  // QR mode
  const [showQR, setShowQR] = useState(false);
  const [qrToken, setQrToken] = useState(null);
  const [qrLoading, setQrLoading] = useState(false);
  const [phoneFileCount, setPhoneFileCount] = useState(0);
  const pollRef = useRef(null);
  const inputRef = useRef(null);

  const uploadUrl = qrToken ? `${window.location.origin}/upload/${qrToken}` : '';

  // Poll for phone uploads when QR is active
  useEffect(() => {
    if (showQR && sessionId) {
      pollRef.current = setInterval(async () => {
        try {
          const res = await api.get(`/uploads/session-status/${sessionId}`);
          const count = res.data.file_count || 0;
          if (count !== phoneFileCount) {
            setPhoneFileCount(count);
            // Build file list from phone uploads
            const phoneFiles = (res.data.files || []).map(f => ({
              id: f.id,
              name: f.filename,
              preview: null, // Phone photos don't have local previews
              size: 0,
              fromPhone: true,
            }));
            // Merge with existing direct uploads
            const directFiles = files.filter(f => !f.fromPhone);
            const allFiles = [...directFiles, ...phoneFiles];
            setFiles(allFiles);
            onUploaded?.({ sessionId, fileCount: allFiles.length, files: allFiles });
          }
        } catch {}
      }, 3000);
    }
    return () => clearInterval(pollRef.current);
  }, [showQR, sessionId, phoneFileCount]); // eslint-disable-line

  // Clean up on unmount
  useEffect(() => () => clearInterval(pollRef.current), []);

  const handleFiles = useCallback(async (fileList) => {
    const newFiles = Array.from(fileList);
    if (files.length + newFiles.length > MAX_FILES) {
      toast.error(`Maximum ${MAX_FILES} files allowed`);
      return;
    }

    const valid = newFiles.filter(f => {
      if (!f.type.startsWith('image/') && f.type !== 'application/pdf') {
        toast.error(`"${f.name}" is not an image or PDF`);
        return false;
      }
      if (f.size > MAX_FILE_SIZE) {
        toast.error(`"${f.name}" exceeds 10MB limit`);
        return false;
      }
      return true;
    });
    if (!valid.length) return;

    setUploading(true);
    try {
      const formData = new FormData();
      valid.forEach(f => formData.append('files', f));
      formData.append('record_type', recordType);
      if (sessionId) formData.append('session_id', sessionId);

      const res = await api.post(`${BACKEND_URL}/api/uploads/direct`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      const newSessionId = res.data.session_id;
      setSessionId(newSessionId);

      const uploadedFiles = valid.map((f, i) => ({
        id: res.data.file_ids?.[i] || `f-${Date.now()}-${i}`,
        name: f.name,
        size: f.size,
        preview: f.type.startsWith('image/') ? URL.createObjectURL(f) : null,
      }));

      const allFiles = [...files, ...uploadedFiles];
      setFiles(allFiles);
      onUploaded?.({ sessionId: newSessionId, fileCount: allFiles.length, files: allFiles });
      toast.success(`${valid.length} photo${valid.length > 1 ? 's' : ''} uploaded`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Upload failed');
    }
    setUploading(false);
  }, [files, sessionId, recordType, onUploaded]);

  const removeFile = async (fileId) => {
    if (sessionId) {
      try {
        await api.delete(`${BACKEND_URL}/api/uploads/direct/${sessionId}/${fileId}`);
      } catch {}
    }
    const updated = files.filter(f => f.id !== fileId);
    setFiles(updated);
    onUploaded?.({ sessionId, fileCount: updated.length, files: updated });
  };

  const handleDrop = (e) => {
    e.preventDefault();
    handleFiles(e.dataTransfer.files);
  };

  const generateQR = async () => {
    setQrLoading(true);
    try {
      const res = await api.post(`${BACKEND_URL}/api/uploads/generate-pending-link`, {
        record_type: recordType,
        session_id: sessionId || undefined,
        record_summary: recordSummary || undefined,
      });
      setQrToken(res.data.token);
      if (!sessionId) setSessionId(res.data.session_id);
      setShowQR(true);
      setPhoneFileCount(0);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to generate QR');
    }
    setQrLoading(false);
  };

  const copyLink = () => navigator.clipboard.writeText(uploadUrl).then(() => toast.success('Link copied!'));

  const totalFiles = files.length;

  // ── Compact mode ──────────────────────────────────────────────────────
  if (compact) {
    return (
      <div data-testid="receipt-upload-inline">
        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={uploading}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border ${
              totalFiles > 0
                ? 'border-emerald-300 bg-emerald-50 text-emerald-700'
                : required
                ? 'border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100'
                : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
            }`}
            data-testid="receipt-upload-btn"
          >
            {uploading ? <RefreshCw size={12} className="animate-spin" /> : totalFiles > 0 ? <Check size={12} /> : <Camera size={12} />}
            {totalFiles > 0 ? `${totalFiles} photo${totalFiles > 1 ? 's' : ''}` : 'Attach Receipt'}
          </button>
          <button
            type="button"
            onClick={generateQR}
            disabled={qrLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 transition-colors"
            data-testid="receipt-qr-btn"
          >
            {qrLoading ? <RefreshCw size={12} className="animate-spin" /> : <Smartphone size={12} />}
            Use Phone
          </button>
          {required && totalFiles === 0 && (
            <span className="text-[10px] text-amber-600 flex items-center gap-0.5">
              <AlertTriangle size={10} /> Required
            </span>
          )}
          {totalFiles > 0 && (
            <div className="flex gap-1">
              {files.slice(0, 4).map(f => (
                <div key={f.id} className="relative group">
                  {f.preview ? (
                    <img src={f.preview} alt="" className="w-8 h-8 rounded object-cover border border-slate-200" />
                  ) : (
                    <div className="w-8 h-8 rounded bg-slate-100 border border-slate-200 flex items-center justify-center">
                      {f.fromPhone ? <Smartphone size={10} className="text-slate-400" /> : <ImageIcon size={12} className="text-slate-400" />}
                    </div>
                  )}
                  <button type="button" onClick={() => removeFile(f.id)}
                    className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-red-500 text-white hidden group-hover:flex items-center justify-center">
                    <X size={8} />
                  </button>
                </div>
              ))}
              {totalFiles > 4 && <span className="text-[10px] text-slate-400 self-center">+{totalFiles - 4}</span>}
            </div>
          )}
        </div>
        {/* Inline QR popup */}
        {showQR && qrToken && <QRPanel uploadUrl={uploadUrl} phoneFileCount={phoneFileCount} onCopy={copyLink} onClose={() => setShowQR(false)} />}
        <input ref={inputRef} type="file" accept="image/*,application/pdf" multiple className="hidden"
          onChange={e => { handleFiles(e.target.files); e.target.value = ''; }} data-testid="receipt-file-input" />
      </div>
    );
  }

  // ── Full-size upload area ─────────────────────────────────────────────
  return (
    <div data-testid="receipt-upload-inline" onPaste={e => { if (e.clipboardData?.files?.length) handleFiles(e.clipboardData.files); }}>
      <label className="text-xs text-slate-500 font-medium flex items-center gap-1.5 mb-1.5">
        <ImageIcon size={12} />
        {label}
        {required && <span className="text-red-500">*</span>}
      </label>
      <div
        className={`relative rounded-xl border-2 border-dashed transition-colors p-4 ${
          totalFiles > 0
            ? 'border-emerald-300 bg-emerald-50/50'
            : required
            ? 'border-amber-300 bg-amber-50/30 hover:border-amber-400'
            : 'border-slate-200 bg-slate-50/50 hover:border-slate-300'
        }`}
        onDragOver={e => e.preventDefault()}
        onDrop={handleDrop}
      >
        {totalFiles === 0 ? (
          <div className="flex flex-col items-center gap-2 py-2">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center ${required ? 'bg-amber-100' : 'bg-slate-100'}`}>
              {uploading ? <RefreshCw size={18} className="animate-spin text-slate-500" /> : <Upload size={18} className={required ? 'text-amber-600' : 'text-slate-400'} />}
            </div>
            <div className="text-center">
              <div className="flex items-center gap-3 justify-center">
                <button type="button" onClick={() => inputRef.current?.click()} disabled={uploading}
                  className="text-sm font-medium text-[#1A4D2E] hover:underline" data-testid="receipt-upload-btn">
                  {uploading ? 'Uploading...' : 'Click to upload'}
                </button>
                <span className="text-slate-300">|</span>
                <button type="button" onClick={generateQR} disabled={qrLoading}
                  className="text-sm font-medium text-blue-600 hover:underline flex items-center gap-1" data-testid="receipt-qr-btn">
                  {qrLoading ? <RefreshCw size={12} className="animate-spin" /> : <Smartphone size={13} />}
                  Use Phone
                </button>
              </div>
              <p className="text-[10px] text-slate-400 mt-0.5">Drag & drop, paste, or scan QR with phone</p>
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="flex flex-wrap gap-2">
              {files.map(f => (
                <div key={f.id} className="relative group">
                  {f.preview ? (
                    <img src={f.preview} alt={f.name} className="w-16 h-16 rounded-lg object-cover border border-emerald-200 shadow-sm" />
                  ) : (
                    <div className="w-16 h-16 rounded-lg bg-slate-100 border border-slate-200 flex flex-col items-center justify-center">
                      {f.fromPhone ? (
                        <>
                          <Smartphone size={14} className="text-blue-400" />
                          <span className="text-[8px] text-blue-400 mt-0.5">Phone</span>
                        </>
                      ) : (
                        <>
                          <ImageIcon size={16} className="text-slate-400" />
                          <span className="text-[8px] text-slate-400 mt-0.5 truncate max-w-[50px]">{f.name}</span>
                        </>
                      )}
                    </div>
                  )}
                  <button type="button" onClick={() => removeFile(f.id)}
                    className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-red-500 text-white hidden group-hover:flex items-center justify-center shadow-sm">
                    <X size={10} />
                  </button>
                </div>
              ))}
              {totalFiles < MAX_FILES && (
                <div className="flex gap-1.5">
                  <button type="button" onClick={() => inputRef.current?.click()} disabled={uploading}
                    className="w-16 h-16 rounded-lg border-2 border-dashed border-slate-300 bg-white hover:border-[#1A4D2E] hover:bg-emerald-50 flex flex-col items-center justify-center transition-colors">
                    {uploading ? <RefreshCw size={14} className="animate-spin text-slate-400" /> : <><Upload size={14} className="text-slate-400" /><span className="text-[9px] text-slate-400 mt-0.5">Add</span></>}
                  </button>
                  <button type="button" onClick={generateQR} disabled={qrLoading}
                    className="w-16 h-16 rounded-lg border-2 border-dashed border-blue-200 bg-white hover:border-blue-400 hover:bg-blue-50 flex flex-col items-center justify-center transition-colors"
                    data-testid="receipt-qr-btn">
                    {qrLoading ? <RefreshCw size={14} className="animate-spin text-blue-400" /> : <><Smartphone size={14} className="text-blue-400" /><span className="text-[9px] text-blue-400 mt-0.5">Phone</span></>}
                  </button>
                </div>
              )}
            </div>
            <p className="text-[10px] text-emerald-600 flex items-center gap-1">
              <Check size={10} /> {totalFiles} receipt{totalFiles > 1 ? 's' : ''} attached
            </p>
          </div>
        )}
      </div>

      {/* QR panel */}
      {showQR && qrToken && <QRPanel uploadUrl={uploadUrl} phoneFileCount={phoneFileCount} onCopy={copyLink} onClose={() => setShowQR(false)} />}

      <input ref={inputRef} type="file" accept="image/*,application/pdf" multiple className="hidden"
        onChange={e => { handleFiles(e.target.files); e.target.value = ''; }} data-testid="receipt-file-input" />
    </div>
  );
}

// ── QR Code Panel ─────────────────────────────────────────────────────────
function QRPanel({ uploadUrl, phoneFileCount, onCopy, onClose }) {
  return (
    <div className="mt-3 p-4 rounded-xl border border-blue-200 bg-blue-50/50" data-testid="qr-upload-panel">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-blue-100 flex items-center justify-center">
            <Smartphone size={14} className="text-blue-600" />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-700">Scan with Phone</p>
            <p className="text-[10px] text-slate-400">Use camera or gallery to upload</p>
          </div>
        </div>
        <button type="button" onClick={onClose} className="w-6 h-6 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center">
          <X size={11} className="text-slate-500" />
        </button>
      </div>
      <div className="flex items-center gap-4">
        <div className="shrink-0" style={{ border: '2px solid #1A4D2E', borderRadius: '10px', padding: '6px', background: '#fff' }}>
          <QRCodeSVG value={uploadUrl} size={110} level="M" fgColor="#1A4D2E" bgColor="#FFFFFF" />
        </div>
        <div className="flex-1 min-w-0 space-y-2">
          <p className="text-[10px] text-slate-500">Point your phone camera at the QR code. The upload page opens automatically with camera and gallery options.</p>
          <div className="flex items-center gap-1.5">
            <div className="flex-1 min-w-0 bg-white rounded-lg px-2 py-1 text-[9px] font-mono text-slate-500 truncate border border-slate-200">
              {uploadUrl}
            </div>
            <button type="button" onClick={onCopy}
              className="shrink-0 w-7 h-7 rounded-lg bg-white border border-slate-200 hover:bg-slate-50 flex items-center justify-center" title="Copy link">
              <Copy size={11} className="text-slate-500" />
            </button>
          </div>
          <div className={`flex items-center gap-1.5 text-[11px] ${phoneFileCount > 0 ? 'text-emerald-600 font-medium' : 'text-slate-400'}`}>
            {phoneFileCount > 0 ? <Check size={11} /> : <Clock size={11} />}
            {phoneFileCount > 0
              ? `${phoneFileCount} photo${phoneFileCount > 1 ? 's' : ''} uploaded from phone`
              : 'Waiting for phone upload...'}
          </div>
        </div>
      </div>
    </div>
  );
}
