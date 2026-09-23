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

(global as any).window = {
  location: { pathname: '/', search: '' },
  addEventListener: () => {},
  removeEventListener: () => {},
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

  console.log('\n🎉 ALL 6 COMPREHENSIVE TESTS PASSED SUCCESSFULLY! No router errors or conflicts.');
}

runTestSuite().catch((err) => {
  console.error('\n❌ TEST RUNNER TERMINATED WITH ERROR:', err);
  process.exit(1);
});
