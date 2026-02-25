import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import {
  CheckCircle, X, ChevronRight, BarChart3, Shield, GitBranch,
  Layers, ArrowRight, Star, Building2, Users, TrendingUp, Menu, XCircle
} from 'lucide-react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const FEATURES_TABLE = [
  { label: "POS & Split Payments", basic: true, standard: true, pro: true },
  { label: "Inventory Management", basic: true, standard: true, pro: true },
  { label: "Customer Management", basic: true, standard: true, pro: true },
  { label: "Daily Close Wizard", basic: true, standard: true, pro: true },
  { label: "Basic Reports", basic: true, standard: true, pro: true },
  { label: "Expense Tracking", basic: true, standard: true, pro: true },
  { label: "Branches", basic: "1", standard: "2", pro: "5" },
  { label: "Users", basic: "5", standard: "15", pro: "Unlimited" },
  { label: "Purchase Orders", basic: false, standard: true, pro: true },
  { label: "Supplier Management", basic: false, standard: true, pro: true },
  { label: "Employee & Cash Advances", basic: false, standard: true, pro: true },
  { label: "4-Wallet Fund Management", basic: false, standard: true, pro: true },
  { label: "Multi-Branch Transfers", basic: false, standard: "Basic", pro: "With Repack Pricing" },
  { label: "Standard Audit Trail", basic: false, standard: true, pro: true },
  { label: "Full Audit Center", basic: false, standard: false, pro: true },
  { label: "Transaction Verification", basic: false, standard: false, pro: true },
  { label: "Granular Role Permissions", basic: false, standard: false, pro: true },
  { label: "2FA Security", basic: false, standard: false, pro: true },
];

const COMPETITORS = [
  { name: "QuickBooks Online", price: "$115/mo", note: "No POS, no fund mgmt", highlight: false },
  { name: "inFlow Inventory", price: "$219/mo", note: "No accounting, no POS", highlight: false },
  { name: "AgriBooks Pro", price: "₱7,500/mo", note: "POS + Inventory + Accounting + Audit", highlight: true },
];

function FeatureCell({ value }) {
  if (value === true) return <CheckCircle size={18} className="mx-auto text-emerald-500" />;
  if (value === false) return <X size={18} className="mx-auto text-slate-300" />;
  return <span className="text-xs font-medium text-slate-700">{value}</span>;
}

