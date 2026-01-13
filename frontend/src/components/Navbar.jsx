import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { logout as logoutApi } from '../services/authApi';
import './Navbar.css';

function Navbar() {
  const { user, logout, isAuthenticated } = useAuth();
  const [showDropdown, setShowDropdown] = useState(false);

  const handleLogout = async () => {
    try {
      await logoutApi();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      logout();
    }
  };

  if (!isAuthenticated) {
    return null;
  }

  return (
    <nav className="navbar">
      <div className="navbar-content">

        {/* ✅ LOGO ADDED HERE (REPLACE TEXT TITLE) */}
        <div className="navbar-brand">
          <img
            src="/logo.png"   // ✅ place logo.png inside /public
            alt="Logo"
            className="navbar-logo"
            style={{ height: "70px", width: "auto" }}
          />
        </div>

        <div className="navbar-user">
          <button
            className="user-button"
            onClick={() => setShowDropdown(!showDropdown)}
          >
            <div className="user-avatar">
              {user?.name?.charAt(0).toUpperCase() || 'U'}
            </div>
            <span className="user-name">{user?.name}</span>
            <svg
              className={`dropdown-icon ${showDropdown ? 'open' : ''}`}
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
            >
              <path
                d="M4 6L8 10L12 6"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>

          {showDropdown && (
            <>
              <div
                className="dropdown-overlay"
                onClick={() => setShowDropdown(false)}
              />
              <div className="dropdown-menu">
                <div className="dropdown-header">
                  <div className="dropdown-user-info">
                    <p className="dropdown-user-name">{user?.name}</p>
                    <p className="dropdown-user-email">{user?.email}</p>
                  </div>
                </div>
                <div className="dropdown-divider" />
                <button
                  className="dropdown-item logout-button"
                  onClick={handleLogout}
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                    <path
                      d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  Logout
                </button>
              </div>
            </>
          )}
        </div>

      </div>
    </nav>
  );
}

export default Navbar;
