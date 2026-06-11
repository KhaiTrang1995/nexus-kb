import { useState, useEffect } from 'react'
import { Routes, Route, Link, useLocation } from 'react-router-dom'
import SearchView from './features/search/SearchView'
import ReviewView from './features/review/ReviewView'
import GraphView from './features/graph/GraphView'
import AuditView from './features/audit/AuditView'

type User = { id: string; name: string; role: string }

const MOCK_USERS: User[] = [
  { id: 'u1', name: 'Alice', role: '' },          // Searcher (default)
  { id: 'u2', name: 'Bob', role: 'Reviewer' },
  { id: 'u3', name: 'Carol', role: 'Auditor' },
]

export default function App() {
  const [currentUser, setCurrentUser] = useState<User | null>(null)
  const [showLogin, setShowLogin] = useState(false)
  const location = useLocation()

  // Persist mock login
  useEffect(() => {
    const saved = localStorage.getItem('nexus-current-user')
    if (saved) setCurrentUser(JSON.parse(saved))
    else setShowLogin(true) // first time: force login
  }, [])

  const loginAs = (user: User) => {
    setCurrentUser(user)
    localStorage.setItem('nexus-current-user', JSON.stringify(user))
    setShowLogin(false)
  }

  const logout = () => {
    setCurrentUser(null)
    localStorage.removeItem('nexus-current-user')
    setShowLogin(true)
  }

  const role = currentUser?.role || ''
  const userId = currentUser?.id || 'anonymous'

  // Permission-gated nav (per design)
  const navItems = [
    { path: '/', label: 'Search', icon: '🔍', always: true },
    { path: '/review', label: 'Review Queue', icon: '✅', requireRole: 'Reviewer' },
    { path: '/graph', label: 'Graph', icon: '🕸️', always: true },
    { path: '/audit', label: 'Audit', icon: '📜', always: true },
  ].filter(item => item.always || (item.requireRole && role === item.requireRole))

  const canBuildGraph = role === 'Reviewer' || role === 'Auditor'
  const canSeeAdvancedAudit = role === 'Auditor'

  return (
    <div className="min-h-screen bg-kb-dark text-kb-text">
      <header className="border-b border-kb-primary/20 bg-kb-surface/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="font-bold text-xl tracking-tight">Nexus-KB</div>
            <div className="text-xs px-2 py-0.5 rounded bg-kb-primary/10 text-kb-primary">Operational Console</div>
          </div>

          {/* User / Login area (replaces simple switcher) */}
          {currentUser ? (
            <div className="flex items-center gap-3 text-xs">
              <span className="text-kb-muted">Logged in as</span>
              <span className="font-medium">{currentUser.name} ({currentUser.role || 'Searcher'})</span>
              <button onClick={logout} className="kb-btn border border-kb-primary/30 text-xs px-2 py-0.5">Logout</button>
              <button onClick={() => setShowLogin(true)} className="kb-btn border border-kb-primary/30 text-xs px-2 py-0.5">Switch user</button>
            </div>
          ) : (
            <button onClick={() => setShowLogin(true)} className="kb-btn kb-btn-primary text-xs">Login (mock)</button>
          )}
        </div>

        <nav className="max-w-7xl mx-auto px-6 border-t border-kb-primary/10">
          <div className="flex gap-1 py-2">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={`nav-link flex items-center gap-2 text-sm ${location.pathname === item.path ? 'active' : ''}`}
              >
                <span>{item.icon}</span>
                <span>{item.label}</span>
              </Link>
            ))}
            <div className="ml-auto text-xs text-kb-muted self-center">
              Proxy → localhost:8000 | Headers: X-User-Role / X-User-Id | Synthetic OK
            </div>
          </div>
        </nav>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6">
        <Routes>
          <Route path="/" element={<SearchView currentUser={currentUser} />} />
          <Route path="/review" element={<ReviewView currentUser={currentUser} />} />
          <Route path="/graph" element={<GraphView canBuild={canBuildGraph} currentUser={currentUser} />} />
          <Route path="/audit" element={<AuditView canAdvanced={canSeeAdvancedAudit} currentUser={currentUser} />} />
        </Routes>
      </main>

      <footer className="text-center text-xs text-kb-muted py-8 border-t border-kb-primary/10">
        Compact operational UI • Mock login + role-based permissions (design in docs/UI/) • Backend Phases 1-5 + document graph links complete
      </footer>

      {/* Login Modal (ASCII-designed) */}
      {showLogin && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-[100]">
          <div className="kb-card w-full max-w-md p-6">
            <h3 className="font-semibold text-lg mb-1">Nexus-KB Login (Mock / Dev)</h3>
            <p className="text-sm text-kb-muted mb-4">Select user to simulate role &amp; actor context. Sets X-User-Role + X-User-Id headers.</p>

            <div className="space-y-2">
              {MOCK_USERS.map(u => (
                <button
                  key={u.id}
                  onClick={() => loginAs(u)}
                  className={`w-full text-left kb-card p-3 hover:border-kb-primary/50 ${currentUser?.id === u.id ? 'border-kb-primary' : ''}`}
                >
                  <div className="font-medium">{u.name} — {u.role || 'Searcher'}</div>
                  <div className="text-xs text-kb-muted">
                    {u.role === 'Reviewer' && 'Can: Review Queue + actions'}
                    {u.role === 'Auditor' && 'Can: + full Audit + Graph build'}
                    {!u.role && 'Can: Search, view Graph context, read Audit'}
                  </div>
                </button>
              ))}
            </div>

            <div className="mt-4 flex gap-2">
              <button onClick={() => { loginAs(MOCK_USERS[0]); }} className="kb-btn border border-kb-primary/30 flex-1">Use default (Alice - Searcher)</button>
              <button onClick={() => setShowLogin(false)} className="kb-btn border border-kb-primary/30 flex-1">Cancel</button>
            </div>
            <div className="text-[10px] text-kb-muted mt-3">Synthetic only. Real JWT/OIDC planned later.</div>
          </div>
        </div>
      )}
    </div>
  )
}
