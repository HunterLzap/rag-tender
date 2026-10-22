import { Navigate, Route, Routes } from 'react-router-dom';
import Shell from './components/Shell';
import ProjectsPage from './pages/ProjectsPage';
import ProjectPage from './pages/ProjectPage';
import WorkbenchPage from './pages/WorkbenchPage';
import EvidencePage from './pages/EvidencePage';
import SettingsPage from './pages/SettingsPage';
import LibraryPage from './pages/LibraryPage';
import InterpretationPage from './pages/InterpretationPage';

export default function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route path="/" element={<ProjectsPage />} />
        <Route path="/projects/:projectId" element={<ProjectPage />} />
        <Route path="/runs/:runId" element={<WorkbenchPage />} />
        <Route path="/projects/:projectId/evidence" element={<EvidencePage />} />
        <Route path="/projects/:projectId/interpretation" element={<InterpretationPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
