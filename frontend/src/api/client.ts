import axios from "axios";

export const api = axios.create({
  baseURL: (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, ""),
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});