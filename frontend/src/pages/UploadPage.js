/**
 * UploadPage — public mobile-friendly page for uploading receipts.
 * Accessible at /upload/:token — no login required.
 * Shows record summary so user can confirm they're uploading to the right record.
 */
import { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { Check, Upload, Image, X, AlertTriangle, RefreshCw, Camera } from 'lucide-react';
import { Button } from '../components/ui/button';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export default function UploadPage() {
  const { token } = useParams();
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploaded, setUploaded] = useState(0);
  const [done, setDone] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    loadPreview();
  }, [token]); // eslint-disable-line

  const loadPreview = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/uploads/preview/${token}`);
      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || 'Upload link not found or expired');
      } else {
        const data = await res.json();
        setPreview(data);
      }
    } catch {
      setError('Cannot connect to server. Check your internet connection.');
    }
    setLoading(false);
  };

  const handleFiles = (e) => {
    const selected = Array.from(e.target.files || []);
    const remaining = 10 - (preview?.file_count || 0) - files.length;
    const toAdd = selected.slice(0, remaining);
    const withPreview = toAdd.map(f => ({
      file: f,
      previewUrl: f.type.startsWith('image/') ? URL.createObjectURL(f) : null,
      name: f.name,
    }));
    setFiles(prev => [...prev, ...withPreview]);
  };

  const removeFile = (idx) => {
    setFiles(prev => prev.filter((_, i) => i !== idx));
  };

  const handleUpload = async () => {
    if (!files.length) return;
    setUploading(true);
    try {
      const formData = new FormData();
      files.forEach(f => formData.append('files', f.file, f.name));
      const res = await fetch(`${BACKEND_URL}/api/uploads/upload/${token}`, {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || 'Upload failed');
      } else {
        const data = await res.json();
        setUploaded(data.uploaded);
        setDone(true);
        setFiles([]);
      }
    } catch {
      setError('Upload failed. Check your internet connection.');
    }
    setUploading(false);
  };

  const php = (n) => '₱' + (parseFloat(n) || 0).toLocaleString('en-PH', { minimumFractionDigits: 2 });

  if (loading) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center">
      <RefreshCw size={24} className="animate-spin text-[#1A4D2E]" />
    </div>
  );

  if (error) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl p-6 shadow-lg max-w-sm w-full text-center space-y-3">
        <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mx-auto">
          <AlertTriangle size={22} className="text-red-600" />
        </div>
        <h2 className="font-bold text-slate-800 text-lg">Link Invalid or Expired</h2>
        <p className="text-sm text-slate-500">{error}</p>
        <p className="text-xs text-slate-400">Upload links expire after 1 hour. Ask the staff member to generate a new link from the PO or Expense record.</p>
      </div>
    </div>
  );

  if (done) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl p-8 shadow-lg max-w-sm w-full text-center space-y-4">
        <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mx-auto">
          <Check size={28} className="text-emerald-600" />
        </div>
        <h2 className="font-bold text-slate-800 text-xl" style={{ fontFamily: 'Manrope' }}>Uploaded!</h2>
        <p className="text-slate-500 text-sm">{uploaded} photo{uploaded !== 1 ? 's' : ''} saved to the record.</p>
        {preview?.record_summary && (
          <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-left">
            <p className="text-xs font-semibold text-emerald-800">{preview.record_summary.type_label}</p>
            <p className="text-sm font-bold text-emerald-700 mt-0.5">{preview.record_summary.title}</p>
          </div>
        )}
        <p className="text-xs text-slate-400">You can close this tab. The staff can view the uploaded photos from the record in AgriBooks.</p>
      </div>
    </div>
  );

  const summary = preview?.record_summary || {};
  const alreadyUploaded = preview?.file_count || 0;
  const canUploadMore = 10 - alreadyUploaded - files.length;

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#1A4D2E]/5 to-slate-100">
      <div className="max-w-sm mx-auto px-4 py-6 space-y-4">
        {/* Header */}
        <div className="bg-white rounded-2xl p-5 shadow-sm border border-slate-200">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-xl bg-[#1A4D2E] flex items-center justify-center shrink-0">
              <Upload size={18} className="text-white" />
            </div>
            <div>
              <h1 className="font-bold text-slate-800 text-base" style={{ fontFamily: 'Manrope' }}>Upload Receipt</h1>
              <p className="text-[11px] text-slate-400">AgriBooks Business Management</p>
            </div>
          </div>

          {/* Record summary */}
          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">{summary.type_label}</p>
            <p className="font-bold text-slate-800 text-sm">{summary.title}</p>
            {summary.description && <p className="text-xs text-slate-500">{summary.description}</p>}
            {summary.amount > 0 && <p className="text-sm font-bold text-[#1A4D2E]">{php(summary.amount)}</p>}
            {summary.date && <p className="text-[10px] text-slate-400">{summary.date}</p>}
          </div>

          <p className="text-xs text-slate-500 mt-2 flex items-center gap-1">
            <AlertTriangle size={11} className="text-amber-500" />
            Confirm this is the correct record before uploading.
          </p>
        </div>

        {/* Already uploaded */}
        {alreadyUploaded > 0 && (
          <div className="bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-2.5 flex items-center gap-2">
            <Check size={14} className="text-emerald-600 shrink-0" />
            <p className="text-xs text-emerald-700">{alreadyUploaded} photo{alreadyUploaded !== 1 ? 's' : ''} already uploaded to this record</p>
          </div>
        )}

        {/* File picker */}
        <div className="bg-white rounded-2xl p-5 shadow-sm border border-slate-200 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-slate-700 text-sm">Add Photos</h2>
            <span className="text-xs text-slate-400">{files.length}/{canUploadMore + files.length} selected · {10 - alreadyUploaded} remaining</span>
          </div>

          {/* Selected file previews */}
          {files.length > 0 && (
            <div className="grid grid-cols-3 gap-2">
              {files.map((f, i) => (
                <div key={i} className="relative aspect-square rounded-xl overflow-hidden bg-slate-100 border border-slate-200">
                  {f.previewUrl ? (
                    <img src={f.previewUrl} alt={f.name} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Image size={20} className="text-slate-400" />
                    </div>
                  )}
                  <button onClick={() => removeFile(i)}
                    className="absolute top-1 right-1 w-5 h-5 rounded-full bg-black/60 text-white flex items-center justify-center">
                    <X size={11} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Add photo buttons */}
          {canUploadMore > 0 && (
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => { fileInputRef.current.setAttribute('capture', 'environment'); fileInputRef.current.click(); }}
                className="flex flex-col items-center gap-1.5 p-3 rounded-xl border-2 border-dashed border-[#1A4D2E]/40 text-[#1A4D2E] hover:bg-[#1A4D2E]/5 transition-colors">
                <Camera size={22} />
                <span className="text-xs font-medium">Take Photo</span>
              </button>
              <button
                onClick={() => { fileInputRef.current.removeAttribute('capture'); fileInputRef.current.click(); }}
                className="flex flex-col items-center gap-1.5 p-3 rounded-xl border-2 border-dashed border-slate-300 text-slate-500 hover:bg-slate-50 transition-colors">
                <Image size={22} />
                <span className="text-xs font-medium">Choose from Gallery</span>
              </button>
            </div>
          )}

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,.pdf"
            multiple
            className="hidden"
            onChange={handleFiles}
          />

          {canUploadMore <= 0 && files.length === 0 && (
            <p className="text-xs text-slate-400 text-center">Maximum 10 files per record</p>
          )}
        </div>

        {/* Upload button */}
        {files.length > 0 && (
          <button
            onClick={handleUpload}
            disabled={uploading}
            className="w-full h-14 rounded-2xl bg-[#1A4D2E] text-white font-bold text-base flex items-center justify-center gap-2 shadow-lg active:scale-[0.98] transition-transform disabled:opacity-60"
          >
            {uploading ? (
              <><RefreshCw size={18} className="animate-spin" /> Uploading...</>
            ) : (
              <><Upload size={18} /> Upload {files.length} Photo{files.length !== 1 ? 's' : ''}</>
            )}
          </button>
        )}

        <p className="text-center text-[10px] text-slate-400 pb-4">
          Link expires 1 hour after it was generated.<br/>Up to 10 photos per record.
        </p>
      </div>
    </div>
  );
}
