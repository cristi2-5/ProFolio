/**
 * Auto-Apply Frontend — Root Application Component.
 *
 * Sets up React Router with page-level routing.
 * Wraps all routes in the Layout shell (nav + sidebar).
 */

import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Login from './pages/Login';
import './App.css';

/**
 * Root application component with client-side routing.
 *
 * Routes:
 *   /           → Redirects to /dashboard
 *   /dashboard  → Main dashboard (job listings, stats)
 *   /login      → Authentication page
 *   *           → 404 redirect to dashboard
 *
 * @returns {JSX.Element} The routed application.
 */
function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<Layout />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
