import { formatApiError } from './src/utils/errorHandler.ts';

// Test 1: Simular error de Axios HTTP 422 con response.data.detail de FastAPI/Pydantic
const axios422Error = new Error("Request failed with status code 422");
(axios422Error as any).response = {
  status: 422,
  data: {
    detail: [
      { loc: ["body", "source_entity_type"], msg: "Field required", type: "missing" },
      { loc: ["body", "source_entity_id"], msg: "Field required", type: "missing" },
      { loc: ["body", "fields_to_translate"], msg: "Field required", type: "missing" }
    ]
  }
};

const formatted = formatApiError(axios422Error);
console.log("Formatted 422 Error Result:\n", formatted);

const expected = "body.source_entity_type: Field required · body.source_entity_id: Field required · body.fields_to_translate: Field required";

if (formatted === expected) {
  console.log("✅ TEST PASSED: formatApiError extrae y formatea el detalle 422 de Pydantic correctamente.");
} else {
  console.error("❌ TEST FAILED: Output no coincide con el esperado.");
  console.error("Expected:", expected);
  console.error("Received:", formatted);
  process.exit(1);
}
