import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import { Loading } from './components/ui';
import { useAuth } from './lib/auth';
import Brand from './pages/Brand';
import CalendarPage from './pages/Calendar';
import Campaigns from './pages/Campaigns';
import DraftEditor from './pages/DraftEditor';
import Login from './pages/Login';
import Review from './pages/Review';
import SettingsPage from './pages/Settings';
import Sources from './pages/Sources';
import Stats from './pages/Stats';

export default function App() {
  const { loading, session } = useAuth();
  if (loading) return <Loading />;
  if (!session) return <Login />;
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Review />} />
        <Route path="drafts/:id" element={<DraftEditor />} />
        <Route path="sources" element={<Sources />} />
        <Route path="calendar" element={<CalendarPage />} />
        <Route path="campaigns" element={<Campaigns />} />
        <Route path="brand" element={<Brand />} />
        <Route path="stats" element={<Stats />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
