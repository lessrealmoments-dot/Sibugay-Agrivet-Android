import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Lock, ArrowRight, CheckCircle, Zap } from 'lucide-react';
import { Button } from './ui/button';

// Maps each feature flag key to display metadata
const FEATURE_META = {
  purchase_orders: {
    name: 'Purchase Orders',
    icon: '📦',
    description: 'Full PO workflow with receive, edit, reopen, and complete audit trail.',
    plan_required: 'standard',
    plan_label: 'Standard',
    unlocks: ['Purchase Orders', 'Pay Supplier workflow', 'Accounts Payable tracking'],
  },
  supplier_management: {
    name: 'Supplier Management',
    icon: '🚛',
    description: 'Supplier profiles, purchase history, and accounts payable management.',
    plan_required: 'standard',
    plan_label: 'Standard',
    unlocks: ['Supplier directory', 'Purchase history', 'AP balance tracking'],
  },
  employee_management: {
    name: 'Employee & Cash Advances',
    icon: '👥',
    description: 'Employee profiles, cash advance requests, and disbursement tracking.',
    plan_required: 'standard',
    plan_label: 'Standard',
    unlocks: ['Employee profiles', 'Cash advance requests', 'Advance history'],
  },
  full_fund_management: {
    name: '4-Wallet Fund Management',
    icon: '💰',
    description: 'Cashier, Safe, Digital (GCash/Maya), and Bank wallets — all tracked separately.',
    plan_required: 'standard',
    plan_label: 'Standard',
    unlocks: ['Cashier & Safe wallets', 'GCash / Maya tracking', 'Bank reconciliation'],
  },
  branch_transfers: {
    name: 'Branch Transfers',
    icon: '🔀',
    description: 'Transfer stock between branches with full cost and capital tracking.',
    plan_required: 'standard',
    plan_label: 'Standard',
    unlocks: ['Stock transfers between branches', 'Transfer capital tracking', 'Shortage management'],
  },
  audit_center: {
    name: 'Audit Center',
    icon: '🔍',
    description: 'Audit scoring, discrepancy detection, and rule-based insights across all modules.',
    plan_required: 'standard',
    plan_label: 'Standard',
    unlocks: ['Transaction audit logs', 'Discrepancy detection', 'User activity tracking'],
  },
  advanced_reports: {
    name: 'Advanced Reports',
    icon: '📊',
    description: 'AR aging, inventory movement, income statements, and financial summaries.',
    plan_required: 'standard',
    plan_label: 'Standard',
    unlocks: ['AR aging report', 'Inventory movement', 'Income statements'],
  },
  granular_permissions: {
    name: 'Granular Role Permissions',
    icon: '🛡️',
    description: 'Custom per-user access control for every module and action in the system.',
    plan_required: 'pro',
    plan_label: 'Pro',
    unlocks: ['Per-module access control', 'Custom role templates', 'Action-level permissions'],
  },
  two_fa: {
    name: '2FA Security (TOTP)',
    icon: '🔐',
    description: 'Google Authenticator two-factor authentication for admin accounts.',
    plan_required: 'pro',
    plan_label: 'Pro',
    unlocks: ['Google Authenticator', 'TOTP for admin accounts', 'Backup recovery codes'],
  },
};

const PLAN_COLORS = {
  standard: { bg: 'bg-emerald-50', border: 'border-emerald-200', badge: 'bg-emerald-600', text: 'text-emerald-700', icon: 'text-emerald-600' },
  pro: { bg: 'bg-indigo-50', border: 'border-indigo-200', badge: 'bg-indigo-600', text: 'text-indigo-700', icon: 'text-indigo-600' },
};

export default function FeatureGate({ featureKey, children }) {
  const { user } = useAuth();
  const navigate = useNavigate();

  // Always allow super admin (platform admin only, not org admin)
  if (user?.is_super_admin) {
    return children;
  }

  const features = user?.subscription?.features;
  const isEnabled = !features || features[featureKey] !== false;

  if (isEnabled) return children;

  const meta = FEATURE_META[featureKey] || {
    name: 'Premium Feature',
    description: 'This feature requires a higher plan.',
    plan_label: 'Standard',
    plan_required: 'standard',
    unlocks: [],
    icon: '⭐',
  };

  const colors = PLAN_COLORS[meta.plan_required] || PLAN_COLORS.standard;
  const planName = user?.subscription?.plan ?? 'basic';

  return (
    <div className="flex items-center justify-center min-h-[60vh] px-4" data-testid={`feature-gate-${featureKey}`}>
      <div className={`max-w-lg w-full rounded-2xl border-2 ${colors.border} ${colors.bg} p-8 text-center shadow-sm`}>
        {/* Lock Badge */}
        <div className="flex justify-center mb-5">
          <div className="relative">
            <div className={`w-16 h-16 rounded-2xl bg-white shadow-md flex items-center justify-center text-3xl`}>
              {meta.icon}
            </div>
            <div className="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-slate-700 flex items-center justify-center">
              <Lock size={12} className="text-white" />
            </div>
          </div>
        </div>

        {/* Plan Badge */}
        <div className="flex justify-center mb-4">
          <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold text-white ${colors.badge}`}>
            <Zap size={11} />
            {meta.plan_label} Plan Feature
          </span>
        </div>

        <h2 className="text-xl font-bold text-slate-800 mb-2" style={{ fontFamily: 'Manrope' }}>
          {meta.name}
        </h2>
        <p className="text-sm text-slate-500 mb-6 leading-relaxed">
          {meta.description}
        </p>

        {/* What you'll unlock */}
        <div className="bg-white rounded-xl border border-slate-100 p-4 mb-6 text-left">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
            What you'll unlock
          </p>
          <ul className="space-y-2">
            {meta.unlocks.map((item) => (
              <li key={item} className="flex items-center gap-2 text-sm text-slate-700">
                <CheckCircle size={14} className={`${colors.icon} shrink-0`} />
                {item}
              </li>
            ))}
          </ul>
        </div>

        {/* Current plan info */}
        <p className="text-xs text-slate-400 mb-4">
          You're on the <span className="font-semibold capitalize">{planName}</span> plan.{' '}
          Upgrade to <span className={`font-bold ${colors.text}`}>{meta.plan_label}</span> to unlock this.
        </p>

        {/* CTA buttons */}
        <div className="flex gap-3 justify-center">
          <Button
            data-testid={`upgrade-cta-${featureKey}`}
            onClick={() => navigate('/upgrade')}
            className={`${colors.badge} hover:opacity-90 text-white font-semibold px-6`}
          >
            Upgrade to {meta.plan_label}
            <ArrowRight size={14} className="ml-1.5" />
          </Button>
          <Button variant="outline" onClick={() => navigate('/dashboard')} className="text-slate-600">
            Back to Dashboard
          </Button>
        </div>
      </div>
    </div>
  );
}
