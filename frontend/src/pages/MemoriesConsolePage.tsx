import React, { useEffect, useState } from 'react';
import { apiService } from '../services/api';
import {
  MemoriesOverviewResponse, MemoryOverviewDetail,
  MemoryRecordItem, MemoryConsistencyReport, MemoryConsistencyIssue,
  MemoryMaintenanceResult
} from '../types';
import {
  Database, FileText, BookOpen, Layers, ShieldCheck,
  Search, Plus, Edit2, Trash2, Archive, CheckCircle2,
  AlertTriangle, RefreshCw, Download, ShieldAlert,
  Wrench, Check, X, Filter, ChevronLeft, ChevronRight,
  ExternalLink, Sparkles, HelpCircle, HardDrive, Compass
} from 'lucide-react';
import { SymbolCurationStudioModal } from '../components/SymbolCurationStudioModal';

type MemoryTabKey = 'document_memory' | 'normative_memory' | 'template_memory' | 'decision_memory' | 'diagnostics';

export const MemoriesConsolePage: React.FC = () => {
  const [overview, setOverview] = useState<MemoriesOverviewResponse | null>(null);
  const [activeTab, setActiveTab] = useState<MemoryTabKey>('normative_memory');
  const [isSymbolStudioOpen, setIsSymbolStudioOpen] = useState(false);
  const [records, setRecords] = useState<MemoryRecordItem[]>([]);
  const [totalRecords, setTotalRecords] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(15);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [disciplineFilter, setDisciplineFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [recordsLoading, setRecordsLoading] = useState(false);

  // Diagnóstico de Consistencia
  const [consistencyReport, setConsistencyReport] = useState<MemoryConsistencyReport | null>(null);
  const [diagnosticsLoading, setDiagnosticsLoading] = useState(false);

  // Modales
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState<MemoryRecordItem | null>(null);
  const [isMaintenanceModalOpen, setIsMaintenanceModalOpen] = useState(false);
  const [maintenanceAction, setMaintenanceAction] = useState('full_maintenance');
  const [maintenanceResult, setMaintenanceResult] = useState<MemoryMaintenanceResult | null>(null);
  const [maintenanceRunning, setMaintenanceRunning] = useState(false);

  // Formularios de Creación / Edición
  const [formCode, setFormCode] = useState('');
  const [formTitle, setFormTitle] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formDiscipline, setFormDiscipline] = useState('general');
  const [formCategory, setFormCategory] = useState('general');
  const [formStatus, setFormStatus] = useState('active');
  const [formRuleExpression, setFormRuleExpression] = useState('');
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // 1. Cargar Overview
  const fetchOverview = async () => {
    try {
      setLoading(true);
      const data = await apiService.getMemoriesOverview();
      setOverview(data);
    } catch (err) {
      console.error('Error fetching memories overview:', err);
    } finally {
      setLoading(false);
    }
  };

  // 2. Cargar Registros de la Memoria Activa
  const fetchRecords = async () => {
    if (activeTab === 'diagnostics') return;
    try {
      setRecordsLoading(true);
      const res = await apiService.getMemoryRecords(activeTab, {
        search: searchQuery || undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
        discipline: disciplineFilter !== 'all' ? disciplineFilter : undefined,
        page,
        page_size: pageSize
      });
      setRecords(res.records);
      setTotalRecords(res.total_count);
    } catch (err) {
      console.error('Error fetching memory records:', err);
    } finally {
      setRecordsLoading(false);
    }
  };

  // 3. Cargar Diagnóstico de Consistencia
  const fetchDiagnostics = async () => {
    try {
      setDiagnosticsLoading(true);
      const rep = await apiService.checkMemoriesConsistency();
      setConsistencyReport(rep);
    } catch (err) {
      console.error('Error running cross consistency check:', err);
    } finally {
      setDiagnosticsLoading(false);
    }
  };

  useEffect(() => {
    fetchOverview();
  }, []);

  useEffect(() => {
    if (activeTab === 'diagnostics') {
      fetchDiagnostics();
    } else {
      setPage(1);
      fetchRecords();
    }
  }, [activeTab, statusFilter, disciplineFilter]);

  useEffect(() => {
    if (activeTab !== 'diagnostics') {
      fetchRecords();
    }
  }, [page]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchRecords();
  };

  // Abrir Modal de Creación
  const openCreateModal = () => {
    setFormCode('');
    setFormTitle('');
    setFormDescription('');
    setFormDiscipline('general');
    setFormCategory(activeTab === 'normative_memory' ? 'high' : 'general');
    setFormStatus('active');
    setFormRuleExpression(activeTab === 'normative_memory' ? 'clear_width_m >= 0.85' : '');
    setActionError(null);
    setIsCreateModalOpen(true);
  };

  // Abrir Modal de Edición
  const openEditModal = (rec: MemoryRecordItem) => {
    setSelectedRecord(rec);
    setFormTitle(rec.title);
    setFormDescription(rec.description || '');
    setFormDiscipline(rec.discipline);
    setFormCategory(rec.category_or_nature);
    setFormStatus(rec.status);
    setActionError(null);
    setIsEditModalOpen(true);
  };

  // Guardar Creación
  const handleSaveCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiService.createMemoryRecord(activeTab, {
        memory_type: activeTab,
        code_or_identifier: formCode || `REC-${Date.now().toString().slice(-4)}`,
        title: formTitle,
        description: formDescription,
        discipline: formDiscipline,
        category_or_nature: formCategory,
        status: formStatus,
        metadata_payload: { rule_expression: formRuleExpression }
      });
      setIsCreateModalOpen(false);
      setActionSuccess('Registro creado exitosamente en la memoria.');
      setTimeout(() => setActionSuccess(null), 4000);
      fetchRecords();
      fetchOverview();
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Error creando registro en la memoria.');
    }
  };

  // Guardar Edición
  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRecord) return;
    try {
      await apiService.updateMemoryRecord(selectedRecord.memory_type, selectedRecord.id, {
        title: formTitle,
        description: formDescription,
        discipline: formDiscipline,
        category_or_nature: formCategory,
        status: formStatus
      });
      setIsEditModalOpen(false);
      setActionSuccess('Registro actualizado correctamente.');
      setTimeout(() => setActionSuccess(null), 4000);
      fetchRecords();
      fetchOverview();
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Error actualizando registro.');
    }
  };

  // Cambiar Estado Rápido (Aprobar / Obsoleto / Archivar)
  const handleQuickStatusChange = async (rec: MemoryRecordItem, nextStatus: string) => {
    try {
      await apiService.updateMemoryRecord(rec.memory_type, rec.id, { status: nextStatus });
      setActionSuccess(`Estado de «${rec.code_or_identifier}» cambiado a ${nextStatus}.`);
      setTimeout(() => setActionSuccess(null), 3000);
      fetchRecords();
      fetchOverview();
    } catch (err) {
      console.error('Error updating status:', err);
    }
  };

  // Eliminar Registro
  const handleDeleteRecord = async (rec: MemoryRecordItem) => {
    if (!window.confirm(`¿Estás seguro de eliminar el registro «${rec.code_or_identifier} - ${rec.title}»? Esta acción requiere validación de dependencias.`)) {
      return;
    }
    try {
      await apiService.deleteMemoryRecord(rec.memory_type, rec.id);
      setActionSuccess(`Registro «${rec.code_or_identifier}» eliminado correctamente.`);
      setTimeout(() => setActionSuccess(null), 3000);
      fetchRecords();
      fetchOverview();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'No se pudo eliminar el registro por dependencias activas.');
    }
  };

  // Ejecutar Mantenimiento
  const handleRunMaintenance = async () => {
    try {
      setMaintenanceRunning(true);
      const res = await apiService.runMemoriesMaintenance(maintenanceAction);
      setMaintenanceResult(res);
      fetchOverview();
      if (activeTab === 'diagnostics') fetchDiagnostics();
      else fetchRecords();
    } catch (err: any) {
      alert('Error ejecutando mantenimiento de memorias.');
    } finally {
      setMaintenanceRunning(false);
    }
  };

  // Exportar Respaldo
  const handleExportBackup = async () => {
    try {
      const data = await apiService.exportMemoriesData();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `backup_las_4_memorias_${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert('Error exportando datos de respaldo.');
    }
  };

  const getStatusBadge = (st: string) => {
    switch (st.toLowerCase()) {
      case 'active':
      case 'validada':
      case 'resolved':
      case 'accepted':
        return <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-emerald-950 text-emerald-300 border border-emerald-800">Activo</span>;
      case 'to_confirm':
      case 'por_confirmar':
      case 'open':
      case 'draft':
        return <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-amber-950 text-amber-300 border border-amber-800">Por Validar</span>;
      case 'obsolete':
        return <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-rose-950 text-rose-300 border border-rose-800">Obsoleto</span>;
      case 'archived':
      case 'eliminado':
        return <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-slate-800 text-slate-400 border border-slate-700">Archivado</span>;
      default:
        return <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-slate-800 text-slate-300">{st}</span>;
    }
  };

  return (
    <div className="page-container space-y-6 animate-in fade-in duration-300">
      {/* Header Superior: Consola de Administración */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2.5 rounded-xl bg-purple-600/20 text-purple-400 border border-purple-500/30">
              <Database className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-black text-white tracking-tight">Consola de Administración: Las 4 Memorias</h1>
              <p className="text-xs text-slate-400 mt-0.5">
                Mantenimiento, edición, auditoría de linaje y consistencia transversal de las 4 memorias persistentes.
              </p>
            </div>
          </div>
        </div>

        {/* Acciones Globales de Gestión */}
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={() => {
              setActiveTab('diagnostics');
              fetchDiagnostics();
            }}
            className="px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-amber-300 hover:text-amber-200 text-xs font-semibold flex items-center gap-1.5 border border-amber-800/40 shadow-sm transition-colors"
          >
            <ShieldCheck className="w-4 h-4 text-amber-400" />
            <span>Verificar Consistencia</span>
          </button>

          <button
            onClick={() => {
              setMaintenanceResult(null);
              setIsMaintenanceModalOpen(true);
            }}
            className="px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-cyan-300 hover:text-cyan-200 text-xs font-semibold flex items-center gap-1.5 border border-cyan-800/40 shadow-sm transition-colors"
          >
            <Wrench className="w-4 h-4 text-cyan-400" />
            <span>Mantenimiento & Reindexación</span>
          </button>

          <button
            onClick={handleExportBackup}
            className="px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-200 text-xs font-semibold flex items-center gap-1.5 border border-slate-700 transition-colors shadow-sm"
          >
            <Download className="w-4 h-4 text-slate-400" />
            <span>Exportar Respaldo</span>
          </button>
        </div>
      </div>

      {/* Alerta de Éxito / Error */}
      {actionSuccess && (
        <div className="p-3 rounded-xl bg-emerald-950/80 border border-emerald-700/80 text-emerald-200 text-xs flex items-center gap-2 animate-in fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {/* 1. Tarjetas de Resumen Operativo de las 4 Memorias */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {overview?.memories?.map((mem) => {
          const isSelected = activeTab === mem.memory_type;
          return (
            <div
              key={mem.memory_type}
              onClick={() => setActiveTab(mem.memory_type as MemoryTabKey)}
              className={`p-4 rounded-2xl border transition-all cursor-pointer flex flex-col justify-between ${
                isSelected
                  ? 'bg-slate-900 border-purple-500 shadow-lg shadow-purple-950/40 ring-1 ring-purple-500/50'
                  : 'bg-slate-900/80 hover:bg-slate-900 border-slate-800 hover:border-slate-700'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-slate-300 truncate">{mem.name.split(' (')[0]}</span>
                  <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
                    {mem.status.toUpperCase()}
                  </span>
                </div>
                <div className="text-2xl font-black text-white font-mono my-1">
                  {mem.total_records} <span className="text-xs font-normal text-slate-400 font-sans">registros</span>
                </div>
                <p className="text-[11px] text-slate-400">
                  {mem.secondary_count} {mem.secondary_label}
                </p>
              </div>

              <div className="mt-3 pt-2.5 border-t border-slate-800/80 flex items-center justify-between text-[10px] font-mono text-slate-400">
                <span>Consistencia: <strong>{Math.round(mem.consistency_score * 100)}%</strong></span>
                <span className="text-cyan-400 capitalize">{mem.index_status}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* 2. Barra de Pestañas de Navegación de la Consola */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-1 flex-wrap gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setActiveTab('document_memory')}
            className={`px-3.5 py-2 text-xs font-bold rounded-lg flex items-center gap-2 transition-all ${
              activeTab === 'document_memory'
                ? 'bg-blue-600 text-white shadow-md shadow-blue-600/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            }`}
          >
            <FileText className="w-4 h-4" />
            <span>Document Memory</span>
          </button>

          <button
            onClick={() => setActiveTab('normative_memory')}
            className={`px-3.5 py-2 text-xs font-bold rounded-lg flex items-center gap-2 transition-all ${
              activeTab === 'normative_memory'
                ? 'bg-purple-600 text-white shadow-md shadow-purple-600/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            }`}
          >
            <BookOpen className="w-4 h-4" />
            <span>Normative Memory</span>
          </button>

          <button
            onClick={() => setActiveTab('template_memory')}
            className={`px-3.5 py-2 text-xs font-bold rounded-lg flex items-center gap-2 transition-all ${
              activeTab === 'template_memory'
                ? 'bg-amber-600 text-white shadow-md shadow-amber-600/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            }`}
          >
            <Layers className="w-4 h-4" />
            <span>Template Memory</span>
          </button>

          <button
            onClick={() => setActiveTab('decision_memory')}
            className={`px-3.5 py-2 text-xs font-bold rounded-lg flex items-center gap-2 transition-all ${
              activeTab === 'decision_memory'
                ? 'bg-rose-600 text-white shadow-md shadow-rose-600/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            }`}
          >
            <ShieldAlert className="w-4 h-4" />
            <span>Decision Memory</span>
          </button>

          <button
            onClick={() => setActiveTab('diagnostics')}
            className={`px-3.5 py-2 text-xs font-bold rounded-lg flex items-center gap-2 transition-all ${
              activeTab === 'diagnostics'
                ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/30'
                : 'text-emerald-400 hover:text-emerald-300 hover:bg-slate-800'
            }`}
          >
            <ShieldCheck className="w-4 h-4" />
            <span>Diagnóstico & Consistencia</span>
          </button>
        </div>

        {activeTab !== 'diagnostics' && (
          <div className="flex items-center gap-2">
            {activeTab === 'template_memory' && (
              <button
                type="button"
                onClick={() => setIsSymbolStudioOpen(true)}
                className="px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-bold flex items-center gap-1.5 shadow-md shadow-purple-600/20 transition-all active:scale-95"
              >
                <Compass className="w-3.5 h-3.5 text-purple-200" />
                <span>Estudio Curación Símbolos (HITL)</span>
              </button>
            )}
            <button
              onClick={openCreateModal}
              className="px-3.5 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold flex items-center gap-1.5 shadow-md shadow-cyan-600/20 transition-all active:scale-95"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Nueva Entrada</span>
            </button>
          </div>
        )}
      </div>

      {/* 3. Contenido Principal según Pestaña */}
      {activeTab === 'diagnostics' ? (
        /* Pestaña: Diagnóstico de Consistencia Cruzada */
        <div className="space-y-4">
          <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2.5">
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
                <div>
                  <h2 className="text-sm font-bold text-white">Informe de Integridad Referencial & Consistencia Transversal</h2>
                  <p className="text-xs text-slate-400">Verifica la ausencia de elementos huérfanos, claves rotas y desincronización entre memorias.</p>
                </div>
              </div>
              <button
                onClick={fetchDiagnostics}
                disabled={diagnosticsLoading}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold flex items-center gap-1.5 border border-slate-700"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${diagnosticsLoading ? 'animate-spin text-cyan-400' : ''}`} />
                <span>Re-analizar</span>
              </button>
            </div>

            {/* Métricas de Diagnóstico */}
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-center">
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                <div className="text-xl font-bold font-mono text-cyan-400">{consistencyReport?.total_checks_run ?? 12}</div>
                <div className="text-[11px] text-slate-400">Chequeos Ejecutados</div>
              </div>
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                <div className="text-xl font-bold font-mono text-emerald-400">
                  {consistencyReport?.consistency_health.toUpperCase() ?? 'HEALTHY'}
                </div>
                <div className="text-[11px] text-slate-400">Salud de Integridad</div>
              </div>
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                <div className="text-xl font-bold font-mono text-amber-400">{consistencyReport?.issues_found_count ?? 0}</div>
                <div className="text-[11px] text-slate-400">Inconsistencias Detectadas</div>
              </div>
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                <div className="text-xl font-bold font-mono text-purple-400">{consistencyReport?.orphaned_elements_count ?? 0}</div>
                <div className="text-[11px] text-slate-400">Elementos Huérfanos</div>
              </div>
            </div>

            {/* Listado de Hallazgos de Consistencia */}
            <div className="space-y-2.5 mt-4">
              {consistencyReport?.issues && consistencyReport.issues.length > 0 ? (
                consistencyReport.issues.map((issue) => (
                  <div
                    key={issue.id}
                    className={`p-4 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs ${
                      issue.severity === 'critical'
                        ? 'bg-rose-950/30 border-rose-800/80 text-rose-200'
                        : 'bg-amber-950/30 border-amber-800/80 text-amber-200'
                    }`}
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white text-sm">{issue.title}</span>
                        <span className="px-2 py-0.5 text-[10px] font-mono font-bold rounded bg-black/40 uppercase">
                          {issue.memory_source}
                        </span>
                      </div>
                      <p className="text-slate-300 mt-1 leading-relaxed">{issue.description}</p>
                      <p className="text-slate-400 mt-1 text-[11px]">
                        <strong>Acción recomendada:</strong> {issue.suggested_action}
                      </p>
                    </div>

                    {issue.can_auto_fix && (
                      <button
                        onClick={() => {
                          setMaintenanceAction('cleanup_orphans');
                          handleRunMaintenance();
                        }}
                        className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shrink-0 self-start sm:self-auto shadow"
                      >
                        Auto-Reparar
                      </button>
                    )}
                  </div>
                ))
              ) : (
                <div className="p-6 rounded-xl bg-slate-950/80 border border-slate-800 text-center text-slate-400 text-xs">
                  <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
                  <p className="font-bold text-slate-200 text-sm">100% Consistencia y Cero Elementos Huérfanos</p>
                  <p className="mt-1 text-slate-400">Todas las relaciones entre documentos, láminas, cláusulas normativas y decisiones están perfectamente sincronizadas.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        /* Pestañas de Exploración y Gestión de Registros */
        <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 shadow-xl space-y-4">
          {/* Barra de Búsqueda y Filtros */}
          <form onSubmit={handleSearchSubmit} className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 flex-1 min-w-[240px]">
              <div className="relative flex-1">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder={`Buscar en ${activeTab}...`}
                  className="w-full pl-9 pr-3 py-2 text-xs bg-slate-950 border border-slate-800 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                />
              </div>
              <button
                type="submit"
                className="px-3.5 py-2 text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl border border-slate-700"
              >
                Buscar
              </button>
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              {/* Filtro Estado */}
              <div className="flex items-center gap-1 text-xs text-slate-400">
                <Filter className="w-3.5 h-3.5" />
                <span>Estado:</span>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="bg-slate-950 border border-slate-800 text-slate-300 rounded-lg text-xs px-2 py-1 focus:outline-none"
                >
                  <option value="all">Todos los estados</option>
                  <option value="active">Activo</option>
                  <option value="to_confirm">Por Validar</option>
                  <option value="obsolete">Obsoleto</option>
                  <option value="archived">Archivado</option>
                </select>
              </div>

              <button
                type="button"
                onClick={fetchRecords}
                className="p-1.5 rounded-lg bg-slate-800 text-slate-400 hover:text-white"
                title="Refrescar lista"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>
          </form>

          {/* Tabla de Registros */}
          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950 text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="py-3 px-4 font-semibold">Identificador / Código</th>
                  <th className="py-3 px-4 font-semibold">Título / Descripción</th>
                  <th className="py-3 px-4 font-semibold">Disciplina / Tipo</th>
                  <th className="py-3 px-4 font-semibold">Estado</th>
                  <th className="py-3 px-4 font-semibold">Actualizado</th>
                  <th className="py-3 px-4 font-semibold text-right">Acciones de Gestión</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80 bg-slate-900/60">
                {recordsLoading ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-slate-400">
                      <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-cyan-400" />
                      <span>Cargando registros de la memoria...</span>
                    </td>
                  </tr>
                ) : records.length > 0 ? (
                  records.map((rec) => (
                    <tr key={rec.id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="py-3 px-4 font-mono font-bold text-cyan-400 whitespace-nowrap">
                        {rec.code_or_identifier}
                      </td>
                      <td className="py-3 px-4 max-w-md">
                        <div className="font-semibold text-slate-100">{rec.title}</div>
                        {rec.description && (
                          <div className="text-[11px] text-slate-400 truncate max-w-sm mt-0.5">
                            {rec.description}
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <span className="capitalize font-medium text-slate-300">{rec.discipline}</span>
                        <div className="text-[10px] text-slate-500 font-mono">{rec.category_or_nature}</div>
                      </td>
                      <td className="py-3 px-4">
                        {getStatusBadge(rec.status)}
                      </td>
                      <td className="py-3 px-4 text-slate-400 font-mono text-[11px] whitespace-nowrap">
                        {new Date(rec.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-3 px-4 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            onClick={() => openEditModal(rec)}
                            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
                            title="Editar entrada"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>

                          {rec.status === 'to_confirm' && (
                            <button
                              type="button"
                              onClick={() => handleQuickStatusChange(rec, 'active')}
                              className="px-2 py-1 rounded bg-emerald-950 hover:bg-emerald-900 text-emerald-300 font-bold text-[10px] border border-emerald-800"
                              title="Aprobar y validar para uso"
                            >
                              Aprobar
                            </button>
                          )}

                          {rec.status === 'active' && (
                            <button
                              type="button"
                              onClick={() => handleQuickStatusChange(rec, 'obsolete')}
                              className="px-2 py-1 rounded bg-rose-950/60 hover:bg-rose-900 text-rose-300 text-[10px] border border-rose-800"
                              title="Marcar como obsoleto"
                            >
                              Obsoleto
                            </button>
                          )}

                          <button
                            type="button"
                            onClick={() => handleDeleteRecord(rec)}
                            className="p-1.5 rounded-lg bg-slate-800 hover:bg-rose-950 text-slate-400 hover:text-rose-300 transition-colors"
                            title="Eliminar registro"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-slate-500">
                      No se encontraron registros que coincidan con la búsqueda o filtro.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Paginación */}
          <div className="flex items-center justify-between text-xs text-slate-400 pt-2">
            <div>
              Mostrando {records.length} de {totalRecords} registros totales
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-2.5 py-1 rounded-lg bg-slate-800 text-slate-300 disabled:opacity-40"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="font-mono">Página {page}</span>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={records.length < pageSize}
                className="px-2.5 py-1 rounded-lg bg-slate-800 text-slate-300 disabled:opacity-40"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: Nueva Entrada en Memoria */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-lg shadow-2xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Plus className="w-4 h-4 text-cyan-400" />
                <span>Nueva Entrada en {activeTab}</span>
              </h3>
              <button onClick={() => setIsCreateModalOpen(false)} className="text-slate-400 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            {actionError && (
              <div className="p-2.5 rounded-lg bg-rose-950 border border-rose-800 text-rose-300 text-xs">
                {actionError}
              </div>
            )}

            <form onSubmit={handleSaveCreate} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 font-semibold mb-1">Código / Identificador:</label>
                <input
                  type="text"
                  value={formCode}
                  onChange={(e) => setFormCode(e.target.value)}
                  placeholder="e.g. Art. 4.1.9 / SYM-VALVE-01"
                  required
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 font-semibold mb-1">Título / Nombre:</label>
                <input
                  type="text"
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                  placeholder="Título descriptivo..."
                  required
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 font-semibold mb-1">Descripción / Texto Normativo:</label>
                <textarea
                  rows={3}
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  placeholder="Contenido técnico detallado..."
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 font-semibold mb-1">Disciplina:</label>
                  <input
                    type="text"
                    value={formDiscipline}
                    onChange={(e) => setFormDiscipline(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white focus:outline-none focus:border-cyan-500"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 font-semibold mb-1">Estado Inicial:</label>
                  <select
                    value={formStatus}
                    onChange={(e) => setFormStatus(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white focus:outline-none"
                  >
                    <option value="active">Activo (Validado)</option>
                    <option value="to_confirm">Por Confirmar (Draft)</option>
                  </select>
                </div>
              </div>

              {activeTab === 'normative_memory' && (
                <div>
                  <label className="block text-slate-400 font-semibold mb-1">Expresión Determinística (Regla AST):</label>
                  <input
                    type="text"
                    value={formRuleExpression}
                    onChange={(e) => setFormRuleExpression(e.target.value)}
                    placeholder="e.g. clear_height_m >= 2.30"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-emerald-300 font-mono focus:outline-none"
                  />
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsCreateModalOpen(false)}
                  className="px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-bold"
                >
                  Guardar en Memoria
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: Editar Entrada */}
      {isEditModalOpen && selectedRecord && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-lg shadow-2xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Edit2 className="w-4 h-4 text-cyan-400" />
                <span>Editar Registro «{selectedRecord.code_or_identifier}»</span>
              </h3>
              <button onClick={() => setIsEditModalOpen(false)} className="text-slate-400 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSaveEdit} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 font-semibold mb-1">Título:</label>
                <input
                  type="text"
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                  required
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 font-semibold mb-1">Descripción / Texto:</label>
                <textarea
                  rows={3}
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 font-semibold mb-1">Disciplina:</label>
                  <input
                    type="text"
                    value={formDiscipline}
                    onChange={(e) => setFormDiscipline(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 font-semibold mb-1">Estado de Registro:</label>
                  <select
                    value={formStatus}
                    onChange={(e) => setFormStatus(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white focus:outline-none"
                  >
                    <option value="active">Activo</option>
                    <option value="to_confirm">Por Validar</option>
                    <option value="obsolete">Obsoleto</option>
                    <option value="archived">Archivado</option>
                  </select>
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsEditModalOpen(false)}
                  className="px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-bold"
                >
                  Actualizar Registro
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: Mantenimiento & Reindexación Transversal */}
      {isMaintenanceModalOpen && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-lg shadow-2xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Wrench className="w-4 h-4 text-cyan-400" />
                <span>Mantenimiento & Reindexación de Memorias</span>
              </h3>
              <button onClick={() => setIsMaintenanceModalOpen(false)} className="text-slate-400 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <p className="text-slate-300 leading-relaxed">
                Selecciona la rutina de mantenimiento a ejecutar sobre la base de datos y vectores de las 4 memorias:
              </p>

              <div className="space-y-2">
                <label className="flex items-center gap-2 p-2.5 rounded-lg bg-slate-950 border border-slate-800 cursor-pointer">
                  <input
                    type="radio"
                    name="maintAction"
                    value="full_maintenance"
                    checked={maintenanceAction === 'full_maintenance'}
                    onChange={(e) => setMaintenanceAction(e.target.value)}
                  />
                  <div>
                    <div className="font-bold text-white">Mantenimiento Completo</div>
                    <div className="text-[11px] text-slate-400">Limpieza de huérfanos, sincronización ontológica y reindexación.</div>
                  </div>
                </label>

                <label className="flex items-center gap-2 p-2.5 rounded-lg bg-slate-950 border border-slate-800 cursor-pointer">
                  <input
                    type="radio"
                    name="maintAction"
                    value="cleanup_orphans"
                    checked={maintenanceAction === 'cleanup_orphans'}
                    onChange={(e) => setMaintenanceAction(e.target.value)}
                  />
                  <div>
                    <div className="font-bold text-white">Limpieza de Elementos Huérfanos</div>
                    <div className="text-[11px] text-slate-400">Purga láminas y decisiones desvinculadas de documentos padre.</div>
                  </div>
                </label>

                <label className="flex items-center gap-2 p-2.5 rounded-lg bg-slate-950 border border-slate-800 cursor-pointer">
                  <input
                    type="radio"
                    name="maintAction"
                    value="reindex_vectors"
                    checked={maintenanceAction === 'reindex_vectors'}
                    onChange={(e) => setMaintenanceAction(e.target.value)}
                  />
                  <div>
                    <div className="font-bold text-white">Reconstrucción de Índices Vectoriales</div>
                    <div className="text-[11px] text-slate-400">Re-sincroniza embeddings normativos y ontológicos en Qdrant/PostgreSQL.</div>
                  </div>
                </label>
              </div>

              {maintenanceResult && (
                <div className="p-3 rounded-xl bg-emerald-950/80 border border-emerald-700 text-emerald-200 text-xs space-y-1">
                  <div className="font-bold flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span>{maintenanceResult.message}</span>
                  </div>
                  <div className="text-[11px] text-slate-300">
                    Registros procesados: {maintenanceResult.records_processed} • Reparados: {maintenanceResult.records_repaired_or_cleaned}
                  </div>
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsMaintenanceModalOpen(false)}
                  className="px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300"
                >
                  Cerrar
                </button>
                <button
                  type="button"
                  onClick={handleRunMaintenance}
                  disabled={maintenanceRunning}
                  className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-bold flex items-center gap-1.5 shadow disabled:opacity-50"
                >
                  {maintenanceRunning ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Ejecutando...</span>
                    </>
                  ) : (
                    <span>Ejecutar Mantenimiento</span>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal de Curación HITL de Simbología */}
      <SymbolCurationStudioModal
        isOpen={isSymbolStudioOpen}
        onClose={() => setIsSymbolStudioOpen(false)}
        onPromoted={() => {
          fetchOverview();
          fetchRecords();
        }}
      />
    </div>
  );
};
