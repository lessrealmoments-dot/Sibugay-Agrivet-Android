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
  const LIMIT = 20;

  const [form, setForm] = useState({ sku: '', name: '', category: 'General', unit: 'Box', cost_price: 0, prices: {}, barcode: '', description: '', product_type: 'stockable', unit_of_measurement: 'Box' });
  const [repackForm, setRepackForm] = useState({ name: '', unit: 'Sachet', units_per_parent: 1, cost_price: 0, prices: {} });

  // ── Batch Quick Repack ──────────────────────────────────────────────────────
  const [qrOpen, setQrOpen] = useState(false);
  const [qrRows, setQrRows] = useState([]);
  const [qrGenerating, setQrGenerating] = useState(false);
  const [qrResults, setQrResults] = useState(null); // null = not yet generated
  const searchTimers = useRef({});

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
    if (!query || query.length < 2) { updateRow(rowId, { parentMatches: [] }); return; }
    searchTimers.current[rowId] = setTimeout(async () => {
      try {
        const res = await api.get('/products', { params: { search: query, is_repack: false, limit: 8 } });
        updateRow(rowId, { parentMatches: res.data.products || [] });
      } catch {}
    }, 250);
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
          <Button variant="outline" size="sm" onClick={() => { setQrOpen(true); setQrParent(null); setQrSearch(''); setQrForm({ name: '', unit: 'Pack', units_per_parent: 1, add_on_cost: 0, retail_price: 0 }); }} data-testid="quick-repack-btn">
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
                        <Button variant="ghost" size="sm" data-testid={`repack-btn-${p.id}`} onClick={() => openRepack(p)} title="Generate Repack">
                          <Link2 size={14} className="text-amber-600" />
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
      {/* Quick Repack Generator */}
      <Dialog open={qrOpen} onOpenChange={setQrOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Manrope' }} className="flex items-center gap-2">
              <Zap size={18} className="text-amber-500" /> Quick Repack Generator
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-1">
            {/* Step 1: Parent search */}
            <div className="relative">
              <Label className="mb-1.5 block">Parent Product <span className="text-red-500">*</span></Label>
              <div className="relative">
                <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  className="pl-9"
                  placeholder="Search parent product name..."
                  value={qrSearch}
                  onChange={e => { setQrSearch(e.target.value); setQrParent(null); }}
                  data-testid="qr-parent-search"
                  autoFocus
                />
              </div>
              {qrMatches.length > 0 && !qrParent && (
                <div className="absolute z-20 top-full mt-1 w-full bg-white border border-slate-200 rounded-lg shadow-lg overflow-hidden">
                  {qrMatches.map(p => (
                    <button key={p.id} onMouseDown={() => selectQrParent(p)}
                      className="w-full text-left px-3 py-2 hover:bg-slate-50 text-sm border-b border-slate-100 last:border-0">
                      <div className="font-medium">{p.name}</div>
                      <div className="text-xs text-slate-400">{p.sku} · {p.unit} · Cost: ₱{p.cost_price}</div>
                    </button>
                  ))}
                </div>
              )}
              {qrParent && (
                <div className="mt-2 p-2.5 bg-emerald-50 border border-emerald-200 rounded-lg text-sm">
                  <span className="font-semibold text-emerald-800">{qrParent.name}</span>
                  <span className="text-emerald-600 text-xs ml-2">{qrParent.unit} · Cost ₱{qrParent.cost_price}</span>
                </div>
              )}
            </div>

            {qrParent && (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="mb-1.5 block">Repack Name</Label>
                    <Input value={qrForm.name} onChange={e => setQrForm(f => ({ ...f, name: e.target.value }))}
                      placeholder={`R ${qrParent.name}`} data-testid="qr-name" />
                  </div>
                  <div>
                    <Label className="mb-1.5 block">Repack Unit</Label>
                    <Input value={qrForm.unit} onChange={e => setQrForm(f => ({ ...f, unit: e.target.value }))}
                      placeholder="Pack, Sachet, Piece" data-testid="qr-unit" />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="mb-1.5 block">Qty per {qrParent.unit} <span className="text-red-500">*</span></Label>
                    <Input type="number" min={1} value={qrForm.units_per_parent}
                      onChange={e => setQrForm(f => ({ ...f, units_per_parent: parseInt(e.target.value) || 1 }))}
                      data-testid="qr-units-per-parent" />
                    <p className="text-[10px] text-slate-400 mt-0.5">How many {qrForm.unit || 'pcs'} in 1 {qrParent.unit}</p>
                  </div>
                  <div>
                    <Label className="mb-1.5 block">Add-on Cost</Label>
                    <Input type="number" min={0} step="0.01" value={qrForm.add_on_cost}
                      onChange={e => setQrForm(f => ({ ...f, add_on_cost: parseFloat(e.target.value) || 0 }))}
                      data-testid="qr-addon-cost" placeholder="0.00" />
                    <p className="text-[10px] text-slate-400 mt-0.5">Packaging, labor, etc.</p>
                  </div>
                </div>

                {/* Auto cost preview */}
                <div className="flex items-center gap-2 text-sm p-2.5 bg-blue-50 border border-blue-200 rounded-lg">
                  <span className="text-blue-600">Auto cost:</span>
                  <span className="font-bold text-blue-800">
                    ₱{((qrParent.cost_price / (qrForm.units_per_parent || 1)) + (qrForm.add_on_cost || 0)).toFixed(2)}
                  </span>
                  <span className="text-blue-500 text-xs">(₱{qrParent.cost_price} ÷ {qrForm.units_per_parent}{qrForm.add_on_cost > 0 ? ` + ₱${qrForm.add_on_cost}` : ''})</span>
                </div>

                <div>
                  <Label className="mb-1.5 block">
                    Retail Price <span className="text-red-500">*</span>
                    <span className="text-xs font-normal text-slate-500 ml-2">— applied to ALL price schemes</span>
                  </Label>
                  <Input type="number" min={0} step="0.01" value={qrForm.retail_price}
                    onChange={e => setQrForm(f => ({ ...f, retail_price: parseFloat(e.target.value) || 0 }))}
                    className="text-lg font-bold"
                    data-testid="qr-retail-price" placeholder="0.00" />
                  {schemes.length > 0 && (
                    <p className="text-[10px] text-slate-400 mt-0.5">
                      Will set: {schemes.map(s => s.name).join(', ')} → all to ₱{qrForm.retail_price}
                    </p>
                  )}
                </div>

                <div className="flex justify-end gap-2 pt-1">
                  <Button variant="outline" onClick={() => setQrOpen(false)}>Cancel</Button>
                  <Button onClick={handleQuickRepack} className="bg-amber-600 hover:bg-amber-700 text-white" data-testid="qr-generate-btn">
                    <Zap size={14} className="mr-1.5" /> Generate Repack
                  </Button>
                </div>
              </>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
