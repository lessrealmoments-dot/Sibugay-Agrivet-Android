import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { ShieldCheck, Lock, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

export default function SectionOverrideDialog({ open, onOpenChange, module, moduleLabel, onGranted }) {
  const { requestSectionOverride } = useAuth();
  const [pin, setPin] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!pin) { toast.error('Enter PIN or TOTP code'); return; }
    setLoading(true);
    try {
      const result = await requestSectionOverride(module, pin);
      toast.success(`Access granted by ${result.granted_by}`);
      setPin('');
      onOpenChange(false);
      onGranted?.(result);
    } catch (e) {
      toast.error(e.message || 'Invalid PIN or TOTP code');
    }
    setLoading(false);
  };

  return (
    <Dialog open={open} onOpenChange={v => { onOpenChange(v); if (!v) setPin(''); }}>
      <DialogContent className="sm:max-w-sm" data-testid="section-override-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
            <Lock size={18} className="text-amber-500" />
            Access Required
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 mt-2">
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
            <p className="text-sm text-amber-800">
              You don't have permission to access <b>{moduleLabel}</b>.
            </p>
            <p className="text-xs text-amber-600 mt-1">
              Ask your admin to enter their PIN or read a TOTP code from their authenticator app.
            </p>
          </div>
          <div>
            <Input
              type="password"
              placeholder="Enter Admin PIN or 6-digit TOTP code"
              value={pin}
              onChange={e => setPin(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleSubmit(); }}
              className="text-center text-lg tracking-widest"
              data-testid="section-override-pin-input"
              autoFocus
            />
          </div>
          <div className="flex gap-2">
            <Button variant="outline" className="flex-1" onClick={() => { onOpenChange(false); setPin(''); }}>
              Cancel
            </Button>
            <Button
              className="flex-1 bg-[#1A4D2E] hover:bg-[#14532d] text-white"
              onClick={handleSubmit}
              disabled={loading || !pin}
              data-testid="section-override-submit"
            >
              {loading ? <RefreshCw size={14} className="animate-spin mr-2" /> : <ShieldCheck size={14} className="mr-2" />}
              Grant Access
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
