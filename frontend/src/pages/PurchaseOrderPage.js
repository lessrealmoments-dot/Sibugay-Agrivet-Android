import { useState, useEffect, useRef } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import SmartProductSearch from '../components/SmartProductSearch';
import { FileText, Plus, Trash2, Save, Truck, Check, X, DollarSign, Search, History, ArrowRight, Receipt, UserPlus } from 'lucide-react';
import { toast } from 'sonner';

const EMPTY_LINE = { product_id: '', product_name: '', description: '', quantity: 1, unit_price: 0 };

export default function PurchaseOrderPage() {
  const { currentBranch } = useAuth();
  const [tab, setTab] = useState('create');
  const [orders, setOrders] = useState([]);
  const [totalOrders, setTotalOrders] = useState(0);
  const [prefixes, setPrefixes] = useState({});
  const [header, setHeader] = useState({
    vendor: '', branch_id: '', purchase_date: new Date().toISOString().slice(0, 10),
    notes: '', status: 'ordered', payment_method: 'cash', po_number: '',
    terms_days: 0, due_date: '',
  });
  const [lines, setLines] = useState([{ ...EMPTY_LINE }]);
  const [saving, setSaving] = useState(false);
  const [payDialog, setPayDialog] = useState(false);
  const [selectedPO, setSelectedPO] = useState(null);
  const [payForm, setPayForm] = useState({ amount: 0, reference: '' });
  const [detailDialog, setDetailDialog] = useState(false);
  const [detailPO, setDetailPO] = useState(null);
  const [createProductDialog, setCreateProductDialog] = useState(false);
  const [newProductForm, setNewProductForm] = useState({ sku: '', name: '', category: 'Pesticide', unit: 'Box', cost_price: 0, prices: {}, product_type: 'stockable' });
  const [schemes, setSchemes] = useState([]);
  const qtyRefs = useRef([]);
  // Pay Supplier state
  const [vendors, setVendors] = useState([]);
  const [payVendor, setPayVendor] = useState('');
  const [vendorSearch, setVendorSearch] = useState('');
  const [vendorPOs, setVendorPOs] = useState([]);
  const [paySupForm, setPaySupForm] = useState({ amount: 0, check_number: '', payment_date: new Date().toISOString().slice(0, 10), check_date: '', selected_po: '' });
  // Supplier History state
  const [historyDialog, setHistoryDialog] = useState(false);
  const [historyVendor, setHistoryVendor] = useState('');
  const [historyPOs, setHistoryPOs] = useState([]);
  // Supplier search state
  const [supplierSearch, setSupplierSearch] = useState('');
  const [supplierResults, setSupplierResults] = useState([]);
  const [showSupplierDropdown, setShowSupplierDropdown] = useState(false);
  const [suppliers, setSuppliers] = useState([]);
  const supplierSearchRef = useRef(null);

  useEffect(() => {
    api.get('/settings/invoice-prefixes').then(r => setPrefixes(r.data)).catch(() => {});
    api.get('/price-schemes').then(r => setSchemes(r.data)).catch(() => {});
    api.get('/purchase-orders/vendors').then(r => setVendors(r.data)).catch(() => {});
    api.get('/suppliers').then(r => setSuppliers(r.data)).catch(() => {});
    fetchOrders();
  }, [currentBranch]);

  // Supplier search effect
  useEffect(() => {
    if (supplierSearch.length > 0) {
      const allNames = [...new Set([...vendors, ...suppliers.map(s => s.name)])];
      const filtered = allNames.filter(n => n.toLowerCase().includes(supplierSearch.toLowerCase()));
      setSupplierResults(filtered.slice(0, 8));
      setShowSupplierDropdown(true);
    } else {
      setSupplierResults([]);
      setShowSupplierDropdown(false);
    }
  }, [supplierSearch, vendors, suppliers]);

  // Click outside handler for supplier dropdown
  useEffect(() => {
    const handleClick = (e) => {
      if (supplierSearchRef.current && !supplierSearchRef.current.contains(e.target)) {
        setShowSupplierDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const selectSupplier = (name) => {
    setHeader(h => ({ ...h, vendor: name }));
    setSupplierSearch(name);
    setShowSupplierDropdown(false);
  };

  const quickCreateSupplier = async () => {
    if (!supplierSearch.trim()) return;
    try {
      await api.post('/suppliers', { name: supplierSearch.trim() });
      toast.success(`Supplier "${supplierSearch}" created`);
      setHeader(h => ({ ...h, vendor: supplierSearch.trim() }));
      setShowSupplierDropdown(false);
      // Refresh suppliers list
      const res = await api.get('/suppliers');
      setSuppliers(res.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to create supplier');
    }
  };

  const fetchOrders = async () => {
    try {
      const res = await api.get('/purchase-orders', { params: { limit: 100 } });
      setOrders(res.data.purchase_orders);
      setTotalOrders(res.data.total);
    } catch {}
  };

  const selectPayVendor = async (vendor) => {
    setPayVendor(vendor);
    setVendorSearch(vendor);
    try {
      const res = await api.get('/purchase-orders/by-vendor', { params: { vendor } });
      setVendorPOs(res.data.filter(p => p.payment_status !== 'paid'));
    } catch { setVendorPOs([]); }
  };

  const handlePaySupplier = async () => {
    if (!paySupForm.selected_po) { toast.error('Select a PO to pay'); return; }
    if (!paySupForm.amount || paySupForm.amount <= 0) { toast.error('Enter amount'); return; }
    try {
      await api.post(`/purchase-orders/${paySupForm.selected_po}/pay`, {
        amount: paySupForm.amount, check_number: paySupForm.check_number,
        payment_date: paySupForm.payment_date, check_date: paySupForm.check_date,
      });
      toast.success('Supplier payment recorded! Deducted from Cashier Drawer.');
      selectPayVendor(payVendor);
      fetchOrders();
      setPaySupForm(f => ({ ...f, amount: 0, check_number: '', selected_po: '' }));
      api.get('/purchase-orders/vendors').then(r => setVendors(r.data)).catch(() => {});
    } catch (e) { toast.error(e.response?.data?.detail || 'Payment failed'); }
  };

  const openSupplierHistory = async (vendor) => {
    setHistoryVendor(vendor);
    try {
      const res = await api.get('/purchase-orders/by-vendor', { params: { vendor } });
      setHistoryPOs(res.data);
      setHistoryDialog(true);
    } catch { setHistoryPOs([]); }
  };

  const filteredVendors = vendorSearch ? vendors.filter(v => v.toLowerCase().includes(vendorSearch.toLowerCase())) : vendors;

  const handleCreateNewProduct = (name) => {
    setNewProductForm({ sku: '', name, category: 'Pesticide', unit: 'Box', cost_price: 0, prices: {}, product_type: 'stockable' });
    setCreateProductDialog(true);
  };

  const saveNewProduct = async () => {
    try {
      const res = await api.post('/products', newProductForm);
      toast.success(`Product "${res.data.name}" created!`);
      setCreateProductDialog(false);
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  const handleProductSelect = (index, product) => {
    const newLines = [...lines];
    newLines[index] = {
      ...newLines[index],
      product_id: product.id, product_name: product.name,
      description: product.description || '', unit_price: product.cost_price || 0,
    };
    if (index === lines.length - 1) newLines.push({ ...EMPTY_LINE });
    setLines(newLines);
    setTimeout(() => qtyRefs.current[index]?.focus(), 50);
  };

  const updateLine = (index, field, value) => {
    const newLines = [...lines];
    newLines[index] = { ...newLines[index], [field]: value };
    setLines(newLines);
  };

  const removeLine = (index) => {
    if (lines.length <= 1) return;
    setLines(lines.filter((_, i) => i !== index));
  };

  const subtotal = lines.reduce((s, l) => s + (l.quantity * l.unit_price), 0);

  const handleSave = async () => {
    const validLines = lines.filter(l => l.product_id);
    if (!validLines.length) { toast.error('Add at least one product'); return; }
    if (!header.vendor) { toast.error('Enter vendor name'); return; }
    if (!currentBranch) { toast.error('Select a branch'); return; }
    setSaving(true);
    try {
      const data = { ...header, branch_id: currentBranch.id, items: validLines };
      const res = await api.post('/purchase-orders', data);
      toast.success(`PO ${res.data.po_number} created!`);
      setLines([{ ...EMPTY_LINE }]);
      setHeader({ vendor: '', branch_id: '', purchase_date: new Date().toISOString().slice(0, 10), notes: '', status: 'ordered', payment_method: 'cash', po_number: '' });
      fetchOrders();
      setTab('list');
    } catch (e) { toast.error(e.response?.data?.detail || 'Error creating PO'); }
    setSaving(false);
  };

  const receivePO = async (poId) => {
    if (!window.confirm('Mark as received? This will add items to inventory.')) return;
    try {
      await api.post(`/purchase-orders/${poId}/receive`);
      toast.success('PO received! Inventory updated.');
      fetchOrders();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  const cancelPO = async (poId) => {
    if (!window.confirm('Cancel this PO?')) return;
    try {
      await api.delete(`/purchase-orders/${poId}`);
      toast.success('PO cancelled');
      fetchOrders();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  const reopenPO = async (po) => {
    if (!window.confirm(`Reopen PO ${po.po_number}? This will reverse the inventory addition (stock will temporarily go negative until you receive again). Continue?`)) return;
    try {
      const res = await api.post(`/purchase-orders/${po.id}/reopen`);
      toast.success(res.data.message);
      fetchOrders();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  const openPay = (po) => {
    setSelectedPO(po);
    setPayForm({ amount: po.balance || po.subtotal, reference: '' });
    setPayDialog(true);
  };

  const handlePay = async () => {
    try {
      await api.post(`/purchase-orders/${selectedPO.id}/pay`, { amount: payForm.amount, reference: payForm.reference });
      toast.success('Payment recorded! Deducted from Cashier Drawer.');
      setPayDialog(false);
      fetchOrders();
    } catch (e) { toast.error(e.response?.data?.detail || 'Payment failed'); }
  };

  const viewDetail = (po) => { setDetailPO(po); setDetailDialog(true); };

  const statusColor = (s) => {
    if (s === 'received') return 'bg-emerald-100 text-emerald-700';
    if (s === 'ordered') return 'bg-blue-100 text-blue-700';
    if (s === 'cancelled') return 'bg-red-100 text-red-700';
    return 'bg-slate-100 text-slate-700';
  };

  return (
    <div className="space-y-5 animate-fadeIn" data-testid="purchase-order-page">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>Purchase Orders</h1>
        <p className="text-sm text-slate-500">Order from suppliers, receive inventory, pay vendors</p>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="create" data-testid="tab-create-po">New PO</TabsTrigger>
          <TabsTrigger value="pay" data-testid="tab-pay-supplier">Pay Supplier</TabsTrigger>
          <TabsTrigger value="list" data-testid="tab-list-po">PO List ({totalOrders})</TabsTrigger>
        </TabsList>

        {/* CREATE TAB */}
        <TabsContent value="create" className="mt-4 space-y-4">
          <Card className="border-slate-200">
            <CardContent className="p-5">
              <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
                <div className="relative" ref={supplierSearchRef}>
                  <Label className="text-xs text-slate-500">Vendor Name</Label>
                  <Input
                    data-testid="po-vendor"
                    className="h-9"
                    value={supplierSearch || header.vendor}
                    onChange={e => {
                      setSupplierSearch(e.target.value);
                      setHeader(h => ({ ...h, vendor: e.target.value }));
                    }}
                    onFocus={() => supplierSearch && setShowSupplierDropdown(true)}
                    placeholder="Type supplier name..."
                    autoComplete="off"
                  />
                  {showSupplierDropdown && (
                    <div className="absolute z-50 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-60 overflow-y-auto">
                      {supplierResults.length > 0 ? (
                        supplierResults.map(name => (
                          <button
                            key={name}
                            onClick={() => selectSupplier(name)}
                            className="w-full text-left px-3 py-2 text-sm hover:bg-slate-50 flex items-center gap-2"
                          >
                            <Truck size={12} className="text-slate-400" />
                            {name}
                          </button>
                        ))
                      ) : null}
                      {supplierSearch && !supplierResults.some(n => n.toLowerCase() === supplierSearch.toLowerCase()) && (
                        <button
                          onClick={quickCreateSupplier}
                          className="w-full text-left px-3 py-2 text-sm bg-emerald-50 hover:bg-emerald-100 text-emerald-700 flex items-center gap-2 border-t"
                        >
                          <UserPlus size={12} />
                          Create "{supplierSearch}" as new supplier
                        </button>
                      )}
                      {supplierResults.length === 0 && !supplierSearch && (
                        <p className="px-3 py-2 text-xs text-slate-400">Start typing to search...</p>
                      )}
                    </div>
                  )}
                </div>
                <div><Label className="text-xs text-slate-500">Purchase Date</Label><Input className="h-9" type="date" value={header.purchase_date} onChange={e => setHeader(h => ({ ...h, purchase_date: e.target.value }))} /></div>
                <div>
                  <Label className="text-xs text-slate-500">Payment</Label>
                  <Select value={header.payment_method} onValueChange={v => setHeader(h => ({ ...h, payment_method: v }))}>
                    <SelectTrigger className="h-9" data-testid="po-payment-method"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="cash">Pay in Cash</SelectItem>
                      <SelectItem value="credit">Purchase on Credit</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs text-slate-500">Status</Label>
                  <Select value={header.status} onValueChange={v => setHeader(h => ({ ...h, status: v }))}>
                    <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="draft">Draft</SelectItem>
                      <SelectItem value="ordered">Ordered</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div><Label className="text-xs text-slate-500">PO Number</Label><Input data-testid="po-number" className="h-9" value={header.po_number} onChange={e => setHeader(h => ({ ...h, po_number: e.target.value }))} placeholder="Auto if blank" /></div>
              </div>
              <div className="mt-3">
                <Label className="text-xs text-slate-500">Notes</Label><Input className="h-9" value={header.notes} onChange={e => setHeader(h => ({ ...h, notes: e.target.value }))} placeholder="Optional notes for this purchase order" />
              </div>
              {header.payment_method === 'cash' && (
                <p className="text-xs text-amber-600 mt-2 flex items-center gap-1"><DollarSign size={12} /> Total will be deducted from Cashier Drawer on save</p>
              )}
              {header.payment_method === 'credit' && (
                <div className="mt-3 grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-xs text-slate-500">Payment Terms (days)</Label>
                    <Input type="number" min="0" className="h-9" value={header.terms_days}
                      onChange={e => {
                        const days = parseInt(e.target.value) || 0;
                        const pd = header.purchase_date || new Date().toISOString().slice(0,10);
                        const due = days > 0 ? new Date(new Date(pd).getTime() + days * 86400000).toISOString().slice(0,10) : '';
                        setHeader(h => ({ ...h, terms_days: days, due_date: due }));
                      }}
                      placeholder="e.g. 30 for Net 30" />
                  </div>
                  <div>
                    <Label className="text-xs text-slate-500">Due Date (auto-computed)</Label>
                    <Input type="date" className="h-9" value={header.due_date}
                      onChange={e => setHeader(h => ({ ...h, due_date: e.target.value }))} />
                  </div>
                </div>
              )}
              {header.payment_method === 'credit' && !header.terms_days && (
                <p className="text-xs text-blue-600 mt-2">Payable will be created. Set payment terms above for due-date tracking.</p>
              )}
            </CardContent>
          </Card>

          {/* Line Items */}
          <Card className="border-slate-200">
            <CardContent className="p-0">
              <table className="w-full text-sm" data-testid="po-lines-table">
                <thead>
                  <tr className="bg-slate-50 border-b">
                    <th className="text-left px-3 py-2 text-xs uppercase text-slate-500 font-medium w-8">#</th>
                    <th className="text-left px-3 py-2 text-xs uppercase text-slate-500 font-medium min-w-[300px]">Product / Barcode</th>
                    <th className="text-left px-3 py-2 text-xs uppercase text-slate-500 font-medium w-[180px]">Description</th>
                    <th className="text-right px-3 py-2 text-xs uppercase text-slate-500 font-medium w-24">Qty</th>
                    <th className="text-right px-3 py-2 text-xs uppercase text-slate-500 font-medium w-28">Unit Price</th>
                    <th className="text-right px-3 py-2 text-xs uppercase text-slate-500 font-medium w-28">Total</th>
                    <th className="w-10"></th>
                  </tr>
                </thead>
                <tbody>
                  {lines.map((line, i) => (
                    <tr key={i} className="border-b border-slate-100 hover:bg-slate-50/50">
                      <td className="px-3 py-1 text-xs text-slate-400">{i + 1}</td>
                      <td className="px-2 py-1">
                        {line.product_id ? (
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-sm">{line.product_name}</span>
                            <button onClick={() => updateLine(i, 'product_id', '')} className="text-slate-400 hover:text-red-500 text-xs">&times;</button>
                          </div>
                        ) : (
                          <SmartProductSearch branchId={currentBranch?.id} onSelect={(p) => handleProductSelect(i, p)} onCreateNew={handleCreateNewProduct} />
                        )}
                      </td>
                      <td className="px-2 py-1"><input className="w-full h-8 px-2 text-sm border border-transparent hover:border-slate-200 focus:border-[#1A4D2E] focus:outline-none rounded" value={line.description} onChange={e => updateLine(i, 'description', e.target.value)} /></td>
                      <td className="px-2 py-1"><input ref={el => qtyRefs.current[i] = el} type="number" min="0" className="w-full h-8 px-2 text-sm text-right border border-transparent hover:border-slate-200 focus:border-[#1A4D2E] focus:outline-none rounded" value={line.quantity} onChange={e => updateLine(i, 'quantity', parseFloat(e.target.value) || 0)} /></td>
                      <td className="px-2 py-1"><input type="number" className="w-full h-8 px-2 text-sm text-right border border-transparent hover:border-slate-200 focus:border-[#1A4D2E] focus:outline-none rounded" value={line.unit_price} onChange={e => updateLine(i, 'unit_price', parseFloat(e.target.value) || 0)} /></td>
                      <td className="px-3 py-1 text-right font-semibold text-sm">{line.product_id ? formatPHP(line.quantity * line.unit_price) : ''}</td>
                      <td className="px-1 py-1">{lines.length > 1 && line.product_id && <button onClick={() => removeLine(i)} className="text-slate-400 hover:text-red-500 p-1"><Trash2 size={14} /></button>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <div className="flex justify-between items-end">
            <div />
            <div className="w-72 space-y-2">
              <div className="flex justify-between text-lg font-bold" style={{ fontFamily: 'Manrope' }}>
                <span>Total</span><span className="text-[#1A4D2E]">{formatPHP(subtotal)}</span>
              </div>
              <Button data-testid="save-po-btn" onClick={handleSave} disabled={saving} className="w-full bg-[#1A4D2E] hover:bg-[#14532d] text-white">
                <Save size={16} className="mr-2" /> {saving ? 'Saving...' : 'Create Purchase Order'}
              </Button>
            </div>
          </div>
        </TabsContent>

        {/* PAY SUPPLIER TAB */}
        <TabsContent value="pay" className="mt-4 space-y-4">
          <div className="grid lg:grid-cols-3 gap-5">
            {/* Vendor Search */}
            <Card className="border-slate-200">
              <CardContent className="p-4 space-y-3">
                <Label className="text-xs text-slate-500 font-semibold uppercase">Supplier</Label>
                <div className="relative">
                  <Search size={14} className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-400" />
                  <Input value={vendorSearch} onChange={e => { setVendorSearch(e.target.value); setPayVendor(''); setVendorPOs([]); }}
                    placeholder="Type supplier name..." className="pl-8 h-9" data-testid="pay-vendor-search" />
                </div>
                <div className="max-h-[350px] overflow-y-auto space-y-0.5">
                  {filteredVendors.map(v => (
                    <button key={v} onClick={() => selectPayVendor(v)}
                      className={`w-full text-left px-3 py-2 text-sm rounded hover:bg-slate-50 ${payVendor === v ? 'bg-[#1A4D2E]/5 border-l-2 border-l-[#1A4D2E] font-medium' : ''}`}>
                      {v}
                    </button>
                  ))}
                  {!filteredVendors.length && <p className="text-xs text-slate-400 text-center py-4">No suppliers found</p>}
                </div>
              </CardContent>
            </Card>

            {/* Payment Form + Unpaid POs */}
            <div className="lg:col-span-2 space-y-4">
              {payVendor ? (
                <>
                  <Card className="border-slate-200">
                    <CardContent className="p-5 space-y-4">
                      <div className="flex items-center justify-between">
                        <h3 className="font-bold" style={{ fontFamily: 'Manrope' }}>{payVendor}</h3>
                        <Button variant="outline" size="sm" onClick={() => openSupplierHistory(payVendor)}>
                          <History size={13} className="mr-1" /> View Full History
                        </Button>
                      </div>
                      <Separator />
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <div><Label className="text-xs">Amount</Label>
                          <Input data-testid="pay-sup-amount" type="number" value={paySupForm.amount} onChange={e => setPaySupForm(f => ({ ...f, amount: parseFloat(e.target.value) || 0 }))} className="h-10 text-lg font-bold" />
                        </div>
                        <div><Label className="text-xs">Payment Date</Label>
                          <Input type="date" value={paySupForm.payment_date} onChange={e => setPaySupForm(f => ({ ...f, payment_date: e.target.value }))} className="h-10" />
                        </div>
                        <div><Label className="text-xs">Check #</Label>
                          <Input value={paySupForm.check_number} onChange={e => setPaySupForm(f => ({ ...f, check_number: e.target.value }))} placeholder="Optional" className="h-10" />
                        </div>
                        <div><Label className="text-xs">Check Date</Label>
                          <Input type="date" value={paySupForm.check_date} onChange={e => setPaySupForm(f => ({ ...f, check_date: e.target.value }))} className="h-10" />
                        </div>
                      </div>
                      <div>
                        <Label className="text-xs">Select PO to Pay</Label>
                        <Select value={paySupForm.selected_po} onValueChange={v => {
                          const po = vendorPOs.find(p => p.id === v);
                          setPaySupForm(f => ({ ...f, selected_po: v, amount: po ? (po.balance || po.subtotal) : f.amount }));
                        }}>
                          <SelectTrigger data-testid="pay-sup-po-select" className="h-10"><SelectValue placeholder="Select unpaid PO..." /></SelectTrigger>
                          <SelectContent>
                            {vendorPOs.map(po => (
                              <SelectItem key={po.id} value={po.id}>
                                {po.po_number} — {formatPHP(po.subtotal)} (bal: {formatPHP(po.balance || po.subtotal)})
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <Button data-testid="confirm-sup-pay" onClick={handlePaySupplier} className="w-full h-11 bg-[#1A4D2E] hover:bg-[#14532d] text-white">
                        <DollarSign size={16} className="mr-2" /> Pay {formatPHP(paySupForm.amount)} to {payVendor}
                      </Button>
                    </CardContent>
                  </Card>

                  {/* Unpaid POs Table */}
                  <Card className="border-slate-200">
                    <CardContent className="p-0">
                      <div className="px-4 py-2 bg-slate-50 border-b text-xs font-semibold uppercase text-slate-500">Open Purchase Orders</div>
                      <Table>
                        <TableHeader><TableRow>
                          <TableHead className="text-xs uppercase text-slate-500">PO #</TableHead>
                          <TableHead className="text-xs uppercase text-slate-500">Date</TableHead>
                          <TableHead className="text-xs uppercase text-slate-500 text-right">Total</TableHead>
                          <TableHead className="text-xs uppercase text-slate-500 text-right">Paid</TableHead>
                          <TableHead className="text-xs uppercase text-slate-500 text-right">Balance</TableHead>
                          <TableHead className="text-xs uppercase text-slate-500">Status</TableHead>
                        </TableRow></TableHeader>
                        <TableBody>
                          {vendorPOs.map(po => (
                            <TableRow key={po.id} className={`table-row-hover cursor-pointer ${paySupForm.selected_po === po.id ? 'bg-emerald-50' : ''}`}
                              onClick={() => { setPaySupForm(f => ({ ...f, selected_po: po.id, amount: po.balance || po.subtotal })); }}>
                              <TableCell className="font-mono text-xs text-blue-600" onClick={e => { e.stopPropagation(); setDetailPO(po); setDetailDialog(true); }}>{po.po_number}</TableCell>
                              <TableCell className="text-xs">{po.purchase_date || po.created_at?.slice(0, 10)}</TableCell>
                              <TableCell className="text-right text-sm">{formatPHP(po.subtotal)}</TableCell>
                              <TableCell className="text-right text-sm text-slate-500">{formatPHP(po.amount_paid || 0)}</TableCell>
                              <TableCell className="text-right text-sm font-bold text-red-600">{formatPHP(po.balance || po.subtotal)}</TableCell>
                              <TableCell><Badge className={`text-[10px] ${po.payment_status === 'partial' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}`}>{po.payment_status || 'unpaid'}</Badge></TableCell>
                            </TableRow>
                          ))}
                          {!vendorPOs.length && <TableRow><TableCell colSpan={6} className="text-center py-6 text-slate-400">No unpaid POs for this supplier</TableCell></TableRow>}
                        </TableBody>
                      </Table>
                    </CardContent>
                  </Card>
                </>
              ) : (
                <div className="flex items-center justify-center h-48 text-slate-400 text-sm">Select a supplier to view unpaid POs</div>
              )}
            </div>
          </div>
        </TabsContent>

        {/* LIST TAB */}
        <TabsContent value="list" className="mt-4">
          <Card className="border-slate-200">
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow className="bg-slate-50">
                    <TableHead className="text-xs uppercase text-slate-500">PO #</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500">Vendor</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500">Items</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500 text-right">Total</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500">Purchase Date</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500">Payment</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500">Status</TableHead>
                    <TableHead className="w-48">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {orders.map(po => (
                    <TableRow key={po.id} className="table-row-hover">
                      <TableCell className="font-mono text-xs cursor-pointer text-blue-600 hover:underline" onClick={() => viewDetail(po)}>{po.po_number}</TableCell>
                      <TableCell className="font-medium">
                        <button onClick={() => openSupplierHistory(po.vendor)} className="hover:text-blue-600 hover:underline">{po.vendor}</button>
                      </TableCell>
                      <TableCell>{po.items?.length || 0}</TableCell>
                      <TableCell className="text-right font-semibold">{formatPHP(po.subtotal)}</TableCell>
                      <TableCell className="text-xs text-slate-500">{po.purchase_date || po.expected_date || '—'}</TableCell>
                      <TableCell>
                        <Badge className={`text-[10px] ${po.payment_status === 'paid' ? 'bg-emerald-100 text-emerald-700' : po.payment_status === 'partial' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}`}>
                          {po.payment_method === 'credit' ? 'Credit' : 'Cash'} · {po.payment_status || (po.payment_method === 'cash' ? 'paid' : 'unpaid')}
                        </Badge>
                      </TableCell>
                      <TableCell><Badge className={`text-[10px] ${statusColor(po.status)}`}>{po.status}</Badge></TableCell>
                      <TableCell>
                        <div className="flex gap-1 flex-wrap">
                          {po.status === 'ordered' && (
                            <Button size="sm" variant="outline" onClick={() => receivePO(po.id)} data-testid={`receive-po-${po.id}`}>
                              <Check size={12} className="mr-1" /> Receive
                            </Button>
                          )}
                          {po.status === 'received' && (
                            <Button size="sm" variant="outline" onClick={() => reopenPO(po)}
                              className="text-amber-600 border-amber-200 hover:bg-amber-50 text-[11px]"
                              data-testid={`reopen-po-${po.id}`}>
                              ↩ Reopen
                            </Button>
                          )}
                          {po.status !== 'cancelled' && po.status !== 'received' && (
                            <Button size="sm" variant="ghost" onClick={() => cancelPO(po.id)} className="text-red-500">
                              <X size={12} />
                            </Button>
                          )}
                          {po.payment_status !== 'paid' && po.payment_method === 'credit' && po.status !== 'cancelled' && (
                            <Button size="sm" variant="outline" onClick={() => openPay(po)} data-testid={`pay-po-${po.id}`}>
                              <DollarSign size={12} className="mr-1" /> Pay
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                  {!orders.length && <TableRow><TableCell colSpan={8} className="text-center py-8 text-slate-400">No purchase orders yet</TableCell></TableRow>}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Pay Supplier Dialog */}
      <Dialog open={payDialog} onOpenChange={setPayDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Pay Supplier (from Cashier Drawer)</DialogTitle></DialogHeader>
          {selectedPO && (
            <div className="space-y-4 mt-2">
              <div className="p-3 bg-slate-50 rounded-lg text-sm">
                <p>PO: <b>{selectedPO.po_number}</b></p>
                <p>Vendor: <b>{selectedPO.vendor}</b></p>
                <p className="text-lg font-bold mt-1">Balance: {formatPHP(selectedPO.balance || selectedPO.subtotal)}</p>
              </div>
              <div><Label>Amount to Pay</Label><Input data-testid="pay-po-amount" type="number" value={payForm.amount} onChange={e => setPayForm({ ...payForm, amount: parseFloat(e.target.value) || 0 })} className="h-11 text-lg font-bold" /></div>
              <div><Label>Reference (optional)</Label><Input value={payForm.reference} onChange={e => setPayForm({ ...payForm, reference: e.target.value })} placeholder="Check number, receipt, etc." /></div>
              <p className="text-xs text-amber-600 flex items-center gap-1"><DollarSign size={12} /> Will be deducted from Cashier Drawer</p>
              <Button data-testid="confirm-po-payment" onClick={handlePay} className="w-full h-11 bg-[#1A4D2E] hover:bg-[#14532d] text-white">
                Pay {formatPHP(payForm.amount)}
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* PO Detail Dialog */}
      <Dialog open={detailDialog} onOpenChange={setDetailDialog}>
        <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>PO Detail</DialogTitle></DialogHeader>
          {detailPO && (
            <div className="space-y-4 mt-2">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div><span className="text-slate-500">PO #:</span> <span className="font-mono">{detailPO.po_number}</span></div>
                <div><span className="text-slate-500">Vendor:</span> <b>{detailPO.vendor}</b></div>
                <div><span className="text-slate-500">Status:</span> <Badge className={`${statusColor(detailPO.status)} text-[10px]`}>{detailPO.status}</Badge></div>
                <div><span className="text-slate-500">Purchase Date:</span> {detailPO.purchase_date || detailPO.expected_date || '—'}</div>
                <div><span className="text-slate-500">Payment:</span> <Badge className={`text-[10px] ${detailPO.payment_status === 'paid' ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>{detailPO.payment_method === 'credit' ? 'Credit' : 'Cash'} · {detailPO.payment_status || 'n/a'}</Badge></div>
                {detailPO.payment_method === 'credit' && <div><span className="text-slate-500">Balance:</span> <b className="text-red-600">{formatPHP(detailPO.balance)}</b></div>}
              </div>
              <Table>
                <TableHeader><TableRow>
                  <TableHead className="text-xs">Product</TableHead>
                  <TableHead className="text-xs text-right">Qty</TableHead>
                  <TableHead className="text-xs text-right">Price</TableHead>
                  <TableHead className="text-xs text-right">Total</TableHead>
                </TableRow></TableHeader>
                <TableBody>
                  {detailPO.items?.map((item, i) => (
                    <TableRow key={i}>
                      <TableCell className="text-sm">{item.product_name}</TableCell>
                      <TableCell className="text-right">{item.quantity}</TableCell>
                      <TableCell className="text-right">{formatPHP(item.unit_price)}</TableCell>
                      <TableCell className="text-right font-semibold">{formatPHP(item.total)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <div className="flex justify-between text-lg font-bold pt-2 border-t">
                <span>Total</span><span>{formatPHP(detailPO.subtotal)}</span>
              </div>
              {detailPO.notes && <p className="text-sm text-slate-500">Notes: {detailPO.notes}</p>}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Create Product Dialog */}
      <Dialog open={createProductDialog} onOpenChange={setCreateProductDialog}>
        <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Create New Product</DialogTitle></DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="grid grid-cols-2 gap-4">
              <div><Label>SKU</Label><Input value={newProductForm.sku} onChange={e => setNewProductForm(f => ({ ...f, sku: e.target.value }))} placeholder="e.g. LAN-250G" /></div>
              <div><Label>Product Name</Label><Input value={newProductForm.name} onChange={e => setNewProductForm(f => ({ ...f, name: e.target.value }))} /></div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div><Label>Category</Label>
                <Select value={newProductForm.category} onValueChange={v => setNewProductForm(f => ({ ...f, category: v }))}>
                  <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Pesticide">Pesticide</SelectItem>
                    <SelectItem value="Fertilizers">Fertilizers</SelectItem>
                    <SelectItem value="Seeds">Seeds</SelectItem>
                    <SelectItem value="Feeds">Feeds</SelectItem>
                    <SelectItem value="Tools">Tools</SelectItem>
                    <SelectItem value="Veterinary">Veterinary</SelectItem>
                    <SelectItem value="Customized">Customized</SelectItem>
                    <SelectItem value="Others">Others</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div><Label>Unit</Label><Input value={newProductForm.unit} onChange={e => setNewProductForm(f => ({ ...f, unit: e.target.value }))} /></div>
              <div><Label>Cost Price</Label><Input type="number" value={newProductForm.cost_price} onChange={e => setNewProductForm(f => ({ ...f, cost_price: parseFloat(e.target.value) || 0 }))} /></div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              {schemes.map(s => (
                <div key={s.id}><Label className="text-xs text-slate-500">{s.name}</Label>
                  <Input type="number" value={newProductForm.prices[s.key] || ''} onChange={e => setNewProductForm(f => ({ ...f, prices: { ...f.prices, [s.key]: parseFloat(e.target.value) || 0 } }))} placeholder="0.00" />
                </div>
              ))}
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setCreateProductDialog(false)}>Cancel</Button>
              <Button onClick={saveNewProduct} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">Create Product</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Supplier History Dialog */}
      <Dialog open={historyDialog} onOpenChange={setHistoryDialog}>
        <DialogContent className="sm:max-w-3xl max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Supplier History — {historyVendor}</DialogTitle></DialogHeader>
          <div className="space-y-4 mt-2">
            {historyPOs.map(po => (
              <Card key={po.id} className={`border-slate-200 ${po.payment_status === 'paid' ? 'opacity-70' : ''}`}>
                <CardContent className="p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <button onClick={() => { setDetailPO(po); setDetailDialog(true); }} className="font-mono text-sm text-blue-600 hover:underline font-bold">{po.po_number}</button>
                      <Badge className={`text-[10px] ${statusColor(po.status)}`}>{po.status}</Badge>
                      <Badge className={`text-[10px] ${po.payment_status === 'paid' ? 'bg-emerald-100 text-emerald-700' : po.payment_status === 'partial' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}`}>
                        {po.payment_status || 'unpaid'}
                      </Badge>
                    </div>
                    <span className="text-lg font-bold" style={{ fontFamily: 'Manrope' }}>{formatPHP(po.subtotal)}</span>
                  </div>
                  <div className="text-xs text-slate-500">
                    Date: {po.purchase_date || po.created_at?.slice(0, 10)} &middot; Items: {po.items?.length || 0}
                    {po.balance > 0 && <> &middot; <span className="text-red-600 font-semibold">Balance: {formatPHP(po.balance)}</span></>}
                  </div>
                  {/* Payment history for this PO */}
                  {po.payment_history?.length > 0 && (
                    <div className="mt-2 bg-slate-50 rounded p-2 space-y-1">
                      <p className="text-[10px] font-semibold uppercase text-slate-400">Payments</p>
                      {po.payment_history.map((pay, i) => (
                        <div key={i} className="flex items-center justify-between text-xs">
                          <div className="flex items-center gap-2">
                            <ArrowRight size={10} className="text-emerald-500" />
                            <span>{pay.date}</span>
                            {pay.check_number && <span className="text-slate-400">Check #{pay.check_number}</span>}
                          </div>
                          <span className="font-bold text-emerald-600">{formatPHP(pay.amount)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
            {!historyPOs.length && <p className="text-center py-8 text-slate-400">No purchase orders found</p>}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
