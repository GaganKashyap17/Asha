import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import VoiceRegisterPage from './pages/VoiceRegisterPage'
import BeneficiaryRegisterPage from './pages/BeneficiaryRegisterPage'
import RevisitPage from './pages/RevisitPage'
import BeneficiaryPage from './pages/BeneficiaryPage'
import VisitHistoryPage from './pages/VisitHistoryPage'
import FollowUpPage from './pages/FollowUpPage'
import EmergencyAlertPage from './pages/EmergencyAlertPage'
import SettingsPage from './pages/SettingsPage'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import Layout from './components/layout/Layout'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAuth()
  return token ? <>{children}</> : <Navigate to="/login" />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={<PrivateRoute><Layout><DashboardPage /></Layout></PrivateRoute>} />
          <Route path="/voice" element={<PrivateRoute><Layout><VoiceRegisterPage /></Layout></PrivateRoute>} />
          <Route path="/register" element={<PrivateRoute><Layout><BeneficiaryRegisterPage /></Layout></PrivateRoute>} />
          <Route path="/revisit" element={<PrivateRoute><Layout><RevisitPage /></Layout></PrivateRoute>} />
          <Route path="/beneficiaries" element={<PrivateRoute><Layout><BeneficiaryPage /></Layout></PrivateRoute>} />
          <Route path="/visits" element={<PrivateRoute><Layout><VisitHistoryPage /></Layout></PrivateRoute>} />
          <Route path="/followups" element={<PrivateRoute><Layout><FollowUpPage /></Layout></PrivateRoute>} />
          <Route path="/alerts" element={<PrivateRoute><Layout><EmergencyAlertPage /></Layout></PrivateRoute>} />
          <Route path="/settings" element={<PrivateRoute><Layout><SettingsPage /></Layout></PrivateRoute>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
