import { useEffect, useState } from "react";
import { listJobs, getJob, refreshJobs, addManualJob, deleteJob } from "../services/api";

const EMPTY = { title: "", company: "", location: "", url: "", description: "", is_remote: false };

export default function Jobs() {
  const [data, setData] = useState({ items: [], total: 0, page: 1, limit: 20 });
  const [q, setQ] = useState("");
  const [remote, setRemote] = useState(false);
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState({});
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = (p = page) =>
    listJobs({ q, remote: remote ? "true" : "", page: p, limit: 20 })
      .then(setData)
      .catch((e) => setError(e.message));
  useEffect(() => { load(1); setPage(1); }, [remote]);

  async function wrap(fn) {
    setBusy(true); setError(""); setMsg("");
    try { await fn(); } catch (e) { setError(e.message); } finally { setBusy(false); }
  }

  const doRefresh = () => wrap(async () => {
    const res = await refreshJobs();
    setMsg(res.map((r) =>
      r.status === "ok" ? `${r.source}: ${r.created} new, ${r.duplicates} duplicates skipped`
        : `${r.source}: ${r.status}. ${r.message}`).join(" | "));
    await load(1); setPage(1);
  });

  const toggle = (id) => wrap(async () => {
    if (open[id]) return setOpen({ ...open, [id]: null });
    setOpen({ ...open, [id]: await getJob(id) });
  });

  const submitManual = (e) => {
    e.preventDefault();
    wrap(async () => {
      await addManualJob(form);
      setForm(EMPTY); setShowForm(false);
      setMsg("Job added to your private list.");
      await load(1); setPage(1);
    });
  };

  const remove = (id) => {
    if (!window.confirm("Remove this job you added?")) return;
    wrap(async () => { await deleteJob(id); await load(); });
  };

  const input = "w-full border rounded px-3 py-2 bg-white";
  const pages = Math.max(1, Math.ceil(data.total / data.limit));

  return (
    <div className="max-w-3xl">
      <h2 className="text-2xl font-semibold">Find Jobs</h2>
      <p className="text-gray-600 mt-1 text-sm">
        Vacancies from permitted sources, each with its source and a link to the official
        posting. For Sri Lankan vacancies, add them yourself with the link and description.
      </p>

      <div className="mt-4 flex flex-wrap gap-2 items-center">
        <input className="border rounded px-3 py-2 flex-1 min-w-[12rem]" placeholder="Search title, company, skills"
          value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && (setPage(1), load(1))} />
        <button className="px-4 py-2 border rounded" onClick={() => { setPage(1); load(1); }}>Search</button>
        <label className="text-sm flex items-center gap-1">
          <input type="checkbox" checked={remote} onChange={(e) => setRemote(e.target.checked)} /> Remote only
        </label>
      </div>
      <div className="mt-3 flex gap-2">
        <button disabled={busy} onClick={doRefresh} className="px-4 py-2 bg-brand text-white rounded">
          {busy ? "Working..." : "Refresh from sources"}
        </button>
        <button onClick={() => setShowForm(!showForm)} className="px-4 py-2 border border-brand text-brand rounded">
          {showForm ? "Cancel" : "Add a job manually"}
        </button>
      </div>
      {error && <p className="mt-3 text-red-600 text-sm">{error}</p>}
      {msg && <p className="mt-3 text-green-700 text-sm">{msg}</p>}

      {showForm && (
        <form onSubmit={submitManual} className="mt-4 space-y-2 bg-white border rounded p-4">
          <input className={input} placeholder="Job title *" required value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <input className={input} placeholder="Company *" required value={form.company}
            onChange={(e) => setForm({ ...form, company: e.target.value })} />
          <input className={input} placeholder="Location (e.g. Colombo)" value={form.location}
            onChange={(e) => setForm({ ...form, location: e.target.value })} />
          <input className={input} placeholder="Official posting URL (https://...)" value={form.url}
            onChange={(e) => setForm({ ...form, url: e.target.value })} />
          <textarea className={input} rows={6} required minLength={10}
            placeholder="Paste the job description and requirements *" value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <label className="text-sm flex items-center gap-1">
            <input type="checkbox" checked={form.is_remote}
              onChange={(e) => setForm({ ...form, is_remote: e.target.checked })} /> Remote
          </label>
          <button disabled={busy} className="px-4 py-2 bg-brand text-white rounded">Save job</button>
        </form>
      )}

      <p className="mt-5 text-sm text-gray-500">{data.total} job(s)</p>
      {data.items.length === 0 && (
        <p className="mt-2 text-gray-600">
          No jobs yet. Click "Refresh from sources", or add a vacancy manually.
        </p>
      )}
      <ul className="mt-2 space-y-3">
        {data.items.map((j) => {
          const d = open[j.id];
          return (
            <li key={j.id} className="bg-white border rounded p-4">
              <div className="flex justify-between gap-2">
                <div>
                  <h3 className="font-semibold">{j.title}</h3>
                  <p className="text-sm text-gray-600">
                    {j.company}{j.location ? ` · ${j.location}` : ""}{j.is_remote ? " · Remote" : ""}
                    {j.salary_text ? ` · ${j.salary_text}` : ""}
                  </p>
                </div>
                <div className="text-right text-xs space-y-1">
                  {j.is_stale && <span className="inline-block px-2 py-0.5 bg-amber-100 text-amber-800 rounded">Old listing</span>}
                  {j.is_manual && <span className="inline-block px-2 py-0.5 bg-blue-100 text-blue-800 rounded">Unverified</span>}
                </div>
              </div>
              <p className="mt-2 text-sm text-gray-700 whitespace-pre-line">
                {d ? d.description : j.description}
              </p>
              <div className="mt-3 flex flex-wrap gap-3 items-center text-sm">
                <button className="text-brand underline" onClick={() => toggle(j.id)}>
                  {d ? "Show less" : "Full description"}
                </button>
                {j.url && (
                  <a className="text-brand underline" href={j.url} target="_blank" rel="noopener noreferrer">
                    View official posting
                  </a>
                )}
                {j.is_manual && (
                  <button className="text-red-600 underline" onClick={() => remove(j.id)}>Remove</button>
                )}
                <span className="text-gray-500 text-xs ml-auto">
                  {j.attribution}{j.posted_at ? ` · posted ${new Date(j.posted_at).toLocaleDateString()}` : ""}
                </span>
              </div>
            </li>
          );
        })}
      </ul>

      {pages > 1 && (
        <div className="mt-4 flex gap-2 items-center text-sm">
          <button disabled={page <= 1} className="px-3 py-1 border rounded"
            onClick={() => { setPage(page - 1); load(page - 1); }}>Prev</button>
          <span>Page {page} / {pages}</span>
          <button disabled={page >= pages} className="px-3 py-1 border rounded"
            onClick={() => { setPage(page + 1); load(page + 1); }}>Next</button>
        </div>
      )}
    </div>
  );
}
