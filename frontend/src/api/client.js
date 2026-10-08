const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");

const TOKEN_STORAGE_KEY = "atlas_auth_token";
let authToken = null;

export function getAuthToken() {
  if (authToken === null) {
    authToken = localStorage.getItem(TOKEN_STORAGE_KEY);
  }
  return authToken;
}

export function setAuthToken(token) {
  authToken = token || null;
  if (token) {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

export function clearAuth() {
  setAuthToken(null);
}

async function request(path, { method = "GET", body, headers = {}, isFormData = false } = {}) {
  const requestHeaders = { ...headers };
  const token = getAuthToken();
  if (token) {
    requestHeaders.Authorization = `Bearer ${token}`;
  }
  if (body !== undefined && !isFormData) {
    requestHeaders["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: requestHeaders,
    body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body),
  });

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const errorBody = await response.json();
      if (errorBody?.detail) {
        detail = typeof errorBody.detail === "string" ? errorBody.detail : JSON.stringify(errorBody.detail);
      }
    } catch {
      // Keep the status-based message when the body is not JSON.
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return null;
  }
  return response.json();
}

// --- Authentication ---

export async function loginUser(email, password) {
  return request("/auth/login", { method: "POST", body: { email, password } });
}

export async function registerUser(email, fullName, password, passwordConfirm) {
  return request("/auth/register", {
    method: "POST",
    body: { email, full_name: fullName, password, password_confirm: passwordConfirm },
  });
}

export async function getMe() {
  return request("/auth/me");
}

export async function logoutUser() {
  return request("/auth/logout", { method: "POST" });
}

// --- Documents ---

export async function getDocuments() {
  return request("/documents");
}

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file, file.name);
  return request("/documents/upload", { method: "POST", body: formData, isFormData: true });
}

export async function getDocument(documentId) {
  return request(`/documents/${encodeURIComponent(documentId)}`);
}

export async function getDocumentEntities(documentId) {
  return request(`/documents/${encodeURIComponent(documentId)}/entities`);
}

export async function getDocumentRelationships(documentId) {
  return request(`/documents/${encodeURIComponent(documentId)}/relationships`);
}

export async function getDocumentEvidence(documentId) {
  return request(`/documents/${encodeURIComponent(documentId)}/evidence`);
}

// --- Knowledge graph, analytics, Q&A ---

export async function getGraphOverview(documentId = null) {
  const query = documentId ? `?document_id=${encodeURIComponent(documentId)}` : "";
  return request(`/graph${query}`);
}

export async function getAnalytics() {
  return request("/analytics");
}

export async function askQuestion(question, documentId = null) {
  return request("/query", { method: "POST", body: { question, document_id: documentId || null } });
}

export async function getDashboardSummary() {
  const [documents, analytics] = await Promise.all([getDocuments(), getAnalytics()]);
  return {
    documentCount: analytics?.document_count ?? documents?.length ?? 0,
    entityCount: analytics?.entity_count ?? null,
    evidenceCount: analytics?.evidence_count ?? null,
    relationshipCount: analytics?.relationship_count ?? null,
    documents: documents || [],
  };
}

export async function getHealth() {
  return request("/health");
}

