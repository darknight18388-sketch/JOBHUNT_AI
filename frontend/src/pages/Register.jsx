import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { register, login } from "../services/api";

export default function Register() {
  const nav = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      await register(email, password, fullName);
      await login(email, password);
      nav("/dashboard");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="max-w-sm mx-auto py-16 px-4">
      <h1 className="text-2xl font-bold text-brand mb-4">Create account</h1>
      <form onSubmit={submit} className="space-y-3">
        <input className="w-full border rounded px-3 py-2" placeholder="Full name"
          value={fullName} onChange={(e) => setFullName(e.target.value)} />
        <input className="w-full border rounded px-3 py-2" type="email" placeholder="Email"
          value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input className="w-full border rounded px-3 py-2" type="password" placeholder="Password (min 8 chars)"
          minLength={8} maxLength={72} value={password} onChange={(e) => setPassword(e.target.value)} required />
        {error && <p className="text-red-600 text-sm">{error}</p>}
        <button className="w-full bg-brand text-white rounded py-2">Register</button>
      </form>
      <p className="mt-4 text-sm">Have an account? <Link className="text-brand underline" to="/login">Log in</Link></p>
    </div>
  );
}
