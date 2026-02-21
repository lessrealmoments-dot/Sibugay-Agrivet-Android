import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth, api } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { ScrollArea } from '../components/ui/scroll-area';
import { Separator } from '../components/ui/separator';
import {
  CheckCircle2, Circle, ChevronRight, ChevronLeft, Receipt, CreditCard,
  Banknote, ReceiptText, Calculator, Wallet, Lock, Sun, Plus, RefreshCw,
  AlertTriangle, Package, Truck, ExternalLink, Check, XCircle, Search
} from 'lucide-react';
import { toast } from 'sonner';

const STEPS = [
  { id: 1, title: 'Sales Log',        icon: Receipt,      desc: 'Verify all cash & credit sales' },
  { id: 2, title: 'Customer Credits', icon: CreditCard,   desc: 'Credit sales, cashouts & farm services' },
  { id: 3, title: 'AR Payments',      icon: Banknote,     desc: 'Payments received on existing credit' },
  { id: 4, title: 'Expenses',         icon: ReceiptText,  desc: 'All expenses recorded today' },
  { id: 5, title: 'Cash Count',       icon: Calculator,   desc: 'Count the actual cash in drawer' },
  { id: 6, title: 'Fund Allocation',  icon: Wallet,       desc: 'Distribute to safe and register' },
  { id: 7, title: 'Close & Sign Off', icon: Lock,         desc: 'Z-Report preview and manager sign-off' },
  { id: 8, title: 'Open Tomorrow',    icon: Sun,          desc: 'Confirm close and start next day' },
];

