import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import {
  Lock, FileText, Building2, ArrowRight, CreditCard, CheckCircle2,
  AlertTriangle, Printer, Image, Eye, Smartphone, Package, ChevronDown,
  ChevronUp, ShieldCheck, RefreshCw
} from 'lucide-react';
import axios from 'axios';

const BACKEND = process.env.REACT_APP_BACKEND_URL || '';
const php = (v) => `₱${(parseFloat(v) || 0).toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtDate = (d) => { try { return new Date(d).toLocaleDateString('en-PH', { year: 'numeric', month: 'short', day: 'numeric' }); } catch { return d || ''; } };
const fmtDateTime = (d) => { try { return new Date(d).toLocaleString('en-PH', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); } catch { return d || ''; } };

// Check if this device is a paired terminal
function getTerminalSession() {
  try {
    const stored = localStorage.getItem('agrismart_terminal');
    return stored ? JSON.parse(stored) : null;
  } catch { return null; }
}

export default function DocViewerPage() {
  const { code } = useParams();
  const [basic, setBasic] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Tier 2: PIN-protected details
  const [showPinPrompt, setShowPinPrompt] = useState(false);
  const [pin, setPin] = useState('');
  const [pinLoading, setPinLoading] = useState(false);
  const [pinError, setPinError] = useState('');
  const [fullData, setFullData] = useState(null);

  // Tier 3: Terminal state
  const [terminalSession] = useState(() => getTerminalSession());
  const isTerminal = !!terminalSession;
  const [terminalAction, setTerminalAction] = useState('');
  const [terminalPin, setTerminalPin] = useState('');
  const [terminalLoading, setTerminalLoading] = useState(false);
  const [terminalError, setTerminalError] = useState('');

  // Load Tier 1 (open) immediately
  useEffect(() => {
    setLoading(true);
    axios.get(`${BACKEND}/api/doc/view/${code?.toUpperCase()}`)
      .then(res => { setBasic(res.data); setError(''); })
      .catch(e => setError(e.response?.data?.detail || 'Document not found'))
      .finally(() => setLoading(false));
  }, [code]);

  // Tier 2: Unlock full details
  const handleUnlockFull = async () => {
    if (!pin) return;
    setPinLoading(true);
    setPinError('');
    try {
      const res = await axios.post(`${BACKEND}/api/doc/lookup`, { code: code?.toUpperCase(), pin });
      setFullData(res.data);
      setShowPinPrompt(false);
      setPin('');
    } catch (e) {
      setPinError(e.response?.data?.detail || 'Invalid PIN');
    }
    setPinLoading(false);
  };

  // Tier 3: Terminal actions
  const handleTerminalPull = async () => {
    if (!terminalPin) return;
    setTerminalLoading(true);
    setTerminalError('');
    try {
      const token = terminalSession?.token;
      const headers = token ? { Authorization: `Bearer ${token}` } : {};

      if (basic.doc_type === 'purchase_order') {
        await axios.post(`${BACKEND}/api/terminal/pull-po`, { po_id: basic.doc_id, pin: terminalPin }, { headers });
        setTerminalAction('success');
      } else if (basic.doc_type === 'branch_transfer') {
        await axios.post(`${BACKEND}/api/terminal/pull-transfer`, { transfer_id: basic.doc_id, pin: terminalPin }, { headers });
        setTerminalAction('success');
      }
    } catch (e) {
      setTerminalError(e.response?.data?.detail || 'Action failed');
    }
    setTerminalLoading(false);
  };

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <RefreshCw size={24} className="animate-spin text-slate-400" />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-lg p-8 text-center max-w-sm">
          <AlertTriangle size={40} className="text-amber-500 mx-auto mb-4" />
          <h2 className="text-lg font-bold text-slate-800 mb-2">Document Not Found</h2>
          <p className="text-slate-500 text-sm">Code: <span className="font-mono font-bold">{code?.toUpperCase()}</span></p>
          <p className="text-slate-400 text-sm mt-2">{error}</p>
        </div>
      </div>
    );
  }

  if (!basic) return null;

  const statusColor = {
    'Fully Paid': 'bg-emerald-100 text-emerald-700',
    'Completed': 'bg-emerald-100 text-emerald-700',
    'In Transit': 'bg-blue-100 text-blue-700',
    'Draft': 'bg-slate-100 text-slate-600',
    'On Terminal': 'bg-amber-100 text-amber-700',
    'Pending Review': 'bg-yellow-100 text-yellow-700',
    'Disputed': 'bg-red-100 text-red-700',
    'Cancelled': 'bg-red-100 text-red-600',
  };
  const sColor = Object.entries(statusColor).find(([k]) => basic.status?.includes(k))?.[1] || 'bg-slate-100 text-slate-600';

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-2xl mx-auto p-4 sm:p-6 space-y-4">

        {/* ═══ TIER 1: Open Basic View ═══ */}
        <div className="bg-white rounded-xl shadow-sm border overflow-hidden" data-testid="doc-basic-view">
          {/* Header bar */}
          <div className="bg-[#1A4D2E] px-5 py-4">
            <p className="text-emerald-200 text-xs uppercase tracking-wider font-medium">
              {basic.doc_type === 'invoice' ? 'Sales Receipt' : basic.doc_type === 'purchase_order' ? 'Purchase Order' : 'Branch Transfer'}
            </p>
            <h1 className="text-white text-xl font-bold mt-0.5" data-testid="doc-number">{basic.number}</h1>
            <p className="text-emerald-200/70 text-sm mt-1">{fmtDateTime(basic.date)}</p>
          </div>

          {/* Status + Party */}
          <div className="px-5 py-4 border-b border-slate-100">
            <div className="flex items-center justify-between">
              <div>
                {basic.doc_type === 'invoice' && (
                  <p className="text-sm text-slate-500">Customer: <span className="font-semibold text-slate-800">{basic.customer_name}</span></p>
                )}
                {basic.doc_type === 'purchase_order' && (
                  <p className="text-sm text-slate-500">Supplier: <span className="font-semibold text-slate-800">{basic.supplier_name}</span></p>
                )}
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

          {/* Items */}
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

          {/* Total */}
          <div className="px-5 py-4 bg-slate-50 border-t border-slate-100">
            <div className="flex items-center justify-between">
              <span className="text-base font-semibold text-slate-700">
                {basic.doc_type === 'invoice' ? 'Grand Total' : basic.doc_type === 'purchase_order' ? 'Grand Total' : 'Transfer Total'}
              </span>
              <span className="text-xl font-bold font-mono text-[#1A4D2E]" data-testid="doc-total">
                {php(basic.grand_total || basic.total)}
              </span>
            </div>
            {basic.discount > 0 && (
              <p className="text-xs text-slate-400 text-right mt-1">Discount: -{php(basic.discount)}</p>
            )}
          </div>
        </div>

        {/* ═══ TIER 2: PIN-Protected Details ═══ */}
        {!fullData ? (
          <div className="bg-white rounded-xl border overflow-hidden" data-testid="tier2-locked">
            {!showPinPrompt ? (
              <button
                onClick={() => setShowPinPrompt(true)}
                className="w-full px-5 py-4 flex items-center justify-between hover:bg-slate-50 transition-colors"
                data-testid="view-full-details-btn"
              >
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-amber-50 flex items-center justify-center">
                    <Lock size={16} className="text-amber-600" />
                  </div>
                  <div className="text-left">
                    <p className="text-sm font-semibold text-slate-800">View Full Details</p>
                    <p className="text-xs text-slate-400">Payment history, attached files, notes</p>
                  </div>
                </div>
                <ChevronDown size={16} className="text-slate-400" />
              </button>
            ) : (
              <div className="p-5 space-y-3">
                <div className="flex items-center gap-3 mb-1">
                  <Lock size={16} className="text-amber-600" />
                  <p className="text-sm font-semibold text-slate-800">Enter PIN to view full details</p>
                </div>
                <Input
                  data-testid="tier2-pin-input"
                  type="password"
                  value={pin}
                  onChange={e => { setPin(e.target.value); setPinError(''); }}
                  onKeyDown={e => e.key === 'Enter' && handleUnlockFull()}
                  placeholder="Manager PIN, Admin PIN, or TOTP"
                  className="h-11 text-center text-lg font-mono tracking-widest"
                  autoFocus
                />
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
          /* Full details unlocked */
          <div className="space-y-4" data-testid="tier2-unlocked">
            <div className="flex items-center gap-2 px-1">
              <ShieldCheck size={14} className="text-emerald-600" />
              <span className="text-xs text-emerald-600 font-medium">Full details unlocked</span>
            </div>

            {/* Payment History (invoices) */}
            {fullData.doc_type === 'invoice' && fullData.payments?.length > 0 && (
              <div className="bg-white rounded-xl border p-4">
                <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2"><CreditCard size={14} /> Payment History</h3>
                <div className="space-y-2">
                  {fullData.payments.map((p, i) => (
                    <div key={i} className="flex items-center justify-between text-sm py-2 border-b border-slate-50 last:border-0">
                      <div>
                        <span className="font-semibold">{php(p.amount)}</span>
                        <span className="text-slate-400 ml-2">{p.method || 'Cash'}</span>
                      </div>
                      <span className="text-slate-400 text-xs">{fmtDateTime(p.date || p.paid_at)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Customer balance (invoices) */}
            {fullData.doc_type === 'invoice' && fullData.customer && fullData.customer.balance > 0 && (
              <div className="bg-white rounded-xl border p-4">
                <h3 className="text-sm font-semibold text-slate-700 mb-2">Customer Account</h3>
                <p className="text-sm text-slate-500">{fullData.customer.name}</p>
                <p className="text-lg font-bold text-red-600 mt-1">Outstanding: {php(fullData.customer.balance)}</p>
              </div>
            )}

            {/* Attached Files (PO & transfers) */}
            {fullData.attached_files?.length > 0 && (
              <div className="bg-white rounded-xl border p-4">
                <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2"><Image size={14} /> Attached Documents</h3>
                <div className="grid grid-cols-3 gap-3">
                  {fullData.attached_files.map((f, i) => (
                    <a key={i} href={f.url || f.file_url} target="_blank" rel="noreferrer"
                      className="block rounded-lg border overflow-hidden hover:shadow-md transition-shadow">
                      {(f.url || f.file_url || '').match(/\.(jpg|jpeg|png|webp)/i)
                        ? <img src={f.url || f.file_url} alt="" className="w-full h-20 object-cover" />
                        : <div className="h-20 flex items-center justify-center bg-slate-50"><FileText size={20} className="text-slate-300" /></div>
                      }
                    </a>
                  ))}
                </div>
              </div>
            )}

            {/* Receiver/dispute notes (transfers) */}
            {fullData.doc_type === 'branch_transfer' && fullData.document?.receive_notes && (
              <div className="bg-white rounded-xl border p-4">
                <h3 className="text-sm font-semibold text-slate-700 mb-2">Receiver Notes</h3>
                <p className="text-sm text-slate-600">{fullData.document.receive_notes}</p>
              </div>
            )}
            {fullData.doc_type === 'branch_transfer' && fullData.document?.dispute_note && (
              <div className="bg-white rounded-xl border border-red-200 p-4">
                <h3 className="text-sm font-semibold text-red-700 mb-2">Dispute Note</h3>
                <p className="text-sm text-red-600">{fullData.document.dispute_note}</p>
              </div>
            )}

            {/* Reprint */}
            <Button variant="outline" className="w-full" onClick={() => window.print()} data-testid="reprint-btn">
              <Printer size={14} className="mr-2" /> Reprint Document
            </Button>
          </div>
        )}

        {/* ═══ TIER 3: Terminal Actions ═══ */}
        {isTerminal && (
          <div className="bg-white rounded-xl border-2 border-amber-200 overflow-hidden" data-testid="terminal-actions">
            <div className="px-5 py-3 bg-amber-50 flex items-center gap-2">
              <Smartphone size={16} className="text-amber-600" />
              <span className="text-sm font-semibold text-amber-800">Terminal Actions</span>
              <Badge className="text-[10px] bg-amber-200 text-amber-800 ml-auto">{terminalSession.branchName || 'Paired'}</Badge>
            </div>

            {terminalAction === 'success' ? (
              <div className="p-5 text-center">
                <CheckCircle2 size={32} className="text-emerald-500 mx-auto mb-2" />
                <p className="text-sm font-semibold text-emerald-700">Action completed successfully</p>
                <p className="text-xs text-slate-400 mt-1">Go to the relevant section on the terminal to continue</p>
              </div>
            ) : (
              <div className="p-5 space-y-3">
                {/* Sales credit — Apply payment */}
                {basic.doc_type === 'invoice' && basic.payment_type === 'credit' && !basic.status?.includes('Fully Paid') && (
                  <p className="text-sm text-slate-600">
                    <CreditCard size={14} className="inline mr-1.5 text-blue-500" />
                    Apply payment to this credit sale from the terminal's <strong>Receive Payments</strong> section.
                  </p>
                )}

                {/* PO — Pull to terminal */}
                {basic.doc_type === 'purchase_order' && ['Draft', 'Ordered', 'In Progress'].includes(basic.status) && (
                  <>
                    <p className="text-sm text-slate-600 mb-2">
                      <Package size={14} className="inline mr-1.5 text-blue-500" />
                      Pull this PO to your terminal for product checking
                    </p>
                    <Input
                      type="password" value={terminalPin}
                      onChange={e => { setTerminalPin(e.target.value); setTerminalError(''); }}
                      onKeyDown={e => e.key === 'Enter' && handleTerminalPull()}
                      placeholder="Enter PIN to pull"
                      className="h-11 text-center font-mono tracking-widest"
                      data-testid="terminal-pin-input"
                    />
                    {terminalError && <p className="text-red-500 text-xs flex items-center gap-1"><AlertTriangle size={12} />{terminalError}</p>}
                    <Button className="w-full h-11 bg-blue-600 hover:bg-blue-700 text-white font-semibold"
                      onClick={handleTerminalPull} disabled={terminalLoading || !terminalPin} data-testid="terminal-pull-btn">
                      {terminalLoading ? <RefreshCw size={14} className="animate-spin mr-2" /> : <Package size={14} className="mr-2" />}
                      Pull PO to Terminal
                    </Button>
                  </>
                )}

                {/* Branch Transfer — Pull to terminal */}
                {basic.doc_type === 'branch_transfer' && basic.raw_status === 'sent' && (
                  <>
                    <p className="text-sm text-slate-600 mb-2">
                      <Building2 size={14} className="inline mr-1.5 text-blue-500" />
                      Pull this transfer to your terminal for receiving
                    </p>
                    <Input
                      type="password" value={terminalPin}
                      onChange={e => { setTerminalPin(e.target.value); setTerminalError(''); }}
                      onKeyDown={e => e.key === 'Enter' && handleTerminalPull()}
                      placeholder="Enter PIN to pull"
                      className="h-11 text-center font-mono tracking-widest"
                      data-testid="terminal-pin-input"
                    />
                    {terminalError && <p className="text-red-500 text-xs flex items-center gap-1"><AlertTriangle size={12} />{terminalError}</p>}
                    <Button className="w-full h-11 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold"
                      onClick={handleTerminalPull} disabled={terminalLoading || !terminalPin} data-testid="terminal-pull-btn">
                      {terminalLoading ? <RefreshCw size={14} className="animate-spin mr-2" /> : <Building2 size={14} className="mr-2" />}
                      Pull Transfer to Terminal
                    </Button>
                  </>
                )}

                {/* No terminal action available */}
                {!(basic.doc_type === 'purchase_order' && ['Draft', 'Ordered', 'In Progress'].includes(basic.status)) &&
                 !(basic.doc_type === 'branch_transfer' && basic.raw_status === 'sent') &&
                 !(basic.doc_type === 'invoice' && basic.payment_type === 'credit' && !basic.status?.includes('Fully Paid')) && (
                  <p className="text-sm text-slate-400 text-center py-2">No terminal actions available for this document's current status</p>
                )}
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
}
