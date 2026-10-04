import React, { useEffect, useState } from 'react';
import { apiService } from '../services/api';
import { ExecutiveDashboardSummary } from '../types';
import {
  LayoutDashboard, FolderKanban, Sparkles, FileSearch, Building2,
  CheckCircle2, AlertTriangle, ShieldAlert, Cpu, Activity, Clock,
  ArrowRight, ShieldCheck, ChevronRight, Zap, RefreshCw, Layers,
  FileText, CheckCircle, Database, Search, Inbox, Award
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';

export const DashboardPage: React.FC = () => {
  const { activeProject, activeProjectId } = useProject();
  const [summary, setSummary] = useState<ExecutiveDashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchDashboardData = async () => {
    try {
      setRefreshing(true);
      const data = await apiService.getExecutiveDashboardSummary(activeProjectId || undefined);
      setSummary(data);
    } catch (err) {
      console.error('Error fetching executive dashboard summary:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, [activeProjectId]);

  const navigateToTab = (tab: string) => {
    window.dispatchEvent(new CustomEvent('navigate-tab', { detail: { tab } }));
  };

  const metrics = summary?.project_metrics;
  const agentHealth = summary?.agent_health;
  const activities = summary?.recent_activities || [];
  const alerts = summary?.alerts_and_recommendations || [];
  const shortcuts = summary?.quick_shortcuts || [];

  return (
    <div className="page-container space-y-6 animate-in fade-in duration-300">
      {/* Header Superior del Dashboard */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-blue-600/20 text-blue-400 border border-blue-500/30">
              <LayoutDashboard className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-2xl font-black text-white tracking-tight">Dashboard Ejecutivo & Control Operativo</h1>
              <p className="text-xs text-slate-400 mt-0.5">
                Monitoreo de alto nivel del proyecto activo y salud global del Agente Híbrido.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchDashboardData}
            disabled={refreshing}
            className="px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-300 text-xs font-semibold flex items-center gap-2 border border-slate-800 transition-colors"
            title="Refrescar métricas ejecutivas"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-cyan-400' : 'text-slate-400'}`} />
            <span>{refreshing ? 'Actualizando...' : 'Refrescar'}</span>
          </button>

          <button
            onClick={() => navigateToTab('pipeline')}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs font-bold flex items-center gap-2 shadow-lg shadow-blue-600/20 transition-all active:scale-95"
          >
            <Sparkles className="w-4 h-4 text-cyan-200" />
            <span>One-Click Review</span>
          </button>
        </div>
      </div>

      {/* 1. Tarjeta Ejecutiva del Proyecto Activo */}
      <div className="p-5 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900 to-blue-950/40 border border-blue-800/40 shadow-xl flex flex-col lg:flex-row lg:items-center justify-between gap-6">
        <div className="flex items-start gap-4">
          <div className="p-3.5 rounded-2xl bg-blue-600/20 text-blue-400 border border-blue-500/30 shrink-0">
            <FolderKanban className="w-7 h-7" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2 mb-1.5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-blue-400">Proyecto Activo en Revisión</span>
              <span className="text-slate-600">•</span>
              <span className="px-2 py-0.5 text-[11px] font-mono font-bold rounded bg-blue-950 text-blue-300 border border-blue-800">
                {metrics?.project_code || (activeProject ? activeProject.code : 'PRJ-DEMO')}
              </span>
              <span className="px-2.5 py-0.5 text-[11px] font-bold rounded bg-amber-950/80 text-amber-300 border border-amber-800/70">
                {metrics?.stage || activeProject?.stage || 'Ingeniería de Detalle'}
              </span>
            </div>
            <h2 className="text-xl font-bold text-slate-100">
              {metrics?.project_name || activeProject?.name || 'Planta Industrial Central - Fase 2'}
            </h2>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400 mt-1">
              <span className="flex items-center gap-1.5">
                <Building2 className="w-3.5 h-3.5 text-slate-500" />
                <span>Cliente: <strong>{metrics?.client_name || activeProject?.client_name || 'Consorcio Mandante'}</strong></span>
              </span>
              <span className="text-slate-600">•</span>
              <span>Disciplina: <strong className="capitalize text-slate-300">{metrics?.discipline || activeProject?.discipline || 'Multidisciplinario'}</strong></span>
            </div>
          </div>
        </div>

        {/* Cobertura & Barra de Avance */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 bg-slate-950/60 p-4 rounded-xl border border-slate-800 lg:min-w-[340px]">
          <div className="flex-1 w-full">
            <div className="flex items-center justify-between text-xs font-semibold mb-1.5">
              <span className="text-slate-400">Avance de Procesamiento</span>
              <span className="text-cyan-400 font-mono font-bold">{metrics?.progress_percentage ?? 100}%</span>
            </div>
            <div className="w-full h-2.5 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full transition-all duration-500"
                style={{ width: `${Math.min(100, Math.max(5, metrics?.progress_percentage ?? 100))}%` }}
              />
            </div>
            <div className="flex items-center justify-between text-[11px] text-slate-400 mt-1.5">
              <span>{metrics?.documents_processed ?? 0} de {metrics?.documents_total ?? 0} Docs procesados</span>
              <span>{metrics?.sheets_rasterized ?? 0} Láminas 300 DPI</span>
            </div>
          </div>

          <button
            onClick={() => navigateToTab('projects')}
            className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold flex items-center gap-1.5 transition-colors border border-slate-700 shrink-0 self-stretch sm:self-auto justify-center"
            title="Cambiar o gestionar proyectos"
          >
            <span>Cambiar</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* 2. Cuatro KPIs Ejecutivos del Proyecto */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Documentos y Láminas */}
        <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800/80 shadow-md flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400">Documentos & Planos</span>
            <div className="p-2 rounded-lg bg-blue-600/20 text-blue-400">
              <FileText className="w-4 h-4" />
            </div>
          </div>
          <div className="my-2">
            <div className="text-2xl font-black text-white font-mono">
              {metrics?.documents_total ?? 0} <span className="text-xs font-normal text-slate-400 font-sans">docs</span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              {metrics?.sheets_total ?? 0} láminas en total ({metrics?.sheets_rasterized ?? 0} rasterizadas a 300 DPI)
            </p>
          </div>
          <button
            onClick={() => navigateToTab('sources')}
            className="text-[11px] text-blue-400 hover:text-blue-300 font-semibold flex items-center gap-1 mt-1 transition-colors"
          >
            <span>Gestionar archivos</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        </div>

        {/* Reglas Activas & Cumplimiento */}
        <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800/80 shadow-md flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400">Reglas & Cumplimiento</span>
            <div className="p-2 rounded-lg bg-emerald-600/20 text-emerald-400">
              <ShieldCheck className="w-4 h-4" />
            </div>
          </div>
          <div className="my-2">
            <div className="text-2xl font-black text-white font-mono">
              {metrics?.active_rules_count ?? 0} <span className="text-xs font-normal text-slate-400 font-sans">reglas</span>
            </div>
            <p className="text-xs text-emerald-400 mt-0.5 flex items-center gap-1 font-medium">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Score de Cumplimiento: {metrics?.compliance_score ?? 95.0}%</span>
            </p>
          </div>
          <button
            onClick={() => navigateToTab('rules')}
            className="text-[11px] text-emerald-400 hover:text-emerald-300 font-semibold flex items-center gap-1 mt-1 transition-colors"
          >
            <span>Ver motor de reglas QA/QC</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        </div>

        {/* Hallazgos Totales y Críticos */}
        <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800/80 shadow-md flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400">Hallazgos de Auditoría</span>
            <div className="p-2 rounded-lg bg-rose-600/20 text-rose-400">
              <ShieldAlert className="w-4 h-4" />
            </div>
          </div>
          <div className="my-2">
            <div className="text-2xl font-black text-white font-mono flex items-center gap-2">
              <span>{metrics?.findings_total ?? 0}</span>
              {(metrics?.findings_critical ?? 0) > 0 && (
                <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-rose-950 text-rose-300 border border-rose-700 animate-pulse">
                  {metrics?.findings_critical} Críticos
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              {metrics?.findings_open ?? 0} Abiertos • {metrics?.findings_resolved ?? 0} Resueltos
            </p>
          </div>
          <button
            onClick={() => navigateToTab('review')}
            className="text-[11px] text-rose-400 hover:text-rose-300 font-semibold flex items-center gap-1 mt-1 transition-colors"
          >
            <span>Ir a Triage & Revisión</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        </div>

        {/* Validaciones Humanas HITL */}
        <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800/80 shadow-md flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400">Validaciones HITL</span>
            <div className="p-2 rounded-lg bg-purple-600/20 text-purple-400">
              <Activity className="w-4 h-4" />
            </div>
          </div>
          <div className="my-2">
            <div className="text-2xl font-black text-white font-mono">
              {metrics?.pending_validations_count ?? 0} <span className="text-xs font-normal text-slate-400 font-sans">pendientes</span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Cobertura Informacional: <strong>{metrics?.information_coverage_score ?? 85}%</strong>
            </p>
          </div>
          <button
            onClick={() => navigateToTab('review')}
            className="text-[11px] text-purple-400 hover:text-purple-300 font-semibold flex items-center gap-1 mt-1 transition-colors"
          >
            <span>Confirmar hallazgos</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* 3. Panel de Última Ejecución de One-Click Review */}
      {metrics?.last_review_run && (
        <div className="p-4 rounded-2xl bg-gradient-to-r from-indigo-950/40 via-slate-900 to-slate-900 border border-indigo-800/40 shadow-lg flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="p-2.5 rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
              <Sparkles className="w-5 h-5 text-indigo-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wider text-indigo-400">Última Auditoría One-Click Review</span>
                <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-emerald-950 text-emerald-300 border border-emerald-700">
                  {metrics.last_review_run.status}
                </span>
              </div>
              <p className="text-sm font-bold text-slate-200 mt-0.5">
                {metrics.last_review_run.run_name}
              </p>
              <div className="flex items-center gap-3 text-xs text-slate-400 mt-1">
                <span>{metrics.last_review_run.rules_applied_count} Reglas aplicadas</span>
                <span>•</span>
                <span>{metrics.last_review_run.findings_count} Hallazgos detectados</span>
                <span>•</span>
                <span>Duración: {metrics.last_review_run.execution_time_sec}s</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => navigateToTab('reports')}
              className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center gap-1.5 transition-colors border border-slate-700"
            >
              <FileText className="w-3.5 h-3.5 text-blue-400" />
              <span>Ver Informe</span>
            </button>
            <button
              onClick={() => navigateToTab('pipeline')}
              className="px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold flex items-center gap-1.5 transition-all shadow-md shadow-indigo-600/30"
            >
              <span>Relanzar Auditoría</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* 4. Salud Operativa del Agente IA & Motores */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Motores IA en Vivo (Columna 2/3) */}
        <div className="lg:col-span-2 p-5 rounded-2xl bg-slate-900 border border-slate-800 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2.5">
              <Zap className="w-5 h-5 text-amber-400" />
              <div>
                <h3 className="text-sm font-bold text-white">Salud Operativa de Motores IA</h3>
                <p className="text-xs text-slate-400">Latencia en tiempo real y disponibilidad de servicios de inferencia.</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-bold rounded-full bg-emerald-950 text-emerald-300 border border-emerald-700">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                Uptime {agentHealth?.system_uptime || '99.98%'}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {agentHealth?.engines?.map((eng) => (
              <div
                key={eng.engine_id}
                className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 hover:border-slate-700 transition-all flex flex-col justify-between"
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-bold text-slate-200 truncate">{eng.name}</span>
                  <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-emerald-950 text-emerald-300 border border-emerald-800 font-mono">
                    {eng.latency_ms}ms
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 line-clamp-2 leading-relaxed">
                  {eng.description}
                </p>
                <div className="mt-2.5 pt-2 border-t border-slate-800/60 flex items-center justify-between text-[10px] text-slate-400 font-mono">
                  <span className="capitalize">Categoría: {eng.category}</span>
                  <span className="text-emerald-400 font-bold">● {eng.status.toUpperCase()}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Estadísticas de background jobs */}
          <div className="p-3 rounded-xl bg-slate-950/90 border border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2 text-slate-400">
              <Activity className="w-4 h-4 text-cyan-400" />
              <span>Jobs en Background:</span>
            </div>
            <div className="flex items-center gap-4 font-mono font-bold">
              <span className="text-cyan-300">{agentHealth?.jobs_summary?.running ?? 0} en ejecución</span>
              <span className="text-slate-400">•</span>
              <span className="text-amber-300">{agentHealth?.jobs_summary?.queued ?? 0} en cola</span>
              <span className="text-slate-400">•</span>
              <span className="text-emerald-300">{agentHealth?.jobs_summary?.completed ?? 0} completados</span>
              <span className="text-slate-400">•</span>
              <span className="text-rose-400">{agentHealth?.jobs_summary?.failed ?? 0} fallidos</span>
            </div>
            <button
              onClick={() => navigateToTab('jobs')}
              className="text-[11px] text-blue-400 hover:text-blue-300 font-semibold underline"
            >
              Ver cola de jobs
            </button>
          </div>
        </div>

        {/* Alertas y Acciones Recomendadas (Columna 1/3) */}
        <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 shadow-xl flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-amber-400" />
                <h3 className="text-sm font-bold text-white">Alertas & Recomendaciones</h3>
              </div>
              <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-slate-800 text-slate-300">
                {alerts.length} activas
              </span>
            </div>

            <div className="space-y-2.5">
              {alerts.map((alert) => (
                <div
                  key={alert.id}
                  className={`p-3 rounded-xl border text-xs space-y-2 transition-all ${
                    alert.severity === 'critical'
                      ? 'bg-rose-950/40 border-rose-800/80 text-rose-200'
                      : alert.severity === 'high'
                      ? 'bg-amber-950/40 border-amber-800/80 text-amber-200'
                      : 'bg-slate-950 border-slate-800 text-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold">{alert.title}</span>
                    <span className="text-[10px] uppercase font-mono font-bold px-1.5 py-0.5 rounded bg-black/40">
                      {alert.severity}
                    </span>
                  </div>
                  <p className="text-[11px] leading-relaxed text-slate-300">
                    {alert.message}
                  </p>
                  <button
                    onClick={() => navigateToTab(alert.action_target_tab)}
                    className="inline-flex items-center gap-1.5 text-[11px] font-bold text-cyan-400 hover:text-cyan-300 underline mt-1"
                  >
                    <span>{alert.action_label}</span>
                    <ArrowRight className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="pt-3 border-t border-slate-800/80 text-[11px] text-slate-400 flex items-center justify-between">
            <span>Confianza Promedio: <strong>{agentHealth?.average_confidence ?? 94.8}%</strong></span>
            <span>Precedentes: <strong>{agentHealth?.precedents_applied_count ?? 0}</strong></span>
          </div>
        </div>
      </div>

      {/* 5. Actividad Reciente del Agente y Atajos Operativos */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Stream de Actividades Recientes (2/3) */}
        <div className="lg:col-span-2 p-5 rounded-2xl bg-slate-900 border border-slate-800 shadow-xl space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <Clock className="w-5 h-5 text-blue-400" />
              <h3 className="text-sm font-bold text-white">Actividad Reciente del Agente</h3>
            </div>
            <span className="text-xs text-slate-400">Eventos de auditoría, intake y feedback humano</span>
          </div>

          <div className="space-y-2.5">
            {activities.length > 0 ? (
              activities.map((act) => (
                <div
                  key={act.id}
                  className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 flex items-center justify-between gap-4"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className={`p-2 rounded-lg shrink-0 ${
                      act.severity === 'success' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' :
                      act.severity === 'warning' ? 'bg-amber-950 text-amber-400 border border-amber-800' :
                      'bg-blue-950 text-blue-400 border border-blue-800'
                    }`}>
                      <Activity className="w-4 h-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-xs font-bold text-slate-200 truncate">{act.title}</div>
                      <div className="text-[11px] text-slate-400 truncate">{act.description}</div>
                    </div>
                  </div>

                  <div className="text-right shrink-0 text-[10px] text-slate-500 font-mono">
                    <div>{new Date(act.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                    <div className="text-slate-400">{act.user_name || 'Agente'}</div>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-xs text-slate-500 text-center py-6">
                No hay actividades recientes registradas.
              </div>
            )}
          </div>
        </div>

        {/* Atajos Operativos Clave (1/3) */}
        <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 shadow-xl space-y-3 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 border-b border-slate-800 pb-3 mb-3">
              <Zap className="w-5 h-5 text-cyan-400" />
              <h3 className="text-sm font-bold text-white">Atajos Operativos</h3>
            </div>

            <div className="space-y-2">
              {shortcuts.map((sc) => (
                <button
                  key={sc.id}
                  onClick={() => navigateToTab(sc.target_tab)}
                  className={`w-full p-3 rounded-xl border text-left flex items-center justify-between transition-all group ${
                    sc.variant === 'primary'
                      ? 'bg-blue-600/10 hover:bg-blue-600/20 border-blue-700/60 text-blue-200'
                      : 'bg-slate-950/70 hover:bg-slate-800/80 border-slate-800 text-slate-300'
                  }`}
                >
                  <div>
                    <div className="text-xs font-bold text-white group-hover:text-cyan-300 transition-colors">
                      {sc.title}
                    </div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      {sc.description}
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-white group-hover:translate-x-0.5 transition-all" />
                </button>
              ))}
            </div>
          </div>

          <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-[11px] text-slate-400">
            <span>Para administración, mantenimiento o auditoría de registros de memoria, accede a la consola dedicada de </span>
            <button
              onClick={() => navigateToTab('memories')}
              className="text-cyan-400 hover:text-cyan-300 font-bold underline ml-1 inline-flex items-center gap-0.5"
            >
              <span>Las 4 Memorias</span>
              <ArrowRight className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
