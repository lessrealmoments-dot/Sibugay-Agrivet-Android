import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import axios from 'axios';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { Toaster } from './components/ui/sonner';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import SetupWizardPage from './pages/SetupWizardPage';
import DashboardPage from './pages/DashboardPage';
import BranchesPage from './pages/BranchesPage';
import BranchTransferPage from './pages/BranchTransferPage';
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
import CloseWizardPage from './pages/CloseWizardPage';
import PaymentsPage from './pages/PaymentsPage';
import FundManagementPage from './pages/FundManagementPage';
import AccountingPage from './pages/AccountingPage';
import SettingsPage from './pages/SettingsPage';
import UserPermissionsPage from './pages/UserPermissionsPage';
import CountSheetsPage from './pages/CountSheetsPage';
import AccountsPage from './pages/AccountsPage';
import EmployeesPage from './pages/EmployeesPage';
import PaySupplierPage from './pages/PaySupplierPage';
import ImportPage from './pages/ImportPage';
import ReportsPage from './pages/ReportsPage';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex items-center justify-center h-screen bg-[#F5F5F0]"><div className="text-slate-400 text-sm">Loading...</div></div>;
  if (!user) return <Navigate to="/login" replace />;
  return <Layout>{children}</Layout>;
}

function AppRoutes() {
  const { user, loading } = useAuth();
  const [setupNeeded, setSetupNeeded] = useState(null);
  
  useEffect(() => {
    const checkSetup = async () => {
      try {
        const res = await axios.get(`${BACKEND_URL}/api/setup/status`);
        setSetupNeeded(!res.data.setup_completed);
      } catch {
        setSetupNeeded(false); // If check fails, assume setup is done
      }
    };
    checkSetup();
  }, []);

  if (loading || setupNeeded === null) {
    return <div className="flex items-center justify-center h-screen bg-[#F5F5F0]"><div className="text-slate-400 text-sm">Loading...</div></div>;
  }

  // If setup is needed, show setup wizard
  if (setupNeeded && !user) {
    return (
      <Routes>
        <Route path="/setup" element={<SetupWizardPage />} />
        <Route path="*" element={<Navigate to="/setup" replace />} />
      </Routes>
    );
  }

  return (
    <Routes>
      <Route path="/setup" element={<Navigate to="/dashboard" replace />} />
      <Route path="/login" element={user ? <Navigate to="/dashboard" replace /> : <LoginPage />} />
      <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
      <Route path="/branches" element={<ProtectedRoute><BranchesPage /></ProtectedRoute>} />
      <Route path="/branch-transfers" element={<ProtectedRoute><BranchTransferPage /></ProtectedRoute>} />
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
      <Route path="/close-wizard" element={<ProtectedRoute><CloseWizardPage /></ProtectedRoute>} />
      <Route path="/payments" element={<ProtectedRoute><PaymentsPage /></ProtectedRoute>} />
      <Route path="/fund-management" element={<ProtectedRoute><FundManagementPage /></ProtectedRoute>} />
      <Route path="/accounting" element={<ProtectedRoute><AccountingPage /></ProtectedRoute>} />
      <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
      <Route path="/user-permissions" element={<ProtectedRoute><UserPermissionsPage /></ProtectedRoute>} />
      <Route path="/accounts" element={<ProtectedRoute><AccountsPage /></ProtectedRoute>} />
      <Route path="/employees" element={<ProtectedRoute><EmployeesPage /></ProtectedRoute>} />
      <Route path="/pay-supplier" element={<ProtectedRoute><PaySupplierPage /></ProtectedRoute>} />
      <Route path="/count-sheets" element={<ProtectedRoute><CountSheetsPage /></ProtectedRoute>} />
      <Route path="/import" element={<ProtectedRoute><ImportPage /></ProtectedRoute>} />
      <Route path="/reports" element={<ProtectedRoute><ReportsPage /></ProtectedRoute>} />
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
