export interface Finding {
  file: string;
  line: number;
  category: string;
  severity: "high" | "medium" | "low";
  message: string;
  title?: string;
  evidence?: string;
  suggestion?: string;
}

export interface ScanSummary {
  total_findings: number;
  files_scanned: number;
  by_severity: Record<string, number>;
  by_category: Record<string, number>;
}

export interface ScanResponse {
  summary: ScanSummary;
  findings: Finding[];
  files: Record<string, Finding[]>;
}
