import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { api } from '../contexts/AuthContext';
import { Shield, Lock, RefreshCw, KeyRound } from 'lucide-react';
import { toast } from 'sonner';

/**
 * TotpVerifyDialog — shared admin verification dialog.
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
  title = 'Admin Verification Required',
}) {
  const [mode, setMode] = useState('totp');   // 'totp' | 'password'
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);

  const reset = () => { setCode(''); setMode('totp'); };

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

  return (
    <Dialog open={open} onOpenChange={v => { if (!v) reset(); onOpenChange(v); }}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
            <Shield size={18} className="text-amber-600" /> {title}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 mt-2">
          {mode === 'totp' ? (
            <div className="space-y-3">
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
                Open your authenticator app (Google Authenticator, Authy, etc.) and enter
                the current <strong>6-digit code</strong>.
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
              <button
                onClick={() => { setMode('password'); setCode(''); }}
                className="text-xs text-slate-400 hover:text-slate-700 underline block"
              >
                Can&apos;t access authenticator? Use admin password instead
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
                Enter the admin&apos;s full <strong>login password</strong> as a fallback.
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
              <button
                onClick={() => { setMode('totp'); setCode(''); }}
                className="text-xs text-slate-400 hover:text-slate-700 underline block"
              >
                Use authenticator app instead
              </button>
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
              disabled={loading || (mode === 'totp' && code.length !== 6) || (mode === 'password' && !code)}
            >
              {loading
                ? <RefreshCw size={14} className="animate-spin mr-2" />
                : <Lock size={14} className="mr-2" />}
              Verify
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
