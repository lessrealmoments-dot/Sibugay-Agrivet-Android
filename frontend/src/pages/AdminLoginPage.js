import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Eye, EyeOff, Shield, Smartphone, Key, RefreshCw } from 'lucide-react';
import { QRCodeCanvas as QRCode } from 'qrcode.react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const api = axios.create({ baseURL: `${BACKEND_URL}/api` });

// Steps: 'password' | 'totp' | 'setup_totp' | 'recovery'
export default function AdminLoginPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState('password');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Password step
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [pendingToken, setPendingToken] = useState('');

  // TOTP step
  const [totpCode, setTotpCode] = useState('');

  // Setup step
  const [qrUri, setQrUri] = useState('');
  const [setupCode, setSetupCode] = useState('');
  const [backupCodes, setBackupCodes] = useState([]);
  const [codesShown, setCodesShown] = useState(false);

  // Recovery step
  const [recoveryCode, setRecoveryCode] = useState('');

  // Check portal status on mount
  useEffect(() => {
    // If already logged in as super admin, redirect
    const token = localStorage.getItem('agripos_token');
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        const isExpired = payload.exp && payload.exp < Date.now() / 1000;
        if (payload.is_super_admin && !isExpired) {
          window.location.href = '/superadmin';
        }
      } catch {}
    }
  }, []);

  const handlePasswordSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await api.post('/admin-auth/login', { email, password });
      setPendingToken(res.data.pending_token);
      if (res.data.totp_ready) {
        setStep('totp');
      } else {
        // First time — need to set up TOTP
        const setupRes = await api.post('/admin-auth/setup-totp', { pending_token: res.data.pending_token });
        setQrUri(setupRes.data.qr_uri);
        setPendingToken(setupRes.data.pending_token);
        setStep('setup_totp');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid credentials');
    }
    setLoading(false);
  };

  const handleTotpSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await api.post('/admin-auth/totp', { pending_token: pendingToken, code: totpCode });
      finishLogin(res.data.token, res.data.user);
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid code');
      setTotpCode('');
    }
    setLoading(false);
  };

  const handleSetupVerify = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await api.post('/admin-auth/verify-setup', { pending_token: pendingToken, code: setupCode });
      if (!res.data.verified) {
        setError(res.data.error || 'Invalid code');
        setLoading(false);
        return;
      }
      setBackupCodes(res.data.backup_codes);
      setCodesShown(true);
      // Store token for after codes are saved
      setPendingToken(res.data.token);
    } catch (err) {
      setError(err.response?.data?.detail || 'Verification failed');
    }
    setLoading(false);
  };

  const handleRecovery = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await api.post('/admin-auth/recover', {
        pending_token: pendingToken,
        recovery_code: recoveryCode,
      });
      finishLogin(res.data.token, res.data.user);
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid recovery code');
    }
    setLoading(false);
  };

  const finishLogin = (token, _user) => {
    localStorage.setItem('agripos_token', token);
    // Full reload so AuthContext reinitializes from localStorage with the new token
    window.location.href = '/superadmin';
  };

  const afterCodesSaved = () => {
    // pendingToken is now the full JWT
    localStorage.setItem('agripos_token', pendingToken);
    window.location.href = '/superadmin';
  };

  return (
    <div className="min-h-screen bg-[#060D1A] flex items-center justify-center p-6" style={{ fontFamily: 'Manrope, sans-serif' }}>
      <div className="w-full max-w-sm">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-14 h-14 bg-slate-800 border border-slate-700 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <Shield size={26} className="text-emerald-400" />
          </div>
          <h1 className="text-white font-bold text-xl">Platform Administration</h1>
          <p className="text-slate-500 text-sm mt-1">Restricted access — authorized personnel only</p>
        </div>

        {/* Step: Password */}
        {step === 'password' && (
          <form onSubmit={handlePasswordSubmit} className="space-y-4">
            {error && <div className="bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-4 py-3 rounded-lg">{error}</div>}
            <div className="space-y-1.5">
              <Label className="text-slate-400 text-sm">Email</Label>
              <Input
                type="email"
                data-testid="admin-email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="admin@agribooks.com"
                className="bg-white/5 border-white/10 text-white placeholder:text-slate-600 h-11"
                autoFocus
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-slate-400 text-sm">Password</Label>
              <div className="relative">
                <Input
                  type={showPw ? 'text' : 'password'}
                  data-testid="admin-password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="Password"
                  className="bg-white/5 border-white/10 text-white placeholder:text-slate-600 h-11 pr-10"
                />
                <button type="button" onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
                  {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>
            <Button type="submit" disabled={loading} data-testid="admin-login-btn"
              className="w-full h-11 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-xl">
              {loading ? 'Verifying...' : 'Continue'}
            </Button>
          </form>
        )}

        {/* Step: TOTP */}
        {step === 'totp' && (
          <form onSubmit={handleTotpSubmit} className="space-y-4">
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4 text-center mb-2">
              <Smartphone size={28} className="text-emerald-400 mx-auto mb-2" />
              <p className="text-white text-sm font-medium">Google Authenticator</p>
              <p className="text-slate-400 text-xs mt-1">Open your authenticator app and enter the 6-digit code for AgriBooks Platform Admin</p>
            </div>
            {error && <div className="bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-4 py-3 rounded-lg">{error}</div>}
            <div className="space-y-1.5">
              <Label className="text-slate-400 text-sm">6-Digit Code</Label>
              <Input
                data-testid="admin-totp-code"
                value={totpCode}
                onChange={e => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="000000"
                maxLength={6}
                className="bg-white/5 border-white/10 text-white placeholder:text-slate-600 h-11 text-center text-xl tracking-[0.5em] font-mono"
                autoFocus
              />
            </div>
            <Button type="submit" disabled={loading || totpCode.length < 6} data-testid="admin-totp-btn"
              className="w-full h-11 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-xl">
              {loading ? 'Verifying...' : 'Verify & Sign In'}
            </Button>
            <button type="button" onClick={() => { setStep('recovery'); setError(''); }}
              className="w-full text-center text-slate-500 text-xs hover:text-slate-300 transition-colors">
              Lost access to authenticator? Use recovery code →
            </button>
          </form>
        )}

        {/* Step: First-time TOTP Setup */}
        {step === 'setup_totp' && !codesShown && (
          <form onSubmit={handleSetupVerify} className="space-y-4">
            <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-3 text-center">
              <p className="text-amber-300 text-xs font-medium">First-time setup required</p>
              <p className="text-amber-400/70 text-xs mt-0.5">Scan the QR code with Google Authenticator</p>
            </div>
            {qrUri && (
              <div className="flex justify-center p-4 bg-white rounded-xl">
                <QRCode value={qrUri} size={180} />
              </div>
            )}
            <p className="text-slate-400 text-xs text-center">
              After scanning, enter the 6-digit code to confirm setup.
              <br />Backup codes will be emailed to you.
            </p>
            {error && <div className="bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-4 py-3 rounded-lg">{error}</div>}
            <div className="space-y-1.5">
              <Label className="text-slate-400 text-sm">Confirm Code</Label>
              <Input
                data-testid="admin-setup-code"
                value={setupCode}
                onChange={e => setSetupCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="000000"
                maxLength={6}
                className="bg-white/5 border-white/10 text-white h-11 text-center text-xl tracking-[0.5em] font-mono"
                autoFocus
              />
            </div>
            <Button type="submit" disabled={loading || setupCode.length < 6}
              className="w-full h-11 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-xl">
              {loading ? 'Setting up...' : 'Enable Authenticator'}
            </Button>
          </form>
        )}

        {/* Step: Show backup codes */}
        {step === 'setup_totp' && codesShown && (
          <div className="space-y-4">
            <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-3 text-center">
              <p className="text-emerald-300 text-sm font-semibold">Authenticator Enabled!</p>
              <p className="text-emerald-400/70 text-xs mt-0.5">Codes also sent to your email</p>
            </div>
            <div>
              <p className="text-slate-300 text-sm font-medium mb-2">Your Recovery Backup Codes</p>
              <p className="text-slate-500 text-xs mb-3">Save these somewhere safe. Each can only be used once.</p>
              <div className="grid grid-cols-2 gap-2">
                {backupCodes.map((code, i) => (
                  <div key={i} className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 font-mono text-xs text-emerald-300 text-center">
                    {code}
                  </div>
                ))}
              </div>
            </div>
            <Button onClick={afterCodesSaved}
              className="w-full h-11 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-xl">
              I've saved my codes — Go to Admin Panel →
            </Button>
          </div>
        )}

        {/* Step: Recovery */}
        {step === 'recovery' && (
          <form onSubmit={handleRecovery} className="space-y-4">
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4 text-center mb-2">
              <Key size={28} className="text-amber-400 mx-auto mb-2" />
              <p className="text-white text-sm font-medium">Account Recovery</p>
              <p className="text-slate-400 text-xs mt-1">Enter one of your backup recovery codes</p>
            </div>
            {error && <div className="bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-4 py-3 rounded-lg">{error}</div>}
            <div className="space-y-1.5">
              <Label className="text-slate-400 text-sm">Recovery Code</Label>
              <Input
                data-testid="admin-recovery-code"
                value={recoveryCode}
                onChange={e => setRecoveryCode(e.target.value.toUpperCase())}
                placeholder="XXXXXX-XXXXXX"
                className="bg-white/5 border-white/10 text-white placeholder:text-slate-600 h-11 text-center font-mono tracking-widest uppercase"
                autoFocus
              />
            </div>
            <Button type="submit" disabled={loading || !recoveryCode}
              className="w-full h-11 bg-amber-600 hover:bg-amber-500 text-white font-semibold rounded-xl">
              {loading ? 'Verifying...' : 'Use Recovery Code'}
            </Button>
            <button type="button" onClick={() => { setStep('totp'); setError(''); }}
              className="w-full text-center text-slate-500 text-xs hover:text-slate-300 transition-colors flex items-center justify-center gap-1">
              <RefreshCw size={11} /> Back to authenticator code
            </button>
          </form>
        )}

        <p className="text-center text-slate-700 text-xs mt-8">
          This portal is for authorized administrators only.
        </p>
      </div>
    </div>
  );
}
