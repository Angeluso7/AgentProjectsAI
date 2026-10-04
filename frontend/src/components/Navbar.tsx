import React, { useEffect, useState, useRef } from 'react';
import {
  RefreshCw, User, LogOut, Building2, ChevronDown, Shield,
  Activity, Mail, Key, Settings, FolderKanban, Check, Plus, Search, Layers, ExternalLink
} from 'lucide-react';
import { apiService } from '../services/api';
import { UserMembership } from '../types';
import { EngineHealthModal } from './EngineHealthModal';
import { UserProfileModal, ProfileModalTab } from './UserProfileModal';
import { useProject } from '../context/ProjectContext';
import { ProjectFormModal } from './ProjectFormModal';

interface NavbarProps {
  onSync: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onSync }) => {
  const { projects, activeProject, activeProjectId, setActiveProjectId, createProject } = useProject();
  const [syncing, setSyncing] = useState(false);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [showHealthModal, setShowHealthModal] = useState(false);
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [profileModalTab, setProfileModalTab] = useState<ProfileModalTab>('profile');
  const [showUserDropdown, setShowUserDropdown] = useState(false);
  const [showProjectDropdown, setShowProjectDropdown] = useState(false);
  const [projectSearch, setProjectSearch] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [userInfo, setUserInfo] = useState<any>(null);
  const [memberships, setMemberships] = useState<UserMembership[]>([]);
  const [activeOrgId, setActiveOrgId] = useState<string>('');
  const [activeRole, setActiveRole] = useState<string>('viewer');

  const dropdownRef = useRef<HTMLDivElement>(null);
  const projectDropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    checkStatus();
    loadAuthContext();
    const interval = setInterval(checkStatus, 15000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowUserDropdown(false);
      }
      if (projectDropdownRef.current && !projectDropdownRef.current.contains(event.target as Node)) {
        setShowProjectDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const loadAuthContext = async () => {
    try {
      const storedUser = localStorage.getItem('user_info');
      if (storedUser) setUserInfo(JSON.parse(storedUser));
      setActiveOrgId(localStorage.getItem('active_org_id') || '');
      setActiveRole(localStorage.getItem('active_role') || 'viewer');

      const me = await apiService.getCurrentUser();
      if (me.user) {
        setUserInfo(me.user);
        setMemberships(me.memberships || []);
      }
    } catch {
      // Ignorar si aún no ha iniciado sesión
    }
  };

  const checkStatus = async () => {
    try {
      await apiService.checkHealth();
      setBackendOnline(true);
    } catch {
      setBackendOnline(false);
    }
  };

  const handleSyncKnowledge = async () => {
    try {
      setSyncing(true);
      await apiService.seedConfidencePolicies();
      alert('Conocimiento y políticas sincronizadas exitosamente con la Base de Datos.');
      onSync();
    } catch (e) {
      console.error(e);
      alert('Error sincronizando conocimiento.');
    } finally {
      setSyncing(false);
    }
  };

  const handleOrgChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newOrgId = e.target.value;
    localStorage.setItem('active_org_id', newOrgId);
    setActiveOrgId(newOrgId);
    const mem = memberships.find((m) => m.organization_id === newOrgId);
    if (mem) {
      localStorage.setItem('active_role', mem.role);
      setActiveRole(mem.role);
    }
    window.location.reload();
  };

  const handleOpenTab = (tab: ProfileModalTab) => {
    setProfileModalTab(tab);
    setShowProfileModal(true);
    setShowUserDropdown(false);
  };

  const roleColors: Record<string, string> = {
    admin: '#ef4444',
    audit_lead: '#f59e0b',
    reviewer: '#06b6d4',
    contributor: '#3b82f6',
    viewer: '#64748b'
  };

  return (
    <header className="top-navbar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 20px', height: '56px', background: 'var(--bg-card)', borderBottom: '1px solid var(--border-subtle)', position: 'relative', zIndex: 40 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        {/* Selector de Organización / Tenant */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'var(--bg-main)', padding: '4px 10px', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
          <Building2 size={15} style={{ color: 'var(--accent-primary)' }} />
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Org:</span>
          {memberships.length > 1 ? (
            <select
              value={activeOrgId}
              onChange={handleOrgChange}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-main)',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
                outline: 'none'
              }}
            >
              {memberships.map((m) => (
                <option key={m.organization_id} value={m.organization_id} style={{ background: '#0f172a', color: '#f8fafc' }}>
                  {m.organization_name}
                </option>
              ))}
            </select>
          ) : (
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-main)' }}>
              {memberships[0]?.organization_name || 'Organización Principal'}
            </span>
          )}
        </div>
        <div style={{ width: '1px', height: '18px', background: 'var(--border-subtle)' }} />

        {/* Selector Global Interactivo de Proyecto Activo */}
        <div className="relative" ref={projectDropdownRef}>
          <button
            type="button"
            onClick={() => setShowProjectDropdown(!showProjectDropdown)}
            className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg border transition-all hover:border-blue-500/50 bg-slate-950/80 border-slate-800 cursor-pointer"
            title="Haz clic para alternar de proyecto activo"
          >
            <FolderKanban className="w-3.5 h-3.5 text-blue-400 shrink-0" />
            <span className="text-[11px] text-slate-400 font-medium">Proyecto:</span>
            {activeProject ? (
              <div className="flex items-center gap-1.5 max-w-[280px]">
                <span className="text-xs font-mono font-bold text-blue-300">
                  {activeProject.code}
                </span>
                <span className="text-xs font-semibold text-slate-200 truncate">
                  {activeProject.name}
                </span>
                <span className="px-1.5 py-0.2 text-[9px] font-bold rounded bg-amber-950/80 text-amber-300 border border-amber-800/60 shrink-0">
                  {activeProject.stage || 'Ing. Detalle'}
                </span>
              </div>
            ) : (
              <span className="text-xs text-slate-400 italic">Ningún proyecto activo</span>
            )}
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 ml-1" />
          </button>

          {/* Menú Flotante de Conmutación de Proyectos */}
          {showProjectDropdown && (
            <div
              style={{
                position: 'absolute',
                top: 'calc(100% + 6px)',
                left: 0,
                width: '360px',
                backgroundColor: '#020617',
                border: '1px solid #334155',
                borderRadius: '12px',
                boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.8), 0 8px 10px -6px rgba(0, 0, 0, 0.8)',
                zIndex: 100,
                overflow: 'hidden',
                animation: 'fade-in 0.15s ease-out',
              }}
              onClick={(e) => e.stopPropagation()}
            >
              {/* Buscador Rápido */}
              <div className="p-2.5 border-b border-slate-800 bg-slate-900/60 flex items-center gap-2">
                <Search className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                <input
                  type="text"
                  autoFocus
                  value={projectSearch}
                  onChange={(e) => setProjectSearch(e.target.value)}
                  placeholder="Buscar por código o nombre..."
                  className="w-full bg-transparent text-xs text-slate-100 placeholder-slate-500 focus:outline-none"
                />
                {projectSearch && (
                  <button onClick={() => setProjectSearch('')} className="text-slate-400 hover:text-slate-200 text-xs">
                    ✕
                  </button>
                )}
              </div>

              {/* Lista de Proyectos */}
              <div className="max-h-[260px] overflow-y-auto p-1.5 space-y-1">
                {projects
                  .filter((p) => p.status !== 'deleted')
                  .filter((p) =>
                    !projectSearch ||
                    p.name.toLowerCase().includes(projectSearch.toLowerCase()) ||
                    p.code.toLowerCase().includes(projectSearch.toLowerCase())
                  )
                  .map((p) => {
                    const isActive = p.id === activeProjectId;
                    const isArchived = p.status === 'archived';

                    return (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => {
                          setActiveProjectId(p.id);
                          setShowProjectDropdown(false);
                        }}
                        className={`w-full p-2 rounded-lg text-left flex items-start justify-between gap-2 transition-all cursor-pointer ${
                          isActive
                            ? 'bg-blue-950/70 border border-blue-600/50 text-blue-200'
                            : 'hover:bg-slate-800/70 text-slate-300 border border-transparent'
                        }`}
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5 mb-0.5">
                            <span className="text-[11px] font-mono font-bold text-blue-400">
                              {p.code}
                            </span>
                            {isArchived && (
                              <span className="px-1 py-0.2 text-[8px] uppercase font-bold rounded bg-amber-950 text-amber-400 border border-amber-800">
                                Archivado
                              </span>
                            )}
                            <span className="px-1.5 py-0.2 text-[9px] font-medium rounded bg-slate-800 text-slate-300 border border-slate-700">
                              {p.stage || 'Ingeniería'}
                            </span>
                          </div>
                          <p className="text-xs font-semibold text-slate-100 truncate">
                            {p.name}
                          </p>
                          {p.client_name && (
                            <p className="text-[10px] text-slate-400 truncate">
                              {p.client_name}
                            </p>
                          )}
                        </div>
                        {isActive && (
                          <div className="p-1 rounded-md bg-blue-500/20 text-blue-400 shrink-0">
                            <Check className="w-3.5 h-3.5" />
                          </div>
                        )}
                      </button>
                    );
                  })}
              </div>

              {/* Acciones del Footer del Dropdown */}
              <div className="p-2 border-t border-slate-800 bg-slate-950 flex items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowProjectDropdown(false);
                    setShowCreateModal(true);
                  }}
                  className="px-2.5 py-1 text-[11px] font-bold text-blue-400 hover:text-blue-300 hover:bg-blue-950/50 rounded-lg border border-blue-800/40 flex items-center gap-1 transition-colors cursor-pointer"
                >
                  <Plus className="w-3 h-3" />
                  <span>Nuevo Proyecto</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowProjectDropdown(false);
                    window.dispatchEvent(new CustomEvent('navigate-tab', { detail: { tab: 'projects' } }));
                  }}
                  className="px-2.5 py-1 text-[11px] font-medium text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg flex items-center gap-1 transition-colors cursor-pointer"
                >
                  <span>Administrar</span>
                  <ExternalLink className="w-3 h-3" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        {/* Indicador de estado y Motores IA */}
        <button
          onClick={() => setShowHealthModal(true)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '12px',
            background: 'var(--bg-main)',
            border: '1px solid var(--border-subtle)',
            padding: '4px 10px',
            borderRadius: '6px',
            cursor: 'pointer',
            color: 'var(--text-main)'
          }}
          title="Ver estado operativo y latencia de los motores IA"
        >
          <Activity size={14} style={{ color: backendOnline ? '#10b981' : '#ef4444' }} />
          <span style={{ fontWeight: 600 }}>Salud Motores IA</span>
          <span
            style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              backgroundColor: backendOnline === true ? 'var(--success)' : backendOnline === false ? 'var(--danger)' : 'var(--warning)',
              display: 'inline-block',
            }}
          />
        </button>

        <EngineHealthModal
          isOpen={showHealthModal}
          onClose={() => setShowHealthModal(false)}
        />

        <button
          className="btn btn-secondary"
          onClick={handleSyncKnowledge}
          disabled={syncing}
          title="Sincroniza políticas de confianza"
          style={{ fontSize: '12px', padding: '4px 10px', display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <RefreshCw size={13} className={syncing ? 'animate-spin' : ''} />
          <span>{syncing ? 'Sincronizando...' : 'Sync Políticas'}</span>
        </button>

        <div style={{ width: '1px', height: '24px', background: 'var(--border-subtle)' }} />

        {/* Perfil de Usuario con Menú Desplegable Accesible */}
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setShowUserDropdown(!showUserDropdown)}
            className="flex items-center space-x-2.5 p-1.5 rounded-xl hover:bg-slate-800/80 transition-colors focus:outline-none focus:ring-1 focus:ring-blue-500"
            aria-expanded={showUserDropdown}
            aria-haspopup="true"
            title="Menú de usuario y seguridad"
          >
            <div className="flex flex-col items-end leading-tight">
              <span className="text-xs font-semibold text-slate-200">
                {userInfo?.display_name || userInfo?.email?.split('@')[0] || 'Auditor QA'}
              </span>
              <span
                className="text-[10px] font-bold uppercase tracking-wider"
                style={{ color: roleColors[activeRole] || '#94a3b8' }}
              >
                {activeRole}
              </span>
            </div>
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-md shadow-blue-500/20">
              <User className="w-4 h-4" />
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
          </button>

          {/* Menú Desplegable de Usuario */}
          {showUserDropdown && (
            <div
              style={{
                position: 'absolute',
                top: 'calc(100% + 8px)',
                right: 0,
                width: '240px',
                backgroundColor: '#020617',
                border: '1px solid #334155',
                borderRadius: '12px',
                boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.8), 0 8px 10px -6px rgba(0, 0, 0, 0.8)',
                zIndex: 50,
                padding: '6px',
                animation: 'fade-in 0.15s ease-out',
              }}
            >
              {/* Información de Identidad */}
              <div className="px-4 py-3 border-b border-slate-800">
                <p className="text-xs font-bold text-slate-100 truncate">
                  {userInfo?.display_name || 'Auditor QA'}
                </p>
                <p className="text-[11px] text-slate-400 truncate">
                  {userInfo?.email || 'admin@hybridplan.com'}
                </p>
              </div>

              {/* Acciones de Cuenta */}
              <div className="py-1">
                <button
                  type="button"
                  onClick={() => handleOpenTab('profile')}
                  className="w-full px-4 py-2 text-xs text-slate-300 hover:text-white hover:bg-slate-800 flex items-center space-x-2.5 transition-colors text-left"
                >
                  <User className="w-4 h-4 text-blue-400" />
                  <span>Mi perfil</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleOpenTab('email')}
                  className="w-full px-4 py-2 text-xs text-slate-300 hover:text-white hover:bg-slate-800 flex items-center space-x-2.5 transition-colors text-left"
                >
                  <Mail className="w-4 h-4 text-emerald-400" />
                  <span>Cambiar correo electrónico</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleOpenTab('password')}
                  className="w-full px-4 py-2 text-xs text-slate-300 hover:text-white hover:bg-slate-800 flex items-center space-x-2.5 transition-colors text-left"
                >
                  <Key className="w-4 h-4 text-amber-400" />
                  <span>Cambiar contraseña</span>
                </button>
              </div>

              {/* Cerrar Sesión */}
              <div className="border-t border-slate-800 pt-1 mt-1">
                <button
                  type="button"
                  onClick={() => apiService.logout()}
                  className="w-full px-4 py-2 text-xs text-red-400 hover:text-red-300 hover:bg-red-950/30 flex items-center space-x-2.5 transition-colors text-left"
                >
                  <LogOut className="w-4 h-4" />
                  <span>Cerrar sesión</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Modal de Perfil y Credenciales */}
      <UserProfileModal
        isOpen={showProfileModal}
        initialTab={profileModalTab}
        onClose={() => setShowProfileModal(false)}
      />

      {/* Modal de Creación Rápida de Proyecto */}
      <ProjectFormModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onSubmit={async (data, setAsActive) => {
          await createProject(data, setAsActive);
        }}
        existingProjects={projects}
      />
    </header>
  );
};
