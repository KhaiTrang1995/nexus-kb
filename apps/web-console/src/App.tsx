import { useState, useEffect } from 'react'
import { Routes, Route, Link, useLocation } from 'react-router-dom'
import SearchView from './features/search/SearchView'
import ReviewView from './features/review/ReviewView'
import GraphView from './features/graph/GraphView'
import AuditView from './features/audit/AuditView'
import IngestionView from './features/ingestion/IngestionView'
import { type NexusUser, getSavedUser, clearAuth, loginDev } from './lib/auth'

// Dev-login roster. `is_admin` here is a *system* admin (workspace/user
// management, bypasses workspace filtering everywhere) -- a separate axis
// from `role` (Reviewer/Auditor, the Phase 2 review-queue privilege). Carol
// is marked admin so the demo has at least one user who can see everything
// without needing a workspace pre-seeded; Alice/Bob have no workspace
// membership yet, so search/upload/chat correctly show nothing for them
// until an admin adds them to a workspace via POST /api/v1/workspaces.
const MOCK_USERS: NexusUser[] = [
  { id: 'u1', name: 'Alice', role: '', is_admin: false, workspace_ids: [] },
  { id: 'u2', name: 'Bob', role: 'Reviewer', is_admin: false, workspace_ids: [] },
  { id: 'u3', name: 'Carol', role: 'Auditor', is_admin: true, workspace_ids: [] },
]

const NAV_ITEMS = [
  { path: '/', label: 'Search', icon: 'S', always: true },
  { path: '/ingest', label: 'Ingest', icon: 'I', requireRole: 'Reviewer' },
  { path: '/review', label: 'Review', icon: 'R', requireRole: 'Reviewer' },
  { path: '/graph', label: 'Graph', icon: 'G', always: true },
  { path: '/audit', label: 'Audit', icon: 'A', always: true },
]

function roleLabel(role: string): string {
  return role || 'Searcher'
}

export default function App() {
  const [currentUser, setCurrentUser] = useState<NexusUser | null>(null)
  const [showLogin, setShowLogin] = useState(false)
  const [loginError, setLoginError] = useState<string | null>(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const location = useLocation()

  useEffect(() => {
    const saved = getSavedUser()
    if (saved) setCurrentUser(saved)
    else setShowLogin(true)
  }, [])

  const loginAs = async (user: NexusUser) => {
    setLoginError(null)
    try {
      const authed = await loginDev(
        user.id,
        user.name,
        user.role,
        user.is_admin ?? false,
        user.workspace_ids ?? [],
      )
      setCurrentUser(authed)
      setShowLogin(false)
    } catch {
      setLoginError('Backend unavailable. Check that the API server is running.')
    }
  }

  const logout = () => {
    setCurrentUser(null)
    clearAuth()
    setShowLogin(true)
  }

  const role = currentUser?.role || ''
  const visibleNav = NAV_ITEMS.filter(
    item => item.always || (item.requireRole && (role === item.requireRole || role === 'Auditor'))
  )
  const canBuildGraph = role === 'Reviewer' || role === 'Auditor'
  const canSeeAdvancedAudit = role === 'Auditor'

  return (
    <div className="min-h-screen bg-kb-dark text-kb-text">
      {/* Sidebar */}
      <aside className={`sidebar ${sidebarCollapsed ? 'collapsed' : ''}`} data-testid="sidebar">
        <div className="flex items-center gap-2 px-3 h-12 border-b border-kb-primary/10">
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="text-kb-muted hover:text-kb-text text-sm w-5 h-5 flex items-center justify-center"
            aria-label="Toggle sidebar"
          >
            =
          </button>
          {!sidebarCollapsed && (
            <span className="font-bold text-sm tracking-tight">Nexus-KB</span>
          )}
        </div>

        <nav className="flex-1 py-2">
          {visibleNav.map(item => (
            <Link
              key={item.path}
              to={item.path}
              className={`sidebar-nav-item ${location.pathname === item.path ? 'active' : ''}`}
            >
              <span className="nav-icon">{item.icon}</span>
              <span className="nav-label">{item.label}</span>
            </Link>
          ))}
        </nav>

        {!sidebarCollapsed && (
          <div className="px-3 py-3 text-[10px] text-kb-muted border-t border-kb-primary/10">
            v0.4.0
          </div>
        )}
      </aside>

      {/* Main area */}
      <div className="main-content" style={{ marginLeft: sidebarCollapsed ? 48 : 200 }}>
        {/* Top bar */}
        <header className="topbar">
          <div className="text-xs text-kb-muted">
            Enterprise Knowledge Hub
          </div>
          {currentUser ? (
            <div className="flex items-center gap-3 text-xs">
              <span className="text-kb-muted">
                {currentUser.name}
              </span>
              <span className="badge badge-primary">{roleLabel(currentUser.role)}</span>
              <button onClick={() => setShowLogin(true)} className="text-kb-muted hover:text-kb-text">
                Switch
              </button>
              <button onClick={logout} className="text-kb-muted hover:text-kb-text">
                Logout
              </button>
            </div>
          ) : (
            <button onClick={() => setShowLogin(true)} className="kb-btn kb-btn-primary text-xs py-1">
              Login
            </button>
          )}
        </header>

        {/* Page content */}
        <main className="p-5">
          <Routes>
            <Route path="/" element={<SearchView />} />
            <Route path="/review" element={<ReviewView currentUser={currentUser} />} />
            <Route path="/ingest" element={<IngestionView currentUser={currentUser} />} />
            <Route path="/graph" element={<GraphView canBuild={canBuildGraph} />} />
            <Route path="/audit" element={<AuditView canAdvanced={canSeeAdvancedAudit} />} />
          </Routes>
        </main>
      </div>

      {/* Login modal */}
      {showLogin && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-[100]">
          <div className="kb-card w-full max-w-sm p-6">
            <div className="text-center mb-5">
              <h3 className="font-bold text-lg">Nexus-KB</h3>
              <p className="text-xs text-kb-muted mt-1">Enterprise Knowledge Hub</p>
            </div>

            <p className="text-sm text-kb-muted mb-4">Select a user to sign in via JWT dev-token.</p>

            {loginError && (
              <div className="mb-3 text-red-400 text-sm border border-red-400/30 rounded px-3 py-2">{loginError}</div>
            )}

            <div className="space-y-2">
              {MOCK_USERS.map(u => (
                <button
                  key={u.id}
                  onClick={() => loginAs(u)}
                  className={`w-full text-left kb-card p-3 hover:border-kb-primary/50 transition ${currentUser?.id === u.id ? 'border-kb-primary' : ''}`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm">{u.name}</span>
                    <span className="badge badge-primary">{roleLabel(u.role)}</span>
                  </div>
                  <div className="text-[11px] text-kb-muted mt-1">
                    {u.role === 'Reviewer' && 'Search + Review Queue + Ingest + Graph build'}
                    {u.role === 'Auditor' && 'All permissions + actor filtering in Audit'}
                    {!u.role && 'Search, view Graph, read Audit log'}
                  </div>
                </button>
              ))}
            </div>

            {currentUser && (
              <button
                onClick={() => setShowLogin(false)}
                className="mt-4 w-full kb-btn border border-kb-primary/30 text-xs"
              >
                Cancel
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
