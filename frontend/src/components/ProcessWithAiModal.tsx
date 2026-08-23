import React, { useState } from 'react';
import {
  X, Sparkles, Globe, FileText, ArrowRight, ArrowLeft, Search,
  ShieldAlert, BookOpen, Layers, CheckCircle2, AlertCircle,
  HelpCircle, Compass, Lightbulb, ExternalLink
} from 'lucide-react';
import { apiService } from '../services/api';
import { BASE_DISCIPLINES } from '../pages/SourcesPage';

interface ProcessWithAiModalProps {
  isOpen: boolean;
  initialTitle?: string;
  initialDiscipline?: string;
  initialDocType?: string;
  initialAuthority?: string;
  initialTextContent?: string;
  initialSourceAssetId?: string;
  availableDisciplines?: string[];
  onClose: () => void;
  onExtractionCreated: (extractionId: string) => void;
}

type AiProcessStep = 'select_mode' | 'form_document' | 'form_web';

const QUICK_RESEARCH_PROMPTS = [
  {
    title: 'Accesibilidad Universal OGUC',
    prompt: 'Investigar criterios de accesibilidad universal, rampas, anchos de puertas y pasillos según OGUC',
    discipline: 'Arquitectura',
  },
  {
    title: 'Vías y Escaleras de Evacuación',
    prompt: 'Requisitos de diseño, anchos mínimos y puertas de escape para escaleras de evacuación',
    discipline: 'Arquitectura',
  },
  {
    title: 'Resistencia al Fuego (Muros Cortafuego)',
    prompt: 'Exigencias de resistencia al fuego F-60 / F-120 para muros cortafuego y elementos estructurales',
    discipline: 'Estructuras',
  },
  {
    title: 'Instalaciones Sanitarias (RIDAA)',
    prompt: 'Criterios de dimensionamiento de redes de agua potable, alcantarillado y ventilaciones según RIDAA',
    discipline: 'Mecánica',
  },
  {
    title: 'Cálculo Sísmico NCh433',
    prompt: 'Parámetros de diseño sísmico de edificios, factores de modificación de respuesta y derivas según NCh433',
    discipline: 'Estructuras',
  },
  {
    title: 'Instalaciones Eléctricas RIC / SEC',
    prompt: 'Pliegos técnicos normativos RIC para tableros eléctricos, canalizaciones y protecciones diferenciales SEC',
    discipline: 'Eléctrica',
  },
];

