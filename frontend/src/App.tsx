import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { Navbar } from './components/Navbar';
import { DashboardPage } from './pages/DashboardPage';
import { PipelinePage } from './pages/PipelinePage';
import { JobsPage } from './pages/JobsPage';
import { SourcesPage } from './pages/SourcesPage';
import { ProjectsPage } from './pages/ProjectsPage';
import { PlanViewerPage } from './pages/PlanViewerPage';
import { KnowledgePage } from './pages/KnowledgePage';
import { RulesPage } from './pages/RulesPage';
import { ReviewPage } from './pages/ReviewPage';
import { ReportsPage } from './pages/ReportsPage';
import { EvaluationPage } from './pages/EvaluationPage';
import { AiEnginesPage } from './pages/AiEnginesPage';
import { LoginPage } from './pages/LoginPage';
import { ResetPasswordPage } from './pages/ResetPasswordPage';
import { Shield, RefreshCw } from 'lucide-react';
import { ProjectProvider } from './context/ProjectContext';

export function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isAuthChecking, setIsAuthChecking] = useState<boolean>(true);
  const [currentTab, setCurrentTab] = useState<string>('dashboard');
  const [refreshKey, setRefreshKey] = useState(0);

  // Detección de ruta de restablecimiento de contraseña o verificación de correo
  const pathname = window.location.pathname;
  const searchParams = new URLSearchParams(window.location.search);
  const isResetFlow =
    pathname.includes('reset-password') ||
    pathname.includes('verify-email') ||
    (searchParams.has('token') && !localStorage.getItem('auth_token'));


  useEffect(() => {
    // 1. Verificar presencia de token en almacenamiento local
    const token = localStorage.getItem('auth_token');
    if (token) {
      setIsAuthenticated(true);
    } else {
      setIsAuthenticated(false);
    }
    setIsAuthChecking(false);

    // 2. Manejador de navegación entre pestañas
    const handleNavEvent = (e: any) => {
      if (e.detail?.tab) {
        setCurrentTab(e.detail.tab);
        if (e.detail.docId) {
          localStorage.setItem('viewer_target_doc_id', e.detail.docId);
        }
        if (e.detail.sheetId) {
          localStorage.setItem('viewer_target_sheet_id', e.detail.sheetId);
        }
        if (e.detail.projectId) {
          localStorage.setItem('active_project_id', e.detail.projectId);
        }
        setRefreshKey((prev) => prev + 1);
      }
    };

    // 3. Manejador de logout por expiración o 401
    const handleLogoutEvent = () => {
      setIsAuthenticated(false);
      setCurrentTab('dashboard');
    };

    // 4. Invalidador reactivo por cambio de proyecto activo
    const handleProjectChanged = () => {
      setRefreshKey((prev) => prev + 1);
    };

    window.addEventListener('navigate-tab', handleNavEvent);
    window.addEventListener('auth-logout', handleLogoutEvent);
    window.addEventListener('active-project-changed', handleProjectChanged);

    return () => {
      window.removeEventListener('navigate-tab', handleNavEvent);
      window.removeEventListener('auth-logout', handleLogoutEvent);
      window.removeEventListener('active-project-changed', handleProjectChanged);
    };
  }, []);

  const handleSync = () => {
    setRefreshKey((prev) => prev + 1);
  };

  const handleLoginSuccess = () => {
    setIsAuthenticated(true);
    setCurrentTab('dashboard');
    setRefreshKey((prev) => prev + 1);
  };

  // Fallback de carga inicial para evitar cualquier pantalla negra
  if (isAuthChecking) {
    return (
      <div className="min-h-screen bg-[#090d16] flex flex-col items-center justify-center text-slate-100 gap-4">
        <div className="p-3 bg-gradient-to-tr from-cyan-500 to-indigo-600 rounded-2xl shadow-xl shadow-cyan-500/20 border border-cyan-400/30 animate-pulse">
          <Shield className="w-10 h-10 text-white" />
        </div>
        <div className="flex items-center gap-2 text-sm text-slate-400 font-mono">
          <RefreshCw className="w-4 h-4 animate-spin text-cyan-400" />
          <span>Iniciando Plan Review AI Hybrid...</span>
        </div>
      </div>
    );
  }

  // Si es flujo de restablecimiento de contraseña o confirmación de correo
  if (isResetFlow) {
    return <ResetPasswordPage onSuccess={() => { window.location.href = '/login'; }} />;
  }

  // Si no hay sesión válida, renderizar login
  if (!isAuthenticated) {
    return <LoginPage onLoginSuccess={handleLoginSuccess} />;
  }


  // Si está autenticado, renderizar la aplicación envuelta en el contexto global de proyectos
  return (
    <ProjectProvider>
      <div className="app-container">
        <Sidebar currentTab={currentTab} setCurrentTab={setCurrentTab} />

        <div className="main-content">
          <Navbar onSync={handleSync} />

          {currentTab === 'dashboard' && <DashboardPage key={refreshKey} />}
          {currentTab === 'pipeline' && <PipelinePage key={refreshKey} />}
          {currentTab === 'engines' && <AiEnginesPage key={refreshKey} />}
          {currentTab === 'jobs' && <JobsPage key={refreshKey} />}
          {currentTab === 'sources' && <SourcesPage key={refreshKey} />}
          {currentTab === 'projects' && <ProjectsPage key={refreshKey} />}
          {currentTab === 'viewer' && <PlanViewerPage key={refreshKey} />}
          {currentTab === 'review' && <ReviewPage key={refreshKey} />}
          {currentTab === 'rules' && <RulesPage key={refreshKey} />}
          {currentTab === 'reports' && <ReportsPage key={refreshKey} />}
          {currentTab === 'evaluation' && <EvaluationPage key={refreshKey} />}
          {currentTab === 'knowledge' && <KnowledgePage key={refreshKey} />}
          {currentTab === 'memories' && <DashboardPage key={refreshKey} />}
          {currentTab === 'mlops' && <KnowledgePage key={refreshKey} />}
        </div>
      </div>
    </ProjectProvider>
  );
}

export default App;
