# Authentication System Guide

## Overview

Your Fact Checker app now has a complete, secure authentication system integrated. This guide explains what was added and how to use it.

## Features Implemented

### ✅ Backend (FastAPI)

1. **User Management**
   - User signup with validation
   - User login with credentials
   - Password hashing with bcrypt (12 rounds)
   - MongoDB user storage with unique email index

2. **JWT Authentication**
   - Access tokens (30-minute expiry)
   - Refresh tokens (30-day expiry)
   - Token refresh endpoint
   - Secure token verification middleware

3. **API Endpoints** (all under `/api/auth`)
   - `POST /signup` - Register new user
   - `POST /login` - Authenticate user
   - `POST /refresh` - Refresh access token
   - `POST /logout` - Logout user (client-side token removal)
   - `GET /me` - Get current user info

4. **Protected Routes**
   - All fact-checking endpoints now require authentication
   - `POST /api/claims/` - Text fact checking
   - `POST /api/claims/multimodal` - Multimodal fact checking
   - `POST /api/claims/url` - URL fact checking

5. **Security Features**
   - Password validation (min 8 chars, uppercase, lowercase, digit)
   - Email validation
   - Duplicate email prevention
   - Secure password hashing (never stored in plain text)
   - JWT signature verification

### ✅ Frontend (React)

1. **Pages**
   - Login page (`/login`)
   - Signup page (`/signup`)
   - Protected home page (`/`)

2. **Components**
   - `Login.jsx` - Login form with error handling
   - `Signup.jsx` - Registration form with password validation
   - `Navbar.jsx` - User profile display with dropdown menu
   - `ProtectedRoute.jsx` - Route guard component

3. **Authentication Context**
   - `AuthContext` provides global auth state
   - Automatic token persistence in localStorage
   - User session management

4. **Features**
   - Auto-redirect to login if not authenticated
   - Auto-redirect to home if already logged in
   - Persistent sessions across page refreshes
   - User profile display in navbar
   - Logout functionality

## Setup Instructions

### 1. Backend Setup

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
# Copy .env.example to .env and update:
cp .env.example .env

# Edit .env and add:
# - JWT_SECRET_KEY (generate with: openssl rand -hex 32)
# - GEMINI_API_KEY (required)
# - MONGO_URI (required)
# - PERPLEXITY_API_KEY (optional)

# Start the backend server
uvicorn main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start the frontend
npm start
```

The app will open at `http://localhost:3000` and redirect you to login.

## Usage Flow

### First-Time User

1. Navigate to `http://localhost:3000`
2. You'll be redirected to `/login`
3. Click "Sign up" link
4. Fill in:
   - Full Name (min 2 characters)
   - Email (valid email format)
   - Password (min 8 chars with uppercase, lowercase, digit)
   - Confirm Password
5. Click "Sign Up"
6. You'll be automatically logged in and redirected to home page

### Returning User

1. Navigate to `http://localhost:3000`
2. Enter email and password
3. Click "Sign In"
4. You'll be redirected to the fact checker

### Using the Fact Checker

Once logged in:
- Use the fact checker as normal
- All requests automatically include your JWT token
- Your name appears in the navbar
- Click on your profile to see dropdown menu
- Click "Logout" to sign out

## API Authentication

All fact-checking API calls now require authentication. The frontend automatically includes the JWT token in the `Authorization` header:

```javascript
Authorization: Bearer <access_token>
```

### Example: Manual API Call

```bash
# Login first
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "Password123"}'

# Use the access_token from response
curl -X POST http://localhost:8000/api/claims/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"claim_text": "The Earth is round"}'
```

## Token Management

### Access Token
- **Expires**: 30 minutes
- **Purpose**: Authenticate API requests
- **Storage**: localStorage (frontend)

### Refresh Token
- **Expires**: 30 days
- **Purpose**: Get new access tokens without re-login
- **Storage**: localStorage (frontend)
- **Usage**: Call `/api/auth/refresh` when access token expires

