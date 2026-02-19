import { useState, useEffect, useCallback } from 'react';
import { api } from '../contexts/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Users, Plus, Pencil, Trash2, Search } from 'lucide-react';
import { toast } from 'sonner';

export default function CustomersPage() {
  const [customers, setCustomers] = useState([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [schemes, setSchemes] = useState([]);
  const LIMIT = 20;
  const [form, setForm] = useState({ name: '', phone: '', email: '', address: '', price_scheme: 'retail', credit_limit: 0 });

  const fetchCustomers = useCallback(async () => {
    try {
      const params = { skip: page * LIMIT, limit: LIMIT };
      if (search) params.search = search;
      const res = await api.get('/customers', { params });
      setCustomers(res.data.customers);
      setTotal(res.data.total);
    } catch { toast.error('Failed to load customers'); }
  }, [search, page]);

  useEffect(() => { fetchCustomers(); }, [fetchCustomers]);
  useEffect(() => { api.get('/price-schemes').then(r => setSchemes(r.data)).catch(() => {}); }, []);

  const openCreate = () => { setEditing(null); setForm({ name: '', phone: '', email: '', address: '', price_scheme: 'retail', credit_limit: 0 }); setDialogOpen(true); };
  const openEdit = (c) => { setEditing(c); setForm({ name: c.name, phone: c.phone || '', email: c.email || '', address: c.address || '', price_scheme: c.price_scheme || 'retail', credit_limit: c.credit_limit || 0 }); setDialogOpen(true); };

  const handleSave = async () => {
    try {
      if (editing) { await api.put(`/customers/${editing.id}`, form); toast.success('Customer updated'); }
      else { await api.post('/customers', form); toast.success('Customer created'); }
      setDialogOpen(false); fetchCustomers();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error saving customer'); }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this customer?')) return;
    try { await api.delete(`/customers/${id}`); toast.success('Customer deleted'); fetchCustomers(); }
    catch { toast.error('Failed to delete'); }
  };

  return (
    <div className="space-y-6 animate-fadeIn" data-testid="customers-page">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>Customers</h1>
          <p className="text-sm text-slate-500 mt-1">{total} customers with price scheme assignment</p>
        </div>
        <Button data-testid="create-customer-btn" onClick={openCreate} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">
          <Plus size={16} className="mr-2" /> Add Customer
        </Button>
      </div>

      <div className="relative max-w-sm">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <Input data-testid="customer-search" value={search} onChange={e => { setSearch(e.target.value); setPage(0); }} placeholder="Search by name or phone..." className="pl-9 h-10" />
      </div>

      <Card className="border-slate-200">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Name</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Phone</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Price Scheme</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium text-right">Balance</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium text-right">Credit Limit</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium w-24">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {customers.map(c => (
                <TableRow key={c.id} className="table-row-hover">
                  <TableCell className="font-medium">{c.name}</TableCell>
                  <TableCell className="text-slate-500">{c.phone || '—'}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-[10px] capitalize">{c.price_scheme}</Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <span className={c.balance > 0 ? 'text-red-600 font-semibold' : ''}>{(c.balance || 0).toFixed(2)}</span>
                  </TableCell>
                  <TableCell className="text-right">{(c.credit_limit || 0).toFixed(2)}</TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="sm" data-testid={`edit-customer-${c.id}`} onClick={() => openEdit(c)}><Pencil size={14} /></Button>
                      <Button variant="ghost" size="sm" data-testid={`delete-customer-${c.id}`} onClick={() => handleDelete(c.id)} className="text-red-500"><Trash2 size={14} /></Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {!customers.length && (
                <TableRow><TableCell colSpan={6} className="text-center py-8 text-slate-400">No customers yet</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>{editing ? 'Edit Customer' : 'New Customer'}</DialogTitle></DialogHeader>
          <div className="space-y-4 mt-2">
            <div>
              <Label>Customer Name</Label>
              <Input data-testid="customer-name-input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div><Label>Phone</Label><Input data-testid="customer-phone-input" value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} /></div>
              <div><Label>Email</Label><Input value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} /></div>
            </div>
            <div><Label>Address</Label><Input value={form.address} onChange={e => setForm({ ...form, address: e.target.value })} /></div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Price Scheme</Label>
                <Select value={form.price_scheme} onValueChange={v => setForm({ ...form, price_scheme: v })}>
                  <SelectTrigger data-testid="customer-scheme-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {schemes.map(s => <SelectItem key={s.id} value={s.key}>{s.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Credit Limit</Label>
                <Input data-testid="customer-credit-input" type="number" value={form.credit_limit} onChange={e => setForm({ ...form, credit_limit: parseFloat(e.target.value) || 0 })} />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
              <Button data-testid="save-customer-btn" onClick={handleSave} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">Save</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
