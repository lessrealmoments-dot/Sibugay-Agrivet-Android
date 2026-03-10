import { useState, useEffect } from 'react';
import { api, useAuth } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import UploadQRDialog from './UploadQRDialog';
import ReceiptGallery from './ReceiptGallery';
import VerificationBadge from './VerificationBadge';
import VerifyPinDialog from './VerifyPinDialog';
import ViewQRDialog from './ViewQRDialog';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Separator } from './ui/separator';
import { Textarea } from './ui/textarea';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import {
  ShieldCheck, Upload, Pencil, Check, AlertTriangle,
  RefreshCw, Ban, DollarSign, Wallet, CreditCard, Clock
} from 'lucide-react';
import { toast } from 'sonner';

export default function SaleDetailModal({ open, onOpenChange, saleId, invoiceNumber, onUpdated }) {
  const { user, hasPerm } = useAuth();
  const isAdmin = user?.role === 'admin';

  const [sale, setSale] = useState(null);
  const [loading, setLoading] = useState(true);

  // Edit
  const [editMode, setEditMode] = useState(false);
  const [editItems, setEditItems] = useState([]);
  const [editNotes, setEditNotes] = useState('');
  const [editReason, setEditReason] = useState('');
  const [saving, setSaving] = useState(false);

  // Actions
  const [voidOpen, setVoidOpen] = useState(false);
  const [voidReason, setVoidReason] = useState('');
  const [voidPin, setVoidPin] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  // QR/Receipt
  const [uploadQROpen, setUploadQROpen] = useState(false);
  const [viewQROpen, setViewQROpen] = useState(false);
  const [verifyDialogOpen, setVerifyDialogOpen] = useState(false);

  useEffect(() => {
    if (open && (saleId || invoiceNumber)) {
      loadSale();
      setEditMode(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, saleId, invoiceNumber]);

  const loadSale = async () => {
    setLoading(true);
    try {
      let res;
      if (saleId) {
        res = await api.get(`/invoices/${saleId}`);
      } else {
        res = await api.get(`/invoices/by-number/${encodeURIComponent(invoiceNumber)}`);
      }
      setSale(res.data);
    } catch {
      toast.error('Failed to load sale details');
      onOpenChange(false);
    }
    setLoading(false);
  };

  const canEdit = sale && sale.status !== 'voided' && (isAdmin || hasPerm('pos', 'sell'));
  const canVoid = sale && sale.status !== 'voided' && (isAdmin || hasPerm('pos', 'sell'));

  // ── Edit ──
  const openEdit = () => {
    setEditItems(sale.items?.map(i => ({ ...i })) || []);
    setEditNotes(sale.notes || '');
    setEditReason('');
    setEditMode(true);
  };

  const handleItemChange = (index, field, value) => {
    const items = [...editItems];
    items[index] = { ...items[index], [field]: value };
    const item = items[index];
    const qty = parseFloat(item.quantity) || 0;
    const rate = parseFloat(item.rate || item.unit_price || item.price) || 0;
    const discVal = parseFloat(item.discount_value) || 0;
    const discType = item.discount_type || 'amount';
    const discAmt = discType === 'percent' ? qty * rate * discVal / 100 : discVal;
    items[index].total = Math.round((qty * rate - discAmt) * 100) / 100;
    setEditItems(items);
  };

  const saveEdit = async () => {
    if (!editReason.trim()) { toast.error('Please provide a reason for the edit'); return; }
    setSaving(true);
    try {
      await api.put(`/invoices/${sale.id}/edit`, {
        items: editItems, notes: editNotes, reason: editReason,
        customer_name: sale.customer_name, freight: sale.freight || 0, overall_discount: sale.overall_discount || 0,
      });
      toast.success('Sale updated');
      setEditMode(false);
      loadSale();
      onUpdated?.();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to save'); }
    setSaving(false);
  };

  // ── Void ──
  const handleVoid = async () => {
    if (!voidReason || !voidPin) { toast.error('Reason and PIN required'); return; }
    setActionLoading(true);
    try {
      await api.post(`/invoices/${sale.id}/void`, { reason: voidReason, pin: voidPin });
      toast.success('Sale voided');
      setVoidOpen(false);
      setVoidReason('');
      setVoidPin('');
      loadSale();
      onUpdated?.();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to void'); }
    setActionLoading(false);
  };

  const saleNumber = sale?.invoice_number || sale?.sale_number || '';
  const isVoided = sale?.status === 'voided';

  if (!open) return null;

  return (
    <>
      <Dialog open={open} onOpenChange={v => { onOpenChange(v); if (!v) setEditMode(false); }}>
        <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto" data-testid="sale-detail-modal">
          <DialogHeader>
            <div className="flex items-center justify-between">
              <DialogTitle style={{ fontFamily: 'Manrope' }} data-testid="sale-detail-title">
                {editMode ? `Edit Sale — ${saleNumber}` : `Sale Detail — ${saleNumber}`}
              </DialogTitle>
              {sale && !loading && (
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" className="h-7 text-xs bg-slate-800 text-white border-slate-600 hover:bg-slate-700"
                    onClick={() => setViewQROpen(true)} data-testid="sale-view-phone-btn">
                    <span className="mr-1">📱</span> View
                  </Button>
                  <Button size="sm" variant="outline" className="h-7 text-xs"
                    onClick={() => setUploadQROpen(true)} data-testid="sale-upload-receipt-btn">
                    <Upload size={12} className="mr-1" /> Upload Receipt
                  </Button>
                  {!sale.verified && !isVoided && (
                    <Button size="sm" variant="outline" className="h-7 text-xs text-[#1A4D2E] border-[#1A4D2E]/40 hover:bg-[#1A4D2E]/10"
                      onClick={() => setVerifyDialogOpen(true)} data-testid="sale-verify-btn">
                      <ShieldCheck size={12} className="mr-1" /> Verify
                    </Button>
                  )}
                  {canEdit && !editMode && (
                    <Button size="sm" variant="outline" className="h-7 text-xs text-amber-600 border-amber-300"
                      onClick={openEdit} data-testid="sale-edit-btn">
                      <Pencil size={12} className="mr-1" /> Edit
                    </Button>
                  )}
                </div>
              )}
            </div>
            {sale?.verified && (
              <div className="mt-1.5 flex items-center gap-2">
                <VerificationBadge doc={sale} />
                {sale.verified_at && <span className="text-[10px] text-slate-400">{sale.verified_at?.slice(0, 16)?.replace('T', ' ')}</span>}
              </div>
            )}
          </DialogHeader>

          {loading ? (
            <div className="flex items-center justify-center py-12"><div className="text-slate-400">Loading...</div></div>
          ) : sale ? (
            <div className="space-y-4 mt-2">
              {/* Receipts gallery */}
              <ReceiptGallery recordType="invoice" recordId={sale.id} />

              {/* Header info */}
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div><span className="text-slate-500">Customer:</span> <b>{sale.customer_name || 'Walk-in'}</b></div>
                <div><span className="text-slate-500">Date:</span> {sale.order_date || sale.created_at?.slice(0, 10)}</div>
                <div><span className="text-slate-500">Cashier:</span> {sale.cashier_name || '—'}</div>
                <div><span className="text-slate-500">Payment:</span> <Badge variant="outline" className="text-[10px]">{sale.payment_method || 'Cash'}</Badge></div>
                <div><span className="text-slate-500">Status:</span>
                  <Badge className={`text-[10px] ml-1 ${isVoided ? 'bg-red-100 text-red-700' : sale.status === 'paid' ? 'bg-emerald-100 text-emerald-700' : sale.status === 'partial' ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'}`}>
                    {sale.status || 'completed'}
                  </Badge>
                </div>
                {sale.terms && <div><span className="text-slate-500">Terms:</span> {sale.terms_label || sale.terms}</div>}
                {sale.due_date && <div><span className="text-slate-500">Due:</span> {sale.due_date}</div>}
                {sale.balance > 0 && <div><span className="text-slate-500">Balance:</span> <b className="text-red-600">{formatPHP(sale.balance)}</b></div>}
              </div>

              {/* Digital payment info */}
              {(sale.digital_platform || sale.fund_source === 'digital' || sale.fund_source === 'split') && (
                <div className="grid grid-cols-2 gap-3 text-sm bg-slate-50 rounded-lg p-3">
                  {sale.digital_platform && <div><span className="text-slate-500">Platform:</span> <span className="flex items-center gap-1 inline-flex"><Wallet size={12} className="text-blue-500" />{sale.digital_platform}</span></div>}
                  {sale.digital_ref_number && <div><span className="text-slate-500">Ref #:</span> <span className="font-mono">{sale.digital_ref_number}</span></div>}
                  {sale.digital_sender && <div><span className="text-slate-500">Sender:</span> {sale.digital_sender}</div>}
                  {sale.fund_source && <div><span className="text-slate-500">Fund Source:</span> <span className="capitalize">{sale.fund_source}</span></div>}
                  {sale.cash_amount > 0 && <div><span className="text-slate-500">Cash Portion:</span> {formatPHP(sale.cash_amount)}</div>}
                  {sale.digital_amount > 0 && <div><span className="text-slate-500">Digital Portion:</span> {formatPHP(sale.digital_amount)}</div>}
                </div>
              )}

              {/* Items table */}
              {editMode ? (
                <div className="space-y-2">
                  <p className="text-xs text-slate-500 font-medium uppercase">Edit Items</p>
                  {editItems.map((item, i) => (
                    <div key={i} className="grid grid-cols-12 gap-1.5 items-center p-2 bg-slate-50 rounded-lg border border-slate-200">
                      <div className="col-span-5 text-xs font-medium truncate">{item.product_name}</div>
                      <div className="col-span-3">
                        <Label className="text-[9px] text-slate-400">Qty</Label>
                        <Input type="number" min={0} value={item.quantity}
                          onChange={e => handleItemChange(i, 'quantity', parseFloat(e.target.value) || 0)}
                          className="h-7 text-sm text-right font-mono" />
                      </div>
                      <div className="col-span-4">
                        <Label className="text-[9px] text-slate-400">Price</Label>
                        <Input type="number" min={0} value={item.rate || item.unit_price || item.price}
                          onChange={e => handleItemChange(i, 'rate', parseFloat(e.target.value) || 0)}
                          className="h-7 text-sm text-right font-mono" />
                      </div>
                    </div>
                  ))}
                  <div className="mt-2">
                    <Label className="text-xs text-slate-500">Reason for Edit <span className="text-red-500">*</span></Label>
                    <Input value={editReason} onChange={e => setEditReason(e.target.value)}
                      placeholder="e.g. Customer correction, wrong item scanned..."
                      className="mt-1 h-9 text-sm" />
                  </div>
                  <div className="flex gap-2 pt-2 border-t">
                    <Button variant="outline" onClick={() => setEditMode(false)} className="flex-1">Cancel</Button>
                    <Button onClick={saveEdit} disabled={saving} className="flex-1 bg-amber-600 hover:bg-amber-700 text-white">
                      {saving ? <RefreshCw size={13} className="animate-spin mr-1.5" /> : <Check size={13} className="mr-1.5" />}
                      Save Changes
                    </Button>
                  </div>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-xs">Product</TableHead>
                      <TableHead className="text-xs text-right">Qty</TableHead>
                      <TableHead className="text-xs text-right">Price</TableHead>
                      <TableHead className="text-xs text-right">Disc</TableHead>
                      <TableHead className="text-xs text-right">Total</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sale.items?.map((item, i) => (
                      <TableRow key={i}>
                        <TableCell className="text-sm">
                          {item.product_name}
                          {item.is_repack && <Badge variant="outline" className="text-[9px] ml-1">R</Badge>}
                        </TableCell>
                        <TableCell className="text-right">{item.quantity}</TableCell>
                        <TableCell className="text-right font-mono">{formatPHP(item.rate || item.unit_price || item.price || 0)}</TableCell>
                        <TableCell className="text-right text-xs text-emerald-600">{(item.discount_amount || 0) > 0 ? `-${formatPHP(item.discount_amount)}` : '—'}</TableCell>
                        <TableCell className="text-right font-semibold font-mono">{formatPHP(item.total || 0)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}

              {!editMode && (
                <>
                  <div className="text-sm space-y-1 border-t pt-3">
                    <div className="flex justify-between"><span className="text-slate-500">Subtotal</span><span className="font-mono">{formatPHP(sale.subtotal || sale.line_subtotal || 0)}</span></div>
                    {(sale.overall_discount || sale.overall_discount_amount || 0) > 0 && (
                      <div className="flex justify-between text-emerald-600"><span>Discount</span><span className="font-mono">-{formatPHP(sale.overall_discount || sale.overall_discount_amount || 0)}</span></div>
                    )}
                    {(sale.freight || 0) > 0 && <div className="flex justify-between"><span className="text-slate-500">Freight</span><span className="font-mono">{formatPHP(sale.freight)}</span></div>}
                    {(sale.tax_amount || 0) > 0 && <div className="flex justify-between"><span className="text-slate-500">Tax</span><span className="font-mono">{formatPHP(sale.tax_amount)}</span></div>}
                    <div className="flex justify-between font-bold text-base pt-1 border-t"><span>Grand Total</span><span className="font-mono text-[#1A4D2E]">{formatPHP(sale.grand_total || sale.total || 0)}</span></div>
                    {(sale.amount_paid || 0) > 0 && <div className="flex justify-between text-sm text-emerald-600"><span>Paid</span><span className="font-mono">{formatPHP(sale.amount_paid)}</span></div>}
                    {(sale.balance || 0) > 0 && <div className="flex justify-between text-sm text-red-600"><span>Balance</span><span className="font-mono">{formatPHP(sale.balance)}</span></div>}
                  </div>

                  {sale.notes && <p className="text-sm text-slate-500 border-t pt-2">Notes: {sale.notes}</p>}

                  {/* Sales rep / created info */}
                  <div className="text-xs text-slate-400 space-y-0.5 border-t pt-2">
                    {sale.sales_rep_name && <p>Sales Rep: {sale.sales_rep_name}</p>}
                    <p>Created: {sale.created_at ? new Date(sale.created_at).toLocaleString() : '—'} by {sale.cashier_name || '—'}</p>
                    {sale.edited && <p>Last edited: {sale.last_edited_at ? new Date(sale.last_edited_at).toLocaleString() : '—'} by {sale.last_edited_by || '—'}</p>}
                  </div>

                  {/* Payment history */}
                  {sale.payments?.length > 0 && (
                    <div className="border-t pt-2">
                      <p className="text-xs font-semibold uppercase text-slate-400 mb-2">Payment History</p>
                      {sale.payments.map((pay, i) => (
                        <div key={i} className="flex items-center justify-between text-xs py-1 border-b last:border-0">
                          <div className="flex items-center gap-2">
                            <Check size={10} className="text-emerald-500" />
                            <span>{pay.date || '—'}</span>
                            {pay.method && <Badge variant="outline" className="text-[9px]">{pay.method}</Badge>}
                            {pay.fund_source && <span className="text-slate-400">{pay.fund_source}</span>}
                          </div>
                          <span className="font-bold text-emerald-600">{formatPHP(pay.amount || 0)}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Edit history */}
                  {sale.edit_history?.length > 0 && (
                    <div className="border-t pt-2">
                      <p className="text-xs font-semibold uppercase text-slate-400 mb-2">Edit History</p>
                      {sale.edit_history.map((edit, i) => (
                        <div key={i} className="text-xs p-2 bg-amber-50 rounded mb-1.5 border border-amber-100">
                          <div className="flex items-center justify-between mb-0.5">
                            <span className="font-semibold text-amber-800">{edit.edited_by_name || edit.changed_by}</span>
                            <span className="text-slate-400">{(edit.edited_at || edit.changed_at)?.slice(0, 10)}</span>
                          </div>
                          <p className="text-slate-600 italic">"{edit.reason}"</p>
                          {edit.change_summary && <p className="text-slate-500 mt-0.5">{edit.change_summary}</p>}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Void button */}
                  {canVoid && (
                    <Button variant="destructive" className="w-full" onClick={() => setVoidOpen(true)} data-testid="sale-void-btn">
                      <Ban size={14} className="mr-2" /> Void Sale
                    </Button>
                  )}
                </>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center py-12"><div className="text-slate-400">Sale not found</div></div>
          )}
        </DialogContent>
      </Dialog>

      {/* Upload QR Dialog */}
      <UploadQRDialog
        open={uploadQROpen}
        onClose={(count) => { setUploadQROpen(false); if (count > 0) { toast.success(`${count} photo(s) uploaded`); onUpdated?.(); } }}
        recordType="invoice"
        recordId={sale?.id}
      />

      {/* View QR Dialog */}
      <ViewQRDialog open={viewQROpen} onClose={() => setViewQROpen(false)} recordType="invoice" recordId={sale?.id} />

      {/* Verify PIN Dialog */}
      <VerifyPinDialog
        open={verifyDialogOpen}
        onClose={() => setVerifyDialogOpen(false)}
        docType="invoice"
        docId={sale?.id}
        docLabel={saleNumber}
        onVerified={(result) => {
          setVerifyDialogOpen(false);
          setSale(prev => ({ ...prev, verified: true, verified_by_name: result.verified_by, verified_at: new Date().toISOString() }));
          onUpdated?.();
        }}
      />

      {/* Void dialog */}
      <Dialog open={voidOpen} onOpenChange={setVoidOpen}>
        <DialogContent className="sm:max-w-sm" data-testid="sale-void-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-600"><Ban size={18} /> Void Sale</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <Input placeholder="Reason for voiding" value={voidReason} onChange={e => setVoidReason(e.target.value)} data-testid="void-reason-input" />
            <Input type="password" placeholder="Manager/Admin PIN" value={voidPin} onChange={e => setVoidPin(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && voidReason && voidPin) handleVoid(); }} data-testid="void-pin-input" />
            <div className="flex gap-2">
              <Button variant="outline" className="flex-1" onClick={() => { setVoidOpen(false); setVoidReason(''); setVoidPin(''); }}>Cancel</Button>
              <Button variant="destructive" className="flex-1" onClick={handleVoid} disabled={!voidReason || !voidPin || actionLoading} data-testid="void-confirm-btn">
                {actionLoading ? 'Processing...' : 'Void Sale'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
