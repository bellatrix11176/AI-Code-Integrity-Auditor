"use client";

import Link from "next/link";
import Image from "next/image";
import { ShieldCheck, Activity, BrainCircuit, Code2, MoveRight, Cloud, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";

export default function LandingPage() {
  return (
    <div className="relative w-full min-h-screen flex flex-col items-center overflow-hidden bg-[#0a0f1a]">
      {/* ── Background Effects ── */}
      <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
        {/* Animated Mesh Gradient */}
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-[#f58e65]/10 rounded-full blur-[120px] animate-pulse" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-[#f58e65]/5 rounded-full blur-[150px] animate-pulse delay-700" />
        
        {/* Animated Clouds */}
        <motion.div 
          initial={{ x: -100, opacity: 0 }}
          animate={{ x: "100vw", opacity: [0, 0.2, 0.2, 0] }}
          transition={{ duration: 40, repeat: Infinity, ease: "linear" }}
          className="absolute top-[15%] left-0 text-white/10"
        >
          <Cloud size={120} fill="currentColor" className="blur-sm" />
        </motion.div>
        
        <motion.div 
          initial={{ x: "100vw", opacity: 0 }}
          animate={{ x: -200, opacity: [0, 0.15, 0.15, 0] }}
          transition={{ duration: 55, repeat: Infinity, ease: "linear" }}
          className="absolute top-[40%] right-0 text-white/5"
        >
          <Cloud size={180} fill="currentColor" className="blur-md" />
        </motion.div>

        <motion.div 
          initial={{ x: -150, opacity: 0 }}
          animate={{ x: "100vw", opacity: [0, 0.1, 0.1, 0] }}
          transition={{ duration: 30, repeat: Infinity, ease: "linear", delay: 10 }}
          className="absolute top-[65%] left-0 text-[#f58e65]/10"
        >
          <Cloud size={100} fill="currentColor" className="blur-[2px]" />
        </motion.div>

        {/* Grid Pattern Overlay */}
        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 brightness-100 contrast-150 pointer-events-none"></div>
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:40px_40px]"></div>
      </div>

      <div className="relative z-10 w-full max-w-6xl px-6 mx-auto">
        {/* Navbar Minimal */}
        <nav className="w-full flex justify-between items-center py-8 mb-12 md:mb-20">
          <div className="flex items-center space-x-3 group cursor-pointer">
            <div className="relative w-9 h-9">
              <Image 
                src="/logo.svg" 
                alt="ACIA Logo" 
                fill 
                className="object-contain relative z-10"
              />
              <div className="absolute inset-[-4px] bg-[#f58e65]/40 blur-md rounded-lg group-hover:scale-125 transition-transform"></div>
            </div>
            <span className="text-2xl font-bold tracking-tighter text-white">ACIA</span>
          </div>
          <Link href="/dashboard">
            <Button variant="ghost" className="text-sm font-medium pr-0 hover:bg-transparent hover:text-[#f58e65] transition-colors">
              Sign In
            </Button>
          </Link>
        </nav>

        {/* Hero Section */}
        <div className="flex flex-col items-center text-center space-y-10 mb-32">
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="inline-flex items-center rounded-full border border-[#f58e65]/30 bg-[#f58e65]/5 px-4 py-1.5 text-xs font-semibold text-[#f58e65] backdrop-blur-md shadow-[0_0_15px_rgba(245,142,101,0.1)]"
          >
            <Sparkles className="w-3.5 h-3.5 mr-2 animate-pulse" />
            Auditor Engine v2.0 is Live
          </motion.div>
          
          <motion.h1 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-6xl md:text-[5.5rem] font-bold leading-[1.05] tracking-tight text-white max-w-5xl mx-auto"
            style={{ fontFamily: "var(--font-instrument)" }}
          >
            Ship AI code with <br className="hidden md:block"/>
            <span className="relative inline-block text-transparent bg-clip-text bg-gradient-to-r from-white via-[#f58e65] to-white bg-[length:200%_auto] animate-gradient-flow">
              absolute certainty.
            </span>
          </motion.h1>
          
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="text-lg md:text-xl text-[#f8b195] max-w-2xl mx-auto font-light leading-relaxed"
          >
            The ultimate defense mechanism against structural hallucinations, logic drift, and silent failures in AI-generated backend configurations.
          </motion.p>

          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="flex flex-col sm:flex-row items-center gap-6 pt-6"
          >
            <Link href="/dashboard">
              <Button size="lg" className="group relative overflow-hidden rounded-full bg-[#f58e65] px-10 h-14 text-lg font-bold text-white shadow-[0_0_40px_rgba(245,142,101,0.3)] hover:scale-105 active:scale-95 transition-all duration-300">
                <span className="relative z-10 flex items-center">
                  Get Started <MoveRight className="ml-2 w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </span>
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-[100%] group-hover:translate-x-[100%] transition-transform duration-700"></div>
              </Button>
            </Link>
            <Button variant="outline" size="lg" className="rounded-full border-[#1e2d45] hover:border-[#f58e65]/50 px-10 h-14 text-lg font-medium text-[#c9d1d9] backdrop-blur-sm transition-all hover:bg-white/5">
              Read Docs
            </Button>
          </motion.div>
        </div>

        {/* Features Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto mb-32">
          {[
            { 
              title: "Logic Drift Detection", 
              icon: Activity, 
              desc: "Instantly maps control flow divergence and identifies \"paths to nowhere\" before they reach production." 
            },
            { 
              title: "Hallucination Defense", 
              icon: BrainCircuit, 
              desc: "Analyzes Abstract Syntax Trees (AST) to reliably flag AI placeholder logic and missing references." 
            },
            { 
              title: "Silent Failure Shields", 
              icon: Code2, 
              desc: "Captures narrative state mismatches to prevent swallowed exceptions or falsely narrated terminal states." 
            }
          ].map((feature, idx) => (
            <motion.div 
              key={idx}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: idx * 0.1 }}
              className="p-10 rounded-3xl border border-white/5 bg-[#111827]/40 backdrop-blur-xl hover:border-[#f58e65]/20 transition-all group"
            >
              <div className="w-14 h-14 rounded-2xl bg-[#f58e65]/10 flex items-center justify-center mb-8 group-hover:scale-110 group-hover:bg-[#f58e65]/20 transition-all border border-[#f58e65]/10">
                <feature.icon className="w-7 h-7 text-[#f58e65]" strokeWidth={1.5} />
              </div>
              <h3 className="text-2xl font-semibold text-white mb-4" style={{ fontFamily: "var(--font-instrument)" }}>{feature.title}</h3>
              <p className="text-[#f8b195] leading-relaxed font-light">
                {feature.desc}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
      
      <style jsx global>{`
        @keyframes gradient-flow {
          0% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
          100% { background-position: 0% 50%; }
        }
        .animate-gradient-flow {
          animation: gradient-flow 6s ease infinite;
          background-size: 200% auto;
        }
      `}</style>
    </div>
  );
}
