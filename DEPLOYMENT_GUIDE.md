# Production Deployment Guide

## Environment Variables Setup

### Backend (Render) - Required Environment Variables

Go to your Render dashboard → Your service → Environment tab, and add these variables:

```
GEMINI_API_KEY=<your-gemini-api-key>
PERPLEXITY_API_KEY=<your-perplexity-api-key>
MONGO_URI=<your-mongodb-uri>
FRONTEND_URL=https://fact-checker-pi5i.vercel.app
BACKEND_PORT=10000
BACKEND_HOST=0.0.0.0
GEMINI_MODEL=gemini-2.0-flash
```

**Important Notes:**
- `BACKEND_PORT`: Render typically uses port 10000 (check your service settings)
- `BACKEND_HOST`: Must be `0.0.0.0` to accept external connections
- `FRONTEND_URL`: Your Vercel frontend URL (for CORS)
- Make sure MongoDB password is URL-encoded (`@` becomes `%40`)

### Frontend (Vercel) - Required Environment Variables

Go to Vercel dashboard → Your project → Settings → Environment Variables:

```
REACT_APP_API_BASE_URL=https://fact-checker-e7el.onrender.com
```

**Important Notes:**
- Vercel environment variables must start with `REACT_APP_` to be accessible in React
- After adding variables, you MUST redeploy for changes to take effect
- Click "Redeploy" in Vercel dashboard → Deployments tab

---

## Deployment Checklist

### Backend Deployment (Render)

1. **Push backend code to GitHub**
   ```bash
   git add backend/
   git commit -m "Configure production CORS and environment"
   git push origin main
   ```

2. **Configure Render Service**
   - Build Command: `cd backend && pip install -r requirements.txt`
   - Start Command: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Environment Variables: Add all variables listed above

3. **Verify Deployment**
   - Check logs for any errors
   - Test root endpoint: `https://fact-checker-e7el.onrender.com/`
   - Should return: `{"message": "Fact Checker API is running. Use /api/claims endpoint."}`

### Frontend Deployment (Vercel)

1. **Push frontend code to GitHub**
   ```bash
   git add frontend/
   git commit -m "Configure production API URL"
   git push origin main
   ```

2. **Configure Vercel Project**
   - Build Command: `npm run build` (default for Create React App)
   - Output Directory: `build` (default)
   - Install Command: `npm install`
   - Root Directory: `frontend`

3. **Add Environment Variable**
   - Settings → Environment Variables
   - Add `REACT_APP_API_BASE_URL=https://fact-checker-e7el.onrender.com`
   - Select "Production" environment
   - Click "Save"

4. **Redeploy**
   - Go to Deployments tab
   - Click "Redeploy" on latest deployment
   - Wait for build to complete

### MongoDB Atlas

Your connection string is already configured:
```
MONGO_URI=<your-mongodb-uri>
```

**Security Checklist:**
1. Go to MongoDB Atlas → Network Access
2. Add Render IP addresses to whitelist (or use `0.0.0.0/0` for all IPs - less secure but easier)
3. Verify database user `fact_user` has read/write permissions
4. Check that database `factchecker_db` exists

---

## Connection Flow Verification

```
User Browser
    ↓
[React on Vercel]
    ↓ (HTTPS Request to https://fact-checker-e7el.onrender.com/api/claims/)
[FastAPI on Render]
    ↓ (MongoDB connection)
[MongoDB Atlas]
    ↓ (Return data)
[FastAPI on Render]
    ↓ (JSON Response)
[React on Vercel]
    ↓
User Browser (Display Result)
```

---

## Testing Instructions

### 1. Test Backend API Directly

Open your browser or use curl:

```bash
curl https://fact-checker-e7el.onrender.com/
```

Expected response:
```json
{"message": "Fact Checker API is running. Use /api/claims endpoint."}
```

Test the claims endpoint:
```bash
curl -X POST https://fact-checker-e7el.onrender.com/api/claims/ \
  -H "Content-Type: application/json" \
  -d '{"claim_text": "The Earth is round"}'
```

### 2. Test Frontend to Backend Connection

