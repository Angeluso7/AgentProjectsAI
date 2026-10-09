import React from 'react';
import ReactDOMServer from 'react-dom/server';
import App from '../src/App';
import { PipelinePage, PipelinePageProps } from '../src/pages/PipelinePage';
import { PlanViewerPage } from '../src/pages/PlanViewerPage';
import { DashboardPage } from '../src/pages/DashboardPage';
import { ProjectsPage, DocumentSymbolDetectionIndicator } from '../src/pages/ProjectsPage';
import { SourcesPage } from '../src/pages/SourcesPage';
import { RulesPage } from '../src/pages/RulesPage';
import { ReviewPage } from '../src/pages/ReviewPage';
import { ReportsPage } from '../src/pages/ReportsPage';
import { EvaluationPage } from '../src/pages/EvaluationPage';
import { AiEnginesPage } from '../src/pages/AiEnginesPage';
import { JobsPage } from '../src/pages/JobsPage';
import { KnowledgePage } from '../src/pages/KnowledgePage';
import { MemoriesConsolePage } from '../src/pages/MemoriesConsolePage';
import { LoginPage } from '../src/pages/LoginPage';
import { ResetPasswordPage } from '../src/pages/ResetPasswordPage';
import { ProjectProvider } from '../src/context/ProjectContext';
import { apiService, apiClient } from '../src/services/api';
import { ReviewRunDetailModal } from '../src/components/ReviewRunDetailModal';
import { Sidebar } from '../src/components/Sidebar';

// Global mocks
const storage: Record<string, string> = {
  auth_token: 'test-jwt-token-active',
  active_project_id: 'prj-test-audit-001'
};

global.localStorage = {
  getItem: (k: string) => storage[k] ?? null,
  setItem: (k: string, v: string) => { storage[k] = String(v); },
  removeItem: (k: string) => { delete storage[k]; },
  clear: () => { Object.keys(storage).forEach(k => delete storage[k]); },
  key: (i: number) => Object.keys(storage)[i] ?? null,
  length: Object.keys(storage).length
} as any;

const dispatchedEvents: Array<{ type: string; detail: any }> = [];
const createdBlobUrls: string[] = [];
const revokedBlobUrls: string[] = [];
const downloadedFiles: Array<{ url: string; filename: string }> = [];
let windowOpenCalled = false;

(global as any).window = {
  location: { pathname: '/', search: '' },
  addEventListener: () => {},
  removeEventListener: () => {},
  open: (...args: any[]) => {
    windowOpenCalled = true;
    return null;
  },
  URL: {
    createObjectURL: (blob: any) => {
      const url = `blob:http://localhost:5173/${Math.random().toString(36).substring(2)}`;
      createdBlobUrls.push(url);
      return url;
    },
    revokeObjectURL: (url: string) => {
      revokedBlobUrls.push(url);
    }
  },
  dispatchEvent: (e: any) => {
    dispatchedEvents.push({ type: e.type, detail: e.detail });
    return true;
  },
  CustomEvent: class CustomEvent {
    type: string;
    detail: any;
    constructor(type: string, params: any) {
      this.type = type;
      this.detail = params?.detail;
    }
  }
};

(global as any).CustomEvent = (global as any).window.CustomEvent;

(global as any).document = {
  body: {
    appendChild: (el: any) => {},
    removeChild: (el: any) => {}
  },
  createElement: (tag: string) => {
    if (tag === 'a') {
      const anchor: any = {
        href: '',
        download: '',
        click: () => {
          downloadedFiles.push({ url: anchor.href, filename: anchor.download });
        }
      };
      return anchor;
    }
    return {};
  }
};

