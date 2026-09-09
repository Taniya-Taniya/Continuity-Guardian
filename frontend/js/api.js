/**
 * Thin fetch wrapper around the real Continuity Guardian API
 * (api/main.py). Change API_BASE if your backend runs somewhere
 * other than localhost:8000.
 */

const API_BASE = "http://localhost:8000/api";
const API_ORIGIN = "http://localhost:8000"; // for /generated/* asset URLs, which aren't under /api

async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json();
}

async function apiPostForm(path, formData) {
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", body: formData });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `POST ${path} failed: ${res.status}`);
  }
  return res.json();
}

async function apiPost(path) {
  const res = await fetch(`${API_BASE}${path}`, { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `POST ${path} failed: ${res.status}`);
  }
  return res.json();
}

const Api = {
  listScenes: () => apiGet("/scenes"),
  getScene: (sceneId) => apiGet(`/scenes/${sceneId}`),
  dashboardSummary: () => apiGet("/dashboard/summary"),
  uploadScript: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return apiPostForm("/scripts/upload", fd);
  },
  uploadTake: (sceneId, file) => {
    const fd = new FormData();
    fd.append("file", file);
    return apiPostForm(`/scenes/${sceneId}/takes`, fd);
  },
  lockScene: (sceneId) => apiPost(`/scenes/${sceneId}/lock`),
  runBudget: (sceneId) => apiPost(`/scenes/${sceneId}/budget`),
  runPerformance: (sceneId) => apiPost(`/scenes/${sceneId}/performance`),
  runPreviz: (sceneId) => apiPost(`/scenes/${sceneId}/previz`),
  runScore: (sceneId) => apiPost(`/scenes/${sceneId}/score`),
  runLocalization: (sceneId, lang) => apiPost(`/scenes/${sceneId}/localize?lang=${lang}`),
  runAccessibility: (sceneId) => apiPost(`/scenes/${sceneId}/accessibility`),
};
