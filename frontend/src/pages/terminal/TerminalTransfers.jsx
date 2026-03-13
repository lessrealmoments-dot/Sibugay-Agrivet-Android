import { useState, useEffect, useCallback } from 'react';
import { ArrowLeftRight, Search, RefreshCw, Check, AlertTriangle, Loader2, Package, ArrowRight } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { toast } from 'sonner';
import { formatPHP } from '../../lib/utils';

const STATUS_COLORS = {
  draft: 'bg-slate-100 text-slate-600',
  sent: 'bg-blue-100 text-blue-700',
  received_pending: 'bg-amber-100 text-amber-700',
  received: 'bg-emerald-100 text-emerald-700',
  disputed: 'bg-red-100 text-red-700',
};

export default function TerminalTransfers({ api, session, isOnline, onRefreshRef }) {
  const [transfers, setTransfers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [selectedTransfer, setSelectedTransfer] = useState(null);
  const [items, setItems] = useState([]);
  const [saving, setSaving] = useState(false);

  const loadTransfers = useCallback(async () => {
    if (!isOnline) { toast('Transfers require internet', { duration: 2000 }); return; }
    setLoading(true);
    try {
      // Get transfers where this branch is the destination
      const res = await api.get('/branch-transfers', {
        params: { to_branch_id: session.branchId, status: 'sent' }
      });
      const list = res.data.orders || res.data || [];
      setTransfers(Array.isArray(list) ? list : []);
    } catch {
      toast.error('Failed to load transfers');
    }
    setLoading(false);
  }, [api, session.branchId, isOnline]);

  useEffect(() => { if (isOnline) loadTransfers(); }, [isOnline, loadTransfers]);

  // Expose refresh callback to parent for WebSocket notifications
  useEffect(() => {
    if (onRefreshRef) onRefreshRef.current = loadTransfers;
  }, [onRefreshRef, loadTransfers]);

  const openTransfer = (transfer) => {
    setSelectedTransfer(transfer);
    setItems((transfer.items || []).map(item => ({
      ...item,
      qty_received: item.qty,
      has_variance: false,
    })));
  };

  const updateReceivedQty = (idx, val) => {
    setItems(prev => prev.map((item, i) => {
      if (i !== idx) return item;
      const qty = parseFloat(val) || 0;
      return { ...item, qty_received: qty, has_variance: qty !== item.qty };
    }));
  };

  const receiveTransfer = async () => {
    if (!selectedTransfer) return;
    setSaving(true);
    try {
      const receivedItems = items.map(i => ({
        product_id: i.product_id,
        qty_received: i.qty_received,
        qty: i.qty,
      }));

      await api.post(`/branch-transfers/${selectedTransfer.id}/receive`, {
        items: receivedItems,
        skip_receipt_check: true, // Terminal doesn't do receipt upload yet
        terminal_id: session.terminalId,
      });

      toast.success('Transfer received!');
      setSelectedTransfer(null);
      loadTransfers();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to receive transfer');
    }
    setSaving(false);
  };

  const filteredTransfers = search
    ? transfers.filter(t =>
        (t.transfer_number || '').toLowerCase().includes(search.toLowerCase()) ||
        (t.from_branch_name || '').toLowerCase().includes(search.toLowerCase()))
    : transfers;

  return (
    <div className="flex flex-col h-full" data-testid="terminal-transfers">
      {/* Header */}
      <div className="p-3 bg-white border-b border-slate-200">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-base font-bold text-slate-800">Pending Transfers</h2>
          <Button variant="outline" size="sm" onClick={loadTransfers} disabled={loading || !isOnline}>
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </Button>
        </div>
        <Input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search transfer # or branch..."
          className="h-9"
          data-testid="transfer-search-input"
        />
      </div>

      {/* Transfer List */}
      <div className="flex-1 overflow-auto p-3">
        {!isOnline ? (
          <div className="text-center py-12 text-slate-400">
            <AlertTriangle size={28} className="mx-auto mb-2 opacity-40" />
            <p className="text-sm">Transfers require internet connection</p>
          </div>
        ) : loading ? (
          <div className="text-center py-12">
            <Loader2 size={24} className="animate-spin mx-auto text-slate-400" />
          </div>
        ) : filteredTransfers.length === 0 ? (
          <div className="text-center py-12 text-slate-400">
            <ArrowLeftRight size={28} className="mx-auto mb-2 opacity-40" />
            <p className="text-sm">No pending transfers for this branch</p>
          </div>
        ) : (
          <div className="space-y-2">
            {filteredTransfers.map(t => (
              <button
                key={t.id}
                onClick={() => openTransfer(t)}
                className="w-full bg-white rounded-xl border border-slate-200 p-3 text-left hover:border-emerald-300 transition-colors"
                data-testid={`transfer-item-${t.id}`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-bold text-slate-800">{t.transfer_number || 'Transfer'}</span>
                  <Badge className={STATUS_COLORS[t.status] || 'bg-slate-100'}>{t.status}</Badge>
                </div>
                <div className="flex items-center gap-1 text-xs text-slate-500">
                  <span>{t.from_branch_name || 'Source'}</span>
                  <ArrowRight size={12} />
                  <span>{t.to_branch_name || session.branchName}</span>
                </div>
                <div className="flex items-center justify-between mt-2">
                  <span className="text-xs text-slate-400">{(t.items || []).length} items</span>
                  <span className="text-xs text-slate-400">{t.created_at?.slice(0, 10) || ''}</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Transfer Detail Dialog */}
      <Dialog open={!!selectedTransfer} onOpenChange={(open) => { if (!open) setSelectedTransfer(null); }}>
        <DialogContent className="max-w-lg mx-auto max-h-[90vh] overflow-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Package size={18} />
              {selectedTransfer?.transfer_number || 'Receive Transfer'}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <p className="text-xs text-slate-500">
              From: {selectedTransfer?.from_branch_name || '—'}
            </p>

            {/* Items */}
            <div className="space-y-2">
              {items.map((item, idx) => (
                <div key={idx} className={`p-3 rounded-xl border ${item.has_variance ? 'border-amber-300 bg-amber-50' : 'border-slate-200 bg-white'}`}>
                  <div className="flex items-center justify-between mb-1.5">
                    <p className="text-sm font-medium text-slate-800 truncate max-w-[65%]">{item.product_name}</p>
                    <p className="text-xs text-slate-500">{item.sku || ''}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-xs text-slate-500">
                      Sent: <strong>{item.qty}</strong>
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-1.5">
                        <label className="text-xs text-slate-500 whitespace-nowrap">Received:</label>
                        <Input
                          type="number"
                          value={item.qty_received}
                          onChange={e => updateReceivedQty(idx, e.target.value)}
                          className="h-8 text-sm w-20"
                          data-testid={`transfer-qty-${idx}`}
                        />
                      </div>
                    </div>
                    {item.has_variance ? (
                      <AlertTriangle size={16} className="text-amber-500 flex-shrink-0" />
                    ) : (
                      <Check size={16} className="text-emerald-500 flex-shrink-0" />
                    )}
                  </div>
                </div>
              ))}
            </div>

            <Button
              onClick={receiveTransfer}
              disabled={saving}
              className="w-full bg-[#1A4D2E] hover:bg-[#15412a] text-white h-11"
              data-testid="receive-transfer-btn"
            >
              {saving ? <Loader2 size={16} className="animate-spin mr-2" /> : <Check size={16} className="mr-2" />}
              {saving ? 'Processing...' : 'Receive Transfer'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
