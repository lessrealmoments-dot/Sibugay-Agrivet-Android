import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Lock, FileText, Package, Building2, ArrowRight, CreditCard, CheckCircle2, AlertTriangle, Printer, Image, ExternalLink } from 'lucide-react';
import axios from 'axios';

const BACKEND = process.env.REACT_APP_BACKEND_URL || '';
const php = (v) => `₱${(parseFloat(v) || 0).toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtDate = (d) => { try { return new Date(d).toLocaleDateString('en-PH', { year: 'numeric', month: 'short', day: 'numeric' }); } catch { return d || ''; } };
const fmtDateTime = (d) => { try { return new Date(d).toLocaleString('en-PH', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); } catch { return d || ''; } };

export default function DocViewerPage() {
  const { code } = useParams();
  const [pin, setPin] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [data, setData] = useState(null);
  const [verifier, setVerifier] = useState('');

  const handleUnlock = async () => {
    if (!pin) return;
    setLoading(true);
    setError('');
    try {
      const res = await axios.post(`${BACKEND}/api/doc/lookup`, { code: code?.toUpperCase(), pin });
      setData(res.data);
      setVerifier(res.data.verifier || '');
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to look up document');
    }
    setLoading(false);
  };

  // PIN gate
  if (!data) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm overflow-hidden" data-testid="doc-pin-gate">
          <div className="bg-[#1A4D2E] px-6 py-5 text-center">
            <div className="w-12 h-12 bg-white/20 rounded-xl mx-auto mb-3 flex items-center justify-center">
              <Lock size={24} className="text-white" />
            </div>
            <h1 className="text-xl font-bold text-white">Document Viewer</h1>
            <p className="text-emerald-200 text-sm mt-1">Enter PIN to access document</p>
          </div>
          <div className="p-6 space-y-4">
            <div className="bg-slate-50 rounded-lg px-4 py-3 text-center">
              <p className="text-xs text-slate-400 uppercase tracking-wider">Document Code</p>
              <p className="text-2xl font-bold font-mono tracking-[4px] text-slate-800 mt-1" data-testid="doc-code-display">{code?.toUpperCase()}</p>
            </div>
            <Input
              data-testid="doc-pin-input"
              type="password"
              value={pin}
              onChange={e => { setPin(e.target.value); setError(''); }}
              onKeyDown={e => e.key === 'Enter' && handleUnlock()}
              placeholder="Manager PIN, Admin PIN, or TOTP"
              className="h-12 text-center text-lg font-mono tracking-widest"
              autoFocus
            />
            {error && <p className="text-red-500 text-sm text-center flex items-center justify-center gap-1"><AlertTriangle size={14} />{error}</p>}
            <Button
              data-testid="doc-unlock-btn"
              onClick={handleUnlock}
              disabled={loading || !pin}
              className="w-full h-12 bg-[#1A4D2E] hover:bg-[#14532d] text-white font-semibold text-base"
            >
              {loading ? 'Verifying...' : 'View Document'}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // Document view
  const { doc_type, document: doc } = data;

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-3xl mx-auto p-4 sm:p-6">
        {/* Header */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden mb-4">
          <div className="bg-[#1A4D2E] px-5 py-4 flex items-center justify-between">
            <div>
              <p className="text-emerald-200 text-xs uppercase tracking-wider">{doc_type === 'invoice' ? 'Sales Receipt' : doc_type === 'purchase_order' ? 'Purchase Order' : 'Branch Transfer'}</p>
              <h1 className="text-white text-xl font-bold mt-0.5" data-testid="doc-number">
                {doc.invoice_number || doc.po_number || doc.order_number || ''}
              </h1>
            </div>
            <Button size="sm" variant="outline" className="bg-white/10 border-white/30 text-white hover:bg-white/20" onClick={() => window.print()}>
              <Printer size={14} className="mr-1.5" /> Print
            </Button>
          </div>
          <div className="px-5 py-3 flex items-center justify-between text-sm">
            <span className="text-slate-500">{fmtDateTime(doc.created_at || doc.order_date || doc.purchase_date)}</span>
            <span className="text-slate-400">Verified by: {verifier}</span>
          </div>
        </div>

        {doc_type === 'invoice' && <InvoiceView doc={doc} data={data} />}
        {doc_type === 'purchase_order' && <POView doc={doc} data={data} />}
        {doc_type === 'branch_transfer' && <TransferView doc={doc} data={data} />}
      </div>
    </div>
  );
}

// ── Invoice View ────────────────────────────────────────────────────────────
function InvoiceView({ doc, data }) {
  const balance = (doc.grand_total || 0) - (doc.amount_paid || 0);
  const isPaid = balance <= 0 || doc.payment_status === 'paid';
  return (
    <div className="space-y-4">
      {/* Status + Customer */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border p-4">
          <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Payment Status</p>
          <Badge className={`text-sm px-3 py-1 ${isPaid ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
            {isPaid ? 'Fully Paid' : `Balance: ${php(balance)}`}
          </Badge>
          <p className="text-sm text-slate-500 mt-2">{doc.payment_method || 'Cash'}</p>
        </div>
        <div className="bg-white rounded-xl border p-4">
          <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Customer</p>
          <p className="font-semibold text-slate-800">{doc.customer_name || 'Walk-in'}</p>
          {data.customer?.phone && <p className="text-sm text-slate-500">{data.customer.phone}</p>}
        </div>
      </div>

      {/* Items */}
      <div className="bg-white rounded-xl border overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="bg-slate-50 text-xs text-slate-500 uppercase">
            <th className="px-4 py-3 text-left">Item</th>
            <th className="px-4 py-3 text-center">Qty</th>
            <th className="px-4 py-3 text-right">Price</th>
            <th className="px-4 py-3 text-right">Total</th>
          </tr></thead>
          <tbody>
            {(doc.items || []).map((item, i) => (
              <tr key={i} className="border-t border-slate-100">
                <td className="px-4 py-3 font-medium">{item.product_name || ''}</td>
                <td className="px-4 py-3 text-center font-mono">{item.quantity || 0}</td>
                <td className="px-4 py-3 text-right font-mono">{php(item.rate || item.unit_price || item.price)}</td>
                <td className="px-4 py-3 text-right font-mono font-semibold">{php(item.total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="border-t border-slate-200 bg-slate-50 px-4 py-3 flex justify-end">
          <div className="w-48 space-y-1 text-sm">
            <div className="flex justify-between"><span className="text-slate-500">Subtotal</span><span className="font-mono">{php(doc.subtotal)}</span></div>
            {doc.overall_discount > 0 && <div className="flex justify-between"><span className="text-slate-500">Discount</span><span className="font-mono text-red-500">-{php(doc.overall_discount)}</span></div>}
            <div className="flex justify-between font-bold text-base border-t pt-1 mt-1"><span>Total</span><span className="font-mono text-[#1A4D2E]">{php(doc.grand_total)}</span></div>
            {doc.amount_paid > 0 && <div className="flex justify-between text-slate-500"><span>Paid</span><span className="font-mono">{php(doc.amount_paid)}</span></div>}
          </div>
        </div>
      </div>

      {/* Payment History */}
      {data.payments?.length > 0 && (
        <div className="bg-white rounded-xl border p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2"><CreditCard size={14} /> Payment History</h3>
          <div className="space-y-2">
            {data.payments.map((p, i) => (
              <div key={i} className="flex items-center justify-between text-sm py-2 border-b border-slate-50 last:border-0">
                <div><span className="font-medium">{php(p.amount)}</span> <span className="text-slate-400 ml-2">{p.method || 'Cash'}</span></div>
                <span className="text-slate-400 text-xs">{fmtDateTime(p.date || p.paid_at)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Purchase Order View ─────────────────────────────────────────────────────
function POView({ doc, data }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border p-4">
          <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Supplier</p>
          <p className="font-semibold text-slate-800 text-lg">{doc.vendor || ''}</p>
          {doc.dr_number && <p className="text-sm text-slate-500 mt-1">DR #: {doc.dr_number}</p>}
        </div>
        <div className="bg-white rounded-xl border p-4">
          <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Payment</p>
          <Badge className={`text-sm px-3 py-1 ${doc.payment_status === 'paid' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
            {doc.payment_status || 'Unpaid'}
          </Badge>
          <p className="text-sm text-slate-500 mt-2">{doc.po_type === 'cash' ? 'Cash' : doc.terms_label || 'Terms'}</p>
          {doc.due_date && <p className="text-sm text-slate-500">Due: {fmtDate(doc.due_date)}</p>}
        </div>
      </div>

      {/* Items */}
      <div className="bg-white rounded-xl border overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="bg-slate-50 text-xs text-slate-500 uppercase">
            <th className="px-4 py-3 text-left">Item</th>
            <th className="px-4 py-3 text-center">Qty</th>
            <th className="px-4 py-3 text-right">Unit Cost</th>
            <th className="px-4 py-3 text-right">Total</th>
          </tr></thead>
          <tbody>
            {(doc.items || []).map((item, i) => (
              <tr key={i} className="border-t border-slate-100">
                <td className="px-4 py-3 font-medium">{item.product_name || item.description || ''}</td>
                <td className="px-4 py-3 text-center font-mono">{item.quantity || 0}</td>
                <td className="px-4 py-3 text-right font-mono">{php(item.rate || item.unit_price || item.price)}</td>
                <td className="px-4 py-3 text-right font-mono font-semibold">{php(item.total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="border-t border-slate-200 bg-slate-50 px-4 py-3 flex justify-end">
          <div className="w-48 space-y-1 text-sm">
            <div className="flex justify-between font-bold text-base"><span>Grand Total</span><span className="font-mono text-[#1A4D2E]">{php(doc.grand_total)}</span></div>
            {doc.balance > 0 && <div className="flex justify-between text-red-600"><span>Balance</span><span className="font-mono">{php(doc.balance)}</span></div>}
          </div>
        </div>
      </div>

      {/* Attached Files */}
      {data.attached_files?.length > 0 && (
        <div className="bg-white rounded-xl border p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2"><Image size={14} /> Attached Receipts</h3>
          <div className="grid grid-cols-3 gap-3">
            {data.attached_files.map((f, i) => (
              <a key={i} href={f.url || f.file_url} target="_blank" rel="noreferrer" className="block rounded-lg border border-slate-200 overflow-hidden hover:shadow-md transition-shadow">
                {(f.url || f.file_url || '').match(/\.(jpg|jpeg|png|webp)/i)
                  ? <img src={f.url || f.file_url} alt="" className="w-full h-24 object-cover" />
                  : <div className="h-24 flex items-center justify-center bg-slate-50"><FileText size={24} className="text-slate-300" /></div>
                }
                <p className="text-xs text-slate-500 px-2 py-1 truncate">{f.original_name || 'File'}</p>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Branch Transfer View ────────────────────────────────────────────────────
function TransferView({ doc, data }) {
  const statusColors = {
    draft: 'bg-slate-100 text-slate-600', sent: 'bg-blue-100 text-blue-700',
    sent_to_terminal: 'bg-amber-100 text-amber-700', received_pending: 'bg-yellow-100 text-yellow-700',
    received: 'bg-emerald-100 text-emerald-700', disputed: 'bg-red-100 text-red-700',
  };
  const hasVariance = doc.status === 'received' || doc.status === 'received_pending';
  const items = hasVariance ? (doc.pending_items || doc.items || []) : (doc.items || []);

  return (
    <div className="space-y-4">
      {/* Branch info + Status */}
      <div className="bg-white rounded-xl border p-4">
        <div className="flex items-center gap-3 mb-3">
          <Badge className={`text-sm px-3 py-1 ${statusColors[doc.status] || 'bg-slate-100'}`}>{doc.status?.replace('_', ' ')?.toUpperCase()}</Badge>
          {doc.has_shortage && <Badge className="text-sm bg-red-100 text-red-700">Shortage</Badge>}
        </div>
        <div className="flex items-center gap-3">
          <div className="flex-1 bg-slate-50 rounded-lg p-3">
            <p className="text-xs text-slate-400 uppercase">From</p>
            <p className="font-bold text-[#1A4D2E] text-lg">{data.from_branch_name}</p>
          </div>
          <ArrowRight size={20} className="text-slate-300 shrink-0" />
          <div className="flex-1 bg-slate-50 rounded-lg p-3">
            <p className="text-xs text-slate-400 uppercase">To</p>
            <p className="font-bold text-[#1A4D2E] text-lg">{data.to_branch_name}</p>
          </div>
        </div>
      </div>

      {/* Timeline */}
      <div className="bg-white rounded-xl border p-4">
        <div className="flex items-center justify-between">
          {[
            { label: 'Created', done: true, date: doc.created_at },
            { label: 'Sent', done: ['sent','sent_to_terminal','received_pending','received','disputed'].includes(doc.status), date: doc.sent_at },
            { label: 'Received', done: ['received_pending','received','disputed'].includes(doc.status), date: doc.received_at || doc.pending_receipt_at },
            { label: 'Complete', done: doc.status === 'received' },
          ].map((step, i, arr) => (
            <React.Fragment key={i}>
              <div className="flex flex-col items-center">
                <div className={`w-4 h-4 rounded-full ${step.done ? 'bg-emerald-500' : 'bg-slate-200'}`} />
                <p className={`text-xs mt-1 ${step.done ? 'text-slate-700 font-semibold' : 'text-slate-400'}`}>{step.label}</p>
                {step.done && step.date && <p className="text-[10px] text-slate-400">{fmtDate(step.date)}</p>}
              </div>
              {i < arr.length - 1 && <div className={`flex-1 h-0.5 mx-2 rounded ${step.done ? 'bg-emerald-400' : 'bg-slate-200'}`} />}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Items */}
      <div className="bg-white rounded-xl border overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="bg-slate-50 text-xs text-slate-500 uppercase">
            <th className="px-4 py-3 text-left">Product</th>
            <th className="px-4 py-3 text-center">{hasVariance ? 'Sent' : 'Qty'}</th>
            {hasVariance && <th className="px-4 py-3 text-center">Rcvd</th>}
            {hasVariance && <th className="px-4 py-3 text-center">Variance</th>}
            <th className="px-4 py-3 text-right">Transfer Price</th>
            <th className="px-4 py-3 text-right">Total</th>
          </tr></thead>
          <tbody>
            {items.map((item, i) => {
              const sent = item.qty_ordered ?? item.qty;
              const rcvd = item.qty_received ?? item.qty;
              const variance = sent - rcvd;
              const tc = parseFloat(item.transfer_capital) || 0;
              return (
                <tr key={i} className={`border-t border-slate-100 ${hasVariance && variance > 0 ? 'bg-red-50/50' : ''}`}>
                  <td className="px-4 py-3"><p className="font-medium">{item.product_name}</p><p className="text-xs text-slate-400 font-mono">{item.sku}</p></td>
                  <td className="px-4 py-3 text-center font-mono">{sent}</td>
                  {hasVariance && <td className="px-4 py-3 text-center font-mono font-bold">{rcvd}</td>}
                  {hasVariance && <td className={`px-4 py-3 text-center font-mono font-bold ${variance > 0 ? 'text-red-600' : variance < 0 ? 'text-blue-600' : 'text-emerald-600'}`}>{variance === 0 ? 'OK' : variance > 0 ? `-${variance}` : `+${Math.abs(variance)}`}</td>}
                  <td className="px-4 py-3 text-right font-mono">{php(tc)}</td>
                  <td className="px-4 py-3 text-right font-mono font-semibold">{php(tc * sent)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Attached files */}
      {data.attached_files?.length > 0 && (
        <div className="bg-white rounded-xl border p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2"><Image size={14} /> Attached Documents</h3>
          <div className="grid grid-cols-3 gap-3">
            {data.attached_files.map((f, i) => (
              <a key={i} href={f.url || f.file_url} target="_blank" rel="noreferrer" className="block rounded-lg border border-slate-200 overflow-hidden hover:shadow-md transition-shadow">
                {(f.url || f.file_url || '').match(/\.(jpg|jpeg|png|webp)/i)
                  ? <img src={f.url || f.file_url} alt="" className="w-full h-24 object-cover" />
                  : <div className="h-24 flex items-center justify-center bg-slate-50"><FileText size={24} className="text-slate-300" /></div>
                }
                <p className="text-xs text-slate-500 px-2 py-1 truncate">{f.original_name || 'File'}</p>
              </a>
            ))}
          </div>
        </div>
      )}

      {doc.receive_notes && (
        <div className="bg-white rounded-xl border p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-2">Receiver Notes</h3>
          <p className="text-sm text-slate-600">{doc.receive_notes}</p>
        </div>
      )}
    </div>
  );
}
