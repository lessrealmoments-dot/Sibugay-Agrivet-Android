import { useState, useEffect, useCallback, useRef } from 'react';
import { AlertTriangle, Calendar, ChevronDown, Check } from 'lucide-react';
import { api } from '../contexts/AuthContext';

const localToday = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

export function UnclosedDaysBanner({ branchId, currentDate, onDateSelect, className = '' }) {
  const [unclosedDays, setUnclosedDays] = useState([]);
  const [lastCloseDate, setLastCloseDate] = useState(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const dropdownRef = useRef(null);

  const today = localToday();
  // Use the parent-controlled date (order_date). Fall back to today if not passed.
  const selectedDate = currentDate || today;

  const fetchUnclosedDays = useCallback(async () => {
    if (!branchId) return;
    try {
      setLoading(true);
      const res = await api.get('/daily-close/unclosed-days', { params: { branch_id: branchId } });
      const days = res.data.unclosed_days || [];
      setUnclosedDays(days);
      setLastCloseDate(res.data.last_close_date);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, [branchId]);

  useEffect(() => { fetchUnclosedDays(); }, [fetchUnclosedDays]);

  // Close dropdown on click outside
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const handleDateSelect = (date) => {
    setOpen(false);
    if (onDateSelect) onDateSelect(date);
  };

  // Filter out today from the "backlog" — today is always current
  const pastUnclosed = unclosedDays.filter(d => d.date < today);

  // Always show the banner if either:
  // 1. There are unclosed past days
  // 2. The user has manually set a past sale date
  const isEncodingPastDate = selectedDate < today;
  if (loading) return null;
  if (pastUnclosed.length === 0 && !isEncodingPastDate) return null;

  return (
    <div className={`rounded-lg border ${className}`}
      style={{ borderColor: isEncodingPastDate ? '#d97706' : '#f59e0b', background: isEncodingPastDate ? '#fffbeb' : '#fefce8' }}>
      {/* Warning header */}
      <div className="flex items-center justify-between px-4 py-2.5 gap-3 rounded-t-lg"
        style={{ background: isEncodingPastDate ? '#fef3c7' : '#fef9c3' }}>
        <div className="flex items-center gap-2 min-w-0">
          <AlertTriangle size={16} className="text-amber-600 flex-shrink-0" />
          <span className="text-sm font-medium text-amber-800" data-testid="unclosed-days-warning">
            {isEncodingPastDate
              ? <>Encoding for <strong>{selectedDate}</strong> — sale will be saved to this date</>
              : <>{pastUnclosed.length} unclosed day{pastUnclosed.length > 1 ? 's' : ''} detected
                  <span className="font-normal text-amber-600 ml-1">
                    ({pastUnclosed[0].date}{pastUnclosed.length > 1 ? ` to ${pastUnclosed[pastUnclosed.length - 1].date}` : ''})
                  </span>
                </>
            }
          </span>
        </div>

        {/* Date selector — only show when there are unclosed days to pick from */}
        {pastUnclosed.length > 0 && (
          <div className="relative flex-shrink-0" ref={dropdownRef}>
            <button
              onClick={() => setOpen(!open)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium border transition-colors"
              style={{
                background: isEncodingPastDate ? '#f59e0b' : '#fff',
                color: isEncodingPastDate ? '#fff' : '#92400e',
                borderColor: isEncodingPastDate ? '#d97706' : '#fbbf24'
              }}
              data-testid="unclosed-date-selector"
            >
              <Calendar size={14} />
              <span>Switch date</span>
              <ChevronDown size={14} />
            </button>

            {open && (
              <div className="absolute right-0 top-full mt-1 bg-white border border-amber-200 rounded-lg shadow-lg z-50 min-w-[200px] max-h-[280px] overflow-y-auto"
                data-testid="unclosed-date-dropdown">
                {/* Today option */}
                <button
                  onClick={() => handleDateSelect(today)}
                  className="w-full flex items-center justify-between px-3 py-2 text-sm hover:bg-amber-50 transition-colors border-b border-amber-100"
                >
                  <span className="font-medium text-slate-700">Today ({today})</span>
                  {selectedDate === today && <Check size={14} className="text-green-600" />}
                </button>
                {/* Unclosed past days */}
                <div className="px-2 py-1.5">
                  <span className="text-[10px] uppercase tracking-wider text-amber-500 font-semibold">Unclosed Days</span>
                </div>
                {pastUnclosed.map(day => (
                  <button
                    key={day.date}
                    onClick={() => handleDateSelect(day.date)}
                    className="w-full flex items-center justify-between px-3 py-2 text-sm hover:bg-amber-50 transition-colors"
                    data-testid={`select-date-${day.date}`}
                  >
                    <div className="text-left">
                      <span className={`font-medium ${selectedDate === day.date ? 'text-amber-700' : 'text-slate-700'}`}>
                        {day.date}
                      </span>
                      <span className="ml-2 text-xs text-slate-400">
                        {day.sales_count} sales, {day.expense_count} exp
                      </span>
                    </div>
                    {selectedDate === day.date && <Check size={14} className="text-amber-600" />}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Subtext when encoding a past date */}
      {isEncodingPastDate && (
        <div className="px-4 py-1.5 text-xs text-amber-700 flex items-center justify-between" style={{ background: '#fef3c7' }}
          data-testid="past-date-indicator">
          <span>Change <strong>Sale Date</strong> back to today when done.</span>
          <button
            onClick={() => handleDateSelect(today)}
            className="text-xs font-semibold underline text-amber-800 hover:text-amber-900"
          >
            Reset to today
          </button>
        </div>
      )}
    </div>
  );
}
