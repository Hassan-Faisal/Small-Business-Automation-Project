import axios from "axios";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const data: unknown = error.response?.data;
    if (isRecord(data)) {
      if (isRecord(data.error) && typeof data.error.message === "string") return data.error.message;
      if (typeof data.detail === "string") return data.detail;
      if (typeof data.message === "string") return data.message;
    }
  }
  if (error instanceof Error && error.message && !error.message.startsWith("Unexpected ")) return error.message;
  return fallback;
}
