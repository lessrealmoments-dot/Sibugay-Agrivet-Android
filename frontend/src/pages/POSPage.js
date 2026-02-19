import { useState, useEffect, useRef } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Label } from '../components/ui/label';
import { Card } from '../components/ui/card';
import { ScrollArea } from '../components/ui/scroll-area';
import { Separator } from '../components/ui/separator';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Search, Plus, Minus, Trash2, ShoppingCart, CreditCard, X, Wifi, WifiOff, RefreshCw, FileText, Lock, Printer } from 'lucide-react';
import { toast } from 'sonner';
import {
  cacheProducts, getProducts, cacheCustomers, getCustomers,
  cachePriceSchemes, getPriceSchemes, addPendingSale, getPendingSaleCount
} from '../lib/offlineDB';
import { syncPendingSales, refreshPOSCache, startAutoSync, stopAutoSync } from '../lib/syncManager';

export default function POSPage() {
  const { currentBranch, user } = useAuth();
  const [allProducts, setAllProducts] = useState([]);
  const [filteredProducts, setFilteredProducts] = useState([]);
  const [search, setSearch] = useState('');
  const [cart, setCart] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [paymentMethod, setPaymentMethod] = useState('Cash');
  const [discount, setDiscount] = useState(0);
  const [checkoutDialog, setCheckoutDialog] = useState(false);
  const [amountTendered, setAmountTendered] = useState(0);
  const [schemes, setSchemes] = useState([]);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [pendingCount, setPendingCount] = useState(0);
  const [dataLoaded, setDataLoaded] = useState(false);
  const [reportDialog, setReportDialog] = useState(false);
  const [closeDialog, setCloseDialog] = useState(false);
  const [dailyReport, setDailyReport] = useState(null);
  const [closing, setClosing] = useState(null);
  const [closeForm, setCloseForm] = useState({ actual_cash: 0, bank_checks: 0, other_payment_forms: 0, cash_to_drawer: 0, cash_to_safe: 0 });
  const [closingResult, setClosingResult] = useState(null);
  const searchRef = useRef(null);

  // Online/Offline detection
  useEffect(() => {
    const goOnline = async () => {
      setIsOnline(true);
      toast.success('Back online! Syncing pending sales...');
      const result = await syncPendingSales();
      if (result?.synced > 0) {
        toast.success(`${result.synced} offline sale(s) synced!`);
      }
      const count = await getPendingSaleCount();
      setPendingCount(count);
      // Refresh data from server
      await loadPOSData(true);
    };
    const goOffline = () => {
      setIsOnline(false);
      toast('Offline Mode - Sales will be saved locally', { duration: 4000 });
    };
    window.addEventListener('online', goOnline);
    window.addEventListener('offline', goOffline);
    startAutoSync();
    return () => {
      window.removeEventListener('online', goOnline);
      window.removeEventListener('offline', goOffline);
      stopAutoSync();
    };
  }, []);

  // Load POS data (API when online, IndexedDB when offline)
  const loadPOSData = async (forceOnline = false) => {
    const online = forceOnline || navigator.onLine;
    if (online) {
      try {
        const res = await api.get('/sync/pos-data');
        setAllProducts(res.data.products);
        setCustomers(res.data.customers);
        setSchemes(res.data.price_schemes);
        // Cache to IndexedDB for offline use
        await Promise.all([
          cacheProducts(res.data.products),
          cacheCustomers(res.data.customers),
          cachePriceSchemes(res.data.price_schemes),
        ]);
        setDataLoaded(true);
        return;
      } catch (e) {
        console.warn('API failed, falling back to offline cache');
      }
    }
    // Offline fallback: read from IndexedDB
    const [prods, custs, schs] = await Promise.all([
      getProducts(), getCustomers(), getPriceSchemes()
    ]);
    setAllProducts(prods);
    setCustomers(custs);
    setSchemes(schs);
    setDataLoaded(true);
  };

  useEffect(() => {
    loadPOSData();
    getPendingSaleCount().then(setPendingCount);
  }, []);

  // Client-side product search/filter
  useEffect(() => {
    if (!search) {
      setFilteredProducts(allProducts);
    } else {
      const q = search.toLowerCase();
      setFilteredProducts(allProducts.filter(p =>
        p.name.toLowerCase().includes(q) || p.sku.toLowerCase().includes(q) || (p.barcode && p.barcode.includes(q))
      ));
    }
  }, [search, allProducts]);

  const getPriceForCustomer = (product) => {
    const scheme = selectedCustomer?.price_scheme || 'retail';
    return product.prices?.[scheme] || product.prices?.retail || product.cost_price || 0;
  };

  const addToCart = (product) => {
    const existing = cart.find(c => c.product_id === product.id);
    const price = getPriceForCustomer(product);
    if (existing) {
      setCart(cart.map(c => c.product_id === product.id ? { ...c, quantity: c.quantity + 1, total: (c.quantity + 1) * c.price } : c));
    } else {
      setCart([...cart, {
        product_id: product.id, product_name: product.name, sku: product.sku,
        price, quantity: 1, total: price, unit: product.unit, is_repack: product.is_repack,
        cost_price: product.cost_price || 0,
      }]);
    }
  };

  const updateQty = (productId, delta) => {
    setCart(cart.map(c => {
      if (c.product_id !== productId) return c;
      const newQty = Math.max(0, c.quantity + delta);
      return newQty === 0 ? null : { ...c, quantity: newQty, total: newQty * c.price };
    }).filter(Boolean));
  };

  const setItemQty = (productId, qty) => {
    const newQty = Math.max(0, parseFloat(qty) || 0);
    if (newQty === 0) { removeFromCart(productId); return; }
    setCart(cart.map(c => c.product_id === productId ? { ...c, quantity: newQty, total: newQty * c.price } : c));
  };

  const setItemPrice = (productId, newPrice) => {
    const price = parseFloat(newPrice) || 0;
    setCart(cart.map(c => c.product_id === productId ? { ...c, price, total: c.quantity * price } : c));
  };

  const validateItemPrice = (productId) => {
    const item = cart.find(c => c.product_id === productId);
    if (!item) return;
    if (item.price > 0 && item.price < item.cost_price) {
      toast.error(`Cannot sell below capital (₱${item.cost_price.toFixed(2)}). Reverting price.`);
      setCart(cart.map(c => c.product_id === productId ? { ...c, price: c.cost_price, total: c.quantity * c.cost_price } : c));
    }
  };

  const removeFromCart = (productId) => setCart(cart.filter(c => c.product_id !== productId));
  const clearCart = () => { setCart([]); setSelectedCustomer(null); setDiscount(0); };

  const subtotal = cart.reduce((sum, c) => sum + c.total, 0);
  const grandTotal = subtotal - discount;
  const change = amountTendered - grandTotal;

  const handleCheckout = async () => {
    if (!currentBranch) { toast.error('Select a branch first'); return; }
    if (!cart.length) { toast.error('Cart is empty'); return; }

    const saleId = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    const saleNumber = `SL-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-${saleId.slice(0, 6).toUpperCase()}`;

    const saleData = {
      id: saleId,
      sale_number: saleNumber,
      branch_id: currentBranch.id,
      customer_id: selectedCustomer?.id || null,
      customer_name: selectedCustomer?.name || 'Walk-in',
      items: cart.map(c => ({
        product_id: c.product_id, product_name: c.product_name, sku: c.sku,
        quantity: c.quantity, price: c.price, total: c.total, is_repack: c.is_repack || false,
      })),
      subtotal,
      discount,
      total: grandTotal,
      payment_method: paymentMethod,
      payment_details: paymentMethod === 'Cash' ? { tendered: amountTendered, change: Math.max(0, change) } : {},
      cashier_id: user?.id,
      cashier_name: user?.full_name || user?.username,
      status: 'completed',
      created_at: new Date().toISOString(),
    };

    if (isOnline) {
      try {
        const res = await api.post('/sales', saleData);
        toast.success(`Sale ${res.data.sale_number} completed!`);
      } catch (e) {
        // API failed while online - save offline as fallback
        await addPendingSale(saleData);
        const count = await getPendingSaleCount();
        setPendingCount(count);
        toast.success(`Sale saved offline (will sync when stable)`);
      }
    } else {
      // Offline: save locally
      await addPendingSale(saleData);
      const count = await getPendingSaleCount();
      setPendingCount(count);
      toast.success(`Sale ${saleNumber} saved offline!`);
    }

    clearCart();
    setCheckoutDialog(false);
  };

  const today = new Date().toISOString().slice(0, 10);

  const loadDailyReport = async () => {
    if (!currentBranch) return;
    try {
      const [reportRes, closeRes] = await Promise.all([
        api.get('/daily-report', { params: { date: today, branch_id: currentBranch.id } }),
        api.get(`/daily-close/${today}`, { params: { branch_id: currentBranch.id } }),
      ]);
      setDailyReport(reportRes.data);
      setClosing(closeRes.data);
    } catch (e) { toast.error('Failed to load report'); }
  };

  const openReport = async () => { await loadDailyReport(); setReportDialog(true); };
  const openClose = async () => {
    await loadDailyReport();
    const closeRes = await api.get(`/daily-close/${today}`, { params: { branch_id: currentBranch?.id } });
    if (closeRes.data?.status === 'closed') { setClosingResult(closeRes.data); }
    else { setClosingResult(null); }
    setCloseDialog(true);
  };

  const handleCloseDay = async () => {
    if (!window.confirm(`Close accounts for ${today}? This locks all transactions.`)) return;
    try {
      const res = await api.post('/daily-close', { ...closeForm, date: today, branch_id: currentBranch.id });
      toast.success(`Day closed! Extra cash: ${formatPHP(res.data.extra_cash)}`);
      setClosingResult(res.data);
    } catch (e) { toast.error(e.response?.data?.detail || 'Error closing day'); }
  };

  const PrintableReport = ({ data }) => {
    if (!data) return null;
    const r = dailyReport;
    const expectedCash = Math.round(((r?.total_revenue || 0) + (r?.total_payments || 0) - (r?.total_expenses || 0) + (data.previous_cashier_balance || 0)) * 100) / 100;
    const isOwner = user?.role === 'admin';
    // Categorize expenses
    const allExpenses = data.expenses || r?.expenses || [];
    const empAdvances = allExpenses.filter(e => e.category === 'Employee Cash Advance');
    const farmExps = allExpenses.filter(e => e.category === 'Farm Expense');
    const otherExps = allExpenses.filter(e => !['Employee Cash Advance', 'Farm Expense'].includes(e.category));

    return (
      <div id="printable-report" className="max-w-[680px] mx-auto bg-white" style={{ fontFamily: 'IBM Plex Sans, sans-serif' }}>
        {/* Title */}
        <div className="text-center mb-4">
          <h2 className="text-xl font-bold tracking-tight" style={{ color: '#1a365d', fontFamily: 'Manrope' }}>DAILY CLOSING REPORT</h2>
          <p className="text-sm text-slate-600">{new Date(data.date || today).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}</p>
          {data.closed_by_name && <p className="text-[11px] text-slate-400 mt-1">Closed by {data.closed_by_name}</p>}
        </div>

        {/* GENERAL DETAILS */}
        <div className="rpt-header">General Details</div>
        <div className="rpt-row"><span>Total Cash in Safe:</span><b>{formatPHP(data.safe_balance)}</b></div>
        <div className="rpt-row"><span>Total Cash in Bank:</span><b>{isOwner ? formatPHP(data.bank_balance) : 'HIDDEN'}</b></div>
        <div className="rpt-row"><span>Cash Deposit to Safe Today:</span><b>{formatPHP(data.cash_deposited_to_safe)}</b></div>
        <div className="rpt-row"><span>Previous Cashier Balance:</span><b>{formatPHP(data.previous_cashier_balance)}</b></div>

        {/* SALES / PAYMENTS TODAY */}
        <div className="rpt-header">Sales / Payments Today</div>
        {Object.entries(data.sales_by_category || r?.sales_by_category || {}).map(([cat, val]) => (
          <div key={cat} className="rpt-row"><span>{cat}:</span><b>{formatPHP(typeof val === 'object' ? val.total : val)}</b></div>
        ))}
        {Object.keys(data.sales_by_category || r?.sales_by_category || {}).length === 0 && (
          <div className="rpt-row text-slate-400"><span>No sales recorded</span><b>₱0.00</b></div>
        )}

        {/* PAYMENTS RECEIVED TODAY */}
        <div className="rpt-header">Payments Received Today</div>
        {(data.payments_received?.length > 0 || r?.payments_today?.length > 0) ? (
          <table className="w-full text-xs border-collapse mt-1">
            <thead>
              <tr style={{ backgroundColor: '#1a365d', color: 'white' }}>
                <th className="text-left py-2 px-3 font-semibold">Payee</th>
                <th className="text-right py-2 px-3 font-semibold">Open Balance</th>
                <th className="text-right py-2 px-3 font-semibold">Principal Paid</th>
                <th className="text-right py-2 px-3 font-semibold">Interest Paid</th>
                <th className="text-right py-2 px-3 font-semibold">Penalty Paid</th>
                <th className="text-right py-2 px-3 font-semibold">Total Payment</th>
              </tr>
            </thead>
            <tbody>
              {(data.payments_received || []).map((p, i) => (
                <tr key={i} className={i % 2 === 0 ? 'bg-slate-50' : 'bg-white'}>
                  <td className="py-1.5 px-3 text-left">{p.customer || p.customer_name}</td>
                  <td className="py-1.5 px-3 text-right">{formatPHP(p.balance)}</td>
                  <td className="py-1.5 px-3 text-right">{formatPHP(p.principal_paid)}</td>
                  <td className="py-1.5 px-3 text-right">{formatPHP(p.interest_paid || 0)}</td>
                  <td className="py-1.5 px-3 text-right">{formatPHP(p.penalty_paid || 0)}</td>
                  <td className="py-1.5 px-3 text-right font-semibold">{formatPHP(p.total_paid)}</td>
                </tr>
              ))}
              {r?.payments_today?.map((p, i) => (
                <tr key={`api-${i}`} className={i % 2 === 0 ? 'bg-slate-50' : 'bg-white'}>
                  <td className="py-1.5 px-3">{p.customer_name}</td>
                  <td className="py-1.5 px-3 text-right">{formatPHP(p.balance)}</td>
                  <td className="py-1.5 px-3 text-right">{formatPHP(p.payment?.applied_to_principal || p.payment?.amount)}</td>
                  <td className="py-1.5 px-3 text-right">{formatPHP(p.payment?.applied_to_interest || 0)}</td>
                  <td className="py-1.5 px-3 text-right">₱0.00</td>
                  <td className="py-1.5 px-3 text-right font-semibold">{formatPHP(p.payment?.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="rpt-row text-slate-400"><span>No payments received</span></div>
        )}

        {/* EXPENSES FOR TODAY */}
        <div className="rpt-header">Expenses for Today</div>
        <div className="px-4 py-2 space-y-1 text-[13px]">
          {empAdvances.map((e, i) => (
            <div key={`adv-${i}`} className="flex items-baseline gap-1">
              <span className="text-slate-600">&#8226;</span>
              <span>Employee Cash Advance: <b>{formatPHP(e.amount)}</b></span>
              <span className="text-xs text-slate-400 ml-1">(Total CA This Month: {formatPHP(e.monthly_total || 0)})</span>
            </div>
          ))}
          {otherExps.map((e, i) => (
            <div key={`oth-${i}`} className="flex items-baseline gap-1">
              <span className="text-slate-600">&#8226;</span>
              <span>{e.category || e.description}: <b>{formatPHP(e.amount)}</b></span>
            </div>
          ))}
          {farmExps.map((e, i) => (
            <div key={`farm-${i}`} className="flex items-baseline gap-1">
              <span className="text-slate-600">&#8226;</span>
              <span>Farm Charge - {e.description?.replace('Farm Cash Out - ', '')}: <b>{formatPHP(e.amount)}</b></span>
            </div>
          ))}
          {allExpenses.length === 0 && <p className="text-slate-400 text-sm">No expenses recorded</p>}
        </div>

        {/* CASH COUNTING */}
        <div className="rpt-header">Cash Counting</div>
        <div className="rpt-row"><span>Expected Cash in Drawer:</span><b>{formatPHP(data.expected_cash || expectedCash)}</b></div>
        <div className="rpt-row"><span>Actual Cash in Drawer:</span><b>{formatPHP(data.actual_cash)}</b></div>
        <div className="rpt-row"><span>Bank Checks:</span><b>{formatPHP(data.bank_checks)}</b></div>
        <div className="rpt-row"><span>Other Payments (GCash, etc.):</span><b>{formatPHP(data.other_payment_forms)}</b></div>

        {/* ALLOCATION BOX */}
        <div className="rpt-alloc">
          <div className="rpt-row"><span>Cash to Leave in Drawer:</span><b>{formatPHP(data.cash_to_drawer)}</b></div>
          <div className="rpt-row"><span>Cash Transferred to Safe:</span><b>{formatPHP(data.cash_to_safe)}</b></div>
          <div className="rpt-extra">
            <span>EXTRA MONEY ({(data.extra_cash || 0) >= 0 ? 'Over' : 'Short'}):</span>
            <span>{formatPHP(Math.abs(data.extra_cash || 0))}</span>
          </div>
        </div>

        <p className="text-[10px] text-slate-400 text-center mt-4 italic">
          Extra cash may be used to offset missing inventory during stock counts. If missing inventory exceeds extra cash, cashier is responsible for the difference.
        </p>
      </div>
    );
  };

  return (
    <div className="pos-grid -m-4 lg:-m-6" data-testid="pos-page">
      {/* Left: Products */}
      <div className="pos-products p-4">
        <div className="flex items-center gap-3 mb-4">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <Input
              ref={searchRef}
              data-testid="pos-search"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search product or scan barcode..."
              className="pl-9 h-11 text-base"
              autoFocus
            />
          </div>
          <div className={`flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-medium ${isOnline ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
            {isOnline ? <Wifi size={14} /> : <WifiOff size={14} />}
            {isOnline ? 'Online' : 'Offline'}
            {pendingCount > 0 && (
              <Badge className="ml-1 h-5 bg-amber-500 text-white text-[10px]">{pendingCount} pending</Badge>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {filteredProducts.map(p => (
            <button
              key={p.id}
              data-testid={`pos-product-${p.id}`}
              onClick={() => addToCart(p)}
              className="text-left p-3 rounded-lg border border-slate-200 bg-white hover:border-[#1A4D2E]/40 hover:shadow-sm transition-all duration-200 active:scale-[0.98]"
            >
              <p className="font-medium text-sm truncate">{p.name}</p>
              <p className="text-[11px] text-slate-400 font-mono mt-0.5">{p.sku}</p>
              <div className="flex items-center justify-between mt-2">
                <span className="text-base font-bold text-[#1A4D2E]">₱{getPriceForCustomer(p).toFixed(2)}</span>
                {p.is_repack && <Badge variant="outline" className="text-[9px] border-amber-300 text-amber-600">R</Badge>}
              </div>
              <p className="text-[10px] text-slate-400 mt-1">per {p.unit}</p>
            </button>
          ))}
          {!filteredProducts.length && (
            <div className="col-span-full text-center py-12 text-slate-400 text-sm">
              {dataLoaded ? 'No products found' : 'Loading products...'}
            </div>
          )}
        </div>
      </div>

      {/* Right: Cart */}
      <div className="pos-cart bg-white flex flex-col">
        <div className="p-4 border-b border-slate-100">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-bold text-lg" style={{ fontFamily: 'Manrope' }}>
              <ShoppingCart size={18} className="inline mr-2 text-[#1A4D2E]" />Cart
            </h3>
            {cart.length > 0 && (
              <Button variant="ghost" size="sm" onClick={clearCart} className="text-red-500 text-xs">
                <X size={12} className="mr-1" /> Clear
              </Button>
            )}
          </div>
          <Select
            value={selectedCustomer?.id || 'walk-in'}
            onValueChange={v => {
              if (v === 'walk-in') setSelectedCustomer(null);
              else setSelectedCustomer(customers.find(c => c.id === v));
            }}
          >
            <SelectTrigger data-testid="pos-customer-select" className="h-9 text-sm">
              <SelectValue placeholder="Walk-in Customer" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="walk-in">Walk-in Customer</SelectItem>
              {customers.map(c => (
                <SelectItem key={c.id} value={c.id}>{c.name} ({c.price_scheme})</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <ScrollArea className="flex-1">
          <div className="p-4 space-y-3">
            {cart.map(item => (
              <div key={item.product_id} className="p-3 rounded-lg bg-slate-50 animate-slideIn">
                <div className="flex items-center justify-between mb-1.5">
                  <p className="text-sm font-medium truncate flex-1">{item.product_name}</p>
                  <button onClick={() => removeFromCart(item.product_id)} className="text-red-400 hover:text-red-600 ml-2">
                    <Trash2 size={12} />
                  </button>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1">
                    <Button variant="outline" size="sm" className="h-7 w-7 p-0" data-testid={`cart-minus-${item.product_id}`} onClick={() => updateQty(item.product_id, -1)}>
                      <Minus size={12} />
                    </Button>
                    <input
                      type="number"
                      min="0"
                      value={item.quantity}
                      onChange={e => setItemQty(item.product_id, e.target.value)}
                      className="w-12 h-7 text-center text-sm font-bold border border-slate-200 rounded focus:outline-none focus:border-[#1A4D2E]"
                      data-testid={`cart-qty-${item.product_id}`}
                    />
                    <Button variant="outline" size="sm" className="h-7 w-7 p-0" data-testid={`cart-plus-${item.product_id}`} onClick={() => updateQty(item.product_id, 1)}>
                      <Plus size={12} />
                    </Button>
                  </div>
                  <span className="text-xs text-slate-400">x</span>
                  <div className="flex items-center gap-0.5">
                    <span className="text-xs text-slate-400">₱</span>
                    <input
                      type="number"
                      min="0"
                      value={item.price}
                      onChange={e => setItemPrice(item.product_id, e.target.value)}
                      className="w-20 h-7 text-right text-sm font-semibold border border-slate-200 rounded focus:outline-none focus:border-[#1A4D2E]"
                      data-testid={`cart-price-${item.product_id}`}
                    />
                  </div>
                  <span className="text-sm font-bold text-right flex-1">₱{item.total.toFixed(2)}</span>
                </div>
              </div>
            ))}
            {!cart.length && (
              <div className="text-center py-12 text-slate-300">
                <ShoppingCart size={40} className="mx-auto mb-3" />
                <p className="text-sm">Cart is empty</p>
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Cart Footer */}
        <div className="border-t border-slate-100 p-4 space-y-3 bg-slate-50/50">
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-500">Subtotal</span>
            <span className="font-semibold">₱{subtotal.toFixed(2)}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-500">Discount</span>
            <Input
              data-testid="pos-discount"
              type="number"
              value={discount}
              onChange={e => setDiscount(parseFloat(e.target.value) || 0)}
              className="h-8 w-24 text-sm ml-auto"
              min={0}
            />
          </div>
          <div className="flex items-center justify-between pt-2 border-t border-slate-200">
            <span className="text-lg font-bold" style={{ fontFamily: 'Manrope' }}>Total</span>
            <span className="text-2xl font-bold text-[#1A4D2E]" style={{ fontFamily: 'Manrope' }}>₱{grandTotal.toFixed(2)}</span>
          </div>
          <Button
            data-testid="pos-checkout-btn"
            disabled={!cart.length}
            onClick={() => { setAmountTendered(grandTotal); setCheckoutDialog(true); }}
            className="w-full h-12 text-base bg-[#1A4D2E] hover:bg-[#14532d] text-white"
          >
            <CreditCard size={18} className="mr-2" /> Checkout
          </Button>
          <div className="flex gap-2 pt-1">
            <Button variant="outline" size="sm" className="flex-1 text-xs" data-testid="pos-today-report" onClick={openReport}>
              <FileText size={14} className="mr-1" /> Today's Report
            </Button>
            <Button variant="outline" size="sm" className="flex-1 text-xs border-red-200 text-red-600 hover:bg-red-50" data-testid="pos-close-day" onClick={openClose}>
              <Lock size={14} className="mr-1" /> Close Day
            </Button>
          </div>
        </div>
      </div>

      {/* Checkout Dialog */}
      <Dialog open={checkoutDialog} onOpenChange={setCheckoutDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Complete Sale</DialogTitle></DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="p-4 bg-emerald-50 rounded-lg text-center">
              <p className="text-sm text-emerald-600">Total Amount</p>
              <p className="text-3xl font-bold text-emerald-800" style={{ fontFamily: 'Manrope' }}>₱{grandTotal.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-sm font-medium mb-2">Payment Method</p>
              <div className="grid grid-cols-2 gap-2">
                {['Cash', 'Voucher', 'Digital Wallet', 'Credit'].map(m => (
                  <Button
                    key={m}
                    variant={paymentMethod === m ? 'default' : 'outline'}
                    size="sm"
                    data-testid={`payment-${m.toLowerCase().replace(' ', '-')}`}
                    onClick={() => setPaymentMethod(m)}
                    className={paymentMethod === m ? 'bg-[#1A4D2E] text-white' : ''}
                  >
                    {m}
                  </Button>
                ))}
              </div>
            </div>
            {paymentMethod === 'Cash' && (
              <div>
                <p className="text-sm font-medium mb-1">Amount Tendered</p>
                <Input
                  data-testid="amount-tendered"
                  type="number"
                  value={amountTendered}
                  onChange={e => setAmountTendered(parseFloat(e.target.value) || 0)}
                  className="h-12 text-xl text-center font-bold"
                />
                {change >= 0 && (
                  <p className="text-center mt-2 text-lg font-bold text-emerald-600">Change: {change.toFixed(2)}</p>
                )}
              </div>
            )}
            <Button
              data-testid="confirm-sale-btn"
              onClick={handleCheckout}
              className="w-full h-12 text-base bg-[#1A4D2E] hover:bg-[#14532d] text-white"
            >
              Confirm Sale
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Today's Report Dialog */}
      <Dialog open={reportDialog} onOpenChange={setReportDialog}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <div className="flex items-center justify-between">
              <DialogTitle style={{ fontFamily: 'Manrope' }}>Today's Sales Report — {today}</DialogTitle>
              <Button variant="outline" size="sm" onClick={() => window.print()}><Printer size={14} className="mr-1" /> Print</Button>
            </div>
          </DialogHeader>
          {dailyReport ? (
            <div className="max-w-[680px] mx-auto" style={{ fontFamily: 'IBM Plex Sans, sans-serif' }}>
              <div className="text-center mb-3">
                <h2 className="text-lg font-bold" style={{ color: '#1a365d', fontFamily: 'Manrope' }}>TODAY'S SALES REPORT</h2>
                <p className="text-xs text-slate-500">{currentBranch?.name} &middot; {new Date(today).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}</p>
              </div>
              <div className="rpt-header">Summary</div>
              <div className="rpt-row"><span>Total Revenue:</span><b className="text-emerald-700">{formatPHP(dailyReport.total_revenue)}</b></div>
              <div className="rpt-row"><span>Cost of Goods Sold:</span><b>{formatPHP(dailyReport.total_cogs)}</b></div>
              <div className="rpt-row"><span>Gross Profit:</span><b className={dailyReport.gross_profit >= 0 ? 'text-emerald-700' : 'text-red-600'}>{formatPHP(dailyReport.gross_profit)}</b></div>
              <div className="rpt-row"><span>Total Expenses:</span><b className="text-red-600">{formatPHP(dailyReport.total_expenses)}</b></div>
              <div className="rpt-row" style={{ backgroundColor: dailyReport.net_profit >= 0 ? '#ecfdf5' : '#fef2f2' }}>
                <span className="font-bold">Net Profit:</span>
                <b className={dailyReport.net_profit >= 0 ? 'text-emerald-700' : 'text-red-700'}>{formatPHP(dailyReport.net_profit)}</b>
              </div>

              <div className="rpt-header">Sales by Category</div>
              {Object.entries(dailyReport.sales_by_category || {}).map(([cat, d]) => (
                <div key={cat} className="rpt-row"><span>{cat}:</span><b>{formatPHP(typeof d === 'object' ? d.total : d)}</b></div>
              ))}

              {dailyReport.payments_today?.length > 0 && (
                <>
                  <div className="rpt-header">Payments Received</div>
                  <table className="w-full text-xs border-collapse mt-1">
                    <thead><tr style={{ backgroundColor: '#1a365d', color: 'white' }}>
                      <th className="text-left py-1.5 px-3 font-semibold">Payee</th>
                      <th className="text-left py-1.5 px-3 font-semibold">Invoice</th>
                      <th className="text-right py-1.5 px-3 font-semibold">Amount</th>
                    </tr></thead>
                    <tbody>{dailyReport.payments_today.map((p, i) => (
                      <tr key={i} className={i % 2 === 0 ? 'bg-slate-50' : ''}>
                        <td className="py-1 px-3">{p.customer_name}</td>
                        <td className="py-1 px-3 font-mono">{p.invoice_number}</td>
                        <td className="py-1 px-3 text-right font-semibold">{formatPHP(p.payment?.amount)}</td>
                      </tr>
                    ))}</tbody>
                  </table>
                </>
              )}

              {dailyReport.expenses?.length > 0 && (
                <>
                  <div className="rpt-header">Expenses</div>
                  <div className="px-4 py-2 space-y-1 text-[13px]">
                    {dailyReport.expenses.map((e, i) => (
                      <div key={i} className="flex items-baseline gap-1">
                        <span>&#8226;</span>
                        <span>{e.category}: {e.description} <b className="text-red-600">{formatPHP(e.amount)}</b></span>
                      </div>
                    ))}
                  </div>
                </>
              )}
              <div className="text-xs text-slate-400 text-center pt-3">{dailyReport.transaction_count} transactions today</div>
            </div>
          ) : <p className="text-center py-8 text-slate-400">Loading...</p>}
        </DialogContent>
      </Dialog>

      {/* Close Day Dialog */}
      <Dialog open={closeDialog} onOpenChange={setCloseDialog}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <div className="flex items-center justify-between">
              <DialogTitle style={{ fontFamily: 'Manrope' }}>
                {closingResult ? 'Daily Closing Report' : 'Close Accounts'} — {today}
              </DialogTitle>
              {closingResult && <Button variant="outline" size="sm" onClick={() => window.print()}><Printer size={14} className="mr-1" /> Print</Button>}
            </div>
          </DialogHeader>
          {closingResult ? (
            <PrintableReport data={closingResult} />
          ) : (
            <div className="space-y-4 mt-2">
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
                This will lock all transactions for {today}. New sales will go to the next day.
              </div>
              {dailyReport && (
                <div className="grid grid-cols-3 gap-3 text-sm">
                  <div className="p-3 bg-slate-50 rounded-lg"><p className="text-xs text-slate-500">Sales</p><p className="font-bold">{formatPHP(dailyReport.total_revenue)}</p></div>
                  <div className="p-3 bg-slate-50 rounded-lg"><p className="text-xs text-slate-500">Payments</p><p className="font-bold">{formatPHP(dailyReport.total_payments)}</p></div>
                  <div className="p-3 bg-slate-50 rounded-lg"><p className="text-xs text-slate-500">Expenses</p><p className="font-bold text-red-600">{formatPHP(dailyReport.total_expenses)}</p></div>
                </div>
              )}
              <Separator />
              <h3 className="font-bold text-sm" style={{ fontFamily: 'Manrope' }}>Cash Counting</h3>
              <p className="text-xs text-slate-500">Expected Cash: <span className="font-bold text-slate-800">{formatPHP(
                ((dailyReport?.total_revenue || 0) + (dailyReport?.total_payments || 0) - (dailyReport?.total_expenses || 0))
              )}</span></p>
              <div className="grid grid-cols-2 gap-3">
                <div><Label className="text-xs">Actual Cash Count</Label><Input type="number" value={closeForm.actual_cash} onChange={e => setCloseForm(f => ({ ...f, actual_cash: parseFloat(e.target.value) || 0 }))} className="h-10 text-lg font-bold" data-testid="close-actual-cash" /></div>
                <div><Label className="text-xs">Bank Checks</Label><Input type="number" value={closeForm.bank_checks} onChange={e => setCloseForm(f => ({ ...f, bank_checks: parseFloat(e.target.value) || 0 }))} className="h-10" /></div>
                <div><Label className="text-xs">Other (GCash, transfers)</Label><Input type="number" value={closeForm.other_payment_forms} onChange={e => setCloseForm(f => ({ ...f, other_payment_forms: parseFloat(e.target.value) || 0 }))} className="h-10" /></div>
                <div><Label className="text-xs">Extra Cash</Label>
                  <div className={`h-10 flex items-center px-3 rounded-md font-bold ${(closeForm.actual_cash - ((dailyReport?.total_revenue || 0) + (dailyReport?.total_payments || 0) - (dailyReport?.total_expenses || 0) - closeForm.bank_checks - closeForm.other_payment_forms)) >= 0 ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'}`}>
                    {formatPHP(Math.round((closeForm.actual_cash - ((dailyReport?.total_revenue || 0) + (dailyReport?.total_payments || 0) - (dailyReport?.total_expenses || 0) - closeForm.bank_checks - closeForm.other_payment_forms)) * 100) / 100)}
                  </div>
                </div>
              </div>
              <Separator />
              <h3 className="font-bold text-sm" style={{ fontFamily: 'Manrope' }}>End-of-Day Allocation</h3>
              <div className="grid grid-cols-2 gap-3">
                <div><Label className="text-xs">Cash Remaining in Drawer</Label><Input type="number" value={closeForm.cash_to_drawer} onChange={e => setCloseForm(f => ({ ...f, cash_to_drawer: parseFloat(e.target.value) || 0 }))} className="h-10" /></div>
                <div><Label className="text-xs">Cash to Transfer to Safe</Label><Input type="number" value={closeForm.cash_to_safe} onChange={e => setCloseForm(f => ({ ...f, cash_to_safe: parseFloat(e.target.value) || 0 }))} className="h-10" /></div>
              </div>
              <Button onClick={handleCloseDay} className="w-full h-11 bg-red-600 hover:bg-red-700 text-white" data-testid="confirm-close-day">
                <Lock size={16} className="mr-2" /> Close Accounts for {today}
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
