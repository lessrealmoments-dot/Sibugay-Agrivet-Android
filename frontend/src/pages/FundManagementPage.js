import { useState, useEffect } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Wallet, Plus, ArrowRightLeft, Landmark, Lock, Banknote } from 'lucide-react';
import { toast } from 'sonner';

export default function FundManagementPage() {
  const { currentBranch, branches } = useAuth();
  const [wallets, setWallets] = useState([]);
  const [safeLots, setSafeLots] = useState([]);
  const [createDialog, setCreateDialog] = useState(false);
  const [depositDialog, setDepositDialog] = useState(false);
  const [transferDialog, setTransferDialog] = useState(false);
  const [selectedWallet, setSelectedWallet] = useState(null);
  const [createForm, setCreateForm] = useState({ type: 'cashier', name: '', bank_name: '', account_number: '', balance: 0 });
  const [depositForm, setDepositForm] = useState({ amount: 0, reference: '', date: new Date().toISOString().slice(0, 10) });
  const [transferForm, setTransferForm] = useState({ from_wallet_id: '', to_wallet_id: '', amount: 0, reference: '' });

  const fetchWallets = async () => {
    try {
      const res = await api.get('/fund-wallets', { params: { branch_id: currentBranch?.id } });
      setWallets(res.data);
    } catch { toast.error('Failed to load wallets'); }
  };

  const fetchSafeLots = async () => {
    try {
      const res = await api.get('/safe-lots', { params: { branch_id: currentBranch?.id } });
      setSafeLots(res.data);
    } catch {}
  };

  useEffect(() => { if (currentBranch) { fetchWallets(); fetchSafeLots(); } }, [currentBranch]);

  const handleCreate = async () => {
    try {
      await api.post('/fund-wallets', { ...createForm, branch_id: currentBranch?.id });
      toast.success('Wallet created'); setCreateDialog(false); fetchWallets();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  const handleDeposit = async () => {
    try {
      await api.post(`/fund-wallets/${selectedWallet.id}/deposit`, depositForm);
      toast.success('Deposit recorded'); setDepositDialog(false); fetchWallets(); fetchSafeLots();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  const openDeposit = (w) => { setSelectedWallet(w); setDepositForm({ amount: 0, reference: '', date: new Date().toISOString().slice(0, 10) }); setDepositDialog(true); };

  const getIcon = (type) => {
    if (type === 'cashier') return <Banknote size={20} className="text-emerald-600" />;
    if (type === 'safe') return <Lock size={20} className="text-amber-600" />;
    return <Landmark size={20} className="text-blue-600" />;
  };

  const totalBalance = wallets.reduce((s, w) => s + (w.balance || 0), 0);

  return (
    <div className="space-y-6 animate-fadeIn" data-testid="fund-management-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>Fund Management</h1>
          <p className="text-sm text-slate-500">Cashier Drawer, Safe & Bank — {currentBranch?.name}</p>
        </div>
        <Button data-testid="create-wallet-btn" onClick={() => { setCreateForm({ type: 'cashier', name: '', bank_name: '', account_number: '', balance: 0 }); setCreateDialog(true); }} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">
          <Plus size={16} className="mr-2" /> Add Wallet
        </Button>
      </div>

      {/* Total Balance */}
      <Card className="border-slate-200 bg-white">
        <CardContent className="p-5">
          <p className="text-xs text-slate-500 uppercase font-medium">Total Funds ({currentBranch?.name})</p>
          <p className="text-3xl font-bold mt-1" style={{ fontFamily: 'Manrope' }}>{formatPHP(totalBalance)}</p>
        </CardContent>
      </Card>

      {/* Wallet Cards */}
      <div className="grid md:grid-cols-3 gap-4">
        {wallets.map(w => (
          <Card key={w.id} className="border-slate-200 hover:border-[#1A4D2E]/30 transition-colors">
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  {getIcon(w.type)}
                  <div>
                    <p className="font-semibold text-sm">{w.name}</p>
                    <p className="text-[11px] text-slate-400 capitalize">{w.type}{w.bank_name ? ` — ${w.bank_name}` : ''}</p>
                  </div>
                </div>
                <Badge variant="outline" className="text-[10px] capitalize">{w.type}</Badge>
              </div>
              <p className="text-2xl font-bold" style={{ fontFamily: 'Manrope' }}>{formatPHP(w.balance)}</p>
              {w.type === 'safe' && w.lots && (
                <p className="text-[11px] text-slate-400 mt-1">{w.lots.length} active cash lot{w.lots.length !== 1 ? 's' : ''}</p>
              )}
              <Button variant="outline" size="sm" className="mt-3 w-full" onClick={() => openDeposit(w)}>
                <Plus size={12} className="mr-1" /> Deposit
              </Button>
            </CardContent>
          </Card>
        ))}
        {!wallets.length && (
          <p className="col-span-3 text-center py-8 text-slate-400">No wallets set up. Create Cashier Drawer, Safe, and Bank accounts.</p>
        )}
      </div>

      {/* Safe Lots */}
      {safeLots.length > 0 && (
        <Card className="border-slate-200">
          <CardHeader className="pb-3"><CardTitle className="text-base font-semibold" style={{ fontFamily: 'Manrope' }}>Safe Cash Lots</CardTitle></CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader><TableRow className="bg-slate-50">
                <TableHead className="text-xs uppercase text-slate-500">Date</TableHead>
                <TableHead className="text-xs uppercase text-slate-500 text-right">Original</TableHead>
                <TableHead className="text-xs uppercase text-slate-500 text-right">Remaining</TableHead>
                <TableHead className="text-xs uppercase text-slate-500">Source</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {safeLots.map(lot => (
                  <TableRow key={lot.id}>
                    <TableCell className="text-sm">{lot.date_received}</TableCell>
                    <TableCell className="text-right">{formatPHP(lot.original_amount)}</TableCell>
                    <TableCell className="text-right font-semibold">{formatPHP(lot.remaining_amount)}</TableCell>
                    <TableCell className="text-xs text-slate-500">{lot.source_reference}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Create Wallet Dialog */}
      <Dialog open={createDialog} onOpenChange={setCreateDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Create Wallet</DialogTitle></DialogHeader>
          <div className="space-y-4 mt-2">
            <div>
              <Label>Type</Label>
              <Select value={createForm.type} onValueChange={v => setCreateForm({ ...createForm, type: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="cashier">Cashier Drawer</SelectItem>
                  <SelectItem value="safe">Safe</SelectItem>
                  <SelectItem value="bank">Bank Account</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div><Label>Name</Label><Input value={createForm.name} onChange={e => setCreateForm({ ...createForm, name: e.target.value })} placeholder="e.g. Main Cashier" /></div>
            {createForm.type === 'bank' && (
              <>
                <div><Label>Bank Name</Label><Input value={createForm.bank_name} onChange={e => setCreateForm({ ...createForm, bank_name: e.target.value })} /></div>
                <div><Label>Account #</Label><Input value={createForm.account_number} onChange={e => setCreateForm({ ...createForm, account_number: e.target.value })} /></div>
              </>
            )}
            {createForm.type !== 'safe' && (
              <div><Label>Starting Balance</Label><Input type="number" value={createForm.balance} onChange={e => setCreateForm({ ...createForm, balance: parseFloat(e.target.value) || 0 })} /></div>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setCreateDialog(false)}>Cancel</Button>
              <Button onClick={handleCreate} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">Create</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Deposit Dialog */}
      <Dialog open={depositDialog} onOpenChange={setDepositDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Deposit to {selectedWallet?.name}</DialogTitle></DialogHeader>
          <div className="space-y-4 mt-2">
            <div><Label>Amount</Label><Input type="number" value={depositForm.amount} onChange={e => setDepositForm({ ...depositForm, amount: parseFloat(e.target.value) || 0 })} className="h-11 text-lg font-bold" /></div>
            <div><Label>Reference</Label><Input value={depositForm.reference} onChange={e => setDepositForm({ ...depositForm, reference: e.target.value })} placeholder="e.g. Daily sales deposit" /></div>
            <div><Label>Date</Label><Input type="date" value={depositForm.date} onChange={e => setDepositForm({ ...depositForm, date: e.target.value })} /></div>
            <Button onClick={handleDeposit} className="w-full bg-[#1A4D2E] hover:bg-[#14532d] text-white">Deposit {formatPHP(depositForm.amount)}</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
