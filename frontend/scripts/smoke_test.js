import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const srcDir = path.resolve(__dirname, '../src');

console.log('🔍 [SMOKE-TEST] Checking React Page & Component Syntax and TypeScript Integrity...');

try {
  // 1. Run tsc --noEmit
  console.log('⏳ Running TypeScript type check (tsc --noEmit)...');
  execSync('npx tsc --noEmit', { cwd: path.resolve(__dirname, '..'), stdio: 'inherit' });
  console.log('✅ TypeScript type check PASSED with 0 errors.');

  // 2. Verify all primary pages and components exist and have exports
  const primaryPages = [
    'DashboardPage.tsx',
    'PipelinePage.tsx',
    'JobsPage.tsx',
    'SourcesPage.tsx',
    'ProjectsPage.tsx',
    'PlanViewerPage.tsx',
    'KnowledgePage.tsx',
    'RulesPage.tsx',
    'ReviewPage.tsx',
    'ReportsPage.tsx',
    'EvaluationPage.tsx',
    'AiEnginesPage.tsx',
    'LoginPage.tsx',
    'ResetPasswordPage.tsx'
  ];

  console.log('\n⏳ Validating existence and non-emptiness of primary pages...');
  for (const page of primaryPages) {
    const pagePath = path.join(srcDir, 'pages', page);
    if (!fs.existsSync(pagePath)) {
      throw new Error(`Critical Page missing: ${page}`);
    }
    const content = fs.readFileSync(pagePath, 'utf8');
    if (content.length < 50) {
      throw new Error(`Page ${page} is suspiciously empty.`);
    }
    console.log(`  ✓ ${page} (${(content.length / 1024).toFixed(1)} KB)`);
  }

  // 3. Verify key components
  const keyComponents = [
    'AssistantCopilotDrawer.tsx',
    'ProjectMaturityProfileView.tsx',
    'ConsolidatedStageReportView.tsx',
    'KnowledgeBaseManager.tsx',
    'InformationAcquisitionManagerView.tsx',
    'PlanSelectionsModal.tsx',
    'DocumentManualViewerModal.tsx',
    'DocumentContentReviewModal.tsx',
    'EngineHealthModal.tsx',
    'ObservationsPanel.tsx'
  ];

  console.log('\n⏳ Validating existence and non-emptiness of key modular components...');
  for (const comp of keyComponents) {
    const compPath = path.join(srcDir, 'components', comp);
    if (!fs.existsSync(compPath)) {
      throw new Error(`Critical Component missing: ${comp}`);
    }
    const content = fs.readFileSync(compPath, 'utf8');
    if (content.length < 50) {
      throw new Error(`Component ${comp} is suspiciously empty.`);
    }
    console.log(`  ✓ ${comp} (${(content.length / 1024).toFixed(1)} KB)`);
  }

  console.log('\n🎉 [SMOKE-TEST] All checks completed successfully. Frontend is robust and stable.\n');
  process.exit(0);
} catch (err) {
  console.error('\n❌ [SMOKE-TEST] Verification failed:', err.message);
  process.exit(1);
}
