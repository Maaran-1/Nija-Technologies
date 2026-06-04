import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import Layout from '@/components/Layout'
import LoginPage from '@/pages/LoginPage'
import ExecutiveDashboard from '@/pages/ExecutiveDashboard'
import ManagerDashboard from '@/pages/ManagerDashboard'
import RecommendationCenter from '@/pages/RecommendationCenter'
import ProjectHealth from '@/pages/ProjectHealth'
import TeamUtilization from '@/pages/TeamUtilization'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<ExecutiveDashboard />} />
          <Route path="manager" element={<ManagerDashboard />} />
          <Route path="recommendations" element={<RecommendationCenter />} />
          <Route path="projects" element={<ProjectHealth />} />
          <Route path="team" element={<TeamUtilization />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
