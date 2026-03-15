import { useState, useEffect } from 'react';
import { api, useAuth } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import UploadQRDialog from './UploadQRDialog';
import ReceiptGallery from './ReceiptGallery';
import VerificationBadge from './VerificationBadge';
import VerifyPinDialog from './VerifyPinDialog';
import ViewQRDialog from './ViewQRDialog';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Separator } from './ui/separator';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import {
  FileText, Check, X, AlertTriangle, ShieldCheck, Pencil, Upload,
  RefreshCw, DollarSign, Package, Clock, Printer
} from 'lucide-react';
import { toast } from 'sonner';
import PrintEngine from '../lib/PrintEngine';

const statusColor = (s) => {
  if (s === 'received') return 'bg-emerald-100 text-emerald-700';
  if (s === 'ordered') return 'bg-blue-100 text-blue-700';
  if (s === 'draft') return 'bg-slate-100 text-slate-600';
  if (s === 'cancelled') return 'bg-red-100 text-red-600';
  return 'bg-slate-100 text-slate-700';
};
const payStatusColor = (s) => {
  if (s === 'paid') return 'bg-emerald-100 text-emerald-700';
  if (s === 'partial') return 'bg-amber-100 text-amber-700';
  return 'bg-red-100 text-red-600';
};

export default function PODetailModal({ open, onOpenChange, poId, poNumber, onUpdated }) {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  const [po, setPo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [businessInfo, setBusinessInfo] = useState({});

  useEffect(() => {
    api.get('/settings/business-info').then(r => setBusinessInfo(r.data)).catch(() => {});
  }, []);

  const handlePrintPO = async (format = 'full_page') => {
    if (!po) return;
    let docCode = po.doc_code || '';
    if (!docCode && po.id) {
      try {
        const res = await api.post('/doc/generate-code', { doc_type: 'purchase_order', doc_id: po.id });
        docCode = res.data?.code || '';
        setPo(prev => prev ? { ...prev, doc_code: docCode } : prev);
      } catch { /* print without QR */ }
    }
    PrintEngine.print({ type: 'purchase_order', data: po, format, businessInfo, docCode });
  };

  // Edit
  const [editMode, setEditMode] = useState(false);
  const [editItems, setEditItems] = useState([]);
  const [editDR, setEditDR] = useState('');
  const [editReason, setEditReason] = useState('');
  const [saving, setSaving] = useState(false);

  // Payment adjustment after edit
  const [payAdjDialog, setPayAdjDialog] = useState(false);
  const [payAdjData, setPayAdjData] = useState(null);
  const [payAdjFundSource, setPayAdjFundSource] = useState('cashier');
  const [payAdjReason, setPayAdjReason] = useState('');
  const [payAdjFunds, setPayAdjFunds] = useState({ cashier: 0, safe: 0 });
  const [payAdjSaving, setPayAdjSaving] = useState(false);

  // QR/Receipt dialogs
  const [uploadQROpen, setUploadQROpen] = useState(false);
  const [viewQROpen, setViewQROpen] = useState(false);
  const [verifyDialogOpen, setVerifyDialogOpen] = useState(false);

  // Receipt review
  const [reviewPinDialog, setReviewPinDialog] = useState(false);
  const [reviewPin, setReviewPin] = useState('');
  const [reviewSaving, setReviewSaving] = useState(false);

  useEffect(() => {
    if (open && (poId || poNumber)) {
      loadPO();
      setEditMode(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, poId, poNumber]);

  const loadPO = async () => {
    setLoading(true);
    try {
      let res;
      if (poId) {
        res = await api.get(`/purchase-orders/${poId}`);
      } else {
        res = await api.get(`/invoices/by-number/${encodeURIComponent(poNumber)}`);
      }
      setPo(res.data);
    } catch {
      toast.error('Failed to load PO');
      onOpenChange(false);
    }
    setLoading(false);
  };

  const poTotal = (p) => {
    if (!p) return 0;
    if (p.grand_total != null) return p.grand_total;
    const lineSub = (p.items || []).reduce((s, i) => s + (i.total || i.quantity * i.unit_price), 0);
    return lineSub + (p.freight || 0) - (p.overall_discount_amount || 0) + (p.tax_amount || 0);
  };

  // ── Edit ──
  const openEdit = () => {
    setEditItems(po.items?.map(i => ({ ...i })) || []);
    setEditDR(po.dr_number || '');
    setEditReason('');
    setEditMode(true);
  };

  const saveEdit = async () => {
    if (!editReason.trim()) { toast.error('Please enter a reason for the edit'); return; }
    setSaving(true);
    try {
      const res = await api.put(`/purchase-orders/${po.id}`, {
        items: editItems, dr_number: editDR, notes: po.notes, edit_reason: editReason,
      });
      const updated = res.data;
      const oldTotal = poTotal(po);
      const newTotal = poTotal(updated);
      const delta = Math.round((newTotal - oldTotal) * 100) / 100;
      const isPaid = po.payment_status === 'paid' || po.po_type === 'cash' || po.payment_method === 'cash';

      setPo(updated);
      setEditMode(false);
      toast.success('PO updated!');
      onUpdated?.();

      if (Math.abs(delta) > 0.01 && isPaid) {
        try {
          const fundsRes = await api.get('/purchase-orders/fund-balances');
          setPayAdjFunds({ cashier: fundsRes.data.cashier || 0, safe: fundsRes.data.safe || 0 });
        } catch {}
        setPayAdjData({ po: updated, delta, oldTotal, newTotal });
        setPayAdjReason(editReason);
        setPayAdjFundSource('cashier');
        setPayAdjDialog(true);
      }
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to save'); }
    setSaving(false);
  };

  const handlePayAdjustment = async () => {
    if (!payAdjReason.trim()) { toast.error('Please enter a reason'); return; }
    if (!payAdjData) return;
    setPayAdjSaving(true);
    try {
      const res = await api.post(`/purchase-orders/${payAdjData.po.id}/adjust-payment`, {
        new_grand_total: payAdjData.newTotal, old_grand_total: payAdjData.oldTotal,
        fund_source: payAdjFundSource, reason: payAdjReason, payment_method: 'Cash',
      });
      toast.success(res.data.message);
      setPayAdjDialog(false);
      setPayAdjData(null);
      const updated = await api.get(`/purchase-orders/${payAdjData.po.id}`).catch(() => null);
      if (updated) setPo(updated.data);
      onUpdated?.();
    } catch (e) {
      const detail = e.response?.data?.detail;
      toast.error(typeof detail === 'object' ? detail?.message : (typeof detail === 'string' ? detail : 'Adjustment failed'));
    }
    setPayAdjSaving(false);
  };

  // ── Receipt review ──
  const handleMarkReviewed = async () => {
    if (!reviewPin) { toast.error('Enter admin PIN or TOTP'); return; }
    setReviewSaving(true);
    try {
      const res = await api.post(`/purchase-orders/${po.id}/mark-reviewed`, { pin: reviewPin });
      toast.success(res.data.message);
      setReviewPinDialog(false);
      setReviewPin('');
      setPo(prev => ({ ...prev, receipt_review_status: 'reviewed', receipt_reviewed_by_name: res.data.reviewed_by, receipt_reviewed_at: new Date().toISOString() }));
      onUpdated?.();
    } catch (e) { toast.error(e.response?.data?.detail || 'Review failed'); }
    setReviewSaving(false);
  };

  if (!open) return null;

  return (
    <>
      <Dialog open={open} onOpenChange={v => { onOpenChange(v); if (!v) setEditMode(false); }}>
        <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto" data-testid="po-detail-modal">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Manrope' }} data-testid="po-detail-title">
              {editMode ? `Edit PO — ${po?.po_number}` : `PO Detail — ${po?.po_number}`}
            </DialogTitle>
            {po?.verified && (
              <div className="mt-1 flex items-center gap-2">
                <VerificationBadge doc={po} />
                {po.verified_at && <span className="text-[10px] text-slate-400">{po.verified_at?.slice(0, 16)?.replace('T', ' ')}</span>}
              </div>
            )}
          </DialogHeader>

          {/* Action toolbar — always visible */}
          {po && !loading && (
            <div className="flex flex-wrap items-center gap-1.5 pb-2 border-b border-slate-100" data-testid="po-action-bar">
              <Button size="sm" variant="outline" className="h-7 text-xs"
                onClick={() => handlePrintPO('full_page')} data-testid="po-print-btn">
                <Printer size={12} className="mr-1" /> Print Full
              </Button>
              <Button size="sm" variant="outline" className="h-7 text-xs"
                onClick={() => handlePrintPO('thermal')} data-testid="po-print-thermal-btn">
                <Printer size={12} className="mr-1" /> Print 58mm
              </Button>
              <Button size="sm" variant="outline" className="h-7 text-xs"
                onClick={() => setViewQROpen(true)} data-testid="po-view-phone-btn">
                <Package size={12} className="mr-1" /> View on Phone
              </Button>
              <Button size="sm" variant="outline" className="h-7 text-xs"
                onClick={() => setUploadQROpen(true)} data-testid="po-upload-receipt-btn">
                <Upload size={12} className="mr-1" /> Upload Receipt
              </Button>
              {!po.verified && (
                <Button size="sm" variant="outline" className="h-7 text-xs text-[#1A4D2E] border-[#1A4D2E]/30 hover:bg-[#1A4D2E]/5"
                  onClick={() => setVerifyDialogOpen(true)} data-testid="po-verify-btn">
                  <ShieldCheck size={12} className="mr-1" /> Verify
                </Button>
              )}
              {po.status === 'ordered' && po.reopened_at && !editMode && (
                <Button size="sm" variant="outline" className="h-7 text-xs text-amber-600 border-amber-200 hover:bg-amber-50"
                  onClick={openEdit} data-testid="po-edit-btn">
                  <Pencil size={12} className="mr-1" /> Edit
                </Button>
              )}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-12"><div className="text-slate-400">Loading...</div></div>
          ) : po ? (
            <div className="space-y-4">
              {/* Reopened banner */}
              {po.reopened_at && (
                <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800 flex items-center gap-2">
                  <AlertTriangle size={12} className="shrink-0 text-amber-600" />
                  <span>This PO was reopened by <b>{po.reopened_by}</b>. Inventory was reversed. Edit then click <b>Receive</b> to re-add stock.</span>
                </div>
              )}

              {/* Receipts gallery */}
              <ReceiptGallery recordType="purchase_order" recordId={po.id} />

              {/* Receipt Review Status */}
              {(po.receipt_count > 0 || po.receipt_review_status) && (
                <div className={`p-3 rounded-xl border ${po.receipt_review_status === 'reviewed' ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {po.receipt_review_status === 'reviewed' ? (
                        <>
                          <ShieldCheck size={16} className="text-emerald-600" />
                          <div>
                            <p className="text-xs font-semibold text-emerald-700">Receipts Reviewed</p>
                            <p className="text-[10px] text-emerald-600">by {po.receipt_reviewed_by_name} {po.receipt_reviewed_at ? `on ${po.receipt_reviewed_at.slice(0, 10)}` : ''}</p>
                          </div>
                        </>
                      ) : (
                        <>
                          <AlertTriangle size={16} className="text-amber-600" />
                          <div>
                            <p className="text-xs font-semibold text-amber-700">Receipts Pending Review</p>
                            <p className="text-[10px] text-amber-600">{po.receipt_count || 0} photo(s) attached</p>
                          </div>
                        </>
                      )}
                    </div>
                    {po.receipt_review_status !== 'reviewed' && po.status === 'received' && (
                      <Button size="sm" variant="outline" className="h-7 text-xs text-[#1A4D2E] border-[#1A4D2E]/40 hover:bg-[#1A4D2E]/10"
                        onClick={() => setReviewPinDialog(true)} data-testid="po-mark-reviewed-btn">
                        <ShieldCheck size={12} className="mr-1" /> Mark as Reviewed
                      </Button>
                    )}
                  </div>
                </div>
              )}

              {/* Header info */}
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div><span className="text-slate-500">Vendor:</span> <b>{po.vendor}</b></div>
                <div><span className="text-slate-500">Date:</span> {po.purchase_date}</div>
                <div>
                  <span className="text-slate-500">DR #:</span>{' '}
                  {editMode ? (
                    <Input value={editDR} onChange={e => setEditDR(e.target.value)} className="h-7 text-sm mt-0.5 w-full" placeholder="DR number" />
                  ) : <b>{po.dr_number || '—'}</b>}
                </div>
                <div><span className="text-slate-500">Status:</span> <Badge className={`${statusColor(po.status)} text-[10px]`}>{po.status}</Badge></div>
                <div className="flex items-center gap-1"><span className="text-slate-500">Payment:</span>
                  <Badge className={`text-[10px] ${payStatusColor(po.payment_status || 'unpaid')}`}>
                    {po.po_type === 'cash' || po.payment_method === 'cash' ? 'Cash' : 'Terms'} · {po.payment_status || 'unpaid'}
                  </Badge>
                </div>
                {po.balance > 0 && <div><span className="text-slate-500">Balance:</span> <b className="text-red-600">{formatPHP(po.balance)}</b></div>}
                {po.due_date && <div><span className="text-slate-500">Due:</span> {po.due_date}</div>}
              </div>

              {/* Items table — view or edit mode */}
              {editMode ? (
                <div className="space-y-2">
                  <p className="text-xs text-slate-500 font-medium uppercase">Edit Items</p>
                  {editItems.map((item, i) => (
                    <div key={i} className="grid grid-cols-12 gap-1.5 items-center p-2 bg-slate-50 rounded-lg border border-slate-200">
                      <div className="col-span-5 text-xs font-medium truncate">{item.product_name}</div>
                      <div className="col-span-3">
                        <Label className="text-[9px] text-slate-400">Qty</Label>
                        <Input type="number" min={0} value={item.quantity}
                          onChange={e => { const n = [...editItems]; n[i] = { ...n[i], quantity: parseFloat(e.target.value) || 0 }; setEditItems(n); }}
                          className="h-7 text-sm text-right font-mono" />
                      </div>
                      <div className="col-span-4">
                        <Label className="text-[9px] text-slate-400">Unit Price</Label>
                        <Input type="number" min={0} value={item.unit_price}
                          onChange={e => { const n = [...editItems]; n[i] = { ...n[i], unit_price: parseFloat(e.target.value) || 0 }; setEditItems(n); }}
                          className="h-7 text-sm text-right font-mono" />
                      </div>
                    </div>
                  ))}
                  <div className="mt-2">
                    <Label className="text-xs text-slate-500">Reason for Edit <span className="text-red-500">*</span></Label>
                    <Input value={editReason} onChange={e => setEditReason(e.target.value)}
                      placeholder="e.g. Supplier corrected quantity on actual DR, price was wrong on original..."
                      className="mt-1 h-9 text-sm" />
                    <p className="text-[10px] text-slate-400 mt-0.5">This reason will be saved in the edit history.</p>
                  </div>
                  <div className="flex gap-2 pt-2 border-t">
                    <Button variant="outline" onClick={() => setEditMode(false)} className="flex-1">Cancel Edit</Button>
                    <Button onClick={saveEdit} disabled={saving} className="flex-1 bg-amber-600 hover:bg-amber-700 text-white">
                      {saving ? <RefreshCw size={13} className="animate-spin mr-1.5" /> : <Check size={13} className="mr-1.5" />}
                      Save Changes
                    </Button>
                  </div>
                  <p className="text-[10px] text-amber-600 text-center">After saving, use the Receive button in the PO list to re-add inventory.</p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-xs">Product</TableHead>
                      <TableHead className="text-xs">Unit</TableHead>
                      <TableHead className="text-xs text-right">Qty</TableHead>
                      <TableHead className="text-xs text-right">Price</TableHead>
                      <TableHead className="text-xs text-right">Disc</TableHead>
                      <TableHead className="text-xs text-right">Total</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {po.items?.map((item, i) => (
                      <TableRow key={i}>
                        <TableCell className="text-sm">{item.product_name}</TableCell>
                        <TableCell className="text-xs text-slate-500">{item.unit || '—'}</TableCell>
                        <TableCell className="text-right">{item.quantity}</TableCell>
                        <TableCell className="text-right font-mono">{formatPHP(item.unit_price)}</TableCell>
                        <TableCell className="text-right text-xs text-emerald-600">{item.discount_amount > 0 ? `-${formatPHP(item.discount_amount)}` : '—'}</TableCell>
                        <TableCell className="text-right font-semibold font-mono">{formatPHP(item.total || item.quantity * item.unit_price)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}

              {!editMode && (
                <>
                  <div className="text-sm space-y-1 border-t pt-3">
                    <div className="flex justify-between"><span className="text-slate-500">Subtotal</span><span className="font-mono">{formatPHP(po.line_subtotal || po.subtotal)}</span></div>
                    {po.overall_discount_amount > 0 && <div className="flex justify-between text-emerald-600"><span>Overall Discount</span><span className="font-mono">-{formatPHP(po.overall_discount_amount)}</span></div>}
                    {po.freight > 0 && <div className="flex justify-between"><span className="text-slate-500">Freight</span><span className="font-mono">{formatPHP(po.freight)}</span></div>}
                    {po.tax_amount > 0 && <div className="flex justify-between"><span className="text-slate-500">VAT ({po.tax_rate}%)</span><span className="font-mono">{formatPHP(po.tax_amount)}</span></div>}
                    <div className="flex justify-between font-bold text-base pt-1 border-t"><span>Grand Total</span><span className="font-mono text-[#1A4D2E]">{formatPHP(po.grand_total || po.subtotal)}</span></div>
                  </div>
                  {po.notes && <p className="text-sm text-slate-500 border-t pt-2">Notes: {po.notes}</p>}
                  {po.edit_history?.length > 0 && (
                    <div className="border-t pt-2">
                      <p className="text-xs font-semibold uppercase text-slate-400 mb-2">Edit History</p>
                      {po.edit_history.map((edit, i) => (
                        <div key={i} className="text-xs p-2 bg-amber-50 rounded mb-1.5 border border-amber-100">
                          <div className="flex items-center justify-between mb-0.5">
                            <span className="font-semibold text-amber-800">{edit.changed_by}</span>
                            <span className="text-slate-400">{edit.changed_at?.slice(0, 10)}</span>
                          </div>
                          <p className="text-slate-600 italic">"{edit.reason}"</p>
                          <p className="text-slate-500 mt-0.5">{edit.change_summary}</p>
                        </div>
                      ))}
                    </div>
                  )}
                  {po.payment_history?.length > 0 && (
                    <div className="border-t pt-2">
                      <p className="text-xs font-semibold uppercase text-slate-400 mb-2">Payment History</p>
                      {po.payment_history.map((pay, i) => (
                        <div key={i} className="flex items-center justify-between text-xs py-1 border-b last:border-0">
                          <div className="flex items-center gap-2">
                            <Check size={10} className="text-emerald-500" />
                            <span>{pay.date}</span>
                            <span className="text-slate-400">{pay.method}</span>
                            {pay.check_number && <span className="text-slate-400">#{pay.check_number}</span>}
                            <span className="text-slate-400">{pay.fund_source || ''}</span>
                          </div>
                          <span className="font-bold text-emerald-600">{formatPHP(pay.amount)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center py-12"><div className="text-slate-400">PO not found</div></div>
          )}
        </DialogContent>
      </Dialog>

      {/* Upload QR Dialog */}
      <UploadQRDialog
        open={uploadQROpen}
        onClose={(count) => {
          setUploadQROpen(false);
          if (count > 0) {
            toast.success(`${count} receipt photo(s) uploaded!`);
            if (po) setPo(prev => ({ ...prev, receipt_count: (prev.receipt_count || 0) + count }));
            onUpdated?.();
          }
        }}
        recordType="purchase_order"
        recordId={po?.id}
      />

      {/* View QR Dialog */}
      <ViewQRDialog open={viewQROpen} onClose={() => setViewQROpen(false)} recordType="purchase_order" recordId={po?.id} />

      {/* Verify PIN Dialog */}
      <VerifyPinDialog
        open={verifyDialogOpen}
        onClose={() => setVerifyDialogOpen(false)}
        docType="purchase_order"
        docId={po?.id}
        docLabel={po?.po_number}
        onVerified={(result) => {
          setVerifyDialogOpen(false);
          setPo(prev => ({ ...prev, verified: true, verified_by_name: result.verified_by, verified_at: new Date().toISOString(), verification_status: result.status, has_discrepancy: result.status === 'discrepancy' }));
          onUpdated?.();
        }}
      />

      {/* Mark as Reviewed PIN Dialog */}
      <Dialog open={reviewPinDialog} onOpenChange={v => { if (!v) { setReviewPinDialog(false); setReviewPin(''); } }}>
        <DialogContent className="sm:max-w-xs">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
              <ShieldCheck size={18} className="text-[#1A4D2E]" /> Review Receipts
            </DialogTitle>
            <DialogDescription>
              Enter your admin PIN or TOTP to confirm you have reviewed the receipt photos for PO {po?.po_number}.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 mt-2">
            <div>
              <Label className="text-xs">Admin PIN or TOTP</Label>
              <Input type="password" autoComplete="new-password" value={reviewPin} onChange={e => setReviewPin(e.target.value)}
                placeholder="Enter PIN..." className="mt-1" onKeyDown={e => { if (e.key === 'Enter') handleMarkReviewed(); }}
                data-testid="review-pin-input" />
            </div>
            <Button onClick={handleMarkReviewed} disabled={reviewSaving || !reviewPin}
              className="w-full bg-[#1A4D2E] hover:bg-[#14532d] text-white" data-testid="confirm-review-btn">
              {reviewSaving ? <RefreshCw size={13} className="animate-spin mr-1.5" /> : <ShieldCheck size={13} className="mr-1.5" />}
              Confirm Review
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Payment Adjustment Dialog */}
      <Dialog open={payAdjDialog} onOpenChange={v => { if (!v) setPayAdjDialog(false); }}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
              <DollarSign size={18} className="text-amber-600" /> Payment Adjustment
            </DialogTitle>
          </DialogHeader>
          {payAdjData && (
            <div className="space-y-3 mt-2">
              <div className="text-sm space-y-1 bg-amber-50 rounded-lg p-3 border border-amber-200">
                <div className="flex justify-between"><span className="text-slate-600">Old Total</span><span className="font-mono">{formatPHP(payAdjData.oldTotal)}</span></div>
                <div className="flex justify-between"><span className="text-slate-600">New Total</span><span className="font-mono">{formatPHP(payAdjData.newTotal)}</span></div>
                <Separator />
                <div className="flex justify-between font-bold">
                  <span>{payAdjData.delta > 0 ? 'Additional Payment' : 'Refund'}</span>
                  <span className={payAdjData.delta > 0 ? 'text-red-600' : 'text-emerald-600'}>{formatPHP(Math.abs(payAdjData.delta))}</span>
                </div>
              </div>
              <div>
                <Label className="text-xs text-slate-500">Fund Source</Label>
                <Select value={payAdjFundSource} onValueChange={setPayAdjFundSource}>
                  <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="cashier">Cashier ({formatPHP(payAdjFunds.cashier)})</SelectItem>
                    <SelectItem value="safe">Safe ({formatPHP(payAdjFunds.safe)})</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs text-slate-500">Reason</Label>
                <Input value={payAdjReason} onChange={e => setPayAdjReason(e.target.value)} className="mt-1" />
              </div>
              <Button onClick={handlePayAdjustment} disabled={payAdjSaving || !payAdjReason.trim()}
                className="w-full bg-amber-600 hover:bg-amber-700 text-white">
                {payAdjSaving ? <RefreshCw size={13} className="animate-spin mr-1.5" /> : <Check size={13} className="mr-1.5" />}
                Confirm Adjustment
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
