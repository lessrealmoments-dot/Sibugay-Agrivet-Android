import { useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useAuth, api } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Separator } from '../components/ui/separator';
import { ScrollArea } from '../components/ui/scroll-area';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import {
  Plus, Trash2, Send, CheckCircle2, Search, RefreshCw, Settings2,
  AlertTriangle, ChevronDown, ChevronUp, Building2, Package, X,
  TrendingUp, Clock, ArrowRight, Eye, XCircle, Pencil
} from 'lucide-react';
import { toast } from 'sonner';

const STATUS_COLORS = {
  draft: 'bg-slate-100 text-slate-600',
  sent: 'bg-blue-100 text-blue-700',
  received_pending: 'bg-yellow-100 text-yellow-700',
  received: 'bg-emerald-100 text-emerald-700',
  disputed: 'bg-red-100 text-red-700',
  cancelled: 'bg-red-100 text-red-600',
};

function newRow() {
  return {
    id: Math.random().toString(36).slice(2),
    productSearch: '', productMatches: [], product: null,
    activeSearchIndex: -1,
    qty: 1,
    branch_capital: 0,
    global_cost_price: 0,
    is_branch_specific_cost: false,
    transfer_capital: '',
    branch_retail: '',
    last_purchase_ref: null, moving_average_ref: null, last_branch_retail: null,
    override: false, override_reason: '',
  };
}

const MARKUP_TYPES = [
  { value: 'fixed', label: '+ Fixed ₱' },
  { value: 'percent', label: '+ % of Capital' },
];

// ── Per-row validation ──────────────────────────────────────────────────────
function validateRow(row, minMargin) {
  const tc = parseFloat(row.transfer_capital) || 0;
  const br = parseFloat(row.branch_retail) || 0;
  if (!tc || !br) return { ok: false, reason: 'incomplete', margin: 0 };
  const margin = br - tc;
  if (tc > br) return { ok: false, reason: 'below_cost', margin };
  if (margin < minMargin) return { ok: false, reason: 'low_margin', margin };
  return { ok: true, reason: '', margin };
}

