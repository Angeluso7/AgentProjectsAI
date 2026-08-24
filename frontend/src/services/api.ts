import axios from 'axios';
import {
  Project, DocumentItem, DocumentSheet, DocumentImpact, ReviewRun,
  MemoriesStats, RuleDefinition, RuleFinding, ExtractedTextItem,
  SheetRegionItem, TitleBlockExtractionItem, SourceAssetItem,
  ProcessingJobItem, JobEventItem, ReviewTaskItem, ReviewDecisionItem,
  ConfidencePolicyItem, EngineDefinitionItem, EnginesSummaryResponse,
  KnowledgeItemSummaryDTO, KnowledgeItemDetailDTO, KnowledgeSyncResponseDTO,
  KnowledgeSearchResponseDTO, KnowledgeStatsDTO,
  AssistantExecutionRequestDTO, AssistantExecutionResponseDTO, AssistantFeedbackRequestDTO,
  AssistantInteractionItemDTO, AssistantTaskCatalogItemDTO,
  ProjectMaturityProfileDTO, AcquisitionRouteItemDTO,
  InformationAcquisitionRequestDTO, DetectInformationGapResponseDTO,
  WebSearchPermissionActionDTO, ViewerKnowledgeCaptureDTO,
  VisualDeduplicationCheckResponseDTO, IngestionChannelSummaryResponseDTO, KnowledgeItemDTO,
  SourceDependenciesInfo, SourceDeleteResult, ResearchQueryItem, ResearchQueryDetail,
  SourceDocumentPagesResponse, PageCropResponse, RuleSummarizeResponse,
  ExtractedTableItem, ExtractedTableCellItem, DetectedSymbolItem,
  SheetSymbolsSummaryResponse, RuleDefinitionItem, RuleEvaluationSummaryResponse,
  RuleFindingItem, AuditReportItem, EvidenceManifestItem, ReviewPipelineRunItem,
  PipelineStageRunItem, BatchUploadResponse, BatchFileResultItem
} from '../types';



const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor para inyectar Token Bearer y X-Organization-Id en cada solicitud
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  const orgId = localStorage.getItem('active_org_id');
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  if (orgId) {
    config.headers['X-Organization-Id'] = orgId;
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

// Interceptor para manejar expiración de sesión (401 Unauthorized)
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('active_org_id');
      localStorage.removeItem('user_info');
      window.dispatchEvent(new CustomEvent('auth-logout'));
    }
    return Promise.reject(error);
  }
);

