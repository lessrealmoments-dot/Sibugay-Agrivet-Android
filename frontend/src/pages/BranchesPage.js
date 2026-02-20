import { useState, useEffect } from 'react';
import { api } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Building2, Plus, Pencil, Trash2, Zap } from 'lucide-react';
import { toast } from 'sonner';
import { BranchCapitalWizard } from '../components/BranchCapitalWizard';

export default function BranchesPage() {
  const [branches, setBranches] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: '', address: '', phone: '' });
  const [wizardBranch, setWizardBranch] = useState(null); // branch to run quick-fill for

  const fetchBranches = async () => {
    try {
      const res = await api.get('/branches');
      setBranches(res.data);
    } catch { toast.error('Failed to load branches'); }
  };

  useEffect(() => { fetchBranches(); }, []);

  const openCreate = () => { setEditing(null); setForm({ name: '', address: '', phone: '' }); setDialogOpen(true); };
  const openEdit = (b) => { setEditing(b); setForm({ name: b.name, address: b.address || '', phone: b.phone || '' }); setDialogOpen(true); };

  const handleSave = async () => {
    try {
      if (editing) {
        await api.put(`/branches/${editing.id}`, form);
        toast.success('Branch updated');
      } else {
        await api.post('/branches', form);
        toast.success('Branch created');
      }
      setDialogOpen(false);
      fetchBranches();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error saving branch'); }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this branch?')) return;
    try {
      await api.delete(`/branches/${id}`);
      toast.success('Branch deleted');
      fetchBranches();
    } catch { toast.error('Failed to delete'); }
  };

  return (
    <div className="space-y-6 animate-fadeIn" data-testid="branches-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>Branches</h1>
          <p className="text-sm text-slate-500 mt-1">Manage your business locations</p>
        </div>
        <Button data-testid="create-branch-btn" onClick={openCreate} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">
          <Plus size={16} className="mr-2" /> Add Branch
        </Button>
      </div>

      <Card className="border-slate-200">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Name</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Address</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Phone</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium w-24">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {branches.map(b => (
                <TableRow key={b.id} className="table-row-hover">
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      <Building2 size={16} className="text-slate-400" strokeWidth={1.5} />
                      {b.name}
                    </div>
                  </TableCell>
                  <TableCell className="text-slate-500">{b.address || '—'}</TableCell>
                  <TableCell className="text-slate-500">{b.phone || '—'}</TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="sm" title="Quick-Fill Capital"
                        data-testid={`quickfill-${b.id}`}
                        onClick={() => setWizardBranch(b)}
                        className="text-amber-600 hover:text-amber-700">
                        <Zap size={14} />
                      </Button>
                      <Button variant="ghost" size="sm" data-testid={`edit-branch-${b.id}`} onClick={() => openEdit(b)}>
                        <Pencil size={14} />
                      </Button>
                      <Button variant="ghost" size="sm" data-testid={`delete-branch-${b.id}`} onClick={() => handleDelete(b.id)} className="text-red-500 hover:text-red-700">
                        <Trash2 size={14} />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {!branches.length && (
                <TableRow><TableCell colSpan={4} className="text-center py-8 text-slate-400">No branches yet</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Manrope' }}>{editing ? 'Edit Branch' : 'New Branch'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div>
              <Label>Branch Name</Label>
              <Input data-testid="branch-name-input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="e.g. Main Branch" />
            </div>
            <div>
              <Label>Address</Label>
              <Input data-testid="branch-address-input" value={form.address} onChange={e => setForm({ ...form, address: e.target.value })} placeholder="Branch address" />
            </div>
            <div>
              <Label>Phone</Label>
              <Input data-testid="branch-phone-input" value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} placeholder="Contact number" />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
              <Button data-testid="save-branch-btn" onClick={handleSave} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">Save</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
