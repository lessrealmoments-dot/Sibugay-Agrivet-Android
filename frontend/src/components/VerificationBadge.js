/**
 * VerificationBadge — shows verified/unverified/discrepancy status on transactions.
 */
import { ShieldCheck, ShieldAlert, Shield } from 'lucide-react';

export default function VerificationBadge({ doc, compact = false }) {
  if (!doc) return null;

  const verified = doc.verified;
  const status = doc.verification_status; // 'clean' | 'discrepancy' | 'resolved'

  if (!verified) {
    if (compact) return (
      <span className="inline-flex items-center gap-1 text-[10px] text-slate-400">
        <Shield size={10} /> Unverified
      </span>
    );
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-400">
        <Shield size={11} /> Unverified
      </span>
    );
  }

  if (status === 'discrepancy') {
    const badge = (
      <span className={`inline-flex items-center gap-1 ${compact ? 'text-[10px] text-amber-600' : 'px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200'}`}>
        <ShieldAlert size={compact ? 10 : 11} />
        {!compact && 'Verified ⚠ Discrepancy'}
        {compact && 'Discrepancy'}
      </span>
    );
    return badge;
  }

  if (status === 'resolved') {
    return (
      <span className={`inline-flex items-center gap-1 ${compact ? 'text-[10px] text-blue-600' : 'px-2 py-0.5 rounded-full text-[11px] font-medium bg-blue-50 text-blue-700 border border-blue-200'}`}>
        <ShieldCheck size={compact ? 10 : 11} />
        {!compact && 'Verified — Resolved'}
        {compact && 'Resolved'}
      </span>
    );
  }

  // Clean
  return (
    <span className={`inline-flex items-center gap-1 ${compact ? 'text-[10px] text-emerald-600' : 'px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200'}`}>
      <ShieldCheck size={compact ? 10 : 11} />
      {!compact && `Verified by ${doc.verified_by_name || 'Admin'}`}
      {compact && 'Verified'}
    </span>
  );
}