export const ProcessWithAiModal: React.FC<ProcessWithAiModalProps> = ({
  isOpen,
  initialTitle = 'Ordenanza General de Urbanismo y Construcciones (OGUC)',
  initialDiscipline = 'Arquitectura',
  initialDocType = 'norma',
  initialAuthority = 'MINVU',
  initialTextContent = '',
  initialSourceAssetId,
  availableDisciplines = BASE_DISCIPLINES,
  onClose,
  onExtractionCreated,
}) => {
  const [step, setStep] = useState<AiProcessStep>('select_mode');
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Formulario Documento
  const [docTitle, setDocTitle] = useState(initialTitle);
  const [docType, setDocType] = useState(initialDocType);
  const [docDiscipline, setDocDiscipline] = useState(initialDiscipline);
  const [docAuthority, setDocAuthority] = useState(initialAuthority);
  const [docTextContent, setDocTextContent] = useState(initialTextContent);

  // Formulario Investigación Web
  const [webPrompt, setWebPrompt] = useState('Investigar criterios de accesibilidad universal para edificios residenciales');
  const [webDiscipline, setWebDiscipline] = useState(initialDiscipline);
  const [webDocType, setWebDocType] = useState('norma');
  const [webAuthority, setWebAuthority] = useState('MINVU / Web Research');
  const [webFocusAreas, setWebFocusAreas] = useState<string>('accesibilidad, rampas, anchos_minimos, puertas');

  if (!isOpen) return null;

  const handleResetAndClose = () => {
    setStep('select_mode');
    setError(null);
    onClose();
  };

  // Submit Opción 1: Documento
  const handleSubmitDocument = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!docTitle.trim()) return;

    setProcessing(true);
    setError(null);
    try {
      const res = await apiService.processDocumentWithAi({
        title: docTitle.trim(),
        document_type: docType,
        discipline: docDiscipline,
        authority: docAuthority.trim() || undefined,
        text_content: docTextContent.trim() || undefined,
        source_asset_id: initialSourceAssetId || undefined,
      });
      handleResetAndClose();
      onExtractionCreated(res.id);
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || 'Error al procesar el documento con IA.');
    } finally {
      setProcessing(false);
    }
  };

  // Submit Opción 2: Búsquedas en Internet
  const handleSubmitWebResearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!webPrompt.trim()) return;

    setProcessing(true);
    setError(null);
    try {
      const focusList = webFocusAreas
        .split(',')
        .map((f) => f.trim())
        .filter((f) => f.length > 0);

      const res = await apiService.processWebResearch({
        search_prompt: webPrompt.trim(),
        discipline: webDiscipline,
        document_type: webDocType,
        authority: webAuthority.trim() || undefined,
        focus_areas: focusList.length > 0 ? focusList : undefined,
      });
      handleResetAndClose();
      onExtractionCreated(res.id);
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || 'Error al ejecutar investigación en Internet con IA.');
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/85 backdrop-blur-sm p-4 animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
    >
      <div className="relative w-full max-w-3xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        
        {/* Encabezado */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/70">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-teal-500/10 text-teal-400 border border-teal-500/20">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-slate-100">
                  Procesar Fuentes & Incorporar Conocimiento con IA
                </h2>
                <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full bg-teal-950 text-teal-300 border border-teal-800">
                  Asistido por IA
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                {step === 'select_mode' && 'Paso 1: Selecciona el método de generación y procedencia de la información'}
                {step === 'form_document' && 'Paso 2: Configura el análisis y extracción estructurada desde el documento'}
                {step === 'form_web' && 'Paso 2: Define el tema de investigación técnica y búsqueda en Internet'}
              </p>
            </div>
          </div>
          <button
            onClick={handleResetAndClose}
            className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Cuerpo del Modal */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          
          {error && (
            <div className="p-3.5 rounded-xl bg-rose-950/50 border border-rose-800/80 text-rose-300 text-xs flex items-center gap-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          {/* ========================================================= */}
          {/* PASO 1: SELECCIÓN DE ESTRATEGIA (DOCUMENTO vs INTERNET) */}
          {/* ========================================================= */}
          {step === 'select_mode' && (
            <div className="space-y-4">
              <div className="text-center max-w-lg mx-auto mb-6">
                <h3 className="text-sm font-semibold text-slate-200">
                  ¿Cómo deseas que la IA genere y estructure el conocimiento?
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Ambas opciones procesarán la información y la presentarán en el panel interactivo de revisión antes de incorporar reglas definitivas.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                
                {/* TARJETA 1: EN BASE AL DOCUMENTO */}
                <button
                  type="button"
                  onClick={() => setStep('form_document')}
                  className="flex flex-col text-left p-5 rounded-2xl bg-gradient-to-br from-slate-900 via-slate-900 to-teal-950/30 border-2 border-slate-800 hover:border-teal-500/70 hover:shadow-lg hover:shadow-teal-950/40 transition-all group"
                >
                  <div className="flex items-center justify-between w-full mb-3">
                    <div className="p-2.5 rounded-xl bg-teal-500/10 text-teal-400 border border-teal-500/20 group-hover:scale-110 transition-transform">
                      <FileText className="w-6 h-6" />
                    </div>
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-teal-900/60 text-teal-300 border border-teal-700">
                      Prioridad Alta
                    </span>
                  </div>

                  <h4 className="text-sm font-bold text-slate-100 group-hover:text-teal-300 transition-colors flex items-center gap-1.5">
                    Opción 1: Generar en base al documento
                    <ArrowRight className="w-4 h-4 opacity-0 group-hover:opacity-100 -translate-x-1 group-hover:translate-x-0 transition-all text-teal-400" />
                  </h4>
                  
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed flex-1">
                    Analiza un archivo cargado o fragmento oficial. La IA ejecuta OCR, desglosa capítulos, artículos, tablas, figuras y formula reglas técnicas oficiales validadas.
                  </p>

                  <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
                    <span className="flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5 text-teal-400" /> Origen: Documento Interno
                    </span>
                    <span className="text-slate-300 font-medium group-hover:underline">Configurar →</span>
                  </div>
                </button>

                {/* TARJETA 2: EN BASE A BÚSQUEDAS EN INTERNET */}
                <button
                  type="button"
                  onClick={() => setStep('form_web')}
                  className="flex flex-col text-left p-5 rounded-2xl bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950/30 border-2 border-slate-800 hover:border-indigo-500/70 hover:shadow-lg hover:shadow-indigo-950/40 transition-all group"
                >
                  <div className="flex items-center justify-between w-full mb-3">
                    <div className="p-2.5 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 group-hover:scale-110 transition-transform">
                      <Globe className="w-6 h-6" />
                    </div>
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-900/60 text-indigo-300 border border-indigo-700">
                      Apoyo / Investigación
                    </span>
                  </div>

                  <h4 className="text-sm font-bold text-slate-100 group-hover:text-indigo-300 transition-colors flex items-center gap-1.5">
                    Opción 2: Búsquedas en Internet
                    <ArrowRight className="w-4 h-4 opacity-0 group-hover:opacity-100 -translate-x-1 group-hover:translate-x-0 transition-all text-indigo-400" />
                  </h4>
                  
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed flex-1">
                    Investiga externamente un tema, norma, decreto o manual mediante un prompt temático. Recupera referencias normativas, tablas y propone reglas de apoyo técnico.
                  </p>

                  <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
                    <span className="flex items-center gap-1">
                      <ShieldAlert className="w-3.5 h-3.5 text-amber-400" /> Validación Humana Reforzada
                    </span>
                    <span className="text-slate-300 font-medium group-hover:underline">Investigar →</span>
                  </div>
                </button>

              </div>

              {/* Nota de Gobernanza Institucional */}
              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800/80 flex items-start gap-3">
                <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                <div className="text-xs text-slate-300 leading-relaxed">
                  <span className="font-semibold text-slate-100">Regla Obligatoria de Gobernanza:</span> Toda información recopilada en Internet se clasifica como <em>Contenido de Apoyo e Investigación</em> y nunca entrará de forma ciega como regla definitiva. Requiere validación y aprobación explícita en el panel de revisión.
                </div>
              </div>
            </div>
          )}

          {/* ========================================================= */}
          {/* PASO 2A: FORMULARIO GENERACIÓN EN BASE AL DOCUMENTO */}
          {/* ========================================================= */}
          {step === 'form_document' && (
            <form id="ai-document-form" onSubmit={handleSubmitDocument} className="space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <button
                  type="button"
                  onClick={() => setStep('select_mode')}
                  className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1 font-medium transition-colors"
                >
                  <ArrowLeft className="w-3.5 h-3.5" /> Volver a selección de opción
                </button>
                <span className="text-xs font-semibold text-teal-400 flex items-center gap-1">
                  <FileText className="w-3.5 h-3.5" /> Modo: Documento Interno
                </span>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Título del Documento / Norma <span className="text-rose-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={docTitle}
                  onChange={(e) => setDocTitle(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-200 focus:outline-none focus:border-teal-500"
                  placeholder="Ej: Ordenanza General de Urbanismo y Construcciones (OGUC) - Título 4"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Tipo de Documento
                  </label>
                  <select
                    value={docType}
                    onChange={(e) => setDocType(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-teal-500"
                  >
                    <option value="norma">Norma / Ordenanza</option>
                    <option value="decreto">Decreto Supremo</option>
                    <option value="manual">Manual Técnico</option>
                    <option value="reglamento">Reglamento</option>
                    <option value="guia">Guía de Diseño</option>
                    <option value="ficha_tecnica">Ficha Técnica</option>
                    <option value="otro">Otro Documento</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Disciplina
                  </label>
                  <select
                    value={docDiscipline}
                    onChange={(e) => setDocDiscipline(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-teal-500"
                  >
                    {availableDisciplines.map((d) => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Autoridad / Regulador
                  </label>
                  <input
                    type="text"
                    value={docAuthority}
                    onChange={(e) => setDocAuthority(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-200 focus:outline-none focus:border-teal-500"
                    placeholder="Ej: MINVU, SEC, MOP"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Texto o Contenido del Documento (Opcional si se utiliza pipeline de archivo)
                </label>
                <textarea
                  rows={4}
                  value={docTextContent}
                  onChange={(e) => setDocTextContent(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 focus:outline-none focus:border-teal-500 font-mono leading-relaxed"
                  placeholder="Pega aquí el texto normativo, artículos, decretos o déjalo vacío para usar la síntesis asistida inteligente..."
                />
              </div>

              <div className="p-3 rounded-xl bg-teal-950/30 border border-teal-800/40 text-[11px] text-teal-200 flex items-center gap-2">
                <Lightbulb className="w-4 h-4 text-teal-400 shrink-0" />
                <span>La IA identificará reglas con prioridad alta, clasificará artículos y estructurará tablas y figuras en la Base de Conocimiento operativa.</span>
              </div>
            </form>
          )}

          {/* ========================================================= */}
          {/* PASO 2B: FORMULARIO BÚSQUEDA E INVESTIGACIÓN EN INTERNET */}
          {/* ========================================================= */}
          {step === 'form_web' && (
            <form id="ai-web-form" onSubmit={handleSubmitWebResearch} className="space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <button
                  type="button"
                  onClick={() => setStep('select_mode')}
                  className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1 font-medium transition-colors"
                >
                  <ArrowLeft className="w-3.5 h-3.5" /> Volver a selección de opción
                </button>
                <span className="text-xs font-semibold text-indigo-400 flex items-center gap-1">
                  <Globe className="w-3.5 h-3.5" /> Modo: Búsqueda en Internet
                </span>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Prompt o Tema de Investigación <span className="text-rose-400">*</span>
                </label>
                <div className="relative">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
                  <textarea
                    rows={2}
                    required
                    value={webPrompt}
                    onChange={(e) => setWebPrompt(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-3.5 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 leading-relaxed"
                    placeholder="Ej: Investigar criterios de distanciamiento y antejardines según OGUC para condominios residenciales..."
                  />
                </div>
              </div>

              {/* Sugerencias Rápidas de Temas */}
              <div>
                <span className="text-[11px] font-medium text-slate-400 block mb-1.5">
                  Sugerencias Rápidas de Investigación Normativa:
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {QUICK_RESEARCH_PROMPTS.map((q, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => {
                        setWebPrompt(q.prompt);
                        setWebDiscipline(q.discipline);
                      }}
                      className="text-[11px] px-2.5 py-1 rounded-lg bg-slate-800/80 hover:bg-indigo-900/50 hover:text-indigo-200 border border-slate-700 hover:border-indigo-700/60 text-slate-300 transition-all text-left flex items-center gap-1.5"
                    >
                      <Sparkles className="w-3 h-3 text-indigo-400 shrink-0" />
                      <span>{q.title}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Disciplina Objetivo
                  </label>
                  <select
                    value={webDiscipline}
                    onChange={(e) => setWebDiscipline(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                  >
                    {availableDisciplines.map((d) => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Tipo de Norma / Documento
                  </label>
                  <select
                    value={webDocType}
                    onChange={(e) => setWebDocType(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                  >
                    <option value="norma">Norma Oficial</option>
                    <option value="manual">Manual Técnico</option>
                    <option value="reglamento">Reglamento</option>
                    <option value="decreto">Decreto</option>
                    <option value="guia">Guía de Buenas Prácticas</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Autoridad / Regulador Sugerido
                  </label>
                  <input
                    type="text"
                    value={webAuthority}
                    onChange={(e) => setWebAuthority(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                    placeholder="Ej: MINVU / Web Research"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Áreas de Enfoque / Palabras Clave (Separadas por comas)
                </label>
                <input
                  type="text"
                  value={webFocusAreas}
                  onChange={(e) => setWebFocusAreas(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                  placeholder="Ej: accesibilidad, rampas, pasillos, ancho_util, pendientes"
                />
              </div>

              <div className="p-3.5 rounded-xl bg-amber-950/30 border border-amber-800/40 text-[11px] text-amber-200 flex items-start gap-2.5">
                <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold text-amber-300">Trazabilidad y Gobernanza:</span> Cada elemento generado guardará la cita de procedencia web y se marcará como <em>Regla Propuesta / Apoyo</em>. Deberás aceptarla o editarla en el panel de revisión final.
                </div>
              </div>
            </form>
          )}

        </div>

        {/* Footer con Acciones */}
        <div className="px-6 py-4 border-t border-slate-800 bg-slate-950/70 flex items-center justify-between">
          <button
            type="button"
            onClick={handleResetAndClose}
            disabled={processing}
            className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-xl transition-colors disabled:opacity-50"
          >
            Cancelar
          </button>

          {step === 'select_mode' && (
            <span className="text-xs text-slate-400">
              Selecciona una de las dos tarjetas superiores para continuar
            </span>
          )}

          {step === 'form_document' && (
            <button
              type="submit"
              form="ai-document-form"
              disabled={processing || !docTitle.trim()}
              className="px-5 py-2 bg-gradient-to-r from-teal-500 to-emerald-600 hover:from-teal-400 hover:to-emerald-500 text-slate-950 font-bold text-xs rounded-xl shadow-lg shadow-teal-950/50 transition-all flex items-center gap-2 disabled:opacity-50"
            >
              {processing ? (
                <>
                  <Sparkles className="w-4 h-4 animate-spin text-slate-950" />
                  <span>Procesando Documento...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 text-slate-950" />
                  <span>Iniciar Procesamiento de Documento</span>
                </>
              )}
            </button>
          )}

          {step === 'form_web' && (
            <button
              type="submit"
              form="ai-web-form"
              disabled={processing || !webPrompt.trim()}
              className="px-5 py-2 bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-400 hover:to-purple-500 text-white font-bold text-xs rounded-xl shadow-lg shadow-indigo-950/50 transition-all flex items-center gap-2 disabled:opacity-50"
            >
              {processing ? (
                <>
                  <Globe className="w-4 h-4 animate-spin text-white" />
                  <span>Investigando en Internet...</span>
                </>
              ) : (
                <>
                  <Globe className="w-4 h-4 text-white" />
                  <span>Ejecutar Investigación Web con IA</span>
                </>
              )}
            </button>
          )}
        </div>

      </div>
    </div>
  );
};
