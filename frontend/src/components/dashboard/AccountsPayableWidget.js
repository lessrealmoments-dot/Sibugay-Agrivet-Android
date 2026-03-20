import { useState, useEffect, useCallback } from 'react';
import { api } from '../../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { ScrollArea } from '../ui/scroll-area';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';
import { formatPHP } from '../../lib/utils';
import ViewQRDialog from '../ViewQRDialog';
import {
  FileText, AlertTriangle, Clock, ChevronRight, RefreshCw, User, Building2,
  CalendarDays, Package, Camera, Receipt, Shield, CheckCircle2, ShieldCheck,
  ExternalLink, QrCode
} from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

function PODetailDialog({ poId, open, onClose }) {
  const navigate = useNavigate();
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [receiptFiles, setReceiptFiles] = useState([]);
  const [reviewPin, setReviewPin] = useState('');
  const [reviewNotes, setReviewNotes] = useState('');
  const [reviewSaving, setReviewSaving] = useState(false);
  const [viewQROpen, setViewQROpen] = useState(false);

  useEffect(() => {
    if (open && poId) {
      setLoading(true);
      setDetail(null);
      setReviewPin('');
      setReviewNotes('');
      api.get(`/dashboard/review-detail/purchase_order/${poId}`)
        .then(res => {
          setDetail(res.data);
          setReceiptFiles(res.data.receipt_files || []);
        })
        .catch(() => toast.error('Failed to load PO details'))
        .finally(() => setLoading(false));
    }
  }, [open, poId]);

  const handleMarkReviewed = async () => {
    if (!reviewPin) { toast.error('Enter admin PIN, auditor PIN, or TOTP'); return; }
    setReviewSaving(true);
    try {
      await api.post(`/purchase-orders/${poId}/mark-reviewed`, { pin: reviewPin, notes: reviewNotes });
      toast.success('Receipts marked as reviewed');
      setDetail(prev => prev ? { ...prev, receipt_review_status: 'reviewed' } : prev);
      setReviewPin('');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Review failed');
    }
    setReviewSaving(false);
  };

  const d = detail;

  return (
    <>
      <Dialog open={open} onOpenChange={v => { if (!v) onClose(); }}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
              <FileText size={18} className="text-blue-600" />
              {d?.record_number || 'Loading...'}
            </DialogTitle>
          </DialogHeader>

          <ScrollArea className="flex-1 -mx-6 px-6">
            <div className="space-y-4 pb-2">
              {loading ? (
                <div className="flex items-center justify-center py-8 text-slate-400 text-sm">
                  <RefreshCw size={14} className="animate-spin mr-2" /> Loading...
                </div>
              ) : d ? (
                <>
                  {/* Header info */}
                  <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 space-y-2">
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="text-sm font-bold text-slate-800">{d.record_number}</p>
                        <div className="flex items-center gap-1.5 mt-1">
                          <User size={11} className="text-blue-600" />
                          <span className="text-xs font-semibold text-blue-800">{d.supplier}</span>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-lg font-bold font-mono text-slate-800">{formatPHP(d.grand_total)}</p>
                        <Badge className={`text-[9px] ${
                          d.payment_status === 'paid' ? 'bg-emerald-100 text-emerald-700' :
                          d.payment_status === 'partial' ? 'bg-amber-100 text-amber-700' :
                          'bg-red-100 text-red-700'
                        }`}>
                          {d.payment_status === 'paid' ? 'Paid' : d.payment_status === 'partial' ? `Partial (${formatPHP(d.total_paid)})` : `Unpaid — ${formatPHP(d.balance)} due`}
                        </Badge>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-slate-500 pt-1 border-t border-blue-100">
                      <span className="flex items-center gap-1"><Building2 size={10} /> {d.branch_name}</span>
                      <span className="flex items-center gap-1"><CalendarDays size={10} /> Date: {d.date?.slice(0, 10)}</span>
                      {d.due_date && <span className="flex items-center gap-1"><Clock size={10} /> Due: {d.due_date.slice(0, 10)}</span>}
                      <span>Status: <Badge className="text-[9px] bg-slate-200 text-slate-600">{d.status}</Badge></span>
                    </div>
                    {/* Verification badge */}
                    {d.verified && (
                      <div className="flex items-center gap-1.5 text-[10px] text-emerald-600 bg-emerald-50 rounded-lg px-2 py-1">
                        <ShieldCheck size={11} /> Verified by {d.verified_by} {d.verified_at ? `on ${d.verified_at.slice(0, 10)}` : ''}
                      </div>
                    )}
                    {/* Review badge */}
                    {d.receipt_review_status === 'reviewed' && (
                      <div className="flex items-center gap-1.5 text-[10px] text-emerald-600 bg-emerald-50 rounded-lg px-2 py-1">
                        <CheckCircle2 size={11} /> Receipts reviewed{d.receipt_reviewed_by ? ` by ${d.receipt_reviewed_by}` : ''}
                      </div>
                    )}
                  </div>

                  {/* Items */}
                  {d.items?.length > 0 && (
                    <div className="bg-white border rounded-xl overflow-hidden">
                      <div className="px-3 py-2 bg-slate-50 border-b flex items-center gap-2">
                        <Package size={13} className="text-slate-500" />
                        <span className="text-xs font-semibold text-slate-700">Items ({d.items.length})</span>
                      </div>
                      <Table>
                        <TableHeader>
                          <TableRow className="bg-slate-50/50">
                            <TableHead className="text-[10px] uppercase text-slate-500">Product</TableHead>
                            <TableHead className="text-[10px] uppercase text-slate-500 text-right">Qty</TableHead>
                            <TableHead className="text-[10px] uppercase text-slate-500 text-right">Price</TableHead>
                            <TableHead className="text-[10px] uppercase text-slate-500 text-right">Total</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {d.items.map((item, idx) => (
                            <TableRow key={idx} className="hover:bg-slate-50/50">
                              <TableCell className="text-xs">
                                <span className="font-medium">{item.product_name}</span>
                                {item.sku && <span className="text-[10px] text-slate-400 ml-1">({item.sku})</span>}
                              </TableCell>
                              <TableCell className="text-xs text-right font-mono">{item.quantity}{item.unit ? ` ${item.unit}` : ''}</TableCell>
                              <TableCell className="text-xs text-right font-mono">{formatPHP(item.unit_price)}</TableCell>
                              <TableCell className="text-xs text-right font-mono font-semibold">{formatPHP(item.total)}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  )}

                  {/* Receipt photos */}
                  {receiptFiles.length > 0 && (
                    <div className="bg-white border rounded-xl overflow-hidden">
                      <div className="px-3 py-2 bg-slate-50 border-b flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Camera size={13} className="text-slate-500" />
                          <span className="text-xs font-semibold text-slate-700">Receipt Photos ({receiptFiles.length})</span>
                        </div>
                        <Button variant="outline" size="sm" className="h-6 text-[10px] px-2"
                          onClick={() => setViewQROpen(true)} data-testid="ap-view-phone-btn">
                          <QrCode size={10} className="mr-1" /> View on Phone
                        </Button>
                      </div>
                      <div className="p-3 flex flex-wrap gap-2">
                        {receiptFiles.map((f, i) => {
                          const isImage = (f.content_type || '').startsWith('image/');
                          const url = `${BACKEND_URL}/api/uploads/file/purchase_order/${poId}/${f.id}`;
                          return (
                            <a key={f.id || i} href={url} target="_blank" rel="noopener noreferrer"
                              className="block rounded-lg border border-slate-200 overflow-hidden hover:shadow-md transition-shadow">
                              {isImage ? (
                                <img src={url} alt={f.filename} className="w-24 h-24 object-cover" />
                              ) : (
                                <div className="w-24 h-24 bg-slate-50 flex flex-col items-center justify-center">
                                  <Receipt size={18} className="text-slate-400" />
                                  <span className="text-[8px] text-slate-400 mt-1 truncate max-w-[80px]">{f.filename}</span>
                                </div>
                              )}
                            </a>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Review section — only if NOT yet reviewed */}
                  {d.receipt_review_status !== 'reviewed' && receiptFiles.length > 0 && (
                    <div className="space-y-3 bg-amber-50 border border-amber-200 rounded-xl p-4">
                      <p className="text-xs font-semibold text-amber-700 flex items-center gap-1.5">
                        <AlertTriangle size={12} /> Receipts pending review
                      </p>
                      <Input
                        value={reviewNotes}
                        onChange={e => setReviewNotes(e.target.value)}
                        placeholder="Review notes (optional)"
                        className="h-9 text-sm bg-white"
                      />
                      <div>
                        <label className="text-[10px] text-slate-500 font-medium flex items-center gap-1 mb-1">
                          <Shield size={10} className="text-amber-500" /> Admin PIN, Auditor PIN, or TOTP
                        </label>
                        <Input
                          type="password" autoComplete="new-password"
                          value={reviewPin}
                          onChange={e => setReviewPin(e.target.value)}
                          onKeyDown={e => { if (e.key === 'Enter') handleMarkReviewed(); }}
                          placeholder="Enter PIN"
                          className="h-9 text-sm font-mono bg-white"
                          data-testid="ap-review-pin"
                        />
                      </div>
                      <Button size="sm" onClick={handleMarkReviewed} disabled={reviewSaving || !reviewPin}
                        className="bg-[#1A4D2E] hover:bg-[#14532d] text-white w-full"
                        data-testid="ap-mark-reviewed-btn">
                        {reviewSaving ? <RefreshCw size={12} className="animate-spin mr-1" /> : <CheckCircle2 size={12} className="mr-1" />}
                        Mark as Reviewed
                      </Button>
                    </div>
                  )}
                </>
              ) : null}
            </div>
          </ScrollArea>

          {/* Footer */}
          <div className="flex justify-between items-center pt-3 border-t -mx-6 px-6">
            <Button variant="ghost" size="sm" onClick={() => { onClose(); navigate(`/purchase-orders?open=${poId}`); }}
              className="text-xs text-slate-500 hover:text-[#1A4D2E]">
              <ExternalLink size={12} className="mr-1" /> Open Full Page
            </Button>
            <Button variant="outline" size="sm" onClick={onClose}>Close</Button>
          </div>
        </DialogContent>
      </Dialog>

      <ViewQRDialog
        open={viewQROpen}
        onClose={() => setViewQROpen(false)}
        recordType="purchase_order"
        recordId={poId}
        fileCount={receiptFiles.length}
      />
    </>
  );
}

export default function AccountsPayableWidget({ branchId }) {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedPO, setSelectedPO] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (branchId && branchId !== 'all') params.branch_id = branchId;
      const res = await api.get('/dashboard/accounts-payable', { params });
      setData(res.data);
    } catch {}
    setLoading(false);
  }, [branchId]);

  useEffect(() => { load(); }, [load]);

  if (loading) return (
    <Card className="border-slate-200 h-full" data-testid="ap-widget">
      <CardContent className="flex items-center justify-center h-40"><RefreshCw size={16} className="animate-spin text-slate-400" /></CardContent>
    </Card>
  );

  const d = data || {};
  const hasOverdue = d.overdue_count > 0;

  const PORow = ({ po, variant }) => (
    <div key={po.po_id} className={`flex items-center justify-between text-xs rounded px-2.5 py-1.5 ${
      variant === 'overdue' ? 'bg-red-50' : 'bg-amber-50'
    }`}>
      <div>
        <button className="font-semibold font-mono text-blue-600 hover:underline cursor-pointer"
          onClick={() => setSelectedPO(po.po_id)} data-testid={`ap-po-${po.po_id}`}>
          {po.po_number}
        </button>
        <p className="text-slate-500 text-[10px]">{po.vendor}</p>
      </div>
      <div className="text-right">
        <p className={`font-bold ${variant === 'overdue' ? 'text-red-700' : 'text-amber-700'}`}>{formatPHP(po.balance)}</p>
        <p className={`text-[10px] ${variant === 'overdue' ? 'text-red-500' : 'text-amber-500'}`}>
          {variant === 'overdue' ? `${Math.abs(po.days_left)}d overdue` : po.days_left === 0 ? 'Due today' : `${po.days_left}d left`}
        </p>
      </div>
    </div>
  );

  return (
    <>
      <Card className={`border-slate-200 h-full ${hasOverdue ? 'border-red-200' : ''}`} data-testid="ap-widget">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-semibold flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
              <FileText size={15} className="text-red-600" /> Accounts Payable
            </CardTitle>
            <Button variant="ghost" size="sm" className="h-7 text-xs text-slate-500" onClick={() => navigate('/pay-supplier')}>
              Pay <ChevronRight size={12} />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {/* Total */}
          <div className="text-center py-2">
            <p className="text-2xl font-bold font-mono text-red-700" style={{ fontFamily: 'Manrope' }}>{formatPHP(d.total_payable || 0)}</p>
            <p className="text-[10px] text-slate-400">Total outstanding</p>
          </div>

          {/* Breakdown */}
          <div className="grid grid-cols-3 gap-2">
            <div className={`rounded-lg p-2.5 text-center ${hasOverdue ? 'bg-red-50 border border-red-200' : 'bg-slate-50'}`}>
              <p className={`text-sm font-bold font-mono ${hasOverdue ? 'text-red-700' : 'text-slate-500'}`}>{formatPHP(d.overdue_total || 0)}</p>
              <p className="text-[10px] text-slate-500 flex items-center justify-center gap-1">
                {hasOverdue && <AlertTriangle size={9} className="text-red-500" />}
                Overdue ({d.overdue_count || 0})
              </p>
            </div>
            <div className="rounded-lg p-2.5 text-center bg-amber-50 border border-amber-200">
              <p className="text-sm font-bold font-mono text-amber-700">{formatPHP(d.due_this_week_total || 0)}</p>
              <p className="text-[10px] text-slate-500 flex items-center justify-center gap-1">
                <Clock size={9} className="text-amber-500" />
                This Week
              </p>
            </div>
            <div className="rounded-lg p-2.5 text-center bg-slate-50">
              <p className="text-sm font-bold font-mono text-slate-700">{formatPHP(d.upcoming_total || 0)}</p>
              <p className="text-[10px] text-slate-500">Upcoming ({d.upcoming_count || 0})</p>
            </div>
          </div>

          {/* Overdue list */}
          {hasOverdue && (
            <div className="space-y-1">
              <p className="text-[10px] font-semibold text-red-600 uppercase">Overdue</p>
              {(d.overdue || []).slice(0, 3).map(po => <PORow key={po.po_id} po={po} variant="overdue" />)}
            </div>
          )}

          {/* Due this week */}
          {(d.due_this_week || []).length > 0 && (
            <div className="space-y-1">
              <p className="text-[10px] font-semibold text-amber-600 uppercase">Due This Week</p>
              {(d.due_this_week || []).slice(0, 3).map(po => <PORow key={po.po_id} po={po} variant="due" />)}
            </div>
          )}

          {d.total_payable === 0 && (
            <p className="text-xs text-emerald-600 text-center py-3">All supplier payments are up to date</p>
          )}
        </CardContent>
      </Card>

      {/* PO Detail Dialog */}
      <PODetailDialog
        poId={selectedPO}
        open={!!selectedPO}
        onClose={() => { setSelectedPO(null); load(); }}
      />
    </>
  );
}
