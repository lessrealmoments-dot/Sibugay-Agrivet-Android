/**
 * ReviewDetailDialog — Shared review dialog for POs, Branch Transfers, and Expenses.
 * Phase 1: Balance fix + wallet balances
 * Phase 2: "Verify & Approve" button with PIN policy (no files.length gate for POs)
 *
 * Props:
 *   open, onClose, recordType, recordId, recordNumber
 *   showReviewAction   — show Verify & Approve section (both AP and Pending Reviews)
 *   showPayAction      — show Pay Now panel (AP widget only, Phase 3)
 *   onReviewed         — callback after successful review
 */
import { useState, useEffect } from 'react';
import { api } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { formatPHP } from '../lib/utils';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Input } from './ui/input';
import { ScrollArea } from './ui/scroll-area';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import ViewQRDialog from './ViewQRDialog';
import {
  FileCheck, Receipt, CheckCircle2, RefreshCw, Camera, Building2, Clock,
  AlertTriangle, Shield, Package, User, CalendarDays, ShieldCheck,
  ExternalLink, QrCode, ChevronDown, ChevronUp, XCircle
} from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

// Allowed PIN methods for the two review policy keys
const PO_VERIFY_METHODS = 'Admin PIN, Manager PIN, TOTP, or Auditor PIN';
const OTHER_VERIFY_METHODS = 'Admin PIN, Manager PIN, TOTP, or Auditor PIN';

