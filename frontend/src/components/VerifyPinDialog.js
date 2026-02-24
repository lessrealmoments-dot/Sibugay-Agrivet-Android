/**
 * VerifyPinDialog — PIN entry for transaction verification.
 * Supports: Admin PIN, Admin TOTP (6-digit), Auditor PIN
 * Optionally records a discrepancy with expected vs found values.
 */
import { useState } from 'react';
import { api } from '../contexts/AuthContext';
import { ShieldCheck, ShieldAlert, X, Eye, EyeOff } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export default function VerifyPinDialog({ open, onClose, docType, docId, docLabel, onVerified }) {
  const [pin, setPin] = useState('');
  const [showPin, setShowPin] = useState(false);
  const [hasDiscrepancy, setHasDiscrepancy] = useState(false);
  const [discrepancyNote, setDiscrepancyNote] = useState('');
  const [itemDescription, setItemDescription] = useState('');
  const [expectedQty, setExpectedQty] = useState('');
  const [foundQty, setFoundQty] = useState('');
  const [unit, setUnit] = useState('');
  const [unitCost, setUnitCost] = useState('');
  const [loading, setLoading] = useState(false);

  if (!open) return null;

  const valueImpact = hasDiscrepancy && expectedQty !== '' && foundQty !== '' && unitCost !== ''
    ? ((parseFloat(foundQty) - parseFloat(expectedQty)) * parseFloat(unitCost || 0)).toFixed(2)
    : null;

  const handleSubmit = async () => {
    if (!pin) { toast.error('Please enter your PIN'); return; }
    if (hasDiscrepancy && !discrepancyNote) { toast.error('Please describe the discrepancy'); return; }

    setLoading(true);
    try {
      const payload = {
        pin,
        has_discrepancy: hasDiscrepancy,
        discrepancy_note: discrepancyNote,
        item_description: itemDescription,
        expected_qty: expectedQty !== '' ? parseFloat(expectedQty) : null,
        found_qty: foundQty !== '' ? parseFloat(foundQty) : null,
        unit,
        unit_cost: parseFloat(unitCost || 0),
      };
      const res = await api.post(`${BACKEND_URL}/api/verify/${docType}/${docId}`, payload);
      toast.success(`Verified by ${res.data.verified_by}`);
      onVerified?.(res.data);
      handleClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Verification failed — invalid PIN');
    }
    setLoading(false);
  };

  const handleClose = () => {
    setPin(''); setShowPin(false); setHasDiscrepancy(false);
    setDiscrepancyNote(''); setItemDescription('');
    setExpectedQty(''); setFoundQty(''); setUnit(''); setUnitCost('');
    onClose();
  };

  return (
    <div
      className="fixed inset-0 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.65)', zIndex: 9999 }}
      onClick={e => { if (e.target === e.currentTarget) handleClose(); }}
    >
      <div className="relative bg-white rounded-2xl shadow-2xl w-full overflow-y-auto" style={{ maxWidth: '420px', maxHeight: '90vh' }}>
        <button onClick={handleClose} className="absolute top-3 right-3 z-10 w-7 h-7 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center">
          <X size={14} className="text-slate-500" />
        </button>

        <div className="p-5">
          {/* Header */}
          <div className="flex items-center gap-2 mb-4">
            <span className="inline-flex w-8 h-8 rounded-lg bg-[#1A4D2E] items-center justify-center shrink-0">
              <ShieldCheck size={15} className="text-white" />
            </span>
            <div>
              <p className="font-semibold text-slate-800 text-sm leading-tight">Verify Transaction</p>
              <p className="text-[11px] text-slate-400 truncate">{docLabel}</p>
            </div>
          </div>

          {/* PIN Input */}
          <div className="mb-4">
            <label className="text-xs font-medium text-slate-600 mb-1 block">Authorization PIN</label>
            <p className="text-[10px] text-slate-400 mb-2">Enter Admin PIN, TOTP code (6-digit), or your Auditor PIN</p>
            <div className="relative">
              <input
                type={showPin ? 'text' : 'password'}
                value={pin}
                onChange={e => setPin(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSubmit()}
                placeholder="Enter PIN..."
                className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm pr-10 focus:outline-none focus:ring-2 focus:ring-[#1A4D2E]/30"
                autoFocus
              />
              <button
                onClick={() => setShowPin(v => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                {showPin ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>

          {/* Discrepancy Toggle */}
          <div className="mb-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <div
                onClick={() => setHasDiscrepancy(v => !v)}
                className={`w-9 h-5 rounded-full transition-colors relative ${hasDiscrepancy ? 'bg-amber-500' : 'bg-slate-200'}`}
              >
                <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${hasDiscrepancy ? 'translate-x-4' : 'translate-x-0.5'}`} />
              </div>
              <span className="text-sm text-slate-700 font-medium">Flag a discrepancy</span>
              <ShieldAlert size={14} className={hasDiscrepancy ? 'text-amber-500' : 'text-slate-300'} />
            </label>
            <p className="text-[10px] text-slate-400 mt-1 ml-11">Physical evidence doesn't match the system record</p>
          </div>

          {/* Discrepancy Details */}
          {hasDiscrepancy && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 mb-4 flex flex-col gap-3">
              <div>
                <label className="text-[11px] font-medium text-amber-800 mb-1 block">Item / Description *</label>
                <input
                  type="text"
                  value={itemDescription}
                  onChange={e => setItemDescription(e.target.value)}
                  placeholder="e.g. Rice 50kg bags"
                  className="w-full border border-amber-200 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none bg-white"
                />
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="text-[11px] font-medium text-amber-800 mb-1 block">Expected</label>
                  <input
                    type="number"
                    value={expectedQty}
                    onChange={e => setExpectedQty(e.target.value)}
                    placeholder="15"
                    className="w-full border border-amber-200 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none bg-white"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-medium text-amber-800 mb-1 block">Found</label>
                  <input
                    type="number"
                    value={foundQty}
                    onChange={e => setFoundQty(e.target.value)}
                    placeholder="5"
                    className="w-full border border-amber-200 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none bg-white"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-medium text-amber-800 mb-1 block">Unit</label>
                  <input
                    type="text"
                    value={unit}
                    onChange={e => setUnit(e.target.value)}
                    placeholder="bags"
                    className="w-full border border-amber-200 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none bg-white"
                  />
                </div>
              </div>
              <div>
                <label className="text-[11px] font-medium text-amber-800 mb-1 block">Unit Cost (₱)</label>
                <input
                  type="number"
                  value={unitCost}
                  onChange={e => setUnitCost(e.target.value)}
                  placeholder="500.00"
                  className="w-full border border-amber-200 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none bg-white"
                />
              </div>
              {valueImpact !== null && (
                <div className={`text-xs font-bold rounded-lg px-3 py-1.5 text-center ${parseFloat(valueImpact) < 0 ? 'bg-red-100 text-red-700' : parseFloat(valueImpact) > 0 ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-600'}`}>
                  Value Impact: {parseFloat(valueImpact) > 0 ? '+' : ''}₱{parseFloat(valueImpact).toLocaleString('en-PH', { minimumFractionDigits: 2 })}
                </div>
              )}
              <div>
                <label className="text-[11px] font-medium text-amber-800 mb-1 block">Note / Explanation *</label>
                <textarea
                  value={discrepancyNote}
                  onChange={e => setDiscrepancyNote(e.target.value)}
                  placeholder="e.g. Physical DR shows 5 bags, system encoded 15 — possible encoding error"
                  rows={2}
                  className="w-full border border-amber-200 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none bg-white resize-none"
                />
              </div>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex gap-2">
            <button
              onClick={handleClose}
              className="flex-1 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-600 hover:bg-slate-50 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={loading || !pin}
              className={`flex-1 py-2.5 rounded-xl font-medium text-sm transition-colors flex items-center justify-center gap-1.5
                ${hasDiscrepancy ? 'bg-amber-500 hover:bg-amber-600 text-white' : 'bg-[#1A4D2E] hover:bg-[#14532d] text-white'}
                disabled:opacity-50`}
            >
              {loading ? (
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
              ) : hasDiscrepancy ? (
                <><ShieldAlert size={14} /> Flag & Verify</>
              ) : (
                <><ShieldCheck size={14} /> Verify Transaction</>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
