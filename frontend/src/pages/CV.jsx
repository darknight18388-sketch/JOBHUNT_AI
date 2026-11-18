import { useEffect, useState } from "react";
import {
  listResumes, uploadResume, analyzeResume, getAnalysis, saveAnalysis, deleteResume,
} from "../services/api";

const LISTS = ["skills", "education", "experience", "certifications", "languages"];
const toLines = (arr) => (arr || []).join("\n");
const fromLines = (t) => t.split("\n").map((x) => x.trim()).filter(Boolean);

export default function CV() {
  const [resumes, setResumes] = useState([]);
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState(null);
  const [uncertain, setUncertain] = useState([]);
  const [confirmed, setConfirmed] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = () => listResumes().then(setResumes).catch((e) => setError(e.message));
  useEffect(() => { refresh(); }, []);

  function show(a) {
    setForm({
      full_name: a.full_name, email: a.email, phone: a.phone,
      ...Object.fromEntries(LISTS.map((k) => [k, toLines(a[k])])),
    });
    setUncertain(a.uncertain_fields || []);
    setConfirmed(a.confirmed);
  }

  async function wrap(fn) {
    setBusy(true); setError(""); setMsg("");
    try { await fn(); } catch (e) { setError(e.message); } finally { setBusy(false); }
  }

  const onUpload = (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    wrap(async () => {
      const r = await uploadResume(file);
      const a = await analyzeResume(r.id);
      await refresh();
      setSelected(r.id);
      show(a);
      setMsg("Uploaded and analysed. Please review the extracted details.");
    });
  };

  const open = (id) => wrap(async () => {
    setSelected(id);
    try { show(await getAnalysis(id)); } catch { show(await analyzeResume(id)); }
  });

  const reanalyze = () => wrap(async () => {
    show(await analyzeResume(selected));
    setMsg("Re-analysed. Your earlier edits were replaced.");
  });

  const save = () => wrap(async () => {
    const body = {
      full_name: form.full_name, email: form.email, phone: form.phone, confirmed: true,
      ...Object.fromEntries(LISTS.map((k) => [k, fromLines(form[k])])),
    };
    show(await saveAnalysis(selected, body));
    setMsg("Saved and confirmed.");
  });

  const remove = () => {
    if (!window.confirm("Delete this CV and its extracted data permanently?")) return;
    wrap(async () => {
      await deleteResume(selected);
      setSelected(null); setForm(null);
      await refresh();
      setMsg("CV deleted.");
    });
  };

  const input = "w-full border rounded px-3 py-2 bg-white";
  return (
    <div className="max-w-3xl">
      <h2 className="text-2xl font-semibold">My CV</h2>
      <p className="text-gray-600 mt-1 text-sm">
        PDF or DOCX, max 5 MB. Files are stored privately. Review everything extracted
        before it is used for matching or applications.
      </p>

      <label className="inline-block mt-4 px-4 py-2 bg-brand text-white rounded cursor-pointer">
        {busy ? "Working..." : "Upload CV"}
        <input type="file" accept=".pdf,.docx" className="hidden" onChange={onUpload} disabled={busy} />
      </label>
      {error && <p className="mt-3 text-red-600 text-sm">{error}</p>}
      {msg && <p className="mt-3 text-green-700 text-sm">{msg}</p>}

      {resumes.length > 0 && (
        <ul className="mt-4 space-y-1">
          {resumes.map((r) => (
            <li key={r.id}>
              <button onClick={() => open(r.id)}
                className={`w-full text-left px-3 py-2 rounded border ${selected === r.id ? "border-brand bg-green-50" : "bg-white hover:bg-gray-50"}`}>
                {r.original_filename}
                <span className="text-xs text-gray-500 ml-2">
                  {new Date(r.created_at).toLocaleString()}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {form && (
        <div className="mt-6 space-y-3">
          {uncertain.length > 0 && !confirmed && (
            <p className="text-amber-700 text-sm bg-amber-50 border border-amber-200 rounded p-2">
              Could not find: {uncertain.join(", ")}. Please fill these in if they apply.
            </p>
          )}
          {confirmed && <p className="text-green-700 text-sm">Confirmed by you.</p>}
          {["full_name", "email", "phone"].map((k) => (
            <div key={k}>
              <label className="text-sm font-medium capitalize">{k.replace("_", " ")}</label>
              <input className={input} value={form[k]}
                onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
            </div>
          ))}
          {LISTS.map((k) => (
            <div key={k}>
              <label className="text-sm font-medium capitalize">{k} (one per line)</label>
              <textarea className={input} rows={k === "languages" ? 2 : 4} value={form[k]}
                onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
            </div>
          ))}
          <div className="flex gap-2 pt-2">
            <button onClick={save} disabled={busy} className="px-4 py-2 bg-brand text-white rounded">
              Save and confirm
            </button>
            <button onClick={reanalyze} disabled={busy} className="px-4 py-2 border rounded">
              Re-analyse
            </button>
            <button onClick={remove} disabled={busy} className="px-4 py-2 border border-red-400 text-red-600 rounded">
              Delete CV
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
