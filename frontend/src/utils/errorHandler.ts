/**
 * Helper centralizado para formatear errores de API y validaciones FastAPI/Pydantic
 * asegurando que NUNCA se devuelva ni renderice un objeto en React JSX.
 */
export function formatApiError(error: unknown): string {
  if (typeof error === "string") return error;

  // Si es un objeto AxiosError o similar con response.data, priorizar el detalle de la API
  if (typeof error === "object" && error !== null) {
    const errObj = error as Record<string, any>;
    if (errObj.response && errObj.response.data !== undefined) {
      return formatApiError(errObj.response.data);
    }
  }

  if (Array.isArray(error)) {
    const formatted = error.map(formatApiError).filter(Boolean);
    return formatted.length > 0 ? formatted.join(" · ") : "Error de validación en la solicitud.";
  }

  if (error && typeof error === "object") {
    const value = error as Record<string, unknown>;
    if (typeof value.msg === "string") {
      const loc = Array.isArray(value.loc) ? value.loc.join(".") : "";
      return loc ? `${loc}: ${value.msg}` : value.msg;
    }
    if ("detail" in value && value.detail !== undefined) {
      return formatApiError(value.detail);
    }
    if (typeof value.message === "string") return value.message;
    if (typeof value.error === "string") return value.error;
  }

  if (error instanceof Error) return error.message;

  return "Ocurrió un error inesperado al procesar la solicitud.";
}
