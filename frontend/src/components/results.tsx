import { ShieldAlert, Info, AlertTriangle, Download, Terminal, ChevronDown } from "lucide-react";
import { Finding, ScanResponse } from "@/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "./ui/card";
import { Button } from "./ui/button";
import { useState } from "react";
import { cn } from "@/lib/utils";

const SEVERITY_COLORS = {
  high: "text-red-500 bg-red-500/10 border-red-500/20",
  medium: "text-amber-500 bg-amber-500/10 border-amber-500/20",
  low: "text-blue-500 bg-blue-500/10 border-blue-500/20",
};

const SEVERITY_ICONS = {
  high: <ShieldAlert className="w-4 h-4 text-red-500" />,
  medium: <AlertTriangle className="w-4 h-4 text-amber-500" />,
  low: <Info className="w-4 h-4 text-blue-500" />,
};

interface ResultsProps {
  data: ScanResponse;
  onReset: () => void;
}

export function Results({ data, onReset }: ResultsProps) {
  const [filter, setFilter] = useState<string>("all");
  const { summary, findings } = data;

  const downloadJSON = () => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `scan-report-${new Date().toISOString()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const filteredFindings = findings.filter(f => filter === "all" || f.severity === filter);

  return (
    <div className="space-y-8 animate-in fade-in zoom-in-95 duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white mb-2">Scan Report</h2>
          <p className="text-muted">Analyzed {summary.files_scanned} files</p>
        </div>
        <div className="flex space-x-3">
          <Button variant="outline" onClick={downloadJSON}>
            <Download className="w-4 h-4 mr-2" />
            Export JSON
          </Button>
          <Button onClick={onReset}>Scan New Files</Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="md:col-span-1 border-white/5 py-4">
          <CardHeader className="pb-2 pt-0">
            <CardTitle className="text-[#f58e65] uppercase text-xs tracking-wider">Total Findings</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-extrabold text-white">{summary.total_findings}</div>
          </CardContent>
        </Card>
        
        <Card className="md:col-span-1 border-white/5 py-4 hover:border-red-500/30 cursor-pointer transition-colors" onClick={() => setFilter(filter === 'high' ? 'all' : 'high')}>
          <CardHeader className="pb-2 pt-0 flex flex-row items-center justify-between">
            <CardTitle className="text-red-500 uppercase text-xs tracking-wider">High Risk</CardTitle>
            {SEVERITY_ICONS.high}
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-extrabold text-white">{summary.by_severity.high || 0}</div>
          </CardContent>
        </Card>

        <Card className="md:col-span-1 border-white/5 py-4 hover:border-amber-500/30 cursor-pointer transition-colors" onClick={() => setFilter(filter === 'medium' ? 'all' : 'medium')}>
          <CardHeader className="pb-2 pt-0 flex flex-row items-center justify-between">
            <CardTitle className="text-amber-500 uppercase text-xs tracking-wider">Medium Risk</CardTitle>
            {SEVERITY_ICONS.medium}
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-extrabold text-white">{summary.by_severity.medium || 0}</div>
          </CardContent>
        </Card>

        <Card className="md:col-span-1 border-white/5 py-4 hover:border-blue-500/30 cursor-pointer transition-colors" onClick={() => setFilter(filter === 'low' ? 'all' : 'low')}>
          <CardHeader className="pb-2 pt-0 flex flex-row items-center justify-between">
            <CardTitle className="text-blue-500 uppercase text-xs tracking-wider">Low Risk</CardTitle>
            {SEVERITY_ICONS.low}
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-extrabold text-white">{summary.by_severity.low || 0}</div>
          </CardContent>
        </Card>
      </div>

      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-white/90 border-b border-white/10 pb-2">
          {filter === 'all' ? 'All Findings' : `${filter.charAt(0).toUpperCase() + filter.slice(1)} Severity Findings`}
        </h3>
        {filteredFindings.length === 0 ? (
          <div className="text-center py-8 rounded-md border border-dashed border-card-border bg-background/40">
            <ShieldAlert className="w-12 h-12 text-[#f58e65]/40 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-white">Clean Code</h3>
            <p className="text-muted">No issues found in this category.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredFindings.map((finding, idx) => (
              <FindingRow key={idx} finding={finding} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function FindingRow({ finding }: { finding: Finding }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={cn(
      "rounded-lg border bg-card-bg overflow-hidden transition-all duration-200",
      expanded ? "border-[#f58e65]/40 shadow-lg shadow-[#f58e65]/5" : "border-card-border hover:border-[#f58e65]/20"
    )}>
      <div 
        className="p-4 flex items-start gap-4 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="mt-1">
          {SEVERITY_ICONS[finding.severity] || SEVERITY_ICONS.low}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline justify-between gap-4 mb-1">
            <h4 className="text-sm font-semibold text-white truncate">
              {finding.title || finding.message}
            </h4>
            <div className="flex shrink-0 gap-2 items-center">
              <span className="badge badge-outline badge-sm font-mono bg-black/40 text-muted border-white/10">
                {finding.file}:{finding.line}
              </span>
              <span className={cn("badge badge-sm border", SEVERITY_COLORS[finding.severity])}>
                {finding.category}
              </span>
            </div>
          </div>
          <p className="text-sm text-muted line-clamp-2">
            {finding.message}
          </p>
        </div>
        <ChevronDown className={cn("w-5 h-5 text-[#355c7d] transition-transform flex-shrink-0 mt-2", expanded ? "rotate-180" : "")} />
      </div>

      {expanded && (
        <div className="border-t border-card-border bg-card-bg p-4 text-sm animate-in slide-in-from-top-2">
          {finding.suggestion && (
            <div className="mb-4">
              <span className="text-[#f58e65] font-semibold text-xs tracking-wider uppercase block mb-1">Suggestion</span>
              <p className="text-foreground bg-card-bg px-4 py-3 rounded-md border border-card-border">{finding.suggestion}</p>
            </div>
          )}
          {finding.evidence && (
            <div className="font-mono bg-black rounded-md p-4 border border-card-border overflow-x-auto relative group">
              <div className="absolute top-2 right-3 text-xs text-[#355c7d] opacity-0 group-hover:opacity-100 transition-opacity">
                L{finding.line}
              </div>
              <div className="flex items-start text-muted">
                <Terminal className="w-4 h-4 mr-3 mt-0.5 shrink-0 text-[#f58e65]" />
                <code className="text-foreground whitespace-pre-wrap">{finding.evidence}</code>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
