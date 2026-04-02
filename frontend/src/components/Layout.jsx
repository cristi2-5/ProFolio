/**
 * Layout Component — Application shell with sidebar navigation.
 *
 * Wraps all authenticated pages with a persistent sidebar
 * and main content area. Uses React Router's Outlet for
 * rendering child routes.
 */

import { NavLink, Outlet } from 'react-router-dom';

/**
 * Navigation items configuration.
 * Each item defines a route path, display label, and icon emoji.
 *
 * @type {Array<{path: string, label: string, icon: string}>}
 */
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
 * - Main content area that renders the current route's component.
 * - Active state styling via NavLink.
 *
 * @returns {JSX.Element} The layout wrapper with sidebar and outlet.
 */
function Layout() {
  return (
    <div className="app-layout">
      <aside className="sidebar" role="navigation" aria-label="Main navigation">
        <div className="sidebar-logo">
          <h1>
            <span className="text-gradient">Auto</span>Apply
          </h1>
        </div>
        <nav className="sidebar-nav">
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
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}

export default Layout;
