import React, { useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import FactCheckerInput from './components/FactCheckerInput';
import FactCheckerResult from './components/FactCheckerResult';
import LoadingAnimation from './components/LoadingAnimation';
import Login from './components/Login';
import Signup from './components/Signup';
import ProtectedRoute from './components/ProtectedRoute';
import Navbar from './components/Navbar';
import './App.css';

function HomePage() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  return (
    <>
      <Navbar />
      <div className="container">
        <header className="app-header">
          <h1 className="app-title">Bringing Clarity to Every Claim</h1>
          {/* <p className="app-subtitle">Verify claims with AI-powered research</p> */}
        </header>
        <FactCheckerInput onResult={setResult} loading={loading} setLoading={setLoading} />
        {loading && <LoadingAnimation />}
        {!loading && <FactCheckerResult result={result} />}
      </div>
    </>
  );
}

function App() {
  const { isAuthenticated } = useAuth();

  return (
    <Routes>
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/" replace /> : <Login />}
      />
      <Route
        path="/signup"
        element={isAuthenticated ? <Navigate to="/" replace /> : <Signup />}
      />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <HomePage />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}

export default App;
