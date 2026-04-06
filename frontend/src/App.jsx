/**
 * Auto-Apply Frontend — Root Application Component.
 *
 * Sets up React Router with page-level routing and global authentication state.
 * Wraps all routes in AuthProvider for global auth state management.
 */

import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, ProtectedRoute } from './contexts/AuthContext';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Resumes from './pages/Resumes';
import Jobs from './pages/Jobs';
import JobDetail from './pages/JobDetail';
import Benchmarks from './pages/Benchmarks';
import Interview from './pages/Interview';
import Login from './pages/Login';
import JobPreferences from './components/JobPreferences';
import './App.css';

/**
 * Root application component with client-side routing and authentication.
 *
 * Routes:
 *   /login      → Authentication page (public)
 *   /dashboard  → Main dashboard (protected)
 *   /           → Redirects to /dashboard
 *   *           → 404 redirect to dashboard
 *
 * @returns {JSX.Element} The routed application wrapped with AuthProvider.
 */
function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<Login />} />

          {/* Protected routes */}
          <Route element={<Layout />}>
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/resumes"
              element={
                <ProtectedRoute>
                  <Resumes />
                </ProtectedRoute>
              }
            />
            <Route
              path="/jobs"
              element={
                <ProtectedRoute>
                  <Jobs />
                </ProtectedRoute>
              }
            />
            <Route
              path="/jobs/:jobId"
              element={
                <ProtectedRoute>
                  <JobDetail />
                </ProtectedRoute>
              }
            />
            <Route
              path="/benchmarks"
              element={
                <ProtectedRoute>
                  <Benchmarks />
                </ProtectedRoute>
              }
            />
            <Route
              path="/interview"
              element={
                <ProtectedRoute>
                  <Interview />
                </ProtectedRoute>
              }
            />
            <Route
              path="/settings"
              element={
                <ProtectedRoute>
                  <div className="animate-fade-in card" style={{ maxWidth: '800px', margin: '0 auto' }}>
                    <h2 style={{ marginBottom: 'var(--space-6)' }}>Account Settings</h2>
                    <JobPreferences />
                  </div>
                </ProtectedRoute>
              }
            />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Navigate to="/dashboard" replace />
                </ProtectedRoute>
              }
            />
            <Route
              path="*"
              element={
                <ProtectedRoute>
                  <Navigate to="/dashboard" replace />
                </ProtectedRoute>
              }
            />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
