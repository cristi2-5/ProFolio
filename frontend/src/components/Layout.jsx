/**
 * Layout Component — Application shell with sidebar navigation.
 *
 * Wraps all authenticated pages with a persistent sidebar
 * and main content area. Uses React Router's Outlet for
 * rendering child routes.
 */

import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const navItems = [
  { path: '/dashboard', label: 'Dashboard', icon: '📊' },
  { path: '/resumes', label: 'My Resumes', icon: '📄' },
  { path: '/jobs', label: 'Job Matches', icon: '🔍' },
  { path: '/benchmarks', label: 'Benchmarks', icon: '📈' },
  { path: '/interview', label: 'Interview Prep', icon: '🎯' },
  { path: '/settings', label: 'Settings', icon: '⚙️' },
];

/**
 * Application layout shell.
 *
 * Provides:
 * - Fixed sidebar with logo and navigation links.
 * - Logged-in user identity + logout button anchored at the bottom.
 * - Main content area that renders the current route's component.
 *
 * @returns {JSX.Element} The layout wrapper with sidebar and outlet.
 */
function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <div className="app-layout">
      <aside
        className="sidebar"
        role="navigation"
        aria-label="Main navigation"
        style={{ display: 'flex', flexDirection: 'column' }}
      >
        <div className="sidebar-logo">
          <h1>
            <span className="text-gradient">Auto</span>Apply
          </h1>
        </div>

        <nav className="sidebar-nav" style={{ flex: 1 }}>
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `nav-item ${isActive ? 'active' : ''}`
              }
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        {user && (
          <div
            style={{
              borderTop: '1px solid var(--color-border)',
              padding: 'var(--space-3) var(--space-2)',
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--space-2)',
            }}
          >
            <div
              title={user.email}
              style={{
                fontSize: 'var(--font-size-xs)',
                color: 'var(--color-text-muted)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {user.full_name || user.email}
            </div>
            <button
              type="button"
              onClick={handleLogout}
              className="btn btn-secondary"
              style={{
                fontSize: 'var(--font-size-sm)',
                padding: 'var(--space-2)',
                width: '100%',
              }}
            >
              🚪 Log out
            </button>
          </div>
        )}
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}

export default Layout;
