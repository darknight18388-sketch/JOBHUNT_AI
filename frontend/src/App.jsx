import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./layouts/Layout.jsx";
import Landing from "./pages/Landing.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Profile from "./pages/Profile.jsx";
import CV from "./pages/CV.jsx";
import Jobs from "./pages/Jobs.jsx";
import Documents from "./pages/Documents.jsx";
import Applications from "./pages/Applications.jsx";
import Interview from "./pages/Interview.jsx";
import Notifications from "./pages/Notifications.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route element={<Layout />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/cv" element={<CV />} />
        <Route path="/jobs" element={<Jobs />} />
        <Route path="/documents" element={<Documents />} />
        <Route path="/applications" element={<Applications />} />
        <Route path="/interview" element={<Interview />} />
        <Route path="/notifications" element={<Notifications />} />
      </Route>
      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  );
}
