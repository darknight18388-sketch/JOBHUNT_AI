import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { getHealth } from "../services/api";

export default function Landing() {
  const [api, setApi] = useState("checking...");
  useEffect(() => {
    getHealth().then(() => setApi("online")).catch(() => setApi("offline"));
  }, []);
  return (
    <div className="max-w-2xl mx-auto py-16 px-4 text-center">
      <h1 className="text-4xl font-bold text-brand">JOBHUNT AI</h1>
      <p className="mt-3 text-gray-600">
        Upload your CV, find suitable jobs, prepare truthful applications, and
        track everything. You approve every submission.
      </p>
      <Link to="/dashboard" className="inline-block mt-6 px-5 py-2 bg-brand text-white rounded">
        Get started
      </Link>
      <p className="mt-6 text-sm text-gray-500">Backend API: {api}</p>
    </div>
  );
}
