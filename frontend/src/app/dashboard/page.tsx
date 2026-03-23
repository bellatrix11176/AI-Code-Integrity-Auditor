"use client";

import { useState } from "react";
import Image from "next/image";
import { ShieldAlert, ArrowLeft } from "lucide-react";
import { Uploader } from "@/components/uploader";
import { Results } from "@/components/results";
import { ScanResponse } from "@/types";
import Link from "next/link";

import { scanFiles } from "@/lib/api";

export default function Dashboard() {
  const [isScanning, setIsScanning] = useState(false);
  const [results, setResults] = useState<ScanResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleScan = async (files: File[]) => {
    setIsScanning(true);
    setError(null);
    
    try {
      const data = await scanFiles(files);
      setResults(data);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "An error occurred during scanning.");
    } finally {
      setIsScanning(false);
    }
  };

  const handleReset = () => {
    setResults(null);
    setError(null);
  };

  return (
    <div className="w-full flex-col mt-4">
      <div className="mb-8">
        <Link href="/" className="inline-flex items-center text-sm font-medium text-foreground hover:text-[#f58e65] transition-colors">
          <ArrowLeft className="w-4 h-4 mr-2" /> Back to Home
        </Link>
      </div>
      
      <div className="mb-12 space-y-2">
        <div className="flex items-center space-x-3 mb-2">
          <div className="relative w-10 h-10">
            <Image 
              src="/logo.svg" 
              alt="ACIA Logo" 
              fill 
              className="object-contain drop-shadow-[0_0_8px_rgba(245,142,101,0.8)]"
            />
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight">Code Auditor</h1>
        </div>
        <p className="text-muted max-w-2xl text-base leading-relaxed">
          Upload Python or JSON configurations to instantly detect logic drift and structural hallucination.
        </p>
      </div>

      {error && (
        <div className="alert alert-error max-w-3xl mb-8 shadow-lg">
          <svg xmlns="http://www.w3.org/2000/svg" className="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
          <span>{error}</span>
        </div>
      )}

      {/* Main Content Area */}
      <div className="w-full">
        {!results ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-700 max-w-4xl">
            <Uploader onScan={handleScan} isLoading={isScanning} />
            <div className="mt-4 flex justify-center space-x-8 text-sm text-[#355c7d]">
              <div className="flex items-center"><span className="w-1.5 h-1.5 rounded-md bg-[#f58e65] mr-2 shadow-[0_0_8px_#f58e65]"></span> Python (.py) AST</div>
              <div className="flex items-center"><span className="w-1.5 h-1.5 rounded-md bg-[#f58e65] mr-2 shadow-[0_0_8px_#f58e65]"></span> JSON Configurations</div>
            </div>
          </div>
        ) : (
          <Results data={results} onReset={handleReset} />
        )}
      </div>
    </div>
  );
}
