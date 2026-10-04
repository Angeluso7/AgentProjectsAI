/**
 * Script de validación unitaria de la lógica de habilitación del botón en ProjectDeleteModal.
 */
import assert from 'assert';

function normalizeCode(str) {
  if (!str) return '';
  return str.replace(/\s+/g, ' ').trim().toUpperCase();
}

function evaluateCanSubmit({
  projectCode,
  confirmInput,
  activeTab,
  deleteMode,
  acknowledgeLoss,
  impact,
  isProcessing
}) {
  const expectedCode = normalizeCode(projectCode);
  const normalizedInput = normalizeCode(confirmInput);
  const isCodeMatch = normalizedInput === expectedCode && expectedCode.length > 0;

  const isHardDeleteBlocked =
    activeTab === 'delete' &&
    deleteMode === 'hard_delete' &&
    impact?.can_hard_delete === false &&
    (impact.blocking_reasons?.length ?? 0) > 0;

  const isHardDeleteConfirmationValid =
    activeTab === 'delete' &&
    deleteMode === 'hard_delete' &&
    isCodeMatch &&
    acknowledgeLoss &&
    !isHardDeleteBlocked &&
    !isProcessing;

  const isAnonymizeConfirmationValid =
    activeTab === 'delete' &&
    deleteMode === 'anonymize' &&
    isCodeMatch &&
    acknowledgeLoss &&
    !isProcessing;

  const isClearContentValid =
    activeTab === 'clear_content' &&
    isCodeMatch &&
    acknowledgeLoss &&
    !isProcessing;

  return isHardDeleteConfirmationValid || isAnonymizeConfirmationValid || isClearContentValid;
}

console.log('🧪 Iniciando pruebas unitarias de lógica del botón en ProjectDeleteModal...');

// Test 1: Hard delete con código exacto + checkbox marcado + can_hard_delete = true -> ENABLED
{
  const result = evaluateCanSubmit({
    projectCode: 'PRJ-2026-008',
    confirmInput: 'PRJ-2026-008',
    activeTab: 'delete',
    deleteMode: 'hard_delete',
    acknowledgeLoss: true,
    impact: { can_hard_delete: true, blocking_reasons: [] },
    isProcessing: false
  });
  assert.strictEqual(result, true, 'Test 1 falló: debería estar habilitado con código exacto y checkbox');
  console.log('  ✓ Test 1: Código exacto + checkbox + impacto permisivo -> ENABLED');
}

// Test 2: Código con espacios antes y después (trim) -> ENABLED
{
  const result = evaluateCanSubmit({
    projectCode: 'PRJ-2026-008',
    confirmInput: '   PRJ-2026-008   ',
    activeTab: 'delete',
    deleteMode: 'hard_delete',
    acknowledgeLoss: true,
    impact: { can_hard_delete: true, blocking_reasons: [] },
    isProcessing: false
  });
  assert.strictEqual(result, true, 'Test 2 falló: trim debería permitir confirmación');
  console.log('  ✓ Test 2: Código con espacios (trim) -> ENABLED');
}

// Test 3: Código con minúsculas (case-insensitive) -> ENABLED
{
  const result = evaluateCanSubmit({
    projectCode: 'PRJ-2026-008',
    confirmInput: 'prj-2026-008',
    activeTab: 'delete',
    deleteMode: 'hard_delete',
    acknowledgeLoss: true,
    impact: { can_hard_delete: true, blocking_reasons: [] },
    isProcessing: false
  });
  assert.strictEqual(result, true, 'Test 3 falló: case-insensitivity debería permitir confirmación');
  console.log('  ✓ Test 3: Código con minúsculas -> ENABLED');
}

// Test 4: Checkbox sin marcar -> DISABLED
{
  const result = evaluateCanSubmit({
    projectCode: 'PRJ-2026-008',
    confirmInput: 'PRJ-2026-008',
    activeTab: 'delete',
    deleteMode: 'hard_delete',
    acknowledgeLoss: false,
    impact: { can_hard_delete: true, blocking_reasons: [] },
    isProcessing: false
  });
  assert.strictEqual(result, false, 'Test 4 falló: debe requerir checkbox marcado');
  console.log('  ✓ Test 4: Checkbox sin marcar -> DISABLED');
}

// Test 5: Código incorrecto -> DISABLED
{
  const result = evaluateCanSubmit({
    projectCode: 'PRJ-2026-008',
    confirmInput: 'PRJ-2026-009',
    activeTab: 'delete',
    deleteMode: 'hard_delete',
    acknowledgeLoss: true,
    impact: { can_hard_delete: true, blocking_reasons: [] },
    isProcessing: false
  });
  assert.strictEqual(result, false, 'Test 5 falló: código incorrecto debe bloquear el botón');
  console.log('  ✓ Test 5: Código incorrecto -> DISABLED');
}

// Test 6: can_hard_delete = false con blocking reasons en hard_delete -> DISABLED
{
  const result = evaluateCanSubmit({
    projectCode: 'PRJ-2026-008',
    confirmInput: 'PRJ-2026-008',
    activeTab: 'delete',
    deleteMode: 'hard_delete',
    acknowledgeLoss: true,
    impact: { can_hard_delete: false, blocking_reasons: ['Trabajo en ejecución'] },
    isProcessing: false
  });
  assert.strictEqual(result, false, 'Test 6 falló: hard delete debe estar bloqueado si can_hard_delete = false');
  console.log('  ✓ Test 6: can_hard_delete = false en modo hard_delete -> DISABLED');
}

// Test 7: Anonymize habilitado aun si hard_delete está bloqueado -> ENABLED
{
  const result = evaluateCanSubmit({
    projectCode: 'PRJ-2026-008',
    confirmInput: 'PRJ-2026-008',
    activeTab: 'delete',
    deleteMode: 'anonymize',
    acknowledgeLoss: true,
    impact: { can_hard_delete: false, blocking_reasons: ['Trabajo en ejecución'] },
    isProcessing: false
  });
  assert.strictEqual(result, true, 'Test 7 falló: anonymize debe permitir avanzar');
  console.log('  ✓ Test 7: Modo Anonymize con hard_delete bloqueado -> ENABLED');
}

// Test 8: Vaciar contenido (clear_content) con código y checkbox -> ENABLED
{
  const result = evaluateCanSubmit({
    projectCode: 'PRJ-2026-008',
    confirmInput: 'PRJ-2026-008',
    activeTab: 'clear_content',
    deleteMode: 'hard_delete',
    acknowledgeLoss: true,
    impact: { can_hard_delete: true, blocking_reasons: [] },
    isProcessing: false
  });
  assert.strictEqual(result, true, 'Test 8 falló: clear_content debe estar habilitado');
  console.log('  ✓ Test 8: Vaciar Contenido -> ENABLED');
}

// Test 9: isProcessing = true -> DISABLED
{
  const result = evaluateCanSubmit({
    projectCode: 'PRJ-2026-008',
    confirmInput: 'PRJ-2026-008',
    activeTab: 'delete',
    deleteMode: 'hard_delete',
    acknowledgeLoss: true,
    impact: { can_hard_delete: true, blocking_reasons: [] },
    isProcessing: true
  });
  assert.strictEqual(result, false, 'Test 9 falló: isProcessing debe bloquear el botón');
  console.log('  ✓ Test 9: Durante procesamiento (isProcessing = true) -> DISABLED');
}

console.log('🎉 Todas las 9 pruebas unitarias de lógica de modal pasaron al 100%!');
