import { useState, useEffect, useCallback, useRef } from 'react';
import { api, useAuth } from '../contexts/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Package, Plus, Pencil, Trash2, Search, Link2, ChevronRight, Eye, Upload, Zap, X, CheckCircle, XCircle } from 'lucide-react';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import { formatPHP } from '../lib/utils';

export default function ProductsPage() {
  const navigate = useNavigate();
  const { currentBranch } = useAuth();
  const [products, setProducts] = useState([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [page, setPage] = useState(0);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [repackDialog, setRepackDialog] = useState(false);
  const [editing, setEditing] = useState(null);
  const [selectedParent, setSelectedParent] = useState(null);
  const [schemes, setSchemes] = useState([]);
  const [categories, setCategories] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [repackParentIds, setRepackParentIds] = useState(new Set()); // parents that have at least one repack
  const [repackConfirmParent, setRepackConfirmParent] = useState(null); // pending confirm dialog
  const LIMIT = 20;

  const [form, setForm] = useState({ sku: '', name: '', category: 'General', unit: 'Box', cost_price: 0, prices: {}, barcode: '', description: '', product_type: 'stockable', unit_of_measurement: 'Box' });
  const [repackForm, setRepackForm] = useState({ name: '', unit: 'Sachet', units_per_parent: 1, cost_price: 0, prices: {} });

  // ── Batch Quick Repack ──────────────────────────────────────────────────────
  const [qrOpen, setQrOpen] = useState(false);
  const [qrRows, setQrRows] = useState([]);
  const [qrGenerating, setQrGenerating] = useState(false);
  const [qrResults, setQrResults] = useState(null); // null = not yet generated
  const searchTimers = useRef({});
  const pendingFocusRowId = useRef(null);

  // After a new row is added via Tab, focus its parent search input
  useEffect(() => {
    if (pendingFocusRowId.current) {
      const input = document.querySelector(`[data-testid="qr-parent-${pendingFocusRowId.current}"]`);
      if (input) { input.focus(); pendingFocusRowId.current = null; }
    }
  }, [qrRows]);

  const computeCapital = (parent, unitsPerParent, addOnCost) => {
    if (!parent) return 0;
    return Math.round((parent.cost_price / (unitsPerParent || 1) + (parseFloat(addOnCost) || 0)) * 100) / 100;
  };

  const newRow = () => ({
    id: Math.random().toString(36).slice(2),
    parentSearch: '', parentMatches: [], parent: null,
    repackName: '', unit: 'Pack',
    unitsPerParent: 1, addOnCost: 0,
    capital: 0,
    retailPrice: '',
    retailError: null, rowError: null,
  });

  const updateRow = (id, updates) =>
    setQrRows(rows => rows.map(r => r.id === id ? { ...r, ...updates } : r));

  const removeRow = (id) =>
    setQrRows(rows => rows.filter(r => r.id !== id));

  const searchParent = (rowId, query) => {
    updateRow(rowId, { parentSearch: query, parent: null, capital: 0, rowError: null });
    if (searchTimers.current[rowId]) clearTimeout(searchTimers.current[rowId]);
    if (!query || query.length < 1) { updateRow(rowId, { parentMatches: [] }); return; }
    searchTimers.current[rowId] = setTimeout(async () => {
      try {
        const res = await api.get('/products', { params: { search: query, is_repack: false, limit: 8 } });
        updateRow(rowId, { parentMatches: res.data.products || [] });
      } catch {}
    }, 180);
  };

  const selectParent = (rowId, p) => {
    const capital = computeCapital(p, 1, 0);
    updateRow(rowId, {
      parent: p, parentSearch: p.name, parentMatches: [],
      repackName: `R ${p.name}`,
      unitsPerParent: 1, addOnCost: 0, capital,
      retailPrice: '', retailError: null, rowError: null,
    });
  };

  // onBlur validation for retail price — check against capital
  const handleRetailBlur = (rowId, value) => {
    const row = qrRows.find(r => r.id === rowId);
    if (!row || !value) return;
    const retail = parseFloat(value);
    if (isNaN(retail) || retail <= 0) return;
    if (row.capital > 0 && retail <= row.capital) {
      updateRow(rowId, { retailError: `Below capital ₱${row.capital.toFixed(2)}` });
    } else {
      updateRow(rowId, { retailError: null });
    }
  };

  const openQrModal = () => {
    setQrRows([newRow()]);
    setQrResults(null);
    setQrOpen(true);
  };

  const handleBatchGenerate = async () => {
    // Validate all rows — mark errors, block if any invalid
    let hasErrors = false;
    const validated = qrRows.map(row => {
      let rowError = null;
      let retailError = row.retailError;
      if (!row.parent) { rowError = 'Select a parent product'; hasErrors = true; }
      else if (!row.repackName.trim()) { rowError = 'Repack name required'; hasErrors = true; }
      else if (!row.retailPrice || parseFloat(row.retailPrice) <= 0) { rowError = 'Retail price required'; hasErrors = true; }
      else if (row.capital > 0 && parseFloat(row.retailPrice) <= row.capital) {
        retailError = `Below capital ₱${row.capital.toFixed(2)}`; rowError = 'Fix retail price'; hasErrors = true;
      }
      return { ...row, rowError, retailError };
    });

    if (hasErrors) {
      setQrRows(validated);
      toast.error('Fix the highlighted rows before generating');
      return;
    }

    setQrGenerating(true);
    const results = [];
    for (const row of qrRows) {
      try {
        const allPrices = {};
        schemes.forEach(s => { allPrices[s.key] = parseFloat(row.retailPrice); });
        await api.post(`/products/${row.parent.id}/generate-repack`, {
          name: row.repackName, unit: row.unit,
          units_per_parent: row.unitsPerParent,
          add_on_cost: row.addOnCost || 0,
          cost_price: row.capital,
          prices: allPrices,
        });
        results.push({ name: row.repackName, status: 'ok' });
      } catch (e) {
        results.push({ name: row.repackName, status: 'error', error: e.response?.data?.detail || 'Error' });
      }
    }
    setQrGenerating(false);
    setQrResults(results);
    fetchProducts();
  };

  const fetchProducts = useCallback(async () => {
    try {
      const params = { skip: page * LIMIT, limit: LIMIT };
      if (search) params.search = search;
      if (filter === 'parent') params.is_repack = false;
      if (filter === 'repack') params.is_repack = true;
      const res = await api.get('/products', { params });
      setProducts(res.data.products);
      setTotal(res.data.total);
    } catch { toast.error('Failed to load products'); }
  }, [search, filter, page]);

  useEffect(() => { fetchProducts(); }, [fetchProducts]);
  useEffect(() => {
    api.get('/price-schemes').then(r => setSchemes(r.data)).catch(() => {});
    api.get('/products/categories').then(r => setCategories(r.data)).catch(() => {});
  }, []);

  // Load all repack parent IDs so we can show green/red indicator
  const refreshRepackIndicators = useCallback(async () => {
    try {
      const res = await api.get('/products', { params: { is_repack: true, limit: 5000 } });
      const ids = new Set((res.data.products || []).filter(p => p.parent_id).map(p => p.parent_id));
      setRepackParentIds(ids);
    } catch {}
  }, []);
  useEffect(() => { refreshRepackIndicators(); }, [refreshRepackIndicators]);

  const openCreate = (prefillName = '') => {
    setEditing(null);
    setForm({ sku: '', name: prefillName, category: 'Pesticide', unit: 'Box', cost_price: 0, prices: {}, barcode: '', description: '', product_type: 'stockable', starting_inventory: 0 });
    setDialogOpen(true);
  };

  const openEdit = (p) => {
    setEditing(p);
    setForm({ sku: p.sku, name: p.name, category: p.category, unit: p.unit, cost_price: p.cost_price, prices: p.prices || {}, barcode: p.barcode || '', description: p.description || '' });
    setDialogOpen(true);
  };

  const openRepack = (p) => {
    if (repackParentIds.has(p.id)) {
      // Already has repacks — show confirmation first
      setRepackConfirmParent(p);
      return;
    }
    // No repacks yet — open directly
    _launchRepackDialog(p);
  };

  const _launchRepackDialog = (p) => {
    setSelectedParent(p);
    const autoCost = p.cost_price ? Math.round((p.cost_price / 1) * 100) / 100 : 0;
    setRepackForm({ name: `R ${p.name}`, unit: 'Sachet', units_per_parent: 1, cost_price: autoCost, add_on_cost: 0, prices: {} });
    setRepackDialog(true);
  };

  const handleSave = async () => {
    try {
      if (editing) {
        await api.put(`/products/${editing.id}`, form);
        toast.success('Product updated');
      } else {
        const res = await api.post('/products', form);
        // Set starting inventory if provided
        if (form.starting_inventory > 0 && currentBranch) {
          await api.post('/inventory/set', {
            product_id: res.data.id, branch_id: currentBranch.id, quantity: form.starting_inventory
          });
        }
        toast.success('Product created');
      }
      setDialogOpen(false);
      fetchProducts();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error saving product'); }
  };

  const handleRepack = async () => {
    try {
      await api.post(`/products/${selectedParent.id}/generate-repack`, repackForm);
      toast.success('Repack SKU generated!');
      setRepackDialog(false);
      fetchProducts();
      refreshRepackIndicators();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error generating repack'); }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this product? This will also deactivate linked repacks.')) return;
    try {
      await api.delete(`/products/${id}`);
      toast.success('Product deleted');
      fetchProducts();
    } catch { toast.error('Failed to delete'); }
  };

  const handleBulkDelete = async () => {
    if (!selected.size) return;
    if (!window.confirm(`Delete ${selected.size} product(s)? This will also deactivate their linked repacks.`)) return;
    let deleted = 0;
    for (const id of selected) {
      try { await api.delete(`/products/${id}`); deleted++; } catch {}
    }
    toast.success(`${deleted} product(s) deleted`);
    setSelected(new Set());
    fetchProducts();
  };

  const toggleSelect = (id) => setSelected(prev => { const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s; });
  const toggleAll = () => { if (selected.size === products.length) { setSelected(new Set()); } else { setSelected(new Set(products.map(p => p.id))); } };

  const updatePrice = (key, val) => setForm({ ...form, prices: { ...form.prices, [key]: parseFloat(val) || 0 } });
  const updateRepackPrice = (key, val) => setRepackForm({ ...repackForm, prices: { ...repackForm.prices, [key]: parseFloat(val) || 0 } });

  const totalPages = Math.ceil(total / LIMIT);

  return (
    <div className="space-y-6 animate-fadeIn" data-testid="products-page">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>Products</h1>
          <p className="text-sm text-slate-500 mt-1">{total} products &middot; Parent & Repack management</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => navigate('/import')} data-testid="go-to-import-btn">
            <Upload size={15} className="mr-1.5" /> Import
          </Button>
          <Button variant="outline" size="sm" onClick={openQrModal} data-testid="quick-repack-btn">
            <Zap size={15} className="mr-1.5 text-amber-500" /> Quick Repack
          </Button>
          <Button data-testid="create-product-btn" onClick={() => openCreate()} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">
            <Plus size={16} className="mr-2" /> Add Product
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input
            data-testid="product-search"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(0); }}
            placeholder="Search SKU or name..."
            className="pl-9 h-10"
          />
        </div>
        <Select value={filter} onValueChange={v => { setFilter(v); setPage(0); }}>
          <SelectTrigger data-testid="product-filter" className="w-[160px] h-10">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Products</SelectItem>
            <SelectItem value="parent">Parent Only</SelectItem>
            <SelectItem value="repack">Repacks Only</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Bulk Actions */}
      {selected.size > 0 && (
        <div className="flex items-center gap-3 bg-red-50 border border-red-200 rounded-lg px-4 py-2 animate-fadeIn">
          <span className="text-sm font-medium text-red-700">{selected.size} selected</span>
          <Button size="sm" variant="destructive" onClick={handleBulkDelete} data-testid="bulk-delete-btn">
            <Trash2 size={13} className="mr-1" /> Delete Selected
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())} className="text-slate-500 text-xs">Clear</Button>
        </div>
      )}

      {/* Products Table */}
      <Card className="border-slate-200">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead className="w-10"><input type="checkbox" checked={products.length > 0 && selected.size === products.length} onChange={toggleAll} className="rounded border-slate-300 cursor-pointer" /></TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">SKU</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Product Name</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Category</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Unit</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium text-right">Cost</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Type</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium w-32">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {products.map(p => (
                <TableRow key={p.id} className={`table-row-hover ${selected.has(p.id) ? 'bg-blue-50/50' : ''}`}>
                  <TableCell><input type="checkbox" checked={selected.has(p.id)} onChange={() => toggleSelect(p.id)} className="rounded border-slate-300 cursor-pointer" /></TableCell>
                  <TableCell className="font-mono text-xs">{p.sku}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      {p.is_repack && <span className="w-4 border-l-2 border-b-2 border-slate-300 h-3 inline-block" />}
                      <span className="font-medium">{p.name}</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-slate-500">{p.category}</TableCell>
                  <TableCell>{p.unit}</TableCell>
                  <TableCell className="text-right font-mono">{formatPHP(p.cost_price)}</TableCell>
                  <TableCell>
                    {p.is_repack ? (
                      <Badge variant="outline" className="text-[10px] border-amber-300 text-amber-700 bg-amber-50">Repack</Badge>
                    ) : (
                      <Badge variant="outline" className="text-[10px] border-emerald-300 text-emerald-700 bg-emerald-50">Parent</Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="sm" data-testid={`view-product-${p.id}`} onClick={() => navigate(`/products/${p.id}`)} title="View Details">
                        <Eye size={14} className="text-blue-500" />
                      </Button>
                      {!p.is_repack && (
                        <Button variant="ghost" size="sm"
                          data-testid={`repack-btn-${p.id}`}
                          onClick={() => openRepack(p)}
                          title={repackParentIds.has(p.id) ? `Has repack — click to add another` : 'No repack yet — click to generate'}
                          className={repackParentIds.has(p.id) ? 'text-emerald-600 hover:text-emerald-700' : 'text-red-400 hover:text-red-500'}
                        >
                          <Link2 size={14} />
                        </Button>
                      )}
                      <Button variant="ghost" size="sm" data-testid={`edit-product-${p.id}`} onClick={() => openEdit(p)}>
                        <Pencil size={14} />
                      </Button>
                      <Button variant="ghost" size="sm" data-testid={`delete-product-${p.id}`} onClick={() => handleDelete(p.id)} className="text-red-500">
                        <Trash2 size={14} />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {!products.length && (
                <TableRow><TableCell colSpan={7} className="text-center py-8 text-slate-400">No products found</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-xs text-slate-500">Showing {page * LIMIT + 1}-{Math.min((page + 1) * LIMIT, total)} of {total}</p>
          <div className="flex gap-1">
            <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage(page - 1)}>Prev</Button>
            <Button variant="outline" size="sm" disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)}>Next</Button>
          </div>
        </div>
      )}

      {/* Product Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Manrope' }}>{editing ? 'Edit Product' : 'New Product'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>SKU <span className="text-xs text-muted-foreground font-normal">(optional - auto-generated if blank)</span></Label>
                <Input data-testid="product-sku-input" value={form.sku} onChange={e => setForm({ ...form, sku: e.target.value })} placeholder="Leave blank to auto-generate" disabled={!!editing} />
              </div>
              <div>
                <Label>Product Name</Label>
                <Input data-testid="product-name-input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="e.g. Lannate 250g" />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <Label>Category</Label>
                <Select value={form.category} onValueChange={v => setForm({ ...form, category: v })}>
                  <SelectTrigger data-testid="product-category-input" className="h-9"><SelectValue placeholder="Select category" /></SelectTrigger>
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
              <div>
                <Label>Unit</Label>
                <Input data-testid="product-unit-input" value={form.unit} onChange={e => setForm({ ...form, unit: e.target.value })} placeholder="Box, Bag, Bottle, Pack" />
              </div>
              <div>
                <Label>Cost Price</Label>
                <Input data-testid="product-cost-input" type="number" value={form.cost_price} onChange={e => setForm({ ...form, cost_price: parseFloat(e.target.value) || 0 })} />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <Label>Type</Label>
                <Select value={form.product_type || 'stockable'} onValueChange={v => setForm({ ...form, product_type: v })}>
                  <SelectTrigger data-testid="product-type-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="stockable">Stockable</SelectItem>
                    <SelectItem value="service">Service</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Barcode</Label>
                <Input value={form.barcode} onChange={e => setForm({ ...form, barcode: e.target.value })} placeholder="Optional" />
              </div>
              <div>
                <Label>Description</Label>
                <Input value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="Optional" />
              </div>
            </div>
            <div>
              <Label className="text-sm font-semibold">Price Schemes</Label>
              <div className="grid grid-cols-2 gap-3 mt-2">
                {schemes.map(s => (
                  <div key={s.id}>
                    <Label className="text-xs text-slate-500">{s.name}</Label>
                    <Input
                      data-testid={`price-${s.key}`}
                      type="number"
                      value={form.prices[s.key] || ''}
                      onChange={e => updatePrice(s.key, e.target.value)}
                      placeholder="0.00"
                    />
                  </div>
                ))}
              </div>
            </div>
            {!editing && (
              <div>
                <Label>Starting Inventory ({currentBranch?.name || 'Current Branch'})</Label>
                <Input data-testid="product-starting-inventory" type="number" value={form.starting_inventory || 0} onChange={e => setForm({ ...form, starting_inventory: parseFloat(e.target.value) || 0 })} placeholder="0" />
                <p className="text-[11px] text-slate-400 mt-0.5">Leave 0 if no stock yet</p>
              </div>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
              <Button data-testid="save-product-btn" onClick={handleSave} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">Save Product</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Repack Already Exists — Confirmation Dialog */}
      <Dialog open={!!repackConfirmParent} onOpenChange={() => setRepackConfirmParent(null)}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Manrope' }} className="flex items-center gap-2">
              <Link2 size={18} className="text-emerald-600" /> Repack Already Exists
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 mt-2">
            <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-sm">
              <p className="font-semibold text-emerald-800">{repackConfirmParent?.name}</p>
              <p className="text-emerald-600 text-xs mt-0.5">
                This product already has at least one repack SKU. You can generate an additional repack
                if needed (e.g., a different unit size).
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <Button
                className="bg-[#1A4D2E] hover:bg-[#14532d] text-white"
                onClick={() => { _launchRepackDialog(repackConfirmParent); setRepackConfirmParent(null); }}
              >
                <Link2 size={14} className="mr-2" /> Generate Another Repack
              </Button>
              <Button variant="outline"
                onClick={() => { navigate(`/products/${repackConfirmParent?.id}`); setRepackConfirmParent(null); }}
              >
                View Existing Repacks
              </Button>
              <Button variant="ghost" onClick={() => setRepackConfirmParent(null)}>Cancel</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Repack Dialog */}
      <Dialog open={repackDialog} onOpenChange={setRepackDialog}>
        <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Manrope' }}>Generate Repack SKU</DialogTitle>
          </DialogHeader>
          {selectedParent && (
            <div className="space-y-4 mt-2">
              <div className="p-3 bg-emerald-50 rounded-lg border border-emerald-200 text-sm">
                <p className="font-semibold text-emerald-800">Parent: {selectedParent.name}</p>
                <p className="text-emerald-600 text-xs">SKU: {selectedParent.sku} &middot; Unit: {selectedParent.unit}</p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Repack Name</Label>
                  <Input data-testid="repack-name-input" value={repackForm.name} onChange={e => setRepackForm({ ...repackForm, name: e.target.value })} />
                </div>
                <div>
                  <Label>Unit</Label>
                  <Input data-testid="repack-unit-input" value={repackForm.unit} onChange={e => setRepackForm({ ...repackForm, unit: e.target.value })} placeholder="Sachet, Pack, Piece" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Units per Parent ({selectedParent.unit})</Label>
                  <Input
                    data-testid="repack-units-per-parent"
                    type="number"
                    value={repackForm.units_per_parent}
                    onChange={e => {
                      const units = parseInt(e.target.value) || 1;
                      const autoCost = selectedParent.cost_price ? Math.round((selectedParent.cost_price / units + (repackForm.add_on_cost || 0)) * 100) / 100 : 0;
                      setRepackForm({ ...repackForm, units_per_parent: units, cost_price: autoCost });
                    }}
                    min={1}
                  />
                  <p className="text-[11px] text-slate-500 mt-1">How many {repackForm.unit || 'pieces'} inside 1 {selectedParent.unit}?</p>
                </div>
                <div>
                  <Label>Add-on Cost (optional)</Label>
                  <Input data-testid="repack-addon-cost" type="number" value={repackForm.add_on_cost || 0}
                    onChange={e => {
                      const addon = parseFloat(e.target.value) || 0;
                      const units = repackForm.units_per_parent || 1;
                      const autoCost = Math.round((selectedParent.cost_price / units + addon) * 100) / 100;
                      setRepackForm({ ...repackForm, add_on_cost: addon, cost_price: autoCost });
                    }}
                    placeholder="Extra cost per repack"
                  />
                  <p className="text-[11px] text-slate-500 mt-1">Repacking labor, packaging, etc.</p>
                </div>
              </div>
              <div className="p-3 bg-blue-50 rounded-lg border border-blue-200 text-sm">
                <p className="text-blue-800 font-medium">Auto-computed Cost per {repackForm.unit || 'unit'}:</p>
                <p className="text-blue-900 text-lg font-bold" style={{ fontFamily: 'Manrope' }}>
                  ₱{(selectedParent.cost_price / (repackForm.units_per_parent || 1)).toFixed(2)} (parent ÷ {repackForm.units_per_parent})
                  {(repackForm.add_on_cost || 0) > 0 && <span> + ₱{repackForm.add_on_cost.toFixed(2)} add-on</span>}
                  {' '}= <span className="text-emerald-700">₱{repackForm.cost_price.toFixed(2)}</span>
                </p>
              </div>
              <div>
                <Label className="text-sm font-semibold">Repack Prices</Label>
                <div className="grid grid-cols-2 gap-3 mt-2">
                  {schemes.map(s => (
                    <div key={s.id}>
                      <Label className="text-xs text-slate-500">{s.name}</Label>
                      <Input type="number" value={repackForm.prices[s.key] || ''} onChange={e => updateRepackPrice(s.key, e.target.value)} placeholder="0.00" />
                    </div>
                  ))}
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={() => setRepackDialog(false)}>Cancel</Button>
                <Button data-testid="generate-repack-btn" onClick={handleRepack} className="bg-[#D97706] hover:bg-[#b45309] text-white">
                  <Link2 size={16} className="mr-2" /> Generate Repack
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
      {/* ── Batch Quick Repack Generator ─────────────────────────────── */}
      <Dialog open={qrOpen} onOpenChange={setQrOpen}>
        <DialogContent className="max-w-[96vw] w-[1100px] max-h-[90vh] flex flex-col">
          <DialogHeader className="shrink-0">
            <DialogTitle style={{ fontFamily: 'Manrope' }} className="flex items-center gap-2">
              <Zap size={18} className="text-amber-500" /> Quick Repack Generator
              <span className="text-sm font-normal text-slate-500 ml-1">— fill each row, then Generate All</span>
            </DialogTitle>
          </DialogHeader>

          {/* ── Results view (after generation) ── */}
          {qrResults ? (
            <div className="flex-1 overflow-auto space-y-3 py-2">
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-center">
                  <div className="text-2xl font-bold text-emerald-700">{qrResults.filter(r => r.status === 'ok').length}</div>
                  <div className="text-xs text-emerald-600">Repacks Created</div>
                </div>
                <div className={`p-3 rounded-lg border text-center ${qrResults.filter(r => r.status === 'error').length > 0 ? 'bg-red-50 border-red-200' : 'bg-slate-50 border-slate-200'}`}>
                  <div className={`text-2xl font-bold ${qrResults.filter(r => r.status === 'error').length > 0 ? 'text-red-700' : 'text-slate-400'}`}>{qrResults.filter(r => r.status === 'error').length}</div>
                  <div className="text-xs text-slate-500">Failed</div>
                </div>
              </div>
              <div className="border rounded-lg overflow-hidden">
                {qrResults.map((r, i) => (
                  <div key={i} className={`flex items-center gap-3 px-4 py-2.5 text-sm border-b last:border-0 ${r.status === 'ok' ? 'bg-emerald-50/50' : 'bg-red-50/50'}`}>
                    {r.status === 'ok' ? <CheckCircle size={15} className="text-emerald-600 shrink-0" /> : <XCircle size={15} className="text-red-500 shrink-0" />}
                    <span className="font-medium flex-1">{r.name}</span>
                    {r.status === 'ok' ? <span className="text-xs text-emerald-600">Created</span> : <span className="text-xs text-red-500">{r.error}</span>}
                  </div>
                ))}
              </div>
              <div className="flex justify-end gap-2 pt-1">
                <Button variant="outline" onClick={() => { setQrRows([newRow()]); setQrResults(null); }}>
                  <Zap size={14} className="mr-1.5 text-amber-500" /> Generate More
                </Button>
                <Button onClick={() => setQrOpen(false)} className="bg-[#1A4D2E] text-white">Done</Button>
              </div>
            </div>
          ) : (
            /* ── Spreadsheet table ── */
            <div className="flex-1 flex flex-col overflow-hidden">
              <div className="overflow-x-auto flex-1 overflow-y-visible"
                   style={{ overflowY: 'visible' }}>
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="bg-slate-50 border-b-2 border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                      <th className="px-2 py-2 text-left font-semibold" style={{minWidth:'220px'}}>Parent Product <span className="text-red-400">*</span></th>
                      <th className="px-2 py-2 text-left font-semibold" style={{minWidth:'180px'}}>Repack Name <span className="text-red-400">*</span></th>
                      <th className="px-2 py-2 text-left font-semibold" style={{minWidth:'90px'}}>Unit</th>
                      <th className="px-2 py-2 text-center font-semibold" style={{minWidth:'90px'}}>Qty / Box</th>
                      <th className="px-2 py-2 text-center font-semibold" style={{minWidth:'90px'}}>Add-on</th>
                      <th className="px-2 py-2 text-center font-semibold" style={{minWidth:'100px'}}>Capital <span className="text-[10px] normal-case tracking-normal font-normal text-slate-400">(auto)</span></th>
                      <th className="px-2 py-2 text-center font-semibold" style={{minWidth:'115px'}}>Retail Price <span className="text-red-400">*</span></th>
                      <th className="px-2 py-2 w-8"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {qrRows.map((row) => {
                      const hasErr = !!row.rowError;
                      return (
                        <tr key={row.id} className={`border-b border-slate-100 transition-colors ${hasErr ? 'bg-red-50' : 'hover:bg-slate-50/50'}`}>

                          {/* Parent search / selected */}
                          <td className="px-2 py-1.5 relative" style={{minWidth:'220px'}}>
                            {row.parent ? (
                              <div className={`flex items-center gap-1.5 h-8 px-2 rounded border ${hasErr && !row.parent ? 'border-red-400' : 'border-emerald-300 bg-emerald-50'}`}>
                                <span className="text-sm text-emerald-800 truncate flex-1 font-medium">{row.parent.name}</span>
                                <button onClick={() => updateRow(row.id, { parent: null, parentSearch: '', capital: 0, repackName: '', retailPrice: '', retailError: null })}
                                  className="text-slate-400 hover:text-red-500 shrink-0">
                                  <X size={12} />
                                </button>
                              </div>
                            ) : (
                              <div className="relative">
                                <Search size={13} className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-400" />
                                <Input value={row.parentSearch} placeholder="Search parent..."
                                  onChange={e => searchParent(row.id, e.target.value)}
                                  className={`h-8 pl-7 text-sm ${hasErr ? 'border-red-400 bg-red-50/50' : ''}`}
                                  data-testid={`qr-parent-${row.id}`} />
                                {row.parentMatches.length > 0 && (
                                  <div className="absolute top-full mt-0.5 z-50 w-64 bg-white border border-slate-200 rounded-lg shadow-xl overflow-hidden max-h-44 overflow-y-auto">
                                    {row.parentMatches.map(p => (
                                      <button key={p.id} onMouseDown={() => selectParent(row.id, p)}
                                        className="w-full text-left px-3 py-2 hover:bg-slate-50 border-b border-slate-100 last:border-0">
                                        <div className="font-medium text-sm truncate">{p.name}</div>
                                        <div className="text-xs text-slate-400">{p.unit} · Cost ₱{p.cost_price}</div>
                                      </button>
                                    ))}
                                  </div>
                                )}
                              </div>
                            )}
                            {hasErr && !row.parent && <p className="text-[10px] text-red-500 mt-0.5 leading-none">{row.rowError}</p>}
                          </td>

                          {/* Repack Name */}
                          <td className="px-2 py-1.5" style={{minWidth:'180px'}}>
                            <Input value={row.repackName} placeholder="R Product Name"
                              onChange={e => updateRow(row.id, { repackName: e.target.value })}
                              className={`h-8 text-sm ${hasErr && !row.repackName.trim() ? 'border-red-400 bg-red-50/50' : ''}`}
                              data-testid={`qr-name-${row.id}`} />
                          </td>

                          {/* Unit */}
                          <td className="px-2 py-1.5" style={{minWidth:'90px'}}>
                            <Input value={row.unit} placeholder="Pack"
                              onChange={e => updateRow(row.id, { unit: e.target.value })}
                              className="h-8 text-sm" data-testid={`qr-unit-${row.id}`} />
                          </td>

                          {/* Qty per parent */}
                          <td className="px-2 py-1.5" style={{minWidth:'90px'}}>
                            <Input type="number" min={1} value={row.unitsPerParent}
                              onChange={e => {
                                const v = parseInt(e.target.value) || 1;
                                updateRow(row.id, { unitsPerParent: v, capital: computeCapital(row.parent, v, row.addOnCost) });
                              }}
                              className="h-8 text-sm text-right font-mono"
                              data-testid={`qr-units-${row.id}`} />
                          </td>

                          {/* Add-on cost */}
                          <td className="px-2 py-1.5" style={{minWidth:'90px'}}>
                            <Input type="number" min={0} step="0.01" value={row.addOnCost}
                              onChange={e => {
                                const v = parseFloat(e.target.value) || 0;
                                updateRow(row.id, { addOnCost: v, capital: computeCapital(row.parent, row.unitsPerParent, v) });
                              }}
                              className="h-8 text-sm text-right font-mono"
                              data-testid={`qr-addon-${row.id}`} />
                          </td>

                          {/* Capital — read-only computed */}
                          <td className="px-2 py-1.5" style={{minWidth:'100px'}}>
                            <div className={`h-8 px-2 flex items-center justify-center text-sm font-mono rounded border ${row.capital > 0 ? 'bg-blue-50 border-blue-200 text-blue-800 font-semibold' : 'bg-slate-50 border-slate-200 text-slate-400'}`}>
                              {row.capital > 0 ? `₱${row.capital.toFixed(2)}` : '—'}
                            </div>
                          </td>

                          {/* Retail price — blank, validated on blur */}
                          <td className="px-2 py-1.5" style={{minWidth:'115px'}}>
                            <Input type="number" min={0} step="0.01" value={row.retailPrice}
                              placeholder="0.00"
                              onChange={e => updateRow(row.id, { retailPrice: e.target.value, retailError: null })}
                              onBlur={e => handleRetailBlur(row.id, e.target.value)}
                              onKeyDown={e => {
                                if (e.key === 'Tab' && !e.shiftKey) {
                                  e.preventDefault();
                                  const next = newRow();
                                  pendingFocusRowId.current = next.id;
                                  setQrRows(rows => [...rows, next]);
                                }
                              }}
                              className={`h-8 text-sm text-right font-mono font-bold ${
                                (hasErr && !row.retailPrice) || row.retailError ? 'border-red-400 bg-red-50/50 text-red-700' : ''
                              }`}
                              data-testid={`qr-retail-${row.id}`} />
                            {row.retailError && (
                              <p className="text-[10px] text-red-500 mt-0.5 leading-none whitespace-nowrap">{row.retailError}</p>
                            )}
                            {hasErr && !row.retailPrice && !row.retailError && (
                              <p className="text-[10px] text-red-500 mt-0.5 leading-none">Required</p>
                            )}
                          </td>

                          {/* Delete row */}
                          <td className="px-1 py-1.5 w-8">
                            {qrRows.length > 1 && (
                              <button onClick={() => removeRow(row.id)}
                                className="p-1 text-slate-300 hover:text-red-500 transition-colors rounded">
                                <Trash2 size={14} />
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Footer actions */}
              <div className="shrink-0 flex items-center justify-between pt-3 border-t border-slate-200 mt-3">
                <Button variant="outline" size="sm" onClick={() => setQrRows(r => [...r, newRow()])} data-testid="qr-add-row">
                  <Plus size={14} className="mr-1.5" /> Add Row
                </Button>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-400">{qrRows.length} row{qrRows.length !== 1 ? 's' : ''}</span>
                  <Button variant="outline" onClick={() => setQrOpen(false)}>Cancel</Button>
                  <Button onClick={handleBatchGenerate} disabled={qrGenerating}
                    className="bg-amber-600 hover:bg-amber-700 text-white min-w-36"
                    data-testid="qr-generate-all-btn">
                    {qrGenerating ? (
                      <><div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />Generating...</>
                    ) : (
                      <><Zap size={15} className="mr-1.5" />Generate {qrRows.length} Repack{qrRows.length !== 1 ? 's' : ''}</>
                    )}
                  </Button>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