export default function BranchTransferPage() {
  const { branches, currentBranch, user, canViewAllBranches, selectedBranchId, isConsolidatedView } = useAuth();
  const isAdmin = user?.role === 'admin';
  const searchTimers = useRef({});
  const dropdownRefs = useRef({});

  // ── Lists / history ────────────────────────────────────────────────────────
  const [tab, setTab] = useState('new');
  const [historyTab, setHistoryTab] = useState('outgoing'); // outgoing | incoming | requests
  const [stockRequests, setStockRequests] = useState([]);
  const [requestsLoading, setRequestsLoading] = useState(false);
  const [generatingTransfer, setGeneratingTransfer] = useState(null); // request id being processed
  const [orders, setOrders] = useState([]);
  const [ordersLoading, setOrdersLoading] = useState(false);
  const [viewOrder, setViewOrder] = useState(null);
  const [receiveDialog, setReceiveDialog] = useState(false);
  const [receiveSaving, setReceiveSaving] = useState(false);
  const [editingOrderId, setEditingOrderId] = useState(null); // ID of draft being edited

  // ── New transfer form ──────────────────────────────────────────────────────
  const [fromBranchId, setFromBranchId] = useState(() => currentBranch?.id || '');
  const [toBranchId, setToBranchId] = useState('');
  const [minMargin, setMinMargin] = useState(20);
  const [categoryMarkups, setCategoryMarkups] = useState([]);
  const [markupPanelOpen, setMarkupPanelOpen] = useState(false);
  const [rows, setRows] = useState(() => [newRow()]);
  const [saving, setSaving] = useState(false);
  const [categories, setCategories] = useState([]);
  const [templateLoaded, setTemplateLoaded] = useState(false);

  // Sync fromBranchId with currentBranch on initial load
  useEffect(() => {
    if (currentBranch?.id && !fromBranchId) setFromBranchId(currentBranch.id);
  }, [currentBranch?.id]); // eslint-disable-line

  const destBranch = branches.find(b => b.id === toBranchId);

  // Load categories once
  useEffect(() => {
    api.get('/products/categories').then(r => setCategories(r.data || [])).catch(() => {});
  }, []);

  // Reset rows and template when source branch changes
  useEffect(() => {
    setRows([newRow()]);
    setToBranchId('');
    setTemplateLoaded(false);
  }, [fromBranchId]); // eslint-disable-line

  // Load markup template when destination branch changes
  useEffect(() => {
    if (!toBranchId) { setTemplateLoaded(false); return; }
    setRows([newRow()]); // Reset rows for new destination
    api.get(`/branch-transfers/markup-template/${toBranchId}`)
      .then(r => {
        setMinMargin(r.data.min_margin ?? 20);
        setCategoryMarkups(r.data.category_markups || []);
        setTemplateLoaded(true);
      })
      .catch(() => setTemplateLoaded(true));
  }, [toBranchId]);

  // Re-apply markups to all rows when categoryMarkups change
  useEffect(() => {
    if (!rows.length) return;
    setRows(prev => prev.map(row => applyMarkupToRow(row, categoryMarkups)));
  }, [categoryMarkups]); // eslint-disable-line

  // Load transfer history — filtered by branch context
  const loadOrders = useCallback(async () => {
    setOrdersLoading(true);
    try {
      const params = { limit: 100 };
      // Admin in specific branch view: filter by that branch
      if (canViewAllBranches && !isConsolidatedView && currentBranch?.id) {
        params.branch_id = currentBranch.id;
      }
      // isConsolidatedView (All Branches) → no filter, admin sees everything
      const res = await api.get('/branch-transfers', { params });
      setOrders(res.data.orders || []);
    } catch { toast.error('Failed to load transfer history'); }
    setOrdersLoading(false);
  }, [canViewAllBranches, isConsolidatedView, currentBranch?.id]);

  useEffect(() => { if (tab === 'history') loadOrders(); }, [tab, loadOrders]);

  // ── Row helpers ─────────────────────────────────────────────────────────────
  const updateRow = (id, updates) =>
    setRows(prev => prev.map(r => r.id === id ? { ...r, ...updates } : r));

  const handleRowSearchKeyDown = (e, row) => {
    const matches = row.productMatches || [];
    if (!matches.length) {
      if (e.key === 'Escape') updateRow(row.id, { productSearch: '', productMatches: [], activeSearchIndex: -1 });
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      updateRow(row.id, { activeSearchIndex: Math.min((row.activeSearchIndex ?? -1) + 1, matches.length - 1) });
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      updateRow(row.id, { activeSearchIndex: Math.max((row.activeSearchIndex ?? 0) - 1, 0) });
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const idx = row.activeSearchIndex ?? -1;
      if (idx >= 0 && matches[idx]) selectProduct(row.id, matches[idx]);
    } else if (e.key === 'Escape') {
      updateRow(row.id, { productMatches: [], activeSearchIndex: -1 });
    }
  };

  function applyMarkupToRow(row, markups) {
    if (!row.product) return row;
    const cat = row.product.category || 'General';
    const rule = markups.find(m => m.category === cat);
    if (!rule) return row;
    const bc = parseFloat(row.branch_capital) || 0;
    const type = rule.type;
    const val = parseFloat(rule.value) || 0;
    const tc = type === 'percent' ? Math.round(bc * (1 + val / 100) * 100) / 100
                                   : Math.round((bc + val) * 100) / 100;
    return { ...row, transfer_capital: String(tc) };
  }

  const searchProduct = (rowId, q) => {
    updateRow(rowId, { productSearch: q, product: null });
    if (searchTimers.current[rowId]) clearTimeout(searchTimers.current[rowId]);
    if (!q || q.length < 1) { updateRow(rowId, { productMatches: [] }); return; }
    searchTimers.current[rowId] = setTimeout(async () => {
      try {
        const params = { q, from_branch_id: fromBranchId, to_branch_id: toBranchId };
        const res = await api.get('/branch-transfers/product-lookup', { params });
        updateRow(rowId, { productMatches: res.data || [] });
      } catch {}
    }, 200);
  };

  const selectProduct = (rowId, p) => {
    const rowUpdate = {
      product: p, productSearch: p.name, productMatches: [], activeSearchIndex: -1,
      branch_capital: p.branch_capital,
      global_cost_price: p.global_cost_price ?? p.branch_capital,
      is_branch_specific_cost: p.is_branch_specific_cost ?? false,
      last_purchase_ref: p.last_purchase_ref,
      moving_average_ref: p.moving_average_ref,
      last_branch_retail: p.last_branch_retail,
      branch_retail: p.last_branch_retail != null ? String(p.last_branch_retail) : '',
    };
    // Apply markup to get transfer capital
    const cat = p.category || 'General';
    const rule = categoryMarkups.find(m => m.category === cat);
    if (rule) {
      const bc = p.branch_capital;
      const val = parseFloat(rule.value) || 0;
      const tc = rule.type === 'percent'
        ? Math.round(bc * (1 + val / 100) * 100) / 100
        : Math.round((bc + val) * 100) / 100;
      rowUpdate.transfer_capital = String(tc);
    } else {
      rowUpdate.transfer_capital = String(p.branch_capital);
    }
    updateRow(rowId, rowUpdate);
  };

  // ── Category markup panel ───────────────────────────────────────────────────
  const setMarkup = (category, field, value) => {
    setCategoryMarkups(prev => {
      const existing = prev.find(m => m.category === category);
      if (existing) {
        return prev.map(m => m.category === category ? { ...m, [field]: value } : m);
      }
      return [...prev, { category, type: 'fixed', value: 0, [field]: value }];
    });
  };
  const getMarkup = (category) => categoryMarkups.find(m => m.category === category) || { type: 'fixed', value: '' };

  const saveTemplate = async () => {
    if (!toBranchId) return;
    try {
      await api.put(`/branch-transfers/markup-template/${toBranchId}`, {
        min_margin: minMargin,
        category_markups: categoryMarkups.filter(m => m.value !== '' && parseFloat(m.value) > 0),
      });
      toast.success('Markup template saved');
    } catch { toast.error('Failed to save template'); }
  };

  // ── Submit ─────────────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    if (!toBranchId) { toast.error('Select a destination branch'); return; }
    if (!rows.length || rows.every(r => !r.product)) { toast.error('Add at least one product'); return; }

    const validRows = rows.filter(r => r.product);
    const blockers = validRows.filter(r => {
      const v = validateRow(r, minMargin);
      return !v.ok && !r.override;
    });
    if (blockers.length > 0) {
      toast.error(`${blockers.length} row(s) have validation errors. Fix or override them.`);
      return;
    }

    setSaving(true);
    try {
      await api.post('/branch-transfers', {
        from_branch_id: fromBranchId,
        to_branch_id: toBranchId,
        min_margin: minMargin,
        category_markups: categoryMarkups.filter(m => parseFloat(m.value) > 0),
        items: validRows.map(r => ({
          product_id: r.product.id,
          product_name: r.product.name,
          sku: r.product.sku,
          category: r.product.category,
          unit: r.product.unit,
          qty: parseFloat(r.qty) || 0,
          branch_capital: r.branch_capital,
          transfer_capital: parseFloat(r.transfer_capital) || 0,
          branch_retail: parseFloat(r.branch_retail) || 0,
          last_purchase_ref: r.last_purchase_ref,
          moving_average_ref: r.moving_average_ref,
          override: r.override,
          override_reason: r.override_reason,
        })),
      });
      toast.success('Branch transfer order created!');
      setRows([newRow()]);
      setTab('history');
      loadOrders();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to create transfer'); }
    setSaving(false);
  };

  // ── Edit existing draft order ──────────────────────────────────────────────
  const loadOrderIntoEdit = (order) => {
    setFromBranchId(order.from_branch_id || '');
    setToBranchId(order.to_branch_id || '');
    setMinMargin(order.min_margin ?? 20);
    setCategoryMarkups(order.category_markups || []);
    setEditingOrderId(order.id);
    // Reconstruct rows from stored items
    const editRows = (order.items || []).map(item => ({
      ...newRow(),
      product: { id: item.product_id, name: item.product_name, sku: item.sku, category: item.category, unit: item.unit },
      productSearch: item.product_name,
      qty: item.qty,
      branch_capital: item.branch_capital || 0,
      global_cost_price: item.branch_capital || 0,
      is_branch_specific_cost: false,
      transfer_capital: String(item.transfer_capital || ''),
      branch_retail: String(item.branch_retail || ''),
      override: item.override || false,
      override_reason: item.override_reason || '',
    }));
    setRows(editRows.length ? editRows : [newRow()]);
    setTab('new');
  };

  const handleUpdateDraft = async () => {
    if (!editingOrderId) { handleSubmit(); return; }
    if (!rows.length || rows.every(r => !r.product)) { toast.error('Add at least one product'); return; }
    const validRows = rows.filter(r => r.product);
    const blockers = validRows.filter(r => { const v = validateRow(r, minMargin); return !v.ok && !r.override; });
    if (blockers.length > 0) { toast.error(`${blockers.length} row(s) have validation errors.`); return; }

    setSaving(true);
    try {
      await api.put(`/branch-transfers/${editingOrderId}`, {
        min_margin: minMargin,
        category_markups: categoryMarkups.filter(m => parseFloat(m.value) > 0),
        items: validRows.map(r => ({
          product_id: r.product.id,
          product_name: r.product.name,
          sku: r.product.sku,
          category: r.product.category,
          unit: r.product.unit,
          qty: parseFloat(r.qty) || 0,
          branch_capital: r.branch_capital,
          transfer_capital: parseFloat(r.transfer_capital) || 0,
          branch_retail: parseFloat(r.branch_retail) || 0,
          override: r.override,
          override_reason: r.override_reason,
        })),
      });
      toast.success('Draft transfer updated!');
      setEditingOrderId(null);
      setRows([newRow()]);
      setTab('history');
      loadOrders();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to update transfer'); }
    setSaving(false);
  };

  const cancelEdit = () => {
    setEditingOrderId(null);
    setRows([newRow()]);
    setFromBranchId(currentBranch?.id || '');
    setToBranchId('');
  };
  const [receiveQtys, setReceiveQtys] = useState({});
  const [receiveNotes, setReceiveNotes] = useState('');
  const [receiveConfirmStep, setReceiveConfirmStep] = useState(false); // double-check step
  const [acceptDialog, setAcceptDialog] = useState(null); // order to accept
  const [disputeDialog, setDisputeDialog] = useState(null); // order to dispute
  const [disputeNote, setDisputeNote] = useState('');
  const [actionSaving, setActionSaving] = useState(false);

  const openReceive = (order) => {
    setViewOrder(order);
    const qtys = {};
    order.items.forEach(item => { qtys[item.product_id] = item.qty; });
    setReceiveQtys(qtys);
    setReceiveNotes('');
    setReceiveConfirmStep(false);
    setReceiveDialog(true);
  };

  // Compute variance for current receiveQtys
  const getVariances = (items) => {
    if (!items) return { hasVariance: false, shortages: [], excesses: [] };
    const shortages = [], excesses = [];
    items.forEach(item => {
      const ordered = parseFloat(item.qty) || 0;
      const received = parseFloat(receiveQtys[item.product_id] ?? ordered) || 0;
      const diff = received - ordered;
      if (diff < 0) shortages.push({ ...item, qty_received: received, diff });
      else if (diff > 0) excesses.push({ ...item, qty_received: received, diff });
    });
    return { hasVariance: shortages.length > 0 || excesses.length > 0, shortages, excesses };
  };

  const handleReceive = async () => {
    if (!viewOrder) return;
    const { hasVariance } = getVariances(viewOrder.items);

    // First click with variance: show double-check step
    if (hasVariance && !receiveConfirmStep) {
      setReceiveConfirmStep(true);
      return;
    }

    setReceiveSaving(true);
    try {
      const items = viewOrder.items.map(item => ({
        product_id: item.product_id,
        qty: item.qty,
        qty_received: parseFloat(receiveQtys[item.product_id]) ?? item.qty,
        transfer_capital: item.transfer_capital,
        branch_retail: item.branch_retail,
      }));
      const res = await api.post(`/branch-transfers/${viewOrder.id}/receive`, { items, notes: receiveNotes });
      if (res.data.status === 'received_pending') {
        toast.warning('Quantities have variance — submitted for source branch confirmation.');
      } else {
        toast.success(res.data.message || 'Transfer received!');
      }
      setReceiveDialog(false);
      setReceiveConfirmStep(false);
      setViewOrder(null);
      loadOrders();
    } catch (e) { toast.error(e.response?.data?.detail || 'Receive failed'); }
    setReceiveSaving(false);
  };

  const handleAcceptReceipt = async (orderId, note = '') => {
    setActionSaving(true);
    try {
      await api.post(`/branch-transfers/${orderId}/accept-receipt`, { note });
      toast.success('Receipt accepted — inventory updated.');
      setAcceptDialog(null);
      loadOrders();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to accept'); }
    setActionSaving(false);
  };

  const handleDisputeReceipt = async () => {
    if (!disputeDialog || !disputeNote.trim()) { toast.error('Dispute reason is required'); return; }
    setActionSaving(true);
    try {
      await api.post(`/branch-transfers/${disputeDialog.id}/dispute-receipt`, { note: disputeNote });
      toast.success('Receipt disputed — destination has been notified to re-count.');
      setDisputeDialog(null);
      setDisputeNote('');
      loadOrders();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to dispute'); }
    setActionSaving(false);
  };

  const handleSend = async (orderId) => {
    try {
      await api.post(`/branch-transfers/${orderId}/send`);
      toast.success('Transfer marked as sent');
      loadOrders();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  // ── Print Transfer Order (QuickBooks-style) ──────────────────────────────
  const printTransferOrder = (order) => {
    const toBranch = branches.find(b => b.id === order.to_branch_id)?.name || '';
    const fromBranch = branches.find(b => b.id === order.from_branch_id)?.name || '';
    const items = order.items || [];
    const totalTransfer = items.reduce((s, i) => s + i.transfer_capital * i.qty, 0);
    const totalRetail = items.reduce((s, i) => s + i.branch_retail * i.qty, 0);
    const php = (n) => '₱' + parseFloat(n || 0).toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>${order.order_number}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: Arial, Helvetica, sans-serif; font-size: 11px; color: #1a1a1a; padding: 24px 32px; }
    .header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; padding-bottom: 16px; border-bottom: 2px solid #1A4D2E; }
    .company { }
    .company h1 { font-size: 22px; font-weight: 800; color: #1A4D2E; letter-spacing: -0.5px; }
    .company p { font-size: 11px; color: #666; margin-top: 2px; }
    .doc-info { text-align: right; }
    .doc-info h2 { font-size: 16px; font-weight: 700; color: #1A4D2E; text-transform: uppercase; letter-spacing: 1px; }
    .doc-info .number { font-size: 18px; font-weight: 800; color: #333; }
    .doc-info .date { font-size: 11px; color: #666; margin-top: 4px; }
    .address-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }
    .address-box { border: 1px solid #e0e0e0; border-radius: 6px; padding: 12px; background: #fafafa; }
    .address-box .label { font-size: 9px; font-weight: 700; color: #999; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 4px; }
    .address-box .value { font-size: 13px; font-weight: 700; color: #1A4D2E; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
    thead tr { background: #1A4D2E; color: white; }
    thead th { padding: 8px 10px; text-align: left; font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
    thead th.right { text-align: right; }
    tbody tr { border-bottom: 1px solid #f0f0f0; }
    tbody tr:nth-child(even) { background: #f9f9f9; }
    tbody td { padding: 7px 10px; font-size: 11px; }
    tbody td.right { text-align: right; font-family: 'Courier New', monospace; }
    tbody td.sku { color: #999; font-size: 9px; font-family: 'Courier New', monospace; }
    .totals { margin-left: auto; width: 300px; border: 1px solid #e0e0e0; border-radius: 6px; overflow: hidden; }
    .totals-row { display: flex; justify-content: space-between; padding: 6px 12px; font-size: 11px; border-bottom: 1px solid #f0f0f0; }
    .totals-row.total { background: #1A4D2E; color: white; font-weight: 700; font-size: 13px; }
    .totals-row.retail { background: #e8f5e9; color: #1A4D2E; font-weight: 600; }
    .signatures { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 24px; margin-top: 36px; padding-top: 16px; border-top: 1px solid #e0e0e0; }
    .sig-box { text-align: center; }
    .sig-line { border-bottom: 1px solid #333; margin-bottom: 6px; height: 28px; }
    .sig-label { font-size: 9px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }
    .note { font-size: 9px; color: #999; margin-top: 20px; text-align: center; }
    @media print { body { padding: 0; } @page { margin: 16mm; } }
  </style>
</head>
<body>
  <div class="header">
    <div class="company">
      <h1>AgriBooks</h1>
      <p>Agricultural Inventory &amp; Business Management System</p>
    </div>
    <div class="doc-info">
      <h2>Branch Transfer Order</h2>
      <div class="number">${order.order_number}</div>
      <div class="date">Date: ${order.created_at?.slice(0, 10) || ''}</div>
      <div class="date">Status: ${order.status?.toUpperCase()}</div>
    </div>
  </div>

  <div class="address-row">
    <div class="address-box">
      <div class="label">From (Source Branch)</div>
      <div class="value">${fromBranch}</div>
    </div>
    <div class="address-box">
      <div class="label">To (Destination Branch)</div>
      <div class="value">${toBranch}</div>
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th style="width:38%">Product</th>
        <th class="right" style="width:14%">Qty</th>
        <th class="right" style="width:16%">Transfer Capital</th>
        <th class="right" style="width:16%">Total</th>
        <th class="right" style="width:16%">Recommended Retail</th>
      </tr>
    </thead>
    <tbody>
      ${items.map(item => `
      <tr>
        <td>
          <div style="font-weight:600">${item.product_name}</div>
          <div class="sku">${item.sku} · ${item.category}</div>
        </td>
        <td class="right">${item.qty} ${item.unit || ''}</td>
        <td class="right">${php(item.transfer_capital)}</td>
        <td class="right" style="font-weight:700">${php(item.transfer_capital * item.qty)}</td>
        <td class="right" style="color:#1A4D2E;font-weight:700">${php(item.branch_retail)}</td>
      </tr>`).join('')}
    </tbody>
  </table>

  <div class="totals">
    <div class="totals-row"><span>Total Items</span><span>${items.length}</span></div>
    <div class="totals-row"><span>Total Qty</span><span>${items.reduce((s, i) => s + i.qty, 0)}</span></div>
    <div class="totals-row total"><span>Transfer Total</span><span>${php(totalTransfer)}</span></div>
    <div class="totals-row retail"><span>Retail Value at Branch</span><span>${php(totalRetail)}</span></div>
  </div>

  <div class="signatures">
    <div class="sig-box">
      <div class="sig-line"></div>
      <div class="sig-label">Prepared by</div>
    </div>
    <div class="sig-box">
      <div class="sig-line"></div>
      <div class="sig-label">Released by (Source Branch)</div>
    </div>
    <div class="sig-box">
      <div class="sig-line"></div>
      <div class="sig-label">Received by (Destination Branch)</div>
    </div>
  </div>

  <div class="note">AgriBooks — Agricultural Inventory &amp; Business Management System &nbsp;|&nbsp; Internal Use Only</div>
</body>
</html>`;

    const win = window.open('', '_blank', 'width=900,height=700');
    win.document.write(html);
    win.document.close();
    win.focus();
    setTimeout(() => { win.print(); }, 500);
  };

  const handleCancel = async (orderId) => {    if (!window.confirm('Cancel this transfer order?')) return;
    try {
      await api.delete(`/branch-transfers/${orderId}`);
      toast.success('Transfer cancelled');
      loadOrders();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  // ── Totals ─────────────────────────────────────────────────────────────────
  const validRows = rows.filter(r => r.product);
  const totalBranchCapital = validRows.reduce((s, r) => s + (r.branch_capital * (parseFloat(r.qty)||0)), 0);
  const totalTransfer = validRows.reduce((s, r) => s + ((parseFloat(r.transfer_capital)||0) * (parseFloat(r.qty)||0)), 0);
  const totalRetail = validRows.reduce((s, r) => s + ((parseFloat(r.branch_retail)||0) * (parseFloat(r.qty)||0)), 0);

  return (
    <div className="space-y-5 animate-fadeIn" data-testid="branch-transfer-page">
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
          <Building2 size={22} className="text-[#1A4D2E]" /> Branch Transfers
        </h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Transfer stock between any branches with auto-computed pricing
        </p>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="new"><Plus size={14} className="mr-1" /> New Transfer</TabsTrigger>
          <TabsTrigger value="history" data-testid="transfer-history-tab"><Clock size={14} className="mr-1" /> History</TabsTrigger>
        </TabsList>

        {/* ── NEW TRANSFER TAB ── */}
        <TabsContent value="new" className="space-y-4 mt-4">
          {/* Editing banner */}
          {editingOrderId && (
            <div className="flex items-center justify-between px-4 py-2.5 rounded-lg bg-amber-50 border border-amber-200">
              <div className="flex items-center gap-2 text-sm text-amber-800">
                <AlertTriangle size={15} className="shrink-0" />
                <span>Editing draft order — changes won't affect inventory until it's sent and received.</span>
              </div>
              <Button variant="ghost" size="sm" onClick={cancelEdit} className="text-amber-700 h-7">
                Discard Changes
              </Button>
            </div>
          )}

          {/* Header row */}
          <div className="flex flex-wrap items-end gap-4">
            <div className="flex-1 min-w-[160px]">
              <Label className="text-xs">From Branch <span className="text-slate-400">(source)</span></Label>
              <Select value={fromBranchId} onValueChange={val => { setFromBranchId(val); setToBranchId(''); }}
                data-testid="from-branch-select">
                <SelectTrigger className="mt-1 h-9" data-testid="from-branch-trigger">
                  <SelectValue placeholder="Select source branch" />
                </SelectTrigger>
                <SelectContent>
                  {branches.filter(b => b.id !== toBranchId).map(b => (
                    <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center pb-1">
              <ArrowRight size={18} className="text-slate-400" />
            </div>
            <div className="flex-1 min-w-[160px]">
              <Label className="text-xs">To Branch <span className="text-slate-400">(destination)</span></Label>
              <Select value={toBranchId} onValueChange={setToBranchId} disabled={!fromBranchId}>
                <SelectTrigger className="mt-1 h-9" data-testid="dest-branch-select">
                  <SelectValue placeholder="Select destination branch" />
                </SelectTrigger>
                <SelectContent>
                  {branches.filter(b => b.id !== fromBranchId).map(b => (
                    <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="w-40">
              <Label className="text-xs">Min Margin (₱ / unit)</Label>
              <Input type="number" min={0} value={minMargin}
                onChange={e => setMinMargin(parseFloat(e.target.value) || 0)}
                className="mt-1 h-9 font-mono" data-testid="min-margin-input" />
            </div>
            {toBranchId && (
              <Button variant="outline" size="sm" onClick={saveTemplate} className="h-9 mt-5">
                Save as Default
              </Button>
            )}
          </div>

          {/* Category Markup Panel */}
          {toBranchId && (
            <Card className="border-slate-200">
              <button
                type="button"
                onClick={() => setMarkupPanelOpen(v => !v)}
                className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 rounded-xl transition-colors"
                data-testid="markup-panel-toggle"
              >
                <span className="flex items-center gap-2">
                  <Settings2 size={15} className="text-[#1A4D2E]" />
                  Category Markup Rules
                  {categoryMarkups.filter(m => parseFloat(m.value) > 0).length > 0 && (
                    <Badge className="text-[10px] bg-[#1A4D2E]/10 text-[#1A4D2E]">
                      {categoryMarkups.filter(m => parseFloat(m.value) > 0).length} active
                    </Badge>
                  )}
                </span>
                {markupPanelOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>
              {markupPanelOpen && (
                <CardContent className="pt-0 pb-4">
                  <p className="text-xs text-slate-400 mb-3">
                    Set per-category add-ons. Applies to all products when added. All values are editable per row.
                  </p>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    {categories.map(cat => {
                      const mk = getMarkup(cat);
                      return (
                        <div key={cat} className="p-3 rounded-lg border border-slate-200 bg-slate-50">
                          <p className="text-xs font-semibold text-slate-600 mb-2">{cat}</p>
                          <div className="flex gap-1.5">
                            <Select value={mk.type || 'fixed'} onValueChange={v => setMarkup(cat, 'type', v)}>
                              <SelectTrigger className="h-7 text-xs w-28"><SelectValue /></SelectTrigger>
                              <SelectContent>
                                {MARKUP_TYPES.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                              </SelectContent>
                            </Select>
                            <Input type="number" min={0} placeholder="0"
                              value={mk.value}
                              onChange={e => setMarkup(cat, 'value', e.target.value)}
                              className="h-7 text-xs font-mono flex-1"
                              data-testid={`markup-${cat}`}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              )}
            </Card>
          )}

          {/* Product table */}
          {toBranchId && (
            <>
              <Card className="border-slate-200 overflow-visible">
                <CardContent className="p-0">
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="bg-slate-50 border-b-2 border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                        <th className="px-3 py-2 text-left" style={{minWidth:'200px'}}>Product</th>
                        <th className="px-2 py-2 text-center" style={{minWidth:'70px'}}>Qty</th>
                        <th className="px-2 py-2 text-right" style={{minWidth:'100px'}}>Branch Capital</th>
                        <th className="px-2 py-2 text-right" style={{minWidth:'110px'}}>
                          Transfer Capital
                          <span className="text-[9px] font-normal block text-slate-400">(their cost)</span>
                        </th>
                        <th className="px-2 py-2 text-right" style={{minWidth:'110px'}}>
                          Branch Retail
                          <span className="text-[9px] font-normal block text-slate-400">(their sell price)</span>
                        </th>
                        <th className="px-2 py-2 text-center" style={{minWidth:'90px'}}>Margin</th>
                        {isAdmin && <th className="px-2 py-2 text-center" style={{minWidth:'80px'}}>Override</th>}
                        <th className="w-8"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => {
                        const v = row.product ? validateRow(row, minMargin) : { ok: true, margin: 0 };
                        const rowBad = !v.ok && !row.override;
                        return (
                          <tr key={row.id} className={`border-b border-slate-100 ${rowBad ? 'bg-red-50/50' : 'hover:bg-slate-50/30'}`}>
                            {/* Product search */}
                            <td className="px-2 py-1.5" style={{minWidth:'200px'}}>
                              {row.product ? (
                                <div>
                                  <div className="flex items-center gap-1.5 bg-emerald-50 border border-emerald-200 rounded px-2 h-8">
                                    <span className="text-sm font-medium text-emerald-800 truncate flex-1">{row.product.name}</span>
                                    <button onClick={() => updateRow(row.id, { product: null, productSearch: '', transfer_capital: '', branch_retail: '' })}
                                      className="text-slate-300 hover:text-red-500">
                                      <X size={12} />
                                    </button>
                                  </div>
                                  <p className="text-[10px] text-slate-400 mt-0.5">{row.product.sku} · {row.product.category}</p>
                                </div>
                              ) : (
                                <div className="relative">
                                  <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-400" />
                                  <Input value={row.productSearch}
                                    onChange={e => searchProduct(row.id, e.target.value)}
                                    onKeyDown={e => handleRowSearchKeyDown(e, row)}
                                    placeholder="Search product..."
                                    className="h-8 pl-7 text-sm"
                                    data-testid={`product-search-${row.id}`}
                                    ref={el => { dropdownRefs.current[row.id] = el; }}
                                    autoComplete="off"
                                  />
                                  {row.productMatches?.length > 0 && (() => {
                                    const el = dropdownRefs.current[row.id];
                                    if (!el) return null;
                                    const rect = el.getBoundingClientRect();
                                    return createPortal(
                                      <div style={{ position:'fixed', top: rect.bottom+4, left: rect.left, width: Math.max(rect.width, 300), zIndex: 9999 }}
                                        className="bg-white border border-slate-200 rounded-lg shadow-xl max-h-64 overflow-y-auto">
                                        {row.productMatches.map((p, idx) => (
                                          <button key={p.id} onMouseDown={() => selectProduct(row.id, p)}
                                            className={`w-full text-left px-3 py-2 border-b last:border-0 transition-colors ${
                                              idx === row.activeSearchIndex
                                                ? 'bg-emerald-50 border-l-[3px] border-l-emerald-700'
                                                : 'hover:bg-slate-50'
                                            }`}>
                                            <div className="flex justify-between items-start">
                                              <div>
                                                <span className="font-medium text-sm">{p.name}</span>
                                                <span className="text-slate-400 text-xs ml-2">{p.sku} · {p.category}</span>
                                              </div>
                                              <span className="text-xs font-mono text-slate-600">{formatPHP(p.branch_capital)}</span>
                                            </div>
                                            {p.last_branch_retail && (
                                              <span className="text-[10px] text-blue-500">Last retail at branch: {formatPHP(p.last_branch_retail)}</span>
                                            )}
                                          </button>
                                        ))}
                                        <div className="px-3 py-1 bg-slate-50 text-[10px] text-slate-400 flex gap-3 border-t">
                                          <span>↑↓ navigate</span>
                                          <span>Enter to select</span>
                                          <span>Esc to close</span>
                                        </div>
                                      </div>,
                                      document.body
                                    );
                                  })()}
                                </div>
                              )}
                            </td>

                            {/* Qty */}
                            <td className="px-2 py-1.5 text-center">
                              <Input type="number" min={1} value={row.qty}
                                onChange={e => updateRow(row.id, { qty: e.target.value })}
                                className="h-8 text-sm text-center font-mono w-16"
                                data-testid={`qty-${row.id}`} />
                            </td>

                            {/* Branch Capital — read-only */}
                            <td className="px-2 py-1.5 text-right">
                              <div className="h-auto flex flex-col items-end justify-center pr-2">
                                <span className="font-mono text-sm text-slate-600">{row.product ? formatPHP(row.branch_capital) : '—'}</span>
                                {row.product && row.is_branch_specific_cost && (
                                  <span className="text-[9px] text-amber-600 leading-tight">
                                    branch cost (global: {formatPHP(row.global_cost_price)})
                                  </span>
                                )}
                              </div>
                            </td>

                            {/* Transfer Capital — editable */}
                            <td className="px-2 py-1.5">
                              <div>
                                <Input type="number" min={0} step="0.01"
                                  value={row.transfer_capital}
                                  onChange={e => updateRow(row.id, { transfer_capital: e.target.value })}
                                  placeholder="0.00"
                                  className={`h-8 text-sm text-right font-mono font-bold ${rowBad && v.reason === 'below_cost' ? 'border-red-400 text-red-700 bg-red-50' : ''}`}
                                  data-testid={`transfer-capital-${row.id}`}
                                  disabled={!row.product}
                                />
                                {row.product && (
                                  <div className="flex gap-2 mt-0.5">
                                    {row.last_purchase_ref != null && <span className="text-[9px] text-slate-400">LP: {formatPHP(row.last_purchase_ref)}</span>}
                                    {row.moving_average_ref != null && <span className="text-[9px] text-slate-400">MA: {formatPHP(row.moving_average_ref)}</span>}
                                  </div>
                                )}
                              </div>
                            </td>

                            {/* Branch Retail — editable */}
                            <td className="px-2 py-1.5">
                              <div>
                                <Input type="number" min={0} step="0.01"
                                  value={row.branch_retail}
                                  onChange={e => updateRow(row.id, { branch_retail: e.target.value })}
                                  placeholder="0.00"
                                  className={`h-8 text-sm text-right font-mono font-bold ${rowBad ? 'border-red-400 text-red-700 bg-red-50' : ''}`}
                                  data-testid={`branch-retail-${row.id}`}
                                  disabled={!row.product}
                                />
                                {row.last_branch_retail != null && (
                                  <span className="text-[9px] text-blue-400 mt-0.5 block">Last: {formatPHP(row.last_branch_retail)}</span>
                                )}
                              </div>
                            </td>

                            {/* Margin badge */}
                            <td className="px-2 py-1.5 text-center">
                              {row.product && row.transfer_capital && row.branch_retail ? (
                                <div>
                                  <span className={`text-sm font-bold font-mono ${v.ok ? 'text-emerald-600' : 'text-red-600'}`}>
                                    {v.margin >= 0 ? '+' : ''}{formatPHP(v.margin)}
                                  </span>
                                  {!v.ok && !row.override && (
                                    <p className="text-[9px] text-red-500 leading-tight">
                                      {v.reason === 'below_cost' ? 'Below cost' : `< ₱${minMargin} min`}
                                    </p>
                                  )}
                                </div>
                              ) : <span className="text-slate-300">—</span>}
                            </td>

                            {/* Admin override */}
                            {isAdmin && (
                              <td className="px-2 py-1.5 text-center">
                                {row.product && !v.ok ? (
                                  <div>
                                    <label className="flex items-center gap-1 justify-center cursor-pointer">
                                      <input type="checkbox" checked={row.override}
                                        onChange={e => updateRow(row.id, { override: e.target.checked })}
                                        className="rounded border-slate-300"
                                        data-testid={`override-${row.id}`}
                                      />
                                      <span className="text-[10px] text-amber-600">Override</span>
                                    </label>
                                    {row.override && (
                                      <Input value={row.override_reason}
                                        onChange={e => updateRow(row.id, { override_reason: e.target.value })}
                                        placeholder="Reason" className="h-6 text-[10px] mt-0.5" />
                                    )}
                                  </div>
                                ) : <span className="text-slate-200">—</span>}
                              </td>
                            )}

                            {/* Delete row */}
                            <td className="px-1">
                              {rows.length > 1 && (
                                <button onClick={() => setRows(r => r.filter(x => x.id !== row.id))}
                                  className="p-1 text-slate-300 hover:text-red-500 transition-colors">
                                  <Trash2 size={13} />
                                </button>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </CardContent>
              </Card>

              {/* Add row + Totals + Submit */}
              <div className="flex items-start justify-between gap-4">
                <Button variant="outline" size="sm" onClick={() => setRows(r => [...r, newRow()])}
                  data-testid="add-row-btn">
                  <Plus size={14} className="mr-1" /> Add Product
                </Button>

                <div className="flex items-center gap-6 text-sm">
                  <div className="text-right">
                    <p className="text-[10px] text-slate-400 uppercase tracking-wider">Our Cost</p>
                    <p className="font-mono font-bold text-slate-700">{formatPHP(totalBranchCapital)}</p>
                  </div>
                  <ArrowRight size={14} className="text-slate-400" />
                  <div className="text-right">
                    <p className="text-[10px] text-slate-400 uppercase tracking-wider">Transfer Price</p>
                    <p className="font-mono font-bold text-blue-700">{formatPHP(totalTransfer)}</p>
                  </div>
                  <ArrowRight size={14} className="text-slate-400" />
                  <div className="text-right">
                    <p className="text-[10px] text-slate-400 uppercase tracking-wider">Branch Retail</p>
                    <p className="font-mono font-bold text-emerald-700">{formatPHP(totalRetail)}</p>
                  </div>
                  <Button onClick={editingOrderId ? handleUpdateDraft : handleSubmit}
                    disabled={saving || !toBranchId || !validRows.length}
                    className="bg-[#1A4D2E] hover:bg-[#14532d] text-white ml-4"
                    data-testid="create-transfer-btn">
                    {saving ? <RefreshCw size={14} className="animate-spin mr-1.5" /> : <Send size={14} className="mr-1.5" />}
                    {editingOrderId ? 'Save Draft' : 'Create Transfer Order'}
                  </Button>
                </div>
              </div>
            </>
          )}

          {!toBranchId && (
            <div className="text-center py-16 text-slate-400">
              <Building2 size={40} className="mx-auto mb-3 opacity-30" />
              <p>{!fromBranchId ? 'Select a source branch first.' : 'Select a destination branch to start building the transfer order.'}</p>
            </div>
          )}
        </TabsContent>

        {/* ── HISTORY TAB ── */}
        <TabsContent value="history" className="mt-4">
          {/* Outgoing / Incoming sub-tabs */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex gap-1 bg-slate-100 rounded-lg p-1">
              {['outgoing', 'incoming'].map(ht => {
                const effectiveBranchId = currentBranch?.id || user?.branch_id || '';
                const count = isConsolidatedView
                  ? orders.length
                  : orders.filter(o => ht === 'outgoing' ? o.from_branch_id === effectiveBranchId : o.to_branch_id === effectiveBranchId).length;
                return (
                  <button key={ht}
                    onClick={() => setHistoryTab(ht)}
                    className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors capitalize ${historyTab === ht ? 'bg-white shadow-sm text-slate-800' : 'text-slate-500 hover:text-slate-700'}`}
                    data-testid={`history-${ht}-tab`}
                  >
                    {ht} <span className="ml-1 text-xs text-slate-400">({count})</span>
                  </button>
                );
              })}
            </div>
            <Button variant="outline" size="sm" onClick={loadOrders} disabled={ordersLoading}>
              <RefreshCw size={13} className={`mr-1.5 ${ordersLoading ? 'animate-spin' : ''}`} /> Refresh
            </Button>
          </div>

          {(() => {
            const effectiveBranchId = currentBranch?.id || user?.branch_id || '';
            const filteredOrders = isConsolidatedView
              ? orders
              : orders.filter(o => historyTab === 'outgoing'
                  ? o.from_branch_id === effectiveBranchId
                  : o.to_branch_id === effectiveBranchId);

            return (
              <Card className="border-slate-200">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-slate-50">
                      <TableHead className="text-xs uppercase text-slate-500 font-medium">Order #</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500 font-medium">From</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500 font-medium">To</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500 font-medium">Items</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500 font-medium text-right">Transfer Value</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500 font-medium text-right">Retail Value</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500 font-medium">Status</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500 font-medium">Date</TableHead>
                      <TableHead className="w-36"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredOrders.length === 0 ? (
                      <TableRow><TableCell colSpan={9} className="text-center py-8 text-slate-400">
                        No {historyTab} transfers{!isConsolidatedView ? ' for this branch' : ''}.
                      </TableCell></TableRow>
                    ) : filteredOrders.map(o => {
                      const toBranch = branches.find(b => b.id === o.to_branch_id);
                      const fromBranchObj = branches.find(b => b.id === o.from_branch_id);
                      const isSourceBranch = isAdmin || o.from_branch_id === effectiveBranchId;
                      const isDestBranch = isAdmin || o.to_branch_id === effectiveBranchId;
                      return (
                        <TableRow key={o.id} className="hover:bg-slate-50">
                          <TableCell className="font-mono text-sm text-blue-600">{o.order_number}</TableCell>
                          <TableCell className="text-sm text-slate-500">{fromBranchObj?.name || o.from_branch_id?.slice(0,8) || '—'}</TableCell>
                          <TableCell className="font-medium">{toBranch?.name || o.to_branch_id}</TableCell>
                          <TableCell className="text-slate-500">{o.items?.length || 0} products</TableCell>
                          <TableCell className="text-right font-mono">{formatPHP(o.total_at_transfer_capital)}</TableCell>
                          <TableCell className="text-right font-mono text-emerald-700">{formatPHP(o.total_at_branch_retail)}</TableCell>
                          <TableCell>
                            <Badge className={`text-[10px] ${STATUS_COLORS[o.status]}`}>{o.status}</Badge>
                            {o.has_shortage && <Badge className="ml-1 text-[10px] bg-red-100 text-red-700">Short</Badge>}
                          </TableCell>
                          <TableCell className="text-xs text-slate-400">{o.created_at?.slice(0, 10)}</TableCell>
                          <TableCell>
                            <div className="flex gap-0.5">
                              {/* View — always */}
                              <Button variant="ghost" size="sm" onClick={() => { setViewOrder(o); setReceiveDialog(false); }}
                                title="View" className="h-7 px-2" data-testid={`view-btn-${o.id}`}>
                                <Eye size={13} />
                              </Button>
                              {/* Edit draft — source branch only */}
                              {o.status === 'draft' && isSourceBranch && !isDestBranch && (
                                <Button variant="ghost" size="sm" onClick={() => loadOrderIntoEdit(o)}
                                  className="h-7 px-2 text-amber-600" title="Edit Draft"
                                  data-testid={`edit-btn-${o.id}`}>
                                  <Pencil size={13} />
                                </Button>
                              )}
                              {/* Admin can always edit draft */}
                              {o.status === 'draft' && isAdmin && (
                                <Button variant="ghost" size="sm" onClick={() => loadOrderIntoEdit(o)}
                                  className="h-7 px-2 text-amber-600" title="Edit Draft"
                                  data-testid={`edit-btn-admin-${o.id}`}>
                                  <Pencil size={13} />
                                </Button>
                              )}
                              {/* Send — source branch only */}
                              {o.status === 'draft' && isSourceBranch && (
                                <Button variant="ghost" size="sm" onClick={() => handleSend(o.id)}
                                  className="h-7 px-2 text-blue-500" title="Mark as Sent"
                                  data-testid={`send-btn-${o.id}`}>
                                  <Send size={13} />
                                </Button>
                              )}
                              {/* Receive — destination branch only (not source unless admin) */}
                              {o.status === 'sent' && (isDestBranch) && (
                                <Button variant="ghost" size="sm" onClick={() => openReceive(o)}
                                  className="h-7 px-2 text-emerald-600" title="Confirm Receipt"
                                  data-testid={`receive-btn-${o.id}`}>
                                  <CheckCircle2 size={13} />
                                </Button>
                              )}
                              {/* Disputed: destination can re-submit */}
                              {o.status === 'disputed' && isDestBranch && (
                                <Button variant="ghost" size="sm" onClick={() => openReceive(o)}
                                  className="h-7 px-2 text-amber-600" title="Re-submit Receipt"
                                  data-testid={`resubmit-btn-${o.id}`}>
                                  <RefreshCw size={13} />
                                </Button>
                              )}
                              {/* Accept / Dispute pending receipt — source branch only */}
                              {o.status === 'received_pending' && isSourceBranch && (
                                <>
                                  <Button variant="ghost" size="sm" onClick={() => setAcceptDialog(o)}
                                    className="h-7 px-2 text-emerald-600" title="Accept Receipt"
                                    data-testid={`accept-btn-${o.id}`}>
                                    <CheckCircle2 size={13} />
                                  </Button>
                                  <Button variant="ghost" size="sm" onClick={() => { setDisputeDialog(o); setDisputeNote(''); }}
                                    className="h-7 px-2 text-red-500" title="Dispute Receipt"
                                    data-testid={`dispute-btn-${o.id}`}>
                                    <XCircle size={13} />
                                  </Button>
                                </>
                              )}
                              {/* Cancel — source branch only */}
                              {(o.status === 'draft' || o.status === 'sent') && isSourceBranch && (
                                <Button variant="ghost" size="sm" onClick={() => handleCancel(o.id)}
                                  className="h-7 px-2 text-red-400" title="Cancel"
                                  data-testid={`cancel-btn-${o.id}`}>
                                  <XCircle size={13} />
                                </Button>
                              )}
                            </div>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </Card>
            );
          })()}
        </TabsContent>
      </Tabs>

      {/* ── View / Receive Order Dialog ── */}
      <Dialog open={!!viewOrder && !receiveDialog} onOpenChange={() => setViewOrder(null)}>
        <DialogContent className="max-w-4xl max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Manrope' }}>
              {viewOrder?.order_number} — {branches.find(b => b.id === viewOrder?.from_branch_id)?.name || '?'}
              <span className="text-slate-400 mx-1">→</span>
              {branches.find(b => b.id === viewOrder?.to_branch_id)?.name || '?'}
              <Badge className={`ml-2 text-[10px] ${STATUS_COLORS[viewOrder?.status]}`}>{viewOrder?.status}</Badge>
              {viewOrder?.has_shortage && (
                <Badge className="ml-2 text-[10px] bg-red-100 text-red-700">Shortage</Badge>
              )}
            </DialogTitle>
          </DialogHeader>
          <ScrollArea className="flex-1">
            {/* Reconciliation view for received orders */}
            {viewOrder?.status === 'received' ? (
              <div className="space-y-3">
                <div className="text-xs text-slate-500 bg-slate-50 rounded px-3 py-2 flex justify-between">
                  <span>Received by: <b>{viewOrder.received_by_name}</b> · {viewOrder.received_at?.slice(0,10)}</span>
                  {viewOrder.has_shortage && (
                    <span className="text-red-600 font-medium flex items-center gap-1">
                      <AlertTriangle size={12}/> {viewOrder.shortages?.length} product(s) short
                    </span>
                  )}
                </div>
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-white border-b">
                    <tr className="text-[10px] uppercase text-slate-500">
                      <th className="px-3 py-2 text-left">Product</th>
                      <th className="px-3 py-2 text-right">Ordered</th>
                      <th className="px-3 py-2 text-right">Received</th>
                      <th className="px-3 py-2 text-right font-semibold">Variance</th>
                      <th className="px-3 py-2 text-right">Capital/unit</th>
                      <th className="px-3 py-2 text-right text-red-600">Capital Loss</th>
                      <th className="px-3 py-2 text-right">Retail/unit</th>
                      <th className="px-3 py-2 text-right text-red-600">Retail Loss</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(viewOrder?.items || []).map((item, i) => {
                      const qtyOrdered = item.qty_ordered ?? item.qty;
                      const qtyReceived = item.qty_received ?? item.qty;
                      const variance = qtyOrdered - qtyReceived;
                      const capLoss = variance * item.transfer_capital;
                      const retLoss = variance * item.branch_retail;
                      const hasShortage = variance > 0;
                      return (
                        <tr key={i} className={`border-b border-slate-50 ${hasShortage ? 'bg-red-50/40' : 'hover:bg-slate-50'}`}>
                          <td className="px-3 py-2">
                            <p className="font-medium">{item.product_name}</p>
                            <p className="text-[10px] text-slate-400 font-mono">{item.sku} · {item.category}</p>
                          </td>
                          <td className="px-3 py-2 text-right font-mono">{qtyOrdered} {item.unit}</td>
                          <td className="px-3 py-2 text-right font-mono font-bold">{qtyReceived} {item.unit}</td>
                          <td className={`px-3 py-2 text-right font-mono font-bold ${variance > 0 ? 'text-red-600' : variance < 0 ? 'text-blue-600' : 'text-emerald-600'}`}>
                            {variance === 0 ? '✓ OK' : variance > 0 ? `-${variance}` : `+${Math.abs(variance)}`}
                          </td>
                          <td className="px-3 py-2 text-right font-mono text-slate-500">{formatPHP(item.transfer_capital)}</td>
                          <td className={`px-3 py-2 text-right font-mono font-bold ${capLoss > 0 ? 'text-red-600' : 'text-slate-300'}`}>
                            {capLoss > 0 ? `-${formatPHP(capLoss)}` : '—'}
                          </td>
                          <td className="px-3 py-2 text-right font-mono text-slate-500">{formatPHP(item.branch_retail)}</td>
                          <td className={`px-3 py-2 text-right font-mono font-bold ${retLoss > 0 ? 'text-red-600' : 'text-slate-300'}`}>
                            {retLoss > 0 ? `-${formatPHP(retLoss)}` : '—'}
                          </td>
                        </tr>
                      );
                    })}
                    {/* Totals row */}
                    {(() => {
                      const items = viewOrder?.items || [];
                      const totalCapLoss = items.reduce((s,i) => {
                        const v = (i.qty_ordered ?? i.qty) - (i.qty_received ?? i.qty);
                        return s + (v > 0 ? v * i.transfer_capital : 0);
                      }, 0);
                      const totalRetLoss = items.reduce((s,i) => {
                        const v = (i.qty_ordered ?? i.qty) - (i.qty_received ?? i.qty);
                        return s + (v > 0 ? v * i.branch_retail : 0);
                      }, 0);
                      return (
                        <tr className="bg-slate-100 font-bold border-t-2 border-slate-300 text-sm">
                          <td className="px-3 py-2" colSpan={5}>Expected Losses (shortage)</td>
                          <td className="px-3 py-2 text-right font-mono text-red-700">{totalCapLoss > 0 ? `-${formatPHP(totalCapLoss)}` : '₱0.00'}</td>
                          <td className="px-3 py-2"></td>
                          <td className="px-3 py-2 text-right font-mono text-red-700">{totalRetLoss > 0 ? `-${formatPHP(totalRetLoss)}` : '₱0.00'}</td>
                        </tr>
                      );
                    })()}
                  </tbody>
                </table>
              </div>
            ) : (
              // Standard view for draft/sent
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-white border-b">
                  <tr className="text-xs uppercase text-slate-500">
                    <th className="px-3 py-2 text-left">Product</th>
                    <th className="px-3 py-2 text-center">Qty</th>
                    <th className="px-3 py-2 text-right">Branch Capital</th>
                    <th className="px-3 py-2 text-right">Transfer Capital</th>
                    <th className="px-3 py-2 text-right">Branch Retail</th>
                    <th className="px-3 py-2 text-right">Margin</th>
                  </tr>
                </thead>
                <tbody>
                  {(viewOrder?.items || []).map((item, i) => {
                    const margin = (item.branch_retail - item.transfer_capital);
                    return (
                      <tr key={i} className="border-b border-slate-50 hover:bg-slate-50">
                        <td className="px-3 py-2">
                          <p className="font-medium">{item.product_name}</p>
                          <p className="text-xs text-slate-400 font-mono">{item.sku} · {item.category}</p>
                        </td>
                        <td className="px-3 py-2 text-center font-mono">{item.qty} {item.unit}</td>
                        <td className="px-3 py-2 text-right font-mono text-slate-500">{formatPHP(item.branch_capital)}</td>
                        <td className="px-3 py-2 text-right font-mono font-bold text-blue-700">{formatPHP(item.transfer_capital)}</td>
                        <td className="px-3 py-2 text-right font-mono font-bold text-emerald-700">{formatPHP(item.branch_retail)}</td>
                        <td className={`px-3 py-2 text-right font-mono font-bold ${margin >= 20 ? 'text-emerald-600' : 'text-red-500'}`}>
                          +{formatPHP(margin)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </ScrollArea>
          {viewOrder?.status === 'sent' && (
            <div className="pt-3 border-t flex justify-between">
              <Button variant="outline" onClick={() => printTransferOrder(viewOrder)} data-testid="print-transfer-btn">
                Print Transfer Order
              </Button>
              <Button onClick={() => setReceiveDialog(true)} className="bg-emerald-600 text-white">
                <CheckCircle2 size={15} className="mr-1.5" /> Confirm Receipt
              </Button>
            </div>
          )}
          {viewOrder?.status !== 'sent' && (
            <div className="pt-3 border-t flex justify-end">
              <Button variant="outline" onClick={() => printTransferOrder(viewOrder)} data-testid="print-transfer-btn">
                Print Transfer Order
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Receive Confirmation Dialog ── */}
      <Dialog open={receiveDialog} onOpenChange={v => { setReceiveDialog(v); if (!v) setViewOrder(null); }}>
        <DialogContent className="max-w-3xl max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Manrope' }}>
              Confirm Receipt — {viewOrder?.order_number}
              <span className="text-slate-400 text-sm font-normal ml-2">
                from {branches.find(b => b.id === viewOrder?.from_branch_id)?.name || '?'}
              </span>
            </DialogTitle>
          </DialogHeader>

          {/* Explanation banner */}
          <div className="grid grid-cols-2 gap-3 px-1">
            <div className="flex gap-2 p-2.5 rounded-lg bg-amber-50 border border-amber-200">
              <span className="text-amber-600 font-bold text-lg leading-none">↓</span>
              <div>
                <p className="text-xs font-semibold text-amber-800">Shortage (received &lt; ordered)</p>
                <p className="text-[10px] text-amber-700 mt-0.5">Destination gets only what arrived. Missing qty stays in source. Source branch is notified.</p>
              </div>
            </div>
            <div className="flex gap-2 p-2.5 rounded-lg bg-blue-50 border border-blue-200">
              <span className="text-blue-600 font-bold text-lg leading-none">↑</span>
              <div>
                <p className="text-xs font-semibold text-blue-800">Excess (received &gt; ordered)</p>
                <p className="text-[10px] text-blue-700 mt-0.5">All extra stock goes to destination, deducted from source. Source branch is alerted to verify their stock.</p>
              </div>
            </div>
          </div>

          <ScrollArea className="flex-1 mt-1">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-white border-b">
                <tr className="text-[10px] uppercase text-slate-500">
                  <th className="px-3 py-2 text-left">Product</th>
                  <th className="px-3 py-2 text-right">Ordered</th>
                  <th className="px-3 py-2 text-center w-28">Qty Received</th>
                  <th className="px-3 py-2 text-center">Variance</th>
                  <th className="px-3 py-2 text-right">Capital ₱</th>
                  <th className="px-3 py-2 text-right">Impact</th>
                </tr>
              </thead>
              <tbody>
                {(viewOrder?.items || []).map((item, i) => {
                  const ordered = parseFloat(item.qty) || 0;
                  const received = parseFloat(receiveQtys[item.product_id] ?? ordered) || 0;
                  const variance = received - ordered; // positive = excess, negative = shortage
                  const isShort = variance < 0;
                  const isExcess = variance > 0;
                  const isOk = variance === 0;
                  const impact = Math.abs(variance) * item.transfer_capital;
                  const retImpact = Math.abs(variance) * item.branch_retail;

                  return (
                    <tr key={i} className={`border-b ${isShort ? 'bg-amber-50/50' : isExcess ? 'bg-blue-50/50' : 'hover:bg-slate-50'}`}>
                      <td className="px-3 py-2">
                        <p className="font-medium text-sm">{item.product_name}</p>
                        <p className="text-[10px] text-slate-400">{item.sku} · {item.category}</p>
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-slate-500">{ordered} {item.unit}</td>
                      <td className="px-3 py-2">
                        <Input
                          type="number"
                          min={0}
                          value={receiveQtys[item.product_id] ?? ordered}
                          onChange={e => setReceiveQtys(q => ({ ...q, [item.product_id]: e.target.value }))}
                          className={`h-8 text-sm text-center font-mono w-24 mx-auto block font-bold ${
                            isShort ? 'border-amber-400 bg-amber-50 text-amber-800' :
                            isExcess ? 'border-blue-400 bg-blue-50 text-blue-800' :
                            'border-emerald-300'
                          }`}
                          data-testid={`receive-qty-${item.product_id}`}
                        />
                      </td>
                      <td className="px-3 py-2 text-center">
                        {isOk && <span className="text-xs font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">✓ OK</span>}
                        {isShort && (
                          <span className="text-xs font-bold text-amber-700 bg-amber-100 px-2 py-0.5 rounded-full">
                            ↓ Short {Math.abs(variance)} {item.unit}
                          </span>
                        )}
                        {isExcess && (
                          <span className="text-xs font-bold text-blue-700 bg-blue-100 px-2 py-0.5 rounded-full">
                            ↑ Excess {variance} {item.unit}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-sm text-blue-700">{formatPHP(item.transfer_capital)}</td>
                      <td className="px-3 py-2 text-right">
                        {isOk && <span className="text-slate-300 text-xs">—</span>}
                        {isShort && (
                          <div className="text-right">
                            <p className="text-[11px] font-bold text-amber-700">-{formatPHP(impact)}</p>
                            <p className="text-[9px] text-amber-500">-{formatPHP(retImpact)} retail</p>
                          </div>
                        )}
                        {isExcess && (
                          <div className="text-right">
                            <p className="text-[11px] font-bold text-blue-700">+{formatPHP(impact)}</p>
                            <p className="text-[9px] text-blue-500">+{formatPHP(retImpact)} retail</p>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {/* Live variance summary */}
            {(() => {
              const items = viewOrder?.items || [];
              let totalShortCapital = 0, totalShortRetail = 0, shortCount = 0;
              let totalExcessCapital = 0, totalExcessRetail = 0, excessCount = 0;
              items.forEach(item => {
                const ordered = parseFloat(item.qty) || 0;
                const received = parseFloat(receiveQtys[item.product_id] ?? ordered) || 0;
                const variance = received - ordered;
                if (variance < 0) {
                  shortCount++;
                  totalShortCapital += Math.abs(variance) * item.transfer_capital;
                  totalShortRetail += Math.abs(variance) * item.branch_retail;
                } else if (variance > 0) {
                  excessCount++;
                  totalExcessCapital += variance * item.transfer_capital;
                  totalExcessRetail += variance * item.branch_retail;
                }
              });
              if (!shortCount && !excessCount) return null;
              return (
                <div className="mt-3 mx-3 space-y-2">
                  {shortCount > 0 && (
                    <div className="flex items-center justify-between p-3 rounded-lg bg-amber-50 border border-amber-200">
                      <div>
                        <p className="text-xs font-bold text-amber-800">Shortage Summary — {shortCount} product(s)</p>
                        <p className="text-[10px] text-amber-600 mt-0.5">Missing quantity stays in source branch. Source branch will be notified.</p>
                      </div>
                      <div className="text-right shrink-0 ml-4">
                        <p className="text-sm font-bold text-amber-800">-{formatPHP(totalShortCapital)} capital</p>
                        <p className="text-[11px] text-amber-600">-{formatPHP(totalShortRetail)} retail</p>
                      </div>
                    </div>
                  )}
                  {excessCount > 0 && (
                    <div className="flex items-center justify-between p-3 rounded-lg bg-blue-50 border border-blue-200">
                      <div>
                        <p className="text-xs font-bold text-blue-800">Excess Summary — {excessCount} product(s)</p>
                        <p className="text-[10px] text-blue-600 mt-0.5">Extra stock will be accepted. Source branch will be alerted to verify inventory.</p>
                      </div>
                      <div className="text-right shrink-0 ml-4">
                        <p className="text-sm font-bold text-blue-800">+{formatPHP(totalExcessCapital)} capital</p>
                        <p className="text-[11px] text-blue-600">+{formatPHP(totalExcessRetail)} retail</p>
                      </div>
                    </div>
                  )}
                </div>
              );
            })()}

            {/* Notes field */}
            <div className="mx-3 mt-3 mb-2">
              <label className="text-xs text-slate-500 font-medium block mb-1">Receiving Notes (optional)</label>
              <textarea
                value={receiveNotes}
                onChange={e => setReceiveNotes(e.target.value)}
                placeholder="e.g. 2 boxes of ENERTONE arrived damaged, accepted 8 of 10..."
                rows={2}
                className="w-full text-sm border border-slate-200 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-300 resize-none"
                data-testid="receive-notes"
              />
            </div>
          </ScrollArea>

          <div className="pt-3 border-t flex gap-2 justify-between items-center">
            <p className="text-xs text-slate-400">
              {receiveConfirmStep
                ? 'Quantities differ from the order. Submitting will send to source for confirmation.'
                : 'Inventory and branch prices update automatically on confirm.'}
            </p>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => { setReceiveDialog(false); setReceiveConfirmStep(false); }}>Cancel</Button>
              {receiveConfirmStep ? (
                <>
                  <Button variant="outline" onClick={() => setReceiveConfirmStep(false)}>
                    Back — Edit Quantities
                  </Button>
                  <Button onClick={handleReceive} disabled={receiveSaving}
                    className="bg-amber-600 hover:bg-amber-700 text-white"
                    data-testid="confirm-receive-variance-btn">
                    {receiveSaving ? <RefreshCw size={14} className="animate-spin mr-1.5" /> : <AlertTriangle size={14} className="mr-1.5" />}
                    Yes, Submit Variance for Review
                  </Button>
                </>
              ) : (
                <Button onClick={handleReceive} disabled={receiveSaving} className="bg-emerald-600 hover:bg-emerald-700 text-white"
                  data-testid="confirm-receive-btn">
                  {receiveSaving ? <RefreshCw size={14} className="animate-spin mr-1.5" /> : <CheckCircle2 size={14} className="mr-1.5" />}
                  Confirm Receipt
                </Button>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>
      {/* ── Accept Receipt Dialog ── */}
      <Dialog open={!!acceptDialog} onOpenChange={() => setAcceptDialog(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Manrope' }}>Accept Receipt — {acceptDialog?.order_number}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-sm text-emerald-800">
              <p className="font-semibold mb-1">Accepting will:</p>
              <ul className="list-disc list-inside text-xs space-y-0.5">
                <li>Deduct received quantities from your branch inventory</li>
                <li>Add received quantities to destination branch</li>
                <li>Record the variance in the audit trail</li>
              </ul>
            </div>
            {/* Show variance summary */}
            {acceptDialog?.shortages?.length > 0 && (
              <div className="text-xs p-2 rounded bg-amber-50 border border-amber-200">
                <p className="font-semibold text-amber-800 mb-1">Shortages (destination received less):</p>
                {acceptDialog.shortages.map((s, i) => (
                  <p key={i} className="text-amber-700">{s.product_name}: ordered {s.qty_ordered}, received {s.qty_received} (short {Math.abs(s.variance)})</p>
                ))}
              </div>
            )}
            {acceptDialog?.excesses?.length > 0 && (
              <div className="text-xs p-2 rounded bg-blue-50 border border-blue-200">
                <p className="font-semibold text-blue-800 mb-1">Excesses (destination received more):</p>
                {acceptDialog.excesses.map((e, i) => (
                  <p key={i} className="text-blue-700">{e.product_name}: ordered {e.qty_ordered}, received {e.qty_received} (excess {Math.abs(e.variance)})</p>
                ))}
              </div>
            )}
            <div>
              <label className="text-xs text-slate-500 font-medium block mb-1">Accept note (optional)</label>
              <input type="text" placeholder="e.g. Verified with packing list, shortfall noted..."
                className="w-full text-sm border border-slate-200 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-300"
                id="accept-note-input" data-testid="accept-note" />
            </div>
          </div>
          <div className="flex gap-2 justify-end pt-2 border-t mt-2">
            <Button variant="outline" onClick={() => setAcceptDialog(null)}>Cancel</Button>
            <Button onClick={() => {
              const note = document.getElementById('accept-note-input')?.value || '';
              handleAcceptReceipt(acceptDialog.id, note);
            }} disabled={actionSaving} className="bg-emerald-600 text-white" data-testid="confirm-accept-btn">
              {actionSaving ? <RefreshCw size={14} className="animate-spin mr-1.5" /> : <CheckCircle2 size={14} className="mr-1.5" />}
              Accept & Update Inventory
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── Dispute Receipt Dialog ── */}
      <Dialog open={!!disputeDialog} onOpenChange={() => { setDisputeDialog(null); setDisputeNote(''); }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Manrope' }}>Dispute Receipt — {disputeDialog?.order_number}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-800">
              <p className="font-semibold mb-1">Disputing will:</p>
              <ul className="list-disc list-inside text-xs space-y-0.5">
                <li>NOT update any inventory</li>
                <li>Notify the destination branch to re-count</li>
                <li>Allow them to re-submit corrected quantities</li>
              </ul>
            </div>
            <div>
              <label className="text-xs text-slate-500 font-medium block mb-1">Reason for dispute <span className="text-red-500">*</span></label>
              <textarea
                value={disputeNote}
                onChange={e => setDisputeNote(e.target.value)}
                placeholder="e.g. Our records show we packed 10 cases, please re-count..."
                rows={3}
                className="w-full text-sm border border-slate-200 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-red-300 resize-none"
                data-testid="dispute-note"
              />
            </div>
          </div>
          <div className="flex gap-2 justify-end pt-2 border-t mt-2">
            <Button variant="outline" onClick={() => { setDisputeDialog(null); setDisputeNote(''); }}>Cancel</Button>
            <Button onClick={handleDisputeReceipt} disabled={actionSaving || !disputeNote.trim()}
              className="bg-red-600 text-white" data-testid="confirm-dispute-btn">
              {actionSaving ? <RefreshCw size={14} className="animate-spin mr-1.5" /> : <XCircle size={14} className="mr-1.5" />}
              Send Dispute
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