export default function LandingPage() {
  const navigate = useNavigate();
  const [plans, setPlans] = useState(null);
  const [mobileMenu, setMobileMenu] = useState(false);
  const [billingAnnual, setBillingAnnual] = useState(false);

  useEffect(() => {
    axios.get(`${BACKEND_URL}/api/organizations/plans`)
      .then(r => setPlans(r.data))
      .catch(() => {});
  }, []);

  const planCards = [
    {
      key: "basic", name: "Basic", tagline: "Get your first branch running clean",
      php: 1500, usd: 30, branches: "1 Branch", users: "5 Users", color: "slate",
      popular: false,
    },
    {
      key: "standard", name: "Standard", tagline: "Run a real multi-branch operation",
      php: 4000, usd: 80, branches: "2 Branches", users: "15 Users", color: "emerald",
      popular: true,
    },
    {
      key: "pro", name: "Pro", tagline: "Audit-grade control for serious businesses",
      php: 7500, usd: 150, branches: "5 Branches", users: "Unlimited Users", color: "indigo",
      popular: false,
    },
  ];

  return (
    <div className="min-h-screen bg-[#060D1A] text-white" style={{ fontFamily: 'Manrope, system-ui, sans-serif' }}>

      {/* ── NAV ── */}
      <nav className="fixed top-0 left-0 right-0 z-50 border-b border-white/5 bg-[#060D1A]/90 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-500 flex items-center justify-center">
              <BarChart3 size={16} className="text-white" />
            </div>
            <span className="font-bold text-lg tracking-tight">AgriBooks</span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-sm text-slate-400">
            <a href="#features" className="hover:text-white transition-colors">Features</a>
            <a href="#pricing" className="hover:text-white transition-colors">Pricing</a>
            <a href="#compare" className="hover:text-white transition-colors">Compare</a>
          </div>
          <div className="hidden md:flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate('/login')}
              className="text-slate-400 hover:text-white hover:bg-white/5">Sign In</Button>
            <Button size="sm" onClick={() => navigate('/register')}
              className="bg-emerald-500 hover:bg-emerald-400 text-white font-semibold px-5">
              Start Free Trial
            </Button>
          </div>
          <button className="md:hidden text-slate-400" onClick={() => setMobileMenu(!mobileMenu)}>
            {mobileMenu ? <XCircle size={22} /> : <Menu size={22} />}
          </button>
        </div>
        {mobileMenu && (
          <div className="md:hidden border-t border-white/5 bg-[#060D1A] px-6 py-4 flex flex-col gap-4">
            <a href="#features" className="text-slate-400 text-sm" onClick={() => setMobileMenu(false)}>Features</a>
            <a href="#pricing" className="text-slate-400 text-sm" onClick={() => setMobileMenu(false)}>Pricing</a>
            <Button size="sm" onClick={() => navigate('/register')}
              className="bg-emerald-500 text-white w-full">Start Free Trial</Button>
            <Button variant="ghost" size="sm" onClick={() => navigate('/login')}
              className="text-slate-400 w-full">Sign In</Button>
          </div>
        )}
      </nav>

      {/* ── HERO ── */}
      <section className="pt-32 pb-24 px-6 relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_30%_20%,rgba(16,185,129,0.08),transparent_60%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_80%_80%,rgba(99,102,241,0.06),transparent_60%)]" />
        <div className="max-w-5xl mx-auto text-center relative z-10">
          <div className="inline-flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 rounded-full px-4 py-1.5 text-emerald-400 text-sm font-medium mb-8">
            <Star size={13} className="fill-emerald-400" />
            14-day free trial — all Pro features included
          </div>
          <h1 className="text-5xl sm:text-6xl lg:text-7xl font-extrabold leading-[1.05] tracking-tight mb-6">
            Audit-Grade
            <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-teal-300">
              Retail Intelligence
            </span>
          </h1>
          <p className="text-xl text-slate-400 max-w-2xl mx-auto mb-4 leading-relaxed">
            Serious control for serious businesses.
          </p>
          <p className="text-base text-slate-500 max-w-xl mx-auto mb-12">
            The all-in-one POS, Inventory, and Accounting platform built for growing Philippine retail businesses.
            One system. Zero blind spots.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Button
              onClick={() => navigate('/register')}
              className="bg-emerald-500 hover:bg-emerald-400 text-white font-bold px-8 py-4 h-auto text-base rounded-xl shadow-lg shadow-emerald-500/20 transition-all hover:scale-105"
            >
              Start Free Trial <ArrowRight size={18} className="ml-2" />
            </Button>
            <Button
              variant="outline"
              onClick={() => navigate('/login')}
              className="border-white/10 bg-white/5 hover:bg-white/10 text-white px-8 py-4 h-auto text-base rounded-xl"
            >
              Sign In to Dashboard
            </Button>
          </div>
          <p className="text-xs text-slate-600 mt-5">No credit card required · 14 days · All Pro features</p>
        </div>
      </section>

      {/* ── STAT BAR ── */}
      <section className="border-y border-white/5 bg-white/[0.02] py-10 px-6">
        <div className="max-w-5xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          {[
            { icon: Building2, value: "Multi-Branch", label: "Inventory Control" },
            { icon: Shield, value: "Audit-Grade", label: "Transaction Verification" },
            { icon: Layers, value: "4-Wallet", label: "Fund Management" },
            { icon: TrendingUp, value: "Real-Time", label: "Reporting & Insights" },
          ].map(({ icon: Icon, value, label }) => (
            <div key={label} className="flex flex-col items-center gap-2">
              <Icon size={22} className="text-emerald-400" />
              <div className="text-lg font-bold text-white">{value}</div>
              <div className="text-xs text-slate-500">{label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── FEATURES ── */}
      <section id="features" className="py-24 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              Everything your business needs. <span className="text-emerald-400">Nothing extra.</span>
            </h2>
            <p className="text-slate-400 max-w-xl mx-auto">
              Built for Philippine retail. AgriBooks replaces three separate tools — at a fraction of the cost.
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                icon: Layers,
                title: "POS + Inventory + Accounting",
                desc: "QuickBooks doesn't have POS. inFlow doesn't have accounting. AgriBooks does all three — in one dashboard.",
                color: "emerald",
              },
              {
                icon: GitBranch,
                title: "Multi-Branch with Repack Pricing",
                desc: "Transfer stock between branches with full cost tracking. Set selling prices per repack at the destination branch.",
                color: "blue",
              },
              {
                icon: Shield,
                title: "Audit Center & Verification",
                desc: "Flag discrepancies. Verify transactions with manager PINs. Full audit trail with no blind spots.",
                color: "purple",
              },
              {
                icon: BarChart3,
                title: "4-Wallet Fund System",
                desc: "Cashier, Safe, Digital (GCash/Maya), and Bank — all tracked separately with role-based access controls.",
                color: "amber",
              },
              {
                icon: Users,
                title: "Granular Role Permissions",
                desc: "Set exactly what each user can see and do. Admin, Manager, Cashier — or fully custom roles.",
                color: "teal",
              },
              {
                icon: TrendingUp,
                title: "Daily Close Wizard",
                desc: "Guided end-of-day closing. Z-Report. Cash reconciliation. Digital payment summary. Never miss a step.",
                color: "rose",
              },
            ].map(({ icon: Icon, title, desc, color }) => (
              <div key={title}
                className="bg-white/[0.03] border border-white/5 rounded-2xl p-6 hover:bg-white/[0.06] hover:border-white/10 transition-all group">
                <div className={`w-10 h-10 rounded-xl bg-${color}-500/10 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform`}>
                  <Icon size={20} className={`text-${color}-400`} />
                </div>
                <h3 className="font-semibold text-white mb-2">{title}</h3>
                <p className="text-slate-400 text-sm leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── COMPARE TABLE ── */}
      <section id="compare" className="py-24 px-6 bg-white/[0.01] border-y border-white/5">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              Why not QuickBooks or inFlow?
            </h2>
            <p className="text-slate-400 max-w-lg mx-auto">
              Those tools charge $259+/month for less features. AgriBooks gives you everything at ₱7,500/month.
            </p>
          </div>
          <div className="overflow-x-auto rounded-2xl border border-white/5">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/5">
                  <th className="text-left px-4 py-4 text-slate-500 font-medium w-44">Feature</th>
                  {COMPETITORS.map(c => (
                    <th key={c.name} className={`px-4 py-4 text-center ${c.highlight ? 'bg-emerald-500/10' : ''}`}>
                      <div className={`font-bold ${c.highlight ? 'text-emerald-400' : 'text-slate-300'}`}>{c.name}</div>
                      <div className={`text-xs mt-1 ${c.highlight ? 'text-emerald-300' : 'text-slate-500'}`}>{c.price}</div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  ["Built-in POS", false, false, true],
                  ["Inventory Management", false, true, true],
                  ["Accounting & Fund Mgmt", true, false, true],
                  ["Multi-Branch Transfers", false, "Limited", true],
                  ["4-Wallet Cash System", false, false, true],
                  ["Audit Center", false, false, true],
                  ["Philippines Payments (Maya/GCash)", false, false, true],
                  ["All-in-one pricing", false, false, true],
                ].map(([label, qb, inflow, agri], i) => (
                  <tr key={label} className={`border-b border-white/5 ${i % 2 === 0 ? 'bg-white/[0.01]' : ''}`}>
                    <td className="px-4 py-3 text-slate-400">{label}</td>
                    <td className="px-4 py-3 text-center">
                      {qb === true ? <CheckCircle size={16} className="mx-auto text-slate-500" /> :
                       qb === false ? <X size={16} className="mx-auto text-slate-600" /> :
                       <span className="text-xs text-slate-500">{qb}</span>}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {inflow === true ? <CheckCircle size={16} className="mx-auto text-slate-500" /> :
                       inflow === false ? <X size={16} className="mx-auto text-slate-600" /> :
                       <span className="text-xs text-slate-500">{inflow}</span>}
                    </td>
                    <td className="px-4 py-3 text-center bg-emerald-500/5">
                      {agri === true ? <CheckCircle size={16} className="mx-auto text-emerald-500" /> :
                       agri === false ? <X size={16} className="mx-auto text-slate-600" /> :
                       <span className="text-xs text-emerald-400">{agri}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ── PRICING ── */}
      <section id="pricing" className="py-24 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">Simple, transparent pricing</h2>
            <p className="text-slate-400 mb-6">14-day free trial on Pro. No credit card needed.</p>
            <div className="inline-flex items-center gap-1 bg-white/5 border border-white/10 rounded-full p-1">
              <button
                onClick={() => setBillingAnnual(false)}
                className={`px-5 py-2 rounded-full text-sm font-medium transition-all ${!billingAnnual ? 'bg-white text-slate-900' : 'text-slate-400 hover:text-white'}`}
              >Monthly</button>
              <button
                onClick={() => setBillingAnnual(true)}
                className={`px-5 py-2 rounded-full text-sm font-medium transition-all ${billingAnnual ? 'bg-white text-slate-900' : 'text-slate-400 hover:text-white'}`}
              >
                Annual <span className="text-emerald-400 text-xs ml-1">2 months free</span>
              </button>
            </div>
          </div>

          <div className="grid md:grid-cols-3 gap-6 mb-8">
            {planCards.map(plan => {
              const monthlyPhp = billingAnnual ? Math.round(plan.php * 10 / 12) : plan.php;
              const monthlyUsd = billingAnnual ? Math.round(plan.usd * 10 / 12) : plan.usd;
              return (
                <div key={plan.key}
                  className={`relative rounded-2xl p-6 border transition-all ${
                    plan.popular
                      ? 'border-emerald-500/50 bg-emerald-500/5 shadow-lg shadow-emerald-500/10'
                      : 'border-white/5 bg-white/[0.03] hover:border-white/10'
                  }`}
                >
                  {plan.popular && (
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                      <span className="bg-emerald-500 text-white text-xs font-bold px-4 py-1 rounded-full">
                        MOST POPULAR
                      </span>
                    </div>
                  )}
                  <div className="mb-5">
                    <h3 className="text-lg font-bold text-white">{plan.name}</h3>
                    <p className="text-slate-400 text-sm mt-1">{plan.tagline}</p>
                  </div>
                  <div className="mb-5">
                    <div className="flex items-baseline gap-1">
                      <span className="text-3xl font-extrabold">₱{monthlyPhp.toLocaleString()}</span>
                      <span className="text-slate-500 text-sm">/mo</span>
                    </div>
                    <div className="text-slate-500 text-sm">${monthlyUsd}/month</div>
                    {billingAnnual && <div className="text-emerald-400 text-xs mt-1">Billed annually</div>}
                  </div>
                  <div className="space-y-2 mb-6 text-sm text-slate-400">
                    <div className="flex items-center gap-2">
                      <CheckCircle size={14} className="text-emerald-500 shrink-0" />
                      {plan.branches}
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle size={14} className="text-emerald-500 shrink-0" />
                      {plan.users}
                    </div>
                  </div>
                  <Button
                    onClick={() => navigate('/register')}
                    className={`w-full h-10 font-semibold rounded-xl ${
                      plan.popular
                        ? 'bg-emerald-500 hover:bg-emerald-400 text-white'
                        : 'bg-white/5 hover:bg-white/10 text-white border border-white/10'
                    }`}
                  >
                    Start Free Trial <ChevronRight size={16} className="ml-1" />
                  </Button>
                </div>
              );
            })}
          </div>

          <div className="text-center text-slate-500 text-sm">
            Need more branches? Add extra branches at ₱1,500/mo ($30) each on Standard & Pro plans.
          </div>
        </div>
      </section>

      {/* ── FULL FEATURE TABLE ── */}
      <section className="py-16 px-6 bg-white/[0.01] border-y border-white/5">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl font-bold text-center mb-10">Full feature comparison</h2>
          <div className="overflow-x-auto rounded-2xl border border-white/5">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/5">
                  <th className="text-left px-4 py-3 text-slate-500 font-medium">Feature</th>
                  <th className="px-4 py-3 text-center text-slate-300 font-semibold">Basic</th>
                  <th className="px-4 py-3 text-center text-emerald-400 font-semibold bg-emerald-500/5">Standard</th>
                  <th className="px-4 py-3 text-center text-indigo-400 font-semibold">Pro</th>
                </tr>
              </thead>
              <tbody>
                {FEATURES_TABLE.map((row, i) => (
                  <tr key={row.label} className={`border-b border-white/5 ${i % 2 === 0 ? 'bg-white/[0.01]' : ''}`}>
                    <td className="px-4 py-3 text-slate-400">{row.label}</td>
                    <td className="px-4 py-3 text-center"><FeatureCell value={row.basic} /></td>
                    <td className="px-4 py-3 text-center bg-emerald-500/5"><FeatureCell value={row.standard} /></td>
                    <td className="px-4 py-3 text-center"><FeatureCell value={row.pro} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="py-24 px-6 text-center relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_50%,rgba(16,185,129,0.06),transparent_70%)]" />
        <div className="max-w-2xl mx-auto relative z-10">
          <h2 className="text-4xl font-extrabold mb-4">Ready to take control?</h2>
          <p className="text-slate-400 mb-8 text-lg">
            Start your 14-day free trial today. No credit card. All Pro features. Cancel anytime.
          </p>
          <Button
            onClick={() => navigate('/register')}
            className="bg-emerald-500 hover:bg-emerald-400 text-white font-bold px-10 py-4 h-auto text-base rounded-xl shadow-lg shadow-emerald-500/20 transition-all hover:scale-105"
          >
            Get Started Free <ArrowRight size={18} className="ml-2" />
          </Button>
          <p className="text-slate-600 text-sm mt-4">
            Questions? Contact us at{' '}
            <a href="mailto:janmarkeahig@gmail.com" className="text-emerald-500 hover:underline">
              janmarkeahig@gmail.com
            </a>
          </p>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer className="border-t border-white/5 py-8 px-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-emerald-500 flex items-center justify-center">
              <BarChart3 size={12} className="text-white" />
            </div>
            <span className="font-semibold text-sm">AgriBooks</span>
            <span className="text-slate-600 text-xs ml-2">Audit-Grade Retail Intelligence</span>
          </div>
          <div className="text-slate-600 text-xs">
            © {new Date().getFullYear()} AgriBooks. Built for growing businesses.
          </div>
        </div>
      </footer>
    </div>
  );
}
