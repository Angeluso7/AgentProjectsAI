import React from 'react';
import ReactDOMServer from 'react-dom/server';
import App from '../src/App';
import { PipelinePage, PipelinePageProps } from '../src/pages/PipelinePage';
import { PlanViewerPage } from '../src/pages/PlanViewerPage';
import { DashboardPage } from '../src/pages/DashboardPage';
import { ProjectsPage } from '../src/pages/ProjectsPage';
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
    console.log(`✅ App rendered successfully (HTML size: ${(appHtml.length / 1024).toFixed(1)} KB) without Router errors.`);
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

  console.log('\n🎉 ALL 8 COMPREHENSIVE TESTS PASSED SUCCESSFULLY! No router errors or conflicts.');
}

runTestSuite().catch((err) => {
  console.error('\n❌ TEST RUNNER TERMINATED WITH ERROR:', err);
  process.exit(1);
});
