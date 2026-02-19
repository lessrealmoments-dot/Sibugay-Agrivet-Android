import { useState, useEffect, useRef } from 'react';
import { api, useAuth } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Badge } from './ui/badge';
import { Search, Package, ArrowUp, ArrowDown } from 'lucide-react';

export default function SmartProductSearch({ onSelect, branchId }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const inputRef = useRef(null);
  const dropdownRef = useRef(null);
  const debounceRef = useRef(null);

  useEffect(() => {
    if (!query || query.length < 1) { setResults([]); setOpen(false); return; }
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await api.get('/products/search-detail', { params: { q: query, branch_id: branchId } });
        setResults(res.data);
        setOpen(res.data.length > 0);
        setActiveIndex(-1);
      } catch { setResults([]); }
    }, 200);
    return () => clearTimeout(debounceRef.current);
  }, [query, branchId]);

  const handleKeyDown = (e) => {
    if (!open || !results.length) {
      if (e.key === 'Escape') { setOpen(false); }
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex(prev => Math.min(prev + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex(prev => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter' && activeIndex >= 0) {
      e.preventDefault();
      selectProduct(results[activeIndex]);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  const selectProduct = (product) => {
    onSelect(product);
    setQuery('');
    setResults([]);
    setOpen(false);
    setActiveIndex(-1);
    inputRef.current?.focus();
  };

  useEffect(() => {
    if (activeIndex >= 0 && dropdownRef.current) {
      const item = dropdownRef.current.children[activeIndex];
      item?.scrollIntoView({ block: 'nearest' });
    }
  }, [activeIndex]);

  return (
    <div className="relative" data-testid="smart-product-search">
      <div className="relative">
        <Search size={14} className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          ref={inputRef}
          data-testid="product-search-input"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => { if (results.length) setOpen(true); }}
          onBlur={() => setTimeout(() => setOpen(false), 200)}
          placeholder="Type product name or scan barcode..."
          className="w-full h-9 pl-8 pr-3 text-sm border border-slate-200 rounded-md focus:outline-none focus:ring-2 focus:ring-[#1A4D2E]/30 focus:border-[#1A4D2E] bg-white"
          autoComplete="off"
        />
      </div>

      {open && results.length > 0 && (
        <div ref={dropdownRef} className="absolute z-50 top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-xl max-h-[400px] overflow-y-auto"
          data-testid="search-results-dropdown">
          {results.map((p, i) => (
            <div
              key={p.id}
              data-testid={`search-result-${p.id}`}
              onClick={() => selectProduct(p)}
              className={`px-3 py-2.5 cursor-pointer border-b border-slate-50 last:border-0 transition-colors ${
                i === activeIndex ? 'bg-[#1A4D2E]/5 border-l-2 border-l-[#1A4D2E]' : 'hover:bg-slate-50'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="font-medium text-sm truncate">{p.name}</span>
                  <span className="text-[10px] font-mono text-slate-400 shrink-0">{p.sku}</span>
                  {p.is_repack && <Badge className="text-[9px] bg-amber-100 text-amber-700 shrink-0">R</Badge>}
                </div>
                <span className="text-sm font-bold text-[#1A4D2E] shrink-0 ml-2">{formatPHP(p.prices?.retail)}</span>
              </div>

              {/* Detail row - always visible when active */}
              {i === activeIndex && (
                <div className="mt-2 p-2.5 rounded-md bg-slate-50 border border-slate-100 text-xs animate-fadeIn">
                  <div className="grid grid-cols-4 gap-3">
                    <div>
                      <span className="text-slate-400 block">Retail</span>
                      <span className="font-bold text-[#1A4D2E]">{formatPHP(p.prices?.retail)}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block">Capital</span>
                      <span className="font-bold">{formatPHP(p.cost_price)}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block">Available</span>
                      <span className={`font-bold ${p.available <= 0 ? 'text-red-600' : ''}`}>{p.available?.toFixed(1)} {p.unit}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block">Reserved / Coming</span>
                      <span className="font-bold">{p.reserved} / {p.coming}</span>
                    </div>
                  </div>
                  {p.is_repack && p.parent_name && (
                    <div className="mt-2 pt-2 border-t border-slate-200 flex items-center gap-2">
                      <Package size={12} className="text-amber-500" />
                      <span className="text-slate-500">Parent: <b>{p.parent_name}</b></span>
                      <span className="text-slate-400">Stock: <b>{p.parent_stock?.toFixed(1)} {p.parent_unit}</b></span>
                    </div>
                  )}
                </div>
              )}

              {/* Compact info when not active */}
              {i !== activeIndex && (
                <div className="flex gap-3 mt-0.5 text-[11px] text-slate-400">
                  <span>Capital: {formatPHP(p.cost_price)}</span>
                  <span>Avail: {p.available?.toFixed(0)} {p.unit}</span>
                  {p.reserved > 0 && <span className="text-amber-500">Rsv: {p.reserved}</span>}
                  {p.is_repack && <span className="text-amber-600">Parent: {p.parent_stock?.toFixed(0)} {p.parent_unit}</span>}
                </div>
              )}
            </div>
          ))}
          <div className="px-3 py-1.5 bg-slate-50 text-[10px] text-slate-400 flex items-center gap-3 border-t">
            <span><ArrowUp size={10} className="inline" /><ArrowDown size={10} className="inline" /> navigate</span>
            <span>Enter to select</span>
            <span>Esc to close</span>
          </div>
        </div>
      )}
    </div>
  );
}
