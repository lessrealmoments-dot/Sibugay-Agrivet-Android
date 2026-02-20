import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { Toaster } from './components/ui/sonner';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import BranchesPage from './pages/BranchesPage';
import ProductsPage from './pages/ProductsPage';
import ProductDetailPage from './pages/ProductDetailPage';
import InventoryPage from './pages/InventoryPage';
import POSPage from './pages/POSPage';
import CustomersPage from './pages/CustomersPage';
import PriceSchemesPage from './pages/PriceSchemesPage';
import SalesPage from './pages/SalesPage';
import SalesOrderPage from './pages/SalesOrderPage';
import UnifiedSalesPage from './pages/UnifiedSalesPage';
import PurchaseOrderPage from './pages/PurchaseOrderPage';
import SuppliersPage from './pages/SuppliersPage';
import DailyLogPage from './pages/DailyLogPage';
import PaymentsPage from './pages/PaymentsPage';
import FundManagementPage from './pages/FundManagementPage';
import AccountingPage from './pages/AccountingPage';
import SettingsPage from './pages/SettingsPage';
import UserPermissionsPage from './pages/UserPermissionsPage';
import CountSheetsPage from './pages/CountSheetsPage';

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex items-center justify-center h-screen bg-[#F5F5F0]"><div className="text-slate-400 text-sm">Loading...</div></div>;
  if (!user) return <Navigate to="/login" replace />;
  return <Layout>{children}</Layout>;
}

function AppRoutes() {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex items-center justify-center h-screen bg-[#F5F5F0]"><div className="text-slate-400 text-sm">Loading...</div></div>;

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/dashboard" replace /> : <LoginPage />} />
      <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
      <Route path="/branches" element={<ProtectedRoute><BranchesPage /></ProtectedRoute>} />
      <Route path="/products" element={<ProtectedRoute><ProductsPage /></ProtectedRoute>} />
      <Route path="/products/:id" element={<ProtectedRoute><ProductDetailPage /></ProtectedRoute>} />
      <Route path="/inventory" element={<ProtectedRoute><InventoryPage /></ProtectedRoute>} />
      <Route path="/sales-new" element={<ProtectedRoute><UnifiedSalesPage /></ProtectedRoute>} />
      <Route path="/pos" element={<ProtectedRoute><POSPage /></ProtectedRoute>} />
      <Route path="/customers" element={<ProtectedRoute><CustomersPage /></ProtectedRoute>} />
      <Route path="/price-schemes" element={<ProtectedRoute><PriceSchemesPage /></ProtectedRoute>} />
      <Route path="/sales" element={<ProtectedRoute><SalesPage /></ProtectedRoute>} />
      <Route path="/sales-order" element={<ProtectedRoute><SalesOrderPage /></ProtectedRoute>} />
      <Route path="/purchase-orders" element={<ProtectedRoute><PurchaseOrderPage /></ProtectedRoute>} />
      <Route path="/suppliers" element={<ProtectedRoute><SuppliersPage /></ProtectedRoute>} />
      <Route path="/daily-ops" element={<ProtectedRoute><DailyLogPage /></ProtectedRoute>} />
      <Route path="/payments" element={<ProtectedRoute><PaymentsPage /></ProtectedRoute>} />
      <Route path="/fund-management" element={<ProtectedRoute><FundManagementPage /></ProtectedRoute>} />
      <Route path="/accounting" element={<ProtectedRoute><AccountingPage /></ProtectedRoute>} />
      <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
      <Route path="/user-permissions" element={<ProtectedRoute><UserPermissionsPage /></ProtectedRoute>} />
      <Route path="/count-sheets" element={<ProtectedRoute><CountSheetsPage /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
        <Toaster position="bottom-right" richColors />
      </AuthProvider>
    </BrowserRouter>
  );
}
