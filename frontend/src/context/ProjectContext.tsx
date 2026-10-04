import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { Project, ProjectLifecycleResult } from '../types';
import { apiService } from '../services/api';

interface ProjectContextType {
  projects: Project[];
  activeProject: Project | null;
  activeProjectId: string;
  isLoading: boolean;
  error: string | null;
  setActiveProjectId: (id: string) => void;
  reloadProjects: () => Promise<void>;
  createProject: (data: Partial<Project>, setAsActive?: boolean) => Promise<Project>;
  updateProject: (id: string, data: Partial<Project>) => Promise<Project>;
  archiveProject: (id: string) => Promise<void>;
  restoreProject: (id: string) => Promise<void>;
  unarchiveProject: (id: string) => Promise<void>;
  clearProjectContent: (id: string, confirmationCode: string, reason?: string) => Promise<ProjectLifecycleResult>;
  deleteProjectConfirmed: (id: string, confirmationCode: string, mode?: 'hard_delete' | 'anonymize', reason?: string) => Promise<ProjectLifecycleResult>;
  deleteProject: (id: string, hardDelete?: boolean, confirmationCode?: string) => Promise<void>;
  exportProject: (id: string) => Promise<void>;
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

const STORAGE_KEY_ACTIVE_PROJECT = 'active_project_id';

export const ProjectProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProjectId, setActiveProjectIdState] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const activeProject = projects.find((p) => p.id === activeProjectId) || null;

  const reloadProjects = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await apiService.getProjects(true);
      setProjects(data);

      const activeList = data.filter((p) => p.status !== 'archived' && p.status !== 'deleted');
      const storedId = localStorage.getItem(STORAGE_KEY_ACTIVE_PROJECT);

      if (storedId && activeList.some((p) => p.id === storedId)) {
        setActiveProjectIdState(storedId);
      } else if (activeList.length > 0) {
        const fallbackId = activeList[0].id;
        setActiveProjectIdState(fallbackId);
        localStorage.setItem(STORAGE_KEY_ACTIVE_PROJECT, fallbackId);
      } else if (data.length > 0) {
        // Si solo hay proyectos archivados
        setActiveProjectIdState(data[0].id);
        localStorage.setItem(STORAGE_KEY_ACTIVE_PROJECT, data[0].id);
      } else {
        setActiveProjectIdState('');
        localStorage.removeItem(STORAGE_KEY_ACTIVE_PROJECT);
      }
    } catch (err: any) {
      console.error('Error al cargar proyectos en ProjectContext:', err);
      setError(err.response?.data?.detail || 'Error al conectar con el servidor de proyectos.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    reloadProjects();
  }, [reloadProjects]);

  const setActiveProjectId = useCallback((id: string) => {
    setActiveProjectIdState(id);
    localStorage.setItem(STORAGE_KEY_ACTIVE_PROJECT, id);
    
    // Limpieza de referencias subordinadas al cambiar de proyecto
    localStorage.removeItem('viewer_target_doc_id');
    localStorage.removeItem('viewer_target_sheet_id');

    // Notificar a toda la aplicación
    const target = projects.find((p) => p.id === id) || null;
    window.dispatchEvent(new CustomEvent('active-project-changed', {
      detail: { projectId: id, project: target }
    }));
  }, [projects]);

  const createProject = async (data: Partial<Project>, setAsActive = true): Promise<Project> => {
    const created = await apiService.createProject(data);
    await reloadProjects();
    if (setAsActive && created.id) {
      setActiveProjectId(created.id);
    }
    return created;
  };

  const updateProject = async (id: string, data: Partial<Project>): Promise<Project> => {
    const updated = await apiService.updateProject(id, data);
    await reloadProjects();
    return updated;
  };

  const archiveProject = async (id: string) => {
    await apiService.archiveProject(id);
    if (activeProjectId === id) {
      const remainingActive = projects.filter((p) => p.id !== id && p.status !== 'archived' && p.status !== 'deleted');
      if (remainingActive.length > 0) {
        setActiveProjectId(remainingActive[0].id);
      } else {
        setActiveProjectIdState('');
        localStorage.removeItem(STORAGE_KEY_ACTIVE_PROJECT);
        window.dispatchEvent(new CustomEvent('active-project-changed', {
          detail: { projectId: '', project: null }
        }));
      }
    }
    await reloadProjects();
  };

  const restoreProject = async (id: string) => {
    await apiService.restoreProject(id);
    await reloadProjects();
  };

  const unarchiveProject = async (id: string) => {
    await apiService.unarchiveProject(id);
    await reloadProjects();
  };

  const clearProjectContent = async (id: string, confirmationCode: string, reason?: string): Promise<ProjectLifecycleResult> => {
    const result = await apiService.clearProjectContent(id, {
      confirmation_code: confirmationCode,
      reason: reason || 'Vaciado de contenido solicitado desde UI',
      acknowledge_data_loss: true,
    });
    await reloadProjects();
    return result;
  };

  const deleteProjectConfirmed = async (
    id: string,
    confirmationCode: string,
    mode: 'hard_delete' | 'anonymize' = 'hard_delete',
    reason?: string
  ): Promise<ProjectLifecycleResult> => {
    const result = await apiService.deleteProjectConfirmed(id, {
      confirmation_code: confirmationCode,
      mode,
      reason: reason || 'Eliminación confirmada desde UI',
      acknowledge_data_loss: true,
    });

    if (activeProjectId === id) {
      setActiveProjectIdState('');
      localStorage.removeItem(STORAGE_KEY_ACTIVE_PROJECT);
      localStorage.removeItem('viewer_target_doc_id');
      localStorage.removeItem('viewer_target_sheet_id');
      window.dispatchEvent(new CustomEvent('active-project-changed', {
        detail: { projectId: '', project: null }
      }));
    }

    await reloadProjects();
    return result;
  };

  const deleteProject = async (id: string, hardDelete = false, confirmationCode?: string) => {
    await apiService.deleteProject(id, hardDelete, confirmationCode);
    if (activeProjectId === id) {
      setActiveProjectIdState('');
      localStorage.removeItem(STORAGE_KEY_ACTIVE_PROJECT);
      localStorage.removeItem('viewer_target_doc_id');
      localStorage.removeItem('viewer_target_sheet_id');
      window.dispatchEvent(new CustomEvent('active-project-changed', {
        detail: { projectId: '', project: null }
      }));
    }
    await reloadProjects();
  };

  const exportProject = async (id: string) => {
    const data = await apiService.exportProject(id);
    const proj = projects.find((p) => p.id === id);
    const code = proj?.code || 'PROJECT';
    const dateStr = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const filename = `${code}_export_${dateStr}.json`;

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <ProjectContext.Provider
      value={{
        projects,
        activeProject,
        activeProjectId,
        isLoading,
        error,
        setActiveProjectId,
        reloadProjects,
        createProject,
        updateProject,
        archiveProject,
        restoreProject,
        unarchiveProject,
        clearProjectContent,
        deleteProjectConfirmed,
        deleteProject,
        exportProject,
      }}
    >
      {children}
    </ProjectContext.Provider>
  );
};

export const useProject = () => {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error('useProject debe ser utilizado dentro de un ProjectProvider');
  }
  return context;
};
