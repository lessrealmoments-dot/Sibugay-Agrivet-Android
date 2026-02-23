import { useState, useEffect, useRef, useMemo } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
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
import {
  FileText, Plus, Trash2, Save, Truck, Check, X, DollarSign,
  Search, History, ArrowRight, Receipt, UserPlus, Package,
  Wallet, Banknote, CreditCard, AlertTriangle, ChevronDown, RefreshCw,
  ShieldCheck, Clock
} from 'lucide-react';
import { toast } from 'sonner';

const EMPTY_LINE = {
  product_id: '', product_name: '', unit: '', description: '',
  quantity: 1, unit_price: 0,
  discount_type: 'amount', discount_value: 0,
};
const PAYMENT_METHODS = ['Cash', 'Check', 'Bank Transfer', 'GCash', 'Maya'];
const TERMS_OPTIONS = [
  { label: 'COD (Due on Receipt)', days: 0 },
  { label: 'Net 7', days: 7 },
  { label: 'Net 15', days: 15 },
  { label: 'Net 30', days: 30 },
  { label: 'Net 45', days: 45 },
  { label: 'Net 60', days: 60 },
];

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

// ── Totals row component ────────────────────────────────────────────────────
function TotalsRow({ label, value, bold, accent }) {
  return (
    <div className={`flex justify-between items-center py-1 text-sm ${bold ? 'font-bold text-base' : ''} ${accent || ''}`}>
      <span className="text-slate-600">{label}</span>
      <span className="font-mono">{formatPHP(value)}</span>
    </div>
  );
}

