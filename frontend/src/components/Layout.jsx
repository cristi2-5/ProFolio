/**
 * Layout Component — Application shell with sidebar navigation.
 *
 * Wraps all authenticated pages with a persistent sidebar
 * and main content area. Uses React Router's Outlet for
 * rendering child routes.
 */

import { useState } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import CookieBanner from './CookieBanner';

const navItems = [
  { path: '/dashboard', label: 'Dashboard', icon: '📊' },
  { path: '/resumes', label: 'My Resumes', icon: '📄' },
  { path: '/jobs', label: 'Job Matches', icon: '🔍' },
  { path: '/benchmarks', label: 'Benchmarks', icon: '📈' },
  { path: '/interview', label: 'Interview Prep', icon: '🎯' },
  { path: '/settings', label: 'Settings', icon: '⚙️' },
];

function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  const closeMobileNav = () => setMobileOpen(false);

  const handleLogout = () => {
    closeMobileNav();
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <div className="app-layout">
      <button
        type="button"
        className="mobile-nav-toggle"
        aria-label={mobileOpen ? 'Close navigation' : 'Open navigation'}
        aria-expanded={mobileOpen}
        onClick={() => setMobileOpen((prev) => !prev)}
      >
        {mobileOpen ? '✕' : '☰'}
      </button>

      {mobileOpen && (
        <div
          className="sidebar-backdrop"
          role="presentation"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <aside
        className={`sidebar${mobileOpen ? ' open' : ''}`}
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
              onClick={closeMobileNav}
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
      <main
        className="main-content"
        style={{ display: 'flex', flexDirection: 'column' }}
      >
        <div style={{ flex: 1 }}>
          <Outlet />
        </div>
        <footer
          style={{
            marginTop: 'var(--space-8)',
            padding: 'var(--space-4) 0',
            borderTop: '1px solid var(--color-border)',
            display: 'flex',
            gap: 'var(--space-4)',
            justifyContent: 'center',
            fontSize: 'var(--font-size-sm)',
            color: 'var(--color-text-muted)',
          }}
        >
          <Link to="/privacy">Privacy</Link>
          <Link to="/terms">Terms</Link>
          <Link to="/cookies">Cookies</Link>
        </footer>
      </main>
      <CookieBanner />
    </div>
  );
}

export default Layout;
