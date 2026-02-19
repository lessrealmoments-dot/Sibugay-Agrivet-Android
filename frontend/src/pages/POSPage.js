import { useState, useEffect, useRef } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Card } from '../components/ui/card';
import { ScrollArea } from '../components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Search, Plus, Minus, Trash2, ShoppingCart, CreditCard, X, Wifi, WifiOff, RefreshCw } from 'lucide-react';
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
        price, quantity: 1, total: price, unit: product.unit, is_repack: product.is_repack
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

  const removeFromCart = (productId) => setCart(cart.filter(c => c.product_id !== productId));
  const clearCart = () => { setCart([]); setSelectedCustomer(null); setDiscount(0); };

  const subtotal = cart.reduce((sum, c) => sum + c.total, 0);
  const grandTotal = subtotal - discount;
  const change = amountTendered - grandTotal;

  const handleCheckout = async () => {
    if (!currentBranch) { toast.error('Select a branch first'); return; }
    if (!cart.length) { toast.error('Cart is empty'); return; }
    try {
      const saleData = {
        branch_id: currentBranch.id,
        customer_id: selectedCustomer?.id,
        customer_name: selectedCustomer?.name || 'Walk-in',
        items: cart.map(c => ({ product_id: c.product_id, quantity: c.quantity, price: c.price })),
        discount,
        payment_method: paymentMethod,
        payment_details: paymentMethod === 'Cash' ? { tendered: amountTendered, change: Math.max(0, change) } : {},
      };
      const res = await api.post('/sales', saleData);
      toast.success(`Sale ${res.data.sale_number} completed!`);
      clearCart();
      setCheckoutDialog(false);
    } catch (e) { toast.error(e.response?.data?.detail || 'Sale failed'); }
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
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {products.map(p => (
            <button
              key={p.id}
              data-testid={`pos-product-${p.id}`}
              onClick={() => addToCart(p)}
              className="text-left p-3 rounded-lg border border-slate-200 bg-white hover:border-[#1A4D2E]/40 hover:shadow-sm transition-all duration-200 active:scale-[0.98]"
            >
              <p className="font-medium text-sm truncate">{p.name}</p>
              <p className="text-[11px] text-slate-400 font-mono mt-0.5">{p.sku}</p>
              <div className="flex items-center justify-between mt-2">
                <span className="text-base font-bold text-[#1A4D2E]">{getPriceForCustomer(p).toFixed(2)}</span>
                {p.is_repack && <Badge variant="outline" className="text-[9px] border-amber-300 text-amber-600">R</Badge>}
              </div>
              <p className="text-[10px] text-slate-400 mt-1">per {p.unit}</p>
            </button>
          ))}
          {!products.length && (
            <div className="col-span-full text-center py-12 text-slate-400 text-sm">No products found</div>
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
              <div key={item.product_id} className="flex items-start gap-3 p-3 rounded-lg bg-slate-50 animate-slideIn">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{item.product_name}</p>
                  <p className="text-[11px] text-slate-400">{item.price.toFixed(2)} x {item.quantity}</p>
                </div>
                <div className="flex items-center gap-1">
                  <Button variant="outline" size="sm" className="h-7 w-7 p-0" data-testid={`cart-minus-${item.product_id}`} onClick={() => updateQty(item.product_id, -1)}>
                    <Minus size={12} />
                  </Button>
                  <span className="w-8 text-center text-sm font-bold">{item.quantity}</span>
                  <Button variant="outline" size="sm" className="h-7 w-7 p-0" data-testid={`cart-plus-${item.product_id}`} onClick={() => updateQty(item.product_id, 1)}>
                    <Plus size={12} />
                  </Button>
                </div>
                <div className="text-right w-20">
                  <p className="text-sm font-bold">{item.total.toFixed(2)}</p>
                  <button onClick={() => removeFromCart(item.product_id)} className="text-red-400 hover:text-red-600">
                    <Trash2 size={12} />
                  </button>
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
            <span className="font-semibold">{subtotal.toFixed(2)}</span>
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
            <span className="text-2xl font-bold text-[#1A4D2E]" style={{ fontFamily: 'Manrope' }}>{grandTotal.toFixed(2)}</span>
          </div>
          <Button
            data-testid="pos-checkout-btn"
            disabled={!cart.length}
            onClick={() => { setAmountTendered(grandTotal); setCheckoutDialog(true); }}
            className="w-full h-12 text-base bg-[#1A4D2E] hover:bg-[#14532d] text-white"
          >
            <CreditCard size={18} className="mr-2" /> Checkout
          </Button>
        </div>
      </div>

      {/* Checkout Dialog */}
      <Dialog open={checkoutDialog} onOpenChange={setCheckoutDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Complete Sale</DialogTitle></DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="p-4 bg-emerald-50 rounded-lg text-center">
              <p className="text-sm text-emerald-600">Total Amount</p>
              <p className="text-3xl font-bold text-emerald-800" style={{ fontFamily: 'Manrope' }}>{grandTotal.toFixed(2)}</p>
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
    </div>
  );
}
