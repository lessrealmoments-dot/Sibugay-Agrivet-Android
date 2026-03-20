/**
 * ReviewDetailDialog — Shared review dialog for POs, Branch Transfers, and Expenses.
 * Shows full record detail, item breakdown, receipt photos, View on Phone QR,
 * and PIN-gated "Mark as Reviewed" action.
 * Used by: PendingReviewsWidget, AccountsPayableWidget, and any future widget.
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
  ExternalLink, QrCode
} from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

/**
 * @param {Object} props
 * @param {boolean} props.open
 * @param {Function} props.onClose
 * @param {string} props.recordType - 'purchase_order' | 'branch_transfer' | 'expense'
 * @param {string} props.recordId
 * @param {string} [props.recordNumber] - Optional display label for the title
 * @param {boolean} [props.showReviewAction=true] - Show PIN + Mark as Reviewed section
 * @param {Function} [props.onReviewed] - Called after successful review
 */
export default function ReviewDetailDialog({ open, onClose, recordType, recordId, recordNumber, showReviewAction = true, onReviewed }) {
  const navigate = useNavigate();
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [reviewPin, setReviewPin] = useState('');
  const [reviewNotes, setReviewNotes] = useState('');
  const [reviewSaving, setReviewSaving] = useState(false);
  const [viewQROpen, setViewQROpen] = useState(false);

  useEffect(() => {
    if (open && recordType && recordId) {
      setLoading(true);
      setDetail(null);
      setReviewPin('');
      setReviewNotes('');
      api.get(`/dashboard/review-detail/${recordType}/${recordId}`)
        .then(res => setDetail(res.data))
        .catch(() => toast.error('Failed to load record details'))
        .finally(() => setLoading(false));
    }
  }, [open, recordType, recordId]);

  const handleReview = async () => {
    if (!reviewPin) { toast.error('Enter admin PIN, auditor PIN, or TOTP'); return; }
    setReviewSaving(true);
    try {
      let endpoint;
      if (recordType === 'purchase_order') {
        endpoint = `/purchase-orders/${recordId}/mark-reviewed`;
      } else {
        endpoint = `/uploads/mark-reviewed/${recordType}/${recordId}`;
      }
      const res = await api.post(endpoint, { pin: reviewPin, notes: reviewNotes });
      toast.success(res.data.message || 'Marked as reviewed');
      setDetail(prev => prev ? { ...prev, receipt_review_status: 'reviewed' } : prev);
      setReviewPin('');
      if (onReviewed) onReviewed();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Review failed');
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
                            {d.payment_status === 'paid' ? 'Paid' : d.payment_status === 'partial' ? `Partial (${formatPHP(d.total_paid)})` : d.balance > 0 ? `Unpaid — ${formatPHP(d.balance)} due` : 'Unpaid'}
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
                          <CheckCircle2 size={11} /> Receipts reviewed{d.receipt_reviewed_by ? ` by ${d.receipt_reviewed_by}` : ''}
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
                        <div className="flex items-center gap-1.5 text-[10px] text-emerald-600 bg-emerald-50 rounded-lg px-2 py-1">
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

                  {/* ── Review Section (only if not yet reviewed AND has receipts) ── */}
                  {showReviewAction && !isReviewed && files.length > 0 && (
                    <div className="space-y-3 bg-amber-50 border border-amber-200 rounded-xl p-4">
                      <p className="text-xs font-semibold text-amber-700 flex items-center gap-1.5">
                        <AlertTriangle size={12} /> Receipts pending review
                      </p>
                      <Input value={reviewNotes} onChange={e => setReviewNotes(e.target.value)}
                        placeholder="Review notes (optional)" className="h-9 text-sm bg-white" data-testid="review-notes-input" />
                      <div>
                        <label className="text-[10px] text-slate-500 font-medium flex items-center gap-1 mb-1">
                          <Shield size={10} className="text-amber-500" /> Admin PIN, Auditor PIN, or TOTP
                        </label>
                        <Input type="password" autoComplete="new-password" value={reviewPin}
                          onChange={e => setReviewPin(e.target.value)}
                          onKeyDown={e => { if (e.key === 'Enter') handleReview(); }}
                          placeholder="Enter PIN" className="h-9 text-sm font-mono bg-white" data-testid="review-pin-input" />
                      </div>
                      <Button size="sm" onClick={handleReview} disabled={reviewSaving || !reviewPin}
                        className="bg-[#1A4D2E] hover:bg-[#14532d] text-white w-full" data-testid="confirm-review-btn">
                        {reviewSaving ? <RefreshCw size={12} className="animate-spin mr-1" /> : <CheckCircle2 size={12} className="mr-1" />}
                        Mark as Reviewed
                      </Button>
                    </div>
                  )}
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
