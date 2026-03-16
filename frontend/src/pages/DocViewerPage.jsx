import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import {
  Lock, FileText, Building2, ArrowRight, CreditCard, CheckCircle2,
  AlertTriangle, Printer, Image, Smartphone, Package, ChevronDown,
  ShieldCheck, RefreshCw, Search, Boxes
} from 'lucide-react';
import axios from 'axios';

const BACKEND = process.env.REACT_APP_BACKEND_URL || '';
const php = (v) => `₱${(parseFloat(v) || 0).toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtDateTime = (d) => { try { return new Date(d).toLocaleString('en-PH', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); } catch { return d || ''; } };

function getTerminalSession() {
  try { const s = localStorage.getItem('agrismart_terminal'); return s ? JSON.parse(s) : null; } catch { return null; }
}

// ── Release Stocks Panel ──────────────────────────────────────────────────────
function ReleaseStocksPanel({ basic, docCode, onDone }) {
  const [items, setItems] = useState(() =>
    (basic.reservations || []).map(r => ({
      ...r, input_qty: r.sold_qty_remaining > 0 ? String(r.sold_qty_remaining) : '0',
    }))
  );
  const [pin, setPin] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState(null);

  const setQty = (idx, val) => setItems(prev => prev.map((it, i) => i === idx ? { ...it, input_qty: val } : it));

  const handleRelease = async () => {
    if (!pin) { setError('PIN is required'); return; }
    const releaseItems = items
      .filter(it => parseFloat(it.input_qty || 0) > 0 && it.sold_qty_remaining > 0)
      .map(it => ({ sold_product_id: it.sold_product_id, qty_release: parseFloat(it.input_qty) }));
    if (!releaseItems.length) { setError('Enter at least one quantity to release'); return; }
    setLoading(true); setError('');
    const releaseRef = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}`;
    try {
      const res = await axios.post(`${BACKEND}/api/qr-actions/${docCode}/release_stocks`, { pin, release_ref: releaseRef, items: releaseItems });
      setDone(res.data);
      if (onDone) onDone(res.data.stock_release_status);
    } catch (e) { setError(e.response?.data?.detail || 'Release failed'); }
    setLoading(false);
  };

  if (done) return (
    <div className="bg-white rounded-xl border border-emerald-200 p-6 text-center space-y-3" data-testid="release-done">
      <CheckCircle2 size={40} className="text-emerald-500 mx-auto" />
      <p className="font-bold text-emerald-700 text-lg">Release #{done.release_number} Recorded</p>
      <p className="text-sm text-slate-500">Authorized by {done.authorized_by}</p>
      <div className="space-y-1 text-sm text-left bg-slate-50 rounded-lg p-3">
        {done.items_released.map((it, i) => (
          <div key={i} className="flex justify-between">
            <span className="text-slate-600">{it.product_name}</span>
            <span className="font-semibold">{it.qty_released} {it.unit}</span>
          </div>
        ))}
      </div>
      {done.fully_released
        ? <p className="text-emerald-700 font-semibold text-sm">All stock fully released!</p>
        : <p className="text-amber-600 text-sm">{done.remaining_qty} units still pending — scan QR again for next batch.</p>
      }
    </div>
  );

  return (
    <div className="bg-white rounded-xl border-2 border-amber-200 overflow-hidden" data-testid="release-stocks-panel">
      <div className="px-5 py-3 bg-amber-50 flex items-center gap-2">
        <Boxes size={16} className="text-amber-600" />
        <span className="text-sm font-semibold text-amber-800">Release Stock</span>
        <Badge className="text-[10px] bg-amber-100 text-amber-700 border-0 ml-auto">
          {basic.stock_release_status === 'partially_released' ? 'Partially Released' : 'Unreleased'}
        </Badge>
      </div>
      <div className="p-5 space-y-4">
        <div className="space-y-3">
          {items.map((it, idx) => {
            const isFullyDone = it.sold_qty_remaining <= 0;
            return (
              <div key={it.sold_product_id} className={`rounded-lg border p-3 ${isFullyDone ? 'bg-slate-50 opacity-60' : 'bg-white'}`}>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div>
                    <p className="text-sm font-semibold text-slate-800">{it.sold_product_name}</p>
                    <p className="text-xs text-slate-400">Ordered: {it.sold_qty_ordered} {it.sold_unit} · Released: {it.sold_qty_released} · Remaining: {it.sold_qty_remaining}</p>
                  </div>
                  {isFullyDone && <CheckCircle2 size={16} className="text-emerald-500 shrink-0 mt-0.5" />}
                </div>
                {!isFullyDone && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500 shrink-0">Release now:</span>
                    <Input type="number" min="0" max={it.sold_qty_remaining} value={it.input_qty}
                      onChange={e => setQty(idx, e.target.value)}
                      className="h-9 text-center font-semibold w-28" data-testid={`release-qty-${it.sold_product_id}`} />
                    <span className="text-xs text-slate-400">{it.sold_unit}</span>
                    <button onClick={() => setQty(idx, String(it.sold_qty_remaining))} className="text-xs text-blue-600 hover:underline ml-auto shrink-0">All</button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
        <div className="space-y-2">
          <p className="text-xs text-slate-500 flex items-center gap-1"><Lock size={11} /> Branch Manager PIN, Admin PIN, or Admin TOTP</p>
          <Input type="password" value={pin} onChange={e => { setPin(e.target.value); setError(''); }}
            onKeyDown={e => e.key === 'Enter' && handleRelease()}
            placeholder="Enter PIN to confirm release"
            className="h-11 text-center text-lg font-mono tracking-widest" data-testid="release-pin-input" />
        </div>
        {error && <p className="text-red-500 text-xs flex items-center gap-1"><AlertTriangle size={12} />{error}</p>}
        <Button className="w-full h-11 bg-amber-600 hover:bg-amber-700 text-white font-semibold"
          onClick={handleRelease} disabled={loading || !pin} data-testid="confirm-release-btn">
          {loading ? <RefreshCw size={14} className="animate-spin mr-2" /> : <Boxes size={14} className="mr-2" />}Confirm Release
        </Button>
      </div>
    </div>
  );
}

// ── Release History Section ───────────────────────────────────────────────────
function ReleaseHistorySection({ releases, reservations }) {
  const [open, setOpen] = useState(false);
  if (!releases || releases.length === 0) return null;

  const totalOrdered = (reservations || []).reduce((s, r) => s + (r.sold_qty_ordered || 0), 0);
  const totalReleased = releases.reduce((s, r) => s + (r.total_qty_released || 0), 0);

  return (
    <div className="bg-white rounded-xl border overflow-hidden" data-testid="release-history">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full px-5 py-4 flex items-center justify-between hover:bg-slate-50 transition-colors"
        data-testid="release-history-toggle"
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-blue-50 flex items-center justify-center">
            <Boxes size={16} className="text-blue-600" />
          </div>
          <div className="text-left">
            <p className="text-sm font-semibold text-slate-800">Release History</p>
            <p className="text-xs text-slate-400">
              {releases.length} batch{releases.length !== 1 ? 'es' : ''} · {totalReleased} of {totalOrdered} units released
            </p>
          </div>
        </div>
        <ChevronDown size={16} className={`text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="border-t border-slate-100">
          <div className="relative px-5 py-4 space-y-0">
            <div className="absolute left-[2.35rem] top-6 bottom-6 w-px bg-slate-200" />
            {releases.map((r, idx) => (
              <div key={idx} className="relative flex gap-4 pb-4 last:pb-0" data-testid={`release-event-${r.release_number}`}>
                <div className="relative z-10 w-8 h-8 rounded-full bg-emerald-100 border-2 border-emerald-300 flex items-center justify-center shrink-0">
                  <span className="text-[10px] font-bold text-emerald-700">#{r.release_number}</span>
                </div>
                <div className="flex-1 bg-slate-50 rounded-lg p-3 min-w-0">
                  <div className="flex items-start justify-between gap-2 flex-wrap">
                    <p className="text-sm font-semibold text-slate-800">
                      Release #{r.release_number}
                      {r.fully_released && (
                        <span className="ml-2 text-[10px] bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full font-medium">Completed</span>
                      )}
                    </p>
                    <p className="text-[11px] text-slate-400 shrink-0">{fmtDateTime(r.released_at)}</p>
                  </div>
                  <div className="mt-2 space-y-1">
                    {r.items.map((it, i) => (
                      <div key={i} className="flex justify-between text-xs">
                        <span className="text-slate-600 truncate">{it.product_name}</span>
                        <span className="font-semibold text-slate-800 shrink-0 ml-2">{it.qty_released} {it.unit}</span>
                      </div>
                    ))}
                  </div>
                  <div className="mt-2 pt-2 border-t border-slate-200 flex items-center justify-between text-[11px]">
                    <span className="text-slate-400">
                      By <span className="font-medium text-slate-600">{r.released_by_name}</span>
                      <span className="mx-1 text-slate-300">·</span>
                      <span className="text-slate-400 capitalize">{(r.pin_method || '').replace('_', ' ')}</span>
                    </span>
                    <span>
                      {r.remaining_after > 0
                        ? <span className="text-amber-600">{r.remaining_after} remaining</span>
                        : <span className="text-emerald-600">All released</span>
                      }
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div className="px-5 pb-4">
            <div className="bg-slate-50 rounded-lg p-3 flex items-center justify-between text-sm">
              <span className="text-slate-500">Total released across all batches</span>
              <span className="font-bold text-slate-800">{totalReleased} / {totalOrdered} units</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}



export default function DocViewerPage() {
  const { code: codeParam } = useParams();
  const navigate = useNavigate();
  const [manualCode, setManualCode] = useState('');
  const code = codeParam;

  const [basic, setBasic] = useState(null);
  const [loading, setLoading] = useState(!!code);
  const [error, setError] = useState('');
  const [releaseStatus, setReleaseStatus] = useState(null);

  const [showPinPrompt, setShowPinPrompt] = useState(false);
  const [pin, setPin] = useState('');
  const [pinLoading, setPinLoading] = useState(false);
  const [pinError, setPinError] = useState('');
  const [fullData, setFullData] = useState(null);

  const [terminalSession] = useState(() => getTerminalSession());
  const isTerminal = !!terminalSession;
  const [terminalAction, setTerminalAction] = useState('');
  const [terminalPin, setTerminalPin] = useState('');
  const [terminalLoading, setTerminalLoading] = useState(false);
  const [terminalError, setTerminalError] = useState('');

  useEffect(() => {
    if (!code) return;
    setLoading(true);
    axios.get(`${BACKEND}/api/doc/view/${code?.toUpperCase()}`)
      .then(res => { setBasic(res.data); setReleaseStatus(res.data.stock_release_status); setError(''); })
      .catch(e => setError(e.response?.data?.detail || 'Document not found'))
      .finally(() => setLoading(false));
  }, [code]);

  const handleManualLookup = () => {
    const c = manualCode.trim().toUpperCase();
    if (c.length >= 6) navigate(`/doc/${c}`);
  };

  const handleUnlockFull = async () => {
    if (!pin) return;
    setPinLoading(true); setPinError('');
    try {
      const res = await axios.post(`${BACKEND}/api/doc/lookup`, { code: code?.toUpperCase(), pin });
      setFullData(res.data); setShowPinPrompt(false); setPin('');
    } catch (e) { setPinError(e.response?.data?.detail || 'Invalid PIN'); }
    setPinLoading(false);
  };

  const handleTerminalPull = async () => {
    if (!terminalPin) return;
    setTerminalLoading(true); setTerminalError('');
    try {
      const headers = terminalSession?.token ? { Authorization: `Bearer ${terminalSession.token}` } : {};
      if (basic.doc_type === 'purchase_order')
        await axios.post(`${BACKEND}/api/terminal/pull-po`, { po_id: basic.doc_id, pin: terminalPin }, { headers });
      else if (basic.doc_type === 'branch_transfer')
        await axios.post(`${BACKEND}/api/terminal/pull-transfer`, { transfer_id: basic.doc_id, pin: terminalPin }, { headers });
      setTerminalAction('success');
    } catch (e) { setTerminalError(e.response?.data?.detail || 'Action failed'); }
    setTerminalLoading(false);
  };

  // ── No code — show entry form ─────────────────────────────────────────────
  if (!code) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-lg p-8 w-full max-w-sm space-y-5">
        <div className="text-center">
          <div className="w-14 h-14 rounded-2xl bg-[#1A4D2E] flex items-center justify-center mx-auto mb-4">
            <Search size={24} className="text-white" />
          </div>
          <h1 className="text-xl font-bold text-slate-800" style={{ fontFamily: 'Manrope' }}>Find Document</h1>
          <p className="text-sm text-slate-500 mt-1">Enter the document code printed on your receipt</p>
        </div>
        <Input value={manualCode} onChange={e => setManualCode(e.target.value.toUpperCase())}
          onKeyDown={e => e.key === 'Enter' && handleManualLookup()}
          placeholder="e.g. AB12CD34" className="h-12 text-center text-xl font-mono tracking-widest uppercase"
          maxLength={10} autoFocus data-testid="doc-code-input" />
        <Button className="w-full h-11 bg-[#1A4D2E] hover:bg-[#14532d] text-white font-semibold"
          onClick={handleManualLookup} disabled={manualCode.trim().length < 6} data-testid="doc-code-search-btn">
          Find Document
        </Button>
      </div>
    </div>
  );

  if (loading) return <div className="min-h-screen bg-slate-50 flex items-center justify-center"><RefreshCw size={24} className="animate-spin text-slate-400" /></div>;

  if (error) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-lg p-8 text-center max-w-sm space-y-4">
        <AlertTriangle size={40} className="text-amber-500 mx-auto" />
        <h2 className="text-lg font-bold text-slate-800">Document Not Found</h2>
        <p className="text-slate-500 text-sm">Code: <span className="font-mono font-bold">{code?.toUpperCase()}</span></p>
        <p className="text-slate-400 text-sm">{error}</p>
        <Button variant="outline" className="w-full" onClick={() => navigate('/doc')}>Try Another Code</Button>
      </div>
    </div>
  );

  if (!basic) return null;

  const statusColor = { 'Fully Paid': 'bg-emerald-100 text-emerald-700', 'Completed': 'bg-emerald-100 text-emerald-700', 'In Transit': 'bg-blue-100 text-blue-700', 'Draft': 'bg-slate-100 text-slate-600', 'On Terminal': 'bg-amber-100 text-amber-700', 'Pending Review': 'bg-yellow-100 text-yellow-700', 'Disputed': 'bg-red-100 text-red-700', 'Cancelled': 'bg-red-100 text-red-600' };
  const sColor = Object.entries(statusColor).find(([k]) => basic.status?.includes(k))?.[1] || 'bg-slate-100 text-slate-600';
  const effectiveReleaseStatus = releaseStatus || basic.stock_release_status;
  const showReleaseAction = basic.available_actions?.includes('release_stocks') && effectiveReleaseStatus !== 'fully_released' && effectiveReleaseStatus !== 'expired';

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-2xl mx-auto p-4 sm:p-6 space-y-4">

        {/* Tier 1: Basic View */}
        <div className="bg-white rounded-xl shadow-sm border overflow-hidden" data-testid="doc-basic-view">
          <div className="bg-[#1A4D2E] px-5 py-4">
            <p className="text-emerald-200 text-xs uppercase tracking-wider font-medium">
              {basic.doc_type === 'invoice' ? 'Sales Receipt' : basic.doc_type === 'purchase_order' ? 'Purchase Order' : 'Branch Transfer'}
            </p>
            <h1 className="text-white text-xl font-bold mt-0.5" data-testid="doc-number">{basic.number}</h1>
            <div className="flex items-center justify-between mt-1">
              <p className="text-emerald-200/70 text-sm">{fmtDateTime(basic.date)}</p>
              {basic.release_mode === 'partial' && (
                <Badge className={`text-[10px] ${effectiveReleaseStatus === 'fully_released' ? 'bg-emerald-500 text-white' : effectiveReleaseStatus === 'partially_released' ? 'bg-blue-500 text-white' : effectiveReleaseStatus === 'expired' ? 'bg-slate-400 text-white' : 'bg-amber-400 text-white'}`}>
                  {effectiveReleaseStatus === 'fully_released' ? 'All Released' : effectiveReleaseStatus === 'partially_released' ? 'Partially Released' : effectiveReleaseStatus === 'expired' ? 'Expired' : 'Unreleased'}
                </Badge>
              )}
            </div>
          </div>
          <div className="px-5 py-4 border-b border-slate-100">
            <div className="flex items-center justify-between">
              <div>
                {basic.doc_type === 'invoice' && <p className="text-sm text-slate-500">Customer: <span className="font-semibold text-slate-800">{basic.customer_name}</span></p>}
                {basic.doc_type === 'purchase_order' && <p className="text-sm text-slate-500">Supplier: <span className="font-semibold text-slate-800">{basic.supplier_name}</span></p>}
                {basic.doc_type === 'branch_transfer' && (
                  <div className="flex items-center gap-2 text-sm">
                    <span className="font-semibold text-slate-800">{basic.from_branch}</span>
                    <ArrowRight size={14} className="text-slate-400" />
                    <span className="font-semibold text-slate-800">{basic.to_branch}</span>
                  </div>
                )}
              </div>
              <Badge className={`text-sm px-3 py-1 ${sColor}`} data-testid="doc-status">{basic.status}</Badge>
            </div>
          </div>
          <div className="divide-y divide-slate-50">
            {basic.items.map((item, i) => (
              <div key={i} className="px-5 py-3 flex items-center justify-between">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-800 truncate">{item.name}</p>
                  <p className="text-xs text-slate-400">Qty: {item.qty} × {php(item.price)}</p>
                </div>
                <span className="text-sm font-semibold font-mono text-slate-800 shrink-0 ml-3">{php(item.total)}</span>
              </div>
            ))}
          </div>
          <div className="px-5 py-4 bg-slate-50 border-t border-slate-100">
            <div className="flex items-center justify-between">
              <span className="text-base font-semibold text-slate-700">{basic.doc_type === 'branch_transfer' ? 'Transfer Total' : 'Grand Total'}</span>
              <span className="text-xl font-bold font-mono text-[#1A4D2E]" data-testid="doc-total">{php(basic.grand_total || basic.total)}</span>
            </div>
            {basic.balance > 0 && <p className="text-xs text-red-500 text-right mt-1 font-semibold">Balance due: {php(basic.balance)}</p>}
          </div>
        </div>

        {/* Release Stocks Action */}
        {showReleaseAction && <ReleaseStocksPanel basic={basic} docCode={code?.toUpperCase()} onDone={(s) => setReleaseStatus(s)} />}

        {/* Release History (visible when any releases have been made) */}
        {basic.release_mode === 'partial' && (basic.stock_releases || []).length > 0 && (
          <ReleaseHistorySection releases={basic.stock_releases} reservations={basic.reservations} />
        )}

        {/* Tier 2: PIN Full Details */}
        {!fullData ? (
          <div className="bg-white rounded-xl border overflow-hidden" data-testid="tier2-locked">
            {!showPinPrompt ? (
              <button onClick={() => setShowPinPrompt(true)} className="w-full px-5 py-4 flex items-center justify-between hover:bg-slate-50 transition-colors" data-testid="view-full-details-btn">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-amber-50 flex items-center justify-center"><Lock size={16} className="text-amber-600" /></div>
                  <div className="text-left">
                    <p className="text-sm font-semibold text-slate-800">View Full Details</p>
                    <p className="text-xs text-slate-400">Payment history, attached files, notes</p>
                  </div>
                </div>
                <ChevronDown size={16} className="text-slate-400" />
              </button>
            ) : (
              <div className="p-5 space-y-3">
                <div className="flex items-center gap-3 mb-1"><Lock size={16} className="text-amber-600" /><p className="text-sm font-semibold text-slate-800">Enter PIN to view full details</p></div>
                <Input data-testid="tier2-pin-input" type="password" value={pin}
                  onChange={e => { setPin(e.target.value); setPinError(''); }}
                  onKeyDown={e => e.key === 'Enter' && handleUnlockFull()}
                  placeholder="Manager PIN, Admin PIN, or TOTP"
                  className="h-11 text-center text-lg font-mono tracking-widest" autoFocus />
                {pinError && <p className="text-red-500 text-xs flex items-center gap-1"><AlertTriangle size={12} />{pinError}</p>}
                <div className="flex gap-2">
                  <Button variant="outline" className="flex-1 h-10" onClick={() => { setShowPinPrompt(false); setPin(''); setPinError(''); }}>Cancel</Button>
                  <Button className="flex-1 h-10 bg-[#1A4D2E] hover:bg-[#14532d] text-white" onClick={handleUnlockFull} disabled={pinLoading || !pin} data-testid="tier2-unlock-btn">
                    {pinLoading ? 'Verifying...' : 'Unlock'}
                  </Button>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4" data-testid="tier2-unlocked">
            <div className="flex items-center gap-2 px-1"><ShieldCheck size={14} className="text-emerald-600" /><span className="text-xs text-emerald-600 font-medium">Full details unlocked</span></div>
            {fullData.doc_type === 'invoice' && fullData.payments?.length > 0 && (
              <div className="bg-white rounded-xl border p-4">
                <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2"><CreditCard size={14} /> Payment History</h3>
                <div className="space-y-2">
                  {fullData.payments.map((p, i) => (
                    <div key={i} className="flex items-center justify-between text-sm py-2 border-b border-slate-50 last:border-0">
                      <div><span className="font-semibold">{php(p.amount)}</span><span className="text-slate-400 ml-2">{p.method || 'Cash'}</span></div>
                      <span className="text-slate-400 text-xs">{fmtDateTime(p.date || p.paid_at)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {fullData.attached_files?.length > 0 && (
              <div className="bg-white rounded-xl border p-4">
                <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2"><Image size={14} /> Attached Documents</h3>
                <div className="grid grid-cols-3 gap-3">
                  {fullData.attached_files.map((f, i) => (
                    <a key={i} href={f.url || f.file_url} target="_blank" rel="noreferrer" className="block rounded-lg border overflow-hidden hover:shadow-md transition-shadow">
                      {(f.url || f.file_url || '').match(/\.(jpg|jpeg|png|webp)/i)
                        ? <img src={f.url || f.file_url} alt="" className="w-full h-20 object-cover" />
                        : <div className="h-20 flex items-center justify-center bg-slate-50"><FileText size={20} className="text-slate-300" /></div>}
                    </a>
                  ))}
                </div>
              </div>
            )}
            <Button variant="outline" className="w-full" onClick={() => window.print()} data-testid="reprint-btn">
              <Printer size={14} className="mr-2" /> Reprint Document
            </Button>
          </div>
        )}

        {/* Tier 3: Terminal Actions */}
        {isTerminal && (
          <div className="bg-white rounded-xl border-2 border-amber-200 overflow-hidden" data-testid="terminal-actions">
            <div className="px-5 py-3 bg-amber-50 flex items-center gap-2">
              <Smartphone size={16} className="text-amber-600" />
              <span className="text-sm font-semibold text-amber-800">Terminal Actions</span>
              <Badge className="text-[10px] bg-amber-200 text-amber-800 ml-auto">{terminalSession.branchName || 'Paired'}</Badge>
            </div>
            {terminalAction === 'success' ? (
              <div className="p-5 text-center"><CheckCircle2 size={32} className="text-emerald-500 mx-auto mb-2" /><p className="text-sm font-semibold text-emerald-700">Action completed successfully</p></div>
            ) : (
              <div className="p-5 space-y-3">
                {basic.doc_type === 'purchase_order' && ['Draft', 'Ordered', 'In Progress'].includes(basic.status) && (
                  <>
                    <p className="text-sm text-slate-600 mb-2"><Package size={14} className="inline mr-1.5 text-blue-500" />Pull this PO to your terminal for product checking</p>
                    <Input type="password" value={terminalPin} onChange={e => { setTerminalPin(e.target.value); setTerminalError(''); }} onKeyDown={e => e.key === 'Enter' && handleTerminalPull()} placeholder="Enter PIN to pull" className="h-11 text-center font-mono tracking-widest" data-testid="terminal-pin-input" />
                    {terminalError && <p className="text-red-500 text-xs flex items-center gap-1"><AlertTriangle size={12} />{terminalError}</p>}
                    <Button className="w-full h-11 bg-blue-600 hover:bg-blue-700 text-white font-semibold" onClick={handleTerminalPull} disabled={terminalLoading || !terminalPin} data-testid="terminal-pull-btn">
                      {terminalLoading ? <RefreshCw size={14} className="animate-spin mr-2" /> : <Package size={14} className="mr-2" />}Pull PO to Terminal
                    </Button>
                  </>
                )}
                {basic.doc_type === 'branch_transfer' && basic.raw_status === 'sent' && (
                  <>
                    <p className="text-sm text-slate-600 mb-2"><Building2 size={14} className="inline mr-1.5 text-blue-500" />Pull this transfer to your terminal for receiving</p>
                    <Input type="password" value={terminalPin} onChange={e => { setTerminalPin(e.target.value); setTerminalError(''); }} onKeyDown={e => e.key === 'Enter' && handleTerminalPull()} placeholder="Enter PIN to pull" className="h-11 text-center font-mono tracking-widest" data-testid="terminal-pin-input" />
                    {terminalError && <p className="text-red-500 text-xs flex items-center gap-1"><AlertTriangle size={12} />{terminalError}</p>}
                    <Button className="w-full h-11 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold" onClick={handleTerminalPull} disabled={terminalLoading || !terminalPin} data-testid="terminal-pull-btn">
                      {terminalLoading ? <RefreshCw size={14} className="animate-spin mr-2" /> : <Building2 size={14} className="mr-2" />}Pull Transfer to Terminal
                    </Button>
                  </>
                )}
                {!(basic.doc_type === 'purchase_order' && ['Draft', 'Ordered', 'In Progress'].includes(basic.status)) &&
                 !(basic.doc_type === 'branch_transfer' && basic.raw_status === 'sent') && (
                  <p className="text-sm text-slate-400 text-center py-2">No terminal actions available for this document's current status</p>
                )}
              </div>
            )}
          </div>
        )}

        <div className="text-center pb-4">
          <button onClick={() => navigate('/doc')} className="text-xs text-slate-400 hover:text-slate-600 underline">
            Enter document code manually
          </button>
        </div>
      </div>
    </div>
  );
}
