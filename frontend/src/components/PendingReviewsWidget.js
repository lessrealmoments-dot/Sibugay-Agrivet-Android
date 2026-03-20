/**
 * PendingReviewsWidget — Dashboard widget showing receipts pending admin review.
 * Owner/Admin: all branches grouped. Branch user: own branch only (read-only).
 */
import { useState, useEffect, useCallback } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { formatPHP } from '../lib/utils';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { ScrollArea } from '../components/ui/scroll-area';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import {
  FileCheck, ShoppingCart, Truck, Receipt, Eye, CheckCircle2,
  RefreshCw, ChevronDown, ChevronRight, Camera, Building2, Clock,
  AlertTriangle, Shield, X, Package, CreditCard, User, CalendarDays,
  ShieldCheck, ExternalLink, QrCode
} from 'lucide-react';
import ViewQRDialog from '../components/ViewQRDialog';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const TYPE_CONFIG = {
  purchase_order: { label: 'Purchase Order', icon: ShoppingCart, color: 'text-blue-600', bg: 'bg-blue-50', border: 'border-blue-200', badge: 'bg-blue-100 text-blue-700', nav: '/purchase-orders' },
  branch_transfer: { label: 'Branch Transfer', icon: Truck, color: 'text-emerald-600', bg: 'bg-emerald-50', border: 'border-emerald-200', badge: 'bg-emerald-100 text-emerald-700', nav: '/branch-transfers' },
  expense: { label: 'Expense', icon: Receipt, color: 'text-amber-600', bg: 'bg-amber-50', border: 'border-amber-200', badge: 'bg-amber-100 text-amber-700', nav: '/accounting' },
};

