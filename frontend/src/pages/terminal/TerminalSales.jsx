import { useState, useEffect, useRef, useCallback } from 'react';
import { Search, Plus, Minus, Trash2, ShoppingCart, Camera, X, Check, CreditCard, Banknote, ChevronUp, ChevronDown } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { toast } from 'sonner';
import { formatPHP } from '../../lib/utils';
import {
  getProducts, getCustomers, getPriceSchemes,
  addPendingSale, getPendingSaleCount, getInventoryItem, getBranchPrice,
} from '../../lib/offlineDB';
import { newEnvelopeId } from '../../lib/syncManager';

export default function TerminalSales({ api, session, isOnline, pendingCount, setPendingCount }) {
  const [products, setProducts] = useState([]);
  const [search, setSearch] = useState('');
  const [results, setResults] = useState([]);
  const [cart, setCart] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [schemes, setSchemes] = useState([]);
  const [activeScheme, setActiveScheme] = useState('retail');
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [scannerActive, setScannerActive] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [custSearch, setCustSearch] = useState('');
  const [showCustList, setShowCustList] = useState(false);
  const [cartExpanded, setCartExpanded] = useState(true);
  const searchRef = useRef(null);
  const scannerRef = useRef(null);
  const scannerContainerRef = useRef(null);

  // Load cached data
  useEffect(() => {
    (async () => {
      const [prods, custs, schs] = await Promise.all([getProducts(), getCustomers(), getPriceSchemes()]);
      setProducts(prods);
      setCustomers(custs);
      setSchemes(schs);
    })();
  }, []);

  // Search products
  useEffect(() => {
    if (!search.trim()) { setResults([]); return; }
    const q = search.toLowerCase();
    const filtered = products.filter(p =>
      (p.name || '').toLowerCase().includes(q) ||
      (p.sku || '').toLowerCase().includes(q) ||
      (p.barcode || '').includes(search)
    ).slice(0, 20);
    setResults(filtered);
  }, [search, products]);

  const getPrice = (product) => product.prices?.[activeScheme] ?? 0;

  const addToCart = useCallback((product) => {
    const price = product.prices?.[activeScheme] ?? 0;
    setCart(prev => {
      const existing = prev.find(c => c.product_id === product.id);
      if (existing) {
        return prev.map(c => c.product_id === product.id
          ? { ...c, quantity: c.quantity + 1, total: (c.quantity + 1) * c.price }
          : c
        );
      }
      return [...prev, {
        product_id: product.id, product_name: product.name, sku: product.sku,
        price, quantity: 1, total: price, unit: product.unit, is_repack: product.is_repack,
        cost_price: product.cost_price || 0,
        effective_capital: product.effective_capital || product.cost_price || 0,
        capital_method: product.capital_method || 'manual',
        original_price: price,
      }];
    });
    setSearch('');
    setResults([]);
    toast.success(product.name, { duration: 1500 });
  }, [activeScheme]);

  const updateQty = (productId, delta) => {
    setCart(prev => prev.map(c => {
      if (c.product_id !== productId) return c;
      const newQty = Math.max(0, c.quantity + delta);
      return newQty === 0 ? null : { ...c, quantity: newQty, total: newQty * c.price };
    }).filter(Boolean));
  };

  const removeItem = (productId) => setCart(prev => prev.filter(c => c.product_id !== productId));
  const clearCart = () => { setCart([]); setSelectedCustomer(null); setCustSearch(''); };

  const grandTotal = cart.reduce((s, c) => s + c.total, 0);

  // Camera barcode scanner
  const startScanner = async () => {
    setScannerActive(true);
    // Wait for div to render before starting scanner
    await new Promise(r => setTimeout(r, 300));
    try {
      const { Html5Qrcode } = await import('html5-qrcode');
      const scanner = new Html5Qrcode('terminal-scanner-view');
      scannerRef.current = scanner;

      await scanner.start(
        { facingMode: 'environment' },
        { fps: 10, qrbox: { width: 250, height: 100 }, aspectRatio: 1.777 },
        (decodedText) => {
          // Barcode detected
          const product = products.find(p => p.barcode === decodedText);
          if (product) {
            addToCart(product);
            if (navigator.vibrate) navigator.vibrate(100);
          } else {
            toast.error(`No product for barcode: ${decodedText}`);
          }
        },
        () => {} // ignore errors
      );
    } catch (e) {
      console.error('Scanner error:', e);
      toast.error('Camera access denied. Check browser permissions.');
      setScannerActive(false);
    }
  };

  const stopScanner = async () => {
    if (scannerRef.current) {
      try { await scannerRef.current.stop(); } catch {}
      scannerRef.current = null;
    }
    setScannerActive(false);
  };

  // Barcode keyboard listener (for hardware scanners like Newland)
  const scanBufferRef = useRef('');
  const scanTimerRef = useRef(null);

  useEffect(() => {
    const handleKeyPress = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (e.key === 'Enter' && scanBufferRef.current.length >= 3) {
        e.preventDefault();
        const barcode = scanBufferRef.current.trim();
        scanBufferRef.current = '';
        clearTimeout(scanTimerRef.current);
        const product = products.find(p => p.barcode === barcode);
        if (product) {
          addToCart(product);
          if (navigator.vibrate) navigator.vibrate(100);
        } else {
          toast.error(`No product: ${barcode}`);
        }
        return;
      }
      if (e.key.length === 1) {
        scanBufferRef.current += e.key;
        clearTimeout(scanTimerRef.current);
        scanTimerRef.current = setTimeout(() => { scanBufferRef.current = ''; }, 100);
      }
    };
    window.addEventListener('keydown', handleKeyPress);
    return () => { window.removeEventListener('keydown', handleKeyPress); clearTimeout(scanTimerRef.current); };
  }, [products, addToCart]);

  // Process sale
  const processSale = async (paymentType = 'cash') => {
    if (cart.length === 0) { toast.error('Cart is empty'); return; }
    setSaving(true);

    const saleId = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    const envelopeId = newEnvelopeId();
    const today = new Date().toISOString().slice(0, 10);

    const saleItems = cart.map(c => ({
      product_id: c.product_id, product_name: c.product_name, sku: c.sku,
      quantity: c.quantity, rate: c.price, price: c.price, total: c.total,
      discount_type: 'amount', discount_value: 0, discount_amount: 0,
      is_repack: c.is_repack || false,
    }));

    const saleData = {
      id: saleId,
      envelope_id: envelopeId,
      branch_id: session.branchId,
      customer_id: selectedCustomer?.id || null,
      customer_name: selectedCustomer?.name || 'Walk-in',
      items: saleItems,
      subtotal: grandTotal,
      freight: 0,
      overall_discount: 0,
      grand_total: grandTotal,
      amount_paid: grandTotal,
      balance: 0,
      terms: 'COD',
      terms_days: 0,
      prefix: 'KS', // Kiosk Sale prefix
      order_date: today,
      invoice_date: today,
      payment_method: 'Cash',
      payment_type: paymentType,
      fund_source: 'cashier',
      sale_type: 'walk_in',
      mode: 'quick',
      source: 'agrismart_terminal',
      terminal_id: session.terminalId,
      status: 'paid',
      created_at: new Date().toISOString(),
    };

    if (isOnline) {
      try {
        const res = await api.post('/unified-sale', saleData);
        const invoiceNum = res.data.invoice_number || res.data.sale_number;
        toast.success(`Sale ${invoiceNum} completed!`);
        clearCart();
        setCheckoutOpen(false);
      } catch {
        await addPendingSale(saleData);
        const count = await getPendingSaleCount();
        setPendingCount(count);
        toast.success('Saved offline — will sync later');
        clearCart();
        setCheckoutOpen(false);
      }
    } else {
      await addPendingSale(saleData);
      const count = await getPendingSaleCount();
      setPendingCount(count);
      toast.success('Sale saved offline');
      clearCart();
      setCheckoutOpen(false);
    }
    setSaving(false);
  };

  return (
    <div className="flex flex-col h-full" data-testid="terminal-sales">
      {/* Search Bar + Scanner Toggle */}
      <div className="p-3 bg-white border-b border-slate-200">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <Input
              ref={searchRef}
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search product or scan barcode..."
              className="pl-9 h-10 text-base"
              data-testid="terminal-search-input"
            />
            {search && (
              <button onClick={() => { setSearch(''); setResults([]); }} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400">
                <X size={16} />
              </button>
            )}
          </div>
          <Button
            variant={scannerActive ? 'default' : 'outline'}
            size="icon"
            className={`h-10 w-10 ${scannerActive ? 'bg-emerald-600 hover:bg-emerald-700' : ''}`}
            onClick={scannerActive ? stopScanner : startScanner}
            data-testid="camera-scanner-btn"
          >
            <Camera size={18} />
          </Button>
        </div>

        {/* Camera scanner view */}
        {scannerActive && (
          <div className="mt-2 rounded-xl overflow-hidden border border-slate-200 bg-black" ref={scannerContainerRef}>
            <div id="terminal-scanner-view" className="w-full" style={{ minHeight: 200 }} />
          </div>
        )}

        {/* Search results */}
        {results.length > 0 && (
          <div className="mt-2 bg-white rounded-xl border border-slate-200 shadow-lg max-h-60 overflow-auto" data-testid="search-results">
            {results.map(p => (
              <button
                key={p.id}
                onClick={() => addToCart(p)}
                className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-emerald-50 border-b border-slate-100 last:border-0 text-left"
                data-testid={`search-result-${p.id}`}
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-800 truncate">{p.name}</p>
                  <p className="text-xs text-slate-400">{p.sku} {p.barcode ? `· ${p.barcode}` : ''}</p>
                </div>
                <div className="text-right flex-shrink-0 ml-2">
                  <p className="text-sm font-bold text-[#1A4D2E]">{formatPHP(getPrice(p))}</p>
                  <p className="text-[10px] text-slate-400">Stock: {p.available ?? '—'}</p>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Cart */}
      <div className="flex-1 overflow-auto p-3">
        {cart.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-400 py-12">
            <ShoppingCart size={36} className="mb-3 opacity-30" />
            <p className="text-sm">Scan or search to add items</p>
          </div>
        ) : (
          <div className="space-y-2" data-testid="cart-items">
            {cart.map(item => (
              <div key={item.product_id} className="bg-white rounded-xl border border-slate-200 p-3 flex items-center gap-3" data-testid={`cart-item-${item.product_id}`}>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-800 truncate">{item.product_name}</p>
                  <p className="text-xs text-slate-400">{formatPHP(item.price)} each</p>
                </div>
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => updateQty(item.product_id, -1)}
                    className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-slate-600 active:bg-slate-200"
                    data-testid={`qty-minus-${item.product_id}`}
                  >
                    <Minus size={14} />
                  </button>
                  <span className="w-8 text-center text-sm font-bold" data-testid={`qty-display-${item.product_id}`}>
                    {item.quantity}
                  </span>
                  <button
                    onClick={() => updateQty(item.product_id, 1)}
                    className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-slate-600 active:bg-slate-200"
                    data-testid={`qty-plus-${item.product_id}`}
                  >
                    <Plus size={14} />
                  </button>
                </div>
                <p className="text-sm font-bold text-[#1A4D2E] w-20 text-right">{formatPHP(item.total)}</p>
                <button
                  onClick={() => removeItem(item.product_id)}
                  className="text-slate-300 hover:text-red-500 p-1"
                  data-testid={`remove-${item.product_id}`}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Bottom: Total + Checkout */}
      {cart.length > 0 && (
        <div className="bg-white border-t border-slate-200 p-3 safe-area-bottom">
          <div className="flex items-center justify-between mb-2">
            <div>
              <p className="text-xs text-slate-500">{cart.length} item(s)</p>
              <p className="text-xl font-bold text-[#1A4D2E]" data-testid="cart-total">{formatPHP(grandTotal)}</p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={clearCart} data-testid="clear-cart-btn">
                <Trash2 size={14} className="mr-1" /> Clear
              </Button>
              <Button
                onClick={() => setCheckoutOpen(true)}
                className="bg-[#1A4D2E] hover:bg-[#15412a] text-white px-6"
                data-testid="checkout-btn"
              >
                <Banknote size={16} className="mr-1.5" /> Checkout
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Checkout Dialog */}
      <Dialog open={checkoutOpen} onOpenChange={setCheckoutOpen}>
        <DialogContent className="max-w-sm mx-auto">
          <DialogHeader>
            <DialogTitle>Checkout</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {/* Customer selection */}
            <div>
              <label className="text-xs text-slate-500 font-medium mb-1 block">Customer</label>
              <Input
                value={custSearch}
                onChange={e => { setCustSearch(e.target.value); setShowCustList(true); }}
                placeholder="Walk-in (type to search)"
                className="h-9"
                data-testid="checkout-customer-input"
              />
              {showCustList && custSearch && (
                <div className="bg-white border rounded-lg mt-1 max-h-32 overflow-auto shadow-lg">
                  {customers.filter(c => c.name?.toLowerCase().includes(custSearch.toLowerCase())).slice(0, 5).map(c => (
                    <button key={c.id} onClick={() => { setSelectedCustomer(c); setCustSearch(c.name); setShowCustList(false); }}
                      className="w-full text-left px-3 py-2 text-sm hover:bg-emerald-50 border-b last:border-0">
                      {c.name}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Order summary */}
            <div className="bg-slate-50 rounded-xl p-3 space-y-1.5">
              {cart.map(c => (
                <div key={c.product_id} className="flex justify-between text-xs">
                  <span className="text-slate-600 truncate max-w-[60%]">{c.product_name} x{c.quantity}</span>
                  <span className="font-mono text-slate-800">{formatPHP(c.total)}</span>
                </div>
              ))}
              <div className="border-t border-slate-200 pt-1.5 mt-2 flex justify-between font-bold text-sm">
                <span>Total</span>
                <span className="text-[#1A4D2E]">{formatPHP(grandTotal)}</span>
              </div>
            </div>

            {/* Payment buttons */}
            <div className="grid grid-cols-1 gap-2">
              <Button
                onClick={() => processSale('cash')}
                disabled={saving}
                className="bg-[#1A4D2E] hover:bg-[#15412a] text-white h-12"
                data-testid="pay-cash-btn"
              >
                <Banknote size={18} className="mr-2" />
                {saving ? 'Processing...' : `Cash — ${formatPHP(grandTotal)}`}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
