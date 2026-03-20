"""
novawireless — Trust Signal Health Governance Framework
Aulabaugh (2026): When KPIs Lie — Governance Signals for AI-Optimized Call Centers

Package layout
--------------
novawireless.pipeline
    loader        — data ingestion and repo-root resolution
    integrity     — integrity gate: validation, quarantine, duplicate policy
    signals       — call-level trust signal scoring
    aggregation   — rep / scenario / customer / monthly summaries
    paper_signals — DAR, DRL, DOV, POR, TER, SII (Appendix A formal definitions)
    alerts        — threshold evaluation and governance alert generation
    charts        — matplotlib chart suite (12 figures)
    reports       — summary report and governance JSON export

novawireless.kardashev
    classifier    — Kardashev Trust Classification (Section 7)
                    Type I  Proxy Mastery   (SII ≥ 30 or override)
                    Type II Resolution Mastery (SII 10–29)
                    Type III Systemic Integrity (SII < 10)
"""

__version__ = "3.0.0"
__author__  = "Gina Aulabaugh / PixelKraze LLC"
__paper__   = "Aulabaugh (2026): When KPIs Lie — Governance Signals for AI-Optimized Call Centers"
