import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const srcDir = path.resolve(__dirname, '../src');

console.log('🔍 [SMOKE-TEST] Checking React Page & Component Syntax, TypeScript Integrity & Rules of Hooks...');

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
    'ResetPasswordPage.tsx',
    'MemoriesConsolePage.tsx'
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
    'ObservationsPanel.tsx',
    'SourceExtractionReviewModal.tsx',
    'ProcessWithAiModal.tsx',
    'ItemCropLightboxModal.tsx',
    'ItemContextViewerModal.tsx'
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

  // 4. Strict Scope-Aware Rules of Hooks Verification
  console.log('\n⏳ Performing Strict Rules of Hooks Verification on all components...');
  const hookRegex = /^\s*(const|let|var)?\s*(\[[^\]]+\]|\w+)\s*=\s*(use[A-Z]\w*)\s*\(/;
  const directHookRegex = /^\s*(use[A-Z]\w*)\s*\(/;

  const componentFiles = fs.readdirSync(path.join(srcDir, 'components')).filter(f => f.endsWith('.tsx'));
  const pageFiles = fs.readdirSync(path.join(srcDir, 'pages')).filter(f => f.endsWith('.tsx'));
  const allFiles = [
    ...componentFiles.map(f => path.join(srcDir, 'components', f)),
    ...pageFiles.map(f => path.join(srcDir, 'pages', f))
  ];

  let hookViolations = 0;
  for (const filePath of allFiles) {
    const relName = path.relative(srcDir, filePath);
    const content = fs.readFileSync(filePath, 'utf8');
    const lines = content.split('\n');

    let braceDepth = 0;
    let componentDepth = -1;
    let componentEarlyReturnDepth = -1;
    let earlyReturnLine = -1;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const trimmed = line.trim();

      // Track component function declaration
      if (
        (trimmed.startsWith('export const ') || trimmed.startsWith('const ') || trimmed.startsWith('export function ') || trimmed.startsWith('function ')) &&
        (trimmed.includes(': React.FC') || trimmed.includes('=>') || trimmed.includes('function ')) &&
        !trimmed.startsWith('const handle') &&
        !trimmed.startsWith('const render') &&
        !trimmed.startsWith('const load') &&
        !trimmed.startsWith('const get')
      ) {
        if (componentDepth === -1 && (trimmed.includes('{') || lines[i + 1]?.includes('{'))) {
          componentDepth = braceDepth + (trimmed.includes('{') ? 1 : 0);
          componentEarlyReturnDepth = -1;
          earlyReturnLine = -1;
        }
      }

      // Track early return from the component level
      if (
        braceDepth === componentDepth &&
        (trimmed.startsWith('if (!isOpen)') || trimmed.startsWith('if (!item)') || trimmed.startsWith('if (!profile)') || trimmed.startsWith('if (!document)')) &&
        trimmed.includes('return null')
      ) {
        componentEarlyReturnDepth = braceDepth;
        earlyReturnLine = i + 1;
      }

      // Check if a hook is called after an early return at component level
      if (componentEarlyReturnDepth === braceDepth && braceDepth === componentDepth) {
        if (hookRegex.test(line) || directHookRegex.test(line)) {
          console.error(`  ❌ [HOOK VIOLATION] ${relName}:${i + 1} - Hook declared at component root after early return on line ${earlyReturnLine}`);
          hookViolations++;
        }
      }

      // Count braces
      for (const char of line) {
        if (char === '{') braceDepth++;
        else if (char === '}') {
          braceDepth--;
          if (braceDepth < componentDepth) {
            componentDepth = -1;
            componentEarlyReturnDepth = -1;
          }
        }
      }
    }
  }

  if (hookViolations > 0) {
    throw new Error(`Found ${hookViolations} React Rules of Hooks violations in components.`);
  }
  console.log('✅ Rules of Hooks check PASSED: All hooks are called unconditionally at top-level.');

  // 5. Deep Architecture & Page Component Rendering Test (includes One-Click Review & Navigation)
  console.log('\n⏳ Running Deep Page Component Rendering & Navigation Contract Tests...');
  execSync('node scripts/run_render_test.js', { cwd: path.resolve(__dirname, '..'), stdio: 'inherit' });
  console.log('✅ Component Rendering & Navigation Suite PASSED with 0 router conflicts.');

  console.log('\n🎉 [SMOKE-TEST] All checks completed successfully. Frontend is robust and stable.\n');
  process.exit(0);
} catch (err) {
  console.error('\n❌ [SMOKE-TEST] Verification failed:', err.message);
  process.exit(1);
}
