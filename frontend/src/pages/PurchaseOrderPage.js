import { useState, useEffect, useRef } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import SmartProductSearch from '../components/SmartProductSearch';
import { FileText, Plus, Trash2, Save, Truck, Check, X, DollarSign } from 'lucide-react';
import { toast } from 'sonner';

const EMPTY_LINE = { product_id: '', product_name: '', description: '', quantity: 1, unit_price: 0 };

export default function PurchaseOrderPage() {
  const { currentBranch } = useAuth();
  const [tab, setTab] = useState('create');
  const [orders, setOrders] = useState([]);
  const [totalOrders, setTotalOrders] = useState(0);
  const [prefixes, setPrefixes] = useState({});
  const [header, setHeader] = useState({
    vendor: '', branch_id: '', purchase_date: new Date().toISOString().slice(0, 10), notes: '', status: 'ordered', payment_method: 'cash',
  });
  const [lines, setLines] = useState([{ ...EMPTY_LINE }]);
  const [saving, setSaving] = useState(false);
  const [payDialog, setPayDialog] = useState(false);
  const [selectedPO, setSelectedPO] = useState(null);
  const [payForm, setPayForm] = useState({ amount: 0, reference: '' });
  const [detailDialog, setDetailDialog] = useState(false);
  const [detailPO, setDetailPO] = useState(null);
  const [createProductDialog, setCreateProductDialog] = useState(false);
  const [newProductForm, setNewProductForm] = useState({ sku: '', name: '', category: 'General', unit: 'Box', cost_price: 0, prices: {}, product_type: 'stockable' });
  const [schemes, setSchemes] = useState([]);
  const qtyRefs = useRef([]);

  useEffect(() => {
    api.get('/settings/invoice-prefixes').then(r => setPrefixes(r.data)).catch(() => {});
    api.get('/price-schemes').then(r => setSchemes(r.data)).catch(() => {});
    fetchOrders();
  }, [currentBranch]);

  const fetchOrders = async () => {
    try {
      const res = await api.get('/purchase-orders', { params: { limit: 100 } });
      setOrders(res.data.purchase_orders);
      setTotalOrders(res.data.total);
    } catch {}
  };

  const handleCreateNewProduct = (name) => {
    setNewProductForm({ sku: '', name, category: 'General', unit: 'Box', cost_price: 0, prices: {}, product_type: 'stockable' });
    setCreateProductDialog(true);
  };

  const saveNewProduct = async () => {
    try {
      const res = await api.post('/products', newProductForm);
      toast.success(`Product "${res.data.name}" created!`);
      setCreateProductDialog(false);
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  const handleProductSelect = (index, product) => {
    const newLines = [...lines];
    newLines[index] = {
      ...newLines[index],
      product_id: product.id, product_name: product.name,
      description: product.description || '', unit_price: product.cost_price || 0,
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

  const subtotal = lines.reduce((s, l) => s + (l.quantity * l.unit_price), 0);

  const handleSave = async () => {
    const validLines = lines.filter(l => l.product_id);
    if (!validLines.length) { toast.error('Add at least one product'); return; }
    if (!header.vendor) { toast.error('Enter vendor name'); return; }
    if (!currentBranch) { toast.error('Select a branch'); return; }
    setSaving(true);
    try {
      const data = { ...header, branch_id: currentBranch.id, items: validLines };
      const res = await api.post('/purchase-orders', data);
      toast.success(`PO ${res.data.po_number} created!`);
      setLines([{ ...EMPTY_LINE }]);
      setHeader({ vendor: '', branch_id: '', purchase_date: new Date().toISOString().slice(0, 10), notes: '', status: 'ordered', payment_method: 'cash' });
      fetchOrders();
      setTab('list');
    } catch (e) { toast.error(e.response?.data?.detail || 'Error creating PO'); }
    setSaving(false);
  };

  const receivePO = async (poId) => {
    if (!window.confirm('Mark as received? This will add items to inventory.')) return;
    try {
      await api.post(`/purchase-orders/${poId}/receive`);
      toast.success('PO received! Inventory updated.');
      fetchOrders();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  const cancelPO = async (poId) => {
    if (!window.confirm('Cancel this PO?')) return;
    try {
      await api.delete(`/purchase-orders/${poId}`);
      toast.success('PO cancelled');
      fetchOrders();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  const openPay = (po) => {
    setSelectedPO(po);
    setPayForm({ amount: po.balance || po.subtotal, reference: '' });
    setPayDialog(true);
  };

  const handlePay = async () => {
    try {
      await api.post(`/purchase-orders/${selectedPO.id}/pay`, { amount: payForm.amount, reference: payForm.reference });
      toast.success('Payment recorded! Deducted from Cashier Drawer.');
      setPayDialog(false);
      fetchOrders();
    } catch (e) { toast.error(e.response?.data?.detail || 'Payment failed'); }
  };

  const viewDetail = (po) => { setDetailPO(po); setDetailDialog(true); };

  const statusColor = (s) => {
    if (s === 'received') return 'bg-emerald-100 text-emerald-700';
    if (s === 'ordered') return 'bg-blue-100 text-blue-700';
    if (s === 'cancelled') return 'bg-red-100 text-red-700';
    return 'bg-slate-100 text-slate-700';
  };

  return (
    <div className="space-y-5 animate-fadeIn" data-testid="purchase-order-page">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>Purchase Orders</h1>
        <p className="text-sm text-slate-500">Order from suppliers, receive inventory, pay vendors</p>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="create" data-testid="tab-create-po">New PO</TabsTrigger>
          <TabsTrigger value="list" data-testid="tab-list-po">PO List ({totalOrders})</TabsTrigger>
        </TabsList>

        {/* CREATE TAB */}
        <TabsContent value="create" className="mt-4 space-y-4">
          <Card className="border-slate-200">
            <CardContent className="p-5">
              <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
                <div><Label className="text-xs text-slate-500">Vendor Name</Label><Input data-testid="po-vendor" className="h-9" value={header.vendor} onChange={e => setHeader(h => ({ ...h, vendor: e.target.value }))} placeholder="Supplier name" /></div>
                <div><Label className="text-xs text-slate-500">Purchase Date</Label><Input className="h-9" type="date" value={header.purchase_date} onChange={e => setHeader(h => ({ ...h, purchase_date: e.target.value }))} /></div>
                <div>
                  <Label className="text-xs text-slate-500">Payment</Label>
                  <Select value={header.payment_method} onValueChange={v => setHeader(h => ({ ...h, payment_method: v }))}>
                    <SelectTrigger className="h-9" data-testid="po-payment-method"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="cash">Pay in Cash</SelectItem>
                      <SelectItem value="credit">Purchase on Credit</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs text-slate-500">Status</Label>
                  <Select value={header.status} onValueChange={v => setHeader(h => ({ ...h, status: v }))}>
                    <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="draft">Draft</SelectItem>
                      <SelectItem value="ordered">Ordered</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div><Label className="text-xs text-slate-500">Notes</Label><Input className="h-9" value={header.notes} onChange={e => setHeader(h => ({ ...h, notes: e.target.value }))} /></div>
              </div>
              {header.payment_method === 'cash' && (
                <p className="text-xs text-amber-600 mt-2 flex items-center gap-1"><DollarSign size={12} /> Total will be deducted from Cashier Drawer on save</p>
              )}
              {header.payment_method === 'credit' && (
                <p className="text-xs text-blue-600 mt-2">Payable will be created. Pay later from PO list.</p>
              )}
            </CardContent>
          </Card>

          {/* Line Items */}
          <Card className="border-slate-200">
            <CardContent className="p-0">
              <table className="w-full text-sm" data-testid="po-lines-table">
                <thead>
                  <tr className="bg-slate-50 border-b">
                    <th className="text-left px-3 py-2 text-xs uppercase text-slate-500 font-medium w-8">#</th>
                    <th className="text-left px-3 py-2 text-xs uppercase text-slate-500 font-medium min-w-[300px]">Product / Barcode</th>
                    <th className="text-left px-3 py-2 text-xs uppercase text-slate-500 font-medium w-[180px]">Description</th>
                    <th className="text-right px-3 py-2 text-xs uppercase text-slate-500 font-medium w-24">Qty</th>
                    <th className="text-right px-3 py-2 text-xs uppercase text-slate-500 font-medium w-28">Unit Price</th>
                    <th className="text-right px-3 py-2 text-xs uppercase text-slate-500 font-medium w-28">Total</th>
                    <th className="w-10"></th>
                  </tr>
                </thead>
                <tbody>
                  {lines.map((line, i) => (
                    <tr key={i} className="border-b border-slate-100 hover:bg-slate-50/50">
                      <td className="px-3 py-1 text-xs text-slate-400">{i + 1}</td>
                      <td className="px-2 py-1">
                        {line.product_id ? (
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-sm">{line.product_name}</span>
                            <button onClick={() => updateLine(i, 'product_id', '')} className="text-slate-400 hover:text-red-500 text-xs">&times;</button>
                          </div>
                        ) : (
                          <SmartProductSearch branchId={currentBranch?.id} onSelect={(p) => handleProductSelect(i, p)} onCreateNew={handleCreateNewProduct} />
                        )}
                      </td>
                      <td className="px-2 py-1"><input className="w-full h-8 px-2 text-sm border border-transparent hover:border-slate-200 focus:border-[#1A4D2E] focus:outline-none rounded" value={line.description} onChange={e => updateLine(i, 'description', e.target.value)} /></td>
                      <td className="px-2 py-1"><input ref={el => qtyRefs.current[i] = el} type="number" min="0" className="w-full h-8 px-2 text-sm text-right border border-transparent hover:border-slate-200 focus:border-[#1A4D2E] focus:outline-none rounded" value={line.quantity} onChange={e => updateLine(i, 'quantity', parseFloat(e.target.value) || 0)} /></td>
                      <td className="px-2 py-1"><input type="number" className="w-full h-8 px-2 text-sm text-right border border-transparent hover:border-slate-200 focus:border-[#1A4D2E] focus:outline-none rounded" value={line.unit_price} onChange={e => updateLine(i, 'unit_price', parseFloat(e.target.value) || 0)} /></td>
                      <td className="px-3 py-1 text-right font-semibold text-sm">{line.product_id ? formatPHP(line.quantity * line.unit_price) : ''}</td>
                      <td className="px-1 py-1">{lines.length > 1 && line.product_id && <button onClick={() => removeLine(i)} className="text-slate-400 hover:text-red-500 p-1"><Trash2 size={14} /></button>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <div className="flex justify-between items-end">
            <div />
            <div className="w-72 space-y-2">
              <div className="flex justify-between text-lg font-bold" style={{ fontFamily: 'Manrope' }}>
                <span>Total</span><span className="text-[#1A4D2E]">{formatPHP(subtotal)}</span>
              </div>
              <Button data-testid="save-po-btn" onClick={handleSave} disabled={saving} className="w-full bg-[#1A4D2E] hover:bg-[#14532d] text-white">
                <Save size={16} className="mr-2" /> {saving ? 'Saving...' : 'Create Purchase Order'}
              </Button>
            </div>
          </div>
        </TabsContent>

        {/* LIST TAB */}
        <TabsContent value="list" className="mt-4">
          <Card className="border-slate-200">
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow className="bg-slate-50">
                    <TableHead className="text-xs uppercase text-slate-500">PO #</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500">Vendor</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500">Items</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500 text-right">Total</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500">Purchase Date</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500">Payment</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500">Status</TableHead>
                    <TableHead className="w-48">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {orders.map(po => (
                    <TableRow key={po.id} className="table-row-hover">
                      <TableCell className="font-mono text-xs cursor-pointer text-blue-600 hover:underline" onClick={() => viewDetail(po)}>{po.po_number}</TableCell>
                      <TableCell className="font-medium">{po.vendor}</TableCell>
                      <TableCell>{po.items?.length || 0}</TableCell>
                      <TableCell className="text-right font-semibold">{formatPHP(po.subtotal)}</TableCell>
                      <TableCell className="text-xs text-slate-500">{po.purchase_date || po.expected_date || '—'}</TableCell>
                      <TableCell>
                        <Badge className={`text-[10px] ${po.payment_status === 'paid' ? 'bg-emerald-100 text-emerald-700' : po.payment_status === 'partial' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}`}>
                          {po.payment_method === 'credit' ? 'Credit' : 'Cash'} · {po.payment_status || (po.payment_method === 'cash' ? 'paid' : 'unpaid')}
                        </Badge>
                      </TableCell>
                      <TableCell><Badge className={`text-[10px] ${statusColor(po.status)}`}>{po.status}</Badge></TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          {po.status === 'ordered' && (
                            <Button size="sm" variant="outline" onClick={() => receivePO(po.id)} data-testid={`receive-po-${po.id}`}>
                              <Check size={12} className="mr-1" /> Receive
                            </Button>
                          )}
                          {po.status !== 'cancelled' && po.status !== 'received' && (
                            <Button size="sm" variant="ghost" onClick={() => cancelPO(po.id)} className="text-red-500">
                              <X size={12} />
                            </Button>
                          )}
                          {po.payment_status !== 'paid' && po.payment_method === 'credit' && (
                            <Button size="sm" variant="outline" onClick={() => openPay(po)} data-testid={`pay-po-${po.id}`}>
                              <DollarSign size={12} className="mr-1" /> Pay
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                  {!orders.length && <TableRow><TableCell colSpan={8} className="text-center py-8 text-slate-400">No purchase orders yet</TableCell></TableRow>}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Pay Supplier Dialog */}
      <Dialog open={payDialog} onOpenChange={setPayDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Pay Supplier (from Cashier Drawer)</DialogTitle></DialogHeader>
          {selectedPO && (
            <div className="space-y-4 mt-2">
              <div className="p-3 bg-slate-50 rounded-lg text-sm">
                <p>PO: <b>{selectedPO.po_number}</b></p>
                <p>Vendor: <b>{selectedPO.vendor}</b></p>
                <p className="text-lg font-bold mt-1">Balance: {formatPHP(selectedPO.balance || selectedPO.subtotal)}</p>
              </div>
              <div><Label>Amount to Pay</Label><Input data-testid="pay-po-amount" type="number" value={payForm.amount} onChange={e => setPayForm({ ...payForm, amount: parseFloat(e.target.value) || 0 })} className="h-11 text-lg font-bold" /></div>
              <div><Label>Reference (optional)</Label><Input value={payForm.reference} onChange={e => setPayForm({ ...payForm, reference: e.target.value })} placeholder="Check number, receipt, etc." /></div>
              <p className="text-xs text-amber-600 flex items-center gap-1"><DollarSign size={12} /> Will be deducted from Cashier Drawer</p>
              <Button data-testid="confirm-po-payment" onClick={handlePay} className="w-full h-11 bg-[#1A4D2E] hover:bg-[#14532d] text-white">
                Pay {formatPHP(payForm.amount)}
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* PO Detail Dialog */}
      <Dialog open={detailDialog} onOpenChange={setDetailDialog}>
        <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>PO Detail</DialogTitle></DialogHeader>
          {detailPO && (
            <div className="space-y-4 mt-2">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div><span className="text-slate-500">PO #:</span> <span className="font-mono">{detailPO.po_number}</span></div>
                <div><span className="text-slate-500">Vendor:</span> <b>{detailPO.vendor}</b></div>
                <div><span className="text-slate-500">Status:</span> <Badge className={`${statusColor(detailPO.status)} text-[10px]`}>{detailPO.status}</Badge></div>
                <div><span className="text-slate-500">Purchase Date:</span> {detailPO.purchase_date || detailPO.expected_date || '—'}</div>
                <div><span className="text-slate-500">Payment:</span> <Badge className={`text-[10px] ${detailPO.payment_status === 'paid' ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>{detailPO.payment_method === 'credit' ? 'Credit' : 'Cash'} · {detailPO.payment_status || 'n/a'}</Badge></div>
                {detailPO.payment_method === 'credit' && <div><span className="text-slate-500">Balance:</span> <b className="text-red-600">{formatPHP(detailPO.balance)}</b></div>}
              </div>
              <Table>
                <TableHeader><TableRow>
                  <TableHead className="text-xs">Product</TableHead>
                  <TableHead className="text-xs text-right">Qty</TableHead>
                  <TableHead className="text-xs text-right">Price</TableHead>
                  <TableHead className="text-xs text-right">Total</TableHead>
                </TableRow></TableHeader>
                <TableBody>
                  {detailPO.items?.map((item, i) => (
                    <TableRow key={i}>
                      <TableCell className="text-sm">{item.product_name}</TableCell>
                      <TableCell className="text-right">{item.quantity}</TableCell>
                      <TableCell className="text-right">{formatPHP(item.unit_price)}</TableCell>
                      <TableCell className="text-right font-semibold">{formatPHP(item.total)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <div className="flex justify-between text-lg font-bold pt-2 border-t">
                <span>Total</span><span>{formatPHP(detailPO.subtotal)}</span>
              </div>
              {detailPO.notes && <p className="text-sm text-slate-500">Notes: {detailPO.notes}</p>}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Create Product Dialog */}
      <Dialog open={createProductDialog} onOpenChange={setCreateProductDialog}>
        <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Create New Product</DialogTitle></DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="grid grid-cols-2 gap-4">
              <div><Label>SKU</Label><Input value={newProductForm.sku} onChange={e => setNewProductForm(f => ({ ...f, sku: e.target.value }))} placeholder="e.g. LAN-250G" /></div>
              <div><Label>Product Name</Label><Input value={newProductForm.name} onChange={e => setNewProductForm(f => ({ ...f, name: e.target.value }))} /></div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div><Label>Category</Label><Input value={newProductForm.category} onChange={e => setNewProductForm(f => ({ ...f, category: e.target.value }))} /></div>
              <div><Label>Unit</Label><Input value={newProductForm.unit} onChange={e => setNewProductForm(f => ({ ...f, unit: e.target.value }))} /></div>
              <div><Label>Cost Price</Label><Input type="number" value={newProductForm.cost_price} onChange={e => setNewProductForm(f => ({ ...f, cost_price: parseFloat(e.target.value) || 0 }))} /></div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              {schemes.map(s => (
                <div key={s.id}><Label className="text-xs text-slate-500">{s.name}</Label>
                  <Input type="number" value={newProductForm.prices[s.key] || ''} onChange={e => setNewProductForm(f => ({ ...f, prices: { ...f.prices, [s.key]: parseFloat(e.target.value) || 0 } }))} placeholder="0.00" />
                </div>
              ))}
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setCreateProductDialog(false)}>Cancel</Button>
              <Button onClick={saveNewProduct} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">Create Product</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
