import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../contexts/AuthContext';
import { Search, FileText, Truck, Receipt, ArrowLeftRight, Wallet, X, Loader2 } from 'lucide-react';
import InvoiceDetailModal from './InvoiceDetailModal';

const TYPE_ICONS = {
  invoice: FileText,
  purchase_order: Truck,
  expense: Receipt,
  internal_invoice: ArrowLeftRight,
  fund_transfer: Wallet,
};

const TYPE_LABELS = {
  invoice: 'Invoice',
  purchase_order: 'PO',
  expense: 'Expense',
  internal_invoice: 'Internal',
  fund_transfer: 'Transfer',
};

const TYPE_COLORS = {
  invoice: 'text-blue-600',
  purchase_order: 'text-amber-600',
  expense: 'text-red-600',
  internal_invoice: 'text-purple-600',
  fund_transfer: 'text-emerald-600',
};

export default function QuickSearch() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [invoiceModal, setInvoiceModal] = useState({ open: false, number: '', expenseId: '' });
  const inputRef = useRef(null);
  const containerRef = useRef(null);
  const navigate = useNavigate();
  const debounceRef = useRef(null);

  // Close on outside click
  useEffect(() => {
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Keyboard shortcut: Ctrl+K / Cmd+K
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen(true);
        setTimeout(() => inputRef.current?.focus(), 50);
      }
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  const search = useCallback(async (q) => {
    if (!q || q.length < 2) { setResults([]); return; }
    setLoading(true);
    try {
      const res = await api.get('/search/transactions', { params: { q, limit: 8 } });
      setResults(res.data.results || []);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleChange = (e) => {
    const val = e.target.value;
    setQuery(val);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(val), 300);
  };

  const handleResultClick = (item) => {
    setOpen(false);
    setQuery('');
    setResults([]);
    if ((item.type === 'invoice' || item.type === 'purchase_order') && item.number) {
      setInvoiceModal({ open: true, number: item.number, expenseId: '' });
    } else if (item.type === 'expense' && item.id) {
      setInvoiceModal({ open: true, number: '', expenseId: item.id });
    } else if (item.type === 'internal_invoice') navigate('/internal-invoices');
    else if (item.type === 'fund_transfer') navigate('/fund-management');
  };

  const goToAdvanced = () => {
    setOpen(false);
    navigate(`/find-transaction${query ? `?q=${encodeURIComponent(query)}` : ''}`);
    setQuery('');
    setResults([]);
  };

  if (!open) {
    return (
      <>
        <button
          data-testid="quick-search-trigger"
          onClick={() => { setOpen(true); setTimeout(() => inputRef.current?.focus(), 50); }}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-200 bg-slate-50 hover:bg-slate-100 transition-colors text-sm text-slate-500"
        >
          <Search size={14} />
          <span className="hidden sm:inline">Find...</span>
          <kbd className="hidden md:inline text-[10px] bg-white border border-slate-200 rounded px-1.5 py-0.5 text-slate-400 font-mono">
            Ctrl+K
          </kbd>
        </button>
        <InvoiceDetailModal
          open={invoiceModal.open}
          onOpenChange={(o) => setInvoiceModal({ open: o, number: o ? invoiceModal.number : '', expenseId: o ? invoiceModal.expenseId : '' })}
          invoiceNumber={invoiceModal.number}
          expenseId={invoiceModal.expenseId}
        />
      </>
    );
  }

  return (
    <div ref={containerRef} className="relative" data-testid="quick-search-container">
      <div className="flex items-center gap-2 bg-white border border-slate-300 rounded-lg shadow-lg px-3 py-1.5 min-w-[280px] sm:min-w-[360px]">
        <Search size={16} className="text-slate-400 shrink-0" />
        <input
          ref={inputRef}
          data-testid="quick-search-input"
          value={query}
          onChange={handleChange}
          placeholder="Search receipts, POs, expenses..."
          className="flex-1 text-sm outline-none bg-transparent text-slate-800 placeholder:text-slate-400"
          onKeyDown={(e) => {
            if (e.key === 'Enter') goToAdvanced();
          }}
        />
        {loading && <Loader2 size={14} className="animate-spin text-slate-400" />}
        <button onClick={() => { setOpen(false); setQuery(''); setResults([]); }} className="text-slate-400 hover:text-slate-600">
          <X size={14} />
        </button>
      </div>

      {/* Dropdown Results */}
      {(results.length > 0 || (query.length >= 2 && !loading)) && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-xl z-50 max-h-[380px] overflow-y-auto"
          data-testid="quick-search-results">
          {results.map((item) => {
            const Icon = TYPE_ICONS[item.type] || FileText;
            const color = TYPE_COLORS[item.type] || 'text-slate-600';
            return (
              <button
                key={`${item.type}-${item.id}`}
                onClick={() => handleResultClick(item)}
                className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-slate-50 border-b border-slate-50 text-left transition-colors"
              >
                <Icon size={14} className={color} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    {item.number && <span className="font-mono text-xs font-semibold text-slate-700">{item.number}</span>}
                    <span className={`text-[10px] ${color}`}>{TYPE_LABELS[item.type]}</span>
                  </div>
                  <p className="text-xs text-slate-500 truncate">{item.title}</p>
                </div>
                <span className="text-xs font-medium text-slate-700 shrink-0">
                  {typeof item.amount === 'number' ? `₱${item.amount.toLocaleString()}` : ''}
                </span>
              </button>
            );
          })}
          {results.length === 0 && query.length >= 2 && !loading && (
            <div className="px-3 py-4 text-center text-sm text-slate-400">
              No results found
            </div>
          )}
          <button
            data-testid="quick-search-advanced-link"
            onClick={goToAdvanced}
            className="w-full text-center py-2.5 text-xs text-[#1A4D2E] font-medium hover:bg-slate-50 border-t border-slate-100"
          >
            Advanced Search →
          </button>
        </div>
      )}
      <InvoiceDetailModal
        open={invoiceModal.open}
        onOpenChange={(o) => setInvoiceModal({ open: o, number: o ? invoiceModal.number : '', expenseId: o ? invoiceModal.expenseId : '' })}
        invoiceNumber={invoiceModal.number}
        expenseId={invoiceModal.expenseId}
      />
    </div>
  );
}