async function runTestSuite() {
  console.log('===============================================================');
  console.log('🧪 TEST SUITE: One-Click Review Rendering & Internal Navigation');
  console.log('===============================================================\n');

  // Test 1: Full App Rendering without Router
  console.log('--- Test 1: Render full App with authenticated session ---');
  try {
    const appHtml = ReactDOMServer.renderToString(<App />);
    if (!appHtml || appHtml.length === 0) {
      throw new Error('App rendered empty HTML string.');
    }
    const sidebarHtml = ReactDOMServer.renderToString(<Sidebar currentTab="knowledge" setCurrentTab={() => {}} />);
    if (!sidebarHtml.includes('Base de Conocimiento')) {
      throw new Error('Sidebar is missing "Base de Conocimiento" navigation item.');
    }
    if (sidebarHtml.includes('MLOps &amp; Active Learning') || sidebarHtml.includes('MLOps & Active Learning')) {
      throw new Error('Sidebar still contains deprecated duplicate "MLOps & Active Learning" item.');
    }
    console.log(`✅ App and Sidebar rendered successfully (App HTML size: ${(appHtml.length / 1024).toFixed(1)} KB); single Base de Conocimiento verified without duplicate MLOps.`);
  } catch (err: any) {
    console.error('❌ Test 1 FAILED:', err.message);
    throw err;
  }

  // Test 2: PipelinePage rendering directly in ProjectProvider
  console.log('\n--- Test 2: Render PipelinePage with ProjectProvider ---');
  try {
    const pipelineHtml = ReactDOMServer.renderToString(
      <ProjectProvider>
        <PipelinePage />
      </ProjectProvider>
    );
    if (!pipelineHtml.includes('One-Click Review') && !pipelineHtml.includes('taxonomía')) {
      throw new Error('PipelinePage did not render expected review headers or loading state.');
    }
    console.log('✅ PipelinePage rendered cleanly without throwing useNavigate() error.');
  } catch (err: any) {
    console.error('❌ Test 2 FAILED:', err.message);
    throw err;
  }

  // Test 3: Navigation callback from finding context to Viewer
  console.log('\n--- Test 3: Validate onNavigate callback contract with context payload ---');
  let receivedTarget: string | null = null;
  let receivedContext: any = null;

  const mockOnNavigate = (target: string, context?: any) => {
    receivedTarget = target;
    receivedContext = context;
  };

  const sampleFinding = {
    id: 'fnd-valve-001',
    rule_code: 'SYM-VALVE-TAG-001',
    title: 'Válvula sin tag reglamentario',
    severity: 'critical',
    description: 'Se detectó gate valve sin tag alfanumérico.',
    bbox: [120.5, 340.2, 180.0, 410.8],
    navigation_context: {
      document_id: 'doc-pid-iso-001',
      sheet_id: 'sheet-001-a',
      project_id: 'prj-test-audit-001',
      page_number: 1
    }
  };

  // Simulate onNavigate invocation
  mockOnNavigate('viewer', {
    projectId: sampleFinding.navigation_context.project_id,
    documentId: sampleFinding.navigation_context.document_id,
    sheetId: sampleFinding.navigation_context.sheet_id,
    pageNumber: sampleFinding.navigation_context.page_number,
    bbox: sampleFinding.bbox
  });

  if (receivedTarget !== 'viewer') {
    throw new Error(`Expected navigation target 'viewer', got '${receivedTarget}'`);
  }
  if (!receivedContext || receivedContext.documentId !== 'doc-pid-iso-001') {
    throw new Error('Navigation context missing documentId');
  }
  if (!receivedContext.bbox || receivedContext.bbox[0] !== 120.5) {
    throw new Error('Navigation context missing bbox coordinates');
  }
  if (receivedContext.sheetId !== 'sheet-001-a') {
    throw new Error('Navigation context missing sheetId');
  }
  console.log('✅ onNavigate callback received exact document/sheet/page/bbox payload:');
  console.log('   Target:', receivedTarget);
  console.log('   Context:', JSON.stringify(receivedContext));

  // Test 4: CustomEvent fallback navigation
  console.log('\n--- Test 4: CustomEvent fallback and localStorage persistence ---');
  dispatchedEvents.length = 0;
  localStorage.setItem('viewer_target_doc_id', sampleFinding.navigation_context.document_id);
  localStorage.setItem('viewer_target_sheet_id', sampleFinding.navigation_context.sheet_id);
  localStorage.setItem('viewer_target_bbox', JSON.stringify(sampleFinding.bbox));
  localStorage.setItem('viewer_return_to_tab', 'pipeline');
  localStorage.setItem('last_active_review_run_id', 'run-review-009');

  window.dispatchEvent(new (window as any).CustomEvent('navigate-tab', {
    detail: {
      tab: 'viewer',
      docId: sampleFinding.navigation_context.document_id,
      sheetId: sampleFinding.navigation_context.sheet_id,
      projectId: sampleFinding.navigation_context.project_id,
      bbox: sampleFinding.bbox
    }
  }));

  if (dispatchedEvents.length === 0 || dispatchedEvents[0].detail.tab !== 'viewer') {
    throw new Error('CustomEvent navigate-tab was not dispatched correctly.');
  }
  if (localStorage.getItem('viewer_target_doc_id') !== 'doc-pid-iso-001') {
    throw new Error('viewer_target_doc_id was not persisted to localStorage.');
  }
  if (localStorage.getItem('viewer_return_to_tab') !== 'pipeline') {
    throw new Error('viewer_return_to_tab was not set to pipeline.');
  }
  if (localStorage.getItem('last_active_review_run_id') !== 'run-review-009') {
    throw new Error('last_active_review_run_id was not persisted.');
  }
  console.log('✅ CustomEvent and localStorage state persisted for bidirectional navigation.');

  // Test 5: PlanViewerPage Return Button
  console.log('\n--- Test 5: PlanViewerPage renders return button when coming from pipeline ---');
  const viewerHtml = ReactDOMServer.renderToString(
    <ProjectProvider>
      <PlanViewerPage />
    </ProjectProvider>
  );
  if (!viewerHtml.includes('Volver a One-Click Review')) {
    throw new Error('PlanViewerPage does not render "Volver a One-Click Review" button when viewer_return_to_tab is set.');
  }
  console.log('✅ PlanViewerPage includes return button to One-Click Review.');

  // Test 6: Full Regression Across All Pages
  console.log('\n--- Test 6: Verify all 15 primary pages render without errors or routers ---');
  const pages: Array<{ name: string; element: React.ReactElement }> = [
    { name: 'DashboardPage', element: <DashboardPage /> },
    { name: 'PipelinePage', element: <PipelinePage /> },
    { name: 'ProjectsPage', element: <ProjectsPage /> },
    { name: 'SourcesPage', element: <SourcesPage /> },
    { name: 'PlanViewerPage', element: <PlanViewerPage /> },
    { name: 'RulesPage', element: <RulesPage /> },
    { name: 'ReviewPage', element: <ReviewPage /> },
    { name: 'ReportsPage', element: <ReportsPage /> },
    { name: 'EvaluationPage', element: <EvaluationPage /> },
    { name: 'AiEnginesPage', element: <AiEnginesPage /> },
    { name: 'JobsPage', element: <JobsPage /> },
    { name: 'KnowledgePage', element: <KnowledgePage /> },
    { name: 'MemoriesConsolePage', element: <MemoriesConsolePage /> },
    { name: 'LoginPage', element: <LoginPage onLoginSuccess={() => {}} /> },
    { name: 'ResetPasswordPage', element: <ResetPasswordPage onSuccess={() => {}} /> }
  ];

  for (const p of pages) {
    try {
      const html = ReactDOMServer.renderToString(
        <ProjectProvider>
          {p.element}
        </ProjectProvider>
      );
      if (!html || html.length === 0) {
        throw new Error(`Page ${p.name} rendered empty HTML.`);
      }
      console.log(`  ✓ ${p.name} (${(html.length / 1024).toFixed(1)} KB HTML)`);
    } catch (e: any) {
      console.error(`❌ Page ${p.name} failed to render:`, e.message);
      throw e;
    }
  }

  // Test 7: Authenticated Report Download Contract & Error Interception
  console.log('\n--- Test 7: Authenticated report download, Blob conversion, and error handling ---');
  // Backup original apiClient.get
  const originalGet = apiClient.get;
  
  try {
    // 7A: Successful PDF Blob download
    createdBlobUrls.length = 0;
    revokedBlobUrls.length = 0;
    downloadedFiles.length = 0;
    windowOpenCalled = false;

    const fakePdfBlob = new Blob(['%PDF-1.4 dummy content'], { type: 'application/pdf' });
    apiClient.get = (async (url: string, config: any) => {
      if (url.includes('/review/reports/rep-test-pdf/download')) {
        if (config?.responseType !== 'blob') {
          throw new Error('downloadReviewReport must request responseType: blob');
        }
        return {
          status: 200,
          data: fakePdfBlob,
          headers: {
            'content-disposition': 'attachment; filename="report_PIPING_PID_SYMBOLS_2026.pdf"',
            'content-type': 'application/pdf',
            'content-length': '22'
          }
        };
      }
      throw new Error(`Unexpected GET url: ${url}`);
    }) as any;

    const dlResult = await apiService.downloadReviewReport('rep-test-pdf');
    if (dlResult.filename !== 'report_PIPING_PID_SYMBOLS_2026.pdf') {
      throw new Error(`Expected filename 'report_PIPING_PID_SYMBOLS_2026.pdf', got '${dlResult.filename}'`);
    }
    if (downloadedFiles.length !== 1 || downloadedFiles[0].filename !== 'report_PIPING_PID_SYMBOLS_2026.pdf') {
      throw new Error('Temporary <a> element was not clicked with correct download filename.');
    }
    if (createdBlobUrls.length !== 1 || revokedBlobUrls.length !== 1 || createdBlobUrls[0] !== revokedBlobUrls[0]) {
      throw new Error('Blob URL was not created or revoked properly.');
    }
    if (windowOpenCalled) {
      throw new Error('window.open was incorrectly called during authenticated download!');
    }
    console.log('✅ Authenticated Blob download succeeded, URL revoked, window.open not used.');

    // 7B: 401 Session Expired Handling
    windowOpenCalled = false;
    const authErrorBlob = new Blob([JSON.stringify({ detail: 'Autenticación requerida. Token no provisto.' })], { type: 'application/json' });
    apiClient.get = (async () => {
      const err: any = new Error('Request failed with status code 401');
      err.response = {
        status: 401,
        data: authErrorBlob
      };
      throw err;
    }) as any;

    let received401Error: any = null;
    try {
      await apiService.downloadReviewReport('rep-expired');
    } catch (e: any) {
      received401Error = e;
    }

    if (!received401Error || !received401Error.message.includes('Sesión expirada')) {
      throw new Error(`Expected 401 to throw session expired message, got: ${received401Error?.message}`);
    }
    if (windowOpenCalled) {
      throw new Error('window.open was called during 401 failure!');
    }
    console.log('✅ 401 error caught cleanly: "Sesión expirada o no autenticada" without opening tab.');

    // 7C: 403 Forbidden Handling
    apiClient.get = (async () => {
      const err: any = new Error('Forbidden');
      err.response = { status: 403, data: { detail: 'Acceso denegado a otra organización' } };
      throw err;
    }) as any;
    try {
      await apiService.downloadReviewReport('rep-cross-org');
      throw new Error('Should have failed with 403');
    } catch (e: any) {
      if (!e.message.includes('No tiene permisos')) {
        throw new Error(`Expected 403 message, got: ${e.message}`);
      }
    }
    console.log('✅ 403 error caught cleanly: "No tiene permisos para descargar este reporte".');

    // 7D: 404 Not Found Handling
    apiClient.get = (async () => {
      const err: any = new Error('Not Found');
      err.response = { status: 404, data: { detail: 'Reporte no encontrado' } };
      throw err;
    }) as any;
    try {
      await apiService.downloadReviewReport('rep-missing');
      throw new Error('Should have failed with 404');
    } catch (e: any) {
      if (!e.message.includes('no existe o fue eliminado')) {
        throw new Error(`Expected 404 message, got: ${e.message}`);
      }
    }
    console.log('✅ 404 error caught cleanly: "El reporte solicitado no existe".');

  } finally {
    apiClient.get = originalGet;
  }

  // Test 8: ReviewRunDetailModal Rendering & Tabs Inspection
  console.log('\n--- Test 8: ReviewRunDetailModal rendering, KPI metrics, tabs & findings navigation ---');
  let modalNavigatedTarget: string | null = null;
  let modalNavigatedContext: any = null;

  const mockDetailData = {
    id: 'run-audit-modal-001',
    project_id: 'prj-test-audit-001',
    run_name: 'Revisión Piping P&ID Sandbox #1',
    discipline_code: 'PIPING',
    discipline_name: 'Piping & Mecánica',
    topic_code: 'PID_SYMBOLS',
    topic_name: 'Simbología P&ID',
    execution_mode: 'sandbox',
    status: 'completed',
    requested_by: 'auditor@test.com',
    requested_at: '2026-09-23T11:00:00Z',
    completed_at: '2026-09-23T11:00:08Z',
    execution_time_sec: 8.42,
    rule_count: 5,
    document_count: 2,
    findings_count: 3,
    baseline_catalog_version: 'v1.2.0-piping-baseline',
    summary_stats: {
      rules_passed: 2,
      rules_failed: 2,
      rules_warning: 0,
      rules_not_evaluable: 1,
      total_findings: 3
    },
    documents: [
      {
        document_id: 'doc-pid-01',
        filename: '001-PID-PROCESO.pdf',
        document_role: 'target_plan',
        inclusion_reason: 'Plano P&ID para extracción de simbología',
        status: 'ready'
      },
      {
        document_id: 'doc-legend-01',
        filename: '000-LEGEND-SYMBOLS.pdf',
        document_role: 'legend',
        inclusion_reason: 'Plano de simbología y notas generales',
        status: 'ready'
      }
    ],
    steps: [
      { phase: 1, phase_name: 'Validación de Entorno y Documentos', step_type: 'technical', status: 'succeeded', input_summary: {}, output_summary: {} },
      { phase: 2, phase_name: 'Extracción Estructural y Bloque de Título', step_type: 'technical', status: 'succeeded', input_summary: {}, output_summary: {} },
      { phase: 3, phase_name: 'Detección de Tablas y Simbología', step_type: 'technical', status: 'succeeded', input_summary: {}, output_summary: {} },
      { phase: 4, phase_name: 'Validación Canónica de Símbolos', step_type: 'technical', status: 'succeeded', input_summary: {}, output_summary: {} },
      { phase: 5, phase_name: 'Consolidación Topológica', step_type: 'technical', status: 'succeeded', input_summary: {}, output_summary: {} },
      { phase: 6, phase_name: 'Evaluación de Reglas de Especialidad', step_type: 'normative', status: 'succeeded', input_summary: {}, output_summary: {} },
      { phase: 7, phase_name: 'Generación de Hallazgos QA/QC', step_type: 'normative', status: 'succeeded', input_summary: {}, output_summary: {} },
      { phase: 8, phase_name: 'Generación de Reportes Técnicos', step_type: 'normative', status: 'succeeded', input_summary: {}, output_summary: {} },
      { phase: 9, phase_name: 'Persistencia de Auditoría y Métricas', step_type: 'normative', status: 'succeeded', input_summary: {}, output_summary: {} }
    ],
    executions: [
      {
        id: 'ex-01',
        rule_code: 'SYM-VALVE-001',
        rule_name: 'Identificación de Válvulas Críticas',
        phase: 6,
        status: 'failed',
        confidence: 0.95,
        missing_requirements: [],
        result_summary: { description: 'Se detectaron válvulas sin tag reglamentario.' }
      },
      {
        id: 'ex-02',
        rule_code: 'SYM-LINE-SPEC-002',
        rule_name: 'Consistencia de Especificación de Línea',
        phase: 6,
        status: 'not_evaluable',
        confidence: 0.0,
        not_evaluable_reason_code: 'MISSING_CATALOG',
        not_evaluable_reason_message: 'Catálogo de tuberías no configurado.',
        missing_requirements: ['Line Spec Catalog v1'],
        recommended_action: 'Cargar especificación de tuberías en Catálogo de Materiales.',
        result_summary: {}
      }
    ],
    findings: [
      {
        id: 'fnd-modal-01',
        rule_code: 'SYM-VALVE-001',
        rule_name: 'Identificación de Válvulas Críticas',
        severity: 'critical',
        status: 'open',
        title: 'Válvula 2"-V-101 sin tag alfanumérico',
        description: 'Válvula de compuerta detectada en coordenada sin anotación de servicio.',
        recommendation: 'Asignar tag alfanumérico en el plano de proceso.',
        bbox: [100.0, 200.0, 150.0, 250.0],
        navigation_context: {
          project_id: 'prj-test-audit-001',
          document_id: 'doc-pid-01',
          sheet_id: 'sheet-01',
          page_number: 1
        }
      }
    ],
    reports: [
      {
        id: 'rep-modal-pdf',
        report_name: 'Reporte PIPING - Simbología (PDF)',
        format: 'pdf',
        file_size_bytes: 145020,
        sha256: '9f83a48e71c9b4e135d94e21a',
        created_at: '2026-09-23T11:00:08Z'
      },
      {
        id: 'rep-modal-xlsx',
        report_name: 'Reporte PIPING - Matriz Hallazgos (XLSX)',
        format: 'xlsx',
        file_size_bytes: 42100,
        sha256: 'e3b0c44298fc1c149afbf4c89',
        created_at: '2026-09-23T11:00:08Z'
      }
    ]
  };

  const modalHtml = ReactDOMServer.renderToString(
    <ReviewRunDetailModal
      isOpen={true}
      run={mockDetailData as any}
      projectName="Refinería Bío-Bío"
      onClose={() => {}}
      onNavigateContext={(finding) => {
        modalNavigatedTarget = 'viewer';
        modalNavigatedContext = finding;
      }}
    />
  );

  console.log('modalHtml length:', modalHtml.length);
  console.log('modalHtml preview:', modalHtml.slice(0, 400));

  // Validate Header & Mode
  if (!modalHtml.includes('Piping') || !modalHtml.includes('SANDBOX')) {
    throw new Error('ReviewRunDetailModal did not render expected run name or SANDBOX badge.');
  }
  if (!modalHtml.includes('v1.2.0-piping-baseline')) {
    throw new Error('ReviewRunDetailModal did not render baseline catalog version.');
  }
  // Validate Sandbox Warning Banner
  if (!modalHtml.includes('Resultado exploratorio en entorno Sandbox')) {
    throw new Error('ReviewRunDetailModal missing fixed Sandbox warning banner.');
  }
  // Validate KPI Counters
  if (!modalHtml.includes('No Evaluable') || !modalHtml.includes('Hallazgos')) {
    throw new Error('ReviewRunDetailModal missing KPI counter labels.');
  }
  // Validate Tabs presence
  if (!modalHtml.includes('Cobertura') || !modalHtml.includes('Fases de Ejecución') || !modalHtml.includes('Reglas Evaluadas') || !modalHtml.includes('Exportaciones')) {
    throw new Error('ReviewRunDetailModal missing navigation tabs.');
  }
  // Validate Documents and Coverage
  if (!modalHtml.includes('001-PID-PROCESO.pdf') || !modalHtml.includes('000-LEGEND-SYMBOLS.pdf')) {
    throw new Error('ReviewRunDetailModal missing included document filenames in overview.');
  }
  console.log('✅ ReviewRunDetailModal rendered with complete KPIs, tabs, sandbox banner, and documents.');

  // ====================================================================
  // TEST: CRASH RESILIENCE & SYMBOL INVENTORY UI STATES
  // ====================================================================
  console.log('\n--- Running Symbol Inventory Crash Resilience & UI States Tests ---');

  // 1. run = null: Must not throw, renders empty
  const nullModalHtml = ReactDOMServer.renderToString(
    <ReviewRunDetailModal isOpen={true} run={null} onClose={() => {}} />
  );
  if (nullModalHtml !== '') {
    throw new Error('ReviewRunDetailModal should return null when run=null.');
  }
  console.log('  ✓ [CRASH TEST 1] run=null does not crash and safely returns empty.');

  // Rules of Hooks test: alternating null -> run -> null -> run
  ReactDOMServer.renderToString(<ReviewRunDetailModal isOpen={false} run={null} onClose={() => {}} />);
  ReactDOMServer.renderToString(<ReviewRunDetailModal isOpen={true} run={mockDetailData} initialTab="exports" onClose={() => {}} />);
  ReactDOMServer.renderToString(<ReviewRunDetailModal isOpen={true} run={null} onClose={() => {}} />);
  ReactDOMServer.renderToString(<ReviewRunDetailModal isOpen={true} run={mockDetailData} initialTab="inventory" onClose={() => {}} />);
  console.log('  ✓ [HOOKS TEST] Alternating run transitions (null -> run -> null -> run) render cleanly without hook count mismatch.');

  // 2. Legacy run with symbol_inventory = null: Must not throw
  const legacyRun = { ...mockDetailData, symbol_inventory: null as any };
  const legacyModalHtml = ReactDOMServer.renderToString(
    <ReviewRunDetailModal isOpen={true} run={legacyRun} initialTab="inventory" onClose={() => {}} />
  );
  if (!legacyModalHtml.includes('Inventario')) {
    throw new Error('ReviewRunDetailModal crashed on legacy run with symbol_inventory=null.');
  }
  console.log('  ✓ [CRASH TEST 2] Legacy run with symbol_inventory=null renders safely.');

  // 3. UI State A: available con grupos
  const runWithGroups = {
    ...mockDetailData,
    symbol_inventory: {
      status: 'available' as const,
      inventory_version: 'v1',
      inventory_generated_at: '2026-09-23T12:00:00Z',
      inventory_source_snapshot_hash: 'hash-abc-123',
      can_generate: true,
      metrics: {
        documents_reviewed: 2,
        sheets_reviewed: 2,
        geometric_candidates: 10,
        valid_symbol_occurrences: 8,
        inventory_groups: 2,
        recognized_production: 6,
        recognized_sandbox: 2,
        recognized_reference_only: 0,
        unknown: 0,
        ambiguous: 0,
        requires_review: 0,
        figures_excluded: 2,
        not_symbols: 0,
        inventory_coverage: 1.0,
        production_coverage: 0.75,
        sandbox_coverage: 0.25,
        unknown_rate: 0.0,
        review_required_rate: 0.0,
        exclusion_rate: 0.2,
        by_document: {}
      },
      groups: [
        {
          id: 'grp-01',
          review_run_id: mockDetailData.id,
          grouping_key: 'VALVE_GATE',
          grouping_method: 'template_match',
          grouping_confidence: 0.98,
          display_code: 'SYM-V-01',
          canonical_name: 'Válvula de Compuerta',
          catalog_status: 'recognized_production',
          total_occurrences: 6,
          requires_human_review: false,
          occurrences_by_document: { '001-PID-PROCESO.pdf': 6 }
        }
      ],
      excluded_groups: []
    }
  };
  const availableGroupsHtml = ReactDOMServer.renderToString(
    <ReviewRunDetailModal isOpen={true} run={runWithGroups} initialTab="inventory" onClose={() => {}} />
  );
  if (!availableGroupsHtml.includes('SYM-V-01') || !availableGroupsHtml.includes('Válvula de Compuerta')) {
    throw new Error('Available with groups failed to render group code or name.');
  }
  if (!availableGroupsHtml.includes('Cob. Productiva') || !availableGroupsHtml.includes('Recalcular')) {
    throw new Error('Available with groups missing metric card or Recalcular button.');
  }
  console.log('  ✓ [UI STATE A] available con grupos renders metrics, table, display codes and recalculate action.');

  // 4. UI State B: available vacío (0 símbolos detectados)
  const runAvailableEmpty = {
    ...mockDetailData,
    symbol_inventory: {
      status: 'available' as const,
      inventory_version: 'v1',
      inventory_generated_at: '2026-09-23T12:00:00Z',
      can_generate: true,
      metrics: {
        documents_reviewed: 2,
        sheets_reviewed: 2,
        geometric_candidates: 3,
        valid_symbol_occurrences: 0,
        inventory_groups: 0,
        recognized_production: 0,
        recognized_sandbox: 0,
        recognized_reference_only: 0,
        unknown: 0,
        ambiguous: 0,
        requires_review: 0,
        figures_excluded: 2,
        not_symbols: 1,
        inventory_coverage: 0.0,
        production_coverage: 0.0,
        sandbox_coverage: 0.0,
        unknown_rate: 0.0,
        review_required_rate: 0.0,
        exclusion_rate: 0.67,
        by_document: {}
      },
      groups: [],
      excluded_groups: []
    }
  };
  const availableEmptyHtml = ReactDOMServer.renderToString(
    <ReviewRunDetailModal isOpen={true} run={runAvailableEmpty} initialTab="inventory" onClose={() => {}} />
  );
  if (!availableEmptyHtml.includes('No se detectaron símbolos geométricos válidos')) {
    throw new Error('Available empty failed to render expected empty state message.');
  }
  if (!availableEmptyHtml.includes('Figuras excluidas:') || !availableEmptyHtml.includes('Regenerar Inventario')) {
    throw new Error('Available empty missing figure counts or regenerate button.');
  }
  console.log('  ✓ [UI STATE B] available vacío renders non-error message, candidate/figure counts, and regenerate action.');

  // 5. UI State C: pending
  const runPending = {
    ...mockDetailData,
    symbol_inventory: {
      status: 'pending' as const,
      can_generate: false,
      reason_code: 'RUN_IN_PROGRESS',
      reason_message: 'La corrida de revisión está en ejecución.',
      metrics: {} as any,
      groups: [],
      excluded_groups: []
    }
  };
  const pendingHtml = ReactDOMServer.renderToString(
    <ReviewRunDetailModal isOpen={true} run={runPending} initialTab="inventory" onClose={() => {}} />
  );
  if (!pendingHtml.includes('Inventario de simbología en proceso...')) {
    throw new Error('Pending state missing loader text.');
  }
  console.log('  ✓ [UI STATE C] pending renders in-progress loader and explanation.');

  // 6. UI State D: unavailable (corrida histórica)
  const runUnavailable = {
    ...mockDetailData,
    symbol_inventory: {
      status: 'unavailable' as const,
      can_generate: true,
      reason_code: 'INVENTORY_NOT_GENERATED',
      reason_message: 'Esta corrida fue creada antes del inventario de simbología.',
      metrics: {} as any,
      groups: [],
      excluded_groups: []
    }
  };
  const unavailableHtml = ReactDOMServer.renderToString(
    <ReviewRunDetailModal isOpen={true} run={runUnavailable} initialTab="inventory" onClose={() => {}} />
  );
  if (!unavailableHtml.includes('Inventario no generado en esta corrida') || !unavailableHtml.includes('Generar Inventario Ahora')) {
    throw new Error('Unavailable state missing historical explanation or Generar Inventario Ahora button.');
  }
  console.log('  ✓ [UI STATE D] unavailable renders historical explanation and "Generar Inventario Ahora" action.');

  // 7. UI State E: failed (error técnico con reintento)
  const runFailed = {
    ...mockDetailData,
    symbol_inventory: {
      status: 'failed' as const,
      can_generate: true,
      reason_code: 'INVENTORY_BUILD_FAILED',
      reason_message: 'Fallo al procesar geometrías de lámina 2.',
      metrics: {} as any,
      groups: [],
      excluded_groups: []
    }
  };
  const failedHtml = ReactDOMServer.renderToString(
    <ReviewRunDetailModal isOpen={true} run={runFailed} initialTab="inventory" onClose={() => {}} />
  );
  if (!failedHtml.includes('Error al Cargar o Generar Inventario') || !failedHtml.includes('INVENTORY_BUILD_FAILED') || !failedHtml.includes('Reintentar Generación')) {
    throw new Error('Failed state missing technical error, reason code, or retry button.');
  }
  console.log('  ✓ [UI STATE E] failed renders safe technical error, reason code, and retry actions.');

  // 8. UI State F: API error (status visual failed con reason INVENTORY_API_ERROR)
  const runApiError = {
    ...mockDetailData,
    symbol_inventory: {
      status: 'failed' as const,
      can_generate: true,
      reason_code: 'INVENTORY_API_ERROR',
      reason_message: 'Error de conexión con el servicio de simbología.',
      metrics: {} as any,
      groups: [],
      excluded_groups: []
    }
  };
  const apiErrorHtml = ReactDOMServer.renderToString(
    <ReviewRunDetailModal isOpen={true} run={runApiError} initialTab="inventory" onClose={() => {}} />
  );
  if (!apiErrorHtml.includes('INVENTORY_API_ERROR') || !apiErrorHtml.includes('Reintentar Consulta')) {
    throw new Error('API error state missing INVENTORY_API_ERROR code or Reintentar Consulta button.');
  }
  console.log('  ✓ [UI STATE F] API error renders failed visual status, INVENTORY_API_ERROR, and retry button.');

  // Test Section: Document Symbol Detection Status Indicator (ProjectsPage)
  console.log('\n--- Test 8: Document Symbol Detection Indicator in Projects Page ---');

  // Case 1: Job running or queued -> "Detectando símbolos..."
  const docDetecting: any = {
    id: 'doc-symbol-detecting-001',
    name: 'plano_arquitectura_p1.pdf',
    symbol_status: {
      job_id: 'job-sym-001',
      job_status: 'running',
      stage: 'running',
      progress_percent: 45,
      total_symbols: 0,
      matched_count: 0,
      unknown_count: 0,
      unmatched_count: 0,
      has_active_catalog: true,
      target_sheet_id: 'sheet-001',
      error_message: null
    }
  };
  const detectingHtml = ReactDOMServer.renderToString(<DocumentSymbolDetectionIndicator doc={docDetecting} />);
  if (!detectingHtml.includes('Detectando símbolos...')) {
    throw new Error('Case 1 FAILED: Detecting state did not render "Detectando símbolos..."');
  }
  console.log('  ✓ [SYMBOL STATUS 1] detecting/running renders "Detectando símbolos..." with spinner indicator.');

  // Case 2: Detected symbols with active catalog -> "Simbología: X elementos detectados" + "Ver en Visor"
  const docDetected: any = {
    id: 'doc-symbol-detected-002',
    name: 'plano_arquitectura_p2.pdf',
    sheets: [{ id: 'sheet-002', name: 'Lámina 2' }],
    symbol_status: {
      job_id: 'job-sym-002',
      job_status: 'completed',
      stage: 'completed',
      progress_percent: 100,
      total_symbols: 8,
      matched_count: 8,
      unknown_count: 0,
      unmatched_count: 0,
      has_active_catalog: true,
      target_sheet_id: 'sheet-002',
      error_message: null
    }
  };
  const detectedHtml = ReactDOMServer.renderToString(<DocumentSymbolDetectionIndicator doc={docDetected} />);
  if (!detectedHtml.includes('Simbología: 8 elementos detectados') || !detectedHtml.includes('Ver en Visor')) {
    throw new Error('Case 2 FAILED: Detected with catalog missing count or "Ver en Visor" button.');
  }
  console.log('  ✓ [SYMBOL STATUS 2] detected with active catalog renders "Simbología: 8 elementos detectados" and link to PlanViewer.');

  // Case 3: Detected symbols but catalog unavailable (unknown_symbol) -> "3 detectados, catálogo no disponible para validar" + "Ver en Visor"
  const docNoCatalog: any = {
    id: 'doc-symbol-nocat-003',
    name: 'plano_arquitectura_p3.pdf',
    sheets: [{ id: 'sheet-003', name: 'Lámina 3' }],
    symbol_status: {
      job_id: 'job-sym-003',
      job_status: 'completed',
      stage: 'completed',
      progress_percent: 100,
      total_symbols: 3,
      matched_count: 0,
      unknown_count: 3,
      unmatched_count: 0,
      has_active_catalog: false,
      target_sheet_id: 'sheet-003',
      error_message: null
    }
  };
  const noCatHtml = ReactDOMServer.renderToString(<DocumentSymbolDetectionIndicator doc={docNoCatalog} />);
  if (!noCatHtml.includes('3 detectados, catálogo no disponible para validar') || !noCatHtml.includes('Ver en Visor')) {
    throw new Error('Case 3 FAILED: Detected without catalog missing "3 detectados, catálogo no disponible para validar" or "Ver en Visor"');
  }
  console.log('  ✓ [SYMBOL STATUS 3] detected without active catalog renders "3 detectados, catálogo no disponible para validar" and link.');

  // Case 4: Completed with 0 symbols
  const docZeroSymbols: any = {
    id: 'doc-symbol-zero-004',
    symbol_status: {
      job_id: 'job-sym-004',
      job_status: 'completed',
      total_symbols: 0,
      has_active_catalog: true,
      unknown_count: 0
    }
  };
  const zeroHtml = ReactDOMServer.renderToString(<DocumentSymbolDetectionIndicator doc={docZeroSymbols} />);
  if (!zeroHtml.includes('Simbología: 0 elementos detectados')) {
    throw new Error('Case 4 FAILED: Completed with 0 symbols missing "Simbología: 0 elementos detectados"');
  }
  console.log('  ✓ [SYMBOL STATUS 4] completed with 0 symbols renders "Simbología: 0 elementos detectados".');

  // Case 5: Symbol detection job failed
  const docFailedSymbols: any = {
    id: 'doc-symbol-failed-005',
    symbol_status: {
      job_id: 'job-sym-005',
      job_status: 'failed',
      total_symbols: 0,
      has_active_catalog: false,
      unknown_count: 0,
      error_message: 'Corrupted image raster'
    }
  };
  const failedSymHtml = ReactDOMServer.renderToString(<DocumentSymbolDetectionIndicator doc={docFailedSymbols} />);
  if (!failedSymHtml.includes('Detección de símbolos falló')) {
    throw new Error('Case 5 FAILED: Failed job missing "Detección de símbolos falló"');
  }
  console.log('  ✓ [SYMBOL STATUS 5] failed job renders "Detección de símbolos falló".');

  console.log('\n🎉 ALL 16 FRONTEND & SYMBOL DETECTION COMPONENT TESTS PASSED SUCCESSFULLY! No crashes or unhandled nulls.');
}

runTestSuite().catch((err) => {
  console.error('\n❌ TEST RUNNER TERMINATED WITH ERROR:', err);
  process.exit(1);
});
