import { Navigate, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import TenderPage from './pages/TenderPage';
import KnowledgePage from './pages/KnowledgePage';
import MatchPage from './pages/MatchPage';
import SettingsPage from './pages/SettingsPage';
import TenderReviewPage from './pages/TenderReviewPage';
import CorrectionsPage from './pages/CorrectionsPage';
import RuleLibraryPage from './pages/RuleLibraryPage';

/**
 * Root application component.
 * Configures routing with a shared Layout wrapper.
 */
function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/index.html" element={<Dashboard />} />
        <Route path="/tenders" element={<TenderPage />} />
        <Route path="/tenders/:id/review" element={<TenderReviewPage />} />
        <Route path="/knowledge" element={<KnowledgePage />} />
        <Route path="/match" element={<MatchPage />} />
        <Route path="/match/:id" element={<MatchPage />} />
        <Route path="/corrections" element={<CorrectionsPage />} />
        <Route path="/rules" element={<RuleLibraryPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
