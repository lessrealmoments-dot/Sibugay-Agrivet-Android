import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import axios from 'axios';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { Toaster } from './components/ui/sonner';
import Layout from './components/Layout';
import FeatureGate from './components/FeatureGate';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import UpgradePage from './pages/UpgradePage';
import SuperAdminPage from './pages/SuperAdminPage';
import AdminLoginPage from './pages/AdminLoginPage';
import SetupWizardPage from './pages/SetupWizardPage';
import DashboardPage from './pages/DashboardPage';
import BranchesPage from './pages/BranchesPage';
import BranchTransferPage from './pages/BranchTransferPage';
import InternalInvoicesPage from './pages/InternalInvoicesPage';
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
import PriceScanManager from './components/PriceScanManager';
import ReturnRefundWizard from './pages/ReturnRefundWizard';
import AuditCenterPage from './pages/AuditCenterPage';
import TeamPage from './pages/TeamPage';
import UploadPage from './pages/UploadPage';
import ViewReceiptsPage from './pages/ViewReceiptsPage';
import BackupManagementPage from './pages/BackupManagementPage';
import IncidentTicketsPage from './pages/IncidentTicketsPage';
import BarcodePrintPage from './pages/BarcodePrintPage';
import BarcodeManagePage from './pages/BarcodeManagePage';
import MobileScannerPage from './pages/MobileScannerPage';
import ExpensesPage from './pages/ExpensesPage';