export default function ReviewDetailDialog({
  open, onClose, recordType, recordId, recordNumber,
  showReviewAction = true,
  showPayAction = false,   // Phase 3 — Pay Now (only from AP widget)
  onReviewed,
}) {
  const navigate = useNavigate();
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);

  // Verify section state
  const [verifyExpanded, setVerifyExpanded] = useState(false);
  const [reviewPin, setReviewPin] = useState('');
  const [reviewNotes, setReviewNotes] = useState('');
  const [reviewSaving, setReviewSaving] = useState(false);

  // QR viewer
  const [viewQROpen, setViewQROpen] = useState(false);

  useEffect(() => {
    if (open && recordType && recordId) {
      setLoading(true);
      setDetail(null);
      setReviewPin('');
      setReviewNotes('');
      setVerifyExpanded(false);
      api.get(`/dashboard/review-detail/${recordType}/${recordId}`)
        .then(res => setDetail(res.data))
        .catch(() => toast.error('Failed to load record details'))
        .finally(() => setLoading(false));
    }
  }, [open, recordType, recordId]);

  const handleReview = async () => {
    if (!reviewPin) { toast.error('Enter PIN or TOTP code'); return; }
    setReviewSaving(true);
    try {
      let endpoint;
      if (recordType === 'purchase_order') {
        endpoint = `/purchase-orders/${recordId}/mark-reviewed`;
      } else {
        endpoint = `/uploads/mark-reviewed/${recordType}/${recordId}`;
      }
      const res = await api.post(endpoint, { pin: reviewPin, notes: reviewNotes });
      toast.success(res.data.message || 'Verified & approved');
      setDetail(prev => prev ? { ...prev, receipt_review_status: 'reviewed' } : prev);
      setReviewPin('');
      setVerifyExpanded(false);
      if (onReviewed) onReviewed();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Verification failed');
    }
    setReviewSaving(false);
  };

  const goToFullPage = () => {
    onClose();
    if (recordType === 'purchase_order') navigate(`/purchase-orders?open=${recordId}`);
    else if (recordType === 'branch_transfer') navigate(`/branch-transfers?tab=history&view=${recordId}`);
    else navigate('/accounting');
  };

  const d = detail;
  const files = d?.receipt_files || [];
  const isReviewed = d?.receipt_review_status === 'reviewed';
  const title = d?.record_number || recordNumber || 'Loading...';

  // For POs: verify button shows regardless of files
  // For other types: only when files exist (original behavior)
  const showVerifySection = showReviewAction && !isReviewed && (
    recordType === 'purchase_order' ? true : files.length > 0
  );

  return (
    <>
      <Dialog open={open} onOpenChange={v => { if (!v) onClose(); }}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh] flex flex-col" data-testid="review-detail-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
              <FileCheck size={18} className="text-[#1A4D2E]" />
              {title}
            </DialogTitle>
          </DialogHeader>

          <ScrollArea className="flex-1 -mx-6 px-6">
            <div className="space-y-4 pb-2">
              {loading ? (
                <div className="flex items-center justify-center py-8 text-slate-400 text-sm">
                  <RefreshCw size={14} className="animate-spin mr-2" /> Loading details...
                </div>
              ) : d ? (
                <>
                  {/* ── Purchase Order Header ── */}
                  {d.record_type === 'purchase_order' && (
                    <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 space-y-2">
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="text-sm font-bold text-slate-800">{d.record_number}</p>
                          <div className="flex items-center gap-1.5 mt-1">
                            <User size={11} className="text-blue-600" />
                            <span className="text-xs font-semibold text-blue-800">{d.supplier}</span>
                            {d.supplier_contact && <span className="text-[10px] text-slate-400">({d.supplier_contact})</span>}
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-lg font-bold font-mono text-slate-800">{formatPHP(d.grand_total)}</p>
                          <Badge className={`text-[9px] ${
                            d.payment_status === 'paid' ? 'bg-emerald-100 text-emerald-700' :
                            d.payment_status === 'partial' ? 'bg-amber-100 text-amber-700' :
                            'bg-red-100 text-red-700'
                          }`}>
                            {d.payment_status === 'paid' ? 'Paid' :
                             d.payment_status === 'partial' ? `Partial — ${formatPHP(d.balance)} remaining` :
                             d.balance > 0 ? `Unpaid — ${formatPHP(d.balance)} due` : 'Unpaid'}
                          </Badge>
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-slate-500 pt-1 border-t border-blue-100">
                        <span className="flex items-center gap-1"><Building2 size={10} /> {d.branch_name}</span>
                        <span className="flex items-center gap-1"><CalendarDays size={10} /> Date: {d.date?.slice(0, 10)}</span>
                        {d.due_date && <span className="flex items-center gap-1"><Clock size={10} /> Due: {d.due_date.slice(0, 10)}</span>}
                        <span>Status: <Badge className="text-[9px] bg-slate-200 text-slate-600">{d.status}</Badge></span>
                        {d.received_by && <span>Received by: {d.received_by}</span>}
                        {d.created_by && <span>Created by: {d.created_by}</span>}
                      </div>
                      {d.verified && (
                        <div className="flex items-center gap-1.5 text-[10px] text-emerald-600 bg-emerald-50 rounded-lg px-2 py-1">
                          <ShieldCheck size={11} /> Verified by {d.verified_by} {d.verified_at ? `on ${d.verified_at.slice(0, 10)}` : ''}
                        </div>
                      )}
                      {isReviewed && (
                        <div className="flex items-center gap-1.5 text-[10px] text-emerald-600 bg-emerald-50 rounded-lg px-2 py-1">
                          <CheckCircle2 size={11} /> Approved &amp; reviewed{d.receipt_reviewed_by ? ` by ${d.receipt_reviewed_by}` : ''}
                        </div>
                      )}
                    </div>
                  )}

                  {/* ── Branch Transfer Header ── */}
                  {d.record_type === 'branch_transfer' && (
                    <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 space-y-2">
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="text-sm font-bold text-slate-800">{d.record_number}</p>
                          {d.invoice_number && <p className="text-[10px] text-blue-600 font-mono">{d.invoice_number}</p>}
                          <div className="flex items-center gap-1.5 mt-1 text-xs text-emerald-800">
                            <Building2 size={11} /> {d.from_branch} <span className="text-slate-400">→</span> {d.to_branch}
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-lg font-bold font-mono text-slate-800">{formatPHP(d.grand_total)}</p>
                          {d.retail_total > 0 && <p className="text-[10px] text-slate-400">Retail: {formatPHP(d.retail_total)}</p>}
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-slate-500 pt-1 border-t border-emerald-100">
                        <span>Status: <Badge className="text-[9px] bg-slate-200 text-slate-600">{d.status}</Badge></span>
                        {d.sent_at && <span>Sent: {d.sent_at.slice(0, 10)}</span>}
                        {d.received_at && <span>Received: {d.received_at.slice(0, 10)}</span>}
                        {d.received_by && <span>By: {d.received_by}</span>}
                        {d.has_shortage && <Badge className="text-[9px] bg-red-100 text-red-700">Shortage</Badge>}
                      </div>
                      {isReviewed && (
                        <div className="flex items-center gap-1.5 text-[10px] text-emerald-600 bg-white rounded-lg px-2 py-1">
                          <CheckCircle2 size={11} /> Receipts reviewed
                        </div>
                      )}
                    </div>
                  )}

                  {/* ── Expense Header ── */}
                  {d.record_type === 'expense' && (
                    <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-2">
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="text-sm font-bold text-slate-800">{d.category}</p>
                          <p className="text-xs text-slate-600">{d.description}</p>
                          {d.vendor && <p className="text-[10px] text-slate-500 mt-0.5">Payee: {d.vendor}</p>}
                        </div>
                        <p className="text-lg font-bold font-mono text-slate-800">{formatPHP(d.grand_total)}</p>
                      </div>
                      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-slate-500 pt-1 border-t border-amber-100">
                        <span className="flex items-center gap-1"><Building2 size={10} /> {d.branch_name}</span>
                        <span className="flex items-center gap-1"><CalendarDays size={10} /> {d.date?.slice(0, 10)}</span>
                        {d.payment_method && <span>Method: {d.payment_method}</span>}
                        {d.created_by && <span>By: {d.created_by}</span>}
                      </div>
                      {isReviewed && (
                        <div className="flex items-center gap-1.5 text-[10px] text-emerald-600 bg-emerald-50 rounded-lg px-2 py-1">
                          <CheckCircle2 size={11} /> Receipts reviewed
                        </div>
                      )}
                    </div>
                  )}

                  {/* ── Item Breakdown ── */}
                  {d.items?.length > 0 && (
                    <div className="bg-white border rounded-xl overflow-hidden">
                      <div className="px-3 py-2 bg-slate-50 border-b flex items-center gap-2">
                        <Package size={13} className="text-slate-500" />
                        <span className="text-xs font-semibold text-slate-700">Items ({d.items.length})</span>
                      </div>
                      <Table>
                        <TableHeader>
                          <TableRow className="bg-slate-50/50">
                            <TableHead className="text-[10px] uppercase text-slate-500">Product</TableHead>
                            <TableHead className="text-[10px] uppercase text-slate-500 text-right">Qty</TableHead>
                            <TableHead className="text-[10px] uppercase text-slate-500 text-right">Price</TableHead>
                            <TableHead className="text-[10px] uppercase text-slate-500 text-right">Total</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {d.items.map((item, idx) => (
                            <TableRow key={idx} className="hover:bg-slate-50/50">
                              <TableCell className="text-xs">
                                <span className="font-medium">{item.product_name}</span>
                                {item.sku && <span className="text-[10px] text-slate-400 ml-1">({item.sku})</span>}
                              </TableCell>
                              <TableCell className="text-xs text-right font-mono">
                                {item.quantity}{item.unit ? ` ${item.unit}` : ''}
                                {item.qty_received !== undefined && item.qty_received !== item.quantity && (
                                  <span className={`text-[10px] ml-1 ${item.qty_received < item.quantity ? 'text-red-500' : 'text-blue-500'}`}>
                                    (rcvd: {item.qty_received})
                                  </span>
                                )}
                              </TableCell>
                              <TableCell className="text-xs text-right font-mono">{formatPHP(item.unit_price || item.transfer_capital || 0)}</TableCell>
                              <TableCell className="text-xs text-right font-mono font-semibold">{formatPHP(item.total || (item.quantity * (item.unit_price || item.transfer_capital || 0)))}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  )}

                  {/* ── Payment History (PO only) ── */}
                  {d.record_type === 'purchase_order' && (d.payment_history || []).length > 0 && (
                    <div className="bg-white border rounded-xl overflow-hidden">
                      <div className="px-3 py-2 bg-slate-50 border-b flex items-center gap-2">
                        <Receipt size={13} className="text-slate-500" />
                        <span className="text-xs font-semibold text-slate-700">Payment History ({d.payment_history.length})</span>
                      </div>
                      <div className="divide-y divide-slate-50">
                        {d.payment_history.map((p, idx) => (
                          <div key={idx} className="flex justify-between items-center px-3 py-2 text-xs">
                            <div>
                              <span className="font-semibold text-slate-700">{p.method || 'Cash'}</span>
                              <span className="text-slate-400 ml-2">from {p.fund_source || 'cashier'}</span>
                              {p.reference && <span className="text-slate-400 ml-1">· ref: {p.reference}</span>}
                              <p className="text-[10px] text-slate-400">{p.date} · {p.recorded_by}</p>
                            </div>
                            <span className="font-bold font-mono text-emerald-700">{formatPHP(p.amount)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* ── Receipt Photos ── */}
                  {files.length > 0 && (
                    <div className="bg-white border rounded-xl overflow-hidden">
                      <div className="px-3 py-2 bg-slate-50 border-b flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Camera size={13} className="text-slate-500" />
                          <span className="text-xs font-semibold text-slate-700">Receipt Photos ({files.length})</span>
                        </div>
                        <Button variant="outline" size="sm" className="h-6 text-[10px] px-2"
                          onClick={() => setViewQROpen(true)} data-testid="review-view-phone-btn">
                          <QrCode size={10} className="mr-1" /> View on Phone
                        </Button>
                      </div>
                      <div className="p-3 flex flex-wrap gap-2">
                        {files.map((f, i) => {
                          const isImage = (f.content_type || '').startsWith('image/');
                          const url = `${BACKEND_URL}/api/uploads/file/${recordType}/${recordId}/${f.id}`;
                          return (
                            <a key={f.id || i} href={url} target="_blank" rel="noopener noreferrer"
                              className="block rounded-lg border border-slate-200 overflow-hidden hover:shadow-md transition-shadow">
                              {isImage ? (
                                <img src={url} alt={f.filename} className="w-24 h-24 object-cover" />
                              ) : (
                                <div className="w-24 h-24 bg-slate-50 flex flex-col items-center justify-center">
                                  <Receipt size={18} className="text-slate-400" />
                                  <span className="text-[8px] text-slate-400 mt-1 truncate max-w-[80px]">{f.filename}</span>
                                </div>
                              )}
                            </a>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* ── Verify & Approve Section ── */}
                  {showVerifySection && (
                    <div className="rounded-xl border border-amber-200 overflow-hidden">
                      {/* Collapsed: Show button */}
                      {!verifyExpanded ? (
                        <button
                          onClick={() => setVerifyExpanded(true)}
                          className="w-full flex items-center justify-between px-4 py-3 bg-amber-50 hover:bg-amber-100 transition-colors text-left"
                          data-testid="verify-po-btn"
                        >
                          <div className="flex items-center gap-2">
                            <ShieldCheck size={15} className="text-amber-600" />
                            <div>
                              <p className="text-sm font-semibold text-amber-800">Verify &amp; Approve this PO</p>
                              <p className="text-[10px] text-amber-600">
                                {files.length > 0
                                  ? `${files.length} receipt photo${files.length > 1 ? 's' : ''} pending review`
                                  : 'Confirm goods received — no photos uploaded yet'}
                              </p>
                            </div>
                          </div>
                          <ChevronDown size={15} className="text-amber-500" />
                        </button>
                      ) : (
                        /* Expanded: Verify form */
                        <div className="bg-amber-50 p-4 space-y-3">
                          <div className="flex items-center justify-between">
                            <p className="text-xs font-semibold text-amber-800 flex items-center gap-1.5">
                              <ShieldCheck size={13} className="text-amber-600" />
                              Verify &amp; Approve
                            </p>
                            <button onClick={() => { setVerifyExpanded(false); setReviewPin(''); setReviewNotes(''); }}
                              className="text-slate-400 hover:text-slate-600">
                              <XCircle size={15} />
                            </button>
                          </div>

                          {files.length === 0 && (
                            <div className="flex items-start gap-2 bg-amber-100 border border-amber-300 rounded-lg px-3 py-2 text-[10px] text-amber-700">
                              <AlertTriangle size={11} className="mt-0.5 shrink-0" />
                              No receipt photos uploaded. You can still approve — or upload receipts first.
                            </div>
                          )}

                          <Input
                            value={reviewNotes}
                            onChange={e => setReviewNotes(e.target.value)}
                            placeholder="Verification notes (optional)"
                            className="h-9 text-sm bg-white"
                            data-testid="review-notes-input"
                          />

                          <div>
                            <label className="text-[10px] text-slate-600 font-medium flex items-center gap-1 mb-1">
                              <Shield size={10} className="text-amber-500" />
                              {recordType === 'purchase_order' ? PO_VERIFY_METHODS : OTHER_VERIFY_METHODS}
                            </label>
                            <Input
                              type="password"
                              autoComplete="new-password"
                              value={reviewPin}
                              onChange={e => setReviewPin(e.target.value)}
                              onKeyDown={e => { if (e.key === 'Enter') handleReview(); }}
                              placeholder="Enter PIN or TOTP"
                              className="h-9 text-sm font-mono bg-white"
                              data-testid="review-pin-input"
                            />
                          </div>

                          <div className="flex gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              className="flex-1"
                              onClick={() => { setVerifyExpanded(false); setReviewPin(''); setReviewNotes(''); }}
                            >
                              Cancel
                            </Button>
                            <Button
                              size="sm"
                              onClick={handleReview}
                              disabled={reviewSaving || !reviewPin}
                              className="flex-1 bg-[#1A4D2E] hover:bg-[#14532d] text-white"
                              data-testid="confirm-review-btn"
                            >
                              {reviewSaving
                                ? <RefreshCw size={12} className="animate-spin mr-1" />
                                : <CheckCircle2 size={12} className="mr-1" />}
                              Confirm Verification
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Already reviewed indicator */}
                  {showReviewAction && isReviewed && (
                    <div className="flex items-center gap-2 text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3" data-testid="already-reviewed">
                      <CheckCircle2 size={14} className="shrink-0" />
                      <div>
                        <p className="font-semibold">Verified &amp; Approved</p>
                        {d?.receipt_reviewed_by && <p className="text-[10px] text-emerald-600">by {d.receipt_reviewed_by}</p>}
                      </div>
                    </div>
                  )}

                  {/* Phase 3 placeholder — Pay Now panel will be inserted here */}
                </>
              ) : null}
            </div>
          </ScrollArea>

          {/* ── Footer ── */}
          <div className="flex justify-between items-center pt-3 border-t -mx-6 px-6">
            <Button variant="ghost" size="sm" onClick={goToFullPage} className="text-xs text-slate-500 hover:text-[#1A4D2E]">
              <ExternalLink size={12} className="mr-1" /> Open Full Page
            </Button>
            <Button variant="outline" size="sm" onClick={onClose}>Close</Button>
          </div>
        </DialogContent>
      </Dialog>

      <ViewQRDialog
        open={viewQROpen}
        onClose={() => setViewQROpen(false)}
        recordType={recordType}
        recordId={recordId}
        fileCount={files.length}
      />
    </>
  );
}
