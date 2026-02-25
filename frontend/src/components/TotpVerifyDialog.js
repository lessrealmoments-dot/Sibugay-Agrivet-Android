import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { api } from '../contexts/AuthContext';
import { Shield, Lock, RefreshCw, KeyRound, Hash } from 'lucide-react';
import { toast } from 'sonner';

/**
 * TotpVerifyDialog — admin verification dialog with 3 modes.
 *
 * Modes (in order of preference):
 *  1. "totp"     — Time-based OTP from Google Authenticator (one-use, for remote approval)
 *  2. "pin"      — Owner PIN set in Settings > Audit Setup (static, for in-person approval)
 *  3. "password" — Admin login password (fallback)
 *
 * Props:
 *   open          – boolean
 *   onOpenChange  – fn(bool)
 *   onVerified    – fn({ manager_name, mode_used })  called on success
 *   context       – string description of what is being authorized (for audit log)
 *   title         – optional dialog title override
 */
export function TotpVerifyDialog({
  open,
  onOpenChange,
  onVerified,
  context = '',
  title = 'Admin Authorization Required',
}) {
  const [mode, setMode] = useState('pin');   // 'totp' | 'pin' | 'password'
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);

  const reset = () => { setCode(''); setMode('pin'); };

  const handleVerify = async () => {
    if (!code) { toast.error('Enter a code'); return; }
    if (mode === 'totp' && code.length !== 6) { toast.error('Enter 6-digit code'); return; }
    setLoading(true);
    try {
      const res = await api.post('/auth/verify-admin-action', { mode, code, context });
      if (res.data.valid) {
        onVerified({ manager_name: res.data.manager_name, mode_used: res.data.mode_used });
        reset();
        onOpenChange(false);
      } else {
        toast.error(res.data.error || 'Invalid — try again');
      }
    } catch {
      toast.error('Verification failed');
    }
    setLoading(false);
  };

  const MODE_TABS = [
    { key: 'pin',      icon: <Hash size={13} />,      label: 'Owner PIN' },
    { key: 'totp',     icon: <Shield size={13} />,    label: 'Authenticator' },
    { key: 'password', icon: <KeyRound size={13} />,  label: 'Password' },
  ];

  return (
    <Dialog open={open} onOpenChange={v => { if (!v) reset(); onOpenChange(v); }}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
            <Shield size={18} className="text-amber-600" /> {title}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 mt-2">

          {/* Mode selector tabs */}
          <div className="flex rounded-lg border border-slate-200 overflow-hidden text-xs">
            {MODE_TABS.map(tab => (
              <button
                key={tab.key}
                onClick={() => { setMode(tab.key); setCode(''); }}
                className={`flex-1 flex items-center justify-center gap-1.5 py-2 font-medium transition-colors ${
                  mode === tab.key
                    ? 'bg-amber-50 text-amber-700 border-b-2 border-amber-500'
                    : 'text-slate-500 hover:bg-slate-50'
                }`}
              >
                {tab.icon}{tab.label}
              </button>
            ))}
          </div>

          {/* PIN mode */}
          {mode === 'pin' && (
            <div className="space-y-3">
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
                Enter the <strong>Owner PIN</strong> set in Settings → Audit Setup.
                For in-person approvals only — do not share with workers.
              </div>
              <div>
                <Label>Owner PIN</Label>
                <Input
                  data-testid="owner-pin-input"
                  type="password"
                  inputMode="numeric"
                  value={code}
                  onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 8))}
                  placeholder="••••"
                  className="text-center text-2xl tracking-[0.4em] font-mono h-12 mt-1"
                  maxLength={8}
                  autoFocus
                  onKeyDown={e => e.key === 'Enter' && handleVerify()}
                />
              </div>
            </div>
          )}

          {/* TOTP mode */}
          {mode === 'totp' && (
            <div className="space-y-3">
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
                Call the admin and ask them to open <strong>Google Authenticator</strong> and
                read you the current 6-digit code. It expires in 30 seconds and cannot be reused.
              </div>
              <div>
                <Label>Authenticator Code</Label>
                <Input
                  data-testid="totp-code-input"
                  value={code}
                  onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="000000"
                  className="text-center text-2xl tracking-[0.4em] font-mono h-12 mt-1"
                  maxLength={6}
                  autoFocus
                  onKeyDown={e => e.key === 'Enter' && handleVerify()}
                />
              </div>
              <p className="text-[10px] text-slate-400">
                Admin must have set up TOTP in Settings → Security first.
              </p>
            </div>
          )}

          {/* Password mode */}
          {mode === 'password' && (
            <div className="space-y-3">
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-700">
                Enter the admin&apos;s full <strong>login password</strong>. Use only as a last resort.
              </div>
              <div>
                <Label>Admin Password</Label>
                <Input
                  data-testid="totp-password-input"
                  type="password"
                  value={code}
                  onChange={e => setCode(e.target.value)}
                  placeholder="Admin login password"
                  className="mt-1"
                  autoFocus
                  onKeyDown={e => e.key === 'Enter' && handleVerify()}
                />
              </div>
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <Button
              variant="outline"
              className="flex-1"
              onClick={() => { reset(); onOpenChange(false); }}
            >
              Cancel
            </Button>
            <Button
              data-testid="totp-verify-btn"
              className="flex-1 bg-amber-600 hover:bg-amber-700 text-white"
              onClick={handleVerify}
              disabled={
                loading ||
                (mode === 'totp' && code.length !== 6) ||
                ((mode === 'pin' || mode === 'password') && !code)
              }
            >
              {loading
                ? <RefreshCw size={14} className="animate-spin mr-2" />
                : <Lock size={14} className="mr-2" />}
              Authorize
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
