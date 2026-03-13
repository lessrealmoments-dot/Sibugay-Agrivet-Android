import { useState, useEffect } from 'react';
import { ClipboardCheck, Search, RefreshCw, ChevronRight, Package, Check, AlertTriangle, Loader2 } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { toast } from 'sonner';
import { formatPHP } from '../../lib/utils';

const STATUS_COLORS = {
  draft: 'bg-slate-100 text-slate-600',
  ordered: 'bg-blue-100 text-blue-700',
  sent_to_terminal: 'bg-amber-100 text-amber-700',
  received: 'bg-emerald-100 text-emerald-700',
  cancelled: 'bg-red-100 text-red-600',
};

export default function TerminalPOCheck({ api, session, isOnline }) {
  const [pos, setPOs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [selectedPO, setSelectedPO] = useState(null);
  const [items, setItems] = useState([]); // editable items with received qty
  const [saving, setSaving] = useState(false);

  const loadPOs = async () => {
    if (!isOnline) { toast('PO Check requires internet', { duration: 2000 }); return; }
    setLoading(true);
    try {
      const res = await api.get('/purchase-orders', {
        params: { branch_id: session.branchId, status: 'ordered' }
      });
      const list = res.data.purchase_orders || res.data || [];
      setPOs(Array.isArray(list) ? list : []);
    } catch (e) {
      toast.error('Failed to load POs');
    }
    setLoading(false);
  };

  useEffect(() => { if (isOnline) loadPOs(); }, [isOnline]); // eslint-disable-line

  const openPO = (po) => {
    setSelectedPO(po);
    setItems((po.items || []).map(item => ({
      ...item,
      qty_received: item.quantity, // default: received = ordered
      has_variance: false,
    })));
  };

  const updateReceivedQty = (idx, val) => {
    setItems(prev => prev.map((item, i) => {
      if (i !== idx) return item;
      const qty = parseFloat(val) || 0;
      return { ...item, qty_received: qty, has_variance: qty !== item.quantity };
    }));
  };

  const hasVariance = items.some(i => i.has_variance);

  const finalizePO = async () => {
    if (!selectedPO) return;
    setSaving(true);
    try {
      // Update PO items with received quantities
      const updatedItems = items.map(i => ({
        product_id: i.product_id,
        product_name: i.product_name,
        quantity: i.qty_received, // use received qty
        unit_price: i.unit_price,
        unit: i.unit,
        original_ordered: i.quantity,
      }));

      await api.put(`/purchase-orders/${selectedPO.id}`, {
        items: updatedItems,
        terminal_verified: true,
        terminal_id: session.terminalId,
        verified_at: new Date().toISOString(),
      });

      toast.success(`PO ${selectedPO.po_number || ''} updated`);
      setSelectedPO(null);
      loadPOs();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to update PO');
    }
    setSaving(false);
  };

  const filteredPOs = search
    ? pos.filter(p => (p.po_number || '').toLowerCase().includes(search.toLowerCase()) ||
        (p.vendor || '').toLowerCase().includes(search.toLowerCase()))
    : pos;

  return (
    <div className="flex flex-col h-full" data-testid="terminal-po-check">
      {/* Header */}
      <div className="p-3 bg-white border-b border-slate-200">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-base font-bold text-slate-800">Purchase Order Check</h2>
          <Button variant="outline" size="sm" onClick={loadPOs} disabled={loading || !isOnline}>
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </Button>
        </div>
        <Input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search PO # or vendor..."
          className="h-9"
          data-testid="po-search-input"
        />
      </div>

      {/* PO List */}
      <div className="flex-1 overflow-auto p-3">
        {!isOnline ? (
          <div className="text-center py-12 text-slate-400">
            <AlertTriangle size={28} className="mx-auto mb-2 opacity-40" />
            <p className="text-sm">PO Check requires internet connection</p>
          </div>
        ) : loading ? (
          <div className="text-center py-12">
            <Loader2 size={24} className="animate-spin mx-auto text-slate-400" />
          </div>
        ) : filteredPOs.length === 0 ? (
          <div className="text-center py-12 text-slate-400">
            <ClipboardCheck size={28} className="mx-auto mb-2 opacity-40" />
            <p className="text-sm">No pending POs for this branch</p>
          </div>
        ) : (
          <div className="space-y-2">
            {filteredPOs.map(po => (
              <button
                key={po.id}
                onClick={() => openPO(po)}
                className="w-full bg-white rounded-xl border border-slate-200 p-3 text-left hover:border-emerald-300 transition-colors"
                data-testid={`po-item-${po.id}`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-bold text-slate-800">{po.po_number || 'No #'}</span>
                  <Badge className={STATUS_COLORS[po.status] || 'bg-slate-100'}>{po.status}</Badge>
                </div>
                <p className="text-xs text-slate-500">{po.vendor || 'Unknown vendor'}</p>
                <div className="flex items-center justify-between mt-2">
                  <span className="text-xs text-slate-400">{(po.items || []).length} items</span>
                  <span className="text-sm font-bold text-[#1A4D2E]">{formatPHP(po.grand_total || 0)}</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* PO Detail Dialog */}
      <Dialog open={!!selectedPO} onOpenChange={(open) => { if (!open) setSelectedPO(null); }}>
        <DialogContent className="max-w-lg mx-auto max-h-[90vh] overflow-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Package size={18} />
              {selectedPO?.po_number || 'PO Check'}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <p className="text-xs text-slate-500">Vendor: {selectedPO?.vendor || '—'}</p>

            {/* Items checklist */}
            <div className="space-y-2">
              {items.map((item, idx) => (
                <div key={idx} className={`p-3 rounded-xl border ${item.has_variance ? 'border-amber-300 bg-amber-50' : 'border-slate-200 bg-white'}`}>
                  <div className="flex items-center justify-between mb-1.5">
                    <p className="text-sm font-medium text-slate-800 truncate max-w-[65%]">{item.product_name}</p>
                    <p className="text-xs text-slate-500">{formatPHP(item.unit_price || 0)}/ea</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-xs text-slate-500">
                      Ordered: <strong>{item.quantity}</strong>
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-1.5">
                        <label className="text-xs text-slate-500 whitespace-nowrap">Received:</label>
                        <Input
                          type="number"
                          value={item.qty_received}
                          onChange={e => updateReceivedQty(idx, e.target.value)}
                          className="h-8 text-sm w-20"
                          data-testid={`po-qty-${idx}`}
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

            {hasVariance && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-2 text-xs text-amber-700">
                Some quantities don't match. The PO will be updated with received quantities.
              </div>
            )}

            <Button
              onClick={finalizePO}
              disabled={saving}
              className="w-full bg-[#1A4D2E] hover:bg-[#15412a] text-white h-11"
              data-testid="finalize-po-btn"
            >
              {saving ? <Loader2 size={16} className="animate-spin mr-2" /> : <Check size={16} className="mr-2" />}
              {saving ? 'Updating...' : 'Finalize PO Check'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
