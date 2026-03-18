import { useState, useEffect, useRef } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Separator } from '../components/ui/separator';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Textarea } from '../components/ui/textarea';
import SmartProductSearch from '../components/SmartProductSearch';
import { Plus, Trash2, Save, CreditCard, Lock, Eye, EyeOff, ChevronDown, X } from 'lucide-react';
import { toast } from 'sonner';

const EMPTY_LINE = {
  product_id: '', product_name: '', description: '', quantity: 1,
  rate: 0, original_rate: 0, cost_price: 0,
  discount_type: 'percent', discount_value: 0, is_repack: false, price_scheme: ''
};

export default function SalesOrderPage() {
  const { currentBranch, user } = useAuth();
  const [customers, setCustomers] = useState([]);
  const [users, setUsers] = useState([]);
  const [terms, setTerms] = useState([]);
  const [prefixes, setPrefixes] = useState({});
  const [schemes, setSchemes] = useState([]);

  const [header, setHeader] = useState({
    customer_id: '', customer_name: '', customer_contact: '', customer_phone: '',
    customer_address: '', shipping_address: '', location: '', mod: '', check_number: '',
    terms: 'COD', terms_days: 0, customer_po: '', sales_rep_id: '', sales_rep_name: '',
    prefix: 'SI', order_date: new Date().toISOString().slice(0, 10),
    invoice_date: new Date().toISOString().slice(0, 10), req_ship_date: '',
    sale_type: 'walk_in', interest_rate: 0, payment_method: 'Cash',
    fund_source: 'cashier', price_scheme: 'retail', notes: '',
  });

  const [lines, setLines] = useState([{ ...EMPTY_LINE }]);
  const [freight, setFreight] = useState(0);
  const [overallDiscount, setOverallDiscount] = useState(0);
  const [amountPaid, setAmountPaid] = useState(0);
  const [saving, setSaving] = useState(false);
  const [payDropdown, setPayDropdown] = useState(false);

  // dialogs
  const [priceChangeDialog, setPriceChangeDialog] = useState(false);
  const [priceChangeInfo, setPriceChangeInfo] = useState(null);
  const [createProductDialog, setCreateProductDialog] = useState(false);
  const [newProductName, setNewProductName] = useState('');
  const [newProductForm, setNewProductForm] = useState({ sku: '', name: '', category: 'Pesticide', unit: 'Box', cost_price: 0, prices: {}, product_type: 'stockable', starting_inventory: 0 });
  const [custSearch, setCustSearch] = useState('');
  const [custDropdownOpen, setCustDropdownOpen] = useState(false);
  const [isNewCustomer, setIsNewCustomer] = useState(false);
  const [saveCustomerDialog, setSaveCustomerDialog] = useState(false);
  const [newCustForm, setNewCustForm] = useState({ name: '', phone: '', address: '', price_scheme: 'retail', interest_rate: 0 });
  const [creditPinDialog, setCreditPinDialog] = useState(false);
  const [managerPin, setManagerPin] = useState('');
  const [showPin, setShowPin] = useState(false);
  const [pinVerifying, setPinVerifying] = useState(false);

  const qtyRefs = useRef([]);
  const payRef = useRef(null);

  useEffect(() => {
    api.get('/customers', { params: { limit: 500 } }).then(r => setCustomers(r.data.customers)).catch(() => {});
    api.get('/settings/terms-options').then(r => setTerms(r.data)).catch(() => {});
    api.get('/settings/invoice-prefixes').then(r => setPrefixes(r.data)).catch(() => {});
    api.get('/users').then(r => setUsers(r.data)).catch(() => setUsers([]));
    api.get('/price-schemes').then(r => setSchemes(r.data)).catch(() => {});
  }, []);

  // close pay dropdown on outside click
  useEffect(() => {
    const handler = (e) => { if (payRef.current && !payRef.current.contains(e.target)) setPayDropdown(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  /* ── Customer ── */
  const selectCustomer = (custId) => {
    const c = customers.find(x => x.id === custId);
    if (c) {
      setHeader(h => ({
        ...h, customer_id: c.id, customer_name: c.name,
        customer_contact: c.phone || '', customer_phone: c.phone || '',
        customer_address: c.address || '', interest_rate: c.interest_rate || 0,
        price_scheme: c.price_scheme || 'retail',
      }));
      setCustSearch(c.name);
      setIsNewCustomer(false);
      setCustDropdownOpen(false);
    }
  };

  const handleCustInput = (val) => {
    setCustSearch(val);
    setCustDropdownOpen(val.length > 0);
    setHeader(h => ({ ...h, customer_id: '', customer_name: val }));
    const match = customers.find(c => c.name.toLowerCase() === val.toLowerCase());
    if (match) { selectCustomer(match.id); } else { setIsNewCustomer(val.length > 0); }
  };

  const filteredCusts = custSearch
    ? customers.filter(c => c.name.toLowerCase().includes(custSearch.toLowerCase())).slice(0, 8)
    : [];

  const openSaveCustomer = () => {
    setNewCustForm({ name: header.customer_name, phone: header.customer_phone, address: header.customer_address, price_scheme: 'retail', interest_rate: 0 });
    setSaveCustomerDialog(true);
  };

  const handleSaveCustomer = async () => {
    try {
      const res = await api.post('/customers', newCustForm);
      toast.success(`Customer "${res.data.name}" saved!`);
      setSaveCustomerDialog(false);
      setCustomers(prev => [...prev, res.data]);
      setHeader(h => ({ ...h, customer_id: res.data.id, customer_name: res.data.name }));
      setIsNewCustomer(false);
    } catch (e) { toast.error(e.response?.data?.detail || 'Error saving customer'); }
  };

  const selectTerm = (label) => {
    const t = terms.find(x => x.label === label);
    setHeader(h => ({ ...h, terms: label, terms_days: t?.days || 0 }));
  };

  const dueDate = (() => {
    if (!header.terms_days) return header.order_date;
    const d = new Date(header.order_date);
    d.setDate(d.getDate() + header.terms_days);
    return d.toISOString().slice(0, 10);
  })();

  /* ── Lines ── */
  const handleCreateNewProduct = (name) => {
    setNewProductName(name);
    setNewProductForm({ sku: '', name, category: 'Pesticide', unit: 'Box', cost_price: 0, prices: {}, product_type: 'stockable', starting_inventory: 0 });
    setCreateProductDialog(true);
  };

  const saveNewProduct = async () => {
    try {
      const res = await api.post('/products', newProductForm);
      if (newProductForm.starting_inventory > 0 && currentBranch) {
        await api.post('/inventory/set', { product_id: res.data.id, branch_id: currentBranch.id, quantity: newProductForm.starting_inventory });
      }
      toast.success(`Product "${res.data.name}" created!`);
      setCreateProductDialog(false);
    } catch (e) { toast.error(e.response?.data?.detail || 'Error creating product'); }
  };

  const handleProductSelect = (index, product) => {
    const scheme = header.price_scheme || customers.find(c => c.id === header.customer_id)?.price_scheme || 'retail';
    const rate = product.prices?.[scheme] || product.prices?.retail || 0;
    const newLines = [...lines];
    newLines[index] = {
      ...newLines[index], product_id: product.id, product_name: product.name,
      description: product.description || '', rate, original_rate: rate,
      cost_price: product.cost_price || 0, price_scheme: scheme,
      is_repack: product.is_repack || false,
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

  const validateLineRate = (index) => {
    const line = lines[index];
    if (!line || !line.product_id || !line.cost_price) return;
    const rate = parseFloat(line.rate) || 0;
    if (rate > 0 && rate < line.cost_price) {
      toast.error(`Cannot sell below capital (₱${line.cost_price.toFixed(2)}). Reverting.`);
      const newLines = [...lines];
      newLines[index] = { ...newLines[index], rate: newLines[index].original_rate };
      setLines(newLines);
      return;
    }
    if (rate !== line.original_rate && rate > 0 && line.original_rate > 0) {
      setPriceChangeInfo({ index, product_id: line.product_id, product_name: line.product_name, scheme: line.price_scheme, old_price: line.original_rate, new_price: rate });
      setPriceChangeDialog(true);
    }
  };

  const confirmPriceChange = async (keepChange) => {
    if (keepChange && priceChangeInfo) {
      try {
        await api.put(`/products/${priceChangeInfo.product_id}/update-price`, { scheme: priceChangeInfo.scheme, price: priceChangeInfo.new_price });
        toast.success(`${priceChangeInfo.scheme} price updated to ${formatPHP(priceChangeInfo.new_price)}`);
        const newLines = [...lines];
        newLines[priceChangeInfo.index] = { ...newLines[priceChangeInfo.index], original_rate: priceChangeInfo.new_price };
        setLines(newLines);
      } catch (e) { toast.error(e.response?.data?.detail || 'Failed to update price'); }
    }
    setPriceChangeDialog(false);
    setPriceChangeInfo(null);
  };

  const removeLine = (index) => {
    if (lines.length <= 1) return;
    setLines(lines.filter((_, i) => i !== index));
  };

  const addLine = () => setLines(prev => [...prev, { ...EMPTY_LINE }]);

  /* ── Totals ── */
  const lineTotal = (line) => {
    const base = line.quantity * line.rate;
    const disc = line.discount_type === 'percent' ? base * line.discount_value / 100 : line.discount_value;
    return Math.max(0, base - disc);
  };
  const subtotal = lines.reduce((s, l) => s + lineTotal(l), 0);
  const grandTotal = subtotal + freight - overallDiscount;
  const balance = grandTotal - amountPaid;

  /* ── Save / Complete ── */
  const handleSaveAs = async (type, approvedBy = null) => {
    const validLines = lines.filter(l => l.product_id);
    if (!validLines.length) { toast.error('Add at least one product'); return; }
    if (!currentBranch) { toast.error('Select a branch'); return; }
    if (type === 'credit' && !approvedBy) {
      setManagerPin(''); setShowPin(false); setCreditPinDialog(true); return;
    }
    setSaving(true);
    try {
      const paid = type === 'paid' ? grandTotal : amountPaid;
      const data = {
        ...header, branch_id: currentBranch.id, items: validLines, freight,
        overall_discount: overallDiscount, amount_paid: paid, due_date: dueDate,
        payment_method: type === 'paid' ? (header.payment_method || 'Cash') : 'Credit',
        approved_by: approvedBy || undefined,
      };
      const res = await api.post('/invoices', data);
      toast.success(type === 'paid'
        ? `Invoice ${res.data.invoice_number} — Fully Paid!`
        : `Invoice ${res.data.invoice_number} — Saved (Balance: ${formatPHP(res.data.balance)})`
      );
      // reset form
      setLines([{ ...EMPTY_LINE }]);
      setFreight(0); setOverallDiscount(0); setAmountPaid(0);
      setHeader(h => ({
        ...h, customer_id: '', customer_name: '', customer_contact: '',
        customer_phone: '', customer_address: '', shipping_address: '',
        location: '', mod: '', check_number: '', customer_po: '', notes: '', req_ship_date: '',
      }));
      setCustSearch(''); setIsNewCustomer(false);
    } catch (e) { toast.error(e.response?.data?.detail || 'Error creating invoice'); }
    setSaving(false);
  };

  const verifyCreditPin = async () => {
    if (!managerPin) { toast.error('Enter authorization PIN'); return; }
    setPinVerifying(true);
    try {
      const res = await api.post('/auth/verify-manager-pin', {
        pin: managerPin.trim(), action_key: 'credit_sale_approval',
        context: {
          type: 'credit_sale', description: `Credit invoice for ${header.customer_name || 'Walk-in'}`,
          amount: grandTotal, customer_name: header.customer_name || 'Walk-in',
          payment_type: 'credit', branch_id: currentBranch?.id, branch_name: currentBranch?.name,
        }
      });
      if (res.data.valid) {
        toast.success(`Approved by ${res.data.manager_name}`);
        setCreditPinDialog(false); setManagerPin('');
        await handleSaveAs('credit', res.data.manager_name);
      } else { toast.error(res.data.detail || 'Invalid PIN / TOTP'); }
    } catch (e) { toast.error(e.response?.data?.detail || 'Verification failed'); }
    setPinVerifying(false);
  };

  /* ── Render ── */
  return (
    <div className="space-y-0 animate-fadeIn" data-testid="sales-order-page">

      {/* ── Top Action Bar ── */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>New Sales Order</h1>
          <p className="text-xs text-slate-400">{currentBranch?.name} · {header.order_date}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="text-slate-500 border-slate-200"
            onClick={() => {
              setLines([{ ...EMPTY_LINE }]); setFreight(0); setOverallDiscount(0); setAmountPaid(0);
              setHeader(h => ({ ...h, customer_id: '', customer_name: '', customer_contact: '', customer_phone: '', customer_address: '', shipping_address: '', location: '', mod: '', check_number: '', customer_po: '', notes: '', req_ship_date: '' }));
              setCustSearch(''); setIsNewCustomer(false);
            }}>
            <X size={14} className="mr-1" /> Cancel Order
          </Button>

          {/* Complete & Pay split button */}
          <div className="relative flex" ref={payRef}>
            <Button
              data-testid="save-paid-btn"
              onClick={() => { setPayDropdown(false); handleSaveAs('paid'); }}
              disabled={saving}
              className="bg-[#1A4D2E] hover:bg-[#14532d] text-white rounded-r-none border-r border-[#0f3320] pr-3"
              size="sm"
            >
              <CreditCard size={14} className="mr-1.5" />
              {saving ? 'Saving...' : 'Complete & Pay'}
            </Button>
            <Button
              onClick={() => setPayDropdown(v => !v)}
              disabled={saving}
              className="bg-[#1A4D2E] hover:bg-[#14532d] text-white rounded-l-none px-2"
              size="sm"
            >
              <ChevronDown size={14} />
            </Button>
            {payDropdown && (
              <div className="absolute right-0 top-full mt-1 z-50 bg-white border border-slate-200 rounded-lg shadow-lg w-44 py-1">
                <button className="w-full text-left px-3 py-2 text-sm hover:bg-slate-50 flex items-center gap-2"
                  onClick={() => { setPayDropdown(false); handleSaveAs('paid'); }}>
                  <CreditCard size={13} className="text-emerald-600" /> Fully Paid
                </button>
                <button className="w-full text-left px-3 py-2 text-sm hover:bg-slate-50 flex items-center gap-2"
                  onClick={() => { setPayDropdown(false); handleSaveAs('credit'); }}>
                  <Save size={13} className="text-amber-600" /> Save as Invoice (Credit)
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Header Card ── */}
      <Card className="border-slate-200 rounded-none rounded-t-lg">
        <CardContent className="p-0">

          {/* Row 1 — Customer + Order Metadata */}
          <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-slate-100">

            {/* Left: Customer info */}
            <div className="p-4 space-y-3">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">Customer</p>

              {/* Customer search */}
              <div className="relative">
                <div className="flex gap-1.5">
                  <Input
                    data-testid="invoice-customer"
                    className="h-9 font-medium"
                    value={custSearch}
                    placeholder="Search customer..."
                    onChange={e => handleCustInput(e.target.value)}
                    onFocus={() => { if (custSearch) setCustDropdownOpen(true); }}
                    onBlur={() => setTimeout(() => setCustDropdownOpen(false), 200)}
                  />
                  {isNewCustomer && !header.customer_id && (
                    <Button size="sm" variant="outline" className="h-9 text-xs text-blue-600 border-blue-200 shrink-0" onClick={openSaveCustomer}>
                      <Plus size={11} className="mr-1" /> Save
                    </Button>
                  )}
                </div>
                {custDropdownOpen && filteredCusts.length > 0 && (
                  <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                    {filteredCusts.map(c => (
                      <button key={c.id} className="w-full text-left px-3 py-2 text-sm hover:bg-slate-50 border-b border-slate-50 last:border-0"
                        onMouseDown={() => selectCustomer(c.id)}>
                        <span className="font-medium">{c.name}</span>
                        <span className="text-xs text-slate-400 ml-2">{c.phone || ''}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-[10px] text-slate-400 uppercase tracking-wide">Contact</Label>
                  <Input className="h-8 text-sm mt-0.5" value={header.customer_contact}
                    onChange={e => setHeader(h => ({ ...h, customer_contact: e.target.value }))} />
                </div>
                <div>
                  <Label className="text-[10px] text-slate-400 uppercase tracking-wide">Phone</Label>
                  <Input className="h-8 text-sm mt-0.5" value={header.customer_phone}
                    onChange={e => setHeader(h => ({ ...h, customer_phone: e.target.value }))} />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-[10px] text-slate-400 uppercase tracking-wide">Billing Address</Label>
                  <Input className="h-8 text-sm mt-0.5" value={header.customer_address}
                    onChange={e => setHeader(h => ({ ...h, customer_address: e.target.value }))} />
                </div>
                <div>
                  <Label className="text-[10px] text-slate-400 uppercase tracking-wide">Shipping Address</Label>
                  <Input className="h-8 text-sm mt-0.5" placeholder="(same as billing)" value={header.shipping_address}
                    onChange={e => setHeader(h => ({ ...h, shipping_address: e.target.value }))} />
                </div>
              </div>
            </div>

            {/* Right: Order details */}
            <div className="p-4 space-y-3">
              <div className="flex items-start justify-between">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">Order Details</p>
                <div className="text-right">
                  <span className="inline-block text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                    Open
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <Label className="text-[10px] text-slate-400 uppercase tracking-wide">Prefix</Label>
                  <Select value={header.prefix} onValueChange={v => setHeader(h => ({ ...h, prefix: v }))}>
                    <SelectTrigger data-testid="invoice-prefix" className="h-8 text-sm mt-0.5"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {Object.entries(prefixes).map(([k, v]) => <SelectItem key={k} value={v}>{v}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-[10px] text-slate-400 uppercase tracking-wide">Order Date</Label>
                  <Input className="h-8 text-sm mt-0.5" type="date" value={header.order_date}
                    onChange={e => setHeader(h => ({ ...h, order_date: e.target.value }))} />
                </div>
                <div>
                  <Label className="text-[10px] text-slate-400 uppercase tracking-wide">Invoice Date</Label>
                  <Input className="h-8 text-sm mt-0.5" type="date" value={header.invoice_date}
                    onChange={e => setHeader(h => ({ ...h, invoice_date: e.target.value }))} />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-[10px] text-slate-400 uppercase tracking-wide">Terms</Label>
                  <Select value={header.terms} onValueChange={selectTerm}>
                    <SelectTrigger data-testid="invoice-terms" className="h-8 text-sm mt-0.5"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {terms.map(t => <SelectItem key={t.label} value={t.label}>{t.label}</SelectItem>)}
                      <SelectItem value="Custom">Custom</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-[10px] text-slate-400 uppercase tracking-wide">P.O. #</Label>
                  <Input className="h-8 text-sm mt-0.5" value={header.customer_po}
                    onChange={e => setHeader(h => ({ ...h, customer_po: e.target.value }))} />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-[10px] text-slate-400 uppercase tracking-wide">Sales Rep</Label>
                  <Select value={header.sales_rep_id || 'none'} onValueChange={v => {
                    const u = users.find(x => x.id === v);
                    setHeader(h => ({ ...h, sales_rep_id: v === 'none' ? '' : v, sales_rep_name: u?.full_name || u?.username || '' }));
                  }}>
                    <SelectTrigger className="h-8 text-sm mt-0.5"><SelectValue placeholder="Select" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">None</SelectItem>
                      {users.map(u => <SelectItem key={u.id} value={u.id}>{u.full_name || u.username}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-[10px] text-slate-400 uppercase tracking-wide">Location</Label>
                  <Input className="h-8 text-sm mt-0.5" value={header.location}
                    onChange={e => setHeader(h => ({ ...h, location: e.target.value }))} />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <Label className="text-[10px] text-slate-400 uppercase tracking-wide">MOD</Label>
                  <Input className="h-8 text-sm mt-0.5" placeholder="e.g. Delivery" value={header.mod}
                    onChange={e => setHeader(h => ({ ...h, mod: e.target.value }))} />
                </div>
                <div>
                  <Label className="text-[10px] text-slate-400 uppercase tracking-wide">Check #</Label>
                  <Input className="h-8 text-sm mt-0.5" value={header.check_number}
                    onChange={e => setHeader(h => ({ ...h, check_number: e.target.value }))} />
                </div>
                <div>
                  <Label className="text-[10px] text-slate-400 uppercase tracking-wide">Type</Label>
                  <Select value={header.sale_type} onValueChange={v => setHeader(h => ({ ...h, sale_type: v }))}>
                    <SelectTrigger className="h-8 text-sm mt-0.5"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="walk_in">Walk-in</SelectItem>
                      <SelectItem value="delivery">Delivery</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

            </div>
          </div>

        </CardContent>
      </Card>

      {/* ── Line Items Table ── */}
      <Card className="border-slate-200 rounded-none border-t-0">
        <CardContent className="p-0">
          <table className="w-full text-sm" data-testid="invoice-lines-table">
            <thead>
              <tr className="bg-slate-50 border-y border-slate-200">
                <th className="text-left px-3 py-2 text-[10px] uppercase text-slate-400 font-semibold tracking-wide w-8">#</th>
                <th className="text-left px-3 py-2 text-[10px] uppercase text-slate-400 font-semibold tracking-wide min-w-[260px]">Item</th>
                <th className="text-left px-3 py-2 text-[10px] uppercase text-slate-400 font-semibold tracking-wide min-w-[140px]">Description</th>
                <th className="text-right px-3 py-2 text-[10px] uppercase text-slate-400 font-semibold tracking-wide w-20">Quantity</th>
                <th className="text-right px-3 py-2 text-[10px] uppercase text-slate-400 font-semibold tracking-wide w-28">Unit Price</th>
                <th className="text-right px-3 py-2 text-[10px] uppercase text-slate-400 font-semibold tracking-wide w-28">Discount</th>
                <th className="text-right px-3 py-2 text-[10px] uppercase text-slate-400 font-semibold tracking-wide w-28">Sub-Total</th>
                <th className="w-8"></th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line, i) => (
                <tr key={i} className="border-b border-slate-100 hover:bg-slate-50/60 transition-colors" data-testid={`line-row-${i}`}>
                  <td className="px-3 py-1.5 text-xs text-slate-400">{i + 1}</td>
                  <td className="px-2 py-1.5">
                    {line.product_id ? (
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">{line.product_name}</span>
                        <button onClick={() => updateLine(i, 'product_id', '')}
                          className="text-slate-300 hover:text-red-400 transition-colors">
                          <X size={12} />
                        </button>
                      </div>
                    ) : (
                      <SmartProductSearch branchId={currentBranch?.id} onSelect={(p) => handleProductSelect(i, p)} onCreateNew={handleCreateNewProduct} />
                    )}
                  </td>
                  <td className="px-2 py-1.5">
                    <input
                      className="w-full h-8 px-2 text-sm border border-transparent hover:border-slate-200 focus:border-[#1A4D2E] focus:outline-none rounded transition-colors bg-transparent"
                      value={line.description}
                      onChange={e => updateLine(i, 'description', e.target.value)}
                    />
                  </td>
                  <td className="px-2 py-1.5">
                    <input
                      ref={el => qtyRefs.current[i] = el}
                      type="number" min="0"
                      className="w-full h-8 px-2 text-sm text-right border border-transparent hover:border-slate-200 focus:border-[#1A4D2E] focus:outline-none rounded transition-colors bg-transparent"
                      value={line.quantity}
                      onChange={e => updateLine(i, 'quantity', parseFloat(e.target.value) || 0)}
                    />
                  </td>
                  <td className="px-2 py-1.5">
                    <input
                      type="number"
                      className="w-full h-8 px-2 text-sm text-right border border-transparent hover:border-slate-200 focus:border-[#1A4D2E] focus:outline-none rounded transition-colors bg-transparent"
                      value={line.rate}
                      onChange={e => updateLine(i, 'rate', parseFloat(e.target.value) || 0)}
                      onBlur={() => validateLineRate(i)}
                    />
                  </td>
                  <td className="px-2 py-1.5">
                    <div className="flex items-center gap-1">
                      <input
                        type="number"
                        className="w-14 h-8 px-2 text-sm text-right border border-transparent hover:border-slate-200 focus:border-[#1A4D2E] focus:outline-none rounded transition-colors bg-transparent"
                        value={line.discount_value}
                        onChange={e => updateLine(i, 'discount_value', parseFloat(e.target.value) || 0)}
                      />
                      <select
                        className="h-8 text-xs border border-transparent hover:border-slate-200 focus:border-[#1A4D2E] rounded bg-transparent focus:outline-none"
                        value={line.discount_type}
                        onChange={e => updateLine(i, 'discount_type', e.target.value)}
                      >
                        <option value="percent">%</option>
                        <option value="amount">₱</option>
                      </select>
                    </div>
                  </td>
                  <td className="px-3 py-1.5 text-right font-semibold text-sm text-slate-700">
                    {line.product_id ? formatPHP(lineTotal(line)) : ''}
                  </td>
                  <td className="px-1 py-1.5">
                    {lines.length > 1 && line.product_id && (
                      <button onClick={() => removeLine(i)}
                        className="text-slate-300 hover:text-red-400 transition-colors p-1">
                        <Trash2 size={13} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Add line button */}
          <div className="px-3 py-2 border-t border-slate-100">
            <button onClick={addLine}
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-[#1A4D2E] transition-colors">
              <Plus size={13} /> Add line item
            </button>
          </div>
        </CardContent>
      </Card>

      {/* ── Bottom Section: Dates | Notes | Totals ── */}
      <Card className="border-slate-200 rounded-none rounded-b-lg border-t-0">
        <CardContent className="p-0">
          <div className="grid grid-cols-1 lg:grid-cols-3 divide-y lg:divide-y-0 lg:divide-x divide-slate-100">

            {/* Dates + Pricing */}
            <div className="p-4 space-y-3">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">Dates & Pricing</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-[10px] text-slate-400 uppercase tracking-wide">Due Date</Label>
                  <Input className="h-8 text-sm mt-0.5 bg-slate-50" value={dueDate} readOnly />
                </div>
                <div>
                  <Label className="text-[10px] text-slate-400 uppercase tracking-wide">Req. Ship Date</Label>
                  <Input className="h-8 text-sm mt-0.5" type="date" value={header.req_ship_date}
                    onChange={e => setHeader(h => ({ ...h, req_ship_date: e.target.value }))} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-[10px] text-slate-400 uppercase tracking-wide">Pricing Scheme</Label>
                  <Select value={header.price_scheme} onValueChange={v => setHeader(h => ({ ...h, price_scheme: v }))}>
                    <SelectTrigger className="h-8 text-sm mt-0.5"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {schemes.map(s => <SelectItem key={s.key} value={s.key}>{s.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-[10px] text-slate-400 uppercase tracking-wide">Payment Method</Label>
                  <Select value={header.payment_method} onValueChange={v => setHeader(h => ({ ...h, payment_method: v }))}>
                    <SelectTrigger className="h-8 text-sm mt-0.5"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Cash">Cash</SelectItem>
                      <SelectItem value="GCash">GCash</SelectItem>
                      <SelectItem value="Maya">Maya</SelectItem>
                      <SelectItem value="Bank Transfer">Bank Transfer</SelectItem>
                      <SelectItem value="Check">Check</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>

            {/* Notes */}
            <div className="p-4 space-y-2">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">Important / Notes</p>
              <Textarea
                className="text-sm resize-none h-[100px] border-slate-200 focus:border-[#1A4D2E]"
                placeholder="Enter order notes, delivery instructions, or reminders..."
                value={header.notes}
                onChange={e => setHeader(h => ({ ...h, notes: e.target.value }))}
              />
            </div>

            {/* Totals */}
            <div className="p-4 space-y-2">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">Summary</p>
              <div className="space-y-1.5">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">Sub-Total</span>
                  <span className="font-medium">{formatPHP(subtotal)}</span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-slate-500">Freight</span>
                  <Input
                    type="number" data-testid="invoice-freight"
                    className="w-28 h-7 text-right text-sm"
                    value={freight}
                    onChange={e => setFreight(parseFloat(e.target.value) || 0)}
                  />
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-slate-500">Discount</span>
                  <Input
                    type="number" data-testid="invoice-discount"
                    className="w-28 h-7 text-right text-sm"
                    value={overallDiscount}
                    onChange={e => setOverallDiscount(parseFloat(e.target.value) || 0)}
                  />
                </div>
                <Separator />
                <div className="flex justify-between text-base font-bold" style={{ fontFamily: 'Manrope' }}>
                  <span>Total</span>
                  <span className="text-[#1A4D2E]">{formatPHP(grandTotal)}</span>
                </div>
                <Separator />
                <div className="flex justify-between items-center text-sm">
                  <span className="text-slate-500">Paid</span>
                  <Input
                    type="number" data-testid="invoice-paid"
                    className="w-28 h-7 text-right text-sm"
                    value={amountPaid}
                    onChange={e => setAmountPaid(parseFloat(e.target.value) || 0)}
                  />
                </div>
                <div className="flex justify-between text-sm font-bold">
                  <span>Balance</span>
                  <span className={balance > 0 ? 'text-amber-600' : 'text-emerald-600'}>
                    {formatPHP(balance)}
                  </span>
                </div>
              </div>
            </div>

          </div>
        </CardContent>
      </Card>

      {/* ── Dialogs (unchanged logic) ── */}

      {/* Price Change */}
      <Dialog open={priceChangeDialog} onOpenChange={(open) => { if (!open) confirmPriceChange(false); }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Price Changed</DialogTitle></DialogHeader>
          {priceChangeInfo && (
            <div className="space-y-4 mt-2">
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm">
                <p className="font-medium">{priceChangeInfo.product_name}</p>
                <p className="mt-1">
                  You changed the <b className="capitalize">{priceChangeInfo.scheme}</b> price from{' '}
                  <b>{formatPHP(priceChangeInfo.old_price)}</b> to <b>{formatPHP(priceChangeInfo.new_price)}</b>
                </p>
              </div>
              <p className="text-sm text-slate-600">Do you want to permanently update the <b className="capitalize">{priceChangeInfo.scheme}</b> price for this product?</p>
              <div className="flex gap-2">
                <Button variant="outline" className="flex-1" onClick={() => confirmPriceChange(false)}>No, just this invoice</Button>
                <Button className="flex-1 bg-[#1A4D2E] hover:bg-[#14532d] text-white" onClick={() => confirmPriceChange(true)} data-testid="confirm-price-update">
                  Yes, update {priceChangeInfo.scheme} price
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Create Product */}
      <Dialog open={createProductDialog} onOpenChange={setCreateProductDialog}>
        <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Create New Product</DialogTitle></DialogHeader>
          <p className="text-sm text-slate-500">Product "{newProductName}" was not found. Create it now:</p>
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
                    {['Pesticide','Fertilizers','Seeds','Feeds','Tools','Veterinary','Customized','Others'].map(c =>
                      <SelectItem key={c} value={c}>{c}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div><Label>Unit</Label><Input value={newProductForm.unit} onChange={e => setNewProductForm(f => ({ ...f, unit: e.target.value }))} placeholder="Box, Bag, Pack" /></div>
              <div><Label>Cost Price</Label><Input type="number" value={newProductForm.cost_price} onChange={e => setNewProductForm(f => ({ ...f, cost_price: parseFloat(e.target.value) || 0 }))} /></div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              {schemes.map(s => (
                <div key={s.id}><Label className="text-xs text-slate-500">{s.name}</Label>
                  <Input type="number" value={newProductForm.prices[s.key] || ''} onChange={e => setNewProductForm(f => ({ ...f, prices: { ...f.prices, [s.key]: parseFloat(e.target.value) || 0 } }))} placeholder="0.00" />
                </div>
              ))}
            </div>
            <div><Label>Starting Inventory ({currentBranch?.name})</Label><Input type="number" value={newProductForm.starting_inventory} onChange={e => setNewProductForm(f => ({ ...f, starting_inventory: parseFloat(e.target.value) || 0 }))} /></div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setCreateProductDialog(false)}>Cancel</Button>
              <Button onClick={saveNewProduct} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">Create Product</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Save New Customer */}
      <Dialog open={saveCustomerDialog} onOpenChange={setSaveCustomerDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Save New Customer</DialogTitle></DialogHeader>
          <div className="space-y-3 mt-2">
            <div><Label>Name</Label><Input value={newCustForm.name} onChange={e => setNewCustForm(f => ({ ...f, name: e.target.value }))} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Phone</Label><Input value={newCustForm.phone} onChange={e => setNewCustForm(f => ({ ...f, phone: e.target.value }))} /></div>
              <div><Label>Price Scheme</Label>
                <Select value={newCustForm.price_scheme} onValueChange={v => setNewCustForm(f => ({ ...f, price_scheme: v }))}>
                  <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                  <SelectContent>{schemes.map(s => <SelectItem key={s.key} value={s.key}>{s.name}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
            <div><Label>Address</Label><Input value={newCustForm.address} onChange={e => setNewCustForm(f => ({ ...f, address: e.target.value }))} /></div>
            <div><Label>Interest Rate (%/mo)</Label><Input type="number" value={newCustForm.interest_rate} onChange={e => setNewCustForm(f => ({ ...f, interest_rate: parseFloat(e.target.value) || 0 }))} /></div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setSaveCustomerDialog(false)}>Cancel</Button>
              <Button onClick={handleSaveCustomer} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">Save Customer</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Credit PIN */}
      <Dialog open={creditPinDialog} onOpenChange={setCreditPinDialog}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
              <Lock size={18} className="text-[#1A4D2E]" /> Credit Sale Authorization
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-1">
            <p className="text-sm text-slate-600">Credit sales require manager or admin authorization.</p>
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
              <p className="text-xs text-slate-500">Amount</p>
              <p className="text-lg font-bold font-mono text-[#1A4D2E]">{formatPHP(grandTotal)}</p>
              <p className="text-xs text-slate-500 mt-1">Customer: {header.customer_name || 'Walk-in'}</p>
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600 mb-1 block">Authorization PIN</label>
              <div className="relative">
                <input
                  type={showPin ? 'text' : 'password'}
                  value={managerPin}
                  onChange={e => setManagerPin(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && verifyCreditPin()}
                  placeholder="Manager PIN or TOTP code..."
                  className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm pr-10 focus:outline-none focus:ring-2 focus:ring-[#1A4D2E]/30"
                  data-testid="credit-pin-input"
                  autoFocus
                />
                <button onClick={() => setShowPin(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                  {showPin ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setCreditPinDialog(false)} className="flex-1">Cancel</Button>
              <Button onClick={verifyCreditPin} disabled={pinVerifying || !managerPin}
                className="flex-1 bg-[#1A4D2E] hover:bg-[#14532d] text-white" data-testid="credit-pin-submit">
                {pinVerifying ? 'Verifying...' : 'Authorize & Save'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

    </div>
  );
}
