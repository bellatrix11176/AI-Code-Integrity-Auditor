"use client";

import { useState, useCallback } from "react";
import { UploadCloud, FileType, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "./ui/button";

interface UploaderProps {
  onScan: (files: File[]) => void;
  isLoading: boolean;
}

export function Uploader({ onScan, isLoading }: UploaderProps) {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") setDragActive(true);
    else if (e.type === "dragleave") setDragActive(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const newFiles = Array.from(e.dataTransfer.files).filter(f => 
        f.name.endsWith('.py') || f.name.endsWith('.json')
      );
      setSelectedFiles(prev => [...prev, ...newFiles]);
    }
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      const newFiles = Array.from(e.target.files).filter(f => 
        f.name.endsWith('.py') || f.name.endsWith('.json')
      );
      setSelectedFiles(prev => [...prev, ...newFiles]);
    }
  };

  const removeFile = (idx: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== idx));
  };

  return (
    <div className="w-full max-w-3xl mx-auto space-y-6">
      <div
        className={cn(
          "relative group border-2 border-dashed rounded-lg p-5 text-center transition-all duration-300 ease-in-out",
          dragActive 
            ? "border-[#f58e65] bg-[#f58e65]/5 shadow-[0_0_30px_rgba(245,142,101,0.15)]" 
            : "border-card-border bg-card-bg hover:border-[#f58e65]/50 hover:bg-card-bg"
        )}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <input
          type="file"
          multiple
          accept=".py,.json"
          onChange={handleChange}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          disabled={isLoading}
        />
        
        <div className="flex flex-col items-center justify-center space-y-4 pointer-events-none">
          <div className="w-16 h-16 rounded-md bg-card-bg flex items-center justify-center group-hover:scale-110 transition-transform duration-300 border border-card-border group-hover:border-[#f58e65]/50 group-hover:shadow-[0_0_20px_rgba(245,142,101,0.2)]">
            <UploadCloud className="w-8 h-8 text-[#f58e65]" />
          </div>
          <div>
            <h3 className="text-xl font-medium text-white mb-1">
              Drag and drop files here
            </h3>
            <p className="text-sm text-muted">
              or click to browse (.py, .json)
            </p>
          </div>
        </div>
      </div>

      {selectedFiles.length > 0 && (
        <div className="glass-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-sm font-semibold uppercase tracking-wider text-[#f58e65]">
              Selected Files ({selectedFiles.length})
            </h4>
            <Button 
              onClick={() => onScan(selectedFiles)}
              disabled={isLoading}
              className="py-1"
            >
              {isLoading ? "Scanning..." : "Run Security Scan"}
            </Button>
          </div>
          <div className="space-y-2 max-h-48 overflow-y-auto pr-2">
            {selectedFiles.map((f, i) => (
              <div key={i} className="flex items-center justify-between p-3 rounded-lg border border-card-border bg-card-bg/50">
                <div className="flex items-center space-x-3">
                  <FileType className="w-5 h-5 text-muted" />
                  <span className="text-sm font-medium text-foreground truncate max-w-[200px] sm:max-w-xs">{f.name}</span>
                  <span className="text-xs text-muted">{(f.size / 1024).toFixed(1)} KB</span>
                </div>
                <button 
                  onClick={() => removeFile(i)}
                  disabled={isLoading}
                  className="text-muted hover:text-red-400 p-1 rounded-md hover:bg-red-400/10 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
