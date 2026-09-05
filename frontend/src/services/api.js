const API_BASE = import.meta.env.VITE_API_URL || '/api';
const SESSION_STORAGE_KEY = 'youtube_rag_session_id';
const COLLECTION_STORAGE_KEY = 'youtube_rag_collection_id';

export function getStoredSessionId() {
  return localStorage.getItem(SESSION_STORAGE_KEY) || null;
}

export function setStoredSessionId(id) {
  if (id) {
    localStorage.setItem(SESSION_STORAGE_KEY, id);
  } else {
    localStorage.removeItem(SESSION_STORAGE_KEY);
  }
}

export function getStoredCollectionId() {
  return localStorage.getItem(COLLECTION_STORAGE_KEY) || null;
}

export function setStoredCollectionId(id) {
  if (id) {
    localStorage.setItem(COLLECTION_STORAGE_KEY, id);
  } else {
    localStorage.removeItem(COLLECTION_STORAGE_KEY);
  }
}

async function fetchWithSession(endpoint, options = {}) {
  const sessionId = getStoredSessionId();
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (sessionId) {
    headers['X-Session-Id'] = sessionId;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  // Capture session ID returned by middleware
  const newSessionId = response.headers.get('X-Session-Id');
  if (newSessionId) {
    setStoredSessionId(newSessionId);
  }

  if (!response.ok) {
    let errorDetail = 'Request failed';
    try {
      const errorJson = await response.json();
      errorDetail = errorJson.detail || errorJson.message || errorDetail;
    } catch {
      errorDetail = response.statusText || errorDetail;
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export async function getOrCreateCollection() {
  const data = await fetchWithSession('/collections', {
    method: 'POST',
  });
  setStoredCollectionId(data.collection_id);
  return data;
}

export async function submitVideos(collectionId, links) {
  return fetchWithSession(`/collections/${collectionId}/videos`, {
    method: 'POST',
    body: JSON.stringify({ links }),
  });
}

export async function getCollectionStatus(collectionId) {
  return fetchWithSession(`/collections/${collectionId}/status`, {
    method: 'GET',
  });
}

export async function askQuestion(collectionId, question) {
  return fetchWithSession(`/collections/${collectionId}/ask`, {
    method: 'POST',
    body: JSON.stringify({ question }),
  });
}

export async function deleteCollection(collectionId) {
  const data = await fetchWithSession(`/collections/${collectionId}`, {
    method: 'DELETE',
  });
  setStoredCollectionId(null);
  return data;
}

export function clearSession() {
  localStorage.removeItem(SESSION_STORAGE_KEY);
  localStorage.removeItem(COLLECTION_STORAGE_KEY);
}
