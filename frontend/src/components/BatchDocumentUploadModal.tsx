import React, { useState, useRef, useCallback } from 'react';
import {
  UploadCloud, FileText, Image as ImageIcon, FileCode,
  Trash2, Plus, CheckCircle2, AlertCircle, AlertTriangle,
  X, RefreshCw, FolderKanban, Check, Layers
} from 'lucide-react';
import { apiService } from '../services/api';
import { BatchUploadResponse, BatchFileResultItem, DocumentItem } from '../types';

interface BatchDocumentUploadModalProps {
  isOpen: boolean;
  projectId: string;
  projectName: string;
  projectCode: string;
  onClose: () => void;
  onSuccess: (uploadedDocs: DocumentItem[], summaryMessage: string) => void;
}

interface StagedFile {
  id: string;
  file: File;
  name: string;
  relativePath?: string;
  size: number;
  typeCategory: 'plan_pdf' | 'raster_image' | 'cad_drawing' | 'technical_doc';
  status: 'pending' | 'uploading' | 'ready' | 'already_exists' | 'error';
  errorMessage?: string;
  documentId?: string;
  sheetsCount?: number;
}

const MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024; // 100 MB

const ALLOWED_EXTENSIONS = [
  '.pdf', '.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff',
  '.dxf', '.dwg', '.docx', '.xlsx', '.txt', '.csv', '.zip'
];

const isAllowedFile = (filename: string): boolean => {
  const lower = filename.toLowerCase();
  return ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext));
};

const isHiddenOrSystemFile = (filename: string): boolean => {
  const base = filename.split(/[/\\]/).pop() || filename;
  if (base.startsWith('.')) return true; // .DS_Store, .gitignore, etc.
  const lower = base.toLowerCase();
  if (['thumbs.db', 'desktop.ini', 'ehthumbs.db'].includes(lower)) return true;
  return false;
};

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const detectCategory = (filename: string): 'plan_pdf' | 'raster_image' | 'cad_drawing' | 'technical_doc' => {
  const lower = filename.toLowerCase();
  if (lower.endsWith('.pdf')) return 'plan_pdf';
  if (lower.endsWith('.png') || lower.endsWith('.jpg') || lower.endsWith('.jpeg') || lower.endsWith('.webp')) return 'raster_image';
  if (lower.endsWith('.dxf') || lower.endsWith('.dwg')) return 'cad_drawing';
  return 'technical_doc';
};