1. Open your Vercel app: `https://fact-checker-pi5i.vercel.app/`
2. Open browser DevTools (F12)
3. Go to **Network** tab
4. Enter a test claim: "The sky is blue"
5. Click "Check Fact"
6. In Network tab, look for a request to:
   - URL: `https://fact-checker-e7el.onrender.com/api/claims/`
   - Method: `POST`
   - Status: `200 OK` (or `201`)

**What to check:**
- ✅ Request URL should be `https://fact-checker-e7el.onrender.com/api/claims/`
- ✅ NOT `http://localhost:8000/api/claims/`
- ✅ Response should contain `claim_text`, `status`, `explanation`
- ❌ If you see CORS errors, check backend CORS configuration
- ❌ If request fails, check Render logs for errors

### 3. Verify MongoDB Connection

Check Render logs for successful MongoDB connection:
```
INFO: Connected to MongoDB at mongodb+srv://...
```

Or check MongoDB Atlas dashboard:
- Go to Clusters → Browse Collections
- Look for `factchecker_db` database
- Check `claims` collection for saved fact-check results

---

## Common Issues and Solutions

### Issue: CORS Error in Browser Console

**Error:** `Access to fetch at 'https://fact-checker-e7el.onrender.com/api/claims/' from origin 'https://fact-checker-pi5i.vercel.app' has been blocked by CORS policy`

**Solution:**
1. Verify `FRONTEND_URL` in Render environment variables matches your Vercel URL
2. Check backend logs to ensure CORS middleware is configured
3. Redeploy backend after changing environment variables

### Issue: Frontend Still Calling Localhost

**Error:** Network tab shows `http://localhost:8000/api/claims/`

**Solution:**
1. Verify `.env.production` exists in `frontend/` folder
2. Verify `REACT_APP_API_BASE_URL` is set in Vercel environment variables
3. Redeploy frontend in Vercel
4. Clear browser cache and hard refresh (Ctrl+Shift+R)

### Issue: 502 Bad Gateway on Render

**Solution:**
1. Check Render logs for Python errors
2. Verify `requirements.txt` includes all dependencies
3. Ensure `PORT` environment variable is used in uvicorn command
4. Check that Render service is using correct start command

### Issue: MongoDB Connection Timeout

**Solution:**
1. Go to MongoDB Atlas → Network Access
2. Add `0.0.0.0/0` to IP whitelist (allows all IPs)
3. Verify connection string has correct password (URL-encoded)
4. Check database user has proper permissions

---

## Quick Verification Commands

Run these to verify your setup:

```bash
# 1. Check backend health
curl https://fact-checker-e7el.onrender.com/

# 2. Check frontend loads
curl https://fact-checker-pi5i.vercel.app/

# 3. Check if frontend has correct API URL (view source)
curl https://fact-checker-pi5i.vercel.app/ | grep -i "fact-checker-e7el"

# 4. Test actual fact-check request
curl -X POST https://fact-checker-e7el.onrender.com/api/claims/ \
  -H "Content-Type: application/json" \
  -H "Origin: https://fact-checker-pi5i.vercel.app" \
  -d '{"claim_text": "Water boils at 100 degrees Celsius"}'
```

---

## Next Steps After Deployment

1. **Monitor Render Logs**
   - Check for any errors or warnings
   - Verify API requests are being processed

2. **Test All Features**
   - Text fact-checking
   - Image fact-checking
   - Video fact-checking
   - Voice fact-checking

3. **Performance Testing**
   - Test with multiple concurrent requests
   - Check response times
   - Monitor Render resource usage

4. **Security Hardening**
   - Remove `0.0.0.0/0` from MongoDB whitelist if possible
   - Add specific Render IP addresses instead
   - Enable rate limiting on API endpoints
   - Add API authentication if needed

5. **Setup Monitoring**
   - Configure Render alerts for downtime
   - Setup uptime monitoring (UptimeRobot, Pingdom)
   - Enable error tracking (Sentry, LogRocket)

---

## Support Resources

- **Render Docs**: https://render.com/docs
- **Vercel Docs**: https://vercel.com/docs
- **MongoDB Atlas Docs**: https://www.mongodb.com/docs/atlas/
- **FastAPI CORS**: https://fastapi.tiangolo.com/tutorial/cors/
- **React Environment Variables**: https://create-react-app.dev/docs/adding-custom-environment-variables/
