import { useState, useEffect, useCallback } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Warehouse, Search, Plus, ArrowRightLeft, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';

export default function InventoryPage() {
  const { currentBranch, branches } = useAuth();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [lowStock, setLowStock] = useState(false);
  const [page, setPage] = useState(0);
  const [adjustDialog, setAdjustDialog] = useState(false);
  const [transferDialog, setTransferDialog] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [adjustForm, setAdjustForm] = useState({ quantity: 0, reason: '' });
  const [transferForm, setTransferForm] = useState({ to_branch_id: '', quantity: 0 });
  const LIMIT = 30;

  const fetchInventory = useCallback(async () => {
    try {
      const params = { skip: page * LIMIT, limit: LIMIT };
      if (currentBranch) params.branch_id = currentBranch.id;
      if (search) params.search = search;
      if (lowStock) params.low_stock = true;
      const res = await api.get('/inventory', { params });
      setItems(res.data.items);
      setTotal(res.data.total);
    } catch { toast.error('Failed to load inventory'); }
  }, [currentBranch, search, lowStock, page]);

  useEffect(() => { fetchInventory(); }, [fetchInventory]);

  const openAdjust = (prod) => {
    setSelectedProduct(prod);
    setAdjustForm({ quantity: 0, reason: '' });
    setAdjustDialog(true);
  };

  const openTransfer = (prod) => {
    setSelectedProduct(prod);
    setTransferForm({ to_branch_id: '', quantity: 0 });
    setTransferDialog(true);
  };

  const handleAdjust = async () => {
    try {
      await api.post('/inventory/adjust', {
        product_id: selectedProduct.id,
        branch_id: currentBranch?.id,
        quantity: parseFloat(adjustForm.quantity),
        reason: adjustForm.reason
      });
      toast.success('Inventory adjusted');
      setAdjustDialog(false);
      fetchInventory();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error adjusting'); }
  };

  const handleTransfer = async () => {
    try {
      await api.post('/inventory/transfer', {
        product_id: selectedProduct.id,
        from_branch_id: currentBranch?.id,
        to_branch_id: transferForm.to_branch_id,
        quantity: parseFloat(transferForm.quantity)
      });
      toast.success('Transfer complete');
      setTransferDialog(false);
      fetchInventory();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error transferring'); }
  };

  const getStockDisplay = (item) => {
    const branchStock = currentBranch ? (item.branch_stock?.[currentBranch.id] || 0) : item.total_stock;
    if (!item.is_repack && item.units_per_parent) {
      const whole = Math.floor(branchStock);
      const frac = branchStock - whole;
      if (frac > 0) return `${whole} ${item.unit}${whole !== 1 ? 's' : ''} + ${Math.round(frac * (item.units_per_parent || 1))} pcs`;
    }
    return `${branchStock?.toFixed(2)} ${item.unit}`;
  };

  const totalPages = Math.ceil(total / LIMIT);

  return (
    <div className="space-y-6 animate-fadeIn" data-testid="inventory-page">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>Inventory</h1>
          <p className="text-sm text-slate-500 mt-1">Stock levels for {currentBranch?.name || 'all branches'}</p>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input data-testid="inventory-search" value={search} onChange={e => { setSearch(e.target.value); setPage(0); }} placeholder="Search products..." className="pl-9 h-10" />
        </div>
        <Button
          variant={lowStock ? "default" : "outline"}
          onClick={() => { setLowStock(!lowStock); setPage(0); }}
          data-testid="low-stock-filter"
          className={lowStock ? "bg-amber-500 hover:bg-amber-600 text-white" : ""}
        >
          <AlertTriangle size={14} className="mr-2" /> Low Stock
        </Button>
      </div>

      <Card className="border-slate-200">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">SKU</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Product</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Type</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium text-right">Stock</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium text-right">Total (All)</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium w-32">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map(item => {
                const branchQty = currentBranch ? (item.branch_stock?.[currentBranch.id] || 0) : item.total_stock;
                const isLow = branchQty <= 10 && branchQty > 0;
                const isOut = branchQty <= 0;
                return (
                  <TableRow key={item.id} className="table-row-hover">
                    <TableCell className="font-mono text-xs">{item.sku}</TableCell>
                    <TableCell className="font-medium">{item.name}</TableCell>
                    <TableCell>
                      {item.is_repack ? (
                        <Badge variant="outline" className="text-[10px] border-amber-300 text-amber-700 bg-amber-50">Repack</Badge>
                      ) : (
                        <Badge variant="outline" className="text-[10px] border-emerald-300 text-emerald-700 bg-emerald-50">Parent</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <span className={`font-semibold ${isOut ? 'text-red-600' : isLow ? 'text-amber-600' : 'text-slate-900'}`}>
                        {getStockDisplay(item)}
                      </span>
                    </TableCell>
                    <TableCell className="text-right text-slate-500">{item.total_stock?.toFixed(2)}</TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button variant="ghost" size="sm" data-testid={`adjust-${item.id}`} onClick={() => openAdjust(item)} title="Adjust Stock">
                          <Plus size={14} />
                        </Button>
                        <Button variant="ghost" size="sm" data-testid={`transfer-${item.id}`} onClick={() => openTransfer(item)} title="Transfer">
                          <ArrowRightLeft size={14} />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
              {!items.length && (
                <TableRow><TableCell colSpan={6} className="text-center py-8 text-slate-400">No inventory data</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-xs text-slate-500">Page {page + 1} of {totalPages}</p>
          <div className="flex gap-1">
            <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage(page - 1)}>Prev</Button>
            <Button variant="outline" size="sm" disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)}>Next</Button>
          </div>
        </div>
      )}

      {/* Adjust Dialog */}
      <Dialog open={adjustDialog} onOpenChange={setAdjustDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Adjust Stock</DialogTitle></DialogHeader>
          {selectedProduct && (
            <div className="space-y-4 mt-2">
              <p className="text-sm font-medium">{selectedProduct.name} ({selectedProduct.sku})</p>
              <div>
                <Label>Quantity Change (+ to add, - to subtract)</Label>
                <Input data-testid="adjust-quantity-input" type="number" value={adjustForm.quantity} onChange={e => setAdjustForm({ ...adjustForm, quantity: e.target.value })} />
              </div>
              <div>
                <Label>Reason</Label>
                <Input data-testid="adjust-reason-input" value={adjustForm.reason} onChange={e => setAdjustForm({ ...adjustForm, reason: e.target.value })} placeholder="e.g. Received delivery" />
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setAdjustDialog(false)}>Cancel</Button>
                <Button data-testid="save-adjust-btn" onClick={handleAdjust} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">Adjust</Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Transfer Dialog */}
      <Dialog open={transferDialog} onOpenChange={setTransferDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Transfer Stock</DialogTitle></DialogHeader>
          {selectedProduct && (
            <div className="space-y-4 mt-2">
              <p className="text-sm font-medium">{selectedProduct.name} ({selectedProduct.sku})</p>
              <p className="text-xs text-slate-500">From: {currentBranch?.name}</p>
              <div>
                <Label>To Branch</Label>
                <Select value={transferForm.to_branch_id} onValueChange={v => setTransferForm({ ...transferForm, to_branch_id: v })}>
                  <SelectTrigger data-testid="transfer-branch-select"><SelectValue placeholder="Select branch" /></SelectTrigger>
                  <SelectContent>
                    {branches.filter(b => b.id !== currentBranch?.id).map(b => (
                      <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Quantity</Label>
                <Input data-testid="transfer-quantity-input" type="number" value={transferForm.quantity} onChange={e => setTransferForm({ ...transferForm, quantity: e.target.value })} min={0} />
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setTransferDialog(false)}>Cancel</Button>
                <Button data-testid="save-transfer-btn" onClick={handleTransfer} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">Transfer</Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
