/**
 * NotificationBell — navigates to the full notification center page.
 * Shows unread count badge. Auto-polls every 30s for count updates.
 */
import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, useAuth } from '../contexts/AuthContext';
import { Bell } from 'lucide-react';

export default function NotificationBell() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [unreadCount, setUnreadCount] = useState(0);

  const isAdmin = user?.role === 'admin' || user?.role === 'owner';

  const fetchCount = useCallback(async () => {
    if (!isAdmin) return;
    try {
      const res = await api.get('/notifications', { params: { limit: 1 } });
      setUnreadCount(res.data.unread_count || 0);
    } catch { /* silent */ }
  }, [isAdmin]);

  useEffect(() => {
    if (!isAdmin) return;
    fetchCount();
    const interval = setInterval(fetchCount, 30000);
    return () => clearInterval(interval);
  }, [fetchCount, isAdmin]);

  if (!isAdmin) return null;

  return (
    <button
      onClick={() => navigate('/notifications')}
      data-testid="notification-bell"
      className="relative p-1.5 rounded-md hover:bg-slate-100 transition-colors"
      aria-label="Notification Center"
    >
      <Bell size={18} className={unreadCount > 0 ? 'text-slate-700' : 'text-slate-400'} />
      {unreadCount > 0 && (
        <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center leading-none">
          {unreadCount > 99 ? '99+' : unreadCount}
        </span>
      )}
    </button>
  );
}
