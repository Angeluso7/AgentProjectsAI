import React, { useState, useEffect } from 'react';
import { Project, Discipline } from '../types';
import { FolderPlus, Edit3, X, AlertCircle, CheckCircle2, Shield, Layers, Building2, Tag } from 'lucide-react';

interface ProjectFormModalProps {
  isOpen: boolean;
  projectToEdit?: Project | null;
  onClose: () => void;
  onSubmit: (data: Partial<Project>, setAsActive: boolean) => Promise<void>;
  existingProjects?: Project[];
  onOpenProject?: (projectId: string) => void;
  onRestoreProject?: (projectId: string) => Promise<void>;
}

export const PROJECT_STAGES = [
  'Ingeniería Conceptual',
  'Ingeniería Básica',
  'Ingeniería de Detalle',
  'Factibilidad',
  'Licitación',
  'Construcción',
  'As-Built'
];

export const PROJECT_TYPES = [
  { id: 'edificacion', label: '🏢 Edificación (Residencial / Comercial)' },
  { id: 'mineria', label: '⛏️ Minería & Procesos Pesados' },
  { id: 'infraestructura', label: '🌉 Infraestructura & Vialidad' },
  { id: 'industrial', label: '🏭 Industrial & Plantas' },
  { id: 'energia', label: '⚡ Energía & Subestaciones' },
  { id: 'sanitario', label: '💧 Sanitario & Tratamiento de Aguas' },
  { id: 'otro', label: '📦 Otro tipo de proyecto' },
];

export const PROJECT_DISCIPLINES: { id: Discipline; label: string }[] = [
  { id: 'architecture', label: 'Arquitectura' },
  { id: 'structural', label: 'Estructuras' },
  { id: 'electrical', label: 'Eléctrica' },
  { id: 'mechanical', label: 'Mecánica / HVAC' },
  { id: 'plumbing', label: 'Piping / Sanitaria' },
  { id: 'fire_protection', label: 'Protección Contra Incendios' },
  { id: 'telecom', label: 'Telecomunicaciones & Control' },
  { id: 'general', label: 'Multidisciplinar / General' },
];

