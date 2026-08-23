import React, { useEffect, useState } from 'react';
import { apiService } from '../services/api';
import { MemoriesStats, Project, ReviewRun } from '../types';
import {
  FileText, ShieldAlert, CheckCircle, Brain, Database, Cpu, Layers,
  FolderKanban, ArrowRight, Sparkles, FileSearch, Building2, CheckCircle2, ChevronRight
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';

export const DashboardPage: React.FC = () => {
  const { activeProject, activeProjectId } = useProject();
  const [stats, setStats] = useState<MemoriesStats | null>(null);
  const [runs, setRuns] = useState<ReviewRun[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsData, runsData] = await Promise.all([
          apiService.getMemoriesStats().catch(() => null),
          apiService.getReviewRuns().catch(() => [])
        ]);
        setStats(statsData);
        setRuns(runsData);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  return (
    <div className="page-container">
      <div style={{ marginBottom: '20px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 800 }}>Dashboard de Control & Auditoría Híbrida</h1>
        <p style={{ color: 'var(--text-muted)', marginTop: '4px', fontSize: '14px' }}>
          Monitoreo en tiempo real de las 4 memorias persistentes, reglas determinísticas y hallazgos.
        </p>
      </div>

      {/* Tarjeta de Contexto del Proyecto Activo */}
      <div className="p-5 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900 to-blue-950/40 border border-blue-800/40 shadow-xl mb-6 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="flex items-start gap-4">
          <div className="p-3 rounded-2xl bg-blue-600/20 text-blue-400 border border-blue-500/30 shrink-0">
            <FolderKanban className="w-6 h-6" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-blue-400">Proyecto Activo en Contexto</span>
              <span className="text-slate-600">•</span>
              <span className="px-2 py-0.5 text-[10px] font-mono font-bold rounded bg-blue-950 text-blue-300 border border-blue-800">
                {activeProject ? activeProject.code : 'SIN ASIGNAR'}
              </span>
              {activeProject?.stage && (
                <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-amber-950 text-amber-300 border border-amber-800">
                  {activeProject.stage}
                </span>
              )}
            </div>
            <h2 className="text-lg font-bold text-slate-100">
              {activeProject ? activeProject.name : 'Ningún proyecto seleccionado'}
            </h2>
            {activeProject?.client_name && (
              <p className="text-xs text-slate-400 mt-0.5 flex items-center gap-1.5">
                <Building2 className="w-3.5 h-3.5 text-slate-500" />
                <span>Cliente / Mandante: <strong>{activeProject.client_name}</strong></span>
                {activeProject.discipline && (
                  <>
                    <span className="text-slate-600">•</span>
                    <span className="capitalize">Disciplina: {activeProject.discipline}</span>
                  </>
                )}
              </p>
            )}
          </div>
        </div>

        {/* Accesos Rápidos sobre el Proyecto Activo */}
        <div className="flex flex-wrap items-center gap-2.5 pt-3 lg:pt-0 border-t lg:border-t-0 border-slate-800">
          <button
            onClick={() => window.dispatchEvent(new CustomEvent('navigate-tab', { detail: { tab: 'viewer' } }))}
            className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold flex items-center gap-1.5 transition-colors border border-slate-700"
          >
            <FileSearch className="w-3.5 h-3.5 text-blue-400" />
            <span>Ver Planos</span>
          </button>
          <button
            onClick={() => window.dispatchEvent(new CustomEvent('navigate-tab', { detail: { tab: 'pipeline' } }))}
            className="px-3.5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold flex items-center gap-1.5 transition-all shadow-md shadow-blue-600/30"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>One-Click Review</span>
          </button>
          <button
            onClick={() => window.dispatchEvent(new CustomEvent('navigate-tab', { detail: { tab: 'projects' } }))}
            className="px-3 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white text-xs font-semibold flex items-center gap-1 transition-colors border border-slate-800"
            title="Administrar o alternar proyectos"
          >
            <span>Gestionar</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Tarjetas de Métricas de las 4 Memorias */}
      <div className="card-grid">
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div className="card-title">document_memory</div>
            <FileText size={18} color="var(--primary)" />
          </div>
          <div className="card-value">{stats?.document_memory?.documents_count ?? 1}</div>
          <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginTop: '6px' }}>
            {stats?.document_memory?.sheets_count ?? 1} Hojas rasterizadas a 300 DPI
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div className="card-title">normative_memory</div>
            <Database size={18} color="var(--accent)" />
          </div>
          <div className="card-value">{stats?.normative_memory?.standards_count ?? 2}</div>
          <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginTop: '6px' }}>
            {stats?.normative_memory?.clauses_count ?? 14} Artículos y criterios activos
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div className="card-title">template_memory</div>
            <Layers size={18} color="var(--warning)" />
          </div>
          <div className="card-value">{stats?.template_memory?.title_block_templates_count ?? 3}</div>
          <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginTop: '6px' }}>
            {stats?.template_memory?.symbol_libraries_count ?? 4} Librerías de simbologías
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div className="card-title">decision_memory</div>
            <ShieldAlert size={18} color="var(--danger)" />
          </div>
          <div className="card-value">{stats?.decision_memory?.findings_count ?? 1}</div>
          <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginTop: '6px' }}>
            {stats?.decision_memory?.human_feedbacks_count ?? 0} Validaciones humanas (HITL)
          </div>
        </div>
      </div>

      {/* Grid de 2 Columnas: Sesiones de Auditoría y Estado de la Arquitectura */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px' }}>
        {/* Sesiones Recientes */}
        <div className="card">
          <h2 style={{ fontSize: '16px', fontWeight: 700, marginBottom: '16px' }}>Últimas Sesiones de Auditoría</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {runs.length > 0 ? (
              runs.map((run) => (
                <div
                  key={run.id}
                  style={{
                    background: 'var(--bg-sidebar)',
                    padding: '14px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-subtle)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '14px' }}>{run.run_name}</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginTop: '2px' }}>
                      {run.rules_applied_count} Reglas aplicadas • {run.execution_time_sec}s
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <span className="badge badge-high">{run.findings_count} Hallazgos</span>
                    <span className="badge badge-success">Completado</span>
                  </div>
                </div>
              ))
            ) : (
              <div style={{ color: 'var(--text-dim)', fontSize: '13px' }}>
                No hay auditorías registradas todavía. Puedes lanzar una desde la sección Triage & Revisión.
              </div>
            )}
          </div>
        </div>

        {/* Estado de la Arquitectura Híbrida */}
        <div className="card">
          <h2 style={{ fontSize: '16px', fontWeight: 700, marginBottom: '16px' }}>Flujo Híbrido Activo</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Cpu size={16} color="var(--primary)" />
              <span><strong>Percepción:</strong> OCR + YOLO v11</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Database size={16} color="var(--accent)" />
              <span><strong>Persistencia:</strong> PostgreSQL + PostGIS</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <ShieldAlert size={16} color="var(--warning)" />
              <span><strong>Verificación:</strong> Reglas Determinísticas</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Brain size={16} color="var(--success)" />
              <span><strong>Aprendizaje:</strong> Active Learning (DVC/MLflow)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