export const apiService = {
  // Autenticación & Control de Acceso RBAC
  login: async (email: string, password: string): Promise<any> => {
    const res = await apiClient.post('/auth/login', { email, password });
    const data = res.data;
    if (data.access_token) {
      localStorage.setItem('auth_token', data.access_token);
      localStorage.setItem('active_org_id', data.active_organization_id);
      localStorage.setItem('active_role', data.active_role);
      localStorage.setItem('user_info', JSON.stringify(data.user));
    }
    return data;
  },
  logout: async (): Promise<void> => {
    try {
      await apiClient.post('/auth/logout');
    } catch {
      // ignore
    } finally {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('active_org_id');
      localStorage.removeItem('active_role');
      localStorage.removeItem('user_info');
      window.dispatchEvent(new CustomEvent('auth-logout'));
    }
  },
  getCurrentUser: async (): Promise<any> => {
    const res = await apiClient.get('/auth/me');
    return res.data;
  },
  updateProfile: async (displayName: string): Promise<any> => {
    const res = await apiClient.put('/auth/me', { display_name: displayName });
    const currentInfo = localStorage.getItem('user_info');
    if (currentInfo) {
      try {
        const parsed = JSON.parse(currentInfo);
        parsed.display_name = res.data.display_name;
        localStorage.setItem('user_info', JSON.stringify(parsed));
      } catch {}
    }
    return res.data;
  },
  changePassword: async (currentPassword: string, newPassword: string): Promise<any> => {
    const res = await apiClient.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
    return res.data;
  },
  requestEmailChange: async (currentPassword: string, newEmail: string): Promise<any> => {
    const res = await apiClient.post('/auth/email-change/request', {
      current_password: currentPassword,
      new_email: newEmail,
    });
    return res.data;
  },
  confirmEmailChange: async (token: string): Promise<any> => {
    const res = await apiClient.post('/auth/email-change/confirm', { token });
    return res.data;
  },
  requestPasswordReset: async (email: string): Promise<any> => {
    const res = await apiClient.post('/auth/password-reset/request', { email });
    return res.data;
  },
  confirmPasswordReset: async (token: string, newPassword: string): Promise<any> => {
    const res = await apiClient.post('/auth/password-reset/confirm', {
      token,
      new_password: newPassword,
    });
    return res.data;
  },


  // Salud del Backend y Estado de Motores IA
  checkHealth: async (): Promise<{ status: string; app_name: string; version: string }> => {
    const healthUrl = API_BASE_URL.includes('/api/v1')
      ? `${API_BASE_URL.replace('/api/v1', '')}/health`
      : 'http://localhost:8000/health';
    const res = await axios.get(healthUrl);
    return res.data;
  },
  getEngineHealth: async (): Promise<{
    status: string;
    total_engines: number;
    engines_ok: number;
    engines_fallback: number;
    engines_error: number;
    engines: Array<{
      category: string;
      name: string;
      active_engine: string;
      available_engines?: Record<string, boolean>;
      status: string;
      type: string;
      cost: string;
      latency_ms: number;
      last_tested: string;
      last_error?: string | null;
      description: string;
    }>;
  }> => {
    const res = await apiClient.get('/health/engines');
    return res.data;
  },
  testEngineHealth: async (): Promise<any> => {
    const res = await apiClient.post('/health/engines/test');
    return res.data;
  },

  // Gestión de IAs / Motores de IA
  getEngines: async (category?: string): Promise<EngineDefinitionItem[]> => {
    const res = await apiClient.get<EngineDefinitionItem[]>('/engines', {
      params: category && category !== 'all' ? { category } : undefined
    });
    return res.data;
  },
  getEnginesSummary: async (): Promise<EnginesSummaryResponse> => {
    const res = await apiClient.get<EnginesSummaryResponse>('/engines/summary');
    return res.data;
  },
  setActiveEngine: async (category: string, engine_id: string): Promise<EngineDefinitionItem> => {
    const res = await apiClient.post<EngineDefinitionItem>(`/engines/${category}/active`, { engine_id });
    return res.data;
  },
  updateEngineConfig: async (category: string, engine_id: string, parameters: Record<string, any>): Promise<EngineDefinitionItem> => {
    const res = await apiClient.put<EngineDefinitionItem>(`/engines/${category}/${engine_id}/config`, { parameters });
    return res.data;
  },
  updateEngineCredentials: async (category: string, engine_id: string, credentials: Record<string, string>): Promise<EngineDefinitionItem> => {
    const res = await apiClient.post<EngineDefinitionItem>(`/engines/${category}/${engine_id}/credentials`, { credentials });
    return res.data;
  },
  testEngine: async (category: string, engine_id: string): Promise<{
    engine_id: string;
    category: string;
    status: string;
    latency_ms: number;
    last_tested: string;
    error?: string | null;
  }> => {
    const res = await apiClient.post(`/engines/${category}/${engine_id}/test`);
    return res.data;
  },

  // Operaciones y Jobs Asíncronos
  getJobs: async (params?: {
    status?: string;
    job_type?: string;
    target_type?: string;
    project_id?: string;
  }): Promise<ProcessingJobItem[]> => {
    const res = await apiClient.get<ProcessingJobItem[]>('/jobs', { params });
    return res.data;
  },
  getJob: async (jobId: string): Promise<ProcessingJobItem> => {
    const res = await apiClient.get<ProcessingJobItem>(`/jobs/${jobId}`);
    return res.data;
  },
  retryJob: async (jobId: string): Promise<ProcessingJobItem> => {
    const res = await apiClient.post<ProcessingJobItem>(`/jobs/${jobId}/retry`);
    return res.data;
  },
  cancelJob: async (jobId: string): Promise<ProcessingJobItem> => {
    const res = await apiClient.post<ProcessingJobItem>(`/jobs/${jobId}/cancel`);
    return res.data;
  },
  getJobEvents: async (jobId: string): Promise<JobEventItem[]> => {
    const res = await apiClient.get<JobEventItem[]>(`/jobs/${jobId}/events`);
    return res.data;
  },

  // Cola de Revisión Humana (HITL)
  getReviewTasks: async (params?: {
    status?: string;
    task_type?: string;
    priority?: string;
    project_id?: string;
  }): Promise<ReviewTaskItem[]> => {
    const res = await apiClient.get<ReviewTaskItem[]>('/review-tasks', { params });
    return res.data;
  },
  getReviewTask: async (taskId: string): Promise<ReviewTaskItem> => {
    const res = await apiClient.get<ReviewTaskItem>(`/review-tasks/${taskId}`);
    return res.data;
  },
  submitReviewDecision: async (
    taskId: string,
    data: {
      decision: string;
      corrected_value?: Record<string, any>;
      reviewer?: string;
      notes?: string;
      reason_code?: string;
    }
  ): Promise<ReviewDecisionItem> => {
    const res = await apiClient.post<ReviewDecisionItem>(`/review-tasks/${taskId}/decision`, data);
    return res.data;
  },

  // Políticas de Confianza
  getConfidencePolicies: async (appliesTo?: string): Promise<ConfidencePolicyItem[]> => {
    const res = await apiClient.get<ConfidencePolicyItem[]>('/policies', { params: { applies_to: appliesTo } });
    return res.data;
  },
  seedConfidencePolicies: async (): Promise<ConfidencePolicyItem[]> => {
    const res = await apiClient.post<ConfidencePolicyItem[]>('/policies/seed-defaults');
    return res.data;
  },

  // Intake & Gobierno de Fuentes (SourceAssets)
  getDisciplines: async (): Promise<string[]> => {
    const res = await apiClient.get<string[]>('/intake/disciplines');
    return res.data;
  },
  getSources: async (params?: {
    source_type?: string;
    discipline?: string;
    status?: string;
    approval_status?: string;
    linked_memory_target?: string;
  }): Promise<SourceAssetItem[]> => {
    const res = await apiClient.get<SourceAssetItem[]>('/intake/sources', { params });
    return res.data;
  },
  getSource: async (id: string): Promise<SourceAssetItem> => {
    const res = await apiClient.get<SourceAssetItem>(`/intake/sources/${id}`);
    return res.data;
  },
  registerSource: async (data: Partial<SourceAssetItem>): Promise<SourceAssetItem> => {
    const res = await apiClient.post<SourceAssetItem>('/intake/sources', data);
    return res.data;
  },
  uploadSourceFile: async (formData: FormData): Promise<SourceAssetItem> => {
    const res = await apiClient.post<SourceAssetItem>('/intake/sources/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
  getSourceDependencies: async (sourceId: string): Promise<SourceDependenciesInfo> => {
    const res = await apiClient.get<SourceDependenciesInfo>(`/intake/sources/${sourceId}/dependencies`);
    return res.data;
  },
  deleteSource: async (sourceId: string, hardDelete: boolean = false): Promise<SourceDeleteResult> => {
    const res = await apiClient.delete<SourceDeleteResult>(`/intake/sources/${sourceId}`, {
      params: { hard_delete: hardDelete }
    });
    return res.data;
  },
  approveSource: async (sourceId: string, approved: boolean, notes?: string, reviewer = 'auditor_qa'): Promise<SourceAssetItem> => {
    const res = await apiClient.post<SourceAssetItem>(`/intake/sources/${sourceId}/approval`, {
      approved,
      notes,
      reviewer,
    });
    return res.data;
  },
  ingestSource: async (sourceId: string, projectId?: string): Promise<any> => {
    const res = await apiClient.post(`/intake/sources/${sourceId}/ingest`, null, {
      params: { project_id: projectId },
    });
    return res.data;
  },
  getResearchQueries: async (params?: { discipline?: string; status?: string }): Promise<ResearchQueryItem[]> => {
    const res = await apiClient.get<ResearchQueryItem[]>('/intake/research/queries', { params });
    return res.data;
  },
  getResearchQueryDetail: async (queryId: string): Promise<ResearchQueryDetail> => {
    const res = await apiClient.get<ResearchQueryDetail>(`/intake/research/queries/${queryId}`);
    return res.data;
  },
  getSourceFileUrl: (sourceId: string): string => {
    return `${API_BASE_URL}/intake/sources/${sourceId}/file`;
  },
  getSourcePages: async (sourceId: string): Promise<SourceDocumentPagesResponse> => {
    const res = await apiClient.get<SourceDocumentPagesResponse>(`/intake/sources/${sourceId}/pages`);
    return res.data;
  },
  cropSourcePage: async (
    sourceId: string,
    pageNumber: number,
    bbox: [number, number, number, number],
    title?: string,
    itemType?: string
  ): Promise<PageCropResponse> => {
    const res = await apiClient.post<PageCropResponse>(`/intake/sources/${sourceId}/crop`, {
      page_number: pageNumber,
      bbox,
      title,
      item_type: itemType,
    });
    return res.data;
  },
  summarizeRuleText: async (
    textContent: string,
    discipline?: string,
    title?: string,
    itemType?: string
  ): Promise<RuleSummarizeResponse> => {
    const res = await apiClient.post<RuleSummarizeResponse>('/intake/sources/summarize-rule', {
      text_content: textContent,
      discipline,
      title,
      item_type: itemType,
    });
    return res.data;
  },

  // Proyectos
  getProjects: async (includeArchived = true, status?: string): Promise<Project[]> => {
    const res = await apiClient.get<Project[]>('/projects/', {
      params: { include_archived: includeArchived, status: status }
    });
    return res.data;
  },
  getProject: async (id: string): Promise<Project> => {
    const res = await apiClient.get<Project>(`/projects/${id}`);
    return res.data;
  },
  createProject: async (data: Partial<Project>): Promise<Project> => {
    const res = await apiClient.post<Project>('/projects/', data);
    return res.data;
  },
  updateProject: async (id: string, data: Partial<Project>): Promise<Project> => {
    const res = await apiClient.put<Project>(`/projects/${id}`, data);
    return res.data;
  },
  archiveProject: async (id: string): Promise<Project> => {
    const res = await apiClient.put<Project>(`/projects/${id}/archive`);
    return res.data;
  },
  unarchiveProject: async (id: string): Promise<Project> => {
    const res = await apiClient.put<Project>(`/projects/${id}/unarchive`);
    return res.data;
  },
  deleteProject: async (id: string, hardDelete = false): Promise<any> => {
    const res = await apiClient.delete(`/projects/${id}`, {
      params: { hard_delete: hardDelete }
    });
    return res.data;
  },
  exportProject: async (id: string): Promise<any> => {
    const res = await apiClient.get(`/projects/${id}/export`);
    return res.data;
  },

  // Documentos
  getDocuments: async (projectId?: string, includeArchived = false): Promise<DocumentItem[]> => {
    const res = await apiClient.get<DocumentItem[]>('/documents/', {
      params: { project_id: projectId, include_archived: includeArchived },
    });
    return res.data;
  },
  getDocumentImpact: async (documentId: string): Promise<DocumentImpact> => {
    const res = await apiClient.get<DocumentImpact>(`/documents/${documentId}/impact`);
    return res.data;
  },
  deleteDocument: async (documentId: string, hardDelete = false): Promise<any> => {
    const res = await apiClient.delete(`/documents/${documentId}`, {
      params: { hard_delete: hardDelete }
    });
    return res.data;
  },
  getDocumentSheets: async (documentId: string): Promise<DocumentSheet[]> => {
    const res = await apiClient.get<DocumentSheet[]>(`/documents/${documentId}/sheets`);
    return res.data;
  },
  getSheetImageUrl: (sheetId: string): string => {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
    return `${baseUrl}/documents/sheets/${sheetId}/image`;
  },
  getSheetThumbnailUrl: (sheetId: string): string => {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
    return `${baseUrl}/documents/sheets/${sheetId}/thumbnail`;
  },
  uploadDocument: async (projectId: string, file: File, versionId?: string): Promise<DocumentItem> => {
    const formData = new FormData();
    formData.append('project_id', projectId);
    if (versionId) formData.append('version_id', versionId);
    formData.append('file', file);
    const res = await apiClient.post<DocumentItem>('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
  batchUploadDocuments: async (
    projectId: string,
    files: File[],
    versionId?: string,
    onProgress?: (percent: number) => void
  ): Promise<BatchUploadResponse> => {
    const formData = new FormData();
    formData.append('project_id', projectId);
    if (versionId) formData.append('version_id', versionId);
    files.forEach((file) => {
      formData.append('files', file);
    });
    const res = await apiClient.post<BatchUploadResponse>('/documents/batch-upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(percent);
        }
      },
    });
    return res.data;
  },



  // OCR Espacial (Síncrono y Asíncrono)
  getOcrEngines: async (): Promise<Record<string, boolean>> => {
    const res = await apiClient.get<Record<string, boolean>>('/ocr/engines');
    return res.data;
  },
  runSheetOcr: async (sheetId: string, force = false, engine?: string): Promise<ExtractedTextItem[]> => {
    const res = await apiClient.post<ExtractedTextItem[]>(`/ocr/sheets/${sheetId}`, {
      force_reprocess: force,
      engine,
    });
    return res.data;
  },
  runSheetOcrAsync: async (sheetId: string, force = false, engine?: string): Promise<any> => {
    const res = await apiClient.post(`/ocr/sheets/${sheetId}/async`, {
      force_reprocess: force,
      engine,
    });
    return res.data;
  },
  runDocumentOcr: async (documentId: string, force = false, engine?: string): Promise<any[]> => {
    const res = await apiClient.post<any[]>(`/ocr/documents/${documentId}`, {
      force_reprocess: force,
      engine,
    });
    return res.data;
  },
  runDocumentOcrAsync: async (documentId: string, force = false, engine?: string): Promise<any> => {
    const res = await apiClient.post(`/ocr/documents/${documentId}/async`, {
      force_reprocess: force,
      engine,
    });
    return res.data;
  },
  getSheetTexts: async (sheetId: string): Promise<ExtractedTextItem[]> => {
    const res = await apiClient.get<ExtractedTextItem[]>(`/ocr/sheets/${sheetId}/texts`);
    return res.data;
  },
  getDocumentTexts: async (documentId: string): Promise<ExtractedTextItem[]> => {
    const res = await apiClient.get<ExtractedTextItem[]>(`/ocr/documents/${documentId}/texts`);
    return res.data;
  },

  // Layout & Title Block Matching (Síncrono y Asíncrono)
  runSheetLayout: async (sheetId: string, force = false): Promise<any> => {
    const res = await apiClient.post(`/layout/sheets/${sheetId}`, { force_reprocess: force });
    return res.data;
  },
  runSheetLayoutAsync: async (sheetId: string, force = false): Promise<any> => {
    const res = await apiClient.post(`/layout/sheets/${sheetId}/async`, { force_reprocess: force });
    return res.data;
  },
  runDocumentLayout: async (documentId: string, force = false): Promise<any[]> => {
    const res = await apiClient.post(`/layout/documents/${documentId}`, { force_reprocess: force });
    return res.data;
  },
  runDocumentLayoutAsync: async (documentId: string, force = false): Promise<any> => {
    const res = await apiClient.post(`/layout/documents/${documentId}/async`, { force_reprocess: force });
    return res.data;
  },
  getSheetRegions: async (sheetId: string): Promise<SheetRegionItem[]> => {
    const res = await apiClient.get<SheetRegionItem[]>(`/layout/sheets/${sheetId}/regions`);
    return res.data;
  },
  matchSheetTitleBlock: async (sheetId: string, force = false, templateId?: string): Promise<TitleBlockExtractionItem> => {
    const res = await apiClient.post<TitleBlockExtractionItem>(`/layout/sheets/${sheetId}/title-block`, {
      force_reprocess: force,
      template_id: templateId
    });
    return res.data;
  },
  getSheetTitleBlock: async (sheetId: string): Promise<TitleBlockExtractionItem | null> => {
    try {
      const res = await apiClient.get<TitleBlockExtractionItem>(`/layout/sheets/${sheetId}/title-block`);
      return res.data;
    } catch {
      return null;
    }
  },

  // Extracción Tabular Profunda (Cuadros de Vanos, Superficies, Cargas)
  getSheetTables: async (sheetId: string): Promise<ExtractedTableItem[]> => {
    const res = await apiClient.get<ExtractedTableItem[]>(`/tables/sheets/${sheetId}`);
    return res.data;
  },
  getTableDetail: async (tableId: string): Promise<ExtractedTableItem> => {
    const res = await apiClient.get<ExtractedTableItem>(`/tables/${tableId}`);
    return res.data;
  },
  getTableCells: async (tableId: string): Promise<ExtractedTableCellItem[]> => {
    const res = await apiClient.get<ExtractedTableCellItem[]>(`/tables/${tableId}/cells`);
    return res.data;
  },
  runSheetTables: async (sheetId: string, force = false, regionId?: string): Promise<ExtractedTableItem[]> => {
    const res = await apiClient.post<ExtractedTableItem[]>(`/tables/sheets/${sheetId}`, {
      force_reprocess: force,
      region_id: regionId
    });
    return res.data;
  },
  runSheetTablesAsync: async (sheetId: string, force = false, regionId?: string): Promise<any> => {
    const res = await apiClient.post(`/tables/sheets/${sheetId}/async`, {
      force_reprocess: force,
      region_id: regionId
    });
    return res.data;
  },
  runDocumentTablesAsync: async (documentId: string, force = false): Promise<any> => {
    const res = await apiClient.post(`/tables/documents/${documentId}/async`, {
      force_reprocess: force
    });
    return res.data;
  },

  // Detección Visual de Símbolos (YOLO / SAHI / Geométrico)
  getSheetSymbols: async (sheetId: string, symbolType?: string, discipline?: string): Promise<DetectedSymbolItem[]> => {
    const res = await apiClient.get<DetectedSymbolItem[]>(`/symbols/sheets/${sheetId}`, {
      params: { symbol_type: symbolType, discipline }
    });
    return res.data;
  },
  getSheetSymbolsSummary: async (sheetId: string): Promise<SheetSymbolsSummaryResponse> => {
    const res = await apiClient.get<SheetSymbolsSummaryResponse>(`/symbols/sheets/${sheetId}/summary`);
    return res.data;
  },
  getDocumentSymbols: async (documentId: string): Promise<DetectedSymbolItem[]> => {
    const res = await apiClient.get<DetectedSymbolItem[]>(`/symbols/documents/${documentId}`);
    return res.data;
  },
  getSymbolDetail: async (symbolId: string): Promise<DetectedSymbolItem> => {
    const res = await apiClient.get<DetectedSymbolItem>(`/symbols/${symbolId}`);
    return res.data;
  },
  runSheetSymbols: async (
    sheetId: string,
    force = false,
    engine = 'yolo_sahi_hybrid',
    confidenceThreshold = 0.50,
    discipline?: string
  ): Promise<DetectedSymbolItem[]> => {
    const res = await apiClient.post<DetectedSymbolItem[]>(`/symbols/sheets/${sheetId}`, {
      force_reprocess: force,
      engine,
      confidence_threshold: confidenceThreshold,
      discipline
    });
    return res.data;
  },
  runSheetSymbolsAsync: async (
    sheetId: string,
    force = false,
    engine = 'yolo_sahi_hybrid',
    confidenceThreshold = 0.50,
    discipline?: string
  ): Promise<any> => {
    const res = await apiClient.post(`/symbols/sheets/${sheetId}/async`, {
      force_reprocess: force,
      engine,
      confidence_threshold: confidenceThreshold,
      discipline
    });
    return res.data;
  },
  runDocumentSymbolsAsync: async (documentId: string, force = false): Promise<any> => {
    const res = await apiClient.post(`/symbols/documents/${documentId}/async`, {
      force_reprocess: force
    });
    return res.data;
  },

  // Memorias y Estadísticas
  getMemoriesStats: async (): Promise<MemoriesStats> => {
    const res = await apiClient.get<MemoriesStats>('/memories/stats');
    return res.data;
  },

  // Reglas QA/QC y Conciliación Cruzada
  getRules: async (discipline?: string, category?: string): Promise<RuleDefinitionItem[]> => {
    const res = await apiClient.get<RuleDefinitionItem[]>('/rules', {
      params: { discipline, category },
    });
    return res.data;
  },
  getRulesSummary: async (documentId?: string, sheetId?: string): Promise<RuleEvaluationSummaryResponse> => {
    const res = await apiClient.get<RuleEvaluationSummaryResponse>('/rules/summary', {
      params: { document_id: documentId, sheet_id: sheetId }
    });
    return res.data;
  },
  getRuleDetail: async (ruleCode: string): Promise<RuleDefinitionItem> => {
    const res = await apiClient.get<RuleDefinitionItem>(`/rules/${ruleCode}`);
    return res.data;
  },
  runSheetRules: async (sheetId: string): Promise<RuleFindingItem[]> => {
    const res = await apiClient.post<RuleFindingItem[]>(`/rules/sheets/${sheetId}`);
    return res.data;
  },
  runSheetRulesAsync: async (sheetId: string): Promise<any> => {
    const res = await apiClient.post(`/rules/sheets/${sheetId}/async`);
    return res.data;
  },
  runDocumentRulesAsync: async (documentId: string): Promise<any> => {
    const res = await apiClient.post(`/rules/documents/${documentId}/async`);
    return res.data;
  },

  // Hallazgos y Resoluciones QA/QC
  getFindings: async (
    documentId?: string,
    sheetId?: string,
    severity?: string,
    status?: string
  ): Promise<RuleFindingItem[]> => {
    const res = await apiClient.get<RuleFindingItem[]>('/findings', {
      params: { document_id: documentId, sheet_id: sheetId, severity, status }
    });
    return res.data;
  },
  getFindingDetail: async (findingId: string): Promise<RuleFindingItem> => {
    const res = await apiClient.get<RuleFindingItem>(`/findings/${findingId}`);
    return res.data;
  },
  resolveFinding: async (
    findingId: string,
    resolutionType: string,
    resolvedBy = 'auditor_qa',
    notes?: string,
    correctedValue?: any
  ): Promise<RuleFindingItem> => {
    const res = await apiClient.post<RuleFindingItem>(`/findings/${findingId}/resolve`, {
      resolution_type: resolutionType,
      resolved_by: resolvedBy,
      notes,
      corrected_value: correctedValue
    });
    return res.data;
  },

  // Revisión & Hallazgos
  getReviewRuns: async (projectId?: string): Promise<ReviewRun[]> => {
    const res = await apiClient.get<ReviewRun[]>('/review-runs/', {
      params: { project_id: projectId },
    });
    return res.data;
  },
  getReviewRun: async (runId: string): Promise<ReviewRun> => {
    const res = await apiClient.get<ReviewRun>(`/review-runs/${runId}`);
    return res.data;
  },
  startReviewRun: async (projectId: string, runName: string): Promise<ReviewRun> => {
    const res = await apiClient.post<ReviewRun>('/review-runs/', {
      project_id: projectId,
      run_name: runName,
    });
    return res.data;
  },
  submitFeedback: async (findingId: string, action: string, notes?: string): Promise<any> => {
    const res = await apiClient.post(`/findings/${findingId}/feedback`, {
      action,
      notes,
    });
    return res.data;
  },

  // Reportes Técnicos & Paquetes de Evidencia
  getReports: async (documentId?: string, sheetId?: string, reportType?: string): Promise<AuditReportItem[]> => {
    const res = await apiClient.get<AuditReportItem[]>('/reports', {
      params: { document_id: documentId, sheet_id: sheetId, report_type: reportType }
    });
    return res.data;
  },
  getReport: async (reportId: string): Promise<AuditReportItem> => {
    const res = await apiClient.get<AuditReportItem>(`/reports/${reportId}`);
    return res.data;
  },
  getReportManifest: async (reportId: string): Promise<EvidenceManifestItem> => {
    const res = await apiClient.get<EvidenceManifestItem>(`/reports/${reportId}/manifest`);
    return res.data;
  },
  generateSheetReport: async (
    sheetId: string,
    reportType = 'technical_audit_qaqc',
    generatedBy = 'auditor_qa'
  ): Promise<AuditReportItem> => {
    const res = await apiClient.post<AuditReportItem>(`/reports/sheets/${sheetId}`, {
      report_type: reportType,
      generated_by: generatedBy
    });
    return res.data;
  },
  generateSheetReportAsync: async (
    sheetId: string,
    reportType = 'technical_audit_qaqc',
    generatedBy = 'auditor_qa'
  ): Promise<any> => {
    const res = await apiClient.post(`/reports/sheets/${sheetId}/async`, {
      report_type: reportType,
      generated_by: generatedBy
    });
    return res.data;
  },
  generateDocumentReportAsync: async (
    documentId: string,
    reportType = 'technical_audit_qaqc',
    generatedBy = 'auditor_qa'
  ): Promise<any> => {
    const res = await apiClient.post(`/reports/documents/${documentId}/async`, {
      report_type: reportType,
      generated_by: generatedBy
    });
    return res.data;
  },
  getReportDownloadPdfUrl: (reportId: string) => `http://localhost:8000/api/v1/reports/${reportId}/download/pdf`,
  getReportDownloadJsonUrl: (reportId: string) => `http://localhost:8000/api/v1/reports/${reportId}/download/json`,
  getReportDownloadBundleUrl: (reportId: string) => `http://localhost:8000/api/v1/reports/${reportId}/download/bundle`,

  // Pipelines One-Click Review
  getPipelines: async (scopeType?: string, scopeId?: string, status?: string): Promise<ReviewPipelineRunItem[]> => {
    const res = await apiClient.get<ReviewPipelineRunItem[]>('/pipelines', {
      params: { scope_type: scopeType, scope_id: scopeId, status: status }
    });
    return res.data;
  },
  getPipeline: async (pipelineRunId: string): Promise<ReviewPipelineRunItem> => {
    const res = await apiClient.get<ReviewPipelineRunItem>(`/pipelines/${pipelineRunId}`);
    return res.data;
  },
  getPipelineStages: async (pipelineRunId: string): Promise<PipelineStageRunItem[]> => {
    const res = await apiClient.get<PipelineStageRunItem[]>(`/pipelines/${pipelineRunId}/stages`);
    return res.data;
  },
  runDocumentPipelineAsync: async (documentId: string, forceReprocess = false, requestedBy = 'auditor_qa'): Promise<any> => {
    const res = await apiClient.post(`/pipelines/documents/${documentId}/run`, {
      force_reprocess: forceReprocess,
      requested_by: requestedBy
    });
    return res.data;
  },
  runSheetPipelineAsync: async (sheetId: string, forceReprocess = false, requestedBy = 'auditor_qa'): Promise<any> => {
    const res = await apiClient.post(`/pipelines/sheets/${sheetId}/run`, {
      force_reprocess: forceReprocess,
      requested_by: requestedBy
    });
    return res.data;
  },
  retryPipeline: async (pipelineRunId: string): Promise<any> => {
    const res = await apiClient.post(`/pipelines/${pipelineRunId}/retry`);
    return res.data;
  },
  cancelPipeline: async (pipelineRunId: string): Promise<any> => {
    const res = await apiClient.post(`/pipelines/${pipelineRunId}/cancel`);
    return res.data;
  },

  // Conocimiento & Assets
  getKnowledgeAssets: async (assetType?: string): Promise<any[]> => {
    const res = await apiClient.get('/knowledge/assets', {
      params: { asset_type: assetType },
    });
    return res.data;
  },
  syncKnowledge: async (): Promise<any> => {
    const res = await apiClient.post('/knowledge/sync-seed');
    return res.data;
  },

  // Organizaciones & Membresías RBAC
  getCurrentOrganization: async (): Promise<any> => {
    const res = await apiClient.get('/organizations/current');
    return res.data;
  },
  getOrganizationMembers: async (organizationId: string): Promise<any[]> => {
    const res = await apiClient.get(`/organizations/${organizationId}/members`);
    return res.data;
  },
  addOrganizationMember: async (organizationId: string, payload: any): Promise<any> => {
    const res = await apiClient.post(`/organizations/${organizationId}/members`, payload);
    return res.data;
  },

  // Golden Datasets & Evaluación Reproducible (Fase 3 - Línea 2)
  getEvaluationDatasets: async (): Promise<any[]> => {
    const res = await apiClient.get('/evaluations/datasets');
    return res.data;
  },
  getEvaluationDataset: async (id: string): Promise<any> => {
    const res = await apiClient.get(`/evaluations/datasets/${id}`);
    return res.data;
  },
  createEvaluationDataset: async (payload: any): Promise<any> => {
    const res = await apiClient.post('/evaluations/datasets', payload);
    return res.data;
  },
  freezeEvaluationDataset: async (id: string): Promise<any> => {
    const res = await apiClient.post(`/evaluations/datasets/${id}/freeze`);
    return res.data;
  },
  addEvaluationSample: async (datasetId: string, payload: any): Promise<any> => {
    const res = await apiClient.post(`/evaluations/datasets/${datasetId}/samples`, payload);
    return res.data;
  },
  getEvaluationSample: async (sampleId: string): Promise<any> => {
    const res = await apiClient.get(`/evaluations/samples/${sampleId}`);
    return res.data;
  },
  getSampleAnnotations: async (sampleId: string): Promise<any[]> => {
    const res = await apiClient.get(`/evaluations/samples/${sampleId}/annotations`);
    return res.data;
  },
  addSampleAnnotation: async (sampleId: string, payload: any): Promise<any> => {
    const res = await apiClient.post(`/evaluations/samples/${sampleId}/annotations`, payload);
    return res.data;
  },
  updateAnnotationStatus: async (annotationId: string, status: string, notes?: string): Promise<any> => {
    const res = await apiClient.patch(`/evaluations/annotations/${annotationId}/status`, { status, notes });
    return res.data;
  },
  runDatasetEvaluation: async (datasetId: string, split: string = 'test', config: any = {}): Promise<any> => {
    const res = await apiClient.post(`/evaluations/datasets/${datasetId}/run`, { split_evaluated: split, config });
    return res.data;
  },
  getEvaluationRuns: async (datasetId?: string): Promise<any[]> => {
    const res = await apiClient.get('/evaluations/runs', { params: { dataset_id: datasetId } });
    return res.data;
  },
  getEvaluationRun: async (runId: string): Promise<any> => {
    const res = await apiClient.get(`/evaluations/runs/${runId}`);
    return res.data;
  },
  getEvaluationMetrics: async (runId: string, params?: { category?: string; component?: string }): Promise<any[]> => {
    const res = await apiClient.get(`/evaluations/runs/${runId}/metrics`, { params });
    return res.data;
  },

  // Anotaciones Manuales, Recortes, OCR y Active Learning (Visor Interactivo)
  runCropOcr: async (imageBase64: string, sheetId?: string): Promise<any> => {
    const res = await apiClient.post('/annotations/crop-ocr', {
      image_base64: imageBase64,
      sheet_id: sheetId,
    });
    return res.data;
  },
  createManualAnnotation: async (payload: any): Promise<any> => {
    const res = await apiClient.post('/annotations', payload);
    return res.data;
  },
  updateManualAnnotation: async (annotationId: string, payload: any): Promise<any> => {
    const res = await apiClient.put(`/annotations/${annotationId}`, payload);
    return res.data;
  },
  getManualAnnotations: async (sheetId?: string, docId?: string, projectId?: string): Promise<any[]> => {
    const res = await apiClient.get('/annotations', {
      params: { sheet_id: sheetId, document_id: docId, project_id: projectId },
    });
    return res.data;
  },
  getAnnotationDisciplines: async (): Promise<string[]> => {
    const res = await apiClient.get<string[]>('/annotations/disciplines');
    return res.data;
  },
  deleteManualAnnotation: async (annotationId: string): Promise<any> => {
    const res = await apiClient.delete(`/annotations/${annotationId}`);
    return res.data;
  },

  addToKnowledgeLibrary: async (payload: any): Promise<any> => {
    const res = await apiClient.post('/annotations/knowledge-library', payload);
    return res.data;
  },
  getKnowledgeLibraryEntries: async (entryType?: string, discipline?: string): Promise<any[]> => {
    const res = await apiClient.get('/annotations/knowledge-library', {
      params: { entry_type: entryType, discipline },
    });
    return res.data;
  },
  promoteToActiveLearning: async (payload: any): Promise<any> => {
    const res = await apiClient.post('/annotations/active-learning/promote', payload);
    return res.data;
  },
  getActiveLearningPromotions: async (targetEngine?: string): Promise<any[]> => {
    const res = await apiClient.get('/annotations/active-learning', {
      params: { target_engine: targetEngine },
    });
    return res.data;
  },
  incorporateSelectionsToProjectDocument: async (payload: { project_id: string; annotation_ids?: string[] }): Promise<any> => {
    const res = await apiClient.post('/annotations/incorporate-to-project-document', payload);
    return res.data;
  },

  // =========================================================
  // INTAKE EXTRACTIONS & DOCUMENTOS MOTOR DE REGLAS
  // =========================================================

  processDocumentWithAi: async (payload: any): Promise<any> => {
    const res = await apiClient.post('/intake/extractions/process-with-ai', payload);
    return res.data;
  },
  processWebResearch: async (payload: {
    search_prompt: string;
    discipline?: string;
    document_type?: string;
    authority?: string;
    focus_areas?: string[];
  }): Promise<any> => {
    const res = await apiClient.post('/intake/extractions/process-web-research', payload);
    return res.data;
  },
  createManualExtraction: async (payload: any): Promise<any> => {
    const res = await apiClient.post('/intake/extractions/create-manual', payload);
    return res.data;
  },
  getExtractions: async (params?: any): Promise<any[]> => {
    const res = await apiClient.get('/intake/extractions', { params });
    return res.data;
  },
  getExtractionDetail: async (extractionId: string): Promise<any> => {
    const res = await apiClient.get(`/intake/extractions/${extractionId}`);
    return res.data;
  },
  addExtractedItem: async (extractionId: string, payload: any): Promise<any> => {
    const res = await apiClient.post(`/intake/extractions/${extractionId}/items`, payload);
    return res.data;
  },
  updateExtractedItem: async (extractionId: string, itemId: string, payload: any): Promise<any> => {
    const res = await apiClient.put(`/intake/extractions/${extractionId}/items/${itemId}`, payload);
    return res.data;
  },
  deleteExtractedItem: async (extractionId: string, itemId: string): Promise<any> => {
    const res = await apiClient.delete(`/intake/extractions/${extractionId}/items/${itemId}`);
    return res.data;
  },
  commitExtractionToRules: async (extractionId: string, payload: any): Promise<any> => {
    const res = await apiClient.post(`/intake/extractions/${extractionId}/commit`, payload);
    return res.data;
  },
  getDocumentOcr: async (payload: any): Promise<any> => {
    const res = await apiClient.post('/intake/extractions/document-ocr', payload);
    return res.data;
  },
  generateRulesFromOcr: async (payload: {
    ocr_text: string;
    discipline?: string;
    document_title?: string;
    page_number?: number;
  }): Promise<{ rules: Array<{ code: string; title: string; statement: string; item_type: string; page_number: number }> }> => {
    const res = await apiClient.post('/intake/extractions/generate-rules-from-ocr', payload);
    return res.data;
  },

  getRuleDocuments: async (params?: any): Promise<any[]> => {
    const res = await apiClient.get('/rules/documents', { params });
    return res.data;
  },
  getRuleDocumentDetail: async (docId: string): Promise<any> => {
    const res = await apiClient.get(`/rules/documents/${docId}`);
    return res.data;
  },
  updateRuleDocument: async (docId: string, payload: any): Promise<any> => {
    const res = await apiClient.put(`/rules/documents/${docId}`, payload);
    return res.data;
  },
  deleteRuleDocument: async (docId: string): Promise<any> => {
    const res = await apiClient.delete(`/rules/documents/${docId}`);
    return res.data;
  },
  getRuleDocumentItems: async (docId: string): Promise<any[]> => {
    const res = await apiClient.get(`/rules/documents/${docId}/items`);
    return res.data;
  },
  updateRuleDocumentItem: async (docId: string, itemId: string, payload: any): Promise<any> => {
    const res = await apiClient.put(`/rules/documents/${docId}/items/${itemId}`, payload);
    return res.data;
  },
  deleteRuleDocumentItem: async (docId: string, itemId: string): Promise<any> => {
    const res = await apiClient.delete(`/rules/documents/${docId}/items/${itemId}`);
    return res.data;
  },
  confirmRuleDocumentContent: async (docId: string, payload?: any): Promise<any> => {
    const res = await apiClient.post(`/rules/documents/${docId}/confirm-content`, payload || {});
    return res.data;
  },
  promoteRuleDocumentToBaseline: async (docId: string): Promise<any> => {
    const res = await apiClient.post(`/rules/documents/${docId}/promote-to-baseline`);
    return res.data;
  },

  // Motor de Completitud Documental y Ciclo de Vida de Evidencia
  getCompletenessRequirements: async (stage?: string, discipline?: string): Promise<any[]> => {
    const res = await apiClient.get('/completeness/requirements', {
      params: { stage, discipline }
    });
    return res.data;
  },
  getProjectCompleteness: async (projectId: string, stage?: string): Promise<any> => {
    const res = await apiClient.get(`/completeness/projects/${projectId}`, {
      params: { stage }
    });
    return res.data;
  },
  evaluateProjectCompleteness: async (projectId: string, stage?: string): Promise<any> => {
    const res = await apiClient.post(`/completeness/projects/${projectId}/evaluate`, null, {
      params: { stage }
    });
    return res.data;
  },
  classifyDocumentDeliverable: async (
    documentId: string,
    payload: { deliverable_type: string; readiness_status?: string; validation_notes?: string }
  ): Promise<any> => {
    const res = await apiClient.post(`/completeness/documents/${documentId}/classify`, payload);
    return res.data;
  },
  updateDocumentReadiness: async (
    documentId: string,
    payload: { readiness_status: string; validation_notes?: string }
  ): Promise<any> => {
    const res = await apiClient.put(`/completeness/documents/${documentId}/readiness`, payload);
    return res.data;
  },

  // Gestión Formal de Observaciones Técnicas, RFIs y Re-evaluación Delta
  getObservations: async (params?: any): Promise<any[]> => {
    const res = await apiClient.get('/observations', { params });
    return res.data;
  },
  getObservationDetail: async (obsId: string): Promise<any> => {
    const res = await apiClient.get(`/observations/${obsId}`);
    return res.data;
  },
  generateObservationsFromRun: async (payload: { project_id: string; review_run_id?: string; stage?: string }): Promise<any[]> => {
    const res = await apiClient.post('/observations/generate-from-run', payload);
    return res.data;
  },
  issueObservation: async (obsId: string, payload: { assigned_to?: string; notes?: string }): Promise<any> => {
    const res = await apiClient.post(`/observations/${obsId}/issue`, payload);
    return res.data;
  },
  submitObservationResponse: async (
    obsId: string,
    payload: { response_text: string; author_role?: string; attached_document_id?: string }
  ): Promise<any> => {
    const res = await apiClient.post(`/observations/${obsId}/response`, payload);
    return res.data;
  },
  provisionObservationEvidence: async (
    obsId: string,
    payload: { document_id: string; notes?: string }
  ): Promise<any> => {
    const res = await apiClient.post(`/observations/${obsId}/provision`, payload);
    return res.data;
  },
  executeObservationDeltaReevaluation: async (obsId: string): Promise<any> => {
    const res = await apiClient.post(`/observations/${obsId}/delta-reevaluation`);
    return res.data;
  },
  reopenObservation: async (obsId: string, payload?: { reason?: string }): Promise<any> => {
    const res = await apiClient.post(`/observations/${obsId}/reopen`, payload || {});
    return res.data;
  },

  // Reporte Consolidado Final por Etapa & Snapshots Inmutables
  getConsolidatedReportPreview: async (projectId: string, stage?: string): Promise<any> => {
    const res = await apiClient.get('/reports/consolidated/preview', {
      params: { project_id: projectId, stage }
    });
    return res.data;
  },
  emitConsolidatedStageReport: async (payload: {
    project_id: string;
    stage?: string;
    title?: string;
    notes?: string;
  }): Promise<any> => {
    const res = await apiClient.post('/reports/consolidated/emit', payload);
    return res.data;
  },
  getStageReportSnapshots: async (projectId: string, stage?: string): Promise<any[]> => {
    const res = await apiClient.get('/reports/consolidated/snapshots', {
      params: { project_id: projectId, stage }
    });
    return res.data;
  },
  getStageReportSnapshotDetail: async (snapshotId: string): Promise<any> => {
    const res = await apiClient.get(`/reports/consolidated/snapshots/${snapshotId}`);
    return res.data;
  },
  getSnapshotPdfDownloadUrl: (snapshotId: string): string => {
    return `/api/v1/reports/consolidated/snapshots/${snapshotId}/download/pdf`;
  },
  getSnapshotJsonDownloadUrl: (snapshotId: string): string => {
    return `/api/v1/reports/consolidated/snapshots/${snapshotId}/download/json`;
  },

  // Base de Conocimiento Operacional para el Asistente
  getKnowledgeItems: async (params?: {
    project_id?: string;
    domain?: string;
    status?: string;
    discipline?: string;
    stage?: string;
    active_only?: boolean;
    search?: string;
    include_global?: boolean;
    skip?: number;
    limit?: number;
  }): Promise<KnowledgeItemSummaryDTO[]> => {
    const res = await apiClient.get<KnowledgeItemSummaryDTO[]>('/knowledge/items', { params });
    return res.data;
  },
  getKnowledgeItemDetail: async (itemId: string): Promise<KnowledgeItemDetailDTO> => {
    const res = await apiClient.get<KnowledgeItemDetailDTO>(`/knowledge/items/${itemId}`);
    return res.data;
  },
  createKnowledgeItem: async (payload: any): Promise<KnowledgeItemDetailDTO> => {
    const res = await apiClient.post<KnowledgeItemDetailDTO>('/knowledge/items', payload);
    return res.data;
  },
  updateKnowledgeItem: async (itemId: string, payload: any): Promise<KnowledgeItemDetailDTO> => {
    const res = await apiClient.put<KnowledgeItemDetailDTO>(`/knowledge/items/${itemId}`, payload);
    return res.data;
  },
  transitionKnowledgeStatus: async (
    itemId: string,
    payload: { target_status: string; notes?: string; reviewer?: string }
  ): Promise<KnowledgeItemDetailDTO> => {
    const res = await apiClient.post<KnowledgeItemDetailDTO>(`/knowledge/items/${itemId}/transition`, payload);
    return res.data;
  },
  versionKnowledgeItem: async (
    itemId: string,
    payload: {
      new_title?: string;
      new_content_text: string;
      new_summary?: string;
      new_structured_payload?: any;
      change_notes: string;
      author?: string;
    }
  ): Promise<KnowledgeItemDetailDTO> => {
    const res = await apiClient.post<KnowledgeItemDetailDTO>(`/knowledge/items/${itemId}/version`, payload);
    return res.data;
  },
  syncKnowledgeBase: async (payload: {
    project_id?: string;
    auto_approve?: boolean;
    source_module?: string;
  }): Promise<KnowledgeSyncResponseDTO> => {
    const module = payload.source_module || 'all';
    const endpoint = module === 'all' ? '/knowledge/sync/all' : `/knowledge/sync/${module}`;
    const res = await apiClient.post<KnowledgeSyncResponseDTO>(endpoint, payload);
    return res.data;
  },
  searchKnowledgeBase: async (payload: {
    query: string;
    project_id?: string;
    domain?: string;
    discipline?: string;
    stage?: string;
    active_only?: boolean;
    top_k?: number;
  }): Promise<KnowledgeSearchResponseDTO> => {
    const res = await apiClient.post<KnowledgeSearchResponseDTO>('/knowledge/search', payload);
    return res.data;
  },
  getKnowledgeStats: async (projectId?: string): Promise<KnowledgeStatsDTO> => {
    const res = await apiClient.get<KnowledgeStatsDTO>('/knowledge/stats', {
      params: { project_id: projectId }
    });
    return res.data;
  },

  // Asistente Operacional RAG & Routing de Motores
  getAssistantTasks: async (): Promise<AssistantTaskCatalogItemDTO[]> => {
    const res = await apiClient.get<AssistantTaskCatalogItemDTO[]>('/assistant/tasks');
    return res.data;
  },
  executeAssistantTask: async (payload: AssistantExecutionRequestDTO): Promise<AssistantExecutionResponseDTO> => {
    const res = await apiClient.post<AssistantExecutionResponseDTO>('/assistant/execute', payload);
    return res.data;
  },
  submitAssistantFeedback: async (
    interactionId: string,
    payload: AssistantFeedbackRequestDTO
  ): Promise<AssistantInteractionItemDTO> => {
    const res = await apiClient.post<AssistantInteractionItemDTO>(`/assistant/interactions/${interactionId}/feedback`, payload);
    return res.data;
  },
  getAssistantInteractions: async (params?: {
    project_id?: string;
    task_type?: string;
    feedback_status?: string;
    limit?: number;
  }): Promise<AssistantInteractionItemDTO[]> => {
    const res = await apiClient.get<AssistantInteractionItemDTO[]>('/assistant/interactions', {
      params
    });
    return res.data;
  },

  // Perfil de Madurez o Suficiencia Informacional
  getLatestProjectMaturity: async (projectId: string, stage?: string): Promise<ProjectMaturityProfileDTO> => {
    const res = await apiClient.get<ProjectMaturityProfileDTO>(`/projects/${projectId}/maturity/latest`, {
      params: { stage }
    });
    return res.data;
  },
  evaluateProjectMaturity: async (
    projectId: string,
    stage?: string,
    targetLevel = 'advanced'
  ): Promise<ProjectMaturityProfileDTO> => {
    const res = await apiClient.post<ProjectMaturityProfileDTO>(`/projects/${projectId}/maturity/evaluate`, {
      stage,
      target_level: targetLevel
    });
    return res.data;
  },
  getProjectMaturityHistory: async (projectId: string, limit = 15): Promise<ProjectMaturityProfileDTO[]> => {
    const res = await apiClient.get<ProjectMaturityProfileDTO[]>(`/projects/${projectId}/maturity/history`, {
      params: { limit }
    });
    return res.data;
  },
  getProjectAcquisitionRoutes: async (projectId: string, stage?: string): Promise<AcquisitionRouteItemDTO[]> => {
    const res = await apiClient.get<AcquisitionRouteItemDTO[]>(`/projects/${projectId}/maturity/acquisition-routes`, {
      params: { stage }
    });
    return res.data;
  },
  exportProjectMaturityProfile: async (projectId: string, profileId: string): Promise<any> => {
    const res = await apiClient.get(`/projects/${projectId}/maturity/${profileId}/export`);
    return res.data;
  },

  // Adquisición de Información & Política Web-First con Permiso
  detectInformationGap: async (req: {
    project_id?: string;
    stage?: string;
    discipline?: string;
    topic_query: string;
    detection_source?: string;
    auto_request_permission?: boolean;
  }): Promise<DetectInformationGapResponseDTO> => {
    const res = await apiClient.post<DetectInformationGapResponseDTO>('/acquisition/detect-gap', req);
    return res.data;
  },
  getAcquisitionRequests: async (params?: {
    project_id?: string;
    permission_status?: string;
    status?: string;
    limit?: number;
  }): Promise<InformationAcquisitionRequestDTO[]> => {
    const res = await apiClient.get<InformationAcquisitionRequestDTO[]>('/acquisition/requests', {
      params
    });
    return res.data;
  },
  getAcquisitionRequest: async (requestId: string): Promise<InformationAcquisitionRequestDTO> => {
    const res = await apiClient.get<InformationAcquisitionRequestDTO>(`/acquisition/requests/${requestId}`);
    return res.data;
  },
  respondWebSearchPermission: async (
    requestId: string,
    payload: WebSearchPermissionActionDTO
  ): Promise<InformationAcquisitionRequestDTO> => {
    const res = await apiClient.post<InformationAcquisitionRequestDTO>(`/acquisition/requests/${requestId}/permission`, payload);
    return res.data;
  },
  captureFromViewerToKnowledge: async (
    payload: ViewerKnowledgeCaptureDTO
  ): Promise<KnowledgeItemDTO> => {
    const res = await apiClient.post<KnowledgeItemDTO>('/acquisition/capture-from-viewer', payload);
    return res.data;
  },
  checkVisualDeduplication: async (payload: {
    name: string;
    normalized_category?: string;
    discipline?: string;
    element_type?: string;
  }): Promise<VisualDeduplicationCheckResponseDTO> => {
    const res = await apiClient.post<VisualDeduplicationCheckResponseDTO>('/acquisition/visual-dedup-check', payload);
    return res.data;
  },
  getIngestionChannelsSummary: async (
    projectId?: string
  ): Promise<IngestionChannelSummaryResponseDTO> => {
    const res = await apiClient.get<IngestionChannelSummaryResponseDTO>('/acquisition/channels-summary', {
      params: { project_id: projectId }
    });
    return res.data;
  }
};




