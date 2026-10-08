import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import { Loading } from './components/ui';
import { useAuth } from './lib/auth';
import Login from './pages/Login';
import Review from './pages/Review';

// Other pages load on first visit — the review queue opens faster
const Brand = lazy(() => import('./pages/Brand'));
const CalendarPage = lazy(() => import('./pages/Calendar'));
const Campaigns = lazy(() => import('./pages/Campaigns'));
const DraftEditor = lazy(() => import('./pages/DraftEditor'));
const SettingsPage = lazy(() => import('./pages/Settings'));
const Sources = lazy(() => import('./pages/Sources'));
const Stats = lazy(() => import('./pages/Stats'));
const Library = lazy(() => import('./pages/Library'));
const Team = lazy(() => import('./pages/Team'));
const Admin = lazy(() => import('./pages/Admin'));
const Products = lazy(() => import('./pages/Products'));
const Newsletters = lazy(() => import('./pages/Newsletters'));

export default function App() {
  const { loading, session } = useAuth();
  if (loading) return <Loading />;
  if (!session) return <Login />;
  return (
    <Suspense fallback={<Loading />}>
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
        <Route path="library" element={<Library />} />
        <Route path="team" element={<Team />} />
        <Route path="admin" element={<Admin />} />
        <Route path="products" element={<Products />} />
        <Route path="newsletters/*" element={<Newsletters />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
    </Suspense>
  );
}
