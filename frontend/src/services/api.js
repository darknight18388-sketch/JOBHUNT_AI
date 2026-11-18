const TOKEN_KEY = "jobhunt_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const r = await fetch(path, { ...options, headers });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = data.detail;
    throw new Error(typeof d === "string" ? d : "Request failed");
  }
  return data;
}

export const getHealth = () => request("/api/health");
export const register = (email, password, full_name) =>
  request("/api/auth/register", { method: "POST", body: JSON.stringify({ email, password, full_name }) });
export const login = async (email, password) => {
  const d = await request("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
  setToken(d.access_token);
};
export const me = () => request("/api/auth/me");

export const listResumes = () => request("/api/resumes");
export const uploadResume = (file) => {
  const fd = new FormData();
  fd.append("file", file);
  return request("/api/resumes/upload", { method: "POST", body: fd });
};
export const analyzeResume = (id) => request(`/api/resumes/${id}/analyze`, { method: "POST" });
export const getAnalysis = (id) => request(`/api/resumes/${id}/analysis`);
export const saveAnalysis = (id, body) =>
  request(`/api/resumes/${id}/analysis`, { method: "PUT", body: JSON.stringify(body) });
export const deleteResume = (id) => request(`/api/resumes/${id}`, { method: "DELETE" });