export default function PurchaseOrderPage() {
  const { currentBranch, branches, user } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role === 'admin';
  const today = new Date().toISOString().slice(0, 10);

  // ── Source type: external supplier vs internal branch request ──────────
  const [sourceType, setSourceType] = useState('external'); // 'external' | 'branch_request'
  const [supplyBranchId, setSupplyBranchId] = useState(''); // for branch_request
  const [showRetailToggle, setShowRetailToggle] = useState(isAdmin); // admin default ON, manager default OFF

  // ── Header state ────────────────────────────────────────────────────────
  const [tab, setTab] = useState('create');
  const [header, setHeader] = useState({
    vendor: '', dr_number: '', po_number: '', purchase_date: today, notes: '',
    show_freight: false, freight: 0,
    overall_discount_type: 'amount', overall_discount_value: '',
    show_vat: false, tax_rate: 12,
  });
  const [lines, setLines] = useState([{ ...EMPTY_LINE }]);
  const [saving, setSaving] = useState(false);

  // ── Supplier search ────────────────────────────────────────────────────
  const [suppliers, setSuppliers] = useState([]);
  const [vendorsList, setVendorsList] = useState([]);
  const [supplierSearch, setSupplierSearch] = useState('');
  const [supplierResults, setSupplierResults] = useState([]);
  const [showSupplierDd, setShowSupplierDd] = useState(false);
  const supplierRef = useRef(null);

  // ── Cash dialog ────────────────────────────────────────────────────────
  const [cashDialog, setCashDialog] = useState(false);
  const [cashFunds, setCashFunds] = useState({ cashier: 0, safe: 0 });
  const [cashForm, setCashForm] = useState({ fund_source: 'cashier', payment_method_detail: 'Cash', check_number: '' });
  const [cashLoading, setCashLoading] = useState(false);

  // ── Terms dialog ───────────────────────────────────────────────────────
  const [termsDialog, setTermsDialog] = useState(false);
  const [termsForm, setTermsForm] = useState({ terms_days: 30, terms_label: 'Net 30', due_date: '' });

  // ── PO List ────────────────────────────────────────────────────────────
  const [orders, setOrders] = useState([]);
  const [totalOrders, setTotalOrders] = useState(0);
  const [listFilter, setListFilter] = useState('all');
  const [detailDialog, setDetailDialog] = useState(false);
  const [detailPO, setDetailPO] = useState(null);
  const [schemes, setSchemes] = useState([]);

  // ── Create product dialog ──────────────────────────────────────────────
  const [createProdDialog, setCreateProdDialog] = useState(false);
  const [newProdForm, setNewProdForm] = useState({ sku: '', name: '', category: 'Pesticide', unit: 'Box', cost_price: 0, prices: {}, product_type: 'stockable' });

  // ── Supplier history dialog ────────────────────────────────────────────
  const [historyDialog, setHistoryDialog] = useState(false);
  const [historyVendor, setHistoryVendor] = useState('');
  const [historyPOs, setHistoryPOs] = useState([]);

  const qtyRefs = useRef([]);

  // ── Init ───────────────────────────────────────────────────────────────
  useEffect(() => {
    api.get('/purchase-orders/vendors').then(r => setVendorsList(r.data)).catch(() => {});
    api.get('/suppliers').then(r => setSuppliers(r.data)).catch(() => {});
    api.get('/price-schemes').then(r => setSchemes(r.data)).catch(() => {});
    fetchOrders();
  }, [currentBranch]);

  // Supplier search autocomplete
  useEffect(() => {
    if (supplierSearch.length > 0) {
      const all = [...new Set([...vendorsList, ...suppliers.map(s => s.name)])];
      setSupplierResults(all.filter(n => n.toLowerCase().includes(supplierSearch.toLowerCase())).slice(0, 8));
      setShowSupplierDd(true);
    } else { setSupplierResults([]); setShowSupplierDd(false); }
  }, [supplierSearch, vendorsList, suppliers]);

  // Close supplier dropdown on outside click
  useEffect(() => {
    const h = (e) => { if (supplierRef.current && !supplierRef.current.contains(e.target)) setShowSupplierDd(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);

  // ── Computed totals ────────────────────────────────────────────────────
  const computed = useMemo(() => {
    const lineDiscounts = lines.map(l => {
      const base = (parseFloat(l.quantity) || 0) * (parseFloat(l.unit_price) || 0);
      if (l.discount_type === 'percent') return Math.round(base * (parseFloat(l.discount_value) || 0) / 100 * 100) / 100;
      return parseFloat(l.discount_value) || 0;
    });
    const lineTotals = lines.map((l, i) => Math.max(0,
      (parseFloat(l.quantity) || 0) * (parseFloat(l.unit_price) || 0) - lineDiscounts[i]
    ));
    const subtotal = lineTotals.reduce((s, t) => s + t, 0);
    const odVal = parseFloat(header.overall_discount_value) || 0;
    const overallDisc = header.overall_discount_type === 'percent'
      ? Math.round(subtotal * odVal / 100 * 100) / 100
      : odVal;
    const afterDiscount = Math.max(0, subtotal - overallDisc);
    const freight = header.show_freight ? (parseFloat(header.freight) || 0) : 0;
    const preTax = afterDiscount + freight;
    const taxAmt = header.show_vat ? Math.round(preTax * header.tax_rate / 100 * 100) / 100 : 0;
    const grandTotal = preTax + taxAmt;
    return { subtotal, lineDiscounts, lineTotals, overallDisc, afterDiscount, freight, preTax, taxAmt, grandTotal };
  }, [lines, header]);

  // ── Fetch orders ───────────────────────────────────────────────────────
  const fetchOrders = async () => {
    try {
      const res = await api.get('/purchase-orders', { params: { limit: 200 } });
      setOrders(res.data.purchase_orders || []);
      setTotalOrders(res.data.total || 0);
    } catch {}
  };

  // ── Supplier actions ───────────────────────────────────────────────────
  const selectSupplier = (name) => {
    setHeader(h => ({ ...h, vendor: name }));
    setSupplierSearch(name);
    setShowSupplierDd(false);
  };

  const quickCreateSupplier = async () => {
    if (!supplierSearch.trim()) return;
    try {
      await api.post('/suppliers', { name: supplierSearch.trim() });
      toast.success(`Supplier "${supplierSearch}" created`);
      setHeader(h => ({ ...h, vendor: supplierSearch.trim() }));
      setShowSupplierDd(false);
      const res = await api.get('/suppliers');
      setSuppliers(res.data);
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  // ── Line item actions ──────────────────────────────────────────────────
  const handleProductSelect = (index, product) => {
    const nl = [...lines];
    nl[index] = { ...nl[index], product_id: product.id, product_name: product.name, unit: product.unit || '', unit_price: product.cost_price || 0 };
    if (index === lines.length - 1) nl.push({ ...EMPTY_LINE });
    setLines(nl);
    setTimeout(() => qtyRefs.current[index]?.focus(), 50);
  };

  const updateLine = (index, field, value) => {
    const nl = [...lines]; nl[index] = { ...nl[index], [field]: value }; setLines(nl);
  };

  const removeLine = (index) => { if (lines.length > 1) setLines(lines.filter((_, i) => i !== index)); };

  // ── Reset form ─────────────────────────────────────────────────────────
  const resetForm = () => {
    setLines([{ ...EMPTY_LINE }]);
    setHeader({ vendor: '', dr_number: '', po_number: '', purchase_date: today, notes: '', show_freight: false, freight: 0, overall_discount_type: 'amount', overall_discount_value: '', show_vat: false, tax_rate: 12 });
    setSupplierSearch('');
    setSourceType('external');
    setSupplyBranchId('');
    setShowRetailToggle(isAdmin);
  };

  // ── Validate ───────────────────────────────────────────────────────────
  const validate = () => {
    const valid = lines.filter(l => l.product_id);
    if (!valid.length) { toast.error('Add at least one product'); return null; }
    if (sourceType === 'external' && !header.vendor) { toast.error('Enter supplier name'); return null; }
    if (sourceType === 'branch_request' && !supplyBranchId) { toast.error('Select the branch to request from'); return null; }
    if (!currentBranch) { toast.error('Select a branch'); return null; }
    return valid;
  };

  const buildPayload = (validLines, extra = {}) => {
    const base = {
      vendor: sourceType === 'branch_request'
        ? `Branch Request → ${branches.find(b => b.id === supplyBranchId)?.name || supplyBranchId}`
        : header.vendor,
      dr_number: header.dr_number,
      po_number: header.po_number,
      purchase_date: header.purchase_date,
      notes: header.notes,
      branch_id: currentBranch.id,
      items: validLines,
      overall_discount_type: header.overall_discount_type,
      overall_discount_value: parseFloat(header.overall_discount_value) || 0,
      freight: header.show_freight ? (parseFloat(header.freight) || 0) : 0,
      tax_rate: header.show_vat ? header.tax_rate : 0,
      grand_total: computed.grandTotal,
      ...extra,
    };
    if (sourceType === 'branch_request') {
      base.po_type = 'branch_request';
      base.supply_branch_id = supplyBranchId;
      base.show_retail = showRetailToggle;
    }
    return base;
  };

  // ── Save as Draft ──────────────────────────────────────────────────────
  const handleSaveDraft = async () => {
    const valid = validate(); if (!valid) return;
    setSaving(true);
    try {
      const res = await api.post('/purchase-orders', buildPayload(valid, { po_type: 'draft' }));
      toast.success(`Draft PO ${res.data.po_number} saved`);
      resetForm(); fetchOrders(); setTab('list');
    } catch (e) { toast.error(e.response?.data?.detail || 'Error saving PO'); }
    setSaving(false);
  };

  // ── Open Cash Dialog ───────────────────────────────────────────────────
  const openCashDialog = async () => {
    const valid = validate(); if (!valid) return;
    setCashLoading(true);
    try {
      const res = await api.get('/purchase-orders/fund-balances', { params: { branch_id: currentBranch.id } });
      setCashFunds({ cashier: res.data.cashier || 0, safe: res.data.safe || 0 });
      // Default to safe if cashier insufficient
      if ((res.data.cashier || 0) < computed.grandTotal && (res.data.safe || 0) >= computed.grandTotal) {
        setCashForm(f => ({ ...f, fund_source: 'safe' }));
      } else {
        setCashForm(f => ({ ...f, fund_source: 'cashier' }));
      }
    } catch { setCashFunds({ cashier: 0, safe: 0 }); }
    setCashLoading(false);
    setCashDialog(true);
  };

  const handlePayInCash = async () => {
    const valid = validate(); if (!valid) return;
    const insufficient = cashForm.fund_source === 'cashier'
      ? cashFunds.cashier < computed.grandTotal
      : cashFunds.safe < computed.grandTotal;
    if (insufficient) { toast.error('Insufficient funds in selected source'); return; }
    setSaving(true);
    try {
      const res = await api.post('/purchase-orders', buildPayload(valid, {
        po_type: 'cash',
        fund_source: cashForm.fund_source,
        payment_method_detail: cashForm.payment_method_detail,
        check_number: cashForm.check_number,
      }));
      toast.success(`PO ${res.data.po_number} created — inventory updated, ₱${computed.grandTotal.toFixed(2)} deducted from ${cashForm.fund_source}`);
      setCashDialog(false); resetForm(); fetchOrders(); setTab('list');
    } catch (e) {
      const detail = e.response?.data?.detail;
      if (detail?.type === 'insufficient_funds') {
        toast.error(detail.message);
        setCashFunds({ cashier: detail.cashier_balance || 0, safe: detail.safe_balance || 0 });
      } else { toast.error(typeof detail === 'string' ? detail : 'Error creating PO'); }
    }
    setSaving(false);
  };

  // ── Open Terms Dialog ──────────────────────────────────────────────────
  const openTermsDialog = () => {
    const valid = validate(); if (!valid) return;
    // Compute default due date
    const days = termsForm.terms_days;
    const due = days > 0
      ? new Date(new Date(header.purchase_date).getTime() + days * 86400000).toISOString().slice(0, 10)
      : header.purchase_date;
    setTermsForm(f => ({ ...f, due_date: due }));
    setTermsDialog(true);
  };

  const handleReceiveOnTerms = async () => {
    const valid = validate(); if (!valid) return;
    setSaving(true);
    try {
      const res = await api.post('/purchase-orders', buildPayload(valid, {
        po_type: 'terms',
        terms_days: termsForm.terms_days,
        terms_label: termsForm.terms_label,
        due_date: termsForm.due_date,
      }));
      toast.success(`PO ${res.data.po_number} created — inventory updated, payable created (due ${termsForm.due_date || 'on receipt'})`);
      setTermsDialog(false); resetForm(); fetchOrders(); setTab('list');
    } catch (e) { toast.error(e.response?.data?.detail || 'Error creating PO'); }
    setSaving(false);
  };

  // ── PO List actions ────────────────────────────────────────────────────
  const receivePO = async (poId) => {
    if (!window.confirm('Mark as received? This will add items to inventory.')) return;
    try {
      await api.post(`/purchase-orders/${poId}/receive`);
      toast.success('PO received — inventory updated');
      fetchOrders();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  const cancelPO = async (poId) => {
    if (!window.confirm('Cancel this PO?')) return;
    try {
      await api.delete(`/purchase-orders/${poId}`);
      toast.success('PO cancelled'); fetchOrders();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  const reopenPO = async (po) => {
    if (!window.confirm(`Reopen PO ${po.po_number}? This reverses inventory. Continue?`)) return;
    try {
      const res = await api.post(`/purchase-orders/${po.id}/reopen`);
      toast.success(res.data.message); fetchOrders();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  // ── Pay Supplier tab (now standalone page) ────────────────────────────
  const openSupplierHistory = async (vendor) => {
    setHistoryVendor(vendor);
    try {
      const res = await api.get('/purchase-orders/by-vendor', { params: { vendor } });
      setHistoryPOs(res.data); setHistoryDialog(true);
    } catch { setHistoryPOs([]); }
  };

  const saveNewProduct = async () => {
    try {
      const res = await api.post('/products', newProdForm);
      toast.success(`Product "${res.data.name}" created!`);
      setCreateProdDialog(false);
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  // ── Filtered PO list ───────────────────────────────────────────────────
  const filteredOrders = useMemo(() => {
    if (listFilter === 'all') return orders;
    if (listFilter === 'draft') return orders.filter(o => o.status === 'draft');
    if (listFilter === 'ordered') return orders.filter(o => o.status === 'ordered');
    if (listFilter === 'received') return orders.filter(o => o.status === 'received');
    if (listFilter === 'unpaid') return orders.filter(o => o.payment_status !== 'paid' && o.status !== 'cancelled');
    return orders;
  }, [orders, listFilter]);

  const poTotal = (po) => po.grand_total || po.subtotal || 0;

  // ── RENDER ─────────────────────────────────────────────────────────────
  return (
    <div className="space-y-5 animate-fadeIn" data-testid="purchase-order-page">
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
          <FileText size={22} className="text-[#1A4D2E]" /> Purchase Orders
        </h1>
        <p className="text-sm text-slate-500">Receive stock, manage payables, pay suppliers</p>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="create" data-testid="tab-create-po">
            <Plus size={14} className="mr-1.5" /> New PO
          </TabsTrigger>
          <TabsTrigger value="list" data-testid="tab-list-po">
            <FileText size={14} className="mr-1.5" /> PO List ({totalOrders})
          </TabsTrigger>
        </TabsList>

        {/* ── NEW PO TAB ─────────────────────────────────────────────── */}
        <TabsContent value="create" className="mt-4 space-y-4">

          {/* Source Type Toggle */}
          <div className="flex items-center gap-3 p-3 rounded-lg bg-slate-50 border border-slate-200">
            <span className="text-xs font-medium text-slate-600">Source:</span>
            <div className="flex gap-1 bg-white rounded-lg border border-slate-200 p-0.5">
              <button onClick={() => setSourceType('external')}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors flex items-center gap-1.5 ${sourceType === 'external' ? 'bg-[#1A4D2E] text-white shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}>
                <Truck size={12} /> External Supplier
              </button>
              <button onClick={() => { setSourceType('branch_request'); setHeader(h => ({ ...h, vendor: '' })); }}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors flex items-center gap-1.5 ${sourceType === 'branch_request' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}>
                <ArrowRight size={12} /> Branch Stock Request
              </button>
            </div>
            {sourceType === 'branch_request' && (
              <div className="flex items-center gap-2 ml-2">
                <span className="text-[10px] text-slate-500">Show retail price to supply branch:</span>
                <button
                  onClick={() => setShowRetailToggle(v => !v)}
                  className={`relative inline-flex h-5 w-9 rounded-full transition-colors ${showRetailToggle ? 'bg-[#1A4D2E]' : 'bg-slate-300'}`}>
                  <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform mt-0.5 ${showRetailToggle ? 'translate-x-4.5' : 'translate-x-0.5'}`} />
                </button>
                <span className="text-[10px] font-medium text-slate-600">
                  {showRetailToggle ? 'ON (admin/owner)' : 'OFF (manager)'}
                </span>
              </div>
            )}
          </div>

          {/* Header */}
          <Card className="border-slate-200">
            <CardContent className="p-5 space-y-4">
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {/* Supplier OR Branch selector */}
                {sourceType === 'external' ? (
                  <div className="relative lg:col-span-2" ref={supplierRef}>
                    <Label className="text-xs text-slate-500">Supplier / Vendor <span className="text-red-500">*</span></Label>
                    <div className="relative mt-1">
                      <Truck size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                      <Input
                        data-testid="po-vendor"
                        className="h-9 pl-8"
                        value={supplierSearch || header.vendor}
                        onChange={e => { setSupplierSearch(e.target.value); setHeader(h => ({ ...h, vendor: e.target.value })); }}
                        onFocus={() => supplierSearch && setShowSupplierDd(true)}
                        placeholder="Type or search supplier..."
                        autoComplete="off"
                      />
                  </div>
                  {showSupplierDd && (
                    <div className="absolute z-50 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                      {supplierResults.map(name => (
                        <button key={name} onClick={() => selectSupplier(name)}
                          className="w-full text-left px-3 py-2 text-sm hover:bg-slate-50 flex items-center gap-2">
                          <Truck size={12} className="text-slate-400" /> {name}
                        </button>
                      ))}
                      {supplierSearch && !supplierResults.some(n => n.toLowerCase() === supplierSearch.toLowerCase()) && (
                        <button onClick={quickCreateSupplier}
                          className="w-full text-left px-3 py-2 text-sm bg-emerald-50 hover:bg-emerald-100 text-emerald-700 flex items-center gap-2 border-t">
                          <UserPlus size={12} /> Create "{supplierSearch}" as new supplier
                        </button>
                      )}
                    </div>
                  )}
                </div>
                ) : (
                  /* Branch Request — pick supply branch */
                  <div className="lg:col-span-2">
                    <Label className="text-xs text-slate-500">Request Stock From Branch <span className="text-red-500">*</span></Label>
                    <Select value={supplyBranchId} onValueChange={setSupplyBranchId}>
                      <SelectTrigger className="mt-1 h-9" data-testid="supply-branch-select">
                        <SelectValue placeholder="Select branch to request from..." />
                      </SelectTrigger>
                      <SelectContent>
                        {(branches || []).filter(b => b.id !== currentBranch?.id).map(b => (
                          <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="text-[10px] text-blue-600 mt-0.5">
                      That branch gets notified and can generate a Branch Transfer with one click.
                    </p>
                  </div>
                )}
                <div>
                  <Label className="text-xs text-slate-500">Purchase Date</Label>
                  <Input className="h-9 mt-1" type="date" value={header.purchase_date}
                    onChange={e => setHeader(h => ({ ...h, purchase_date: e.target.value }))} />
                </div>

                {/* DR / Reference # */}
                <div>
                  <Label className="text-xs text-slate-500">DR / Reference #</Label>
                  <Input className="h-9 mt-1" value={header.dr_number}
                    onChange={e => setHeader(h => ({ ...h, dr_number: e.target.value }))}
                    placeholder="Supplier's Delivery Receipt #" />
                </div>
              </div>

              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {/* PO Number */}
                <div>
                  <Label className="text-xs text-slate-500">PO Number (auto if blank)</Label>
                  <Input data-testid="po-number" className="h-9 mt-1" value={header.po_number}
                    onChange={e => setHeader(h => ({ ...h, po_number: e.target.value }))}
                    placeholder="Auto-generated" />
                </div>

                {/* Notes */}
                <div className="lg:col-span-3">
                  <Label className="text-xs text-slate-500">Notes</Label>
                  <Input className="h-9 mt-1" value={header.notes}
                    onChange={e => setHeader(h => ({ ...h, notes: e.target.value }))}
                    placeholder="Optional notes for this purchase order" />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Line Items */}
          <Card className="border-slate-200">
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid="po-lines-table">
                  <thead>
                    <tr className="bg-slate-50 border-b">
                      <th className="text-left px-3 py-2 text-xs uppercase text-slate-500 font-medium w-7">#</th>
                      <th className="text-left px-3 py-2 text-xs uppercase text-slate-500 font-medium" style={{minWidth:'260px'}}>Product</th>
                      <th className="text-left px-2 py-2 text-xs uppercase text-slate-500 font-medium w-16">Unit</th>
                      <th className="text-left px-2 py-2 text-xs uppercase text-slate-500 font-medium w-28">Description</th>
                      <th className="text-right px-2 py-2 text-xs uppercase text-slate-500 font-medium w-20">Qty</th>
                      <th className="text-right px-2 py-2 text-xs uppercase text-slate-500 font-medium w-28">Unit Price</th>
                      <th className="text-right px-2 py-2 text-xs uppercase text-slate-500 font-medium w-32">Discount</th>
                      <th className="text-right px-2 py-2 text-xs uppercase text-slate-500 font-medium w-28">Total</th>
                      <th className="w-8"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {lines.map((line, i) => (
                      <tr key={i} className="border-b border-slate-100 hover:bg-slate-50/40">
                        <td className="px-3 py-1 text-xs text-slate-400">{i + 1}</td>
                        <td className="px-2 py-1">
                          {line.product_id ? (
                            <div className="flex items-center gap-1.5">
                              <span className="font-medium text-sm">{line.product_name}</span>
                              <button onClick={() => updateLine(i, 'product_id', '')} className="text-slate-400 hover:text-red-500">&times;</button>
                            </div>
                          ) : (
                            <SmartProductSearch branchId={currentBranch?.id} onSelect={(p) => handleProductSelect(i, p)} onCreateNew={(n) => { setNewProdForm(f => ({ ...f, name: n })); setCreateProdDialog(true); }} />
                          )}
                        </td>
                        <td className="px-2 py-1">
                          <input className="w-full h-8 px-2 text-xs border border-transparent hover:border-slate-200 focus:border-[#1A4D2E] focus:outline-none rounded text-center"
                            value={line.unit} onChange={e => updateLine(i, 'unit', e.target.value)} placeholder="Box" />
                        </td>
                        <td className="px-2 py-1">
                          <input className="w-full h-8 px-2 text-xs border border-transparent hover:border-slate-200 focus:border-[#1A4D2E] focus:outline-none rounded"
                            value={line.description} onChange={e => updateLine(i, 'description', e.target.value)} placeholder="Optional" />
                        </td>
                        <td className="px-2 py-1">
                          <input ref={el => qtyRefs.current[i] = el} type="number" min="0"
                            className="w-full h-8 px-2 text-sm text-right font-mono border border-transparent hover:border-slate-200 focus:border-[#1A4D2E] focus:outline-none rounded"
                            value={line.quantity} onChange={e => updateLine(i, 'quantity', parseFloat(e.target.value) || 0)} />
                        </td>
                        <td className="px-2 py-1">
                          <input type="number" min="0"
                            className="w-full h-8 px-2 text-sm text-right font-mono border border-transparent hover:border-slate-200 focus:border-[#1A4D2E] focus:outline-none rounded"
                            value={line.unit_price} onChange={e => updateLine(i, 'unit_price', parseFloat(e.target.value) || 0)} />
                        </td>
                        <td className="px-2 py-1">
                          <div className="flex gap-1">
                            <select value={line.discount_type} onChange={e => updateLine(i, 'discount_type', e.target.value)}
                              className="h-8 text-xs border border-slate-200 rounded px-1 bg-white focus:outline-none w-12">
                              <option value="amount">₱</option>
                              <option value="percent">%</option>
                            </select>
                            <input type="number" min="0"
                              className="flex-1 h-8 px-2 text-xs text-right font-mono border border-slate-200 hover:border-slate-300 focus:border-[#1A4D2E] focus:outline-none rounded"
                              value={line.discount_value || ''} placeholder="0"
                              onChange={e => updateLine(i, 'discount_value', e.target.value)} />
                          </div>
                          {computed.lineDiscounts[i] > 0 && (
                            <p className="text-[9px] text-emerald-600 text-right mt-0.5">-{formatPHP(computed.lineDiscounts[i])}</p>
                          )}
                        </td>
                        <td className="px-3 py-1 text-right font-semibold text-sm font-mono">
                          {line.product_id ? formatPHP(computed.lineTotals[i]) : ''}
                        </td>
                        <td className="px-1 py-1">
                          {lines.length > 1 && line.product_id && (
                            <button onClick={() => removeLine(i)} className="text-slate-300 hover:text-red-500 p-1"><Trash2 size={13} /></button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Totals + Action Buttons */}
          <div className="flex flex-col lg:flex-row gap-6 items-start justify-between">

            {/* Optional toggles */}
            <div className="flex flex-col gap-2">
              {!header.show_freight && (
                <button onClick={() => setHeader(h => ({ ...h, show_freight: true }))}
                  className="text-xs text-slate-400 hover:text-slate-600 flex items-center gap-1.5">
                  <Plus size={12} /> Add Freight / Shipping Cost
                </button>
              )}
              {header.show_freight && (
                <div className="flex items-center gap-2">
                  <Label className="text-xs text-slate-500 w-32 shrink-0">Freight (₱)</Label>
                  <Input type="number" min="0" className="h-8 w-28 font-mono text-sm text-right"
                    value={header.freight} onChange={e => setHeader(h => ({ ...h, freight: e.target.value }))} />
                  <button onClick={() => setHeader(h => ({ ...h, show_freight: false, freight: 0 }))}
                    className="text-slate-400 hover:text-red-500"><X size={13} /></button>
                </div>
              )}
              {!header.show_vat && (
                <button onClick={() => setHeader(h => ({ ...h, show_vat: true }))}
                  className="text-xs text-slate-400 hover:text-slate-600 flex items-center gap-1.5">
                  <Plus size={12} /> Add VAT
                </button>
              )}
              {header.show_vat && (
                <div className="flex items-center gap-2">
                  <Label className="text-xs text-slate-500 w-32 shrink-0">VAT Rate (%)</Label>
                  <Input type="number" min="0" max="100" className="h-8 w-20 font-mono text-sm text-right"
                    value={header.tax_rate} onChange={e => setHeader(h => ({ ...h, tax_rate: parseFloat(e.target.value) || 0 }))} />
                  <button onClick={() => setHeader(h => ({ ...h, show_vat: false }))}
                    className="text-slate-400 hover:text-red-500"><X size={13} /></button>
                </div>
              )}
            </div>

            {/* Totals + Buttons */}
            <div className="w-full lg:w-80 space-y-2">
              <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 space-y-1">
                <TotalsRow label="Subtotal (before discounts)" value={computed.subtotal} />
                {/* Overall discount */}
                <div className="flex items-center gap-2 py-1">
                  <span className="text-sm text-slate-600 flex-1">Overall Discount</span>
                  <div className="flex gap-1 items-center">
                    <select value={header.overall_discount_type}
                      onChange={e => setHeader(h => ({ ...h, overall_discount_type: e.target.value }))}
                      className="h-7 text-xs border border-slate-200 rounded px-1 bg-white focus:outline-none">
                      <option value="amount">₱</option>
                      <option value="percent">%</option>
                    </select>
                    <input type="number" min="0"
                      className="w-20 h-7 px-2 text-xs text-right font-mono border border-slate-200 rounded focus:outline-none focus:border-[#1A4D2E]"
                      value={header.overall_discount_value} placeholder="0"
                      onChange={e => setHeader(h => ({ ...h, overall_discount_value: e.target.value }))} />
                  </div>
                  {computed.overallDisc > 0 && (
                    <span className="text-xs font-mono text-emerald-600">-{formatPHP(computed.overallDisc)}</span>
                  )}
                </div>
                {header.show_freight && <TotalsRow label="Freight" value={computed.freight} />}
                {header.show_vat && <TotalsRow label={`VAT (${header.tax_rate}%)`} value={computed.taxAmt} />}
                <Separator className="my-1" />
                <TotalsRow label="Grand Total" value={computed.grandTotal} bold accent="text-[#1A4D2E]" />
              </div>

              {/* 3 Action Buttons */}
              <div className="grid grid-cols-3 gap-2">
                <Button variant="outline" size="sm" onClick={handleSaveDraft} disabled={saving}
                  data-testid="save-draft-btn" className="flex flex-col h-14 gap-0.5">
                  <Save size={16} /><span className="text-[10px] leading-tight text-center">Save Draft</span>
                </Button>
                <Button size="sm" onClick={openTermsDialog} disabled={saving}
                  data-testid="receive-terms-btn"
                  className="flex flex-col h-14 gap-0.5 bg-blue-600 hover:bg-blue-700 text-white">
                  <CreditCard size={16} /><span className="text-[10px] leading-tight text-center">Receive on Terms</span>
                </Button>
                <Button size="sm" onClick={openCashDialog} disabled={saving || cashLoading}
                  data-testid="pay-cash-btn"
                  className="flex flex-col h-14 gap-0.5 bg-[#1A4D2E] hover:bg-[#14532d] text-white">
                  {cashLoading ? <RefreshCw size={16} className="animate-spin" /> : <Wallet size={16} />}
                  <span className="text-[10px] leading-tight text-center">Pay in Cash</span>
                </Button>
              </div>
              <p className="text-[10px] text-slate-400 text-center">
                Both "Receive" options immediately update inventory
              </p>
            </div>
          </div>
        </TabsContent>

        {/* ── PO LIST TAB ───────────────────────────────────────────── */}
        <TabsContent value="list" className="mt-4 space-y-3">
          {/* Unpaid POs banner → link to Pay Supplier page */}
          {/* Filter chips */}
          <div className="flex items-center gap-2 flex-wrap">
            {[
              { key: 'all', label: `All (${orders.length})` },
              { key: 'draft', label: `Draft (${orders.filter(o => o.status === 'draft').length})` },
              { key: 'ordered', label: `Ordered (${orders.filter(o => o.status === 'ordered').length})` },
              { key: 'received', label: `Received (${orders.filter(o => o.status === 'received').length})` },
              { key: 'unpaid', label: `Unpaid (${orders.filter(o => o.payment_status !== 'paid' && o.status !== 'cancelled').length})` },
            ].map(f => (
              <button key={f.key} onClick={() => setListFilter(f.key)}
                data-testid={`filter-${f.key}`}
                className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${listFilter === f.key ? 'bg-[#1A4D2E] text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}>
                {f.label}
              </button>
            ))}
            <div className="ml-auto flex gap-2">
              <Button variant="outline" size="sm" onClick={() => navigate('/pay-supplier')}
                className="h-7 border-[#1A4D2E] text-[#1A4D2E] hover:bg-[#1A4D2E]/5">
                <Banknote size={12} className="mr-1" /> Pay Supplier
              </Button>
              <Button variant="outline" size="sm" onClick={fetchOrders} className="h-7">
                <RefreshCw size={12} className="mr-1" /> Refresh
              </Button>
            </div>
          </div>

          <Card className="border-slate-200">
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow className="bg-slate-50">
                    <TableHead className="text-xs uppercase text-slate-500">PO #</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500">Supplier</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500">DR #</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500">Items</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500 text-right">Grand Total</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500">Date</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500">Receive</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500">Payment</TableHead>
                    <TableHead className="w-36">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredOrders.map(po => (
                    <TableRow key={po.id} className="hover:bg-slate-50">
                      <TableCell className="font-mono text-xs cursor-pointer text-blue-600 hover:underline"
                        onClick={() => { setDetailPO(po); setDetailDialog(true); }}>{po.po_number}</TableCell>
                      <TableCell className="font-medium max-w-[120px] truncate">
                        <button onClick={() => openSupplierHistory(po.vendor)} className="hover:text-blue-600 hover:underline">{po.vendor}</button>
                      </TableCell>
                      <TableCell className="text-xs text-slate-400">{po.dr_number || '—'}</TableCell>
                      <TableCell className="text-slate-500 text-xs">{po.items?.length || 0}</TableCell>
                      <TableCell className="text-right font-semibold font-mono">{formatPHP(poTotal(po))}</TableCell>
                      <TableCell className="text-xs text-slate-500">{po.purchase_date || '—'}</TableCell>
                      <TableCell>
                        <Badge className={`text-[10px] ${statusColor(po.status)}`}>{po.status}</Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col gap-0.5">
                          {po.status === 'draft' ? (
                            <Badge className="text-[10px] bg-slate-100 text-slate-500">Draft — pending</Badge>
                          ) : (
                            <Badge className={`text-[10px] ${payStatusColor(po.payment_status || (po.payment_method === 'cash' ? 'paid' : 'unpaid'))}`}>
                              {po.po_type === 'cash' || po.payment_method === 'cash' ? 'Cash' : 'Terms'} · {po.payment_status || (po.payment_method === 'cash' ? 'paid' : 'unpaid')}
                            </Badge>
                          )}
                          {po.balance > 0 && <span className="text-[10px] text-red-600 font-mono">{formatPHP(po.balance)}</span>}
                          {po.due_date && po.payment_status !== 'paid' && po.status !== 'draft' && (
                            <span className={`text-[9px] ${new Date(po.due_date) < new Date() ? 'text-red-600 font-semibold' : 'text-slate-400'}`}>
                              {new Date(po.due_date) < new Date() ? '⚠ ' : ''}Due {po.due_date}
                            </span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1 flex-wrap">
                          {(po.status === 'draft' || po.status === 'ordered') && (
                            <Button size="sm" variant="outline" onClick={() => receivePO(po.id)}
                              className="h-7 text-[11px]" data-testid={`receive-po-${po.id}`}>
                              <Check size={11} className="mr-0.5" /> Receive
                            </Button>
                          )}
                          {po.status === 'received' && (
                            <Button size="sm" variant="outline" onClick={() => reopenPO(po)}
                              className="h-7 text-[11px] text-amber-600 border-amber-200 hover:bg-amber-50"
                              data-testid={`reopen-po-${po.id}`}>
                              ↩ Reopen
                            </Button>
                          )}
                          {po.payment_status !== 'paid' && (po.po_type === 'terms' || po.payment_method === 'credit') && po.status !== 'cancelled' && (
                            <Button size="sm" variant="outline" onClick={() => navigate('/pay-supplier')}
                              className="h-7 text-[11px]" data-testid={`pay-po-${po.id}`}>
                              <DollarSign size={11} className="mr-0.5" /> Pay
                            </Button>
                          )}
                          {po.status !== 'cancelled' && po.status !== 'received' && (
                            <Button size="sm" variant="ghost" onClick={() => cancelPO(po.id)} className="h-7 text-red-500 px-1.5">
                              <X size={12} />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                  {!filteredOrders.length && (
                    <TableRow><TableCell colSpan={9} className="text-center py-8 text-slate-400">No purchase orders found</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* ── PAY IN CASH DIALOG ──────────────────────────────────────── */}
      <Dialog open={cashDialog} onOpenChange={v => { if (!v) setCashDialog(false); }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Manrope' }} className="flex items-center gap-2">
              <Wallet size={18} className="text-[#1A4D2E]" /> Pay in Cash — {formatPHP(computed.grandTotal)}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-1">
            {/* Fund source selection */}
            <div>
              <Label className="text-xs text-slate-500 font-medium">Select Fund Source</Label>
              <div className="grid grid-cols-2 gap-3 mt-2">
                {[
                  { key: 'cashier', label: 'Cashier Drawer', balance: cashFunds.cashier },
                  { key: 'safe', label: 'Safe / Vault', balance: cashFunds.safe },
                ].map(f => {
                  const sufficient = f.balance >= computed.grandTotal;
                  return (
                    <button key={f.key} onClick={() => setCashForm(c => ({ ...c, fund_source: f.key }))}
                      className={`p-3 rounded-lg border-2 text-left transition-all ${cashForm.fund_source === f.key ? 'border-[#1A4D2E] bg-emerald-50' : 'border-slate-200 hover:border-slate-300'} ${!sufficient ? 'opacity-60' : ''}`}>
                      <p className="text-xs font-medium text-slate-600">{f.label}</p>
                      <p className={`text-xl font-bold font-mono mt-0.5 ${sufficient ? 'text-[#1A4D2E]' : 'text-red-600'}`}>
                        {formatPHP(f.balance)}
                      </p>
                      {!sufficient && (
                        <p className="text-[10px] text-red-500 mt-0.5 flex items-center gap-0.5">
                          <AlertTriangle size={10} /> Short {formatPHP(computed.grandTotal - f.balance)}
                        </p>
                      )}
                      {sufficient && cashForm.fund_source === f.key && (
                        <p className="text-[10px] text-emerald-600 mt-0.5">
                          Balance after: {formatPHP(f.balance - computed.grandTotal)}
                        </p>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Payment method */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs text-slate-500">Payment Method</Label>
                <Select value={cashForm.payment_method_detail}
                  onValueChange={v => setCashForm(c => ({ ...c, payment_method_detail: v }))}>
                  <SelectTrigger className="h-9 mt-1"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {PAYMENT_METHODS.map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              {cashForm.payment_method_detail === 'Check' && (
                <div>
                  <Label className="text-xs text-slate-500">Check #</Label>
                  <Input className="h-9 mt-1" value={cashForm.check_number}
                    onChange={e => setCashForm(c => ({ ...c, check_number: e.target.value }))} />
                </div>
              )}
            </div>

            {/* Summary */}
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-sm space-y-1">
              <p className="font-semibold text-slate-700">On confirm:</p>
              <ul className="text-xs text-slate-500 space-y-0.5 list-disc list-inside">
                <li><b>{formatPHP(computed.grandTotal)}</b> deducted from {cashForm.fund_source === 'safe' ? 'Safe' : 'Cashier'}</li>
                <li>Expense record created: PO Payment — {header.vendor}</li>
                <li>Inventory updated immediately</li>
              </ul>
            </div>

            <div className="flex gap-2">
              <Button variant="outline" className="flex-1" onClick={() => setCashDialog(false)}>Cancel</Button>
              <Button onClick={handlePayInCash} disabled={saving}
                className="flex-1 bg-[#1A4D2E] hover:bg-[#14532d] text-white"
                data-testid="confirm-pay-cash-btn">
                {saving ? <RefreshCw size={14} className="animate-spin mr-1.5" /> : <Check size={14} className="mr-1.5" />}
                Confirm & Receive
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── RECEIVE ON TERMS DIALOG ──────────────────────────────────── */}
      <Dialog open={termsDialog} onOpenChange={v => { if (!v) setTermsDialog(false); }}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Manrope' }} className="flex items-center gap-2">
              <CreditCard size={18} className="text-blue-600" /> Receive on Terms — {formatPHP(computed.grandTotal)}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-1">
            <div>
              <Label className="text-xs text-slate-500">Payment Terms</Label>
              <Select value={termsForm.terms_label}
                onValueChange={v => {
                  const opt = TERMS_OPTIONS.find(o => o.label === v) || { label: v, days: termsForm.terms_days };
                  const due = opt.days > 0
                    ? new Date(new Date(header.purchase_date).getTime() + opt.days * 86400000).toISOString().slice(0, 10)
                    : header.purchase_date;
                  setTermsForm({ terms_days: opt.days, terms_label: opt.label, due_date: due });
                }}>
                <SelectTrigger className="mt-1 h-9"><SelectValue placeholder="Select terms..." /></SelectTrigger>
                <SelectContent>
                  {TERMS_OPTIONS.map(o => <SelectItem key={o.label} value={o.label}>{o.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs text-slate-500">Terms (days)</Label>
                <Input type="number" min="0" className="h-9 mt-1 font-mono" value={termsForm.terms_days}
                  onChange={e => {
                    const d = parseInt(e.target.value) || 0;
                    const due = d > 0
                      ? new Date(new Date(header.purchase_date).getTime() + d * 86400000).toISOString().slice(0, 10)
                      : header.purchase_date;
                    setTermsForm(f => ({ ...f, terms_days: d, due_date: due }));
                  }} />
              </div>
              <div>
                <Label className="text-xs text-slate-500">Due Date</Label>
                <Input type="date" className="h-9 mt-1" value={termsForm.due_date}
                  onChange={e => setTermsForm(f => ({ ...f, due_date: e.target.value }))} />
              </div>
            </div>
            <div className="p-3 rounded-lg bg-blue-50 border border-blue-200 text-sm space-y-1">
              <p className="font-semibold text-blue-800">On confirm:</p>
              <ul className="text-xs text-blue-700 space-y-0.5 list-disc list-inside">
                <li>Inventory updated immediately</li>
                <li>Accounts Payable created: <b>{formatPHP(computed.grandTotal)}</b> due to {header.vendor}</li>
                <li>Due date: <b>{termsForm.due_date || 'on receipt'}</b></li>
              </ul>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" className="flex-1" onClick={() => setTermsDialog(false)}>Cancel</Button>
              <Button onClick={handleReceiveOnTerms} disabled={saving}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white"
                data-testid="confirm-terms-btn">
                {saving ? <RefreshCw size={14} className="animate-spin mr-1.5" /> : <Check size={14} className="mr-1.5" />}
                Confirm & Receive
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── PO DETAIL DIALOG ─────────────────────────────────────────── */}
      <Dialog open={detailDialog} onOpenChange={setDetailDialog}>
        <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>PO Detail — {detailPO?.po_number}</DialogTitle></DialogHeader>
          {detailPO && (
            <div className="space-y-4 mt-2">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div><span className="text-slate-500">Vendor:</span> <b>{detailPO.vendor}</b></div>
                <div><span className="text-slate-500">Date:</span> {detailPO.purchase_date}</div>
                {detailPO.dr_number && <div><span className="text-slate-500">DR #:</span> <b>{detailPO.dr_number}</b></div>}
                <div><span className="text-slate-500">Status:</span> <Badge className={`${statusColor(detailPO.status)} text-[10px]`}>{detailPO.status}</Badge></div>
                <div className="flex items-center gap-1"><span className="text-slate-500">Payment:</span>
                  <Badge className={`text-[10px] ${payStatusColor(detailPO.payment_status || 'unpaid')}`}>
                    {detailPO.po_type === 'cash' || detailPO.payment_method === 'cash' ? 'Cash' : 'Terms'} · {detailPO.payment_status || 'unpaid'}
                  </Badge>
                </div>
                {detailPO.balance > 0 && <div><span className="text-slate-500">Balance:</span> <b className="text-red-600">{formatPHP(detailPO.balance)}</b></div>}
                {detailPO.due_date && <div><span className="text-slate-500">Due:</span> {detailPO.due_date}</div>}
              </div>
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
                  {detailPO.items?.map((item, i) => (
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
              <div className="text-sm space-y-1 border-t pt-3">
                <div className="flex justify-between"><span className="text-slate-500">Subtotal</span><span className="font-mono">{formatPHP(detailPO.line_subtotal || detailPO.subtotal)}</span></div>
                {detailPO.overall_discount_amount > 0 && <div className="flex justify-between text-emerald-600"><span>Overall Discount</span><span className="font-mono">-{formatPHP(detailPO.overall_discount_amount)}</span></div>}
                {detailPO.freight > 0 && <div className="flex justify-between"><span className="text-slate-500">Freight</span><span className="font-mono">{formatPHP(detailPO.freight)}</span></div>}
                {detailPO.tax_amount > 0 && <div className="flex justify-between"><span className="text-slate-500">VAT ({detailPO.tax_rate}%)</span><span className="font-mono">{formatPHP(detailPO.tax_amount)}</span></div>}
                <div className="flex justify-between font-bold text-base pt-1 border-t"><span>Grand Total</span><span className="font-mono text-[#1A4D2E]">{formatPHP(detailPO.grand_total || detailPO.subtotal)}</span></div>
              </div>
              {detailPO.notes && <p className="text-sm text-slate-500 border-t pt-2">Notes: {detailPO.notes}</p>}
              {detailPO.payment_history?.length > 0 && (
                <div className="border-t pt-2">
                  <p className="text-xs font-semibold uppercase text-slate-400 mb-2">Payment History</p>
                  {detailPO.payment_history.map((pay, i) => (
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
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ── CREATE PRODUCT DIALOG ────────────────────────────────────── */}
      <Dialog open={createProdDialog} onOpenChange={setCreateProdDialog}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Create New Product</DialogTitle></DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="grid grid-cols-2 gap-4">
              <div><Label>SKU</Label><Input value={newProdForm.sku} onChange={e => setNewProdForm(f => ({ ...f, sku: e.target.value }))} placeholder="e.g. LAN-250G" /></div>
              <div><Label>Product Name</Label><Input value={newProdForm.name} onChange={e => setNewProdForm(f => ({ ...f, name: e.target.value }))} /></div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div><Label>Category</Label>
                <Select value={newProdForm.category} onValueChange={v => setNewProdForm(f => ({ ...f, category: v }))}>
                  <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {['Pesticide','Fertilizers','Seeds','Feeds','Tools','Veterinary','Customized','Others'].map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div><Label>Unit</Label><Input value={newProdForm.unit} onChange={e => setNewProdForm(f => ({ ...f, unit: e.target.value }))} /></div>
              <div><Label>Cost Price</Label><Input type="number" value={newProdForm.cost_price} onChange={e => setNewProdForm(f => ({ ...f, cost_price: parseFloat(e.target.value) || 0 }))} /></div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setCreateProdDialog(false)}>Cancel</Button>
              <Button onClick={saveNewProduct} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">Create Product</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── SUPPLIER HISTORY DIALOG ──────────────────────────────────── */}
      <Dialog open={historyDialog} onOpenChange={setHistoryDialog}>
        <DialogContent className="sm:max-w-3xl max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Supplier History — {historyVendor}</DialogTitle></DialogHeader>
          <div className="space-y-3 mt-2">
            {historyPOs.map(po => (
              <Card key={po.id} className={`border-slate-200 ${po.payment_status === 'paid' ? 'opacity-70' : ''}`}>
                <CardContent className="p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <button onClick={() => { setDetailPO(po); setDetailDialog(true); }}
                        className="font-mono text-sm text-blue-600 hover:underline font-bold">{po.po_number}</button>
                      <Badge className={`text-[10px] ${statusColor(po.status)}`}>{po.status}</Badge>
                      <Badge className={`text-[10px] ${payStatusColor(po.payment_status || 'unpaid')}`}>{po.payment_status || 'unpaid'}</Badge>
                    </div>
                    <span className="text-lg font-bold font-mono">{formatPHP(poTotal(po))}</span>
                  </div>
                  <div className="text-xs text-slate-500">
                    Date: {po.purchase_date} · Items: {po.items?.length || 0}
                    {po.dr_number && <> · DR: <span className="font-mono">{po.dr_number}</span></>}
                    {po.balance > 0 && <> · <span className="text-red-600 font-semibold">Balance: {formatPHP(po.balance)}</span></>}
                    {po.due_date && po.payment_status !== 'paid' && <> · Due: {po.due_date}</>}
                  </div>
                  {po.payment_history?.length > 0 && (
                    <div className="mt-1 bg-slate-50 rounded p-2 space-y-0.5">
                      {po.payment_history.map((pay, i) => (
                        <div key={i} className="flex items-center justify-between text-xs">
                          <span className="text-slate-500">{pay.date} · {pay.method} · {pay.fund_source}</span>
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
