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
import { FileText, Plus, Trash2, Save, AlertTriangle } from 'lucide-react';
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
  const qtyRefs = useRef([]);

  useEffect(() => {
    api.get('/customers', { params: { limit: 500 } }).then(r => setCustomers(r.data.customers)).catch(() => {});
    api.get('/settings/terms-options').then(r => setTerms(r.data)).catch(() => {});
    api.get('/settings/invoice-prefixes').then(r => setPrefixes(r.data)).catch(() => {});
    api.get('/users').then(r => setUsers(r.data)).catch(() => setUsers([]));
  }, []);

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
    newLines[index] = { ...newLines[index], [field]: value };
    setLines(newLines);
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

  const handleSave = async () => {
    const validLines = lines.filter(l => l.product_id);
    if (!validLines.length) { toast.error('Add at least one product'); return; }
    if (!currentBranch) { toast.error('Select a branch'); return; }
    setSaving(true);
    try {
      const data = {
        ...header, branch_id: currentBranch.id, items: validLines, freight, overall_discount: overallDiscount,
        amount_paid: amountPaid, due_date: dueDate,
      };
      const res = await api.post('/invoices', data);
      toast.success(`Invoice ${res.data.invoice_number} created!`);
      // Reset form
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
        <Button data-testid="save-invoice-btn" onClick={handleSave} disabled={saving} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">
          <Save size={16} className="mr-2" /> {saving ? 'Saving...' : 'Save Invoice'}
        </Button>
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
                      <SmartProductSearch branchId={currentBranch?.id} onSelect={(p) => handleProductSelect(i, p)} />
                    )}
                  </td>
                  <td className="px-2 py-1"><input className="w-full h-8 px-2 text-sm border border-transparent hover:border-slate-200 focus:border-[#1A4D2E] focus:outline-none rounded" value={line.description} onChange={e => updateLine(i, 'description', e.target.value)} /></td>
                  <td className="px-2 py-1"><input ref={el => qtyRefs.current[i] = el} type="number" min="0" className="w-full h-8 px-2 text-sm text-right border border-transparent hover:border-slate-200 focus:border-[#1A4D2E] focus:outline-none rounded" value={line.quantity} onChange={e => updateLine(i, 'quantity', parseFloat(e.target.value) || 0)} /></td>
                  <td className="px-2 py-1"><input type="number" className="w-full h-8 px-2 text-sm text-right border border-transparent hover:border-slate-200 focus:border-[#1A4D2E] focus:outline-none rounded" value={line.rate} onChange={e => updateLine(i, 'rate', parseFloat(e.target.value) || 0)} /></td>
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
    </div>
  );
}