function ReviewItem({ item, isAdmin, onReview, onView }) {
  const cfg = TYPE_CONFIG[item.record_type] || TYPE_CONFIG.expense;
  const Icon = cfg.icon;
  const timeAgo = item.submitted_at ? getTimeAgo(item.submitted_at) : '';

  return (
    <div className={`flex items-center gap-3 p-2.5 rounded-lg ${cfg.bg} ${cfg.border} border transition-colors hover:shadow-sm`} data-testid={`pending-review-${item.id}`}>
      <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${cfg.bg}`}>
        <Icon size={15} className={cfg.color} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-semibold text-slate-800 truncate">{item.record_number}</span>
          <Badge className={`text-[9px] ${cfg.badge}`}>{cfg.label}</Badge>
        </div>
        <p className="text-[10px] text-slate-500 truncate">{item.description}</p>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-[10px] text-slate-400 flex items-center gap-0.5">
            <Camera size={9} /> {item.receipt_count} photo{item.receipt_count > 1 ? 's' : ''}
          </span>
          <span className="text-[10px] text-slate-400 flex items-center gap-0.5">
            <Clock size={9} /> {timeAgo}
          </span>
          {item.submitted_by && (
            <span className="text-[10px] text-slate-400">by {item.submitted_by}</span>
          )}
        </div>
      </div>
      <div className="flex items-center gap-1.5 shrink-0">
        <span className="text-xs font-semibold font-mono text-slate-700">{formatPHP(item.amount)}</span>
        {isAdmin ? (
          <Button size="sm" variant="outline" onClick={() => onReview(item)}
            className="h-7 px-2 text-[10px] border-[#1A4D2E]/30 text-[#1A4D2E] hover:bg-[#1A4D2E] hover:text-white"
            data-testid={`review-btn-${item.id}`}>
            <FileCheck size={11} className="mr-1" /> Review
          </Button>
        ) : (
          <Badge className="text-[9px] bg-amber-100 text-amber-700">
            <Clock size={9} className="mr-0.5" /> Pending
          </Badge>
        )}
      </div>
    </div>
  );
}

function getTimeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export default function PendingReviewsWidget({ branchId, compact = false }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expandedBranch, setExpandedBranch] = useState(null);
  const [reviewDialog, setReviewDialog] = useState(null); // item to review
  const [reviewPin, setReviewPin] = useState('');
  const [reviewNotes, setReviewNotes] = useState('');
  const [reviewSaving, setReviewSaving] = useState(false);
  const [receiptPreview, setReceiptPreview] = useState(null); // { files, record_type, record_id }

  const [reviewDetail, setReviewDetail] = useState(null); // full record detail
  const [reviewDetailLoading, setReviewDetailLoading] = useState(false);
  const [viewQROpen, setViewQROpen] = useState(false);

  const isAdmin = user?.role === 'admin' || user?.role === 'owner' || user?.role === 'manager';

  const loadPendingReviews = useCallback(async () => {
    try {
      const params = branchId ? { branch_id: branchId } : {};
      const res = await api.get('/dashboard/pending-reviews', { params });
      setData(res.data);
      // Auto-expand first branch
      if (res.data.by_branch) {
        const keys = Object.keys(res.data.by_branch);
        if (keys.length === 1) setExpandedBranch(keys[0]);
      }
    } catch (e) {
      console.error('Failed to load pending reviews', e);
    }
    setLoading(false);
  }, [branchId]);

  useEffect(() => { loadPendingReviews(); }, [loadPendingReviews]);

  const handleReview = async () => {
    if (!reviewPin) { toast.error('Enter admin PIN or TOTP code'); return; }
    if (!reviewDialog) return;
    setReviewSaving(true);
    try {
      const item = reviewDialog;
      let endpoint;
      if (item.record_type === 'purchase_order') {
        endpoint = `/purchase-orders/${item.id}/mark-reviewed`;
      } else {
        endpoint = `/uploads/mark-reviewed/${item.record_type}/${item.id}`;
      }
      const res = await api.post(endpoint, { pin: reviewPin, notes: reviewNotes });
      toast.success(res.data.message);
      setReviewDialog(null);
      setReviewPin('');
      setReviewNotes('');
      loadPendingReviews();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Review failed');
    }
    setReviewSaving(false);
  };

  const loadReceiptPreview = async (item) => {
    try {
      const res = await api.get(`/uploads/record/${item.record_type}/${item.id}`);
      const files = (res.data.sessions || []).flatMap(s => s.files || []);
      setReceiptPreview({ files, item });
    } catch {
      toast.error('Could not load receipt photos');
    }
  };

  const openReviewWithPreview = async (item) => {
    setReviewDialog(item);
    setReviewPin('');
    setReviewNotes('');
    setReviewDetailLoading(true);
    setReviewDetail(null);
    try {
      // Fetch enriched detail + receipt files in one call
      const res = await api.get(`/dashboard/review-detail/${item.record_type}/${item.id}`);
      setReviewDetail(res.data);
      // Also set receipt preview from the detail response
      setReceiptPreview({ files: (res.data.receipt_files || []).map(f => ({ ...f })), item });
    } catch {
      // Fallback to old method
      await loadReceiptPreview(item);
    }
    setReviewDetailLoading(false);
  };

  const goToRecord = (item) => {
    if (item.record_type === 'purchase_order') {
      navigate(`/purchase-orders?open=${item.id}`);
    } else if (item.record_type === 'branch_transfer') {
      navigate(`/branch-transfers?tab=history&view=${item.id}`);
    } else {
      const cfg = TYPE_CONFIG[item.record_type];
      if (cfg?.nav) navigate(cfg.nav);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-6 text-slate-400 text-xs">
        <RefreshCw size={13} className="animate-spin mr-1.5" /> Loading reviews...
      </div>
    );
  }

  const totalCount = data?.total_count || 0;

  if (totalCount === 0) {
    return (
      <div className="flex items-center gap-2 text-xs text-emerald-600 py-3" data-testid="no-pending-reviews">
        <CheckCircle2 size={14} /> All receipts reviewed — nothing pending
      </div>
    );
  }

  const items = data?.items || [];
  const byBranch = data?.by_branch || {};
  const branchKeys = Object.keys(byBranch).sort();
  const showBranchGroups = isAdmin && !branchId && branchKeys.length > 1;

  return (
    <div data-testid="pending-reviews-widget">
      {showBranchGroups ? (
        // ── Admin: grouped by branch ─────────────────────────────────
        <div className="space-y-2">
          {branchKeys.map(bname => {
            const group = byBranch[bname];
            const isOpen = expandedBranch === bname;
            return (
              <div key={bname} className="rounded-lg border border-slate-200 overflow-hidden">
                <button
                  onClick={() => setExpandedBranch(isOpen ? null : bname)}
                  className="w-full flex items-center justify-between px-3 py-2 bg-slate-50 hover:bg-slate-100 transition-colors text-left"
                  data-testid={`branch-group-${group.branch_id}`}
                >
                  <div className="flex items-center gap-2">
                    <Building2 size={13} className="text-[#1A4D2E]" />
                    <span className="text-xs font-semibold text-slate-700">{bname}</span>
                    <Badge className="text-[9px] bg-amber-100 text-amber-700">{group.count} pending</Badge>
                  </div>
                  {isOpen ? <ChevronDown size={13} className="text-slate-400" /> : <ChevronRight size={13} className="text-slate-400" />}
                </button>
                {isOpen && (
                  <div className="p-2 space-y-1.5">
                    {group.items.map(item => (
                      <ReviewItem key={item.id} item={item} isAdmin={isAdmin} onReview={openReviewWithPreview} onView={goToRecord} />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        // ── Branch view or single-branch admin ──────────────────────
        <div className="space-y-1.5">
          {(compact ? items.slice(0, 5) : items).map(item => (
            <ReviewItem key={item.id} item={item} isAdmin={isAdmin} onReview={openReviewWithPreview} onView={goToRecord} />
          ))}
          {compact && items.length > 5 && (
            <button onClick={() => navigate('/purchase-orders')} className="text-[10px] text-[#1A4D2E] hover:underline mt-1">
              +{items.length - 5} more pending reviews →
            </button>
          )}
        </div>
      )}

      {/* ── Review Dialog ───────────────────────────────────────────── */}
      <Dialog open={!!reviewDialog} onOpenChange={v => { if (!v) { setReviewDialog(null); setReceiptPreview(null); setReviewDetail(null); } }}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
              <FileCheck size={18} className="text-[#1A4D2E]" />
              Review — {reviewDialog?.record_number}
            </DialogTitle>
          </DialogHeader>

          <ScrollArea className="flex-1 -mx-6 px-6">
            <div className="space-y-4 pb-2">
              {reviewDetailLoading ? (
                <div className="flex items-center justify-center py-8 text-slate-400 text-sm">
                  <RefreshCw size={14} className="animate-spin mr-2" /> Loading details...
                </div>
              ) : reviewDetail ? (
                <>
                  {/* ── Record Header Info ── */}
                  {reviewDetail.record_type === 'purchase_order' && (
                    <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 space-y-2">
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="text-sm font-bold text-slate-800">{reviewDetail.record_number}</p>
                          <div className="flex items-center gap-1.5 mt-1">
                            <User size={11} className="text-blue-600" />
                            <span className="text-xs font-semibold text-blue-800">{reviewDetail.supplier}</span>
                            {reviewDetail.supplier_contact && <span className="text-[10px] text-slate-400">({reviewDetail.supplier_contact})</span>}
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-lg font-bold font-mono text-slate-800">{formatPHP(reviewDetail.grand_total)}</p>
                          <Badge className={`text-[9px] ${
                            reviewDetail.payment_status === 'paid' ? 'bg-emerald-100 text-emerald-700' :
                            reviewDetail.payment_status === 'partial' ? 'bg-amber-100 text-amber-700' :
                            'bg-red-100 text-red-700'
                          }`}>
                            {reviewDetail.payment_status === 'paid' ? 'Paid' : reviewDetail.payment_status === 'partial' ? `Partial (${formatPHP(reviewDetail.total_paid)})` : 'Unpaid'}
                          </Badge>
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-slate-500 pt-1 border-t border-blue-100">
                        <span className="flex items-center gap-1"><Building2 size={10} /> {reviewDetail.branch_name}</span>
                        <span className="flex items-center gap-1"><CalendarDays size={10} /> Date: {reviewDetail.date?.slice(0, 10)}</span>
                        {reviewDetail.due_date && <span className="flex items-center gap-1"><Clock size={10} /> Due: {reviewDetail.due_date.slice(0, 10)}</span>}
                        <span className="flex items-center gap-1">Status: <Badge className="text-[9px] bg-slate-200 text-slate-600">{reviewDetail.status}</Badge></span>
                        {reviewDetail.received_by && <span>Received by: {reviewDetail.received_by}</span>}
                        {reviewDetail.created_by && <span>Created by: {reviewDetail.created_by}</span>}
                      </div>
                      {reviewDetail.verified && (
                        <div className="flex items-center gap-1.5 text-[10px] text-emerald-600 bg-emerald-50 rounded-lg px-2 py-1">
                          <ShieldCheck size={11} /> Verified by {reviewDetail.verified_by} {reviewDetail.verified_at ? `on ${reviewDetail.verified_at.slice(0, 10)}` : ''}
                        </div>
                      )}
                    </div>
                  )}

                  {reviewDetail.record_type === 'branch_transfer' && (
                    <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 space-y-2">
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="text-sm font-bold text-slate-800">{reviewDetail.record_number}</p>
                          {reviewDetail.invoice_number && <p className="text-[10px] text-blue-600 font-mono">{reviewDetail.invoice_number}</p>}
                          <div className="flex items-center gap-1.5 mt-1 text-xs text-emerald-800">
                            <Building2 size={11} /> {reviewDetail.from_branch} <span className="text-slate-400">→</span> {reviewDetail.to_branch}
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-lg font-bold font-mono text-slate-800">{formatPHP(reviewDetail.grand_total)}</p>
                          <p className="text-[10px] text-slate-400">Retail: {formatPHP(reviewDetail.retail_total)}</p>
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-slate-500 pt-1 border-t border-emerald-100">
                        <span>Status: <Badge className="text-[9px] bg-slate-200 text-slate-600">{reviewDetail.status}</Badge></span>
                        {reviewDetail.sent_at && <span>Sent: {reviewDetail.sent_at.slice(0, 10)}</span>}
                        {reviewDetail.received_at && <span>Received: {reviewDetail.received_at.slice(0, 10)}</span>}
                        {reviewDetail.received_by && <span>By: {reviewDetail.received_by}</span>}
                        {reviewDetail.has_shortage && <Badge className="text-[9px] bg-red-100 text-red-700">Shortage</Badge>}
                      </div>
                    </div>
                  )}

                  {reviewDetail.record_type === 'expense' && (
                    <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-2">
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="text-sm font-bold text-slate-800">{reviewDetail.category}</p>
                          <p className="text-xs text-slate-600">{reviewDetail.description}</p>
                          {reviewDetail.vendor && <p className="text-[10px] text-slate-500 mt-0.5">Payee: {reviewDetail.vendor}</p>}
                        </div>
                        <p className="text-lg font-bold font-mono text-slate-800">{formatPHP(reviewDetail.grand_total)}</p>
                      </div>
                      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-slate-500 pt-1 border-t border-amber-100">
                        <span className="flex items-center gap-1"><Building2 size={10} /> {reviewDetail.branch_name}</span>
                        <span className="flex items-center gap-1"><CalendarDays size={10} /> {reviewDetail.date?.slice(0, 10)}</span>
                        {reviewDetail.payment_method && <span>Method: {reviewDetail.payment_method}</span>}
                        {reviewDetail.created_by && <span>By: {reviewDetail.created_by}</span>}
                      </div>
                    </div>
                  )}

                  {/* ── Item Breakdown ── */}
                  {reviewDetail.items?.length > 0 && (
                    <div className="bg-white border rounded-xl overflow-hidden">
                      <div className="px-3 py-2 bg-slate-50 border-b flex items-center gap-2">
                        <Package size={13} className="text-slate-500" />
                        <span className="text-xs font-semibold text-slate-700">Items ({reviewDetail.items.length})</span>
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
                          {reviewDetail.items.map((item, idx) => (
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
                  {receiptPreview?.files?.length > 0 && (
                    <div className="bg-white border rounded-xl overflow-hidden">
                      <div className="px-3 py-2 bg-slate-50 border-b flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Camera size={13} className="text-slate-500" />
                          <span className="text-xs font-semibold text-slate-700">Receipt Photos ({receiptPreview.files.length})</span>
                        </div>
                        <Button variant="outline" size="sm" className="h-6 text-[10px] px-2"
                          onClick={() => setViewQROpen(true)} data-testid="review-view-phone-btn">
                          <QrCode size={10} className="mr-1" /> View on Phone
                        </Button>
                      </div>
                      <div className="p-3 flex flex-wrap gap-2">
                        {receiptPreview.files.map((f, i) => {
                          const isImage = (f.content_type || '').startsWith('image/');
                          const url = `${BACKEND_URL}/api/uploads/file/${receiptPreview.item.record_type}/${receiptPreview.item.id}/${f.id}`;
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
                </>
              ) : (
                /* Fallback — old minimal view */
                reviewDialog && (
                  <div className={`p-3 rounded-lg ${TYPE_CONFIG[reviewDialog.record_type]?.bg || 'bg-slate-50'} border ${TYPE_CONFIG[reviewDialog.record_type]?.border || 'border-slate-200'}`}>
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-xs font-semibold text-slate-700">{reviewDialog.record_number}</p>
                        <p className="text-[10px] text-slate-500">{reviewDialog.description}</p>
                      </div>
                      <span className="text-sm font-bold font-mono text-slate-700">{formatPHP(reviewDialog.amount)}</span>
                    </div>
                  </div>
                )
              )}

              {/* ── Review Notes ── */}
              <div>
                <label className="text-xs text-slate-500 font-medium block mb-1">Review Notes (optional)</label>
                <Input
                  value={reviewNotes}
                  onChange={e => setReviewNotes(e.target.value)}
                  placeholder="e.g. Verified receipt matches encoded items..."
                  className="h-9 text-sm"
                  data-testid="review-notes-input"
                />
              </div>

              {/* ── PIN Entry ── */}
              <div>
                <label className="text-xs text-slate-500 font-medium flex items-center gap-1.5 mb-1">
                  <Shield size={11} className="text-amber-500" />
                  Admin PIN, Auditor PIN, or TOTP Code <span className="text-red-500">*</span>
                </label>
                <Input
                  type="password" autoComplete="new-password"
                  value={reviewPin}
                  onChange={e => setReviewPin(e.target.value)}
                  placeholder="Enter PIN or authenticator code"
                  className="h-9 text-sm font-mono"
                  data-testid="review-pin-input"
                  onKeyDown={e => { if (e.key === 'Enter') handleReview(); }}
                />
              </div>
            </div>
          </ScrollArea>

          {/* ── Actions Bar ── */}
          <div className="flex justify-between items-center pt-3 border-t -mx-6 px-6">
            <Button variant="ghost" size="sm" onClick={() => goToRecord(reviewDialog)} className="text-xs text-slate-500 hover:text-[#1A4D2E]">
              <ExternalLink size={12} className="mr-1" /> Open Full Page
            </Button>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => { setReviewDialog(null); setReceiptPreview(null); setReviewDetail(null); }}>Cancel</Button>
              <Button size="sm" onClick={handleReview} disabled={reviewSaving || !reviewPin}
                className="bg-[#1A4D2E] hover:bg-[#14532d] text-white"
                data-testid="confirm-review-btn">
                {reviewSaving ? <RefreshCw size={12} className="animate-spin mr-1" /> : <CheckCircle2 size={12} className="mr-1" />}
                Mark as Reviewed
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── View on Phone QR Dialog ── */}
      <ViewQRDialog
        open={viewQROpen}
        onClose={() => setViewQROpen(false)}
        recordType={reviewDialog?.record_type}
        recordId={reviewDialog?.id}
        fileCount={receiptPreview?.files?.length || 0}
      />
    </div>
  );
}
