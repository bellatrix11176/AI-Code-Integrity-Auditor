"""
novawireless.pipeline.integrity
--------------------------------
Integrity gate for the calls_sanitized schema.

Responsibility
--------------
- Validate required columns are present and non-null.
- Detect unknown scenarios and invalid credit types.
- Flag proxy/true resolution divergence (soft signal — not quarantined).
- Apply configurable duplicate-call-ID policy.
- Split the dataset into clean and quarantined subsets.
- Write integrity_summary.json, calls_clean.csv, calls_quarantine.csv,
  and integrity_flags.csv to output/data/.

Paper connection (Section 2 & Appendix A)
------------------------------------------
Proxy-true divergence (``flag_proxy_true_divergence``) is the raw signal
underlying the Goodhart Gap.  The 42.1pp gap in the NovaWireless benchmark
(89.4% proxy FCR vs 47.3% true CRT) is computed from these flags at
system scale.  Data that fails hard integrity gates is quarantined before
any governance signals are computed, preventing corrupted records from
contaminating the SII calculation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pandas as pd

from .loader import save_json


# ── Schema constants ──────────────────────────────────────────────────────────

REQUIRED_COLUMNS: List[str] = [
    "call_id", "call_date", "scenario", "call_type", "rep_id", "customer_id",
    "true_resolution", "resolution_flag", "credit_applied", "credit_type",
    "credit_authorized",
]

KNOWN_SCENARIOS: Set[str] = {
    "clean", "unresolvable_clean", "gamed_metric",
    "fraud_store_promo", "fraud_line_add", "fraud_hic_exchange", "fraud_care_promo",
    "activation_clean", "activation_failed", "line_add_legitimate",
    "loyalty_offer_missed",
}

VALID_CREDIT_TYPES: Set[str] = {
    "none", "courtesy", "service_credit", "bandaid",
    "dispute_credit", "fee_waiver",
}

DETECTION_FLAG_COLS: List[str] = [
    "imei_mismatch_flag",
    "nrf_generated_flag",
    "promo_override_post_call",
    "line_added_no_usage_flag",
    "line_added_same_day_store",
    "rep_aware_gaming",
]

FRAUD_SCENARIOS:  Set[str] = {
    "fraud_store_promo", "fraud_line_add",
    "fraud_hic_exchange", "fraud_care_promo",
}
GAMING_SCENARIOS: Set[str] = {"gamed_metric"}


# ── Configuration dataclasses ─────────────────────────────────────────────────

@dataclass
class IntegrityConfig:
    """
    Schema-validation configuration for the integrity gate.

    Attributes
    ----------
    required_columns : list[str]
        Columns that must be present and non-null.
    unique_key : str
        Column used for duplicate detection.
    known_scenarios : set[str]
        Valid values for the ``scenario`` column.
    valid_credit_types : set[str]
        Valid values for the ``credit_type`` column.
    """
    required_columns:  List[str] = field(default_factory=lambda: list(REQUIRED_COLUMNS))
    unique_key:        str       = "call_id"
    known_scenarios:   Set[str]  = field(default_factory=lambda: set(KNOWN_SCENARIOS))
    valid_credit_types: Set[str] = field(default_factory=lambda: set(VALID_CREDIT_TYPES))


@dataclass
class ThresholdConfig:
    """
    WATCH / VETO thresholds for the governance alert system (Section 6).

    All numeric values represent inclusive bounds:
      - trust scores   are "below X → alert"
      - gap / bandaid  are "above X → alert"
    """
    trust_score_veto:    float = 50.0
    trust_score_watch:   float = 65.0
    resolution_gap_veto: float = 0.70
    resolution_gap_watch: float = 0.50
    bandaid_rate_veto:   float = 0.50
    bandaid_rate_watch:  float = 0.20
    rep_trust_veto:      float = 60.0
    rep_trust_watch:     float = 65.0
    rep_gap_veto:        float = 0.55
    rep_gap_watch:       float = 0.45
    drift_velocity_watch: float = 2.0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _coerce_flag(series: pd.Series) -> pd.Series:
    """
    Coerce a mixed-type boolean/integer/string column to a clean {0, 1} Series.

    Accepted truthy values (case-insensitive): ``1``, ``"true"``, ``"t"``,
    ``"yes"``, ``"y"``.  Everything else (including NaN) maps to 0.
    """
    s = series.copy()
    if pd.api.types.is_numeric_dtype(s):
        return (pd.to_numeric(s, errors="coerce").fillna(0) > 0).astype(int)
    s = s.astype(str).str.strip().str.lower()
    return s.isin({"1", "true", "t", "yes", "y"}).astype(int)


# ── Flag construction ─────────────────────────────────────────────────────────

def build_integrity_flags(df: pd.DataFrame, cfg: IntegrityConfig) -> pd.DataFrame:
    """
    Build a boolean flag DataFrame aligned with ``df``.

    Columns prefixed ``flag_`` are *hard* flags — rows where any hard flag
    fires are quarantined.  Columns prefixed ``soft_`` are informational
    signals that are recorded but do not trigger quarantine.

    Parameters
    ----------
    df  : pd.DataFrame  — raw combined monthly data
    cfg : IntegrityConfig

    Returns
    -------
    pd.DataFrame
        Same index as ``df``.  One boolean column per integrity check.
    """
    flags = pd.DataFrame(index=df.index)

    # Missing required columns (applies to every row if the column is absent)
    missing = [c for c in cfg.required_columns if c not in df.columns]
    flags["flag_missing_required_columns"] = len(missing) > 0

    # Null / empty required fields (per-row)
    for c in cfg.required_columns:
        if c in df.columns:
            flags[f"flag_null_{c}"] = (
                df[c].isna() | (df[c].astype(str).str.strip() == "")
            )

    # Unknown scenario values
    if "scenario" in df.columns:
        flags["flag_unknown_scenario"] = ~df["scenario"].isin(cfg.known_scenarios)

    # Invalid credit type values
    if "credit_type" in df.columns:
        flags["flag_invalid_credit_type"] = ~(
            df["credit_type"].astype(str).str.strip().isin(cfg.valid_credit_types)
        )

    # Soft signal: bandaid credit marked as authorized
    # (Records where credit_type == "bandaid" AND credit_authorized == 1 suggest
    # a data labelling inconsistency — bandaid credits are by definition
    # unauthorised.  Recorded for analysis, not quarantined.)
    if {"credit_type", "credit_authorized"}.issubset(df.columns):
        flags["soft_bandaid_marked_authorized"] = (
            (df["credit_type"].astype(str).str.strip() == "bandaid")
            & (_coerce_flag(df["credit_authorized"]) == 1)
        )

    # Soft signal: proxy says resolved but true outcome says unresolved
    # This is the per-row form of the Goodhart Gap.
    if {"resolution_flag", "true_resolution"}.issubset(df.columns):
        flags["flag_proxy_true_divergence"] = (
            (_coerce_flag(df["resolution_flag"]) == 1)
            & (_coerce_flag(df["true_resolution"]) == 0)
        )

    # Soft signal: detection flags firing on clean scenarios
    if "scenario" in df.columns:
        is_clean = df["scenario"].isin(
            {"clean", "activation_clean", "line_add_legitimate"}
        )
        det_cols = [c for c in DETECTION_FLAG_COLS if c in df.columns]
        if det_cols:
            any_det = (
                df[det_cols]
                .apply(lambda col: _coerce_flag(col), axis=0)
                .any(axis=1)
            )
            flags["flag_detection_on_clean_scenario"] = is_clean & any_det

    # Placeholder — filled by apply_dupe_policy
    flags["flag_duplicate_call_id"] = False

    return flags


# ── Duplicate policy ──────────────────────────────────────────────────────────

def apply_dupe_policy(
    df: pd.DataFrame,
    cfg: IntegrityConfig,
    dupe_policy: str,
) -> Tuple[pd.Series, Dict]:
    """
    Apply a duplicate-call-ID quarantine policy.

    Parameters
    ----------
    df          : pd.DataFrame
    cfg         : IntegrityConfig
    dupe_policy : str
        One of:
        - ``"quarantine_all"``                  — quarantine every copy of a
          duplicate call_id.
        - ``"quarantine_extras_keep_latest"``   — keep the most recent copy
          per call_id (by call_date), quarantine the rest.
        - ``"quarantine_extras_keep_first"``    — keep the earliest copy.

    Returns
    -------
    (quarantine_mask, stats_dict)
    """
    stats: Dict = {
        "dupe_policy":             dupe_policy,
        "duplicate_ids_count":     0,
        "duplicate_rows_involved": 0,
        "duplicate_rows_quarantined": 0,
    }

    if cfg.unique_key not in df.columns:
        return pd.Series(False, index=df.index), stats

    dup_mask = df.duplicated(subset=[cfg.unique_key], keep=False)
    involved = df.index[dup_mask]
    stats["duplicate_rows_involved"] = int(len(involved))

    if len(involved) == 0:
        return pd.Series(False, index=df.index), stats

    stats["duplicate_ids_count"] = int(
        df.loc[dup_mask, cfg.unique_key].nunique()
    )

    if dupe_policy == "quarantine_all":
        out = pd.Series(False, index=df.index)
        out.loc[involved] = True
        stats["duplicate_rows_quarantined"] = stats["duplicate_rows_involved"]
        return out, stats

    if dupe_policy in {
        "quarantine_extras_keep_latest",
        "quarantine_extras_keep_first",
    }:
        sort_col = "call_date" if "call_date" in df.columns else cfg.unique_key
        asc = (dupe_policy == "quarantine_extras_keep_first")
        sdf = df.sort_values(
            [cfg.unique_key, sort_col], ascending=[True, asc]
        )
        keeper = sdf.drop_duplicates(subset=[cfg.unique_key], keep="first").index
        extras = sdf.index.difference(keeper)
        out = pd.Series(False, index=df.index)
        out.loc[extras] = True
        stats["duplicate_rows_quarantined"] = int(len(extras))
        return out, stats

    raise ValueError(
        f"Unknown dupe_policy: {dupe_policy!r}. "
        "Use 'quarantine_all', 'quarantine_extras_keep_latest', "
        "or 'quarantine_extras_keep_first'."
    )


# ── Gate orchestrator ─────────────────────────────────────────────────────────

def run_integrity_gate(
    df: pd.DataFrame,
    out_dirs: Dict[str, Path],
    cfg: IntegrityConfig | None = None,
    dupe_policy: str = "quarantine_extras_keep_latest",
) -> Dict:
    """
    Run the full integrity gate and write output artefacts.

    Scopes duplicate detection to ``call_id`` within each source file,
    because call IDs reset across monthly files.

    Writes to ``out_dirs["data"]``:
    - ``calls_clean.csv``
    - ``calls_quarantine.csv``
    - ``integrity_flags.csv``
    - ``integrity_summary.json``

    Parameters
    ----------
    df          : pd.DataFrame   — raw combined monthly DataFrame
    out_dirs    : dict[str, Path]
    cfg         : IntegrityConfig (optional; defaults created if None)
    dupe_policy : str

    Returns
    -------
    dict with keys:
        "clean_df"       → pd.DataFrame (rows passing all hard flags)
        "quarantine_df"  → pd.DataFrame (rows failing any hard flag)
        "summary"        → dict (integrity stats for downstream reporting)
    """
    if cfg is None:
        cfg = IntegrityConfig()

    # Composite key: call_id scoped to source file prevents cross-month false dupes
    if "_source_file" in df.columns:
        df = df.copy()
        df["_composite_key"] = (
            df["call_id"].astype(str) + "|" + df["_source_file"].astype(str)
        )
        orig_key = cfg.unique_key
        cfg.unique_key = "_composite_key"

    flags = build_integrity_flags(df, cfg)
    dupe_q, dupe_stats = apply_dupe_policy(df, cfg, dupe_policy)

    if "_source_file" in df.columns:
        cfg.unique_key = orig_key   # restore

    flags["flag_duplicate_call_id"] = dupe_q

    # Hard flags determine quarantine (proxy-true divergence and
    # detection-on-clean-scenario are informational soft signals)
    hard_flag_cols = [
        c for c in flags.columns
        if c.startswith("flag_")
        and c not in {"flag_proxy_true_divergence", "flag_detection_on_clean_scenario"}
    ]
    flags["any_flag"] = flags[hard_flag_cols].any(axis=1) if hard_flag_cols else False

    clean_df = df.loc[~flags["any_flag"]].copy()
    quar_df  = df.loc[flags["any_flag"]].copy()

    # Write artefacts
    clean_df.to_csv(out_dirs["data"] / "calls_clean.csv",       index=False)
    quar_df.to_csv( out_dirs["data"] / "calls_quarantine.csv",  index=False)
    flags.to_csv(   out_dirs["data"] / "integrity_flags.csv",   index=False)

    all_flag_cols = [
        c for c in flags.columns
        if c.startswith("flag_") and c != "any_flag"
    ]
    summary = {
        "timestamp":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "rows_total":        int(len(df)),
        "rows_clean":        int(len(clean_df)),
        "rows_quarantined":  int(len(quar_df)),
        "quarantine_rate":   float(flags["any_flag"].mean()),
        "flag_rates":        {c: float(flags[c].mean()) for c in all_flag_cols},
        "soft_signal_rates": {
            "proxy_true_divergence": float(
                flags.get("flag_proxy_true_divergence", pd.Series(0)).mean()
            ),
            "detection_on_clean_scenario": float(
                flags.get("flag_detection_on_clean_scenario", pd.Series(0)).mean()
            ),
        },
        "months_loaded": (
            int(df["_source_file"].nunique())
            if "_source_file" in df.columns else 0
        ),
        **dupe_stats,
    }

    save_json(out_dirs["reports"] / "integrity_summary.json", summary)

    return {
        "clean_df":      clean_df,
        "quarantine_df": quar_df,
        "summary":       summary,
    }