// Legacy pages (keep files but not in primary nav)
// POSPage → replaced by UnifiedSalesPage (/sales-new)
// SalesOrderPage → replaced by UnifiedSalesPage order mode

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex items-center justify-center h-screen bg-[#F5F5F0]"><div className="text-slate-400 text-sm">Loading...</div></div>;
  if (!user) return <Navigate to="/login" replace />;
  return (
    <Layout>
      <PriceScanManager />
      {children}
    </Layout>
  );
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

  // If setup is needed (fresh install, no users), show setup wizard
  // NOTE: /admin and /login are always accessible so users can log in even on fresh installs
  if (setupNeeded && !user) {
    return (
      <Routes>
        <Route path="/setup" element={<SetupWizardPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<LandingPage />} />
        <Route path="/admin" element={<AdminLoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <Routes>
      {/* Public routes */}
      <Route path="/" element={user ? <Navigate to="/dashboard" replace /> : <LandingPage />} />
      <Route path="/register" element={user ? <Navigate to="/dashboard" replace /> : <RegisterPage />} />
      <Route path="/setup" element={<Navigate to="/dashboard" replace />} />
      <Route path="/login" element={user ? <Navigate to="/dashboard" replace /> : <LoginPage />} />

      {/* Platform admin portal — separate entry point */}
      <Route path="/admin" element={<AdminLoginPage />} />

      {/* Super admin panel (protected, requires is_super_admin) */}
      <Route path="/superadmin" element={<ProtectedRoute><SuperAdminPage /></ProtectedRoute>} />

      {/* Upgrade page (inside app) */}
      <Route path="/upgrade" element={<ProtectedRoute><UpgradePage /></ProtectedRoute>} />

      <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
      <Route path="/branches" element={<ProtectedRoute><BranchesPage /></ProtectedRoute>} />
      <Route path="/branch-transfers" element={<ProtectedRoute><FeatureGate featureKey="branch_transfers"><BranchTransferPage /></FeatureGate></ProtectedRoute>} />
      <Route path="/internal-invoices" element={<ProtectedRoute><InternalInvoicesPage /></ProtectedRoute>} />
      <Route path="/products" element={<ProtectedRoute><ProductsPage /></ProtectedRoute>} />
      <Route path="/products/:id" element={<ProtectedRoute><ProductDetailPage /></ProtectedRoute>} />
      <Route path="/inventory" element={<ProtectedRoute><InventoryPage /></ProtectedRoute>} />
      <Route path="/sales-new" element={<ProtectedRoute><UnifiedSalesPage /></ProtectedRoute>} />
      <Route path="/pos" element={<ProtectedRoute><POSPage /></ProtectedRoute>} />
      <Route path="/customers" element={<ProtectedRoute><CustomersPage /></ProtectedRoute>} />
      <Route path="/price-schemes" element={<ProtectedRoute><PriceSchemesPage /></ProtectedRoute>} />
      <Route path="/sales" element={<ProtectedRoute><SalesPage /></ProtectedRoute>} />
      <Route path="/sales-order" element={<ProtectedRoute><SalesOrderPage /></ProtectedRoute>} />
      <Route path="/purchase-orders" element={<ProtectedRoute><FeatureGate featureKey="purchase_orders"><PurchaseOrderPage /></FeatureGate></ProtectedRoute>} />
      <Route path="/suppliers" element={<ProtectedRoute><FeatureGate featureKey="supplier_management"><SuppliersPage /></FeatureGate></ProtectedRoute>} />
      <Route path="/daily-ops" element={<ProtectedRoute><DailyLogPage /></ProtectedRoute>} />
      <Route path="/close-wizard" element={<ProtectedRoute><CloseWizardPage /></ProtectedRoute>} />
      <Route path="/payments" element={<ProtectedRoute><PaymentsPage /></ProtectedRoute>} />
      <Route path="/fund-management" element={<ProtectedRoute><FeatureGate featureKey="full_fund_management"><FundManagementPage /></FeatureGate></ProtectedRoute>} />
      <Route path="/expenses" element={<ProtectedRoute><ExpensesPage /></ProtectedRoute>} />
      <Route path="/accounting" element={<ProtectedRoute><AccountingPage /></ProtectedRoute>} />
      <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
      <Route path="/team" element={<ProtectedRoute><TeamPage /></ProtectedRoute>} />
      <Route path="/user-permissions" element={<ProtectedRoute><FeatureGate featureKey="granular_permissions"><UserPermissionsPage /></FeatureGate></ProtectedRoute>} />
      <Route path="/accounts" element={<ProtectedRoute><AccountsPage /></ProtectedRoute>} />
      <Route path="/employees" element={<ProtectedRoute><FeatureGate featureKey="employee_management"><EmployeesPage /></FeatureGate></ProtectedRoute>} />
      <Route path="/pay-supplier" element={<ProtectedRoute><FeatureGate featureKey="purchase_orders"><PaySupplierPage /></FeatureGate></ProtectedRoute>} />
      <Route path="/count-sheets" element={<ProtectedRoute><CountSheetsPage /></ProtectedRoute>} />
      <Route path="/import" element={<ProtectedRoute><ImportPage /></ProtectedRoute>} />
      <Route path="/reports" element={<ProtectedRoute><FeatureGate featureKey="advanced_reports"><ReportsPage /></FeatureGate></ProtectedRoute>} />
      <Route path="/returns" element={<ProtectedRoute><ReturnRefundWizard /></ProtectedRoute>} />
      <Route path="/audit" element={<ProtectedRoute><FeatureGate featureKey="audit_center"><AuditCenterPage /></FeatureGate></ProtectedRoute>} />
      <Route path="/incident-tickets" element={<ProtectedRoute><IncidentTicketsPage /></ProtectedRoute>} />
      <Route path="/backups" element={<ProtectedRoute><BackupManagementPage /></ProtectedRoute>} />
      <Route path="/barcode-print" element={<ProtectedRoute><BarcodePrintPage /></ProtectedRoute>} />
      <Route path="/barcode-manage" element={<ProtectedRoute><BarcodeManagePage /></ProtectedRoute>} />
      <Route path="/scanner/:sessionId" element={<MobileScannerPage />} />
      {/* Public upload page — no auth, token-based */}
      <Route path="/upload/:token" element={<UploadPage />} />
      {/* Public view-receipts page — no auth, token-based */}
      <Route path="/view-receipts/:token" element={<ViewReceiptsPage />} />
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
