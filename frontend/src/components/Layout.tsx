import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Users, FolderKanban, Lightbulb,
  BarChart3, LogOut, Zap, Bell
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { authAPI } from '@/api/services'
import clsx from 'clsx'

const navItems = [
  { to: '/dashboard',       icon: LayoutDashboard,  label: 'Executive View' },
  { to: '/manager',         icon: BarChart3,         label: 'Manager View'   },
  { to: '/team',            icon: Users,             label: 'Team Utilization'},
  { to: '/projects',        icon: FolderKanban,      label: 'Project Health' },
  { to: '/recommendations', icon: Lightbulb,         label: 'Recommendations'},
]

export default function Layout() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = async () => {
    try { await authAPI.logout() } catch {}
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen overflow-hidden bg-surface">
      {/* Sidebar */}
      <aside className="w-64 flex-shrink-0 flex flex-col bg-surface-50 border-r border-surface-200">
        {/* Logo */}
        <div className="flex items-center gap-3 px-6 py-5 border-b border-surface-200">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center shadow-glow">
            <Zap size={16} className="text-white" />
          </div>
          <div>
            <p className="text-sm font-bold text-white">WOP</p>
            <p className="text-xs text-slate-500">Workforce Optimizer</p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150',
                  isActive
                    ? 'bg-brand-600/20 text-brand-400 border border-brand-500/30 shadow-glow'
                    : 'text-slate-400 hover:text-white hover:bg-surface-100'
                )
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* User footer */}
        <div className="p-4 border-t border-surface-200">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-brand-600 flex items-center justify-center text-xs font-bold text-white">
              {user?.name?.[0]?.toUpperCase() ?? 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">{user?.name}</p>
              <p className="text-xs text-slate-500 capitalize">{user?.role}</p>
            </div>
          </div>
          <button onClick={handleLogout} className="btn-ghost w-full justify-start text-slate-400 hover:text-red-400">
            <LogOut size={14} />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="h-14 flex items-center justify-between px-6 border-b border-surface-200 bg-surface-50/50 backdrop-blur-sm">
          <h1 className="text-sm font-medium text-slate-400">Workforce Optimization Platform</h1>
          <button className="relative p-2 rounded-lg hover:bg-surface-100 text-slate-400 hover:text-white transition-colors">
            <Bell size={18} />
          </button>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
