import { 
  LayoutDashboard, 
  FolderKanban, 
  FileSearch, 
  BookOpen, 
  ShieldCheck, 
  CheckCircle2, 
  Database,
  Inbox,
  Activity,
  FileText,
  Sparkles,
  Award,
  Zap
} from 'lucide-react';

interface SidebarProps {
  currentTab: string;
  setCurrentTab: (tab: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentTab, setCurrentTab }) => {
  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'pipeline', label: 'One-Click Review', icon: Sparkles },
    { id: 'engines', label: 'Motores IA', icon: Zap },
    { id: 'jobs', label: 'Jobs & Procesos', icon: Activity },
    { id: 'sources', label: 'Intake & Fuentes', icon: Inbox },
    { id: 'projects', label: 'Gestión de Proyectos', icon: FolderKanban },
    { id: 'viewer', label: 'Visor de Planos & Overlays', icon: FileSearch },
    { id: 'review', label: 'Triage & Revisión (HITL)', icon: CheckCircle2 },
    { id: 'rules', label: 'Motor de Reglas QA/QC', icon: ShieldCheck },
    { id: 'reports', label: 'Informes & Evidencias', icon: FileText },
    { id: 'evaluation', label: 'Golden Dataset & Scorecard', icon: Award },
    { id: 'knowledge', label: 'Base de Conocimiento', icon: BookOpen },
    { id: 'memories', label: 'Las 4 Memorias', icon: Database },
    // TODO: MLOps & Active Learning (feedback loop, fine-tuning y active learning) previsto para fase posterior como módulo dedicado
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo-icon">PR</div>
        <div>
          <div className="sidebar-logo-text">Plan Review AI</div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Arquitectura Híbrida v0.2</div>
        </div>
      </div>

      <nav className="sidebar-nav">
        {menuItems.map((item) => {
          const Icon = item.icon;
          return (
            <div
              key={item.id}
              className={`nav-item ${currentTab === item.id ? 'active' : ''}`}
              onClick={() => setCurrentTab(item.id)}
            >
              <Icon size={18} />
              <span>{item.label}</span>
            </div>
          );
        })}
      </nav>

      <div style={{ paddingTop: '16px', borderTop: '1px solid var(--border-subtle)', fontSize: '12px', color: 'var(--text-dim)' }}>
        <div>Estado del Motor: <span style={{ color: 'var(--success)', fontWeight: 600 }}>● Online</span></div>
        <div style={{ marginTop: '4px' }}>Modo: <strong>Percepción + Reglas + Jobs HITL</strong></div>
      </div>
    </aside>
  );
};
