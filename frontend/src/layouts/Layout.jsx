import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { clearToken } from "../services/api";

const links = [
  ["/dashboard", "Dashboard"],
  ["/profile", "My Profile"],
  ["/cv", "My CV"],
  ["/jobs", "Find Jobs"],
  ["/documents", "AI Documents"],
  ["/applications", "Applications"],
  ["/interview", "Interview Prep"],
  ["/notifications", "Notifications"],
];

export default function Layout() {
  const nav = useNavigate();
  return (
    <div className="min-h-screen md:flex bg-gray-50">
      <aside className="md:w-56 bg-white border-r p-4">
        <NavLink to="/" className="text-xl font-bold text-brand block mb-4">
          JOBHUNT AI
        </NavLink>
        <nav className="flex md:flex-col gap-1 overflow-x-auto">
          {links.map(([to, label]) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `px-3 py-2 rounded whitespace-nowrap ${
                  isActive ? "bg-brand text-white" : "hover:bg-gray-100"
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
        <button className="mt-4 px-3 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded w-full text-left"
          onClick={() => { clearToken(); nav("/login"); }}>Log out</button>
      </aside>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  );
}
