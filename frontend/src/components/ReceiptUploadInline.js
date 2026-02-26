/**
 * ReceiptUploadInline — Inline file upload widget for forms.
 * Allows direct photo upload without QR/token flow.
 * Used in: PO creation (mandatory), Branch Transfer receive (mandatory), Expense (optional).
 */
import { useState, useRef, useCallback } from 'react';
import { api } from '../contexts/AuthContext';
import { Upload, X, ImageIcon, RefreshCw, Check, Camera, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const MAX_FILES = 10;
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

export default function ReceiptUploadInline({
  required = false,
  label = 'Receipt / Proof Photos',
  recordType = 'purchase_order',
  onUploaded,          // callback({ sessionId, fileCount, files })
  compact = false,     // compact mode for smaller forms
}) {
  const [files, setFiles] = useState([]);       // { id, name, preview, size }
  const [uploading, setUploading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const inputRef = useRef(null);

  const handleFiles = useCallback(async (fileList) => {
    const newFiles = Array.from(fileList);
    if (files.length + newFiles.length > MAX_FILES) {
      toast.error(`Maximum ${MAX_FILES} files allowed`);
      return;
    }

    // Validate file types and sizes
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

      // Create previews
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

  const handlePaste = (e) => {
    if (e.clipboardData?.files?.length) {
      handleFiles(e.clipboardData.files);
    }
  };

  if (compact) {
    return (
      <div data-testid="receipt-upload-inline">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={uploading}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border ${
              files.length > 0
                ? 'border-emerald-300 bg-emerald-50 text-emerald-700'
                : required
                ? 'border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100'
                : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
            }`}
            data-testid="receipt-upload-btn"
          >
            {uploading ? (
              <RefreshCw size={12} className="animate-spin" />
            ) : files.length > 0 ? (
              <Check size={12} />
            ) : (
              <Camera size={12} />
            )}
            {files.length > 0 ? `${files.length} photo${files.length > 1 ? 's' : ''}` : 'Attach Receipt'}
          </button>
          {required && files.length === 0 && (
            <span className="text-[10px] text-amber-600 flex items-center gap-0.5">
              <AlertTriangle size={10} /> Required
            </span>
          )}
          {files.length > 0 && (
            <div className="flex gap-1">
              {files.map(f => (
                <div key={f.id} className="relative group">
                  {f.preview ? (
                    <img src={f.preview} alt="" className="w-8 h-8 rounded object-cover border border-slate-200" />
                  ) : (
                    <div className="w-8 h-8 rounded bg-slate-100 border border-slate-200 flex items-center justify-center">
                      <ImageIcon size={12} className="text-slate-400" />
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={() => removeFile(f.id)}
                    className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-red-500 text-white hidden group-hover:flex items-center justify-center"
                  >
                    <X size={8} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="image/*,application/pdf"
          multiple
          className="hidden"
          onChange={e => handleFiles(e.target.files)}
          data-testid="receipt-file-input"
        />
      </div>
    );
  }

  // Full-size upload area
  return (
    <div data-testid="receipt-upload-inline" onPaste={handlePaste}>
      <label className="text-xs text-slate-500 font-medium flex items-center gap-1.5 mb-1.5">
        <ImageIcon size={12} />
        {label}
        {required && <span className="text-red-500">*</span>}
      </label>
      <div
        className={`relative rounded-xl border-2 border-dashed transition-colors p-4 ${
          files.length > 0
            ? 'border-emerald-300 bg-emerald-50/50'
            : required
            ? 'border-amber-300 bg-amber-50/30 hover:border-amber-400'
            : 'border-slate-200 bg-slate-50/50 hover:border-slate-300'
        }`}
        onDragOver={e => e.preventDefault()}
        onDrop={handleDrop}
      >
        {files.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-2">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
              required ? 'bg-amber-100' : 'bg-slate-100'
            }`}>
              {uploading ? (
                <RefreshCw size={18} className="animate-spin text-slate-500" />
              ) : (
                <Upload size={18} className={required ? 'text-amber-600' : 'text-slate-400'} />
              )}
            </div>
            <div className="text-center">
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                disabled={uploading}
                className="text-sm font-medium text-[#1A4D2E] hover:underline"
                data-testid="receipt-upload-btn"
              >
                {uploading ? 'Uploading...' : 'Click to upload'}
              </button>
              <p className="text-[10px] text-slate-400 mt-0.5">or drag & drop · Max {MAX_FILES} files</p>
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
                      <ImageIcon size={16} className="text-slate-400" />
                      <span className="text-[8px] text-slate-400 mt-0.5 truncate max-w-[50px]">{f.name}</span>
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={() => removeFile(f.id)}
                    className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-red-500 text-white hidden group-hover:flex items-center justify-center shadow-sm"
                  >
                    <X size={10} />
                  </button>
                </div>
              ))}
              {files.length < MAX_FILES && (
                <button
                  type="button"
                  onClick={() => inputRef.current?.click()}
                  disabled={uploading}
                  className="w-16 h-16 rounded-lg border-2 border-dashed border-slate-300 bg-white hover:border-[#1A4D2E] hover:bg-emerald-50 flex flex-col items-center justify-center transition-colors"
                >
                  {uploading ? (
                    <RefreshCw size={14} className="animate-spin text-slate-400" />
                  ) : (
                    <>
                      <Upload size={14} className="text-slate-400" />
                      <span className="text-[9px] text-slate-400 mt-0.5">Add more</span>
                    </>
                  )}
                </button>
              )}
            </div>
            <p className="text-[10px] text-emerald-600 flex items-center gap-1">
              <Check size={10} /> {files.length} receipt{files.length > 1 ? 's' : ''} attached
            </p>
          </div>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="image/*,application/pdf"
        multiple
        className="hidden"
        onChange={e => { handleFiles(e.target.files); e.target.value = ''; }}
        data-testid="receipt-file-input"
      />
    </div>
  );
}