export const ProjectFormModal: React.FC<ProjectFormModalProps> = ({
  isOpen,
  projectToEdit,
  onClose,
  onSubmit,
  existingProjects = [],
  onOpenProject,
  onRestoreProject
}) => {
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [description, setDescription] = useState('');
  const [clientName, setClientName] = useState('');
  const [discipline, setDiscipline] = useState<Discipline>('architecture');
  const [stage, setStage] = useState<string>('Ingeniería de Detalle');
  const [projectType, setProjectType] = useState<string>('edificacion');
  const [status, setStatus] = useState<string>('active');
  const [setAsActive, setSetAsActive] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [conflictProject, setConflictProject] = useState<{ id: string; code: string; name: string; status: string; is_archived?: boolean } | null>(null);

  useEffect(() => {
    if (isOpen) {
      setError(null);
      setConflictProject(null);
      if (projectToEdit) {
        setName(projectToEdit.name || '');
        setCode(projectToEdit.code || '');
        setDescription(projectToEdit.description || '');
        setClientName(projectToEdit.client_name || '');
        setDiscipline(projectToEdit.discipline || 'architecture');
        setStage(projectToEdit.stage || projectToEdit.settings?.stage || 'Ingeniería de Detalle');
        setProjectType(projectToEdit.project_type || projectToEdit.settings?.project_type || 'edificacion');
        setStatus(projectToEdit.status || 'active');
        setSetAsActive(false);
      } else {
        setName('');
        // Sugerir código autogenerado
        const dateYear = new Date().getFullYear();
        const nextNum = String(existingProjects.length + 1).padStart(3, '0');
        setCode(`PRJ-${dateYear}-${nextNum}`);
        setDescription('');
        setClientName('');
        setDiscipline('architecture');
        setStage('Ingeniería de Detalle');
        setProjectType('edificacion');
        setStatus('active');
        setSetAsActive(true);
      }
    }
  }, [isOpen, projectToEdit, existingProjects]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setConflictProject(null);

    const trimmedName = name.trim();
    const trimmedCode = code.trim().toUpperCase();

    if (!trimmedName) {
      setError('El nombre del proyecto es obligatorio.');
      return;
    }
    if (!trimmedCode) {
      setError('El código o identificador del proyecto es obligatorio.');
      return;
    }

    // Validar duplicado de código en modo creación
    if (!projectToEdit) {
      const match = existingProjects.find((p) => p.code.trim().toUpperCase() === trimmedCode);
      if (match) {
        setError(`El código ${trimmedCode} ya existe en esta organización.`);
        setConflictProject({
          id: match.id,
          code: match.code,
          name: match.name,
          status: match.status,
          is_archived: match.status === 'archived'
        });
        return;
      }
    }

    // Validar duplicado de código en modo edición si se cambia
    if (projectToEdit) {
      const match = existingProjects.find((p) => p.id !== projectToEdit.id && p.code.trim().toUpperCase() === trimmedCode);
      if (match) {
        setError(`Ya existe otro proyecto con el código «${trimmedCode}».`);
        setConflictProject({
          id: match.id,
          code: match.code,
          name: match.name,
          status: match.status,
          is_archived: match.status === 'archived'
        });
        return;
      }
    }

    try {
      setSaving(true);
      const payload: Partial<Project> = {
        name: trimmedName,
        code: trimmedCode,
        description: description.trim() || undefined,
        client_name: clientName.trim() || undefined,
        discipline,
        stage,
        project_type: projectType,
        status,
        settings: {
          ...(projectToEdit?.settings || {}),
          stage,
          project_type: projectType,
        }
      };

      await onSubmit(payload, setAsActive);
      onClose();
    } catch (err: any) {
      const data = err.response?.data;
      let errMsg = 'Error al guardar el proyecto.';
      let conflict: any = null;

      if (data) {
        if (typeof data.detail === 'string') {
          errMsg = data.detail;
        } else if (data.detail && typeof data.detail === 'object') {
          errMsg = data.detail.message || JSON.stringify(data.detail);
          conflict = data.detail.existing_project;
        } else if (data.message) {
          errMsg = data.message;
        }
      } else if (err.message) {
        errMsg = err.message;
      }

      if (err.response?.status === 409) {
        if (!errMsg.startsWith('El código') && !errMsg.startsWith('Ya existe')) {
          errMsg = `El código ${trimmedCode} ya existe en esta organización.`;
        }
        if (!conflict) {
          const localMatch = existingProjects.find((p) => p.code.trim().toUpperCase() === trimmedCode);
          if (localMatch) {
            conflict = {
              id: localMatch.id,
              code: localMatch.code,
              name: localMatch.name,
              status: localMatch.status,
              is_archived: localMatch.status === 'archived'
            };
          }
        }
        if (conflict) {
          setConflictProject(conflict);
        }
      }

      setError(errMsg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(2, 6, 23, 0.85)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '16px',
        animation: 'fade-in 0.15s ease-out',
      }}
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: '#020617',
          borderColor: '#334155',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.9), 0 0 0 1px #334155',
          borderRadius: '16px',
          width: '100%',
          maxWidth: '680px',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Encabezado */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/80">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
              {projectToEdit ? <Edit3 className="w-5 h-5" /> : <FolderPlus className="w-5 h-5" />}
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-100">
                {projectToEdit ? 'Editar Proyecto' : 'Crear Nuevo Proyecto'}
              </h2>
              <p className="text-xs text-slate-400">
                {projectToEdit
                  ? `Modifica los metadatos y la etapa de «${projectToEdit.name}»`
                  : 'Registra un nuevo proyecto para comenzar la ingesta y auditoría'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Formulario */}
        <form onSubmit={handleSubmit} className="p-6 overflow-y-auto space-y-4 flex-1">
          {error && (
            <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-800 text-xs text-rose-300 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {conflictProject && (
            <div className="p-3.5 rounded-xl bg-slate-900/90 border border-amber-500/40 text-xs text-slate-200 space-y-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Shield className="w-4 h-4 text-amber-400 shrink-0" />
                  <span className="font-bold text-amber-300">Proyecto existente detectado en esta organización</span>
                </div>
                <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase ${
                  conflictProject.status === 'archived'
                    ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                    : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                }`}>
                  {conflictProject.status === 'archived' ? 'Archivado' : 'Activo'}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-[11px] bg-slate-950/60 p-2.5 rounded-lg border border-slate-800">
                <div>
                  <span className="text-slate-400 block text-[10px]">Nombre:</span>
                  <span className="font-semibold text-slate-100">{conflictProject.name}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px]">Código:</span>
                  <span className="font-mono text-slate-200">{conflictProject.code}</span>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2 pt-1">
                {onOpenProject && (
                  <button
                    type="button"
                    onClick={() => onOpenProject(conflictProject.id)}
                    className="px-3 py-1.5 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded-lg flex items-center gap-1.5 transition-colors cursor-pointer"
                  >
                    <FolderPlus className="w-3.5 h-3.5" />
                    <span>Abrir proyecto</span>
                  </button>
                )}
                {conflictProject.status === 'archived' && onRestoreProject && (
                  <button
                    type="button"
                    onClick={() => onRestoreProject(conflictProject.id)}
                    className="px-3 py-1.5 text-xs font-semibold text-amber-300 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 rounded-lg flex items-center gap-1.5 transition-colors cursor-pointer"
                  >
                    <span>Restaurar</span>
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => {
                    setCode('');
                    setError(null);
                    setConflictProject(null);
                  }}
                  className="px-3 py-1.5 text-xs font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors cursor-pointer"
                >
                  Usar nuevo código
                </button>
              </div>
            </div>
          )}

          {/* Fila 1: Código y Nombre */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Código / ID <span className="text-rose-400">*</span>
              </label>
              <input
                type="text"
                required
                value={code}
                onChange={(e) => {
                  setCode(e.target.value);
                  setError(null);
                  setConflictProject(null);
                }}
                placeholder="PRJ-2026-001"
                className="w-full px-3 py-2 text-xs font-mono uppercase rounded-xl bg-slate-950 border border-slate-800 text-slate-100 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Nombre del Proyecto <span className="text-rose-400">*</span>
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Ej: Edificio Los Alerces / Planta Desalinizadora"
                className="w-full px-3 py-2 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-100 focus:outline-none focus:border-blue-500 font-medium"
              />
            </div>
          </div>

          {/* Fila 2: Cliente y Tipo de Proyecto */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Cliente / Mandante
              </label>
              <input
                type="text"
                value={clientName}
                onChange={(e) => setClientName(e.target.value)}
                placeholder="Ej: Inmobiliaria Andina / Codelco"
                className="w-full px-3 py-2 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-100 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Tipo de Proyecto
              </label>
              <select
                value={projectType}
                onChange={(e) => setProjectType(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-blue-500"
              >
                {PROJECT_TYPES.map((t) => (
                  <option key={t.id} value={t.id}>{t.label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Fila 3: Disciplina Principal, Etapa Actual y Estado */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Disciplina Principal
              </label>
              <select
                value={discipline}
                onChange={(e) => setDiscipline(e.target.value as Discipline)}
                className="w-full px-3 py-2 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-blue-500"
              >
                {PROJECT_DISCIPLINES.map((d) => (
                  <option key={d.id} value={d.id}>{d.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Etapa del Proyecto <span className="text-amber-400">*</span>
              </label>
              <select
                value={stage}
                onChange={(e) => setStage(e.target.value)}
                className="w-full px-3 py-2 text-xs font-semibold rounded-xl bg-slate-950 border border-amber-600/40 text-amber-300 focus:outline-none focus:border-amber-500"
              >
                {PROJECT_STAGES.map((st) => (
                  <option key={st} value={st}>{st}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Estado
              </label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-blue-500"
              >
                <option value="active">🟢 Activo</option>
                <option value="draft">🟡 Borrador</option>
                <option value="completed">🔵 Completado</option>
                <option value="archived">📦 Archivado</option>
              </select>
            </div>
          </div>

          {/* Fila 4: Descripción */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Descripción Breve / Alcance Técnico
            </label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Detalla las características principales del proyecto, superficie estimada, normativa aplicable..."
              className="w-full px-3 py-2 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-100 focus:outline-none focus:border-blue-500 resize-none font-sans"
            />
          </div>

          {/* Checkbox: Establecer como Activo */}
          <div className="p-3 rounded-xl bg-blue-950/30 border border-blue-800/40 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <input
                type="checkbox"
                id="setAsActiveCheckbox"
                checked={setAsActive}
                onChange={(e) => setSetAsActive(e.target.checked)}
                className="w-4 h-4 rounded border-slate-700 text-blue-600 focus:ring-blue-500 bg-slate-900 cursor-pointer"
              />
              <label htmlFor="setAsActiveCheckbox" className="text-xs font-medium text-slate-200 cursor-pointer select-none">
                Establecer inmediatamente como <strong>Proyecto Activo</strong> del sistema
              </label>
            </div>
            <span className="text-[10px] text-blue-400 font-mono">Contexto Global</span>
          </div>

          {/* Botones de Acción */}
          <div className="pt-3 border-t border-slate-800 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-xl transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-5 py-2 text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 active:bg-blue-700 rounded-xl shadow-lg shadow-blue-600/30 flex items-center gap-2 transition-all disabled:opacity-50"
            >
              {saving ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Guardando...</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  <span>{projectToEdit ? 'Guardar Cambios' : 'Crear Proyecto'}</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
