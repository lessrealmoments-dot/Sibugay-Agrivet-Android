/**
 * NotificationBell
 * In-app notification center for admin/owner users.
 * Shows unread count badge, dropdown with recent notifications.
 * Auto-polls every 30s.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { api, useAuth } from '../contexts/AuthContext';
import { Bell, Check, CheckCheck, Zap, CreditCard, Briefcase, Shield, AlertTriangle } from 'lucide-react';

const TYPE_ICONS = {
  credit_sale:            { icon: CreditCard,    color: 'text-blue-500',   bg: 'bg-blue-50'   },
  employee_advance:       { icon: Briefcase,     color: 'text-amber-500',  bg: 'bg-amber-50'  },
  price_override:         { icon: Zap,           color: 'text-violet-500', bg: 'bg-violet-50' },
  pin_used:               { icon: Shield,        color: 'text-slate-500',  bg: 'bg-slate-50'  },
  security_alert:         { icon: AlertTriangle, color: 'text-red-600',    bg: 'bg-red-50'    },
};

function timeAgo(isoStr) {
  const diff = Date.now() - new Date(isoStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return new Date(isoStr).toLocaleDateString();
}

export default function NotificationBell() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const dropdownRef = useRef(null);

  const isAdmin = user?.role === 'admin';

  const fetchNotifications = useCallback(async () => {
    if (!isAdmin) return;
    try {
      const res = await api.get('/notifications', { params: { limit: 20 } });
      setNotifications(res.data.notifications || []);
      setUnreadCount(res.data.unread_count || 0);
    } catch { /* silent */ }
  }, [isAdmin]);

  // Initial load + auto-poll every 30s
  useEffect(() => {
    if (!isAdmin) return;
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, [fetchNotifications, isAdmin]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handle = (e) => { if (dropdownRef.current && !dropdownRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, [open]);

  // Only render for admin/owner
  if (!isAdmin) return null;

  const markRead = async (id) => {
    await api.put(`/notifications/${id}/read`);
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
    setUnreadCount(c => Math.max(0, c - 1));
  };

  const markAllRead = async () => {
    await api.put('/notifications/mark-all-read');
    setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
    setUnreadCount(0);
  };

  const handleOpen = () => {
    setOpen(o => !o);
    if (!open) fetchNotifications(); // refresh on open
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell button */}
      <button
        onClick={handleOpen}
        data-testid="notification-bell"
        className="relative p-1.5 rounded-md hover:bg-slate-100 transition-colors"
        aria-label="Notifications"
      >
        <Bell size={18} className={unreadCount > 0 ? 'text-slate-700' : 'text-slate-400'} />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center leading-none">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute right-0 top-full mt-2 w-96 bg-white rounded-xl shadow-2xl border border-slate-200 z-50 overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 bg-slate-50">
            <div className="flex items-center gap-2">
              <Bell size={15} className="text-slate-600" />
              <span className="font-semibold text-sm text-slate-700">Notifications</span>
              {unreadCount > 0 && (
                <span className="px-1.5 py-0.5 bg-red-100 text-red-600 text-[10px] font-bold rounded-full">
                  {unreadCount} new
                </span>
              )}
            </div>
            {unreadCount > 0 && (
              <button onClick={markAllRead}
                className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium">
                <CheckCheck size={13} /> Mark all read
              </button>
            )}
          </div>

          {/* List */}
          <div className="max-h-96 overflow-y-auto divide-y divide-slate-50">
            {notifications.length === 0 ? (
              <div className="py-10 text-center text-slate-400">
                <Bell size={28} className="mx-auto mb-2 opacity-30" />
                <p className="text-sm">No notifications yet</p>
              </div>
            ) : (
              notifications.map(n => {
                const config = TYPE_ICONS[n.context_type] || TYPE_ICONS.pin_used;
                const Icon = config.icon;
                return (
                  <div key={n.id}
                    onClick={() => !n.is_read && markRead(n.id)}
                    data-testid={`notification-${n.id}`}
                    className={`flex gap-3 px-4 py-3 transition-colors ${
                      n.is_read ? 'bg-white' : 'bg-blue-50/40 hover:bg-blue-50/60 cursor-pointer'
                    }`}
                  >
                    {/* Icon */}
                    <div className={`w-8 h-8 rounded-full ${config.bg} flex items-center justify-center shrink-0 mt-0.5`}>
                      <Icon size={14} className={config.color} />
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <p className={`text-sm leading-snug ${n.is_read ? 'text-slate-600' : 'text-slate-800 font-medium'}`}>
                          {n.message}
                        </p>
                        {!n.is_read && (
                          <div className="w-2 h-2 rounded-full bg-blue-500 shrink-0 mt-1.5" />
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-[11px] text-slate-400">{timeAgo(n.created_at)}</span>
                        {n.branch_name && (
                          <>
                            <span className="text-slate-300">·</span>
                            <span className="text-[11px] text-slate-400">{n.branch_name}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Footer */}
          {notifications.length > 0 && (
            <div className="px-4 py-2 border-t border-slate-100 bg-slate-50 text-center">
              <span className="text-xs text-slate-400">Showing last {notifications.length} notifications</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
