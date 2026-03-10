import { useState, useEffect } from 'react';
import { api, useAuth } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Separator } from './ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import { ScrollArea } from './ui/scroll-area';
import ReceiptGallery from './ReceiptGallery';
import {
  FileText, Truck, Receipt, ArrowLeftRight, ShieldCheck, Pencil, Ban,
  RotateCcw, Calendar, User, Building2, Loader2, Copy, Check,
  ImageIcon, Package, DollarSign, AlertTriangle, CheckCircle2
} from 'lucide-react';
import { toast } from 'sonner';

const STATUS_STYLES = {
  paid: 'bg-emerald-100 text-emerald-700', open: 'bg-blue-100 text-blue-700',
  partial: 'bg-amber-100 text-amber-700', voided: 'bg-red-100 text-red-700',
  received: 'bg-emerald-100 text-emerald-700', draft: 'bg-slate-100 text-slate-600',
  cancelled: 'bg-red-100 text-red-600', requested: 'bg-blue-100 text-blue-700',
};

function InfoRow({ label, value, icon: Icon, accent }) {
  if (!value && value !== 0) return null;
  return (
    <div className="flex items-start gap-2 py-1.5">
      {Icon && <Icon size={14} className="text-slate-400 mt-0.5 shrink-0" />}
      <span className="text-xs text-slate-500 w-28 shrink-0">{label}</span>
      <span className={`text-sm font-medium ${accent || 'text-slate-800'}`}>{value}</span>
    </div>
  );
}

