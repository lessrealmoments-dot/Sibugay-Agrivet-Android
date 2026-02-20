import { useState, useEffect, useCallback } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Receipt, Edit3 } from 'lucide-react';
import { toast } from 'sonner';
import InvoiceDetailModal from '../components/InvoiceDetailModal';

export default function SalesPage() {
  const { currentBranch } = useAuth();
  const [sales, setSales] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [detailDialog, setDetailDialog] = useState(false);
  const [selectedSale, setSelectedSale] = useState(null);
  const LIMIT = 20;
  
  // Invoice detail modal
  const [invoiceModalOpen, setInvoiceModalOpen] = useState(false);
  const [selectedInvoiceId, setSelectedInvoiceId] = useState(null);

  const fetchSales = useCallback(async () => {
    try {
      const params = { skip: page * LIMIT, limit: LIMIT };
      if (currentBranch) params.branch_id = currentBranch.id;
      // Use invoices endpoint as sales are now stored as invoices
      const res = await api.get('/invoices', { params });
      // Map invoice format to sales format for backward compatibility
      const invoices = res.data.invoices || [];
      const mappedSales = invoices.map(inv => ({
        ...inv,
        sale_number: inv.invoice_number,
        total: inv.grand_total,
        items: inv.items || [],
        status: inv.status === 'voided' ? 'voided' : 'completed',
      }));
      setSales(mappedSales);
      setTotal(res.data.total || 0);
    } catch { toast.error('Failed to load sales'); }
  }, [currentBranch, page]);

  useEffect(() => { fetchSales(); }, [fetchSales]);

  const openInvoiceDetail = (sale) => {
    setSelectedInvoiceId(sale.id);
    setInvoiceModalOpen(true);
  };

  const viewSale = async (sale) => {
    try {
      // Use invoices endpoint
      const res = await api.get(`/invoices/${sale.id}`);
      const inv = res.data;
      // Map to sale format
      setSelectedSale({
        ...inv,
        sale_number: inv.invoice_number,
        total: inv.grand_total,
        subtotal: inv.subtotal,
        discount: inv.overall_discount || 0,
        items: inv.items || [],
        status: inv.status === 'voided' ? 'voided' : 'completed',
      });
      setDetailDialog(true);
    } catch { toast.error('Failed to load sale details'); }
  };

  const voidSale = async (saleId) => {
    if (!window.confirm('Void this sale? Stock will be restored.')) return;
    try { await api.post(`/sales/${saleId}/void`); toast.success('Sale voided'); fetchSales(); setDetailDialog(false); }
    catch (e) { toast.error(e.response?.data?.detail || 'Failed to void sale'); }
  };

  const totalPages = Math.ceil(total / LIMIT);

  return (
    <div className="space-y-6 animate-fadeIn" data-testid="sales-page">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>Sales History</h1>
        <p className="text-sm text-slate-500 mt-1">{total} transactions</p>
      </div>

      <Card className="border-slate-200">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Sale #</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Customer</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Items</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium text-right">Total</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Payment</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Cashier</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Status</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Date</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sales.map(s => (
                <TableRow key={s.id} className="table-row-hover">
                  <TableCell>
                    <button 
                      className="font-mono text-xs text-blue-600 hover:text-blue-800 hover:underline flex items-center gap-1"
                      onClick={() => openInvoiceDetail(s)}
                    >
                      {s.sale_number || s.invoice_number}
                      {s.edited && <Edit3 size={10} className="text-orange-500" />}
                    </button>
                  </TableCell>
                  <TableCell onClick={() => viewSale(s)} className="cursor-pointer">{s.customer_name}</TableCell>
                  <TableCell onClick={() => viewSale(s)} className="cursor-pointer">{s.items?.length || 0}</TableCell>
                  <TableCell onClick={() => viewSale(s)} className="cursor-pointer text-right font-semibold">{s.total?.toFixed(2)}</TableCell>
                  <TableCell onClick={() => viewSale(s)} className="cursor-pointer"><Badge variant="outline" className="text-[10px]">{s.payment_method}</Badge></TableCell>
                  <TableCell onClick={() => viewSale(s)} className="cursor-pointer text-slate-500 text-sm">{s.cashier_name}</TableCell>
                  <TableCell onClick={() => viewSale(s)} className="cursor-pointer">
                    <Badge className={`text-[10px] ${s.status === 'voided' ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'}`}>
                      {s.status}
                    </Badge>
                  </TableCell>
                  <TableCell onClick={() => viewSale(s)} className="cursor-pointer text-xs text-slate-500">{new Date(s.created_at).toLocaleDateString()}</TableCell>
                </TableRow>
              ))}
              {!sales.length && (
                <TableRow><TableCell colSpan={8} className="text-center py-8 text-slate-400">No sales yet</TableCell></TableRow>
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

      <Dialog open={detailDialog} onOpenChange={setDetailDialog}>
        <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Sale Details</DialogTitle></DialogHeader>
          {selectedSale && (
            <div className="space-y-4 mt-2">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div><span className="text-slate-500">Sale #:</span> <span className="font-mono">{selectedSale.sale_number}</span></div>
                <div><span className="text-slate-500">Date:</span> {new Date(selectedSale.created_at).toLocaleString()}</div>
                <div><span className="text-slate-500">Customer:</span> {selectedSale.customer_name}</div>
                <div><span className="text-slate-500">Cashier:</span> {selectedSale.cashier_name}</div>
                <div><span className="text-slate-500">Payment:</span> {selectedSale.payment_method}</div>
                <div><span className="text-slate-500">Status:</span> <Badge className={selectedSale.status === 'voided' ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'}>{selectedSale.status}</Badge></div>
              </div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">Product</TableHead>
                    <TableHead className="text-xs text-right">Qty</TableHead>
                    <TableHead className="text-xs text-right">Price</TableHead>
                    <TableHead className="text-xs text-right">Total</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {selectedSale.items?.map((item, i) => (
                    <TableRow key={i}>
                      <TableCell className="text-sm">{item.product_name} {item.is_repack && <Badge variant="outline" className="text-[9px] ml-1">R</Badge>}</TableCell>
                      <TableCell className="text-right">{item.quantity}</TableCell>
                      <TableCell className="text-right">{item.price?.toFixed(2)}</TableCell>
                      <TableCell className="text-right font-semibold">{item.total?.toFixed(2)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between"><span>Subtotal</span><span>{selectedSale.subtotal?.toFixed(2)}</span></div>
                <div className="flex justify-between"><span>Discount</span><span>-{selectedSale.discount?.toFixed(2)}</span></div>
                <div className="flex justify-between text-lg font-bold pt-2 border-t"><span>Total</span><span>{selectedSale.total?.toFixed(2)}</span></div>
              </div>
              {selectedSale.status === 'completed' && (
                <Button data-testid="void-sale-btn" variant="destructive" className="w-full" onClick={() => voidSale(selectedSale.id)}>Void Sale</Button>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Invoice Detail Modal */}
      <InvoiceDetailModal 
        open={invoiceModalOpen}
        onOpenChange={setInvoiceModalOpen}
        invoiceId={selectedInvoiceId}
        onUpdated={fetchSales}
      />
    </div>
  );
}
