/**
 * DocUploadPage — public mobile-friendly page for uploading business documents.
 * Accessible at /doc-upload/:token — no login required.
 * Shows category/type context so user can confirm they're uploading to the right place.
 * Token expires after 15 minutes.
 */
import { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { Check, Upload, Image, X, AlertTriangle, RefreshCw, Camera, FileText, FolderOpen } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

export default function DocUploadPage() {
  const { token } = useParams();
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    loadPreview();
  }, [token]); // eslint-disable-line

  const loadPreview = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/documents/qr-upload/${token}`);
      if (!res.ok) {
        let msg = 'Upload link not found or expired';
        try { const data = await res.json(); msg = data.detail || msg; } catch {}
        setError(msg);
      } else {
        setPreview(await res.json());
      }
    } catch {
      setError('Cannot connect to server. Check your internet connection.');
    }
    setLoading(false);
  };

  const handleFiles = (e) => {
    const selected = Array.from(e.target.files || []);
    const toAdd = selected.slice(0, 10 - files.length);
    const withPreview = toAdd.map(f => ({
      file: f,
      previewUrl: f.type.startsWith('image/') ? URL.createObjectURL(f) : null,
      name: f.name,
      size: f.size,
      isPdf: f.type === 'application/pdf' || f.name.endsWith('.pdf'),
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
      const res = await fetch(`${BACKEND_URL}/api/documents/qr-upload/${token}`, {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || 'Upload failed');
      } else {
        const data = await res.json();
        setResult(data);
        setFiles([]);
      }
    } catch {
      setError('Upload failed. Check your internet connection.');
    }
    setUploading(false);
  };

  const formatSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  // Loading
  if (loading) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center" data-testid="doc-upload-loading">
      <RefreshCw size={24} className="animate-spin text-[#1A4D2E]" />
    </div>
  );

  // Error
  if (error) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4" data-testid="doc-upload-error">
      <div className="bg-white rounded-2xl p-6 shadow-lg max-w-sm w-full text-center space-y-3">
        <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mx-auto">
          <AlertTriangle size={22} className="text-red-600" />
        </div>
        <h2 className="font-bold text-slate-800 text-lg">Link Invalid or Expired</h2>
        <p className="text-sm text-slate-500">{error}</p>
        <p className="text-xs text-slate-400">Document upload links expire after 15 minutes. Ask the staff member to generate a new QR code from the Documents page.</p>
      </div>
    </div>
  );

  // Success
  if (result) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4" data-testid="doc-upload-success">
      <div className="bg-white rounded-2xl p-8 shadow-lg max-w-sm w-full text-center space-y-4">
        <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mx-auto">
          <Check size={28} className="text-emerald-600" />
        </div>
        <h2 className="font-bold text-slate-800 text-xl">Document Uploaded!</h2>
        <p className="text-slate-500 text-sm">{result.uploaded} file{result.uploaded !== 1 ? 's' : ''} saved successfully.</p>
        <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-left space-y-1">
          <p className="text-xs font-semibold text-emerald-800">{preview?.category_label}</p>
          <p className="text-sm font-bold text-emerald-700">{preview?.sub_category_label}</p>
          {result.document_name && (
            <p className="text-xs text-emerald-600">{result.document_name}</p>
          )}
        </div>
        <p className="text-xs text-slate-400">You can close this tab. The document is now visible in AgriBooks Documents.</p>
      </div>
    </div>
  );

  // Upload form
  const coverageText = preview?.coverage_months?.length > 0
    ? preview.coverage_months.map(m => MONTH_NAMES[m - 1]).join(', ')
    : null;

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#1A4D2E]/5 to-slate-100" data-testid="doc-upload-page">
      <div className="max-w-sm mx-auto px-4 py-6 space-y-4">
        {/* Header */}
        <div className="bg-white rounded-2xl p-5 shadow-sm border border-slate-200">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-xl bg-[#1A4D2E] flex items-center justify-center shrink-0">
              <FolderOpen size={18} className="text-white" />
            </div>
            <div>
              <h1 className="font-bold text-slate-800 text-base">Upload Document</h1>
              <p className="text-[11px] text-slate-400">AgriBooks Document Cloud</p>
            </div>
          </div>

          {/* Context summary */}
          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-1.5">
            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">Uploading to</p>
            <p className="font-bold text-slate-800 text-sm" data-testid="doc-upload-category">{preview?.category_label}</p>
            <p className="text-xs text-slate-600" data-testid="doc-upload-subcategory">{preview?.sub_category_label}</p>
            {preview?.year && (
              <p className="text-xs text-slate-500">Year: {preview.year}</p>
            )}
            {coverageText && (
              <div className="flex items-center gap-1.5 mt-1">
                <span className="text-[10px] font-semibold text-slate-400">Coverage:</span>
                <span className="text-xs text-[#1A4D2E] font-medium">{coverageText}</span>
              </div>
            )}
          </div>

          <p className="text-xs text-slate-500 mt-2 flex items-center gap-1">
            <AlertTriangle size={11} className="text-amber-500 shrink-0" />
            Confirm this is the correct document type before uploading.
          </p>
        </div>

        {/* File picker */}
        <div className="bg-white rounded-2xl p-5 shadow-sm border border-slate-200 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-slate-700 text-sm">Add Files</h2>
            <span className="text-xs text-slate-400">{files.length} selected</span>
          </div>

          {/* Selected file previews */}
          {files.length > 0 && (
            <div className="space-y-2">
              {files.map((f, i) => (
                <div key={i} className="relative flex items-center gap-2 p-2 bg-slate-50 rounded-xl border border-slate-200">
                  {f.previewUrl ? (
                    <img src={f.previewUrl} alt={f.name} className="w-12 h-12 rounded-lg object-cover shrink-0" />
                  ) : (
                    <div className="w-12 h-12 rounded-lg bg-blue-50 flex items-center justify-center shrink-0">
                      <FileText size={20} className="text-blue-500" />
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-slate-700 truncate">{f.name}</p>
                    <p className="text-[10px] text-slate-400">{formatSize(f.size)}</p>
                  </div>
                  <button
                    onClick={() => removeFile(i)}
                    className="w-7 h-7 rounded-full bg-red-100 text-red-500 flex items-center justify-center shrink-0 hover:bg-red-200"
                    data-testid={`remove-file-${i}`}
                  >
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Add file buttons */}
          {files.length < 10 && (
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => { fileInputRef.current.setAttribute('capture', 'environment'); fileInputRef.current.click(); }}
                className="flex flex-col items-center gap-1.5 p-4 rounded-xl border-2 border-dashed border-[#1A4D2E]/40 text-[#1A4D2E] hover:bg-[#1A4D2E]/5 transition-colors"
                data-testid="camera-btn"
              >
                <Camera size={24} />
                <span className="text-xs font-medium">Take Photo</span>
              </button>
              <button
                onClick={() => { fileInputRef.current.removeAttribute('capture'); fileInputRef.current.click(); }}
                className="flex flex-col items-center gap-1.5 p-4 rounded-xl border-2 border-dashed border-slate-300 text-slate-500 hover:bg-slate-50 transition-colors"
                data-testid="gallery-btn"
              >
                <Image size={24} />
                <span className="text-xs font-medium">Browse Files</span>
              </button>
            </div>
          )}

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,.pdf,.doc,.docx,.xls,.xlsx"
            multiple
            className="hidden"
            onChange={handleFiles}
            data-testid="file-input"
          />

          <p className="text-[10px] text-slate-400 text-center">
            PDF, Images, Word, Excel — max 25MB each
          </p>
        </div>

        {/* Upload button */}
        {files.length > 0 && (
          <button
            onClick={handleUpload}
            disabled={uploading}
            className="w-full h-14 rounded-2xl bg-[#1A4D2E] text-white font-bold text-base flex items-center justify-center gap-2 shadow-lg active:scale-[0.98] transition-transform disabled:opacity-60"
            data-testid="upload-submit-btn"
          >
            {uploading ? (
              <><RefreshCw size={18} className="animate-spin" /> Uploading...</>
            ) : (
              <><Upload size={18} /> Upload {files.length} File{files.length !== 1 ? 's' : ''}</>
            )}
          </button>
        )}

        <p className="text-center text-[10px] text-slate-400 pb-4">
          Link expires 15 minutes after it was generated.
        </p>
      </div>
    </div>
  );
}
