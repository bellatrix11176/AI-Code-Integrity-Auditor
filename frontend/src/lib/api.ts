import { ScanResponse } from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function scanFiles(files: File[]): Promise<ScanResponse> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  const res = await fetch(`${API_BASE_URL}/api/scan`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error(`Failed to scan: ${res.statusText}`);
  }

  return res.json();
}
