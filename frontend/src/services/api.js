// Use environment variable for API base URL, fallback to relative path for development
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || '';

// Helper function to get auth headers
function getAuthHeaders() {
  const token = localStorage.getItem('access_token');
  return {
    'Content-Type': 'application/json',
    ...(token && { 'Authorization': `Bearer ${token}` })
  };
}

export async function checkClaim(claimText) {
  const res = await fetch(`${API_BASE_URL}/api/claims/`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ claim_text: claimText }),
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json();
}

export async function checkMultimodalClaim(claimText, file) {
  const formData = new FormData();

  if (claimText) {
    formData.append('claim_text', claimText);
  }

  if (file) {
    formData.append('file', file);
  }

  const token = localStorage.getItem('access_token');
  const headers = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE_URL}/api/claims/multimodal`, {
    method: 'POST',
    headers: headers,
    body: formData,
    // Don't set Content-Type header - browser will set it with boundary for multipart/form-data
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}

export async function checkURLClaim(url) {
  const res = await fetch(`${API_BASE_URL}/api/claims/url`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ url: url }),
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json();
}