function PinDialog({ open, onClose, onSubmit, title, loading }) {
  const [pin, setPin] = useState('');
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-sm" data-testid="pin-dialog">
        <DialogHeader><DialogTitle>{title}</DialogTitle></DialogHeader>
        <div className="space-y-3 py-2">
          <Input data-testid="pin-input" type="password" placeholder="Enter PIN" value={pin}
            onChange={e => setPin(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') onSubmit(pin); }} />
          <div className="flex gap-2">
            <Button variant="outline" className="flex-1" onClick={onClose}>Cancel</Button>
            <Button className="flex-1 bg-[#1A4D2E] hover:bg-[#154025]" onClick={() => onSubmit(pin)}
              disabled={!pin || loading} data-testid="pin-submit-btn">
              {loading ? <Loader2 size={16} className="animate-spin" /> : 'Confirm'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function VoidDialog({ open, onClose, onSubmit, loading }) {
  const [reason, setReason] = useState('');
  const [pin, setPin] = useState('');
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-sm" data-testid="void-dialog">
        <DialogHeader><DialogTitle className="flex items-center gap-2 text-red-600"><Ban size={18} /> Void Transaction</DialogTitle></DialogHeader>
        <div className="space-y-3 py-2">
          <Input placeholder="Reason for voiding" value={reason} onChange={e => setReason(e.target.value)} data-testid="void-reason-input" />
          <Input type="password" placeholder="Manager/Admin PIN" value={pin} onChange={e => setPin(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && reason && pin) onSubmit(reason, pin); }} data-testid="void-pin-input" />
          <div className="flex gap-2">
            <Button variant="outline" className="flex-1" onClick={onClose}>Cancel</Button>
            <Button variant="destructive" className="flex-1" onClick={() => onSubmit(reason, pin)}
              disabled={!reason || !pin || loading} data-testid="void-submit-btn">
              {loading ? <Loader2 size={16} className="animate-spin" /> : 'Void'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function TransactionDetailModal({ open, onOpenChange, transaction, onUpdated }) {
  const { hasPerm, user } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState('details');
  const [copied, setCopied] = useState(false);
  const [pinDialog, setPinDialog] = useState({ open: false, action: '', title: '' });
  const [voidDialog, setVoidDialog] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // Determine transaction type and ID
  const txType = transaction?.type;
  const txId = transaction?.id;
  const txNumber = transaction?.number || '';

  useEffect(() => {
    if (open && txId && txType) {
      loadDetail();
      setTab('details');
    } else {
      setData(null);
    }
  // eslint-disable-next-line
  }, [open, txId, txType]);

  const loadDetail = async () => {
    setLoading(true);
    try {
      if (txType === 'invoice') {
        const res = await api.get(`/invoices/${txId}`);
        setData({ ...res.data, _type: 'invoice' });
      } else if (txType === 'purchase_order') {
        const res = await api.get(`/purchase-orders/${txId}`);
        setData({ ...res.data, _type: 'purchase_order' });
      } else if (txType === 'expense') {
        const res = await api.get(`/expenses/${txId}`);
        setData({ ...res.data, _type: 'expense' });
      } else {
        setData({ ...transaction, _type: txType });
      }
    } catch (e) {
      toast.error('Failed to load transaction details');
      setData(null);
    }
    setLoading(false);
  };

  const copyNumber = async () => {
    try { await navigator.clipboard.writeText(txNumber); } catch { /* fallback */ }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // ── Permission checks ──────────────────────────────────────────────────
  const isAdmin = user?.role === 'admin';
  const canEdit = txType === 'invoice' && (isAdmin || hasPerm('pos', 'sell'));
  const canVoid = txType === 'invoice' && (isAdmin || hasPerm('pos', 'sell'));
  const canVerify = (txType === 'invoice' || txType === 'purchase_order' || txType === 'expense') && (isAdmin || hasPerm('reports', 'view'));
  const canReturn = txType === 'invoice' && data?.status !== 'voided' && (isAdmin || hasPerm('sales', 'view'));
  const canCancelPO = txType === 'purchase_order' && data?.status !== 'cancelled' && (isAdmin || hasPerm('purchase_orders', 'view'));
  const canDeleteExpense = txType === 'expense' && (isAdmin || hasPerm('accounting', 'view'));
  const isVerified = data?.verified === true;
  const isVoided = data?.status === 'voided' || data?.status === 'cancelled';

  // ── Actions ────────────────────────────────────────────────────────────
  const handleVerify = async (pin) => {
    setActionLoading(true);
    try {
      const docType = txType === 'invoice' ? 'invoice' : txType === 'purchase_order' ? 'purchase_order' : 'expense';
      await api.post(`/verify/${docType}/${txId}`, { pin });
      toast.success('Transaction verified');
      setPinDialog({ open: false, action: '', title: '' });
      loadDetail();
      onUpdated?.();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Verification failed');
    }
    setActionLoading(false);
  };

  const handleVoid = async (reason, pin) => {
    setActionLoading(true);
    try {
      if (txType === 'invoice') {
        await api.post(`/invoices/${txId}/void`, { reason, pin });
        toast.success('Invoice voided');
      } else if (txType === 'purchase_order') {
        await api.delete(`/purchase-orders/${txId}`);
        toast.success('PO cancelled');
      } else if (txType === 'expense') {
        await api.delete(`/expenses/${txId}`);
        toast.success('Expense deleted');
      }
      setVoidDialog(false);
      loadDetail();
      onUpdated?.();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Action failed');
    }
    setActionLoading(false);
  };

  // ── Record type for receipts ───────────────────────────────────────────
  const receiptRecordType = txType === 'invoice' ? 'invoice' : txType === 'purchase_order' ? 'purchase_order' : 'expense';

  // ── Render helpers ─────────────────────────────────────────────────────
  const renderInvoiceDetail = () => {
    if (!data) return null;
    const items = data.items || [];
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-x-6">
          <InfoRow label="Customer" value={data.customer_name} icon={User} />
          <InfoRow label="Payment" value={data.payment_type} icon={DollarSign} />
          <InfoRow label="Date" value={data.order_date || data.invoice_date} icon={Calendar} />
          <InfoRow label="Terms" value={data.terms || 'COD'} />
          <InfoRow label="Method" value={data.payment_method} />
          <InfoRow label="Fund Source" value={data.fund_source} />
          {data.digital_platform && <InfoRow label="Platform" value={data.digital_platform} />}
          {data.digital_ref_number && <InfoRow label="Ref #" value={data.digital_ref_number} />}
          <InfoRow label="Cashier" value={data.cashier_name} icon={User} />
          {data.sales_rep_name && <InfoRow label="Sales Rep" value={data.sales_rep_name} />}
        </div>
        <Separator />
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="text-xs">Item</TableHead>
              <TableHead className="text-xs text-right">Qty</TableHead>
              <TableHead className="text-xs text-right">Price</TableHead>
              <TableHead className="text-xs text-right">Total</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item, i) => (
              <TableRow key={i}>
                <TableCell className="text-sm">{item.product_name || item.description || 'Item'}</TableCell>
                <TableCell className="text-sm text-right">{item.quantity}</TableCell>
                <TableCell className="text-sm text-right">{formatPHP(item.rate || item.price || item.unit_price || 0)}</TableCell>
                <TableCell className="text-sm text-right font-medium">{formatPHP(item.total || item.line_total || 0)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <div className="space-y-1 pt-2 border-t">
          <div className="flex justify-between text-sm"><span className="text-slate-500">Subtotal</span><span>{formatPHP(data.subtotal || 0)}</span></div>
          {data.freight > 0 && <div className="flex justify-between text-sm"><span className="text-slate-500">Freight</span><span>{formatPHP(data.freight)}</span></div>}
          {data.overall_discount > 0 && <div className="flex justify-between text-sm"><span className="text-slate-500">Discount</span><span className="text-red-600">-{formatPHP(data.overall_discount)}</span></div>}
          <div className="flex justify-between text-base font-bold pt-1"><span>Grand Total</span><span>{formatPHP(data.grand_total || 0)}</span></div>
          <div className="flex justify-between text-sm"><span className="text-slate-500">Paid</span><span className="text-emerald-600">{formatPHP(data.amount_paid || 0)}</span></div>
          {data.balance > 0 && <div className="flex justify-between text-sm"><span className="text-slate-500">Balance</span><span className="text-red-600 font-semibold">{formatPHP(data.balance)}</span></div>}
        </div>
      </div>
    );
  };

  const renderPODetail = () => {
    if (!data) return null;
    const items = data.items || [];
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-x-6">
          <InfoRow label="Vendor" value={data.vendor} icon={Truck} />
          <InfoRow label="DR #" value={data.dr_number} />
          <InfoRow label="Date" value={data.purchase_date} icon={Calendar} />
          <InfoRow label="PO Type" value={data.po_type} />
          <InfoRow label="Payment" value={data.payment_status} icon={DollarSign} />
          <InfoRow label="Status" value={data.status} />
          {data.due_date && <InfoRow label="Due" value={data.due_date} />}
          <InfoRow label="Created by" value={data.created_by_name} icon={User} />
        </div>
        <Separator />
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="text-xs">Item</TableHead>
              <TableHead className="text-xs text-right">Qty</TableHead>
              <TableHead className="text-xs text-right">Unit Price</TableHead>
              <TableHead className="text-xs text-right">Total</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item, i) => (
              <TableRow key={i}>
                <TableCell className="text-sm">{item.product_name || item.description || 'Item'}</TableCell>
                <TableCell className="text-sm text-right">{item.quantity}</TableCell>
                <TableCell className="text-sm text-right">{formatPHP(item.unit_price || 0)}</TableCell>
                <TableCell className="text-sm text-right font-medium">{formatPHP(item.total || 0)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <div className="space-y-1 pt-2 border-t">
          <div className="flex justify-between text-sm"><span className="text-slate-500">Subtotal</span><span>{formatPHP(data.subtotal || data.line_subtotal || 0)}</span></div>
          {data.overall_discount_amount > 0 && <div className="flex justify-between text-sm"><span className="text-slate-500">Discount</span><span className="text-red-600">-{formatPHP(data.overall_discount_amount)}</span></div>}
          {data.freight > 0 && <div className="flex justify-between text-sm"><span className="text-slate-500">Freight</span><span>{formatPHP(data.freight)}</span></div>}
          {data.tax_amount > 0 && <div className="flex justify-between text-sm"><span className="text-slate-500">Tax</span><span>{formatPHP(data.tax_amount)}</span></div>}
          <div className="flex justify-between text-base font-bold pt-1"><span>Grand Total</span><span>{formatPHP(data.grand_total || 0)}</span></div>
          <div className="flex justify-between text-sm"><span className="text-slate-500">Paid</span><span className="text-emerald-600">{formatPHP(data.amount_paid || 0)}</span></div>
          {data.balance > 0 && <div className="flex justify-between text-sm"><span className="text-slate-500">Balance</span><span className="text-red-600 font-semibold">{formatPHP(data.balance)}</span></div>}
        </div>
      </div>
    );
  };

  const renderExpenseDetail = () => {
    if (!data) return null;
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-x-6">
          <InfoRow label="Category" value={data.category} icon={Receipt} />
          <InfoRow label="Amount" value={formatPHP(data.amount || 0)} icon={DollarSign} accent="text-red-600 font-bold" />
          <InfoRow label="Date" value={data.date} icon={Calendar} />
          <InfoRow label="Fund Source" value={data.fund_source || 'cashier'} />
          {data.vendor_name && <InfoRow label="Vendor" value={data.vendor_name} />}
          {data.reference_number && <InfoRow label="Ref #" value={data.reference_number} />}
          {data.customer_name && <InfoRow label="Customer" value={data.customer_name} icon={User} />}
          {data.employee_name && <InfoRow label="Employee" value={data.employee_name} icon={User} />}
          <InfoRow label="Created by" value={data.created_by_name} icon={User} />
        </div>
        {data.description && (
          <>
            <Separator />
            <div>
              <p className="text-xs text-slate-500 mb-1">Description</p>
              <p className="text-sm text-slate-800">{data.description}</p>
            </div>
          </>
        )}
      </div>
    );
  };

  const renderOtherDetail = () => {
    if (!data) return null;
    return (
      <div className="space-y-3">
        <InfoRow label="Type" value={transaction?.sub_type} />
        <InfoRow label="Date" value={transaction?.date} icon={Calendar} />
        <InfoRow label="Amount" value={formatPHP(transaction?.amount || 0)} icon={DollarSign} />
        <InfoRow label="Title" value={transaction?.title} />
      </div>
    );
  };

  const typeConfig = {
    invoice: { label: 'Invoice / Sale', icon: FileText, color: 'text-blue-600', render: renderInvoiceDetail },
    purchase_order: { label: 'Purchase Order', icon: Truck, color: 'text-amber-600', render: renderPODetail },
    expense: { label: 'Expense', icon: Receipt, color: 'text-red-600', render: renderExpenseDetail },
    internal_invoice: { label: 'Internal Invoice', icon: ArrowLeftRight, color: 'text-purple-600', render: renderOtherDetail },
    fund_transfer: { label: 'Fund Transfer', icon: Package, color: 'text-emerald-600', render: renderOtherDetail },
  };

  const cfg = typeConfig[txType] || typeConfig.invoice;
  const TypeIcon = cfg.icon;

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh] flex flex-col" data-testid="transaction-detail-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <TypeIcon size={20} className={cfg.color} />
              <span className={cfg.color}>{cfg.label}</span>
            </DialogTitle>
          </DialogHeader>

          {/* Reference number header */}
          <div className="flex items-center justify-between bg-slate-50 border border-dashed border-slate-300 rounded-lg px-4 py-2.5">
            <div>
              <p className="font-mono text-lg font-bold text-slate-800" data-testid="detail-reference-number">{txNumber || 'No Number'}</p>
              {data && (
                <div className="flex items-center gap-2 mt-0.5">
                  <Badge className={`text-[10px] ${STATUS_STYLES[data.status] || 'bg-slate-100 text-slate-600'}`}>
                    {data.status || 'N/A'}
                  </Badge>
                  {isVerified && (
                    <Badge className="text-[10px] bg-emerald-100 text-emerald-700">
                      <CheckCircle2 size={10} className="mr-1" /> Verified
                    </Badge>
                  )}
                  {data.verified === false && (
                    <Badge className="text-[10px] bg-amber-100 text-amber-700">
                      <AlertTriangle size={10} className="mr-1" /> Unverified
                    </Badge>
                  )}
                </div>
              )}
            </div>
            <Button variant="ghost" size="sm" onClick={copyNumber} data-testid="detail-copy-btn">
              {copied ? <Check size={14} className="text-green-600" /> : <Copy size={14} />}
            </Button>
          </div>

          {/* Tabs: Details / Receipts / Actions */}
          <Tabs value={tab} onValueChange={setTab} className="flex-1 min-h-0">
            <TabsList className="w-full">
              <TabsTrigger value="details" className="flex-1" data-testid="tab-details">Details</TabsTrigger>
              {(txType === 'invoice' || txType === 'purchase_order' || txType === 'expense') && (
                <TabsTrigger value="receipts" className="flex-1" data-testid="tab-receipts">
                  <ImageIcon size={14} className="mr-1" /> Receipts
                </TabsTrigger>
              )}
              <TabsTrigger value="actions" className="flex-1" data-testid="tab-actions">Actions</TabsTrigger>
            </TabsList>

            <ScrollArea className="flex-1 max-h-[50vh] mt-3">
              <TabsContent value="details" className="mt-0 px-1">
                {loading ? (
                  <div className="flex justify-center py-12"><Loader2 size={28} className="animate-spin text-slate-400" /></div>
                ) : data ? (
                  cfg.render()
                ) : (
                  <p className="text-center text-slate-400 py-8">Failed to load details</p>
                )}
              </TabsContent>

              <TabsContent value="receipts" className="mt-0 px-1">
                {data?.id ? (
                  <ReceiptGallery recordType={receiptRecordType} recordId={data.id} />
                ) : (
                  <p className="text-center text-slate-400 py-8">No receipt data available</p>
                )}
              </TabsContent>

              <TabsContent value="actions" className="mt-0 px-1">
                {isVoided ? (
                  <div className="text-center py-8">
                    <Ban size={32} className="mx-auto text-red-300 mb-2" />
                    <p className="text-red-500 font-medium">This transaction has been voided/cancelled</p>
                    <p className="text-sm text-slate-400 mt-1">No further actions available</p>
                  </div>
                ) : (
                  <div className="space-y-2 py-2" data-testid="action-buttons">
                    {/* Verify */}
                    {canVerify && !isVerified && (
                      <Button
                        data-testid="action-verify"
                        className="w-full justify-start gap-3 h-12 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200"
                        variant="ghost"
                        onClick={() => setPinDialog({ open: true, action: 'verify', title: 'Verify Transaction — Enter PIN' })}
                      >
                        <ShieldCheck size={18} /> Verify Transaction
                        <span className="ml-auto text-xs text-slate-400">Requires PIN</span>
                      </Button>
                    )}
                    {isVerified && (
                      <div className="flex items-center gap-2 px-4 py-3 bg-emerald-50 border border-emerald-200 rounded-lg">
                        <CheckCircle2 size={18} className="text-emerald-600" />
                        <div>
                          <p className="text-sm font-medium text-emerald-700">Verified</p>
                          <p className="text-xs text-emerald-600">
                            by {data?.verified_by_name || 'Admin'} {data?.verified_at ? `on ${data.verified_at.slice(0, 10)}` : ''}
                          </p>
                        </div>
                      </div>
                    )}

                    {/* Edit (invoices only) */}
                    {canEdit && data?.status !== 'voided' && txType === 'invoice' && (
                      <Button
                        data-testid="action-edit"
                        className="w-full justify-start gap-3 h-12 bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200"
                        variant="ghost"
                        onClick={() => {
                          onOpenChange(false);
                          // Open the InvoiceDetailModal in edit mode by navigating to sales
                          window.dispatchEvent(new CustomEvent('open-invoice-edit', { detail: { invoiceId: txId, invoiceNumber: txNumber } }));
                        }}
                      >
                        <Pencil size={18} /> Edit Invoice
                      </Button>
                    )}

                    {/* Void */}
                    {canVoid && txType === 'invoice' && data?.status !== 'voided' && (
                      <Button
                        data-testid="action-void"
                        className="w-full justify-start gap-3 h-12 bg-red-50 text-red-700 hover:bg-red-100 border border-red-200"
                        variant="ghost"
                        onClick={() => setVoidDialog(true)}
                      >
                        <Ban size={18} /> Void Invoice
                        <span className="ml-auto text-xs text-slate-400">Requires PIN + Reason</span>
                      </Button>
                    )}

                    {/* Cancel PO */}
                    {canCancelPO && (
                      <Button
                        data-testid="action-cancel-po"
                        className="w-full justify-start gap-3 h-12 bg-red-50 text-red-700 hover:bg-red-100 border border-red-200"
                        variant="ghost"
                        onClick={() => setVoidDialog(true)}
                      >
                        <Ban size={18} /> Cancel Purchase Order
                      </Button>
                    )}

                    {/* Delete Expense */}
                    {canDeleteExpense && (
                      <Button
                        data-testid="action-delete-expense"
                        className="w-full justify-start gap-3 h-12 bg-red-50 text-red-700 hover:bg-red-100 border border-red-200"
                        variant="ghost"
                        onClick={() => setVoidDialog(true)}
                      >
                        <Ban size={18} /> Delete Expense
                      </Button>
                    )}

                    {/* Return/Refund (invoices only) */}
                    {canReturn && (
                      <Button
                        data-testid="action-return"
                        className="w-full justify-start gap-3 h-12 bg-amber-50 text-amber-700 hover:bg-amber-100 border border-amber-200"
                        variant="ghost"
                        onClick={() => {
                          onOpenChange(false);
                          window.location.href = '/returns';
                        }}
                      >
                        <RotateCcw size={18} /> Return / Refund
                      </Button>
                    )}

                    {(!canVerify && !canEdit && !canVoid && !canReturn && !canCancelPO && !canDeleteExpense) && (
                      <div className="text-center py-8">
                        <p className="text-slate-400 text-sm">No actions available with your current permissions</p>
                      </div>
                    )}
                  </div>
                )}
              </TabsContent>
            </ScrollArea>
          </Tabs>
        </DialogContent>
      </Dialog>

      {/* PIN Dialog for Verify */}
      <PinDialog
        open={pinDialog.open}
        onClose={() => setPinDialog({ open: false, action: '', title: '' })}
        onSubmit={handleVerify}
        title={pinDialog.title}
        loading={actionLoading}
      />

      {/* Void/Cancel/Delete Dialog */}
      <VoidDialog
        open={voidDialog}
        onClose={() => setVoidDialog(false)}
        onSubmit={handleVoid}
        loading={actionLoading}
      />
    </>
  );
}
