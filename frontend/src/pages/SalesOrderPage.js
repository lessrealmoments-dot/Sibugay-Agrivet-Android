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
import SmartProductSearch from '../components/SmartProductSearch';
import { FileText, Plus, Trash2, Save, AlertTriangle, CreditCard } from 'lucide-react';
import { toast } from 'sonner';

const EMPTY_LINE = { product_id: '', product_name: '', description: '', quantity: 1, rate: 0, original_rate: 0, cost_price: 0, discount_type: 'amount', discount_value: 0, is_repack: false, price_scheme: '' };

export default function SalesOrderPage() {
  const { currentBranch, user } = useAuth();
  const [customers, setCustomers] = useState([]);
  const [users, setUsers] = useState([]);
  const [terms, setTerms] = useState([]);
  const [prefixes, setPrefixes] = useState({});
  const [header, setHeader] = useState({
    customer_id: '', customer_name: '', customer_contact: '', customer_phone: '', customer_address: '',
    terms: 'COD', terms_days: 0, customer_po: '', sales_rep_id: '', sales_rep_name: '',
    prefix: 'SI', order_date: new Date().toISOString().slice(0, 10),
    invoice_date: new Date().toISOString().slice(0, 10), sale_type: 'walk_in',
    interest_rate: 0, payment_method: 'Cash', fund_source: 'cashier',
  });
  const [lines, setLines] = useState([{ ...EMPTY_LINE }]);
  const [freight, setFreight] = useState(0);
  const [overallDiscount, setOverallDiscount] = useState(0);
  const [amountPaid, setAmountPaid] = useState(0);
  const [saving, setSaving] = useState(false);
  const [priceChangeDialog, setPriceChangeDialog] = useState(false);
  const [priceChangeInfo, setPriceChangeInfo] = useState(null);
  const [createProductDialog, setCreateProductDialog] = useState(false);
  const [newProductName, setNewProductName] = useState('');
  const [newProductForm, setNewProductForm] = useState({ sku: '', name: '', category: 'General', unit: 'Box', cost_price: 0, prices: {}, product_type: 'stockable', starting_inventory: 0 });
  const qtyRefs = useRef([]);

  useEffect(() => {
    api.get('/customers', { params: { limit: 500 } }).then(r => setCustomers(r.data.customers)).catch(() => {});
    api.get('/settings/terms-options').then(r => setTerms(r.data)).catch(() => {});
    api.get('/settings/invoice-prefixes').then(r => setPrefixes(r.data)).catch(() => {});
    api.get('/users').then(r => setUsers(r.data)).catch(() => setUsers([]));
  }, []);

  const [schemes, setSchemes] = useState([]);
  useEffect(() => { api.get('/price-schemes').then(r => setSchemes(r.data)).catch(() => {}); }, []);

  const handleCreateNewProduct = (name) => {
    setNewProductName(name);
    setNewProductForm({ sku: '', name, category: 'General', unit: 'Box', cost_price: 0, prices: {}, product_type: 'stockable', starting_inventory: 0 });
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

  const selectCustomer = (custId) => {
    const c = customers.find(x => x.id === custId);
    if (c) {
      setHeader(h => ({ ...h, customer_id: c.id, customer_name: c.name,
        customer_contact: c.phone || '', customer_phone: c.phone || '', customer_address: c.address || '',
        interest_rate: c.interest_rate || 0 }));
    }
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

  const handleProductSelect = (index, product) => {
    const newLines = [...lines];
    const scheme = customers.find(c => c.id === header.customer_id)?.price_scheme || 'retail';
    const rate = product.prices?.[scheme] || product.prices?.retail || 0;
    newLines[index] = {
      ...newLines[index],
      product_id: product.id, product_name: product.name,
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
    const line = newLines[index];
    newLines[index] = { ...line, [field]: value };
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
    // If price changed from original, ask to update scheme
    if (rate !== line.original_rate && rate > 0 && line.original_rate > 0) {
      setPriceChangeInfo({ index, product_id: line.product_id, product_name: line.product_name, scheme: line.price_scheme, old_price: line.original_rate, new_price: rate });
      setPriceChangeDialog(true);
    }
  };

  const confirmPriceChange = async (keepChange) => {
    if (keepChange && priceChangeInfo) {
      try {
        await api.put(`/products/${priceChangeInfo.product_id}/update-price`, {
          scheme: priceChangeInfo.scheme, price: priceChangeInfo.new_price
        });
        toast.success(`${priceChangeInfo.scheme} price updated to ${formatPHP(priceChangeInfo.new_price)}`);
        // Update original_rate so we don't ask again
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

  const lineTotal = (line) => {
    const base = line.quantity * line.rate;
    const disc = line.discount_type === 'percent' ? base * line.discount_value / 100 : line.discount_value;
    return Math.max(0, base - disc);
  };

  const subtotal = lines.reduce((s, l) => s + lineTotal(l), 0);
  const grandTotal = subtotal + freight - overallDiscount;
  const balance = grandTotal - amountPaid;

  const handleSaveAs = async (type) => {
    const validLines = lines.filter(l => l.product_id);
    if (!validLines.length) { toast.error('Add at least one product'); return; }
    if (!currentBranch) { toast.error('Select a branch'); return; }
    setSaving(true);
    try {
      const paid = type === 'paid' ? grandTotal : amountPaid;
      const data = {
        ...header, branch_id: currentBranch.id, items: validLines, freight, overall_discount: overallDiscount,
        amount_paid: paid, due_date: dueDate,
        payment_method: type === 'paid' ? (header.payment_method || 'Cash') : 'Credit',
      };
      const res = await api.post('/invoices', data);
      toast.success(type === 'paid'
        ? `Invoice ${res.data.invoice_number} — Fully Paid!`
        : `Invoice ${res.data.invoice_number} — Saved (Balance: ${formatPHP(res.data.balance)})`
      );
      setLines([{ ...EMPTY_LINE }]);
      setFreight(0); setOverallDiscount(0); setAmountPaid(0);
      setHeader(h => ({ ...h, customer_id: '', customer_name: '', customer_contact: '', customer_phone: '', customer_address: '', customer_po: '' }));
    } catch (e) { toast.error(e.response?.data?.detail || 'Error creating invoice'); }
    setSaving(false);
  };

  return (
    <div className="space-y-5 animate-fadeIn" data-testid="sales-order-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>New Sales Order</h1>
          <p className="text-sm text-slate-500">Create invoice with line items</p>
        </div>
        <div className="flex gap-2">
          <Button data-testid="save-paid-btn" onClick={() => handleSaveAs('paid')} disabled={saving}
            className="bg-emerald-600 hover:bg-emerald-700 text-white">
            <CreditCard size={16} className="mr-2" /> {saving ? 'Saving...' : 'Receive Payment (Fully Paid)'}
          </Button>
          <Button data-testid="save-invoice-btn" onClick={() => handleSaveAs('credit')} disabled={saving}
            className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">
            <Save size={16} className="mr-2" /> {saving ? 'Saving...' : 'Save as Invoice'}
          </Button>
        </div>
      </div>

      {/* Header */}
      <Card className="border-slate-200">
        <CardContent className="p-5">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <Label className="text-xs text-slate-500">Customer</Label>
              <Select value={header.customer_id || 'walk-in'} onValueChange={v => v === 'walk-in' ? setHeader(h => ({ ...h, customer_id: '', customer_name: 'Walk-in' })) : selectCustomer(v)}>
                <SelectTrigger data-testid="invoice-customer" className="h-9"><SelectValue placeholder="Walk-in" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="walk-in">Walk-in Customer</SelectItem>
                  {customers.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div><Label className="text-xs text-slate-500">Contact</Label><Input className="h-9" value={header.customer_contact} onChange={e => setHeader(h => ({ ...h, customer_contact: e.target.value }))} /></div>
            <div><Label className="text-xs text-slate-500">Phone</Label><Input className="h-9" value={header.customer_phone} onChange={e => setHeader(h => ({ ...h, customer_phone: e.target.value }))} /></div>
            <div><Label className="text-xs text-slate-500">Address</Label><Input className="h-9" value={header.customer_address} onChange={e => setHeader(h => ({ ...h, customer_address: e.target.value }))} /></div>
            <div>
              <Label className="text-xs text-slate-500">Terms</Label>
              <Select value={header.terms} onValueChange={selectTerm}>
                <SelectTrigger data-testid="invoice-terms" className="h-9"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {terms.map(t => <SelectItem key={t.label} value={t.label}>{t.label}</SelectItem>)}
                  <SelectItem value="Custom">Custom</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {header.terms === 'Custom' && (
              <div><Label className="text-xs text-slate-500">Custom Days</Label><Input className="h-9" type="number" value={header.terms_days} onChange={e => setHeader(h => ({ ...h, terms_days: parseInt(e.target.value) || 0 }))} /></div>
            )}
            <div><Label className="text-xs text-slate-500">Customer PO #</Label><Input className="h-9" value={header.customer_po} onChange={e => setHeader(h => ({ ...h, customer_po: e.target.value }))} /></div>
            <div>
              <Label className="text-xs text-slate-500">Sales Rep</Label>
              <Select value={header.sales_rep_id || 'none'} onValueChange={v => {
                const u = users.find(x => x.id === v);
                setHeader(h => ({ ...h, sales_rep_id: v === 'none' ? '' : v, sales_rep_name: u?.full_name || u?.username || '' }));
              }}>
                <SelectTrigger className="h-9"><SelectValue placeholder="Select" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">None</SelectItem>
                  {users.map(u => <SelectItem key={u.id} value={u.id}>{u.full_name || u.username}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <Separator className="my-4" />
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
            <div>
              <Label className="text-xs text-slate-500">Prefix</Label>
              <Select value={header.prefix} onValueChange={v => setHeader(h => ({ ...h, prefix: v }))}>
                <SelectTrigger data-testid="invoice-prefix" className="h-9"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(prefixes).map(([k, v]) => <SelectItem key={k} value={v}>{v} - {k.replace('_', ' ')}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div><Label className="text-xs text-slate-500">Order Date</Label><Input className="h-9" type="date" value={header.order_date} onChange={e => setHeader(h => ({ ...h, order_date: e.target.value }))} /></div>
            <div><Label className="text-xs text-slate-500">Invoice Date</Label><Input className="h-9" type="date" value={header.invoice_date} onChange={e => setHeader(h => ({ ...h, invoice_date: e.target.value }))} /></div>
            <div><Label className="text-xs text-slate-500">Due Date (auto)</Label><Input className="h-9 bg-slate-50" value={dueDate} readOnly /></div>
            <div>
              <Label className="text-xs text-slate-500">Type</Label>
              <Select value={header.sale_type} onValueChange={v => setHeader(h => ({ ...h, sale_type: v }))}>
                <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="walk_in">Walk-in</SelectItem><SelectItem value="delivery">Delivery</SelectItem></SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Line Items - Excel Style */}
      <Card className="border-slate-200">
        <CardContent className="p-0">
          <table className="w-full text-sm" data-testid="invoice-lines-table">
            <thead>
              <tr className="bg-slate-50 border-b">
                <th className="text-left px-3 py-2 text-xs uppercase text-slate-500 font-medium w-8">#</th>
                <th className="text-left px-3 py-2 text-xs uppercase text-slate-500 font-medium min-w-[280px]">Product / Barcode</th>
                <th className="text-left px-3 py-2 text-xs uppercase text-slate-500 font-medium w-[180px]">Description</th>
                <th className="text-right px-3 py-2 text-xs uppercase text-slate-500 font-medium w-20">Qty</th>
                <th className="text-right px-3 py-2 text-xs uppercase text-slate-500 font-medium w-28">Rate</th>
                <th className="text-right px-3 py-2 text-xs uppercase text-slate-500 font-medium w-28">Discount</th>
                <th className="text-right px-3 py-2 text-xs uppercase text-slate-500 font-medium w-28">Amount</th>
                <th className="w-10"></th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line, i) => (
                <tr key={i} className="border-b border-slate-100 hover:bg-slate-50/50" data-testid={`line-row-${i}`}>
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
                  <td className="px-2 py-1"><input type="number" className="w-full h-8 px-2 text-sm text-right border border-transparent hover:border-slate-200 focus:border-[#1A4D2E] focus:outline-none rounded" value={line.rate} onChange={e => updateLine(i, 'rate', parseFloat(e.target.value) || 0)} onBlur={() => validateLineRate(i)} /></td>
                  <td className="px-2 py-1">
                    <div className="flex items-center gap-1">
                      <input type="number" className="w-16 h-8 px-2 text-sm text-right border border-transparent hover:border-slate-200 focus:border-[#1A4D2E] focus:outline-none rounded" value={line.discount_value} onChange={e => updateLine(i, 'discount_value', parseFloat(e.target.value) || 0)} />
                      <select className="h-8 text-xs border border-transparent hover:border-slate-200 focus:border-[#1A4D2E] rounded bg-transparent" value={line.discount_type} onChange={e => updateLine(i, 'discount_type', e.target.value)}>
                        <option value="amount">₱</option>
                        <option value="percent">%</option>
                      </select>
                    </div>
                  </td>
                  <td className="px-3 py-1 text-right font-semibold text-sm">{line.product_id ? formatPHP(lineTotal(line)) : ''}</td>
                  <td className="px-1 py-1">{lines.length > 1 && line.product_id && <button onClick={() => removeLine(i)} className="text-slate-400 hover:text-red-500 p-1"><Trash2 size={14} /></button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {/* Footer - Totals */}
      <div className="flex justify-end">
        <div className="w-full max-w-sm space-y-2">
          <div className="flex justify-between text-sm"><span className="text-slate-500">Subtotal</span><span className="font-semibold">{formatPHP(subtotal)}</span></div>
          <div className="flex justify-between items-center text-sm">
            <span className="text-slate-500">Freight</span>
            <Input type="number" className="w-28 h-8 text-right text-sm" value={freight} onChange={e => setFreight(parseFloat(e.target.value) || 0)} data-testid="invoice-freight" />
          </div>
          <div className="flex justify-between items-center text-sm">
            <span className="text-slate-500">Overall Discount</span>
            <Input type="number" className="w-28 h-8 text-right text-sm" value={overallDiscount} onChange={e => setOverallDiscount(parseFloat(e.target.value) || 0)} data-testid="invoice-discount" />
          </div>
          <Separator />
          <div className="flex justify-between text-lg font-bold" style={{ fontFamily: 'Manrope' }}>
            <span>Grand Total</span><span className="text-[#1A4D2E]">{formatPHP(grandTotal)}</span>
          </div>
          <Separator />
          <div className="flex justify-between items-center text-sm">
            <span className="text-slate-500">Amount Paid</span>
            <Input type="number" className="w-28 h-8 text-right text-sm" value={amountPaid} onChange={e => setAmountPaid(parseFloat(e.target.value) || 0)} data-testid="invoice-paid" />
          </div>
          <div className="flex justify-between text-base font-bold">
            <span>Balance</span><span className={balance > 0 ? 'text-amber-600' : 'text-emerald-600'}>{formatPHP(balance)}</span>
          </div>
        </div>
      </div>

      {/* Price Change Confirmation Dialog */}
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
                <Button variant="outline" className="flex-1" onClick={() => confirmPriceChange(false)}>
                  No, just this invoice
                </Button>
                <Button className="flex-1 bg-[#1A4D2E] hover:bg-[#14532d] text-white" onClick={() => confirmPriceChange(true)} data-testid="confirm-price-update">
                  Yes, update {priceChangeInfo.scheme} price
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Create Product Dialog (from search) */}
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
              <div><Label>Category</Label><Input value={newProductForm.category} onChange={e => setNewProductForm(f => ({ ...f, category: e.target.value }))} /></div>
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
    </div>
  );
}