### Token Refresh Flow

The frontend can implement automatic token refresh:

```javascript
// import { refreshAccessToken } from './services/authApi';

// // When API returns 401 Unauthorized
// try {
//   const refreshToken = localStorage.getItem('refresh_token');
//   const { access_token } = await refreshAccessToken(refreshToken);
//   // Update token and retry request
// } catch (error) {
//   // Refresh failed - redirect to login
// }
```

## Database Schema

### Users Collection

```javascript
{
  _id: ObjectId,
  name: String,
  email: String (unique, lowercase),
  password_hash: String,
  created_at: DateTime,
  updated_at: DateTime
}
```

## Security Best Practices

1. **JWT Secret Key**: Use a strong, random secret key in production
   ```bash
   # Generate secure key
  
   ```

2. **HTTPS**: Always use HTTPS in production to protect tokens in transit

3. **Environment Variables**: Never commit `.env` file to version control

4. **Token Storage**:
   - localStorage is used for simplicity
   - For higher security, consider HTTP-only cookies

5. **Password Policy**: Current requirements:
   - Minimum 8 characters
   - At least one uppercase letter
   - At least one lowercase letter
   - At least one digit

## File Structure

### Backend Files Added

```
backend/
├── app/
│   ├── api/
│   │   └── auth_api.py              # Auth endpoints
│   ├── middleware/
│   │   └── auth_middleware.py       # JWT verification
│   ├── models/
│   │   └── user.py                  # User models
│   ├── repository/
│   │   └── user_repository.py       # User database operations
│   └── services/
│       ├── auth_service.py          # Auth business logic
│       ├── password_service.py      # Password hashing
│       └── token_service.py         # JWT operations
├── requirements.txt                  # Added: bcrypt, pyjwt, email-validator
└── .env.example                     # Added: JWT config
```

### Frontend Files Added

```
frontend/
├── src/
│   ├── components/
│   │   ├── Login.jsx                # Login page
│   │   ├── Signup.jsx               # Signup page
│   │   ├── Navbar.jsx               # User navbar
│   │   ├── ProtectedRoute.jsx       # Route guard
│   │   ├── Auth.css                 # Auth styles
│   │   └── Navbar.css               # Navbar styles
│   ├── context/
│   │   └── AuthContext.jsx          # Auth state management
│   ├── services/
│   │   ├── authApi.js               # Auth API calls
│   │   └── api.js                   # Updated with auth headers
│   ├── App.jsx                      # Updated with routing
│   └── index.js                     # Added Router + AuthProvider
└── package.json                     # Added: react-router-dom
```

## Troubleshooting

### "Invalid or expired token" error
- Token may have expired (30 min for access token)
- Solution: Logout and login again, or implement token refresh

### "Email already registered"
- Email is already in use
- Solution: Use a different email or login with existing account

### Password validation errors
- Ensure password meets requirements:
  - At least 8 characters
  - Contains uppercase letter
  - Contains lowercase letter
  - Contains digit

### CORS errors
- Ensure `FRONTEND_URL` in backend `.env` matches your frontend URL
- Default: `http://localhost:3000`

### MongoDB connection issues
- Verify `MONGO_URI` in `.env` is correct
- Ensure MongoDB is running and accessible

## Next Steps (Optional Enhancements)

1. **Forgot Password**
   - Email-based password reset
   - OTP verification

2. **Google OAuth**
   - Social login integration
   - FastAPI OAuth2 provider

3. **Profile Management**
   - Update user name
   - Change password
   - Delete account

4. **Session History**
   - View past fact-check queries
   - Saved claims

5. **Rate Limiting**
   - Prevent abuse
   - Limit requests per user

6. **Email Verification**
   - Send verification email on signup
   - Verify email before allowing login

## Support

If you encounter issues:
1. Check that all dependencies are installed
2. Verify `.env` configuration
3. Check backend and frontend logs for errors
4. Ensure MongoDB is running

Your authentication system is now complete and ready to use!
