import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { BarChart3, ArrowLeft, Eye, EyeOff, CheckCircle, Shield, Hash, Smartphone } from 'lucide-react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const PERKS = [
  "14-day free trial — all Pro features",
  "No credit card required",
  "Multi-branch POS + Inventory + Accounting",
  "Audit-grade transaction tracking",
  "Philippines payments (Maya, GCash, Bank)",
];

export default function RegisterPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [form, setForm] = useState({
    company_name: '',
    admin_name: '',
    admin_email: '',
    admin_password: '',
    phone: '',
    branch_name: '',
  });

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    if (!form.company_name || !form.admin_name || !form.admin_email || !form.admin_password) {
      setError('Please fill in all required fields');
      return;
    }
    if (form.admin_password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }
    setLoading(true);
    try {
      await axios.post(`${BACKEND_URL}/api/organizations/register`, form);
      setStep(2);
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed. Please try again.');
    }
    setLoading(false);
  };

  if (step === 2) {
    return (
      <div className="min-h-screen bg-[#060D1A] flex items-center justify-center p-6" style={{ fontFamily: 'Manrope, sans-serif' }}>
        <div className="text-center max-w-md">
          <div className="w-16 h-16 bg-emerald-500/10 border border-emerald-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
            <CheckCircle size={32} className="text-emerald-400" />
          </div>
          <h2 className="text-2xl font-bold text-white mb-3">You're in!</h2>
          <p className="text-slate-400 mb-2">
            <strong className="text-white">{form.company_name}</strong> has been created.
          </p>
          <p className="text-slate-500 text-sm mb-8">
            Your 14-day Pro trial starts now. Your first branch has been set up — sign in to start using AgriBooks.
          </p>
          <Button
            onClick={() => navigate('/login')}
            className="bg-emerald-500 hover:bg-emerald-400 text-white font-bold px-8 py-3 h-auto rounded-xl"
          >
            Go to Sign In
          </Button>
          <p className="text-slate-600 text-xs mt-4">
            Use <strong className="text-slate-400">{form.admin_email}</strong> to sign in
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#060D1A] flex" style={{ fontFamily: 'Manrope, sans-serif' }}>
      {/* Left panel */}
      <div className="hidden lg:flex lg:w-5/12 flex-col justify-between p-12 bg-white/[0.02] border-r border-white/5">
        <div>
          <button onClick={() => navigate('/')} className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors mb-12">
            <ArrowLeft size={16} />
            <span className="text-sm">Back to home</span>
          </button>
          <div className="flex items-center gap-3 mb-12">
            <div className="w-10 h-10 bg-emerald-500 rounded-xl flex items-center justify-center">
              <BarChart3 size={20} className="text-white" />
            </div>
            <span className="text-white font-bold text-xl">AgriBooks</span>
          </div>
          <h2 className="text-3xl font-extrabold text-white mb-3">
            Start your free trial
          </h2>
          <p className="text-slate-400 text-sm leading-relaxed mb-10">
            Get 14 days of full Pro access. No credit card needed.
            Your account is ready in seconds.
          </p>
          <ul className="space-y-3">
            {PERKS.map(p => (
              <li key={p} className="flex items-center gap-3 text-slate-400 text-sm">
                <CheckCircle size={16} className="text-emerald-400 shrink-0" />
                {p}
              </li>
            ))}
          </ul>
        </div>
        <p className="text-slate-600 text-xs">
          Already have an account?{' '}
          <button onClick={() => navigate('/login')} className="text-emerald-400 hover:underline">Sign in</button>
        </p>
      </div>

      {/* Right panel */}
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-md">
          <button onClick={() => navigate('/')} className="flex lg:hidden items-center gap-2 text-slate-400 hover:text-white transition-colors mb-8">
            <ArrowLeft size={16} />
            <span className="text-sm">Back</span>
          </button>
          <Card className="border-white/5 bg-white/[0.04] text-white shadow-2xl">
            <CardHeader className="pb-4">
              <CardTitle className="text-xl text-white">Create your company</CardTitle>
              <p className="text-slate-400 text-sm">Set up your AgriBooks account in seconds</p>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleRegister} className="space-y-4">
                {error && (
                  <div data-testid="register-error" className="bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-4 py-3 rounded-lg">
                    {error}
                  </div>
                )}

                <div className="space-y-1.5">
                  <Label className="text-slate-300 text-sm">Company Name <span className="text-red-400">*</span></Label>
                  <Input
                    data-testid="register-company"
                    value={form.company_name}
                    onChange={e => set('company_name', e.target.value)}
                    placeholder="e.g. Santos General Store"
                    className="bg-white/5 border-white/10 text-white placeholder:text-slate-600 h-11"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label className="text-slate-300 text-sm">Your Full Name <span className="text-red-400">*</span></Label>
                  <Input
                    data-testid="register-name"
                    value={form.admin_name}
                    onChange={e => set('admin_name', e.target.value)}
                    placeholder="Your name"
                    className="bg-white/5 border-white/10 text-white placeholder:text-slate-600 h-11"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label className="text-slate-300 text-sm">Email Address <span className="text-red-400">*</span></Label>
                  <Input
                    data-testid="register-email"
                    type="email"
                    value={form.admin_email}
                    onChange={e => set('admin_email', e.target.value)}
                    placeholder="you@company.com"
                    className="bg-white/5 border-white/10 text-white placeholder:text-slate-600 h-11"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label className="text-slate-300 text-sm">Password <span className="text-red-400">*</span></Label>
                  <div className="relative">
                    <Input
                      data-testid="register-password"
                      type={showPw ? 'text' : 'password'}
                      value={form.admin_password}
                      onChange={e => set('admin_password', e.target.value)}
                      placeholder="Min. 8 characters"
                      className="bg-white/5 border-white/10 text-white placeholder:text-slate-600 h-11 pr-10"
                    />
                    <button type="button" onClick={() => setShowPw(!showPw)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
                      {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label className="text-slate-300 text-sm">Phone <span className="text-slate-500 text-xs">(optional)</span></Label>
                  <Input
                    data-testid="register-phone"
                    value={form.phone}
                    onChange={e => set('phone', e.target.value)}
                    placeholder="+63 9XX XXX XXXX"
                    className="bg-white/5 border-white/10 text-white placeholder:text-slate-600 h-11"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label className="text-slate-300 text-sm">First Branch Name <span className="text-slate-500 text-xs">(optional)</span></Label>
                  <Input
                    data-testid="register-branch"
                    value={form.branch_name}
                    onChange={e => set('branch_name', e.target.value)}
                    placeholder="e.g. Main Branch, Downtown Branch"
                    className="bg-white/5 border-white/10 text-white placeholder:text-slate-600 h-11"
                  />
                  <p className="text-xs text-slate-600">Leave blank to use your company name as the branch name</p>
                </div>

                <Button
                  type="submit"
                  data-testid="register-submit"
                  disabled={loading}
                  className="w-full h-11 bg-emerald-500 hover:bg-emerald-400 text-white font-bold rounded-xl mt-2"
                >
                  {loading ? 'Creating your account...' : 'Create Account & Start Trial'}
                </Button>

                <p className="text-center text-xs text-slate-600">
                  By creating an account, you agree to our terms of service.
                </p>
              </form>
            </CardContent>
          </Card>
          <p className="text-center text-slate-500 text-sm mt-6">
            Already have an account?{' '}
            <button onClick={() => navigate('/login')} className="text-emerald-400 hover:underline font-medium">
              Sign in
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
