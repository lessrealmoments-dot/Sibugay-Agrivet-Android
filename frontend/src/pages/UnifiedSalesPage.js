import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Card, CardContent } from '../components/ui/card';
import { ScrollArea } from '../components/ui/scroll-area';
import { Separator } from '../components/ui/separator';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Switch } from '../components/ui/switch';
import SmartProductSearch from '../components/SmartProductSearch';
import {
  Search, Plus, Minus, Trash2, ShoppingCart, CreditCard, X, Wifi, WifiOff,
  RefreshCw, FileText, Lock, Zap, ClipboardList, AlertTriangle, Shield, CheckCircle2
} from 'lucide-react';
import { toast } from 'sonner';
import {
  cacheProducts, getProducts, cacheCustomers, getCustomers,
  cachePriceSchemes, getPriceSchemes, addPendingSale, getPendingSaleCount
} from '../lib/offlineDB';
import { syncPendingSales, startAutoSync, stopAutoSync } from '../lib/syncManager';

const EMPTY_LINE = { product_id: '', product_name: '', description: '', quantity: 1, rate: 0, original_rate: 0, cost_price: 0, discount_type: 'amount', discount_value: 0, is_repack: false };

export default function UnifiedSalesPage() {
  const { currentBranch, user } = useAuth();
  
  // Mode: 'quick' or 'order'
  const [mode, setMode] = useState('quick');
  
  // Products & Data
  const [allProducts, setAllProducts] = useState([]);
  const [filteredProducts, setFilteredProducts] = useState([]);
  const [search, setSearch] = useState('');
  const [customers, setCustomers] = useState([]);
  const [schemes, setSchemes] = useState([]);
  const [terms, setTerms] = useState([]);
  const [prefixes, setPrefixes] = useState({});
  const [users, setUsers] = useState([]);
  
  // Cart/Lines
  const [cart, setCart] = useState([]);
  const [lines, setLines] = useState([{ ...EMPTY_LINE }]);
  
  // Customer
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [custSearch, setCustSearch] = useState('');
  const [custDropdownOpen, setCustDropdownOpen] = useState(false);
  const [newCustomerDialog, setNewCustomerDialog] = useState(false);
  const [newCustForm, setNewCustForm] = useState({ name: '', phone: '', address: '', price_scheme: 'retail' });
  
  // Order header
  const [header, setHeader] = useState({
    terms: 'COD', terms_days: 0, customer_po: '', sales_rep_id: '', sales_rep_name: '',
    prefix: 'SI', order_date: new Date().toISOString().slice(0, 10),
  });
  const [freight, setFreight] = useState(0);
  const [overallDiscount, setOverallDiscount] = useState(0);
  
  // Default price scheme for walk-in customers
  const [defaultScheme, setDefaultScheme] = useState('retail');

  // Price save dialog
  const [priceSaveDialog, setPriceSaveDialog] = useState(false);
  const [pendingPriceChange, setPendingPriceChange] = useState(null);
  
  // Checkout
  const [checkoutDialog, setCheckoutDialog] = useState(false);
  const [paymentType, setPaymentType] = useState('cash'); // cash, partial, credit
  const [amountTendered, setAmountTendered] = useState(0);
  const [partialPayment, setPartialPayment] = useState(0);
  const [saving, setSaving] = useState(false);
  
  // Credit approval
  const [creditApprovalDialog, setCreditApprovalDialog] = useState(false);
  const [managerPin, setManagerPin] = useState('');
  const [creditCheckResult, setCreditCheckResult] = useState(null);
  const [pendingCreditSale, setPendingCreditSale] = useState(null);
  
  // Offline
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [pendingCount, setPendingCount] = useState(0);
  const [dataLoaded, setDataLoaded] = useState(false);
  
  const searchRef = useRef(null);
  const qtyRefs = useRef([]);

  // Online/Offline detection
  useEffect(() => {
    const goOnline = async () => {
      setIsOnline(true);
      toast.success('Back online! Syncing...');
      const result = await syncPendingSales();
      if (result?.synced > 0) toast.success(`${result.synced} sale(s) synced!`);
      const count = await getPendingSaleCount();
      setPendingCount(count);
      await loadData(true);
    };
    const goOffline = () => {
      setIsOnline(false);
      toast('Offline Mode - Sales saved locally', { duration: 4000 });
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

  const loadData = async (forceOnline = false) => {
    const online = forceOnline || navigator.onLine;
    if (online) {
      try {
        const [posRes, custRes, termRes, prefixRes, userRes, schemeRes] = await Promise.all([
          api.get('/sync/pos-data'),
          api.get('/customers', { params: { limit: 500 } }),
          api.get('/settings/terms-options').catch(() => ({ data: [] })),
          api.get('/settings/invoice-prefixes').catch(() => ({ data: {} })),
          api.get('/users').catch(() => ({ data: [] })),
          api.get('/price-schemes').catch(() => ({ data: [] })),
        ]);
        setAllProducts(posRes.data.products);
        setCustomers(custRes.data.customers || posRes.data.customers);
        setSchemes(schemeRes.data || posRes.data.price_schemes);
        setTerms(termRes.data || []);
        setPrefixes(prefixRes.data || {});
        setUsers(userRes.data || []);
        await Promise.all([
          cacheProducts(posRes.data.products),
          cacheCustomers(custRes.data.customers || posRes.data.customers),
          cachePriceSchemes(schemeRes.data || posRes.data.price_schemes),
        ]);
        setDataLoaded(true);
        return;
      } catch (e) { console.warn('API failed, using offline cache'); }
    }
    const [prods, custs, schs] = await Promise.all([getProducts(), getCustomers(), getPriceSchemes()]);
    setAllProducts(prods);
    setCustomers(custs);
    setSchemes(schs);
    setDataLoaded(true);
  };

  useEffect(() => { loadData(); getPendingSaleCount().then(setPendingCount); }, []);

  // Filter products
  useEffect(() => {
    if (!search) { setFilteredProducts(allProducts); return; }
    const q = search.toLowerCase();
    setFilteredProducts(allProducts.filter(p =>
      p.name.toLowerCase().includes(q) || p.sku?.toLowerCase().includes(q) || (p.barcode && p.barcode.includes(q))
    ));
  }, [search, allProducts]);

  const filteredCusts = custSearch 
    ? customers.filter(c => c.name.toLowerCase().includes(custSearch.toLowerCase())).slice(0, 8) 
    : [];

  const getPriceForCustomer = (product) => {
    const scheme = selectedCustomer?.price_scheme || defaultScheme;
    // Return 0 if scheme has no price — do NOT fall back to retail or cost
    return product.prices?.[scheme] ?? 0;
  };

  // Quick mode: Add to cart
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
        original_price: price,
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

  const setCartQty = (productId, qty) => {
    const newQty = Math.max(0, parseFloat(qty) || 0);
    if (newQty === 0) {
      setCart(cart.filter(c => c.product_id !== productId));
    } else {
      setCart(cart.map(c => c.product_id !== productId ? c : { ...c, quantity: newQty, total: newQty * c.price }));
    }
  };

  const updateCartPrice = (productId, newPrice) => {
    const price = parseFloat(newPrice) || 0;
    setCart(cart.map(c => c.product_id !== productId ? c : { ...c, price, total: price * c.quantity }));
  };

  const removeFromCart = (productId) => setCart(cart.filter(c => c.product_id !== productId));
  const clearCart = () => { setCart([]); setLines([{ ...EMPTY_LINE }]); setSelectedCustomer(null); setCustSearch(''); };

  const clearLine = (index) => {
    const newLines = [...lines];
    newLines[index] = { ...EMPTY_LINE };
    setLines(newLines);
  };

  const triggerPriceSaveDialog = (productId, productName, oldPrice, newPrice) => {
    if (!productId || newPrice === oldPrice || newPrice <= 0) return;
    const scheme = selectedCustomer?.price_scheme || defaultScheme;
    const schemeName = schemes.find(s => s.key === scheme)?.name || scheme;
    setPendingPriceChange({ product_id: productId, product_name: productName, old_price: oldPrice, new_price: newPrice, scheme_key: scheme, scheme_name: schemeName });
    setPriceSaveDialog(true);
  };

  const dismissPriceSaveDialog = () => {
    if (pendingPriceChange) {
      // Update originals so dialog doesn't retrigger on next blur
      setLines(lines.map(l => l.product_id === pendingPriceChange.product_id
        ? { ...l, original_rate: pendingPriceChange.new_price } : l
      ));
      setCart(cart.map(c => c.product_id === pendingPriceChange.product_id
        ? { ...c, original_price: pendingPriceChange.new_price } : c
      ));
    }
    setPriceSaveDialog(false);
    setPendingPriceChange(null);
  };

  const savePriceToScheme = async () => {
    if (!pendingPriceChange) return;
    try {
      await api.put(`/products/${pendingPriceChange.product_id}/update-price`, {
        scheme: pendingPriceChange.scheme_key,
        price: pendingPriceChange.new_price,
      });
      toast.success(`${pendingPriceChange.scheme_name} price updated to ₱${pendingPriceChange.new_price.toFixed(2)}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to save price');
    }
    dismissPriceSaveDialog();
  };

  const handleRateBlur = (line) => {
    if (line.product_id && line.rate !== line.original_rate) {
      triggerPriceSaveDialog(line.product_id, line.product_name, line.original_rate, line.rate);
    }
  };

  // Order mode: Handle lines
  const handleProductSelect = (index, product) => {
    const newLines = [...lines];
    const scheme = selectedCustomer?.price_scheme || defaultScheme;
    const rate = product.prices?.[scheme] ?? 0;
    newLines[index] = {
      ...newLines[index], product_id: product.id, product_name: product.name,
      description: product.description || '', rate, original_rate: rate,
      cost_price: product.cost_price || 0, is_repack: product.is_repack || false,
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

  // Customer selection
  const selectCustomer = (custId) => {
    const c = customers.find(x => x.id === custId);
    if (c) {
      setSelectedCustomer(c);
      setCustSearch(c.name);
      setCustDropdownOpen(false);
    }
  };

  const handleCustInput = (val) => {
    setCustSearch(val);
    setCustDropdownOpen(val.length > 0);
    const match = customers.find(c => c.name.toLowerCase() === val.toLowerCase());
    if (match) selectCustomer(match.id);
    else setSelectedCustomer(null);
  };

  // Create new customer
  const openNewCustomerDialog = () => {
    setNewCustForm({ name: custSearch, phone: '', address: '', price_scheme: 'retail' });
    setCustDropdownOpen(false);
    setNewCustomerDialog(true);
  };

  const createNewCustomer = async () => {
    if (!newCustForm.name.trim()) { toast.error('Customer name is required'); return; }
    try {
      const res = await api.post('/customers', {
        ...newCustForm,
        branch_id: currentBranch?.id,
      });
      // Add to local customers list
      setCustomers([...customers, res.data]);
      // Select the new customer
      setSelectedCustomer(res.data);
      setCustSearch(res.data.name);
      setNewCustomerDialog(false);
      toast.success('Customer created!');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to create customer');
    }
  };

  // Calculations
  const items = mode === 'quick' ? cart : lines.filter(l => l.product_id);
  const subtotal = mode === 'quick' 
    ? cart.reduce((s, c) => s + c.total, 0)
    : lines.reduce((s, l) => s + lineTotal(l), 0);
  const grandTotal = subtotal + freight - overallDiscount;
  const balanceDue = paymentType === 'cash' ? 0 : (paymentType === 'partial' ? grandTotal - partialPayment : grandTotal);
  const change = paymentType === 'cash' ? amountTendered - grandTotal : 0;

  // Check credit limit
  const checkCreditLimit = async () => {
    if (!selectedCustomer) return { allowed: true };
    
    const currentBalance = selectedCustomer.balance || 0;
    const creditLimit = selectedCustomer.credit_limit || 0;
    const newTotal = currentBalance + balanceDue;
    
    if (creditLimit > 0 && newTotal > creditLimit) {
      return {
        allowed: false,
        currentBalance,
        creditLimit,
        newTotal,
        exceededBy: newTotal - creditLimit,
      };
    }
    return { allowed: true, currentBalance, creditLimit, newTotal };
  };

  // Open checkout
  const openCheckout = () => {
    if (items.length === 0) { toast.error('Add items first'); return; }
    if (!currentBranch) { toast.error('Select a branch'); return; }

    // Check for zero-price items (no price set for selected scheme)
    const zeroPriceItem = mode === 'quick'
      ? cart.find(c => c.price <= 0)
      : lines.find(l => l.product_id && l.rate <= 0);
    if (zeroPriceItem) {
      toast.error(`"${zeroPriceItem.product_name}" has no price — edit the price directly on the receipt before checkout`);
      return;
    }

    // Check for below-capital items
    const belowCostItem = mode === 'quick'
      ? cart.find(c => c.cost_price > 0 && c.price < c.cost_price)
      : lines.find(l => l.product_id && l.cost_price > 0 && l.rate < l.cost_price);
    if (belowCostItem) {
      const p = belowCostItem.price ?? belowCostItem.rate;
      toast.error(`Cannot sell "${belowCostItem.product_name}" at ₱${p.toFixed(2)} — below capital ₱${belowCostItem.cost_price.toFixed(2)}`);
      return;
    }

    setPaymentType('cash');
    setAmountTendered(grandTotal);
    setPartialPayment(0);
    setCheckoutDialog(true);
  };

  // Handle credit sale with approval
  const handleCreditSale = async () => {
    // Check credit limit first
    const creditCheck = await checkCreditLimit();
    setCreditCheckResult(creditCheck);
    
    if (!creditCheck.allowed || paymentType !== 'cash') {
      // Requires manager approval
      setPendingCreditSale({ paymentType, partialPayment, amountTendered });
      setCheckoutDialog(false);
      setCreditApprovalDialog(true);
      return;
    }
    
    // Direct cash sale - proceed
    await processSale();
  };

  // Verify manager PIN
  const verifyManagerPin = async () => {
    if (!managerPin) { toast.error('Enter manager PIN'); return; }
    
    try {
      const res = await api.post('/auth/verify-manager-pin', { pin: managerPin });
      if (res.data.valid) {
        toast.success(`Approved by ${res.data.manager_name}`);
        setCreditApprovalDialog(false);
        setManagerPin('');
        await processSale(res.data.manager_name);
      } else {
        toast.error('Invalid PIN');
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Verification failed');
    }
  };

  // Process the sale
  const processSale = async (approvedBy = null) => {
    setSaving(true);
    
    const actualPaymentType = pendingCreditSale?.paymentType || paymentType;
    const actualPartial = pendingCreditSale?.partialPayment || partialPayment;
    const actualTendered = pendingCreditSale?.amountTendered || amountTendered;
    
    const saleId = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    const today = new Date().toISOString().slice(0, 10);
    
    // Calculate amounts
    const amountPaid = actualPaymentType === 'cash' ? grandTotal : (actualPaymentType === 'partial' ? actualPartial : 0);
    const balance = grandTotal - amountPaid;
    
    // Prepare items
    const saleItems = mode === 'quick' 
      ? cart.map(c => ({
          product_id: c.product_id, product_name: c.product_name, sku: c.sku,
          quantity: c.quantity, rate: c.price, price: c.price, total: c.total,
          discount_type: 'amount', discount_value: 0, discount_amount: 0,
          is_repack: c.is_repack || false,
        }))
      : lines.filter(l => l.product_id).map(l => ({
          product_id: l.product_id, product_name: l.product_name,
          description: l.description, quantity: l.quantity, rate: l.rate,
          discount_type: l.discount_type, discount_value: l.discount_value,
          discount_amount: l.discount_type === 'percent' ? l.quantity * l.rate * l.discount_value / 100 : l.discount_value,
          total: lineTotal(l), is_repack: l.is_repack || false,
        }));

    const saleData = {
      id: saleId,
      branch_id: currentBranch.id,
      customer_id: selectedCustomer?.id || null,
      customer_name: selectedCustomer?.name || custSearch || 'Walk-in',
      customer_contact: selectedCustomer?.phone || '',
      customer_phone: selectedCustomer?.phone || '',
      customer_address: selectedCustomer?.address || '',
      items: saleItems,
      subtotal,
      freight,
      overall_discount: overallDiscount,
      grand_total: grandTotal,
      amount_paid: amountPaid,
      balance,
      terms: header.terms,
      terms_days: header.terms_days,
      customer_po: header.customer_po,
      sales_rep_id: header.sales_rep_id,
      sales_rep_name: header.sales_rep_name,
      prefix: header.prefix,
      order_date: header.order_date,
      invoice_date: today,
      payment_method: actualPaymentType === 'cash' ? 'Cash' : 'Credit',
      payment_type: actualPaymentType,
      fund_source: 'cashier',
      sale_type: 'walk_in',
      mode: mode,
      approved_by: approvedBy,
      interest_rate: selectedCustomer?.interest_rate || 0,
      cashier_id: user?.id,
      cashier_name: user?.full_name || user?.username,
      status: balance > 0 ? 'open' : 'paid',
      created_at: new Date().toISOString(),
    };

    if (isOnline) {
      try {
        const res = await api.post('/unified-sale', saleData);
        toast.success(balance > 0 
          ? `Invoice ${res.data.invoice_number} created! Balance: ${formatPHP(balance)}`
          : `Sale ${res.data.invoice_number || res.data.sale_number} completed!`
        );
        clearCart();
        setCheckoutDialog(false);
        setPendingCreditSale(null);
      } catch (e) {
        // Save offline if API fails
        await addPendingSale(saleData);
        const count = await getPendingSaleCount();
        setPendingCount(count);
        toast.success('Sale saved offline (will sync later)');
        clearCart();
        setCheckoutDialog(false);
        setPendingCreditSale(null);
      }
    } else {
      await addPendingSale(saleData);
      const count = await getPendingSaleCount();
      setPendingCount(count);
      toast.success(`Sale saved offline!`);
      clearCart();
      setCheckoutDialog(false);
      setPendingCreditSale(null);
    }
    
    setSaving(false);
  };

  const selectTerm = (label) => {
    const t = terms.find(x => x.label === label);
    setHeader(h => ({ ...h, terms: label, terms_days: t?.days || 0 }));
  };

  return (
    <div className="h-[calc(100vh-80px)] flex flex-col animate-fadeIn" data-testid="unified-sales-page">
      {/* Header */}
      <div className="flex items-center justify-between px-1 py-3">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>Sales</h1>
          
          {/* Mode Toggle */}
          <div className="flex items-center gap-2 bg-slate-100 rounded-lg p-1">
            <button
              onClick={() => setMode('quick')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                mode === 'quick' ? 'bg-white shadow-sm text-[#1A4D2E]' : 'text-slate-500 hover:text-slate-700'
              }`}
              data-testid="mode-quick"
            >
              <Zap size={14} /> Quick
            </button>
            <button
              onClick={() => setMode('order')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                mode === 'order' ? 'bg-white shadow-sm text-[#1A4D2E]' : 'text-slate-500 hover:text-slate-700'
              }`}
              data-testid="mode-order"
            >
              <ClipboardList size={14} /> Order
            </button>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Offline indicator */}
          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
            isOnline ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'
          }`}>
            {isOnline ? <Wifi size={12} /> : <WifiOff size={12} />}
            {isOnline ? 'Online' : 'Offline'}
            {pendingCount > 0 && <Badge variant="secondary" className="ml-1 text-[10px] h-4">{pendingCount}</Badge>}
          </div>
          
          <Button variant="outline" size="sm" onClick={() => loadData(true)} disabled={!isOnline}>
            <RefreshCw size={14} className="mr-1" /> Sync
          </Button>
        </div>
      </div>

      {/* Customer Selection */}
      <div className="px-1 pb-3">
        <Card className="border-slate-200">
          <CardContent className="p-3">
            <div className="flex flex-wrap items-end gap-4">
              <div className="relative flex-1 min-w-[200px]">
                <Label className="text-xs text-slate-500">Customer</Label>
                <Input
                  data-testid="customer-search"
                  className="h-9"
                  value={custSearch}
                  placeholder="Search customer or type name..."
                  onChange={e => handleCustInput(e.target.value)}
                  onFocus={() => { if (custSearch) setCustDropdownOpen(true); }}
                  onBlur={() => setTimeout(() => setCustDropdownOpen(false), 200)}
                />
                {custDropdownOpen && (
                  <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                    {filteredCusts.map(c => (
                      <button key={c.id} className="w-full text-left px-3 py-2 text-sm hover:bg-slate-50 border-b border-slate-50"
                        onMouseDown={() => selectCustomer(c.id)}>
                        <span className="font-medium">{c.name}</span>
                        <span className="text-xs text-slate-400 ml-2">{c.phone || ''}</span>
                        {c.balance > 0 && <Badge variant="outline" className="ml-2 text-[10px] text-red-600">Bal: {formatPHP(c.balance)}</Badge>}
                      </button>
                    ))}
                    {custSearch && !customers.find(c => c.name.toLowerCase() === custSearch.toLowerCase()) && (
                      <button
                        data-testid="create-customer-btn"
                        className="w-full text-left px-3 py-2.5 text-sm bg-[#1A4D2E]/5 hover:bg-[#1A4D2E]/10 text-[#1A4D2E] font-medium border-t border-slate-100"
                        onMouseDown={openNewCustomerDialog}
                      >
                        <Plus size={14} className="inline mr-2" />
                        Create "{custSearch}" as new customer
                      </button>
                    )}
                  </div>
                )}
              </div>
              
              {selectedCustomer && (
                <div className="flex items-center gap-4 text-sm">
                  <div>
                    <span className="text-xs text-slate-500">Scheme:</span>
                    <Badge variant="outline" className="ml-1 capitalize">{selectedCustomer.price_scheme}</Badge>
                  </div>
                  <div>
                    <span className="text-xs text-slate-500">Balance:</span>
                    <span className={`ml-1 font-medium ${selectedCustomer.balance > 0 ? 'text-red-600' : ''}`}>
                      {formatPHP(selectedCustomer.balance || 0)}
                    </span>
                  </div>
                  <div>
                    <span className="text-xs text-slate-500">Limit:</span>
                    <span className="ml-1 font-medium">{formatPHP(selectedCustomer.credit_limit || 0)}</span>
                  </div>
                </div>
              )}

              {/* Price scheme selector (for walk-in when no customer selected) */}
              {!selectedCustomer && (
                <div className="w-32">
                  <Label className="text-xs text-slate-500">Price Scheme</Label>
                  <Select value={defaultScheme} onValueChange={setDefaultScheme}>
                    <SelectTrigger className="h-9" data-testid="price-scheme-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {schemes.map(s => (
                        <SelectItem key={s.key} value={s.key}>{s.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {mode === 'order' && (
                <>
                  <div className="w-32">
                    <Label className="text-xs text-slate-500">Terms</Label>
                    <Select value={header.terms} onValueChange={selectTerm}>
                      <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {terms.map(t => <SelectItem key={t.label} value={t.label}>{t.label}</SelectItem>)}
                        <SelectItem value="Custom">Custom</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="w-28">
                    <Label className="text-xs text-slate-500">Customer PO</Label>
                    <Input className="h-9" value={header.customer_po} onChange={e => setHeader(h => ({ ...h, customer_po: e.target.value }))} />
                  </div>
                </>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex gap-4 px-1 overflow-hidden">
        {mode === 'quick' ? (
          // QUICK MODE: Product grid + Cart
          <>
            {/* Product Grid */}
            <div className="flex-1 flex flex-col min-w-0">
              <div className="relative mb-3">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  ref={searchRef}
                  data-testid="product-search"
                  className="pl-9 h-10"
                  placeholder="Search products by name, SKU, or barcode..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                />
              </div>
              <ScrollArea className="flex-1">
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                  {filteredProducts.slice(0, 50).map(p => (
                    <button
                      key={p.id}
                      data-testid={`product-${p.id}`}
                      onClick={() => addToCart(p)}
                      className="text-left p-3 rounded-lg border border-slate-200 hover:border-[#1A4D2E]/50 hover:bg-slate-50 transition-all"
                    >
                      <p className="font-medium text-sm truncate">{p.name}</p>
                      <p className="text-xs text-slate-400 truncate">{p.sku}</p>
                      <div className="flex items-center justify-between mt-2">
                        <span className="text-sm font-semibold text-[#1A4D2E]">{formatPHP(getPriceForCustomer(p))}</span>
                        <Badge variant="outline" className="text-[10px]">{p.available ?? '?'}</Badge>
                      </div>
                    </button>
                  ))}
                </div>
              </ScrollArea>
            </div>

            {/* Cart */}
            <Card className="w-80 flex flex-col border-slate-200">
              <CardContent className="flex-1 flex flex-col p-0">
                <div className="p-3 border-b border-slate-100 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <ShoppingCart size={16} className="text-slate-400" />
                    <span className="font-semibold text-sm">Cart</span>
                    <Badge variant="secondary" className="text-[10px]">{cart.length}</Badge>
                  </div>
                  {cart.length > 0 && (
                    <Button variant="ghost" size="sm" onClick={clearCart} className="text-xs text-slate-400">Clear</Button>
                  )}
                </div>
                
                <ScrollArea className="flex-1 p-3">
                  {cart.length === 0 ? (
                    <p className="text-center text-slate-400 text-sm py-8">Cart empty</p>
                  ) : (
                    <div className="space-y-2">
                      {cart.map(item => (
                        <div key={item.product_id} className="flex items-center gap-2 p-2 rounded-lg bg-slate-50">
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate">{item.product_name}</p>
                            <p className="text-xs text-slate-500">{formatPHP(item.price)} × {item.quantity}</p>
                          </div>
                          <div className="flex items-center gap-1">
                            <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => updateQty(item.product_id, -1)}>
                              <Minus size={12} />
                            </Button>
                            <span className="text-sm w-6 text-center">{item.quantity}</span>
                            <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => updateQty(item.product_id, 1)}>
                              <Plus size={12} />
                            </Button>
                            <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-red-500" onClick={() => removeFromCart(item.product_id)}>
                              <Trash2 size={12} />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </ScrollArea>

                <div className="p-3 border-t border-slate-100 space-y-2">
                  <div className="flex justify-between text-sm"><span>Subtotal</span><span>{formatPHP(subtotal)}</span></div>
                  <Separator />
                  <div className="flex justify-between font-bold"><span>Total</span><span className="text-lg">{formatPHP(grandTotal)}</span></div>
                  <Button 
                    data-testid="checkout-btn"
                    className="w-full bg-[#1A4D2E] hover:bg-[#14532d] text-white"
                    onClick={openCheckout}
                    disabled={cart.length === 0}
                  >
                    <CreditCard size={16} className="mr-2" /> Checkout
                  </Button>
                </div>
              </CardContent>
            </Card>
          </>
        ) : (
          // ORDER MODE: Excel-style line items
          <div className="flex-1 flex flex-col min-w-0">
            <Card className="flex-1 flex flex-col border-slate-200 overflow-hidden">
              <CardContent className="flex-1 flex flex-col p-0 overflow-hidden">
                <div className="overflow-auto flex-1">
                  <table className="w-full text-sm" data-testid="order-lines-table">
                    <thead className="sticky top-0 bg-slate-50 z-10">
                      <tr className="border-b">
                        <th className="text-left px-3 py-2 text-xs uppercase text-slate-500 font-medium w-8">#</th>
                        <th className="text-left px-3 py-2 text-xs uppercase text-slate-500 font-medium min-w-[280px]">Product</th>
                        <th className="text-right px-3 py-2 text-xs uppercase text-slate-500 font-medium w-20">Qty</th>
                        <th className="text-right px-3 py-2 text-xs uppercase text-slate-500 font-medium w-28">Rate</th>
                        <th className="text-right px-3 py-2 text-xs uppercase text-slate-500 font-medium w-28">Discount</th>
                        <th className="text-right px-3 py-2 text-xs uppercase text-slate-500 font-medium w-28">Amount</th>
                        <th className="w-10"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {lines.map((line, i) => (
                        <tr key={i} className="border-b border-slate-100 hover:bg-slate-50/50">
                          <td className="px-3 py-1 text-xs text-slate-400">{i + 1}</td>
                          <td className="px-3 py-1">
                            <SmartProductSearch
                              branchId={currentBranch?.id}
                              value={line.product_name}
                              onSelect={(p) => handleProductSelect(i, p)}
                              onCreateNew={() => {}}
                              placeholder="Search product..."
                            />
                          </td>
                          <td className="px-3 py-1">
                            <Input
                              ref={el => qtyRefs.current[i] = el}
                              type="number"
                              className="h-8 text-right w-16"
                              value={line.quantity}
                              onChange={e => updateLine(i, 'quantity', parseFloat(e.target.value) || 0)}
                            />
                          </td>
                          <td className="px-3 py-1">
                            <Input
                              type="number"
                              className="h-8 text-right w-24"
                              value={line.rate}
                              onChange={e => updateLine(i, 'rate', parseFloat(e.target.value) || 0)}
                            />
                          </td>
                          <td className="px-3 py-1">
                            <Input
                              type="number"
                              className="h-8 text-right w-20"
                              value={line.discount_value}
                              onChange={e => updateLine(i, 'discount_value', parseFloat(e.target.value) || 0)}
                            />
                          </td>
                          <td className="px-3 py-1 text-right font-medium">{formatPHP(lineTotal(line))}</td>
                          <td className="px-1">
                            {lines.length > 1 && line.product_id && (
                              <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-red-500" onClick={() => removeLine(i)}>
                                <Trash2 size={12} />
                              </Button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Order totals */}
                <div className="border-t border-slate-100 p-4 bg-slate-50">
                  <div className="flex justify-end">
                    <div className="w-72 space-y-2">
                      <div className="flex justify-between text-sm"><span>Subtotal</span><span>{formatPHP(subtotal)}</span></div>
                      <div className="flex items-center justify-between text-sm">
                        <span>Freight</span>
                        <Input type="number" className="h-7 w-24 text-right" value={freight} onChange={e => setFreight(parseFloat(e.target.value) || 0)} />
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <span>Discount</span>
                        <Input type="number" className="h-7 w-24 text-right" value={overallDiscount} onChange={e => setOverallDiscount(parseFloat(e.target.value) || 0)} />
                      </div>
                      <Separator />
                      <div className="flex justify-between font-bold text-lg"><span>Total</span><span>{formatPHP(grandTotal)}</span></div>
                      <Button 
                        data-testid="checkout-btn"
                        className="w-full bg-[#1A4D2E] hover:bg-[#14532d] text-white"
                        onClick={openCheckout}
                        disabled={items.length === 0}
                      >
                        <CreditCard size={16} className="mr-2" /> Proceed to Payment
                      </Button>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>

      {/* Checkout Dialog */}
      <Dialog open={checkoutDialog} onOpenChange={setCheckoutDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Manrope' }}>Payment</DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4">
            {/* Customer display */}
            <div className="bg-slate-50 rounded-lg p-3">
              <p className="text-sm text-slate-500">Customer</p>
              <p className="font-medium">{selectedCustomer?.name || custSearch || 'Walk-in'}</p>
              {selectedCustomer && (
                <div className="flex gap-4 mt-1 text-xs text-slate-500">
                  <span>Balance: <span className={selectedCustomer.balance > 0 ? 'text-red-600 font-medium' : ''}>{formatPHP(selectedCustomer.balance || 0)}</span></span>
                  <span>Limit: {formatPHP(selectedCustomer.credit_limit || 0)}</span>
                </div>
              )}
            </div>

            {/* Total */}
            <div className="text-center py-4">
              <p className="text-sm text-slate-500">Total Amount</p>
              <p className="text-3xl font-bold text-[#1A4D2E]" style={{ fontFamily: 'Manrope' }}>{formatPHP(grandTotal)}</p>
            </div>

            {/* Payment Type */}
            <div className="space-y-2">
              <Label className="text-sm">Payment Type</Label>
              <Tabs value={paymentType} onValueChange={setPaymentType}>
                <TabsList className="grid grid-cols-3 w-full">
                  <TabsTrigger value="cash" data-testid="pay-cash">Cash</TabsTrigger>
                  <TabsTrigger value="partial" data-testid="pay-partial">Partial</TabsTrigger>
                  <TabsTrigger value="credit" data-testid="pay-credit" disabled={!selectedCustomer}>Credit</TabsTrigger>
                </TabsList>
              </Tabs>
              {!selectedCustomer && paymentType !== 'cash' && (
                <p className="text-xs text-amber-600 flex items-center gap-1">
                  <AlertTriangle size={12} /> Select a customer for credit/partial payment
                </p>
              )}
            </div>

            {/* Payment inputs */}
            {paymentType === 'cash' && (
              <div>
                <Label>Amount Tendered</Label>
                <Input
                  data-testid="amount-tendered"
                  type="number"
                  value={amountTendered}
                  onChange={e => setAmountTendered(parseFloat(e.target.value) || 0)}
                  className="text-lg h-12"
                />
                {change > 0 && (
                  <p className="text-right mt-2 text-lg font-bold text-emerald-600">Change: {formatPHP(change)}</p>
                )}
              </div>
            )}

            {paymentType === 'partial' && (
              <div>
                <Label>Amount Paid Now</Label>
                <Input
                  data-testid="partial-amount"
                  type="number"
                  value={partialPayment}
                  onChange={e => setPartialPayment(Math.min(parseFloat(e.target.value) || 0, grandTotal))}
                  className="text-lg h-12"
                />
                <div className="flex justify-between mt-2 p-2 bg-amber-50 rounded-lg">
                  <span className="text-sm text-amber-700">Balance (to AR)</span>
                  <span className="font-bold text-amber-700">{formatPHP(grandTotal - partialPayment)}</span>
                </div>
              </div>
            )}

            {paymentType === 'credit' && (
              <div className="p-3 bg-red-50 rounded-lg">
                <p className="text-sm text-red-700 font-medium">Full Credit Sale</p>
                <p className="text-xs text-red-600 mt-1">
                  {formatPHP(grandTotal)} will be added to {selectedCustomer?.name}'s receivables
                </p>
                <p className="text-xs text-slate-500 mt-2 flex items-center gap-1">
                  <Shield size={12} /> Requires manager approval
                </p>
              </div>
            )}

            {/* Action buttons */}
            <div className="flex gap-2 pt-2">
              <Button variant="outline" className="flex-1" onClick={() => setCheckoutDialog(false)}>Cancel</Button>
              <Button 
                data-testid="confirm-payment"
                className="flex-1 bg-[#1A4D2E] hover:bg-[#14532d] text-white"
                onClick={handleCreditSale}
                disabled={saving || (paymentType === 'cash' && amountTendered < grandTotal)}
              >
                {saving ? 'Processing...' : (paymentType === 'cash' ? 'Complete Sale' : 'Confirm & Create Invoice')}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Credit Approval Dialog */}
      <Dialog open={creditApprovalDialog} onOpenChange={setCreditApprovalDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
              <Shield className="text-amber-500" /> Manager Approval Required
            </DialogTitle>
            <DialogDescription>
              Credit sales require manager authorization
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4">
            {/* Credit check result */}
            {creditCheckResult && !creditCheckResult.allowed && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-sm font-medium text-red-700 flex items-center gap-1">
                  <AlertTriangle size={14} /> Credit Limit Exceeded
                </p>
                <div className="mt-2 space-y-1 text-xs text-red-600">
                  <div className="flex justify-between"><span>Current Balance:</span><span>{formatPHP(creditCheckResult.currentBalance)}</span></div>
                  <div className="flex justify-between"><span>This Sale:</span><span>{formatPHP(balanceDue)}</span></div>
                  <div className="flex justify-between font-medium"><span>New Total:</span><span>{formatPHP(creditCheckResult.newTotal)}</span></div>
                  <div className="flex justify-between"><span>Credit Limit:</span><span>{formatPHP(creditCheckResult.creditLimit)}</span></div>
                  <Separator className="my-1" />
                  <div className="flex justify-between font-bold text-red-700">
                    <span>Exceeded By:</span><span>{formatPHP(creditCheckResult.exceededBy)}</span>
                  </div>
                </div>
              </div>
            )}

            {creditCheckResult?.allowed && (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
                <p className="text-sm text-amber-700">
                  This credit sale of <strong>{formatPHP(balanceDue)}</strong> requires manager approval.
                </p>
              </div>
            )}

            {/* Manager PIN */}
            <div>
              <Label>Manager PIN</Label>
              <Input
                data-testid="manager-pin"
                type="password"
                value={managerPin}
                onChange={e => setManagerPin(e.target.value)}
                placeholder="Enter 4-digit PIN"
                className="text-center text-2xl tracking-widest h-14"
                maxLength={6}
              />
              <p className="text-xs text-slate-500 mt-1">Ask a manager or admin to enter their PIN</p>
            </div>

            <div className="flex gap-2">
              <Button variant="outline" className="flex-1" onClick={() => { setCreditApprovalDialog(false); setManagerPin(''); }}>
                Cancel
              </Button>
              <Button 
                data-testid="verify-pin"
                className="flex-1 bg-amber-500 hover:bg-amber-600 text-white"
                onClick={verifyManagerPin}
                disabled={!managerPin || saving}
              >
                <CheckCircle2 size={16} className="mr-2" /> Approve Sale
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* New Customer Dialog */}
      <Dialog open={newCustomerDialog} onOpenChange={setNewCustomerDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Manrope' }}>Create New Customer</DialogTitle>
            <DialogDescription>Add a new customer to use in this sale</DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4">
            <div>
              <Label>Customer Name *</Label>
              <Input
                data-testid="new-cust-name"
                value={newCustForm.name}
                onChange={e => setNewCustForm({ ...newCustForm, name: e.target.value })}
                placeholder="Enter customer name"
                className="h-10"
                autoFocus
              />
            </div>
            <div>
              <Label>Phone Number</Label>
              <Input
                data-testid="new-cust-phone"
                value={newCustForm.phone}
                onChange={e => setNewCustForm({ ...newCustForm, phone: e.target.value })}
                placeholder="09xx xxx xxxx"
              />
            </div>
            <div>
              <Label>Address</Label>
              <Input
                value={newCustForm.address}
                onChange={e => setNewCustForm({ ...newCustForm, address: e.target.value })}
                placeholder="Customer address"
              />
            </div>
            <div>
              <Label>Price Scheme</Label>
              <Select value={newCustForm.price_scheme} onValueChange={v => setNewCustForm({ ...newCustForm, price_scheme: v })}>
                <SelectTrigger className="h-10">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {schemes.map(s => (
                    <SelectItem key={s.key} value={s.key}>{s.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            <div className="flex gap-2 pt-2">
              <Button variant="outline" className="flex-1" onClick={() => setNewCustomerDialog(false)}>
                Cancel
              </Button>
              <Button 
                data-testid="save-new-customer"
                className="flex-1 bg-[#1A4D2E] hover:bg-[#14532d] text-white"
                onClick={createNewCustomer}
              >
                <Plus size={16} className="mr-2" /> Create Customer
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
