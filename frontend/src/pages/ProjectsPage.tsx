import React, { useEffect, useState } from 'react';
import { apiService } from '../services/api';
import { Project, DocumentItem, DocumentSheet, Discipline } from '../types';
import { useProject } from '../context/ProjectContext';
import {
  FolderPlus, Upload, FileText, CheckCircle2, Layers,
  RefreshCw, Eye, AlertCircle, Clock, ExternalLink, Plus, Trash2,
  FolderKanban, Archive, ArchiveRestore, Download, Edit3, Check, Search,
  Filter, Building2, Shield, Calendar, BarChart3, ChevronRight, HardDriveDownload,
  Compass, SquareCheck, UploadCloud, Eraser
} from 'lucide-react';
import { DeleteDocumentModal } from '../components/DeleteDocumentModal';
import { ProjectFormModal, PROJECT_STAGES, PROJECT_DISCIPLINES } from '../components/ProjectFormModal';
import { ProjectDeleteModal } from '../components/ProjectDeleteModal';
import { CompletenessGatekeeperCard } from '../components/CompletenessGatekeeperCard';
import { DocumentDeliverableModal } from '../components/DocumentDeliverableModal';
import { ProjectMaturityProfileView } from '../components/ProjectMaturityProfileView';
import { BatchDocumentUploadModal } from '../components/BatchDocumentUploadModal';


