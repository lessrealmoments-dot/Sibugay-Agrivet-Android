import { useState, useEffect, useRef } from 'react';
import { Loader2, Smartphone, RefreshCw } from 'lucide-react';
import { Button } from '../../components/ui/button';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export default function TerminalPairScreen({ onPaired }) {
  const [code, setCode] = useState('');
  const [status, setStatus] = useState('loading'); // loading | showing | expired | error
  const [expiresIn, setExpiresIn] = useState(300);
  const pollRef = useRef(null);
  const countdownRef = useRef(null);

  const generateCode = async () => {
    setStatus('loading');
    try {
      const res = await fetch(`${BACKEND_URL}/api/terminal/generate-code`, { method: 'POST' });
      const data = await res.json();
      setCode(data.code);
      setExpiresIn(data.expires_in);
      setStatus('showing');
    } catch {
      setStatus('error');
    }
  };

  useEffect(() => { generateCode(); }, []);

  // Countdown timer
  useEffect(() => {
    if (status !== 'showing') return;
    countdownRef.current = setInterval(() => {
      setExpiresIn(prev => {
        if (prev <= 1) {
          setStatus('expired');
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(countdownRef.current);
  }, [status]);

  // Poll for pairing
  useEffect(() => {
    if (status !== 'showing' || !code) return;
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/api/terminal/poll/${code}`);
        const data = await res.json();
        if (data.status === 'paired') {
          clearInterval(pollRef.current);
          clearInterval(countdownRef.current);
          onPaired({
            token: data.token,
            terminalId: data.terminal_id,
            branchId: data.branch_id,
            branchName: data.branch_name,
            userName: data.user_name,
            organizationId: data.organization_id,
          });
        } else if (data.status === 'expired') {
          setStatus('expired');
        }
      } catch { /* keep polling */ }
    }, 2000);
    return () => clearInterval(pollRef.current);
  }, [status, code, onPaired]);

  const mins = Math.floor(expiresIn / 60);
  const secs = expiresIn % 60;

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4" data-testid="terminal-pair-screen">
      <div className="w-full max-w-md text-center">
        {/* Logo / Brand */}
        <div className="mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 mb-4">
            <Smartphone className="w-8 h-8 text-emerald-400" />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight" style={{ fontFamily: 'Manrope, system-ui' }}>
            AgriSmart Terminal
          </h1>
          <p className="text-slate-400 text-sm mt-1">Enter this code on your computer to connect</p>
        </div>

        {/* Code Display */}
        <div className="bg-slate-800/60 backdrop-blur-md rounded-2xl border border-slate-700/50 p-8 mb-6">
          {status === 'loading' && (
            <div className="py-8">
              <Loader2 className="w-8 h-8 animate-spin text-emerald-400 mx-auto" />
              <p className="text-slate-400 text-sm mt-3">Generating code...</p>
            </div>
          )}

          {status === 'showing' && (
            <>
              <div className="flex justify-center gap-2 mb-4" data-testid="pairing-code">
                {code.split('').map((char, i) => (
                  <div key={i} className="w-12 h-14 sm:w-14 sm:h-16 flex items-center justify-center bg-slate-900/80 rounded-xl border border-slate-600/50 text-2xl sm:text-3xl font-mono font-bold text-white tracking-widest">
                    {char}
                  </div>
                ))}
              </div>
              <p className="text-slate-500 text-xs">
                Code expires in <span className="text-emerald-400 font-mono">{mins}:{secs.toString().padStart(2, '0')}</span>
              </p>
            </>
          )}

          {status === 'expired' && (
            <div className="py-6">
              <p className="text-slate-400 text-sm mb-4">Code expired</p>
              <Button onClick={generateCode} variant="outline" className="border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10" data-testid="regenerate-code-btn">
                <RefreshCw className="w-4 h-4 mr-2" /> Generate New Code
              </Button>
            </div>
          )}

          {status === 'error' && (
            <div className="py-6">
              <p className="text-red-400 text-sm mb-4">Failed to generate code. Check your connection.</p>
              <Button onClick={generateCode} variant="outline" className="border-red-500/30 text-red-400 hover:bg-red-500/10" data-testid="retry-code-btn">
                <RefreshCw className="w-4 h-4 mr-2" /> Retry
              </Button>
            </div>
          )}
        </div>

        {/* Instructions */}
        <div className="text-left space-y-3 px-2">
          <h3 className="text-slate-300 text-xs font-semibold uppercase tracking-wider">How to connect</h3>
          <div className="flex items-start gap-3">
            <span className="flex-shrink-0 w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 text-xs font-bold flex items-center justify-center">1</span>
            <p className="text-slate-400 text-sm">Open <strong className="text-slate-300">Settings</strong> on your computer</p>
          </div>
          <div className="flex items-start gap-3">
            <span className="flex-shrink-0 w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 text-xs font-bold flex items-center justify-center">2</span>
            <p className="text-slate-400 text-sm">Go to <strong className="text-slate-300">Connect Terminal</strong> tab</p>
          </div>
          <div className="flex items-start gap-3">
            <span className="flex-shrink-0 w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 text-xs font-bold flex items-center justify-center">3</span>
            <p className="text-slate-400 text-sm">Enter the code above and select a branch</p>
          </div>
        </div>
      </div>
    </div>
  );
}