export default function CloseWizardPage() {
  const navigate = useNavigate();
  const { currentBranch, user, hasPerm } = useAuth();

  const [step, setStep] = useState(1);
  const [completed, setCompleted] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [date, setDate] = useState('');

  // Wizard data
  const [dailyLog, setDailyLog] = useState(null);
  const [preview, setPreview] = useState(null);
  const [report, setReport]   = useState(null);
  const [isClosed, setIsClosed] = useState(false);
  const [closingRecord, setClosingRecord] = useState(null);

  // Step 5+6 inputs
  const [actualCash, setActualCash]     = useState('');
  const [cashToSafe, setCashToSafe]     = useState('');
  const [cashToDrawer, setCashToDrawer] = useState('');

  // Step 7 manager PIN + close
  const [managerPin, setManagerPin]     = useState('');
  const [pinVerified, setPinVerified]   = useState(false);
  const [pinVerifying, setPinVerifying] = useState(false);
  const [managerName, setManagerName]   = useState('');
  const [closing, setClosing]           = useState(false);

  // Quick-action dialogs
  const [saleDialog, setSaleDialog]   = useState(false);
  const [expDialog, setExpDialog]     = useState(false);
  const [pmtDialog, setPmtDialog]     = useState({ open: false, invoice: null });

  // 1-click report dialogs
  const [lowStockDialog, setLowStockDialog]     = useState(false);
  const [payablesDialog, setPayablesDialog]     = useState(false);
  const [lowStockData, setLowStockData]         = useState(null);
  const [payablesData, setPayablesData]         = useState(null);

  // Quick-add sale form
  const [saleForm, setSaleForm]   = useState({ search: '', product: null, qty: 1, price: '', paymentType: 'cash', customerName: '' });
  const [saleMatches, setSaleMatches] = useState([]);
  const [saleSchemes, setSaleSchemes] = useState([]);

  // Quick-add expense form
  const [expForm, setExpForm] = useState({ description: '', amount: '', category: 'Operational', expenseType: 'other' });
  const [expSaving, setExpSaving] = useState(false);

  // Quick receive payment form
  const [pmtAmount, setPmtAmount] = useState('');
  const [pmtSaving, setPmtSaving] = useState(false);

  const today = new Date().toISOString().split('T')[0];

  const loadWizardData = useCallback(async () => {
    if (!currentBranch) { setLoading(false); return; }
    setLoading(true);
    try {
      const d = today;
      setDate(d);
      const [logRes, previewRes, reportRes, closeRes] = await Promise.all([
        api.get('/daily-log', { params: { date: d, branch_id: currentBranch.id } }),
        api.get('/daily-close-preview', { params: { date: d, branch_id: currentBranch.id } }),
        api.get('/daily-report', { params: { date: d, branch_id: currentBranch.id } }),
        api.get(`/daily-close/${d}`, { params: { branch_id: currentBranch.id } }),
      ]);
      setDailyLog(logRes.data);
      setPreview(previewRes.data);
      setReport(reportRes.data);
      if (closeRes.data?.status === 'closed') {
        setIsClosed(true);
        setClosingRecord(closeRes.data);
        setStep(8);
        setCompleted(new Set([1,2,3,4,5,6,7]));
      }
      // Pre-fill safe/drawer from preview
      const exp = previewRes.data?.expected_counter || 0;
      if (exp > 0) {
        const safe = Math.max(0, Math.floor(exp * 0.7));
        const drawer = Math.max(0, exp - safe);
        setCashToSafe(String(safe));
        setCashToDrawer(String(drawer));
      }
    } catch (e) { toast.error('Failed to load wizard data'); }
    setLoading(false);
    // Load price schemes for quick sale
    api.get('/price-schemes').then(r => setSaleSchemes(r.data || [])).catch(() => {});
  }, [currentBranch, today]);

  useEffect(() => { loadWizardData(); }, [loadWizardData]);

  const markComplete = (s) => setCompleted(prev => new Set([...prev, s]));
  const canProceedToClose = completed.has(5) && completed.has(6) && actualCash !== '';

  const r2 = (n) => Math.round((n || 0) * 100) / 100;

  // ── Verify manager PIN ──────────────────────────────────────────────────────
  const verifyManagerPin = async () => {
    if (!managerPin) { toast.error('Enter PIN'); return; }
    setPinVerifying(true);
    try {
      const res = await api.post('/auth/verify-manager-pin', {
        pin: managerPin, required_level: 'manager',
        context: `Daily close ${date} — ${currentBranch?.name}`
      });
      if (res.data.valid) {
        setPinVerified(true);
        setManagerName(res.data.manager_name);
        toast.success(`Verified: ${res.data.manager_name}`);
      } else {
        toast.error('Invalid PIN');
      }
    } catch { toast.error('PIN verification failed'); }
    setPinVerifying(false);
  };

  // ── Close the day ───────────────────────────────────────────────────────────
  const handleCloseDay = async () => {
    if (!pinVerified) { toast.error('Manager PIN required'); return; }
    if (!actualCash) { toast.error('Enter actual cash count'); return; }
    const safe = parseFloat(cashToSafe) || 0;
    const drawer = parseFloat(cashToDrawer) || 0;
    const actual = parseFloat(actualCash);
    if (safe + drawer > actual) { toast.error('Safe + drawer cannot exceed actual cash'); return; }
    setClosing(true);
    try {
      const res = await api.post('/daily-close', {
        date, branch_id: currentBranch.id,
        admin_pin: managerPin,
        actual_cash: actual,
        cash_to_safe: safe,
        cash_to_drawer: drawer,
        variance_notes: '',
      });
      setClosingRecord(res.data);
      setIsClosed(true);
      markComplete(7);
      setStep(8);
      toast.success('Day closed successfully!');
    } catch (e) { toast.error(e.response?.data?.detail || 'Close failed'); }
    setClosing(false);
  };

  // ── Quick add sale ──────────────────────────────────────────────────────────
  const searchProducts = async (q) => {
    setSaleForm(f => ({ ...f, search: q, product: null }));
    if (q.length < 1) { setSaleMatches([]); return; }
    const res = await api.get('/products', { params: { search: q, is_repack: false, limit: 6 } });
    setSaleMatches(res.data.products || []);
  };

  const quickAddSale = async () => {
    if (!saleForm.product) { toast.error('Select a product'); return; }
    const price = parseFloat(saleForm.price);
    if (!price || price <= 0) { toast.error('Enter price'); return; }
    try {
      const allPrices = {};
      saleSchemes.forEach(s => { allPrices[s.key] = price; });
      await api.post('/unified-sale', {
        branch_id: currentBranch.id,
        date,
        items: [{ product_id: saleForm.product.id, product_name: saleForm.product.name,
          sku: saleForm.product.sku, unit: saleForm.product.unit,
          quantity: saleForm.qty, unit_price: price, line_total: price * saleForm.qty,
          category: saleForm.product.category || 'General' }],
        payment_type: saleForm.paymentType,
        customer_name: saleForm.paymentType === 'cash' ? 'Walk-in' : (saleForm.customerName || 'Walk-in'),
        subtotal: price * saleForm.qty,
        grand_total: price * saleForm.qty,
        amount_paid: saleForm.paymentType === 'cash' ? price * saleForm.qty : 0,
        balance: saleForm.paymentType === 'cash' ? 0 : price * saleForm.qty,
      });
      toast.success('Sale added');
      setSaleDialog(false);
      setSaleForm({ search: '', product: null, qty: 1, price: '', paymentType: 'cash', customerName: '' });
      setSaleMatches([]);
      loadWizardData();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to add sale'); }
  };

  // ── Quick add expense ───────────────────────────────────────────────────────
  const quickAddExpense = async () => {
    if (!expForm.description || !expForm.amount) { toast.error('Description and amount required'); return; }
    setExpSaving(true);
    try {
      const endpoint = expForm.expenseType === 'farm' ? '/expenses/farm'
        : expForm.expenseType === 'advance' ? '/expenses/employee-advance' : '/expenses';
      await api.post(endpoint, { ...expForm, amount: parseFloat(expForm.amount), branch_id: currentBranch.id, date });
      toast.success('Expense added');
      setExpDialog(false);
      setExpForm({ description: '', amount: '', category: 'Operational', expenseType: 'other' });
      loadWizardData();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    setExpSaving(false);
  };

  // ── Quick receive payment ───────────────────────────────────────────────────
  const quickReceivePayment = async () => {
    if (!pmtAmount || !pmtDialog.invoice) { toast.error('Enter amount'); return; }
    setPmtSaving(true);
    try {
      // Find invoice by invoice_number if no invoice_id
      let invId = pmtDialog.invoice.invoice_id;
      if (!invId) {
        const res = await api.get('/invoices', { params: { invoice_number: pmtDialog.invoice.invoice_number } });
        invId = res.data?.[0]?.id;
      }
      if (!invId) { toast.error('Invoice not found'); setPmtSaving(false); return; }
      await api.post(`/invoices/${invId}/payment`, {
        amount: parseFloat(pmtAmount),
        date,
        method: 'Cash',
        branch_id: currentBranch.id,
      });
      toast.success('Payment recorded');
      setPmtDialog({ open: false, invoice: null });
      setPmtAmount('');
      loadWizardData();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    setPmtSaving(false);
  };

  // ── Load 1-click reports ────────────────────────────────────────────────────
  const loadLowStock = async () => {
    if (!currentBranch) return;
    const res = await api.get('/low-stock-alert', { params: { branch_id: currentBranch.id } });
    setLowStockData(res.data);
    setLowStockDialog(true);
  };

  const loadPayables = async () => {
    const res = await api.get('/supplier-payables', { params: { branch_id: currentBranch?.id } });
    setPayablesData(res.data);
    setPayablesDialog(true);
  };

  // Sync step 6 pre-fill whenever actualCash changes (after step 5)
  useEffect(() => {
    if (!actualCash) return;
    const actual = parseFloat(actualCash);
    if (isNaN(actual) || actual <= 0) return;
    const safe = Math.max(0, Math.floor(actual * 0.7));
    const drawer = Math.max(0, Math.round((actual - safe) * 100) / 100);
    setCashToSafe(String(safe));
    setCashToDrawer(String(drawer));
  }, [actualCash]);
  const expectedCash = r2(preview?.expected_counter || 0);
  const overShort    = actualCash !== '' ? r2(parseFloat(actualCash) - expectedCash) : null;

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <RefreshCw size={24} className="animate-spin text-slate-400" />
    </div>
  );

  if (!currentBranch) return (
    <div className="text-center py-20 text-slate-400">
      <p>Please select a branch first to run the Close Wizard.</p>
    </div>
  );

  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-fadeIn" data-testid="close-wizard-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>
            Daily Close Wizard
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {currentBranch?.name} — {date}
            {isClosed && <Badge className="ml-2 bg-emerald-100 text-emerald-700 text-[10px]">CLOSED</Badge>}
          </p>
        </div>
        {/* 1-Click Reports */}
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={loadLowStock} data-testid="low-stock-report-btn">
            <Package size={14} className="mr-1.5 text-amber-500" /> Low Stock
          </Button>
          <Button variant="outline" size="sm" onClick={loadPayables} data-testid="payables-report-btn">
            <Truck size={14} className="mr-1.5 text-red-500" /> Supplier Payables
          </Button>
        </div>
      </div>

      {/* Stepper */}
      <div className="flex items-center gap-0 overflow-x-auto pb-1">
        {STEPS.map((s, idx) => {
          const done = completed.has(s.id);
          const active = step === s.id;
          const Icon = s.icon;
          return (
            <div key={s.id} className="flex items-center shrink-0">
              <button
                onClick={() => setStep(s.id)}
                className={`flex flex-col items-center gap-1 px-3 py-2 rounded-xl transition-colors min-w-[80px] ${
                  active ? 'bg-[#1A4D2E]/10 border border-[#1A4D2E]/30' : 'hover:bg-slate-50'
                }`}
              >
                <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 transition-colors ${
                  done ? 'bg-emerald-500 text-white' : active ? 'bg-[#1A4D2E] text-white' : 'bg-slate-200 text-slate-500'
                }`}>
                  {done ? <Check size={15} /> : <Icon size={15} />}
                </div>
                <span className={`text-[10px] font-medium text-center leading-tight ${active ? 'text-[#1A4D2E]' : 'text-slate-500'}`}>
                  {s.title}
                </span>
              </button>
              {idx < STEPS.length - 1 && (
                <div className={`h-px w-5 mx-0.5 shrink-0 ${completed.has(s.id) ? 'bg-emerald-400' : 'bg-slate-200'}`} />
              )}
            </div>
          );
        })}
      </div>

      {/* Step content */}
      <Card className="border-slate-200 min-h-[400px]">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center bg-[#1A4D2E] text-white`}>
                {(() => { const Icon = STEPS[step-1].icon; return <Icon size={15} />; })()}
              </div>
              <div>
                <CardTitle className="text-base font-bold" style={{ fontFamily: 'Manrope' }}>
                  Step {step}: {STEPS[step-1].title}
                </CardTitle>
                <p className="text-xs text-slate-500">{STEPS[step-1].desc}</p>
              </div>
            </div>
            {!completed.has(step) && step < 7 && (
              <Button size="sm" variant="outline" onClick={() => markComplete(step)}
                className="text-emerald-700 border-emerald-300 hover:bg-emerald-50" data-testid={`mark-complete-step-${step}`}>
                <CheckCircle2 size={13} className="mr-1" /> Mark Complete
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>

          {/* ── STEP 1: Sales Log ── */}
          {step === 1 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex gap-4 text-sm">
                  <span className="text-slate-500">Cash Sales: <strong className="text-emerald-700">{formatPHP(dailyLog?.summary?.total_cash || 0)}</strong></span>
                  <span className="text-slate-500">Credit: <strong className="text-amber-700">{formatPHP(dailyLog?.summary?.total_credit || 0)}</strong></span>
                  <span className="text-slate-500">Total Entries: <strong>{dailyLog?.summary?.cash_count || 0}</strong></span>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => setSaleDialog(true)} data-testid="quick-add-sale-btn">
                    <Plus size={13} className="mr-1" /> Quick Add Sale
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => window.open('/sales-new', '_blank')} className="text-slate-500">
                    <ExternalLink size={13} className="mr-1" /> Full Sales Panel
                  </Button>
                </div>
              </div>
              <ScrollArea className="h-[280px] rounded-lg border border-slate-200">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-slate-50 border-b border-slate-200">
                    <tr className="text-xs uppercase text-slate-500">
                      <th className="px-3 py-2 text-left">#</th>
                      <th className="px-3 py-2 text-left">Product</th>
                      <th className="px-3 py-2 text-center">Qty</th>
                      <th className="px-3 py-2 text-right">Amount</th>
                      <th className="px-3 py-2 text-right">Running Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(dailyLog?.cash_entries || []).map((e, i) => (
                      <tr key={i} className="border-b border-slate-50 hover:bg-slate-50/50">
                        <td className="px-3 py-1.5 text-xs text-slate-400">{e.sequence || i+1}</td>
                        <td className="px-3 py-1.5 font-medium">{e.product_name}</td>
                        <td className="px-3 py-1.5 text-center text-slate-500">{e.quantity} {e.unit}</td>
                        <td className="px-3 py-1.5 text-right font-mono">{formatPHP(e.line_total)}</td>
                        <td className="px-3 py-1.5 text-right font-mono text-emerald-700">{formatPHP(e.cash_running_total)}</td>
                      </tr>
                    ))}
                    {!(dailyLog?.cash_entries?.length) && (
                      <tr><td colSpan={5} className="text-center py-8 text-slate-400">No cash sales yet today</td></tr>
                    )}
                  </tbody>
                </table>
              </ScrollArea>
            </div>
          )}

          {/* ── STEP 2: Customer Credits ── */}
          {step === 2 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between mb-1">
                <p className="text-sm text-slate-500">Credit invoices, cashouts, and farm services recorded today.</p>
                <Button size="sm" variant="outline" onClick={() => window.open('/sales-new', '_blank')}>
                  <ExternalLink size={13} className="mr-1" /> Add Credit Sale
                </Button>
              </div>
              <div className="space-y-2">
                {/* Regular credit sales */}
                {(dailyLog?.credit_invoices || []).filter(inv => !inv.sale_type || inv.sale_type === 'credit').length > 0 && (
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">Credit Sales</p>
                    {(dailyLog?.credit_invoices || []).map((inv, i) => (
                      <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-amber-50 border border-amber-100 mb-1.5 text-sm">
                        <div>
                          <p className="font-semibold">{inv.customer_name}</p>
                          <p className="text-xs text-slate-400">{inv.invoice_number} · {inv.payment_type}</p>
                        </div>
                        <div className="text-right">
                          <p className="font-mono font-bold text-amber-700">{formatPHP(inv.grand_total)}</p>
                          {inv.amount_paid > 0 && <p className="text-xs text-slate-400">Paid: {formatPHP(inv.amount_paid)}</p>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {/* Cashouts & Farm (AR credits from expenses) */}
                {(report?.ar_credits_today || []).length > 0 && (
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">Cash Advances & Farm Services</p>
                    {(report.ar_credits_today).map((inv, i) => (
                      <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-blue-50 border border-blue-100 mb-1.5 text-sm">
                        <div>
                          <p className="font-semibold">{inv.customer_name}</p>
                          <p className="text-xs text-slate-400">{inv.invoice_number} · {inv.sale_type === 'cash_advance' ? 'Cash-out' : 'Farm Service'}</p>
                        </div>
                        <p className="font-mono font-bold text-blue-700">{formatPHP(inv.grand_total)}</p>
                      </div>
                    ))}
                  </div>
                )}
                {!(dailyLog?.credit_invoices?.length) && !(report?.ar_credits_today?.length) && (
                  <p className="text-center py-8 text-slate-400 text-sm">No credit activity today</p>
                )}
              </div>
              <Separator />
              <div className="flex justify-between text-sm font-semibold px-1">
                <span>Total Credit Extended Today</span>
                <span className="text-amber-700">{formatPHP(r2((dailyLog?.summary?.total_credit || 0) + (report?.total_ar_credits_today || 0)))}</span>
              </div>
            </div>
          )}

          {/* ── STEP 3: AR Payments ── */}
          {step === 3 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between mb-1">
                <p className="text-sm text-slate-500">Payments received today on existing credit accounts.</p>
                <p className="text-sm font-semibold text-blue-700">Total Received: {formatPHP(preview?.total_ar_received || 0)}</p>
              </div>
              <ScrollArea className="h-[280px] rounded-lg border border-slate-200">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-slate-50 border-b border-slate-200">
                    <tr className="text-xs uppercase text-slate-500">
                      <th className="px-3 py-2 text-left">Customer / Invoice</th>
                      <th className="px-3 py-2 text-right">Bal Before</th>
                      <th className="px-3 py-2 text-right">Interest</th>
                      <th className="px-3 py-2 text-right">Penalty</th>
                      <th className="px-3 py-2 text-right text-blue-600 font-bold">Paid</th>
                      <th className="px-3 py-2 text-right">Remaining</th>
                      <th className="px-3 py-2 w-10"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {(preview?.ar_payments || []).map((p, i) => (
                      <tr key={i} className="border-b border-slate-50 hover:bg-slate-50/50">
                        <td className="px-3 py-2">
                          <p className="font-medium">{p.customer_name}</p>
                          <p className="text-xs text-slate-400 font-mono">{p.invoice_number}</p>
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-xs">{formatPHP(p.balance_before)}</td>
                        <td className="px-3 py-2 text-right font-mono text-xs text-amber-600">{p.interest_paid > 0 ? formatPHP(p.interest_paid) : '—'}</td>
                        <td className="px-3 py-2 text-right font-mono text-xs text-red-500">{p.penalty_paid > 0 ? formatPHP(p.penalty_paid) : '—'}</td>
                        <td className="px-3 py-2 text-right font-mono font-bold text-blue-700">{formatPHP(p.amount_paid)}</td>
                        <td className="px-3 py-2 text-right font-mono text-xs">{formatPHP(p.remaining_balance)}</td>
                        <td className="px-3 py-2">
                          <Button size="sm" variant="ghost" className="h-6 px-1.5 text-[10px] text-blue-500"
                            onClick={() => { setPmtDialog({ open: true, invoice: p }); setPmtAmount(''); }}>
                            + Pay
                          </Button>
                        </td>
                      </tr>
                    ))}
                    {!(preview?.ar_payments?.length) && (
                      <tr><td colSpan={7} className="text-center py-8 text-slate-400">No AR payments received today</td></tr>
                    )}
                  </tbody>
                </table>
              </ScrollArea>
            </div>
          )}

          {/* ── STEP 4: Expenses ── */}
          {step === 4 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between mb-1">
                <p className="text-sm text-slate-500">All expenses recorded today. Employee advances show monthly totals.</p>
                <Button size="sm" variant="outline" onClick={() => setExpDialog(true)} data-testid="quick-add-expense-btn">
                  <Plus size={13} className="mr-1" /> Add Expense
                </Button>
              </div>
              <ScrollArea className="h-[260px] rounded-lg border border-slate-200">
                <div className="divide-y divide-slate-100">
                  {(preview?.expenses || []).map((e, i) => (
                    <div key={i} className="px-4 py-2.5 flex items-center justify-between text-sm">
                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate">{e.description || e.notes || e.category}</p>
                        <p className="text-xs text-slate-400">{e.category}</p>
                        {e.monthly_ca_total && (
                          <div className="mt-1 inline-flex items-center gap-1 bg-amber-50 border border-amber-200 rounded px-2 py-0.5 text-[10px] text-amber-700">
                            <AlertTriangle size={9} /> Monthly advance total: {formatPHP(e.monthly_ca_total)}
                          </div>
                        )}
                      </div>
                      <p className="font-mono font-semibold text-red-600 ml-4">{formatPHP(e.amount)}</p>
                    </div>
                  ))}
                  {!(preview?.expenses?.length) && (
                    <p className="text-center py-8 text-slate-400 text-sm">No expenses today</p>
                  )}
                </div>
              </ScrollArea>
              <Separator />
              <div className="flex justify-between text-sm font-semibold px-1">
                <span>Total Expenses</span>
                <span className="text-red-600">{formatPHP(preview?.total_expenses || 0)}</span>
              </div>
            </div>
          )}

          {/* ── STEP 5: Cash Count ── */}
          {step === 5 && (
            <div className="space-y-4 max-w-md mx-auto">
              <div className="grid grid-cols-2 gap-3">
                <div className="p-4 rounded-lg bg-slate-50 border border-slate-200">
                  <p className="text-xs text-slate-500 uppercase font-medium mb-1">Starting Float</p>
                  <p className="text-2xl font-bold font-mono">{formatPHP(preview?.starting_float || 0)}</p>
                </div>
                <div className="p-4 rounded-lg bg-blue-50 border border-blue-200">
                  <p className="text-xs text-blue-500 uppercase font-medium mb-1">Total Cash In</p>
                  <p className="text-2xl font-bold font-mono text-blue-700">{formatPHP(preview?.total_cash_in || 0)}</p>
                </div>
                <div className="p-4 rounded-lg bg-red-50 border border-red-200">
                  <p className="text-xs text-red-500 uppercase font-medium mb-1">Total Expenses</p>
                  <p className="text-2xl font-bold font-mono text-red-600">{formatPHP(preview?.total_expenses || 0)}</p>
                </div>
                <div className="p-4 rounded-lg bg-emerald-50 border border-emerald-200">
                  <p className="text-xs text-emerald-600 uppercase font-medium mb-1">Expected in Drawer</p>
                  <p className="text-2xl font-bold font-mono text-emerald-700">{formatPHP(expectedCash)}</p>
                </div>
              </div>
              <Separator />
              <div>
                <Label className="text-sm font-semibold">Actual Cash Count</Label>
                <Input
                  data-testid="actual-cash-input"
                  type="number" min={0} step="0.01"
                  value={actualCash}
                  onChange={e => setActualCash(e.target.value)}
                  placeholder="Count the cash and enter here"
                  className="h-12 text-xl font-mono mt-1"
                />
              </div>
              {overShort !== null && (
                <div className={`p-3 rounded-lg border text-center ${overShort > 0 ? 'bg-emerald-50 border-emerald-200' : overShort < 0 ? 'bg-red-50 border-red-200' : 'bg-slate-50 border-slate-200'}`}>
                  <p className="text-xs uppercase font-medium text-slate-500 mb-0.5">Over / Short</p>
                  <p className={`text-2xl font-bold font-mono ${overShort > 0 ? 'text-emerald-700' : overShort < 0 ? 'text-red-600' : 'text-slate-500'}`}>
                    {overShort > 0 ? '+' : ''}{formatPHP(overShort)}
                  </p>
                  {overShort !== 0 && <p className="text-xs text-slate-500 mt-0.5">{overShort > 0 ? 'Cash over — check for unrecorded sales' : 'Cash short — check for missing expenses or errors'}</p>}
                </div>
              )}
              {actualCash && <Button onClick={() => markComplete(5)} className="w-full bg-[#1A4D2E] text-white" data-testid="complete-cash-count-btn">
                <CheckCircle2 size={15} className="mr-2" /> Confirm Cash Count
              </Button>}
            </div>
          )}

          {/* ── STEP 6: Fund Allocation ── */}
          {step === 6 && (
            <div className="space-y-4 max-w-md mx-auto">
              {!completed.has(5) && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800 flex gap-2">
                  <AlertTriangle size={16} className="shrink-0 mt-0.5" /> Complete the Cash Count (Step 5) first.
                </div>
              )}
              <div className="p-4 rounded-lg bg-slate-50 border border-slate-200">
                <p className="text-xs text-slate-500 uppercase font-medium mb-1">Actual Cash Available</p>
                <p className="text-3xl font-bold font-mono">{formatPHP(parseFloat(actualCash) || 0)}</p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Transfer to Safe</Label>
                  <Input data-testid="cash-to-safe-input" type="number" min={0} step="0.01"
                    value={cashToSafe}
                    onChange={e => { setCashToSafe(e.target.value); const rem = r2((parseFloat(actualCash)||0)-(parseFloat(e.target.value)||0)); setCashToDrawer(String(Math.max(0,rem))); }}
                    className="h-10 font-mono mt-1" />
                </div>
                <div>
                  <Label>Stay in Register (Float)</Label>
                  <Input data-testid="cash-to-drawer-input" type="number" min={0} step="0.01"
                    value={cashToDrawer}
                    onChange={e => { setCashToDrawer(e.target.value); const rem = r2((parseFloat(actualCash)||0)-(parseFloat(e.target.value)||0)); setCashToSafe(String(Math.max(0,rem))); }}
                    className="h-10 font-mono mt-1" />
                </div>
              </div>
              {(() => {
                const safe = parseFloat(cashToSafe)||0, drawer = parseFloat(cashToDrawer)||0, actual = parseFloat(actualCash)||0;
                const allocated = r2(safe+drawer), unallocated = r2(actual-allocated);
                return (
                  <div className={`p-3 rounded-lg border text-sm ${Math.abs(unallocated) < 0.01 ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'}`}>
                    <div className="flex justify-between">
                      <span>Allocated</span><span className="font-mono font-bold">{formatPHP(allocated)}</span>
                    </div>
                    {Math.abs(unallocated) > 0.01 && (
                      <div className="flex justify-between text-amber-700 mt-0.5">
                        <span>Unallocated</span><span className="font-mono font-bold">{formatPHP(unallocated)}</span>
                      </div>
                    )}
                  </div>
                );
              })()}
              <Button onClick={() => markComplete(6)} className="w-full bg-[#1A4D2E] text-white"
                disabled={!completed.has(5)} data-testid="complete-allocation-btn">
                <CheckCircle2 size={15} className="mr-2" /> Confirm Allocation
              </Button>
            </div>
          )}

          {/* ── STEP 7: Close & Sign Off ── */}
          {step === 7 && (
            <div className="space-y-4">
              {!canProceedToClose && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
                  <AlertTriangle size={15} className="inline mr-1" /> Complete Steps 5 and 6 before closing.
                </div>
              )}

              {/* Z-Report Summary */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                {[
                  { label: 'Starting Float', value: preview?.starting_float, color: 'slate' },
                  { label: 'Cash Sales', value: preview?.total_cash_sales, color: 'emerald' },
                  { label: 'AR Received', value: preview?.total_ar_received, color: 'blue' },
                  { label: 'Expenses', value: preview?.total_expenses, color: 'red' },
                  { label: 'Expected Cash', value: expectedCash, color: 'indigo' },
                  { label: 'Actual Cash', value: parseFloat(actualCash)||0, color: 'indigo' },
                  { label: 'To Safe', value: parseFloat(cashToSafe)||0, color: 'slate' },
                  { label: 'Float Tomorrow', value: parseFloat(cashToDrawer)||0, color: 'emerald' },
                ].map(({ label, value, color }) => (
                  <div key={label} className={`p-3 rounded-lg bg-${color}-50 border border-${color}-200`}>
                    <p className={`text-xs text-${color}-500 uppercase font-medium mb-0.5`}>{label}</p>
                    <p className={`text-lg font-bold font-mono text-${color}-700`}>{formatPHP(value)}</p>
                  </div>
                ))}
              </div>

              <Separator />

              {/* Manager PIN */}
              <div className="max-w-sm">
                <Label className="text-sm font-semibold flex items-center gap-1.5">
                  <Lock size={14} className="text-slate-500" /> Manager / Owner Sign-Off
                </Label>
                {pinVerified ? (
                  <div className="mt-1 p-2.5 rounded-lg bg-emerald-50 border border-emerald-200 flex items-center gap-2 text-sm">
                    <CheckCircle2 size={16} className="text-emerald-600" />
                    <span className="text-emerald-700 font-medium">Signed off by {managerName}</span>
                  </div>
                ) : (
                  <div className="flex gap-2 mt-1">
                    <Input
                      data-testid="manager-pin-input"
                      type="password"
                      value={managerPin}
                      onChange={e => setManagerPin(e.target.value)}
                      placeholder="Enter manager PIN"
                      className="h-9"
                      onKeyDown={e => e.key === 'Enter' && verifyManagerPin()}
                    />
                    <Button size="sm" onClick={verifyManagerPin} disabled={pinVerifying || !canProceedToClose}
                      className="shrink-0 bg-slate-700 hover:bg-slate-800 text-white">
                      {pinVerifying ? <RefreshCw size={13} className="animate-spin" /> : 'Verify'}
                    </Button>
                  </div>
                )}
              </div>

              {/* Close Day Button */}
              <Button
                data-testid="close-day-btn"
                onClick={handleCloseDay}
                disabled={!pinVerified || !canProceedToClose || closing || isClosed}
                className="w-full h-12 bg-red-600 hover:bg-red-700 text-white text-base font-semibold"
              >
                {closing ? <><RefreshCw size={16} className="animate-spin mr-2" />Closing...</>
                  : isClosed ? <><CheckCircle2 size={16} className="mr-2" /> Already Closed</>
                  : <><Lock size={16} className="mr-2" /> Close Accounts for {date}</>}
              </Button>
              <p className="text-xs text-slate-400 text-center">This action is permanent. The day will be locked and the Z-Report saved.</p>
            </div>
          )}

          {/* ── STEP 8: Open Tomorrow ── */}
          {step === 8 && (
            <div className="space-y-4 text-center max-w-lg mx-auto py-4">
              {isClosed ? (
                <>
                  <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mx-auto">
                    <CheckCircle2 size={32} className="text-emerald-600" />
                  </div>
                  <h2 className="text-xl font-bold" style={{ fontFamily: 'Manrope' }}>Day Closed Successfully</h2>
                  <p className="text-slate-500 text-sm">
                    {date} has been closed for <strong>{currentBranch?.name}</strong>.<br />
                    All new sales, purchase orders, and expenses will automatically be dated <strong>tomorrow</strong>.
                  </p>
                  {closingRecord && (
                    <div className="mt-2 grid grid-cols-3 gap-3 text-sm text-left">
                      {[
                        { label: 'Closed by', value: closingRecord.closed_by_name },
                        { label: 'To Safe', value: formatPHP(closingRecord.cash_to_safe) },
                        { label: 'Float', value: formatPHP(closingRecord.cash_to_drawer) },
                        { label: 'Over/Short', value: (closingRecord.over_short > 0 ? '+' : '') + formatPHP(closingRecord.over_short) },
                        { label: 'Total Cash', value: formatPHP(closingRecord.actual_cash) },
                        { label: 'AR Received', value: formatPHP(closingRecord.total_ar_received) },
                      ].map(({ label, value }) => (
                        <div key={label} className="p-2 rounded-lg bg-slate-50 border border-slate-100">
                          <p className="text-xs text-slate-400">{label}</p>
                          <p className="font-semibold">{value}</p>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="flex gap-3 justify-center mt-4">
                    <Button variant="outline" onClick={() => window.print()}>Print Z-Report</Button>
                    <Button onClick={() => navigate('/sales-new')} className="bg-[#1A4D2E] text-white">
                      <Sun size={15} className="mr-1.5" /> Open Tomorrow's Sales
                    </Button>
                  </div>
                </>
              ) : (
                <div className="py-8">
                  <p className="text-slate-400">Complete Step 7 (Close & Sign Off) first.</p>
                  <Button variant="outline" onClick={() => setStep(7)} className="mt-3">Go to Step 7</Button>
                </div>
              )}
            </div>
          )}

        </CardContent>
      </Card>

      {/* Navigation */}
      <div className="flex items-center justify-between">
        <Button variant="outline" onClick={() => setStep(s => Math.max(1, s - 1))} disabled={step === 1}>
          <ChevronLeft size={15} className="mr-1" /> Previous
        </Button>
        <span className="text-sm text-slate-400">Step {step} of {STEPS.length}</span>
        <Button onClick={() => { if (step < 8) { markComplete(step); setStep(s => s + 1); } }}
          disabled={step === 8 || (step === 7 && !isClosed)}
          className="bg-[#1A4D2E] hover:bg-[#14532d] text-white" data-testid="next-step-btn">
          {step === 7 ? (isClosed ? 'Next' : 'Close First') : 'Next'} <ChevronRight size={15} className="ml-1" />
        </Button>
      </div>

      {/* ── Quick Add Sale Dialog ── */}
      <Dialog open={saleDialog} onOpenChange={setSaleDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Quick Add Sale</DialogTitle></DialogHeader>
          <div className="space-y-3 mt-2">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <Input value={saleForm.search} onChange={e => searchProducts(e.target.value)}
                placeholder="Search product..." className="pl-8" autoFocus />
              {saleMatches.length > 0 && (
                <div className="absolute z-50 top-full mt-1 w-full bg-white border border-slate-200 rounded-lg shadow-lg max-h-40 overflow-y-auto">
                  {saleMatches.map(p => (
                    <button key={p.id} onMouseDown={() => {
                      const defaultPrice = p.prices?.retail || p.prices?.wholesale || p.cost_price || '';
                      setSaleForm(f => ({ ...f, product: p, search: p.name, price: String(defaultPrice) }));
                      setSaleMatches([]);
                    }} className="w-full text-left px-3 py-2 hover:bg-slate-50 text-sm border-b last:border-0">
                      <span className="font-medium">{p.name}</span>
                      <span className="text-slate-400 text-xs ml-2">{p.unit} · Cost {formatPHP(p.cost_price)}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            {saleForm.product && (
              <div className="grid grid-cols-2 gap-3">
                <div><Label>Quantity</Label><Input type="number" min={1} value={saleForm.qty}
                  onChange={e => setSaleForm(f => ({ ...f, qty: parseInt(e.target.value)||1 }))} className="h-9 mt-1" /></div>
                <div><Label>Unit Price</Label><Input type="number" min={0} value={saleForm.price}
                  onChange={e => setSaleForm(f => ({ ...f, price: e.target.value }))} className="h-9 mt-1 font-mono" /></div>
              </div>
            )}
            <div>
              <Label>Payment Type</Label>
              <Select value={saleForm.paymentType} onValueChange={v => setSaleForm(f => ({ ...f, paymentType: v }))}>
                <SelectTrigger className="mt-1 h-9"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="cash">Cash</SelectItem>
                  <SelectItem value="credit">Credit</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {saleForm.paymentType === 'credit' && (
              <div><Label>Customer Name</Label>
                <Input value={saleForm.customerName} onChange={e => setSaleForm(f => ({ ...f, customerName: e.target.value }))} className="h-9 mt-1" placeholder="Customer name" /></div>
            )}
            {saleForm.product && saleForm.price && (
              <div className="p-2 bg-emerald-50 rounded border border-emerald-200 text-sm">
                Total: <strong className="font-mono">{formatPHP((parseFloat(saleForm.price)||0) * saleForm.qty)}</strong>
              </div>
            )}
            <div className="flex gap-2 pt-1">
              <Button variant="outline" className="flex-1" onClick={() => setSaleDialog(false)}>Cancel</Button>
              <Button className="flex-1 bg-[#1A4D2E] text-white" onClick={quickAddSale}
                disabled={!saleForm.product}>Add Sale</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── Quick Add Expense Dialog ── */}
      <Dialog open={expDialog} onOpenChange={setExpDialog}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Add Expense</DialogTitle></DialogHeader>
          <div className="space-y-3 mt-2">
            <div>
              <Label>Type</Label>
              <Select value={expForm.expenseType} onValueChange={v => setExpForm(f => ({ ...f, expenseType: v }))}>
                <SelectTrigger className="mt-1 h-9"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="other">Operational</SelectItem>
                  <SelectItem value="farm">Farm Service</SelectItem>
                  <SelectItem value="advance">Employee Advance</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div><Label>Description</Label>
              <Input value={expForm.description} onChange={e => setExpForm(f => ({ ...f, description: e.target.value }))} className="h-9 mt-1" autoFocus /></div>
            <div><Label>Amount</Label>
              <Input type="number" min={0} value={expForm.amount} onChange={e => setExpForm(f => ({ ...f, amount: e.target.value }))} className="h-9 mt-1 font-mono" /></div>
            <div className="flex gap-2 pt-1">
              <Button variant="outline" className="flex-1" onClick={() => setExpDialog(false)}>Cancel</Button>
              <Button className="flex-1 bg-[#1A4D2E] text-white" onClick={quickAddExpense} disabled={expSaving}>
                {expSaving ? <RefreshCw size={13} className="animate-spin mr-1" /> : null} Add
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── Quick Receive Payment Dialog ── */}
      <Dialog open={pmtDialog.open} onOpenChange={v => setPmtDialog({ open: v, invoice: null })}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Receive Payment</DialogTitle></DialogHeader>
          {pmtDialog.invoice && (
            <div className="space-y-3 mt-2">
              <div className="p-3 rounded-lg bg-blue-50 border border-blue-200 text-sm">
                <p className="font-semibold">{pmtDialog.invoice.customer_name}</p>
                <p className="text-xs text-slate-500">{pmtDialog.invoice.invoice_number} · Balance: {formatPHP(pmtDialog.invoice.remaining_balance)}</p>
              </div>
              <div><Label>Amount Paid</Label>
                <Input type="number" min={0} step="0.01" value={pmtAmount}
                  onChange={e => setPmtAmount(e.target.value)}
                  placeholder={`Max ${formatPHP(pmtDialog.invoice.remaining_balance)}`}
                  className="h-9 mt-1 font-mono" autoFocus /></div>
              <div className="flex gap-2 pt-1">
                <Button variant="outline" className="flex-1" onClick={() => setPmtDialog({ open: false, invoice: null })}>Cancel</Button>
                <Button className="flex-1 bg-blue-600 text-white" onClick={quickReceivePayment} disabled={pmtSaving}>
                  {pmtSaving ? <RefreshCw size={13} className="animate-spin mr-1" /> : null} Record Payment
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Low Stock Report Dialog ── */}
      <Dialog open={lowStockDialog} onOpenChange={setLowStockDialog}>
        <DialogContent className="sm:max-w-2xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
              <Package size={18} className="text-amber-500" /> Low Stock Alert — {currentBranch?.name}
            </DialogTitle>
          </DialogHeader>
          <ScrollArea className="max-h-[60vh] mt-2">
            {lowStockData === null ? <p className="text-center py-8 text-slate-400">Loading...</p> :
             lowStockData.length === 0 ? <p className="text-center py-8 text-emerald-600">All products are adequately stocked!</p> : (
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-white border-b border-slate-200">
                  <tr className="text-xs uppercase text-slate-500">
                    <th className="px-3 py-2 text-left">Product</th>
                    <th className="px-3 py-2 text-center">Status</th>
                    <th className="px-3 py-2 text-right">Current Qty</th>
                    <th className="px-3 py-2 text-right">Reorder Pt</th>
                    <th className="px-3 py-2 text-right">Reorder Qty</th>
                  </tr>
                </thead>
                <tbody>
                  {lowStockData.map((p, i) => (
                    <tr key={i} className="border-b border-slate-50 hover:bg-slate-50/50">
                      <td className="px-3 py-2">
                        <p className="font-medium">{p.name}</p>
                        <p className="text-xs text-slate-400 font-mono">{p.sku} · {p.category}</p>
                      </td>
                      <td className="px-3 py-2 text-center">
                        <Badge className={`text-[10px] ${p.status === 'out_of_stock' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'}`}>
                          {p.status === 'out_of_stock' ? 'Out of Stock' : 'Low Stock'}
                        </Badge>
                      </td>
                      <td className="px-3 py-2 text-right font-mono font-bold">{p.current_qty} {p.unit}</td>
                      <td className="px-3 py-2 text-right font-mono text-slate-500">{p.reorder_point || '—'}</td>
                      <td className="px-3 py-2 text-right font-mono text-slate-500">{p.reorder_quantity || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </ScrollArea>
        </DialogContent>
      </Dialog>

      {/* ── Supplier Payables Report Dialog ── */}
      <Dialog open={payablesDialog} onOpenChange={setPayablesDialog}>
        <DialogContent className="sm:max-w-2xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
              <Truck size={18} className="text-red-500" /> Outstanding Supplier Payables
            </DialogTitle>
          </DialogHeader>
          <ScrollArea className="max-h-[60vh] mt-2">
            {payablesData === null ? <p className="text-center py-8 text-slate-400">Loading...</p> :
             payablesData.length === 0 ? <p className="text-center py-8 text-emerald-600">No outstanding payables!</p> : (
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-white border-b border-slate-200">
                  <tr className="text-xs uppercase text-slate-500">
                    <th className="px-3 py-2 text-left">Supplier / PO</th>
                    <th className="px-3 py-2 text-right">Total</th>
                    <th className="px-3 py-2 text-right">Balance Due</th>
                    <th className="px-3 py-2 text-center">Due Date</th>
                    <th className="px-3 py-2 text-center">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {payablesData.map((p, i) => (
                    <tr key={i} className={`border-b border-slate-50 hover:bg-slate-50/50 ${p.is_overdue ? 'bg-red-50/50' : p.is_urgent ? 'bg-amber-50/50' : ''}`}>
                      <td className="px-3 py-2">
                        <p className="font-medium">{p.vendor}</p>
                        <p className="text-xs text-slate-400 font-mono">{p.po_number}</p>
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-slate-500">{formatPHP(p.subtotal)}</td>
                      <td className="px-3 py-2 text-right font-mono font-bold text-red-700">{formatPHP(p.balance)}</td>
                      <td className="px-3 py-2 text-center">
                        <p className={`text-xs font-medium ${p.is_overdue ? 'text-red-700' : p.is_urgent ? 'text-amber-700' : 'text-slate-500'}`}>
                          {p.due_date || '—'}
                        </p>
                        {p.days_until_due !== null && (
                          <p className={`text-[10px] ${p.is_overdue ? 'text-red-500' : p.is_urgent ? 'text-amber-500' : 'text-slate-400'}`}>
                            {p.is_overdue ? `${Math.abs(p.days_until_due)}d overdue` : `${p.days_until_due}d left`}
                          </p>
                        )}
                      </td>
                      <td className="px-3 py-2 text-center">
                        <Badge className={`text-[10px] ${p.is_overdue ? 'bg-red-100 text-red-700' : p.is_urgent ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-600'}`}>
                          {p.is_overdue ? 'OVERDUE' : p.is_urgent ? 'DUE SOON' : 'Pending'}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </ScrollArea>
          <div className="flex justify-end pt-2">
            <Button variant="outline" onClick={() => navigate('/pay-supplier')}>
              <ExternalLink size={13} className="mr-1.5" /> Go to Pay Supplier
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