export const ProjectsPage: React.FC = () => {
  const {
    projects,
    activeProject,
    activeProjectId,
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
    error: projectContextError,
  } = useProject();

  // Estados de vista
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [docSheets, setDocSheets] = useState<DocumentSheet[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Modales
  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [projectToEdit, setProjectToEdit] = useState<Project | null>(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deleteModalMode, setDeleteModalMode] = useState<'clear_content' | 'delete'>('delete');
  const [projectToDelete, setProjectToDelete] = useState<Project | null>(null);
  const [docToDelete, setDocToDelete] = useState<DocumentItem | null>(null);
  const [isDocDeleteModalOpen, setIsDocDeleteModalOpen] = useState(false);
  const [docToClassify, setDocToClassify] = useState<DocumentItem | null>(null);
  const [isClassifyModalOpen, setIsClassifyModalOpen] = useState(false);
  const [completenessRefreshKey, setCompletenessRefreshKey] = useState(0);
  const [isBatchUploadModalOpen, setIsBatchUploadModalOpen] = useState(false);

  // Filtros
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedStageFilter, setSelectedStageFilter] = useState<string>('all');
  const [selectedStatusFilter, setSelectedStatusFilter] = useState<string>('all');
  const [selectedDisciplineFilter, setSelectedDisciplineFilter] = useState<string>('all');

  // Proyecto seleccionado para inspección en el panel inferior
  const [inspectedProjectId, setInspectedProjectId] = useState<string>(activeProjectId);
  const [projectDetailTab, setProjectDetailTab] = useState<'maturity' | 'completeness' | 'documents'>('maturity');

  useEffect(() => {
    if (activeProjectId && !inspectedProjectId) {
      setInspectedProjectId(activeProjectId);
    }
  }, [activeProjectId]);

  useEffect(() => {
    if (inspectedProjectId) {
      loadDocuments(inspectedProjectId);
    } else if (activeProjectId) {
      loadDocuments(activeProjectId);
    }
  }, [inspectedProjectId, activeProjectId]);

  const loadDocuments = async (projectId: string) => {
    try {
      setLoadingDocs(true);
      const docs = await apiService.getDocuments(projectId);
      setDocuments(docs);

      if (docs.length > 0) {
        const targetDoc = docs.find((d) => d.id === selectedDocId) || docs[0];
        setSelectedDocId(targetDoc.id);

        if (targetDoc.sheets && targetDoc.sheets.length > 0) {
          setDocSheets(targetDoc.sheets);
        } else {
          try {
            const sheets = await apiService.getDocumentSheets(targetDoc.id);
            setDocSheets(sheets);
          } catch {
            setDocSheets([]);
          }
        }
      } else {
        setSelectedDocId(null);
        setDocSheets([]);
      }
    } catch (e: any) {
      console.error('Error al cargar documentos del proyecto:', e);
    } finally {
      setLoadingDocs(false);
    }
  };

  const handleSelectDoc = async (doc: DocumentItem) => {
    setSelectedDocId(doc.id);
    if (doc.sheets && doc.sheets.length > 0) {
      setDocSheets(doc.sheets);
    } else {
      try {
        const sheets = await apiService.getDocumentSheets(doc.id);
        setDocSheets(sheets);
      } catch {
        setDocSheets([]);
      }
    }
  };

  const [reprocessingDocId, setReprocessingDocId] = useState<string | null>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    const targetProjId = inspectedProjectId || activeProjectId;
    if (!file || !targetProjId) return;

    try {
      setUploading(true);
      setErrorMessage(null);
      setSuccessMessage(null);
      await apiService.uploadDocument(targetProjId, file);
      setSuccessMessage(`Documento «${file.name}» (${(file.size / 1024).toFixed(1)} KB) cargado e indexado exitosamente.`);
      await loadDocuments(targetProjId);
      await reloadProjects();
      setCompletenessRefreshKey(prev => prev + 1);
    } catch (err: any) {
      const msg = err.response?.data?.message || err.response?.data?.detail || err.message || 'Error al procesar y cargar el documento.';
      setErrorMessage(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const handleReprocessDoc = async (docId: string) => {
    try {
      setReprocessingDocId(docId);
      setErrorMessage(null);
      await apiService.reprocessDocument(docId);
      setSuccessMessage('Documento reprocesado exitosamente.');
      const targetProjId = inspectedProjectId || activeProjectId;
      if (targetProjId) await loadDocuments(targetProjId);
    } catch (err: any) {
      const msg = err.response?.data?.message || err.response?.data?.detail || err.message || 'Error al reprocesar documento.';
      setErrorMessage(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setReprocessingDocId(null);
    }
  };


  // Filtrado de proyectos
  const filteredProjects = projects.filter((p) => {
    if (p.status === 'deleted') return false;

    // Filtro de búsqueda
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchName = p.name.toLowerCase().includes(q);
      const matchCode = p.code.toLowerCase().includes(q);
      const matchClient = p.client_name?.toLowerCase().includes(q);
      if (!matchName && !matchCode && !matchClient) return false;
    }

    // Filtro de etapa
    if (selectedStageFilter !== 'all') {
      const pStage = p.stage || p.settings?.stage;
      if (pStage !== selectedStageFilter) return false;
    }

    // Filtro de estado
    if (selectedStatusFilter === 'active' && p.status === 'archived') return false;
    if (selectedStatusFilter === 'archived' && p.status !== 'archived') return false;

    // Filtro de disciplina
    if (selectedDisciplineFilter !== 'all' && p.discipline !== selectedDisciplineFilter) return false;

    return true;
  });

  const inspectedProject = projects.find((p) => p.id === inspectedProjectId) || activeProject;

  const totalActive = projects.filter((p) => p.status !== 'archived' && p.status !== 'deleted').length;
  const totalArchived = projects.filter((p) => p.status === 'archived').length;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Encabezado Principal */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-600 text-white shadow-lg shadow-blue-500/20">
              <FolderKanban className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
                Centro de Gestión de Proyectos
              </h1>
              <p className="text-xs text-slate-400">
                Administra el ciclo de vida, etapas de ingeniería, entregables y conmutación de contexto.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => reloadProjects()}
            className="px-3 py-2 text-xs font-semibold rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 flex items-center gap-1.5 transition-colors"
            title="Refrescar lista de proyectos"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refrescar</span>
          </button>
          <button
            onClick={() => {
              setProjectToEdit(null);
              setIsFormModalOpen(true);
            }}
            className="px-4 py-2 text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 active:bg-blue-700 rounded-xl shadow-lg shadow-blue-600/30 flex items-center gap-2 transition-all cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Nuevo Proyecto</span>
          </button>
        </div>
      </div>

      {/* Alertas de Notificación */}
      {(errorMessage || projectContextError) && (
        <div className="p-3.5 rounded-xl bg-rose-950/70 border border-rose-800 text-xs text-rose-300 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{errorMessage || projectContextError}</span>
          </div>
          {errorMessage && (
            <button onClick={() => setErrorMessage(null)} className="text-rose-400 hover:text-rose-200 text-xs font-bold cursor-pointer">
              ✕
            </button>
          )}
        </div>
      )}

      {successMessage && (
        <div className="p-3.5 rounded-xl bg-emerald-950/70 border border-emerald-800 text-xs text-emerald-300 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{successMessage}</span>
          </div>
          <button onClick={() => setSuccessMessage(null)} className="text-emerald-400 hover:text-emerald-200 text-xs font-bold">
            ✕
          </button>
        </div>
      )}

      {/* Tarjetas Resumen de Métricas */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 flex items-center justify-between">
          <div>
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Total Proyectos</p>
            <p className="text-2xl font-black text-slate-100 mt-1">{projects.filter(p => p.status !== 'deleted').length}</p>
          </div>
          <div className="p-3 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <FolderKanban className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 flex items-center justify-between">
          <div>
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Activos en Curso</p>
            <p className="text-2xl font-black text-emerald-400 mt-1">{totalActive}</p>
          </div>
          <div className="p-3 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 flex items-center justify-between">
          <div>
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Archivados</p>
            <p className="text-2xl font-black text-amber-400 mt-1">{totalArchived}</p>
          </div>
          <div className="p-3 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Archive className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-gradient-to-br from-blue-950/50 to-slate-900 border border-blue-800/40 flex items-center justify-between">
          <div className="min-w-0">
            <p className="text-[11px] font-bold text-blue-300 uppercase tracking-wider">Proyecto Activo</p>
            <p className="text-sm font-bold text-slate-100 mt-1 truncate">
              {activeProject ? activeProject.code : 'Sin seleccionar'}
            </p>
            <p className="text-[10px] text-slate-400 truncate">
              {activeProject?.name || 'Selecciona un proyecto'}
            </p>
          </div>
          <div className="p-2.5 rounded-xl bg-blue-500/20 text-blue-300 border border-blue-500/30 shrink-0">
            <Check className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Barra de Filtros y Búsqueda */}
      <div className="p-4 rounded-2xl bg-slate-900/70 border border-slate-800 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
        {/* Input Buscador */}
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Buscar por código, nombre o cliente..."
            className="w-full pl-9 pr-8 py-2 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 text-xs"
            >
              ✕
            </button>
          )}
        </div>

        {/* Selectores de Filtros */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Filtro Etapa */}
          <select
            value={selectedStageFilter}
            onChange={(e) => setSelectedStageFilter(e.target.value)}
            className="px-3 py-2 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-blue-500"
          >
            <option value="all">Todas las Etapas</option>
            {PROJECT_STAGES.map((st) => (
              <option key={st} value={st}>{st}</option>
            ))}
          </select>

          {/* Filtro Estado */}
          <select
            value={selectedStatusFilter}
            onChange={(e) => setSelectedStatusFilter(e.target.value)}
            className="px-3 py-2 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-blue-500"
          >
            <option value="all">Todos los Estados</option>
            <option value="active">Activos</option>
            <option value="archived">Archivados</option>
          </select>

          {/* Filtro Disciplina */}
          <select
            value={selectedDisciplineFilter}
            onChange={(e) => setSelectedDisciplineFilter(e.target.value)}
            className="px-3 py-2 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-blue-500"
          >
            <option value="all">Todas las Disciplinas</option>
            {PROJECT_DISCIPLINES.map((d) => (
              <option key={d.id} value={d.id}>{d.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Tabla / Listado de Proyectos */}
      <div className="rounded-2xl bg-slate-900/60 border border-slate-800 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950/80 text-slate-400 uppercase text-[10px] font-bold border-b border-slate-800 tracking-wider">
              <tr>
                <th className="py-3 px-4">Estado</th>
                <th className="py-3 px-4">Código & Proyecto</th>
                <th className="py-3 px-4">Cliente</th>
                <th className="py-3 px-4">Etapa Actual</th>
                <th className="py-3 px-4">Disciplina</th>
                <th className="py-3 px-4 text-center">Entregables</th>
                <th className="py-3 px-4 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {filteredProjects.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-500 italic">
                    No se encontraron proyectos con los criterios seleccionados.
                  </td>
                </tr>
              ) : (
                filteredProjects.map((p) => {
                  const isActive = p.id === activeProjectId;
                  const isInspected = p.id === inspectedProjectId;
                  const isArchived = p.status === 'archived';

                  return (
                    <tr
                      key={p.id}
                      onClick={() => setInspectedProjectId(p.id)}
                      className={`hover:bg-slate-800/40 transition-colors cursor-pointer ${
                        isInspected ? 'bg-blue-950/30' : ''
                      }`}
                    >
                      {/* Estado */}
                      <td className="py-3.5 px-4">
                        <div className="flex flex-col gap-1 items-start">
                          {isActive ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-950 text-emerald-300 border border-emerald-700 text-[10px] font-bold">
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                              ACTIVO
                            </span>
                          ) : isArchived ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-950 text-amber-400 border border-amber-800 text-[10px] font-bold">
                              <Archive className="w-3 h-3" />
                              ARCHIVADO
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-800 text-slate-300 border border-slate-700 text-[10px] font-medium">
                              DISPONIBLE
                            </span>
                          )}

                          {p.cleanup_status === 'failed_cleanup' && (
                            <span
                              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-rose-950 text-rose-400 border border-rose-800 text-[9px] font-semibold"
                              title={`Error de limpieza: ${p.cleanup_error || 'Fallo de almacenamiento'}`}
                            >
                              <AlertCircle className="w-2.5 h-2.5" />
                              LIMPIEZA PENDIENTE
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Código y Nombre */}
                      <td className="py-3.5 px-4">
                        <div className="font-mono font-bold text-blue-400 text-[11px] mb-0.5">
                          {p.code}
                        </div>
                        <div className="font-bold text-slate-100 text-xs">
                          {p.name}
                        </div>
                        {p.description && (
                          <div className="text-[11px] text-slate-400 line-clamp-1 max-w-sm">
                            {p.description}
                          </div>
                        )}
                      </td>

                      {/* Cliente */}
                      <td className="py-3.5 px-4 text-slate-300 font-medium">
                        {p.client_name || <span className="text-slate-500 italic">No especificado</span>}
                      </td>

                      {/* Etapa Actual */}
                      <td className="py-3.5 px-4">
                        <span className="px-2 py-1 rounded-lg bg-amber-950/60 text-amber-300 border border-amber-800/60 text-[11px] font-semibold">
                          {p.stage || p.settings?.stage || 'Ingeniería de Detalle'}
                        </span>
                      </td>

                      {/* Disciplina */}
                      <td className="py-3.5 px-4">
                        <span className="px-2 py-0.5 rounded-md bg-slate-800 text-slate-300 border border-slate-700 text-[10px] font-medium capitalize">
                          {p.discipline}
                        </span>
                      </td>

                      {/* Contadores */}
                      <td className="py-3.5 px-4 text-center">
                        <div className="inline-flex items-center gap-3 text-[11px] text-slate-400 font-mono bg-slate-950 px-2.5 py-1 rounded-lg border border-slate-800">
                          <span title="Documentos">📄 {p.documents_count ?? 0}</span>
                          <span title="Láminas">📐 {p.sheets_count ?? 0}</span>
                        </div>
                      </td>

                      {/* Acciones */}
                      <td className="py-3.5 px-4 text-right" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-end gap-1.5">
                          {/* Botón Establecer como Activo */}
                          {!isActive && (
                            <button
                              onClick={() => {
                                setActiveProjectId(p.id);
                                setInspectedProjectId(p.id);
                              }}
                              className="px-2.5 py-1 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold text-[11px] flex items-center gap-1 transition-colors shadow-sm"
                              title="Establecer como proyecto activo para todo el sistema"
                            >
                              <Check className="w-3 h-3" />
                              <span>Activar</span>
                            </button>
                          )}

                          {/* Botón Editar */}
                          <button
                            onClick={() => {
                              setProjectToEdit(p);
                              setIsFormModalOpen(true);
                            }}
                            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
                            title="Editar proyecto"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>

                          {/* Botón Exportar */}
                          <button
                            onClick={() => exportProject(p.id)}
                            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
                            title="Exportar respaldo completo en JSON"
                          >
                            <Download className="w-3.5 h-3.5" />
                          </button>

                          {/* Botón Archivar / Desarchivar */}
                          {isArchived ? (
                            <button
                              onClick={() => unarchiveProject(p.id)}
                              className="p-1.5 rounded-lg bg-amber-950/60 hover:bg-amber-900 border border-amber-800 text-amber-300 transition-colors"
                              title="Desarchivar proyecto"
                            >
                              <ArchiveRestore className="w-3.5 h-3.5" />
                            </button>
                          ) : (
                            <button
                              onClick={() => archiveProject(p.id)}
                              className="p-1.5 rounded-lg bg-slate-800 hover:bg-amber-950 hover:text-amber-300 text-slate-400 transition-colors"
                              title="Archivar proyecto"
                            >
                              <Archive className="w-3.5 h-3.5" />
                            </button>
                          )}

                          {/* Botón Vaciar Contenido */}
                          <button
                            onClick={() => {
                              setProjectToDelete(p);
                              setDeleteModalMode('clear_content');
                              setIsDeleteModalOpen(true);
                            }}
                            className="p-1.5 rounded-lg bg-slate-800 hover:bg-amber-950 hover:text-amber-300 text-slate-400 transition-colors"
                            title="Vaciar contenido del proyecto (documentos, extracciones, hallazgos)"
                          >
                            <Eraser className="w-3.5 h-3.5" />
                          </button>

                          {/* Botón Eliminar Permanentemente */}
                          <button
                            onClick={() => {
                              setProjectToDelete(p);
                              setDeleteModalMode('delete');
                              setIsDeleteModalOpen(true);
                            }}
                            className="p-1.5 rounded-lg bg-slate-800 hover:bg-rose-950 hover:text-rose-300 text-slate-400 transition-colors"
                            title="Eliminar proyecto permanentemente"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Subsección: Documentos y Entregables del Proyecto Inspeccionado */}
      {inspectedProject && (
        <div className="space-y-6">
          
          {/* Selector de Pestañas de Inspección del Proyecto */}
          <div className="flex border-b border-slate-800 text-xs font-semibold gap-2 flex-wrap">
            <button
              onClick={() => setProjectDetailTab('maturity')}
              className={`pb-3 px-3 border-b-2 transition flex items-center gap-1.5 ${
                projectDetailTab === 'maturity' ? 'border-blue-500 text-blue-400' : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Compass className="w-4 h-4" /> Perfil de Madurez & Suficiencia Informacional
            </button>
            <button
              onClick={() => setProjectDetailTab('completeness')}
              className={`pb-3 px-3 border-b-2 transition flex items-center gap-1.5 ${
                projectDetailTab === 'completeness' ? 'border-blue-500 text-blue-400' : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <SquareCheck className="w-4 h-4" /> Gatekeeper & Completitud Documental
            </button>
            <button
              onClick={() => setProjectDetailTab('documents')}
              className={`pb-3 px-3 border-b-2 transition flex items-center gap-1.5 ${
                projectDetailTab === 'documents' ? 'border-blue-500 text-blue-400' : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <FileText className="w-4 h-4" /> Documentos & Láminas ({documents.length})
            </button>
          </div>

          {projectDetailTab === 'maturity' && (
            <ProjectMaturityProfileView />
          )}

          {projectDetailTab === 'completeness' && (
            <CompletenessGatekeeperCard
              key={`${inspectedProject.id}-${inspectedProject.stage}-${completenessRefreshKey}`}
              projectId={inspectedProject.id}
              projectName={inspectedProject.name}
              projectStage={inspectedProject.stage || 'Ingeniería de Detalle'}
              onDocumentClassifyClick={(docId) => {
                const targetDoc = documents.find(d => d.id === docId);
                if (targetDoc) {
                  setDocToClassify(targetDoc);
                  setIsClassifyModalOpen(true);
                }
              }}
            />
          )}

          <div className="rounded-2xl bg-slate-900/80 border border-slate-800 p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold text-blue-400">{inspectedProject.code}</span>
                  <h2 className="text-base font-bold text-slate-100">
                    Documentos & Entregables de «{inspectedProject.name}»
                  </h2>
                </div>
                <p className="text-xs text-slate-400">
                  Planos, memorias de cálculo y especificaciones técnicas asociados al proyecto.
                </p>
              </div>

              {/* Subir Documentos al proyecto */}
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsBatchUploadModalOpen(true)}
                  className="px-3.5 py-1.5 text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 active:bg-blue-700 rounded-xl shadow-md shadow-blue-600/20 flex items-center gap-1.5 transition-all cursor-pointer"
                  title="Abrir asistente de carga múltiple de documentos y planos"
                >
                  <UploadCloud className="w-4 h-4" />
                  <span>Carga por Lotes / Planos</span>
                </button>

                <label
                  className={`px-3 py-1.5 text-xs font-semibold text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-xl flex items-center gap-1.5 cursor-pointer transition-colors ${
                    uploading ? 'opacity-50 pointer-events-none' : ''
                  }`}
                  title="Carga instantánea de un único archivo"
                >
                  <Upload className="w-3.5 h-3.5" />
                  <span>{uploading ? 'Cargando...' : 'Carga Rápida'}</span>
                  <input
                    type="file"
                    accept=".pdf,.png,.jpg,.jpeg,.webp,.bmp,.dxf,.dwg,.docx,.xlsx,.txt,.csv,.zip"
                    onChange={handleFileUpload}
                    className="hidden"
                    disabled={uploading}
                  />
                </label>
              </div>
            </div>


            {/* Listado de Documentos del Proyecto */}
            {loadingDocs ? (
              <div className="py-8 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin text-blue-400" />
                <span>Cargando documentos del proyecto...</span>
              </div>
            ) : documents.length === 0 ? (
              <div className="py-8 text-center rounded-xl bg-slate-950/40 border border-dashed border-slate-800">
                <FileText className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                <p className="text-xs text-slate-400 font-medium">Este proyecto aún no contiene documentos cargados.</p>
                <p className="text-[11px] text-slate-500 mt-1">Haz clic en «Cargar Documento» para añadir planos o especificaciones en PDF.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {documents.map((doc) => {
                  const isDocSelected = doc.id === selectedDocId;

                  return (
                    <div
                      key={doc.id}
                      onClick={() => handleSelectDoc(doc)}
                      className={`p-4 rounded-xl border transition-all cursor-pointer ${
                        isDocSelected
                          ? 'bg-blue-950/40 border-blue-600/50 shadow-md'
                          : 'bg-slate-950/60 border-slate-800 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <FileText className="w-4 h-4 text-blue-400 shrink-0" />
                          <div className="min-w-0">
                            <span className="text-xs font-bold text-slate-100 truncate block">
                              {(doc as any).title || doc.filename}
                            </span>
                            <span className="text-[10px] text-slate-400 font-mono">
                              {((doc.file_size_bytes || 0) / 1024).toFixed(1)} KB · {doc.mime_type?.split('/')[1] || 'doc'}
                            </span>
                          </div>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          {doc.status === 'ready' && (
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-950/60 text-emerald-400 border border-emerald-800/60" title="Procesado e indexado">
                              <CheckCircle2 className="w-3 h-3" />
                              <span>Listo</span>
                            </span>
                          )}
                          {doc.status === 'processing' && (
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-950/60 text-amber-400 border border-amber-800/60 animate-pulse" title="Procesando">
                              <RefreshCw className="w-3 h-3 animate-spin" />
                              <span>Procesando</span>
                            </span>
                          )}
                          {doc.status === 'uploaded' && (
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-950/60 text-blue-400 border border-blue-800/60" title="Cargado, pendiente de análisis">
                              <Clock className="w-3 h-3" />
                              <span>Cargado</span>
                            </span>
                          )}
                          {doc.status === 'failed' && (
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-rose-950/60 text-rose-400 border border-rose-800/60" title={doc.error_message || 'Fallo de procesamiento'}>
                              <AlertCircle className="w-3 h-3" />
                              <span>Falló</span>
                            </span>
                          )}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setDocToDelete(doc);
                              setIsDocDeleteModalOpen(true);
                            }}
                            className="p-1 rounded text-slate-500 hover:text-rose-400 hover:bg-slate-800 transition-colors"
                            title="Eliminar documento"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>

                      {doc.status === 'failed' && (
                        <div className="mt-2 p-2 rounded bg-rose-950/30 border border-rose-900/50 text-[11px] text-rose-300 flex items-center justify-between gap-2">
                          <span className="truncate" title={doc.error_message || 'Error en procesamiento'}>
                            {doc.error_message || 'Fallo durante el procesamiento.'}
                          </span>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleReprocessDoc(doc.id);
                            }}
                            disabled={reprocessingDocId === doc.id}
                            className="px-2 py-0.5 text-[10px] font-bold text-white bg-rose-700 hover:bg-rose-600 rounded flex items-center gap-1 shrink-0 transition"
                          >
                            <RefreshCw className={`w-2.5 h-2.5 ${reprocessingDocId === doc.id ? 'animate-spin' : ''}`} />
                            <span>Reintentar</span>
                          </button>
                        </div>
                      )}

                      <div className="mt-3 flex items-center justify-between text-[11px] text-slate-400 border-t border-slate-800/80 pt-2 font-mono">
                        <span>Láminas: <strong>{(doc as any).total_sheets || doc.sheets?.length || doc.page_count || 1}</strong></span>
                        <span className="capitalize">{(doc as any).discipline || ''}</span>
                      </div>

                      <div className="mt-3 pt-2 border-t border-slate-800/60 flex items-center justify-between gap-2">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setDocToClassify(doc);
                            setIsClassifyModalOpen(true);
                          }}
                          className="text-[11px] font-semibold text-indigo-400 hover:text-indigo-300 bg-indigo-950/40 hover:bg-indigo-900/60 border border-indigo-700/50 px-2.5 py-1 rounded-lg flex items-center gap-1 transition"
                        >
                          <Layers className="w-3 h-3" />
                          <span>Clasificar / Estado</span>
                        </button>

                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            localStorage.setItem('viewer_target_doc_id', doc.id);
                            if (doc.sheets && doc.sheets.length > 0) {
                              localStorage.setItem('viewer_target_sheet_id', doc.sheets[0].id);
                            }
                            window.dispatchEvent(new CustomEvent('navigate-tab', { detail: { tab: 'viewer' } }));
                          }}
                          className="text-[11px] font-bold text-blue-400 hover:text-blue-300 flex items-center gap-1 transition-colors"
                        >
                          <span>Visor</span>
                          <ExternalLink className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Modal de Clasificación de Entregables */}
      {docToClassify && (
        <DocumentDeliverableModal
          document={docToClassify}
          isOpen={isClassifyModalOpen}
          onClose={() => {
            setIsClassifyModalOpen(false);
            setDocToClassify(null);
          }}
          onSaved={() => {
            setCompletenessRefreshKey(prev => prev + 1);
            if (inspectedProjectId) loadDocuments(inspectedProjectId);
            setSuccessMessage('Clasificación de entregable guardada exitosamente.');
          }}
        />
      )}

      {/* Modal de Crear / Editar Proyecto */}
      <ProjectFormModal
        isOpen={isFormModalOpen}
        projectToEdit={projectToEdit}
        onClose={() => setIsFormModalOpen(false)}
        onSubmit={async (data, setAsActive) => {
          if (projectToEdit) {
            await updateProject(projectToEdit.id, data);
            setSuccessMessage(`Proyecto «${data.name}» actualizado correctamente.`);
          } else {
            const created = await createProject(data, setAsActive);
            setSuccessMessage(`Proyecto «${created.name}» creado correctamente.`);
          }
        }}
        existingProjects={projects}
        onOpenProject={(projId) => {
          setActiveProjectId(projId);
          setInspectedProjectId(projId);
          setIsFormModalOpen(false);
          setSuccessMessage('Proyecto seleccionado como activo.');
        }}
        onRestoreProject={async (projId) => {
          await unarchiveProject(projId);
          setActiveProjectId(projId);
          setInspectedProjectId(projId);
          setIsFormModalOpen(false);
          setSuccessMessage('Proyecto restaurado y seleccionado como activo.');
        }}
      />

      {/* Modal de Ciclo de Vida: Vaciar Contenido y Eliminación Definitiva */}
      <ProjectDeleteModal
        isOpen={isDeleteModalOpen}
        project={projectToDelete}
        initialMode={deleteModalMode}
        isActiveProject={projectToDelete?.id === activeProjectId}
        onClose={() => setIsDeleteModalOpen(false)}
        onClearContent={async (projectId, confirmationCode, reason) => {
          await clearProjectContent(projectId, confirmationCode, reason);
          setSuccessMessage(`Contenido del proyecto «${projectToDelete?.name || confirmationCode}» vaciado correctamente.`);
          if (inspectedProjectId === projectId) {
            await loadDocuments(projectId);
          }
          setCompletenessRefreshKey((prev) => prev + 1);
        }}
        onDeleteConfirmed={async (projectId, confirmationCode, mode, reason) => {
          await deleteProjectConfirmed(projectId, confirmationCode, mode, reason);
          setSuccessMessage(`Proyecto «${projectToDelete?.name || confirmationCode}» eliminado exitosamente (${mode === 'hard_delete' ? 'definitivo' : 'anonimizado'}).`);
          if (inspectedProjectId === projectId) {
            setInspectedProjectId('');
            setDocuments([]);
            setSelectedDocId(null);
            setDocSheets([]);
          }
        }}
      />

      {/* Modal de Eliminación de Documento */}
      <DeleteDocumentModal
        isOpen={isDocDeleteModalOpen}
        document={docToDelete}
        onClose={() => setIsDocDeleteModalOpen(false)}
        onDeleted={() => {
          setSuccessMessage('Documento eliminado correctamente.');
          if (inspectedProjectId) loadDocuments(inspectedProjectId);
          reloadProjects();
        }}
      />

      {/* Modal de Carga por Lotes de Documentos y Planos */}
      {inspectedProject && (
        <BatchDocumentUploadModal
          isOpen={isBatchUploadModalOpen}
          projectId={inspectedProject.id}
          projectName={inspectedProject.name}
          projectCode={inspectedProject.code}
          onClose={() => setIsBatchUploadModalOpen(false)}
          onSuccess={(uploadedDocs, summaryMsg) => {
            setSuccessMessage(summaryMsg);
            loadDocuments(inspectedProject.id);
            reloadProjects();
            setCompletenessRefreshKey(prev => prev + 1);
          }}
        />
      )}
    </div>
  );

};