export const BatchDocumentUploadModal: React.FC<BatchDocumentUploadModalProps> = ({
  isOpen,
  projectId,
  projectName,
  projectCode,
  onClose,
  onSuccess,
}) => {
  const [stagedFiles, setStagedFiles] = useState<StagedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [batchResponse, setBatchResponse] = useState<BatchUploadResponse | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const addFilesToStage = (newFiles: FileList | File[]) => {
    setValidationError(null);
    const added: StagedFile[] = [];
    let oversizedCount = 0;
    let ignoredSystemCount = 0;
    let unsupportedExtCount = 0;

    Array.from(newFiles).forEach((file) => {
      const relPath = (file as any).webkitRelativePath || '';
      const checkPath = relPath || file.name;

      // Descartar archivos ocultos y de sistema
      if (isHiddenOrSystemFile(checkPath)) {
        ignoredSystemCount++;
        return;
      }

      // Filtrar extensiones no soportadas
      if (!isAllowedFile(file.name)) {
        unsupportedExtCount++;
        return;
      }

      if (file.size > MAX_FILE_SIZE_BYTES) {
        oversizedCount++;
        return;
      }
      
      // Evitar duplicar en la lista visual previa considerando relativePath o nombre
      const alreadyStaged = stagedFiles.some((f) =>
        (f.relativePath && relPath ? f.relativePath === relPath : f.name === file.name) && f.size === file.size
      );
      if (!alreadyStaged) {
        added.push({
          id: `${relPath || file.name}-${file.size}-${Date.now()}-${Math.random()}`,
          file,
          name: file.name,
          relativePath: relPath || undefined,
          size: file.size,
          typeCategory: detectCategory(file.name),
          status: 'pending',
        });
      }
    });

    const msgs: string[] = [];
    if (oversizedCount > 0) {
      msgs.push(`${oversizedCount} archivo(s) superan el límite máximo de 100 MB.`);
    }
    if (unsupportedExtCount > 0) {
      msgs.push(`${unsupportedExtCount} archivo(s) con formato no admitido fueron descartados.`);
    }
    if (ignoredSystemCount > 0) {
      msgs.push(`${ignoredSystemCount} archivo(s) de sistema/ocultos descartados.`);
    }
    if (msgs.length > 0) {
      setValidationError(msgs.join(' '));
    }

    setStagedFiles((prev) => [...prev, ...added]);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      addFilesToStage(e.dataTransfer.files);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addFilesToStage(e.target.files);
      e.target.value = '';
    }
  };

  const removeFileFromStage = (id: string) => {
    if (isUploading) return;
    setStagedFiles((prev) => prev.filter((f) => f.id !== id));
  };

  const clearAllStaged = () => {
    if (isUploading) return;
    setStagedFiles([]);
    setBatchResponse(null);
    setValidationError(null);
  };

  const handleStartUpload = async () => {
    if (stagedFiles.length === 0 || !projectId) return;

    try {
      setIsUploading(true);
      setValidationError(null);
      setUploadProgress(10);

      const filesToUpload = stagedFiles.map((sf) => sf.file);
      
      // Actualizar estado visual a 'uploading'
      setStagedFiles((prev) =>
        prev.map((f) => ({ ...f, status: 'uploading' }))
      );

      const response = await apiService.batchUploadDocuments(
        projectId,
        filesToUpload,
        undefined,
        (percent) => {
          setUploadProgress(percent);
        }
      );

      setBatchResponse(response);
      setUploadProgress(100);

      // Mapear resultados devueltos a la lista de archivos staged
      setStagedFiles((prev) =>
        prev.map((item) => {
          const result = response.results.find(
            (r) => r.filename === item.name || (item.relativePath && (r.filename === item.relativePath || item.relativePath.endsWith(r.filename)))
          );
          if (!result) return item;

          return {
            ...item,
            status: result.status === 'already_exists' ? 'already_exists' : result.status === 'failed' ? 'error' : 'ready',
            errorMessage: result.error_message || undefined,
            documentId: result.document_id,
            sheetsCount: result.sheets_count,
          };
        })
      );
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Error durante la carga por lotes.';
      setValidationError(msg);
      setStagedFiles((prev) =>
        prev.map((f) => ({
          ...f,
          status: f.status === 'uploading' ? 'error' : f.status,
          errorMessage: msg,
        }))
      );
    } finally {
      setIsUploading(false);
    }
  };

  const handleFinish = () => {
    if (batchResponse) {
      const summaryMsg = `Carga completada: ${batchResponse.successful_count} nuevos, ${batchResponse.duplicated_count} existentes, ${batchResponse.failed_count} con fallos.`;
      onSuccess(batchResponse.documents, summaryMsg);
    }
    onClose();
  };

  const totalBytes = stagedFiles.reduce((acc, f) => acc + f.size, 0);
  const isFinished = batchResponse !== null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-3xl shadow-2xl flex flex-col max-h-[90vh] overflow-hidden">
        
        {/* Cabecera del Modal */}
        <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-900/90">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-blue-600/20 text-blue-400 border border-blue-500/30">
              <UploadCloud className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                Carga por Lotes de Documentos & Planos
              </h3>
              <p className="text-xs text-slate-400 flex items-center gap-1.5 mt-0.5">
                <FolderKanban className="w-3.5 h-3.5 text-blue-400" />
                <span>Asociando a:</span>
                <span className="font-mono text-blue-400 font-semibold">{projectCode}</span>
                <span>— «{projectName}»</span>
              </p>
            </div>
          </div>
          
          <button
            onClick={onClose}
            disabled={isUploading}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Contenido Principal con Scroll */}
        <div className="p-6 space-y-5 overflow-y-auto flex-1">
          
          {/* Alertas de Error / Validación */}
          {validationError && (
            <div className="p-3.5 rounded-xl bg-rose-950/70 border border-rose-800 text-xs text-rose-300 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                <span>{validationError}</span>
              </div>
              <button onClick={() => setValidationError(null)} className="text-rose-400 hover:text-rose-200 text-xs font-bold">
                ✕
              </button>
            </div>
          )}

          {/* Resumen Final de Resultados */}
          {isFinished && batchResponse && (
            <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-200">Resumen de Ingesta por Lote:</span>
                <span className="text-[11px] font-mono text-slate-400">{batchResponse.total_files} archivos procesados</span>
              </div>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="p-2.5 rounded-lg bg-emerald-950/50 border border-emerald-800/60">
                  <p className="text-base font-bold text-emerald-400">{batchResponse.successful_count}</p>
                  <p className="text-[10px] text-emerald-300/80 uppercase font-semibold">Cargados / Listos</p>
                </div>
                <div className="p-2.5 rounded-lg bg-amber-950/50 border border-amber-800/60">
                  <p className="text-base font-bold text-amber-400">{batchResponse.duplicated_count}</p>
                  <p className="text-[10px] text-amber-300/80 uppercase font-semibold">Existentes / Reusados</p>
                </div>
                <div className="p-2.5 rounded-lg bg-rose-950/50 border border-rose-800/60">
                  <p className="text-base font-bold text-rose-400">{batchResponse.failed_count}</p>
                  <p className="text-[10px] text-rose-300/80 uppercase font-semibold">Fallidos</p>
                </div>
              </div>
            </div>
          )}

          {/* Zona de Drop & Selector si no se ha terminado */}
          {!isFinished && (
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={`p-6 border-2 border-dashed rounded-2xl text-center transition-all ${
                isDragging
                  ? 'border-blue-500 bg-blue-950/30 shadow-inner'
                  : 'border-slate-700 bg-slate-950/40 hover:border-slate-600'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.png,.jpg,.jpeg,.webp,.bmp,.tiff,.dxf,.dwg,.docx,.xlsx,.txt,.csv,.zip"
                onChange={handleFileInputChange}
                className="hidden"
                disabled={isUploading}
              />
              <input
                ref={folderInputRef}
                type="file"
                multiple
                {...({ webkitdirectory: '', directory: '' } as any)}
                onChange={handleFileInputChange}
                className="hidden"
                disabled={isUploading}
              />
              <UploadCloud className="w-10 h-10 text-blue-400 mx-auto mb-2 opacity-80" />
              <p className="text-sm font-bold text-slate-200">
                Arrastra y suelta aquí tus archivos o elige una modalidad:
              </p>
              <div className="flex items-center justify-center gap-3 mt-3">
                <button
                  type="button"
                  disabled={isUploading}
                  onClick={(e) => {
                    e.stopPropagation();
                    fileInputRef.current?.click();
                  }}
                  className="px-4 py-2 rounded-xl bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30 text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Seleccionar archivos</span>
                </button>
                <button
                  type="button"
                  disabled={isUploading}
                  onClick={(e) => {
                    e.stopPropagation();
                    folderInputRef.current?.click();
                  }}
                  className="px-4 py-2 rounded-xl bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 border border-amber-500/30 text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
                >
                  <FolderKanban className="w-3.5 h-3.5" />
                  <span>Seleccionar carpeta</span>
                </button>
              </div>
              <p className="text-xs text-slate-400 mt-3">
                Admite PDFs (planos multipágina), Imágenes (PNG/JPG), CAD (DXF/DWG) y memorias de cálculo (DOCX/XLSX/TXT).
              </p>
              <p className="text-[11px] text-slate-500 mt-1 font-mono">
                Máx. 100 MB por archivo — Descarta archivos ocultos/sistema (.DS_Store, Thumbs.db) automáticamente
              </p>
            </div>
          )}

          {/* Lista de Archivos en el Lote */}
          {stagedFiles.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <span className="text-xs font-bold text-slate-300">
                  Archivos en el lote ({stagedFiles.length}) — Total: {formatFileSize(totalBytes)}
                </span>
                {!isFinished && !isUploading && (
                  <button
                    onClick={clearAllStaged}
                    className="text-[11px] text-rose-400 hover:text-rose-300 flex items-center gap-1 transition-colors"
                  >
                    <Trash2 className="w-3 h-3" />
                    <span>Limpiar lote</span>
                  </button>
                )}
              </div>

              <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                {stagedFiles.map((sf) => {
                  let IconComp = FileText;
                  if (sf.typeCategory === 'raster_image') IconComp = ImageIcon;
                  else if (sf.typeCategory === 'cad_drawing') IconComp = FileCode;
                  else if (sf.typeCategory === 'plan_pdf') IconComp = Layers;

                  return (
                    <div
                      key={sf.id}
                      className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between gap-3 text-xs"
                    >
                      <div className="flex items-center gap-2.5 min-w-0 flex-1">
                        <div className="p-1.5 rounded-lg bg-slate-800 text-blue-400 shrink-0">
                          <IconComp className="w-4 h-4" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="font-semibold text-slate-200 truncate" title={sf.relativePath || sf.name}>
                            {sf.relativePath || sf.name}
                          </p>
                          <div className="flex items-center gap-2 text-[10px] text-slate-400 font-mono mt-0.5">
                            <span>{formatFileSize(sf.size)}</span>
                            <span>•</span>
                            <span className="capitalize">{sf.typeCategory.replace('_', ' ')}</span>
                            {sf.relativePath && (
                              <>
                                <span>•</span>
                                <span className="text-amber-400 font-medium">Carpeta</span>
                              </>
                            )}
                            {sf.sheetsCount !== undefined && sf.sheetsCount > 0 && (
                              <>
                                <span>•</span>
                                <span className="text-blue-400">{sf.sheetsCount} lámina(s)</span>
                              </>
                            )}
                          </div>
                          {sf.errorMessage && (
                            <p className="text-[11px] text-rose-400 mt-1">{sf.errorMessage}</p>
                          )}
                        </div>
                      </div>

                      {/* Estado o Acción */}
                      <div className="flex items-center gap-2 shrink-0">
                        {sf.status === 'pending' && !isFinished && !isUploading && (
                          <button
                            onClick={() => removeFileFromStage(sf.id)}
                            className="p-1 text-slate-500 hover:text-rose-400 transition-colors"
                            title="Quitar del lote"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}

                        {sf.status === 'uploading' && (
                          <div className="flex items-center gap-1.5 text-blue-400">
                            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            <span className="text-[10px] font-semibold">Procesando...</span>
                          </div>
                        )}

                        {sf.status === 'ready' && (
                          <div className="flex items-center gap-1 text-emerald-400 font-semibold text-[11px]">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>Listo</span>
                          </div>
                        )}

                        {sf.status === 'already_exists' && (
                          <div className="flex items-center gap-1 text-amber-400 font-semibold text-[11px]">
                            <AlertTriangle className="w-3.5 h-3.5" />
                            <span>Existente</span>
                          </div>
                        )}

                        {sf.status === 'error' && (
                          <div className="flex items-center gap-1 text-rose-400 font-semibold text-[11px]">
                            <AlertCircle className="w-3.5 h-3.5" />
                            <span>Fallido</span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Barra de Progreso de Subida */}
          {isUploading && (
            <div className="space-y-1.5 p-3 rounded-xl bg-slate-950 border border-slate-800">
              <div className="flex justify-between text-xs font-semibold text-slate-300">
                <span>Enviando y rasterizando lote...</span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-600 to-indigo-500 transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Pie del Modal con Acciones */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/90 flex items-center justify-between gap-3">
          <div>
            {!isFinished && stagedFiles.length > 0 && !isUploading && (
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="px-3 py-2 text-xs font-semibold text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-xl flex items-center gap-1.5 transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Añadir más archivos</span>
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            {!isFinished ? (
              <>
                <button
                  type="button"
                  onClick={onClose}
                  disabled={isUploading}
                  className="px-4 py-2 text-xs font-semibold text-slate-300 hover:text-slate-100 hover:bg-slate-800 rounded-xl transition-colors disabled:opacity-50"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={handleStartUpload}
                  disabled={stagedFiles.length === 0 || isUploading}
                  className="px-5 py-2 text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 active:bg-blue-700 rounded-xl shadow-lg shadow-blue-600/30 flex items-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isUploading ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Subiendo ({stagedFiles.length})...</span>
                    </>
                  ) : (
                    <>
                      <UploadCloud className="w-4 h-4" />
                      <span>Iniciar Carga ({stagedFiles.length})</span>
                    </>
                  )}
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={handleFinish}
                className="px-6 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-500 rounded-xl shadow-lg shadow-emerald-600/30 flex items-center gap-2 transition-all"
              >
                <Check className="w-4 h-4" />
                <span>Aceptar y Ver Entregables</span>
              </button>
            )}
          </div>
        </div>

      </div>
    </div>
  );
};
