import { useState, useEffect } from 'react';
import { api } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Textarea } from './ui/textarea';
import { Separator } from './ui/separator';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { ScrollArea } from './ui/scroll-area';
import { Card, CardContent } from './ui/card';
import { 
  FileText, Edit3, History, Save, X, AlertTriangle, Package, 
  User, Calendar, DollarSign, Trash2, Plus, Clock, CheckCircle2
} from 'lucide-react';
import { toast } from 'sonner';

export default function InvoiceDetailModal({ 
  open, 
  onOpenChange, 
  invoiceId, 
  invoiceNumber,
  onUpdated 
}) {
  const [invoice, setInvoice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editMode, setEditMode] = useState(false);
  const [editHistory, setEditHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);
  const [saving, setSaving] = useState(false);
  
  // Edit form state
  const [editData, setEditData] = useState({
    items: [],
    customer_name: '',
    notes: '',
    freight: 0,
    overall_discount: 0,
  });
  const [editReason, setEditReason] = useState('');
  const [proofFile, setProofFile] = useState(null);

  useEffect(() => {
    if (open && (invoiceId || invoiceNumber)) {
      loadInvoice();
    }
  }, [open, invoiceId, invoiceNumber]);

  const loadInvoice = async () => {
    setLoading(true);
    try {
      let res;
      if (invoiceId) {
        res = await api.get(`/invoices/${invoiceId}`);
      } else {
        res = await api.get(`/invoices/by-number/${encodeURIComponent(invoiceNumber)}`);
      }
      setInvoice(res.data);
      setEditData({
        items: JSON.parse(JSON.stringify(res.data.items || [])),
        customer_name: res.data.customer_name || '',
        notes: res.data.notes || '',
        freight: res.data.freight || 0,
        overall_discount: res.data.overall_discount || 0,
      });
      setEditHistory(res.data.edit_history || []);
    } catch (e) {
      toast.error('Failed to load invoice');
      onOpenChange(false);
    }
    setLoading(false);
  };

  const loadEditHistory = async () => {
    if (!invoice?.id) return;
    try {
      const res = await api.get(`/invoices/${invoice.id}/edit-history`);
      setEditHistory(res.data);
      setShowHistory(true);
    } catch (e) {
      toast.error('Failed to load edit history');
    }
  };

  const handleItemChange = (index, field, value) => {
    const newItems = [...editData.items];
    newItems[index] = { ...newItems[index], [field]: value };
    
    // Recalculate line total
    const item = newItems[index];
    const qty = parseFloat(item.quantity) || 0;
    const rate = parseFloat(item.rate) || 0;
    const discVal = parseFloat(item.discount_value) || 0;
    const discType = item.discount_type || 'amount';
    const discAmt = discType === 'percent' ? qty * rate * discVal / 100 : discVal;
    newItems[index].total = Math.round((qty * rate - discAmt) * 100) / 100;
    
    setEditData({ ...editData, items: newItems });
  };

  const removeItem = (index) => {
    const newItems = editData.items.filter((_, i) => i !== index);
    setEditData({ ...editData, items: newItems });
  };

  const calculateTotals = () => {
    const subtotal = editData.items.reduce((sum, item) => sum + (item.total || 0), 0);
    const grandTotal = subtotal + (editData.freight || 0) - (editData.overall_discount || 0);
    return { subtotal, grandTotal };
  };

  const handleSave = async () => {
    if (!editReason.trim()) {
      toast.error('Please provide a reason for the edit');
      return;
    }

    setSaving(true);
    try {
      const res = await api.put(`/invoices/${invoice.id}/edit`, {
        ...editData,
        reason: editReason,
        proof_url: proofFile ? proofFile.name : null,
        _collection: invoice._collection || 'invoices',
      });
      
      toast.success(res.data.message);
      if (res.data.changes?.length > 0) {
        toast(`Changes: ${res.data.changes.slice(0, 2).join(', ')}${res.data.changes.length > 2 ? '...' : ''}`);
      }
      
      setEditMode(false);
      setEditReason('');
      setProofFile(null);
      loadInvoice();
      
      if (onUpdated) onUpdated();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to save changes');
    }
    setSaving(false);
  };

  const getInvoiceTypeInfo = () => {
    if (!invoice) return { label: 'Invoice', color: 'bg-blue-100 text-blue-700' };
    const saleType = invoice.sale_type || invoice._collection;
    switch (saleType) {
      case 'interest_charge': return { label: 'Interest Charge', color: 'bg-amber-100 text-amber-700' };
      case 'penalty_charge': return { label: 'Penalty Charge', color: 'bg-red-100 text-red-700' };
      case 'farm_expense': return { label: 'Farm Expense', color: 'bg-green-100 text-green-700' };
      case 'cash_advance': return { label: 'Customer Cash Out', color: 'bg-purple-100 text-purple-700' };
      case 'purchase_orders': return { label: 'Purchase Order', color: 'bg-purple-100 text-purple-700' };
      case 'sales': return { label: 'POS Sale', color: 'bg-blue-100 text-blue-700' };
      default: return { label: 'Sales Invoice', color: 'bg-blue-100 text-blue-700' };
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      paid: 'bg-emerald-100 text-emerald-700',
      partial: 'bg-amber-100 text-amber-700',
      open: 'bg-red-100 text-red-700',
      received: 'bg-emerald-100 text-emerald-700',
      pending: 'bg-slate-100 text-slate-600',
      voided: 'bg-slate-200 text-slate-500',
    };
    return <Badge className={`text-xs ${styles[status] || styles.pending}`}>{status}</Badge>;
  };

  const typeInfo = getInvoiceTypeInfo();
  const { subtotal, grandTotal } = calculateTotals();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-4xl max-h-[90vh] flex flex-col p-0">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="text-slate-400">Loading invoice...</div>
          </div>
        ) : invoice ? (
          <>
            {/* Header */}
            <div className="px-6 py-4 border-b border-slate-100">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-xl font-bold" style={{ fontFamily: 'Manrope' }}>
                      {invoice.invoice_number || invoice.sale_number || invoice.po_number}
                    </h2>
                    <Badge className={`text-xs ${typeInfo.color}`}>{typeInfo.label}</Badge>
                    {getStatusBadge(invoice.status)}
                    {invoice.edited && (
                      <Badge 
                        className="text-xs bg-orange-100 text-orange-700 cursor-pointer hover:bg-orange-200"
                        onClick={loadEditHistory}
                      >
                        <Edit3 size={10} className="mr-1" /> 
                        Edited {invoice.edit_count > 1 ? `(${invoice.edit_count}x)` : ''}
                      </Badge>
                    )}
                  </div>
                  <p className="text-sm text-slate-500 mt-1">
                    {invoice.customer_name || invoice.vendor || 'Walk-in'} · {invoice.order_date || invoice.created_at?.slice(0, 10)}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {!editMode && invoice.status !== 'voided' && (
                    <Button variant="outline" size="sm" onClick={() => setEditMode(true)}>
                      <Edit3 size={14} className="mr-1" /> Edit
                    </Button>
                  )}
                  {invoice.edit_count > 0 && (
                    <Button variant="ghost" size="sm" onClick={loadEditHistory}>
                      <History size={14} className="mr-1" /> History ({invoice.edit_count})
                    </Button>
                  )}
                </div>
              </div>
            </div>

            {/* Content */}
            <ScrollArea className="flex-1 px-6 py-4">
              {showHistory ? (
                // Edit History View
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold flex items-center gap-2">
                      <History size={16} /> Edit History
                    </h3>
                    <Button variant="ghost" size="sm" onClick={() => setShowHistory(false)}>
                      <X size={14} className="mr-1" /> Close
                    </Button>
                  </div>
                  
                  {editHistory.length === 0 ? (
                    <p className="text-slate-400 text-center py-8">No edit history</p>
                  ) : (
                    <div className="space-y-3">
                      {editHistory.map((edit, i) => (
                        <Card key={edit.id} className="border-slate-200">
                          <CardContent className="p-4">
                            <div className="flex items-start justify-between mb-2">
                              <div>
                                <p className="font-medium text-sm">{edit.edited_by_name}</p>
                                <p className="text-xs text-slate-400">
                                  <Clock size={10} className="inline mr-1" />
                                  {new Date(edit.edited_at).toLocaleString()}
                                </p>
                              </div>
                              {edit.proof_url && (
                                <Badge variant="outline" className="text-xs">Has Proof</Badge>
                              )}
                            </div>
                            <div className="bg-slate-50 rounded-lg p-3 mb-2">
                              <p className="text-sm font-medium text-slate-700">Reason:</p>
                              <p className="text-sm text-slate-600">{edit.reason}</p>
                            </div>
                            {edit.changes?.length > 0 && (
                              <div>
                                <p className="text-xs font-medium text-slate-500 mb-1">Changes:</p>
                                <ul className="text-xs text-slate-600 space-y-0.5">
                                  {edit.changes.map((change, j) => (
                                    <li key={j} className="flex items-start gap-1">
                                      <span className="text-slate-400">•</span> {change}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            {edit.inventory_adjustments?.length > 0 && (
                              <div className="mt-2 pt-2 border-t border-slate-100">
                                <p className="text-xs font-medium text-amber-600 mb-1">Inventory Changes:</p>
                                <ul className="text-xs text-amber-700 space-y-0.5">
                                  {edit.inventory_adjustments.map((adj, j) => (
                                    <li key={j}>
                                      {adj.change > 0 ? '+' : ''}{adj.change} - {adj.reason}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                // Invoice Detail/Edit View
                <div className="space-y-6">
                  {/* Customer/Vendor Info */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <Label className="text-xs text-slate-500">Customer/Vendor</Label>
                      {editMode ? (
                        <Input 
                          value={editData.customer_name} 
                          onChange={e => setEditData({...editData, customer_name: e.target.value})}
                          className="h-9"
                        />
                      ) : (
                        <p className="font-medium">{invoice.customer_name || invoice.vendor || '—'}</p>
                      )}
                    </div>
                    <div>
                      <Label className="text-xs text-slate-500">Date</Label>
                      <p className="font-medium">{invoice.order_date || invoice.po_date || invoice.created_at?.slice(0, 10)}</p>
                    </div>
                    <div>
                      <Label className="text-xs text-slate-500">Due Date</Label>
                      <p className="font-medium">{invoice.due_date || '—'}</p>
                    </div>
                    <div>
                      <Label className="text-xs text-slate-500">Terms</Label>
                      <p className="font-medium">{invoice.terms || 'COD'}</p>
                    </div>
                  </div>

                  <Separator />

                  {/* Items Table */}
                  <div>
                    <Label className="text-xs text-slate-500 uppercase mb-2 block">Line Items</Label>
                    <div className="border border-slate-200 rounded-lg overflow-hidden">
                      <Table>
                        <TableHeader>
                          <TableRow className="bg-slate-50">
                            <TableHead className="text-xs w-8">#</TableHead>
                            <TableHead className="text-xs">Product</TableHead>
                            <TableHead className="text-xs text-right w-20">Qty</TableHead>
                            <TableHead className="text-xs text-right w-28">Rate</TableHead>
                            <TableHead className="text-xs text-right w-24">Discount</TableHead>
                            <TableHead className="text-xs text-right w-28">Amount</TableHead>
                            {editMode && <TableHead className="w-10"></TableHead>}
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {(editMode ? editData.items : invoice.items || []).map((item, i) => (
                            <TableRow key={i}>
                              <TableCell className="text-xs text-slate-400">{i + 1}</TableCell>
                              <TableCell>
                                <p className="font-medium text-sm">{item.product_name}</p>
                                {item.description && <p className="text-xs text-slate-400">{item.description}</p>}
                              </TableCell>
                              <TableCell className="text-right">
                                {editMode ? (
                                  <Input 
                                    type="number" 
                                    value={item.quantity} 
                                    onChange={e => handleItemChange(i, 'quantity', parseFloat(e.target.value) || 0)}
                                    className="h-8 w-16 text-right"
                                  />
                                ) : (
                                  <span className="text-sm">{item.quantity}</span>
                                )}
                              </TableCell>
                              <TableCell className="text-right">
                                {editMode ? (
                                  <Input 
                                    type="number" 
                                    value={item.rate} 
                                    onChange={e => handleItemChange(i, 'rate', parseFloat(e.target.value) || 0)}
                                    className="h-8 w-24 text-right"
                                  />
                                ) : (
                                  <span className="text-sm">{formatPHP(item.rate)}</span>
                                )}
                              </TableCell>
                              <TableCell className="text-right text-sm text-slate-500">
                                {item.discount_amount > 0 ? formatPHP(item.discount_amount) : '—'}
                              </TableCell>
                              <TableCell className="text-right font-medium text-sm">
                                {formatPHP(item.total)}
                              </TableCell>
                              {editMode && (
                                <TableCell>
                                  <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-red-500" onClick={() => removeItem(i)}>
                                    <Trash2 size={12} />
                                  </Button>
                                </TableCell>
                              )}
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  </div>

                  {/* Totals */}
                  <div className="flex justify-end">
                    <div className="w-64 space-y-2">
                      <div className="flex justify-between text-sm">
                        <span className="text-slate-500">Subtotal</span>
                        <span>{formatPHP(editMode ? subtotal : invoice.subtotal)}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-slate-500">Freight</span>
                        {editMode ? (
                          <Input 
                            type="number" 
                            value={editData.freight} 
                            onChange={e => setEditData({...editData, freight: parseFloat(e.target.value) || 0})}
                            className="h-7 w-24 text-right"
                          />
                        ) : (
                          <span>{formatPHP(invoice.freight || 0)}</span>
                        )}
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-slate-500">Discount</span>
                        {editMode ? (
                          <Input 
                            type="number" 
                            value={editData.overall_discount} 
                            onChange={e => setEditData({...editData, overall_discount: parseFloat(e.target.value) || 0})}
                            className="h-7 w-24 text-right"
                          />
                        ) : (
                          <span>{formatPHP(invoice.overall_discount || 0)}</span>
                        )}
                      </div>
                      <Separator />
                      <div className="flex justify-between font-bold">
                        <span>Grand Total</span>
                        <span className="text-lg">{formatPHP(editMode ? grandTotal : invoice.grand_total)}</span>
                      </div>
                      {invoice.amount_paid > 0 && (
                        <>
                          <div className="flex justify-between text-sm text-emerald-600">
                            <span>Amount Paid</span>
                            <span>{formatPHP(invoice.amount_paid)}</span>
                          </div>
                          <div className="flex justify-between text-sm text-red-600 font-medium">
                            <span>Balance Due</span>
                            <span>{formatPHP(invoice.balance || 0)}</span>
                          </div>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Notes */}
                  <div>
                    <Label className="text-xs text-slate-500">Notes</Label>
                    {editMode ? (
                      <Textarea 
                        value={editData.notes} 
                        onChange={e => setEditData({...editData, notes: e.target.value})}
                        placeholder="Add notes..."
                        rows={2}
                      />
                    ) : (
                      <p className="text-sm text-slate-600">{invoice.notes || '—'}</p>
                    )}
                  </div>

                  {/* Edit Reason (only in edit mode) */}
                  {editMode && (
                    <Card className="border-amber-200 bg-amber-50">
                      <CardContent className="p-4">
                        <div className="flex items-start gap-2 mb-3">
                          <AlertTriangle size={16} className="text-amber-600 mt-0.5" />
                          <div>
                            <p className="font-medium text-amber-800">Edit Reason Required</p>
                            <p className="text-xs text-amber-600">Please explain why this invoice needs to be edited.</p>
                          </div>
                        </div>
                        <Textarea 
                          value={editReason} 
                          onChange={e => setEditReason(e.target.value)}
                          placeholder="e.g., Customer requested correction, Wrong product entered, Price adjustment approved by manager..."
                          rows={2}
                          className="bg-white"
                        />
                        <div className="mt-2">
                          <Label className="text-xs text-amber-700">Proof/Attachment (optional)</Label>
                          <Input 
                            type="file" 
                            onChange={e => setProofFile(e.target.files?.[0] || null)}
                            className="h-9 bg-white"
                          />
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Footer info */}
                  <div className="text-xs text-slate-400 space-y-1">
                    <p>Created: {new Date(invoice.created_at).toLocaleString()} by {invoice.cashier_name || invoice.created_by_name || '—'}</p>
                    {invoice.edited && (
                      <p>Last edited: {new Date(invoice.last_edited_at).toLocaleString()} by {invoice.last_edited_by}</p>
                    )}
                  </div>
                </div>
              )}
            </ScrollArea>

            {/* Footer Actions */}
            {editMode && !showHistory && (
              <div className="px-6 py-4 border-t border-slate-100 flex justify-end gap-2">
                <Button variant="outline" onClick={() => { setEditMode(false); setEditReason(''); loadInvoice(); }}>
                  Cancel
                </Button>
                <Button 
                  onClick={handleSave} 
                  disabled={saving || !editReason.trim()}
                  className="bg-[#1A4D2E] hover:bg-[#14532d] text-white"
                >
                  {saving ? 'Saving...' : (
                    <>
                      <Save size={14} className="mr-2" /> Save Changes
                    </>
                  )}
                </Button>
              </div>
            )}
          </>
        ) : (
          <div className="flex items-center justify-center py-20">
            <div className="text-slate-400">Invoice not found</div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
