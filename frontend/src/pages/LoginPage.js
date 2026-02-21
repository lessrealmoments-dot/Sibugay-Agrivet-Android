import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Store, Eye, EyeOff } from 'lucide-react';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed');
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen flex">
      <div
        className="hidden lg:flex lg:w-1/2 relative items-center justify-center"
        style={{
          backgroundImage: "url('/login-bg.jpg')",
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }}
      >
        <div className="absolute inset-0 bg-[#0F172A]/75" />
        <div className="relative z-10 max-w-md px-8 text-center">
          <div className="w-16 h-16 rounded-2xl bg-[#1A4D2E] flex items-center justify-center mx-auto mb-6">
            <Store size={32} className="text-white" />
          </div>
          <h2 className="text-3xl font-bold text-white mb-3" style={{ fontFamily: 'Manrope' }}>AgriPOS</h2>
          <p className="text-slate-300 text-sm leading-relaxed">
            Multi-branch Inventory, POS & Accounting system built for agricultural retail and wholesale businesses.
          </p>
        </div>
      </div>
      <div className="flex-1 flex items-center justify-center p-6 bg-[#F5F5F0]">
        <Card className="w-full max-w-md border-slate-200 shadow-sm">
          <CardHeader className="text-center pb-4">
            <div className="w-12 h-12 rounded-xl bg-[#1A4D2E] flex items-center justify-center mx-auto mb-3 lg:hidden">
              <Store size={24} className="text-white" />
            </div>
            <CardTitle className="text-2xl" style={{ fontFamily: 'Manrope' }}>Sign In</CardTitle>
            <p className="text-sm text-slate-500 mt-1">Access your AgriPOS dashboard</p>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-5">
              {error && (
                <div data-testid="login-error" className="bg-red-50 text-red-700 text-sm px-4 py-3 rounded-lg border border-red-200">
                  {error}
                </div>
              )}
              <div className="space-y-2">
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  data-testid="login-username"
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  placeholder="Enter username"
                  className="h-11"
                  autoFocus
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <div className="relative">
                  <Input
                    id="password"
                    data-testid="login-password"
                    type={showPw ? 'text' : 'password'}
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    placeholder="Enter password"
                    className="h-11 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw(!showPw)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  >
                    {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>
              <Button
                type="submit"
                data-testid="login-submit-btn"
                disabled={loading}
                className="w-full h-11 bg-[#1A4D2E] hover:bg-[#14532d] text-white"
              >
                {loading ? 'Signing in...' : 'Sign In'}
              </Button>
              {process.env.NODE_ENV === 'development' && (
                <p className="text-center text-xs text-slate-400 mt-4">
                  Default: admin / admin123
                </p>
              )}
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
