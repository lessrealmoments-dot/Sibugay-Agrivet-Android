import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth, api } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Warehouse, Search, AlertTriangle, ExternalLink } from 'lucide-react';
import { toast } from 'sonner';

export default function InventoryPage() {
  const navigate = useNavigate();
  const { currentBranch } = useAuth();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [lowStock, setLowStock] = useState(false);
  const [page, setPage] = useState(0);
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

  const totalPages = Math.ceil(total / LIMIT);

  return (
    <div className="space-y-6 animate-fadeIn" data-testid="inventory-page">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>Inventory</h1>
        <p className="text-sm text-slate-500 mt-1">Stock levels for {currentBranch?.name || 'all branches'} &middot; Click a product for full details</p>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input data-testid="inventory-search" value={search} onChange={e => { setSearch(e.target.value); setPage(0); }} placeholder="Search products..." className="pl-9 h-10" />
        </div>
        <Button variant={lowStock ? "default" : "outline"} onClick={() => { setLowStock(!lowStock); setPage(0); }}
          data-testid="low-stock-filter" className={lowStock ? "bg-amber-500 hover:bg-amber-600 text-white" : ""}>
          <AlertTriangle size={14} className="mr-2" /> Low Stock
        </Button>
      </div>

      <Card className="border-slate-200">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Product</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">SKU</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Category</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Type</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium text-right">On Hand</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium text-right">Total (All)</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map(item => {
                const branchQty = currentBranch ? (item.branch_stock?.[currentBranch.id] || 0) : item.total_stock;
                const isLow = branchQty <= (item.reorder_point || 10) && branchQty > 0;
                const isOut = branchQty <= 0;
                return (
                  <TableRow key={item.id} className="table-row-hover cursor-pointer" onClick={() => navigate(`/products/${item.id}`)} data-testid={`inv-row-${item.id}`}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {item.is_repack && <span className="w-4 border-l-2 border-b-2 border-slate-300 h-3" />}
                        <span className="font-medium">{item.name}</span>
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-xs">{item.sku}</TableCell>
                    <TableCell className="text-sm text-slate-500">{item.category}</TableCell>
                    <TableCell>
                      {item.is_repack ? (
                        <Badge variant="outline" className="text-[10px] border-amber-300 text-amber-700 bg-amber-50">Repack</Badge>
                      ) : item.product_type === 'service' ? (
                        <Badge variant="outline" className="text-[10px] border-blue-300 text-blue-700 bg-blue-50">Service</Badge>
                      ) : (
                        <Badge variant="outline" className="text-[10px] border-emerald-300 text-emerald-700 bg-emerald-50">Stockable</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <span className={`font-semibold ${isOut ? 'text-red-600' : isLow ? 'text-amber-600' : ''}`}>
                        {branchQty.toFixed(2)} {item.unit}
                      </span>
                    </TableCell>
                    <TableCell className="text-right text-slate-500">{item.total_stock?.toFixed(2)}</TableCell>
                    <TableCell>
                      {isOut ? <Badge className="bg-red-100 text-red-700 text-[10px]">Out of Stock</Badge>
                        : isLow ? <Badge className="bg-amber-100 text-amber-700 text-[10px]">Low</Badge>
                        : <Badge className="bg-emerald-100 text-emerald-700 text-[10px]">In Stock</Badge>}
                    </TableCell>
                  </TableRow>
                );
              })}
              {!items.length && (
                <TableRow><TableCell colSpan={7} className="text-center py-8 text-slate-400">No inventory data</TableCell></TableRow>
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
    </div>
  );
}
