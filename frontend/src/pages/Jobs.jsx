import { useEffect, useState } from "react";
import {
  listJobs, getJob, searchJobs, getCountries, addManualJob, importJobUrl, deleteJob,
} from "../services/api";

const EMPTY = { title: "", company: "", location: "", url: "", description: "", is_remote: false };

export default function Jobs() {
  const [countries, setCountries] = useState([{ code: "ALL", name: "All countries" }]);
  const [country, setCountry] = useState(localStorage.getItem("jh_country") || "ALL");
  const [query, setQuery] = useState("");
  const [includeRemote, setIncludeRemote] = useState(true);
  const [jobs, setJobs] = useState([]);
  const [total, setTotal] = useState(0);
  const [info, setInfo] = useState(null);
  const [open, setOpen] = useState({});
  const [panel, setPanel] = useState(""); // "", "manual" or "import"
  const [form, setForm] = useState(EMPTY);
  const [link, setLink] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { getCountries().then(setCountries).catch(() => {}); }, []);

  const reload = () =>
    listJobs({ country, include_remote: includeRemote ? "true" : "false", limit: 30 })
      .then((d) => { setJobs(d.items); setTotal(d.total); })
      .catch((e) => setError(e.message));
  useEffect(() => { localStorage.setItem("jh_country", country); setInfo(null); reload(); }, [country, includeRemote]);

  async function wrap(fn) {
    setBusy(true); setError(""); setMsg("");
    try { await fn(); } catch (e) { setError(e.message); } finally { setBusy(false); }
  }

  const find = (e) => {
    e?.preventDefault();
    wrap(async () => {
      const r = await searchJobs({ country, query, include_remote: includeRemote });
      setJobs(r.jobs); setTotal(r.total); setInfo(r);
    });
  };

  const toggle = (id) => wrap(async () => {
    if (open[id]) return setOpen({ ...open, [id]: null });
    setOpen({ ...open, [id]: await getJob(id) });
  });

  const submitManual = (e) => {
    e.preventDefault();
    wrap(async () => {
      await addManualJob({ ...form, country: country === "ALL" ? "" : country });
      setForm(EMPTY); setPanel("");
      setMsg("Job added to your private list.");
      await reload();
    });
  };

  const submitImport = (e) => {
    e.preventDefault();
    wrap(async () => {
      await importJobUrl(link, country === "ALL" ? "" : country);
      setLink(""); setPanel("");
      setMsg("Job imported to your private list. Check it against the official posting.");
      await reload();
    });
  };

  const remove = (id) => {
    if (!window.confirm("Remove this job you added?")) return;
    wrap(async () => { await deleteJob(id); await reload(); });
  };

  const input = "w-full border rounded px-3 py-2 bg-white";
  const countryName = (c) => (c === "ANY" ? "Remote (worldwide)" : (countries.find((x) => x.code === c) || {}).name || c);

  return (
    <div className="max-w-3xl">
      <h2 className="text-2xl font-semibold">Find Jobs</h2>
      <p className="text-gray-600 mt-1 text-sm">
        Pick a country. We check the sources that serve it and show each vacancy with its source and a
        link to the official posting.
      </p>

      <form onSubmit={find} className="mt-4 grid gap-3 bg-white border rounded p-4 sm:grid-cols-[200px_1fr_auto]">
        <label className="text-sm font-medium">Country
          <select className={`${input} mt-1`} value={country} onChange={(e) => setCountry(e.target.value)}>
            {countries.map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium">Job title or skill (optional)
          <input className={`${input} mt-1`} placeholder="Leave blank to search from your CV"
            value={query} onChange={(e) => setQuery(e.target.value)} />
        </label>
        <button disabled={busy} className="self-end px-5 py-2 bg-brand text-white rounded">
          {busy ? "Working..." : "Find jobs"}
        </button>
        <label className="text-sm flex items-center gap-2 sm:col-span-3">
          <input type="checkbox" checked={includeRemote} onChange={(e) => setIncludeRemote(e.target.checked)} />
          Include worldwide remote jobs
        </label>
      </form>

      <div className="mt-3 flex gap-2">
        <button onClick={() => setPanel(panel === "import" ? "" : "import")} className="px-4 py-2 border border-brand text-brand rounded">
          Import from link
        </button>
        <button onClick={() => setPanel(panel === "manual" ? "" : "manual")} className="px-4 py-2 border border-brand text-brand rounded">
          Add manually
        </button>
      </div>

      {error && <p role="alert" className="mt-3 text-red-600 text-sm">{error}</p>}
      {msg && <p className="mt-3 text-green-700 text-sm">{msg}</p>}

      {panel === "import" && (
        <form onSubmit={submitImport} className="mt-4 space-y-2 bg-white border rounded p-4">
          <input className={input} type="url" required placeholder="https://... (one vacancy page)"
            value={link} onChange={(e) => setLink(e.target.value)} />
          <p className="text-xs text-gray-500">
            Works only on pages that publish structured job data and allow automated reading. Otherwise use "Add manually".
          </p>
          <button disabled={busy} className="px-4 py-2 bg-brand text-white rounded">Import</button>
        </form>
      )}

      {panel === "manual" && (
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

      {info && (
        <div className="mt-4 text-sm text-gray-600">
          Searched for <b>{info.queries.join(", ")}</b> ·{" "}
          {info.sources.map((s) =>
            s.status === "ok" ? `${s.source}: ${s.created} new`
              : s.status === "skipped" ? `${s.source}: used saved results`
              : `${s.source}: unavailable`).join(" · ")}
          {info.note && <p className="mt-2 rounded bg-amber-50 border border-amber-200 p-2 text-amber-900">{info.note}</p>}
        </div>
      )}

      <p className="mt-5 text-sm text-gray-500">
        {total} job(s){total > jobs.length ? `, showing the latest ${jobs.length}` : ""}
      </p>
      {jobs.length === 0 && (
        <p className="mt-2 text-gray-600">No jobs here yet. Click "Find jobs", import a vacancy link, or add one manually.</p>
      )}
      <ul className="mt-2 space-y-3">
        {jobs.map((j) => {
          const d = open[j.id];
          return (
            <li key={j.id} className="bg-white border rounded p-4">
              <div className="flex justify-between gap-2">
                <div>
                  <h3 className="font-semibold">{j.title}</h3>
                  <p className="text-sm text-gray-600">
                    {[j.company, j.location, j.country ? countryName(j.country) : "", j.is_remote && j.country !== "ANY" ? "Remote" : "", j.salary_text]
                      .filter(Boolean).join(" · ")}
                  </p>
                </div>
                <div className="text-right text-xs space-y-1">
                  {j.is_stale && <span className="inline-block px-2 py-0.5 bg-amber-100 text-amber-800 rounded">Old listing</span>}
                  {j.is_manual && <span className="inline-block px-2 py-0.5 bg-blue-100 text-blue-800 rounded">Unverified</span>}
                </div>
              </div>
              <p className="mt-2 text-sm text-gray-700 whitespace-pre-line">{d ? d.description : j.description}</p>
              <div className="mt-3 flex flex-wrap gap-3 items-center text-sm">
                <button className="text-brand underline" onClick={() => toggle(j.id)}>
                  {d ? "Show less" : "Full description"}
                </button>
                {j.url && (
                  <a className="text-brand underline" href={j.url} target="_blank" rel="noopener noreferrer">
                    View official posting
                  </a>
                )}
                {j.is_manual && <button className="text-red-600 underline" onClick={() => remove(j.id)}>Remove</button>}
                <span className="text-gray-500 text-xs ml-auto">
                  {j.attribution}{j.posted_at ? ` · posted ${new Date(j.posted_at).toLocaleDateString()}` : ""}
                </span>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
