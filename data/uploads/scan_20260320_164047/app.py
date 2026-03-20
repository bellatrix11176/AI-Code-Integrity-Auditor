"""
DFDE — Dirty Frank's Decision Engine
src/dashboard/app.py

Assets:
    assets/Background.png               — full page background
    assets/DFDELogoTransparentBKG.png   — main header logo (centered, above title)
    assets/favicon.png                  — sidebar icon + browser tab

Run: streamlit run src/dashboard/app.py
"""

import streamlit as st
import pandas as pd
import os, base64

SCORES_PATH  = "output/exports/rep_gaming_scores.csv"
STAGED_DIR   = "data/raw/staged"
FIGURES_DIR  = "output/figures"
BG_PATH      = "assets/Background.png"
LOGO_PATH    = "assets/DFDELogoTransparentBKG.png"
FAVICON_PATH = "assets/DFDELogo01.png"

MAGENTA  = "#E20074"
DARK_BG  = "#0A0A12"
SIG_BLUE = "#00C2FF"
ALERT    = "#FF3B3B"
GRAY     = "#A6A6A6"
BORDER   = "#2A2A44"

RISK_COLOR = {"high_review":ALERT,"moderate_risk":"#FF8C00","watch":"#FFD700","low_concern":"#00C87A"}
RISK_LABEL = {"high_review":"🔴 HIGH REVIEW","moderate_risk":"🟠 MODERATE RISK","watch":"🟡 WATCH","low_concern":"🟢 LOW CONCERN"}

def get_b64(path):
    if os.path.exists(path):
        with open(path,"rb") as f:
            return base64.b64encode(f.read()).decode()
    return None

def img_src(path):
    b64 = get_b64(path)
    return f"data:image/png;base64,{b64}" if b64 else ""

# Page config
_fav = get_b64(FAVICON_PATH)
st.set_page_config(
    page_title="Dirty Frank's Decision Engine",
    page_icon=f"data:image/png;base64,{_fav}" if _fav else "🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

def inject_css():
    bg = img_src(BG_PATH)
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=IBM+Plex+Mono:wght@300;400;500&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

    .stApp {{
        background-image: url("{bg}");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }}
    .stApp::before {{
        content:''; position:fixed; inset:0;
        background:linear-gradient(160deg,{DARK_BG}EE 0%,{DARK_BG}AA 50%,{DARK_BG}EE 100%);
        z-index:0; pointer-events:none;
    }}
    html,body,[class*="css"] {{ font-family:'IBM Plex Sans',sans-serif; color:#E8E8F4; }}
    .main .block-container {{ position:relative; z-index:1; padding:0 2.5rem 3rem; max-width:1500px; background:transparent; }}

    section[data-testid="stSidebar"] {{
        background:linear-gradient(180deg,#06060EF8 0%,#0C0C1CF8 100%) !important;
        border-right:1px solid {BORDER}; backdrop-filter:blur(24px);
    }}
    section[data-testid="stSidebar"]>div {{ background:transparent !important; }}
    section[data-testid="stSidebar"] .block-container {{ padding:0 1rem 2rem; position:relative; z-index:1; }}

    .sb-brand {{
        text-align:center; padding:2rem 0.5rem 1.8rem;
        border-bottom:1px solid {BORDER}; margin-bottom:1.8rem; position:relative;
    }}
    .sb-brand::after {{
        content:''; position:absolute; bottom:-1px; left:10%; right:10%;
        height:1px; background:linear-gradient(90deg,transparent,{MAGENTA},transparent);
    }}
    .sb-icon {{ width:100px; height:auto; display:block; margin:0 auto 1rem; filter:drop-shadow(0 0 16px {MAGENTA}88); }}
    .sb-name {{ font-family:'Rajdhani',sans-serif; font-size:2rem; font-weight:700; color:#fff; letter-spacing:5px; line-height:1; text-shadow:0 0 24px {MAGENTA}55; }}
    .sb-sub {{ font-family:'IBM Plex Mono',monospace; font-size:0.62rem; color:{GRAY}; letter-spacing:2px; text-transform:uppercase; margin-top:0.3rem; }}
    .sb-pill {{ display:inline-block; margin-top:0.8rem; font-family:'IBM Plex Mono',monospace; font-size:0.62rem; color:{MAGENTA}; letter-spacing:2px; background:{MAGENTA}18; border:1px solid {MAGENTA}44; padding:0.22rem 0.9rem; border-radius:20px; }}

    .main-logo-block {{ text-align:center; padding:2rem 0 0.5rem; position:relative; z-index:1; }}
    .main-logo-block img {{ height:200px; width:auto; filter:drop-shadow(0 0 32px {MAGENTA}66) drop-shadow(0 0 64px {SIG_BLUE}33); }}

    .page-header {{ text-align:center; padding:0.5rem 0 1.5rem; border-bottom:1px solid {BORDER}; margin-bottom:1.5rem; position:relative; }}
    .page-header::after {{ content:''; position:absolute; bottom:-1px; left:30%; right:30%; height:1px; background:linear-gradient(90deg,transparent,{MAGENTA},transparent); }}
    .page-title {{ font-family:'Rajdhani',sans-serif; font-size:3rem; font-weight:700; color:#fff; letter-spacing:2px; line-height:1; text-shadow:0 0 40px {MAGENTA}44; }}
    .page-subtitle {{ font-family:'IBM Plex Mono',monospace; font-size:0.7rem; color:{GRAY}; letter-spacing:4px; text-transform:uppercase; margin-top:0.4rem; }}
    .page-subtitle span {{ color:{MAGENTA}; }}

    .section-head {{ font-family:'IBM Plex Mono',monospace; font-size:0.63rem; letter-spacing:4px; text-transform:uppercase; color:{MAGENTA}; padding:1.2rem 0 0.6rem; border-bottom:1px solid {BORDER}; margin-bottom:1rem; }}

    .kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin-bottom:1.5rem; }}
    .kpi-card {{ background:linear-gradient(135deg,#13131ECC,#0A0A18CC); border:1px solid {BORDER}; border-radius:10px; padding:1rem 1.2rem; backdrop-filter:blur(10px); position:relative; overflow:hidden; }}
    .kpi-card .al {{ position:absolute; top:0; left:0; right:0; height:2px; }}
    .kpi-label {{ font-family:'IBM Plex Mono',monospace; font-size:0.6rem; letter-spacing:2.5px; text-transform:uppercase; color:{GRAY}; margin-bottom:0.45rem; }}
    .kpi-value {{ font-family:'Rajdhani',sans-serif; font-size:2rem; font-weight:700; color:#fff; line-height:1; }}
    .kpi-sub {{ font-family:'IBM Plex Mono',monospace; font-size:0.6rem; color:{GRAY}; margin-top:0.25rem; }}

    .sii-banner {{ border-radius:12px; padding:1.4rem 1.8rem; margin-bottom:1.5rem; border:1px solid; backdrop-filter:blur(12px); }}

    .sig-card {{ background:linear-gradient(135deg,#13131ECC,#0A0A18CC); border:1px solid {BORDER}; border-radius:10px; padding:0.9rem 1rem; text-align:center; backdrop-filter:blur(8px); }}
    .sig-label {{ font-family:'IBM Plex Mono',monospace; font-size:0.6rem; letter-spacing:3px; color:{GRAY}; margin-bottom:0.35rem; text-transform:uppercase; }}
    .sig-value {{ font-family:'Rajdhani',sans-serif; font-size:1.8rem; font-weight:700; line-height:1; }}
    .sig-status {{ font-family:'IBM Plex Mono',monospace; font-size:0.56rem; letter-spacing:2px; margin-top:0.25rem; text-transform:uppercase; }}

    .rep-name {{ font-family:'Rajdhani',sans-serif; font-size:2.4rem; font-weight:700; color:#fff; letter-spacing:1px; line-height:1; text-shadow:0 0 25px {MAGENTA}44; }}
    .rep-id {{ font-family:'IBM Plex Mono',monospace; font-size:0.72rem; color:{GRAY}; letter-spacing:2px; margin-top:0.2rem; }}
    .risk-badge {{ display:inline-block; font-family:'IBM Plex Mono',monospace; font-size:0.66rem; padding:0.25rem 0.9rem; border-radius:4px; letter-spacing:2px; }}

    div[data-testid="stMetric"] {{ background:linear-gradient(135deg,#13131ECC,#0A0A18CC); border:1px solid {BORDER}; border-radius:10px; padding:0.9rem 1.1rem; backdrop-filter:blur(8px); }}
    div[data-testid="stMetric"] label {{ font-family:'IBM Plex Mono',monospace !important; font-size:0.6rem !important; letter-spacing:2px !important; text-transform:uppercase !important; color:{GRAY} !important; }}
    div[data-testid="stMetricValue"] {{ font-family:'Rajdhani',sans-serif !important; font-size:1.7rem !important; font-weight:700 !important; color:#fff !important; }}
    div[data-testid="stDataFrame"] {{ border-radius:10px; border:1px solid {BORDER}; backdrop-filter:blur(8px); }}
    div[data-baseweb="select"] {{ background:#13131ECC !important; border-color:{BORDER} !important; }}
    div[data-testid="stRadio"] label {{ font-family:'IBM Plex Mono',monospace !important; font-size:0.76rem !important; letter-spacing:1.5px !important; text-transform:uppercase !important; color:{GRAY} !important; }}
    hr {{ border-color:{BORDER} !important; margin:0.8rem 0 !important; }}
    ::-webkit-scrollbar {{ width:5px; height:5px; }}
    ::-webkit-scrollbar-track {{ background:transparent; }}
    ::-webkit-scrollbar-thumb {{ background:{BORDER}; border-radius:3px; }}
    ::-webkit-scrollbar-thumb:hover {{ background:{MAGENTA}; }}
    #MainMenu,footer,header {{ visibility:hidden; }}
    .stDeployButton {{ display:none; }}
    </style>
    """, unsafe_allow_html=True)

@st.cache_data
def load_scores():
    if not os.path.exists(SCORES_PATH): return None
    return pd.read_csv(SCORES_PATH)

@st.cache_data
def load_interactions():
    p = os.path.join(STAGED_DIR,"interactions.csv")
    return pd.read_csv(p) if os.path.exists(p) else None

@st.cache_data
def load_billing():
    p = os.path.join(STAGED_DIR,"billing_adjustments.csv")
    return pd.read_csv(p) if os.path.exists(p) else None

@st.cache_data
def load_signals():
    p = os.path.join(STAGED_DIR,"interaction_signals.csv")
    if not os.path.exists(p): return None
    cols=["interaction_id","rep_id","flag_store_promise","flag_temporary_credit",
          "flag_promotion_uncertainty","flag_plan_manipulation","flag_unresolved_issue",
          "rep_gaming_propensity","rep_compliance_risk"]
    avail=pd.read_csv(p,nrows=0).columns.tolist()
    return pd.read_csv(p,usecols=[c for c in cols if c in avail])

def sii_risk(v):
    if v>=75: return ALERT,"HIGH RISK"
    if v>=55: return "#FF8C00","MODERATE RISK"
    if v>=30: return "#FFD700","WATCH"
    return "#00C87A","LOW CONCERN"

def sig_color(v):
    if v>0.6: return ALERT,"CRITICAL"
    if v>0.3: return "#FFD700","ELEVATED"
    return "#00C87A","NORMAL"

def render_sidebar():
    fav = img_src(FAVICON_PATH)
    with st.sidebar:
        fav_html = f'<img src="{fav}" class="sb-icon" />' if fav else '<div style="font-size:4rem;">🔍</div>'
        st.markdown(f"""
        <div class="sb-brand">
            {fav_html}
            <div class="sb-name">DIRTY FRANK</div>
            <div class="sb-sub">Dirty Frank's Decision Engine</div>
            <div class="sb-pill">NovaWireless · v0.1</div>
        </div>""", unsafe_allow_html=True)
        page = st.radio("NAV",["System Overview","Rep Risk Table","Rep Investigation","Analysis Figures"],label_visibility="collapsed")
        st.markdown('<div class="section-head">Filters</div>',unsafe_allow_html=True)
        risk_filter=st.multiselect("Risk",options=["high_review","moderate_risk","watch","low_concern"],
            default=["high_review","moderate_risk","watch","low_concern"],
            format_func=lambda x:RISK_LABEL[x],label_visibility="collapsed")
        score_range=st.slider("Score",0,100,(0,100),label_visibility="collapsed")
        search=st.text_input("Search",placeholder="🔍  Search rep name or ID...",label_visibility="collapsed")
        st.markdown("---")
        st.markdown(f'<div style="font-family:IBM Plex Mono,monospace;font-size:0.58rem;color:{GRAY};text-align:center;letter-spacing:1px;opacity:0.6;">DFDE v0.1 · NovaWireless<br/>Governance Signal Detection</div>',unsafe_allow_html=True)
    return page,risk_filter,score_range,search

def page_header(title,subtitle,accent=""):
    logo=img_src(LOGO_PATH)
    logo_html=f'<img src="{logo}" style="height:200px;width:auto;filter:drop-shadow(0 0 32px {MAGENTA}66) drop-shadow(0 0 64px {SIG_BLUE}33);" />' if logo else ""
    acc=f'&nbsp;·&nbsp;<span>{accent}</span>' if accent else ""
    st.markdown(f"""
    <div class="main-logo-block">{logo_html}</div>
    <div class="page-header">
        <div class="page-title">{title}</div>
        <div class="page-subtitle">{subtitle}{acc}</div>
    </div>""", unsafe_allow_html=True)

def page_overview(df):
    page_header("System Overview","Dirty Frank's Decision Engine","Operational Integrity Status")
    sii=df["sii"].mean() if "sii" in df.columns else 0
    high=int((df["risk_category"]=="high_review").sum())
    proxy=df["proxy_rate"].mean() if "proxy_rate" in df.columns else 0
    dur=df["durable_rate"].mean() if "durable_rate" in df.columns else 0
    dar=df["dar"].mean() if "dar" in df.columns else 0
    por=df["por"].mean() if "por" in df.columns else 0
    ter=df["ter"].mean() if "ter" in df.columns else 0
    calls=int(df["interactions"].sum()) if "interactions" in df.columns else 0
    color,label=sii_risk(sii)
    st.markdown(f"""
    <div class="sii-banner" style="background:linear-gradient(135deg,{color}18 0%,{DARK_BG}CC 100%);border-color:{color}55;">
        <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:1.5rem;">
            <div>
                <div style="font-family:'IBM Plex Mono',monospace;font-size:0.6rem;letter-spacing:3px;color:{color};text-transform:uppercase;margin-bottom:0.4rem;">System Integrity Index</div>
                <div style="font-family:'Rajdhani',sans-serif;font-size:4rem;font-weight:700;color:{color};line-height:1;text-shadow:0 0 40px {color}66;">{sii:.1f}</div>
                <div style="font-family:'IBM Plex Mono',monospace;font-size:0.7rem;color:{color};letter-spacing:3px;margin-top:0.3rem;">{label}</div>
            </div>
            <div style="display:flex;gap:2.5rem;flex-wrap:wrap;">
                {"".join([f'<div style="text-align:center;"><div style="font-family:Rajdhani,sans-serif;font-size:2.2rem;font-weight:700;color:{RISK_COLOR.get(r,GRAY)};">{int((df["risk_category"]==r).sum())}</div><div style="font-family:IBM Plex Mono,monospace;font-size:0.56rem;color:{GRAY};letter-spacing:1px;">{RISK_LABEL.get(r,r).split(" ",1)[-1]}</div></div>' for r in ["high_review","moderate_risk","watch","low_concern"]])}
            </div>
            <div style="text-align:right;">
                <div style="font-family:'Rajdhani',sans-serif;font-size:2.8rem;font-weight:700;color:#fff;">{len(df)}</div>
                <div style="font-family:'IBM Plex Mono',monospace;font-size:0.6rem;color:{GRAY};letter-spacing:2px;">REPS ANALYZED</div>
                <div style="font-family:'Rajdhani',sans-serif;font-size:2.8rem;font-weight:700;color:#fff;margin-top:0.5rem;">{calls:,}</div>
                <div style="font-family:'IBM Plex Mono',monospace;font-size:0.6rem;color:{GRAY};letter-spacing:2px;">CALLS ANALYZED</div>
            </div>
        </div>
    </div>""", unsafe_allow_html=True)
    st.markdown(f"""
    <div class="kpi-grid">
        <div class="kpi-card"><div class="al" style="background:linear-gradient(90deg,{MAGENTA},{SIG_BLUE});"></div><div class="kpi-label">High Review</div><div class="kpi-value" style="color:{ALERT};">{high}</div><div class="kpi-sub">Score ≥ 75</div></div>
        <div class="kpi-card"><div class="al" style="background:{ALERT};"></div><div class="kpi-label">DAR</div><div class="kpi-value" style="color:{ALERT if dar>0.5 else '#FFD700'};">{dar:.3f}</div><div class="kpi-sub">Delayed adverse rate</div></div>
        <div class="kpi-card"><div class="al" style="background:{SIG_BLUE};"></div><div class="kpi-label">POR</div><div class="kpi-value" style="color:{SIG_BLUE};">{por:.3f}</div><div class="kpi-sub">Proxy overfit ratio</div></div>
        <div class="kpi-card"><div class="al" style="background:{MAGENTA};"></div><div class="kpi-label">TER</div><div class="kpi-value" style="color:{MAGENTA};">{ter:.3f}</div><div class="kpi-sub">Terminal exit rate</div></div>
        <div class="kpi-card"><div class="al" style="background:#00C87A;"></div><div class="kpi-label">Proxy Rate</div><div class="kpi-value">{proxy:.1%}</div><div class="kpi-sub">Resolution flag</div></div>
        <div class="kpi-card"><div class="al" style="background:#FFD700;"></div><div class="kpi-label">Durable Rate</div><div class="kpi-value" style="color:{'#00C87A' if dur>proxy*0.8 else ALERT};">{dur:.1%}</div><div class="kpi-sub">True resolution</div></div>
        <div class="kpi-card"><div class="al" style="background:{ALERT};"></div><div class="kpi-label">Drift Gap</div><div class="kpi-value" style="color:{ALERT};">{abs(proxy-dur):.1%}</div><div class="kpi-sub">Proxy − Durable</div></div>
    </div>""", unsafe_allow_html=True)
    st.markdown('<div class="section-head">Integrity Signal Breakdown</div>',unsafe_allow_html=True)
    sdefs=[("dar","DAR","Delayed Adverse Rate"),("drl","DRL","Downstream Remediation"),("dov","DOV","Durable Outcome Val."),("por","POR","Proxy Overfit Ratio"),("ter","TER","Terminal Exit Rate")]
    avail=[(k,s,l) for k,s,l in sdefs if k in df.columns]
    if avail:
        cols=st.columns(len(avail))
        for col,(key,short,long) in zip(cols,avail):
            v=df[key].mean(); c,status=sig_color(v)
            col.markdown(f'<div class="sig-card" style="border-top:3px solid {c};"><div class="sig-label">{short}</div><div class="sig-value" style="color:{c};text-shadow:0 0 20px {c}55;">{v:.3f}</div><div class="sig-status" style="color:{c};">{status}</div><div style="font-family:IBM Plex Mono,monospace;font-size:0.54rem;color:{GRAY};margin-top:0.25rem;letter-spacing:1px;">{long}</div></div>',unsafe_allow_html=True)

def page_rep_table(df,risk_filter,score_range,search):
    page_header("Rep Risk Table","All Agents","Sorted by Gaming Score")
    filtered=df[df["risk_category"].isin(risk_filter)]
    filtered=filtered[(filtered["gaming_likelihood_score"]>=score_range[0])&(filtered["gaming_likelihood_score"]<=score_range[1])]
    if search:
        mask=filtered["rep_id"].astype(str).str.contains(search,case=False,na=False)|filtered["rep_name"].astype(str).str.contains(search,case=False,na=False)
        filtered=filtered[mask]
    filtered=filtered.sort_values("gaming_likelihood_score",ascending=False).reset_index(drop=True)
    st.markdown(f'<div style="font-family:IBM Plex Mono,monospace;font-size:0.68rem;color:{GRAY};margin-bottom:0.8rem;">Showing <span style="color:#fff;">{len(filtered)}</span> of <span style="color:#fff;">{len(df)}</span> reps</div>',unsafe_allow_html=True)
    cols_map={"rep_id":"REP ID","rep_name":"NAME","risk_category":"RISK","gaming_likelihood_score":"SCORE","sii":"SII","dar":"DAR","drl":"DRL","dov":"DOV","por":"POR","ter":"TER","proxy_rate":"PROXY %","durable_rate":"DURABLE %","churn_rate":"CHURN %","interactions":"CALLS"}
    avail={k:v for k,v in cols_map.items() if k in filtered.columns}
    table=filtered[list(avail.keys())].rename(columns=avail).copy()
    for c in ["SCORE","SII"]:
        if c in table: table[c]=table[c].round(1)
    for c in ["DAR","DRL","DOV","POR","TER"]:
        if c in table: table[c]=table[c].round(3)
    for c in ["PROXY %","DURABLE %","CHURN %"]:
        if c in table: table[c]=(table[c]*100).round(1).astype(str)+"%"
    st.dataframe(table,width='stretch',height=550,hide_index=True)

def page_investigation(df,risk_filter,score_range,search):
    page_header("Rep Investigation","Drill into Individual Agent Behavior")
    filtered=df[df["risk_category"].isin(risk_filter)]
    filtered=filtered[(filtered["gaming_likelihood_score"]>=score_range[0])&(filtered["gaming_likelihood_score"]<=score_range[1])].sort_values("gaming_likelihood_score",ascending=False)
    if search:
        mask=filtered["rep_id"].astype(str).str.contains(search,case=False,na=False)|filtered["rep_name"].astype(str).str.contains(search,case=False,na=False)
        filtered=filtered[mask]
    if filtered.empty:
        st.warning("No reps match current filters."); return
    options=filtered.apply(lambda r:f"{r.get('rep_name','Unknown')}  ·  {r['rep_id']}  ·  Score: {r['gaming_likelihood_score']:.1f}",axis=1).tolist()
    selected=st.selectbox("Select Rep",options,label_visibility="collapsed")
    rep_id=filtered.iloc[options.index(selected)]["rep_id"]
    rep=df[df["rep_id"]==rep_id].iloc[0]
    risk=rep.get("risk_category","unknown"); rc=RISK_COLOR.get(risk,GRAY); rl=RISK_LABEL.get(risk,risk)
    st.markdown("---")
    c1,c2=st.columns([3,1])
    with c1:
        st.markdown(f'<div class="rep-name">{rep.get("rep_name",rep_id)}</div><div class="rep-id">{rep_id}</div><div style="margin-top:0.6rem;"><span class="risk-badge" style="background:{rc}22;color:{rc};border:1px solid {rc}55;">{rl}</span></div>',unsafe_allow_html=True)
    with c2:
        sv=rep.get("gaming_likelihood_score",0); sc,_=sii_risk(sv)
        st.markdown(f'<div style="text-align:right;padding-top:0.3rem;"><div style="font-family:IBM Plex Mono,monospace;font-size:0.6rem;color:{GRAY};letter-spacing:3px;text-transform:uppercase;margin-bottom:0.3rem;">Gaming Score</div><div style="font-family:Rajdhani,sans-serif;font-size:4rem;font-weight:700;color:{rc};line-height:1;text-shadow:0 0 30px {rc}66;">{sv:.1f}</div></div>',unsafe_allow_html=True)
    st.markdown('<div class="section-head">Score Overview</div>',unsafe_allow_html=True)
    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric("SII",f"{rep.get('sii',0):.1f}")
    c2.metric("Total Calls",f"{int(rep.get('interactions',0)):,}")
    c3.metric("Proxy Rate",f"{rep.get('proxy_rate',0):.1%}")
    c4.metric("Durable Rate",f"{rep.get('durable_rate',0):.1%}")
    c5.metric("Churn Rate",f"{rep.get('churn_rate',0):.1%}")
    st.markdown('<div class="section-head">Integrity Signals</div>',unsafe_allow_html=True)
    scols=st.columns(5)
    for col,key,lbl in zip(scols,["dar","drl","dov","por","ter"],["DAR","DRL","DOV","POR","TER"]):
        v=rep.get(key,0); c,status=sig_color(v)
        col.markdown(f'<div class="sig-card" style="border-top:3px solid {c};"><div class="sig-label">{lbl}</div><div class="sig-value" style="color:{c};text-shadow:0 0 16px {c}55;">{v:.3f}</div><div class="sig-status" style="color:{c};">{status}</div></div>',unsafe_allow_html=True)
    skeys=["kpi_anomaly_score","contradiction_score","nlp_language_score","peer_drift_score","documentation_score"]
    slbls=[("KPI Anomaly","30%"),("Contradiction","25%"),("NLP Language","20%"),("Peer Drift","15%"),("Documentation","10%")]
    if all(k in rep.index for k in skeys):
        st.markdown('<div class="section-head">Gaming Score Components</div>',unsafe_allow_html=True)
        gcols=st.columns(5)
        for col,key,(lbl,wt) in zip(gcols,skeys,slbls):
            v=rep[key]; c,_=sig_color(v/100)
            col.markdown(f'<div class="sig-card" style="border-top:3px solid {c};"><div class="sig-label">{lbl}</div><div class="sig-value" style="color:{c};text-shadow:0 0 16px {c}55;">{v:.1f}</div><div class="sig-status" style="color:{GRAY};">weight {wt}</div></div>',unsafe_allow_html=True)
    ix=load_interactions()
    if ix is not None:
        rep_calls=ix[ix["rep_id"]==rep_id].copy()
        bl=load_billing(); sg=load_signals()
        if bl is not None:
            rep_calls=rep_calls.merge(bl[["interaction_id","credit_amount","credit_type"]],on="interaction_id",how="left")
        if sg is not None:
            fc=[c for c in ["interaction_id","flag_store_promise","flag_temporary_credit","flag_promotion_uncertainty","flag_unresolved_issue","rep_gaming_propensity"] if c in sg.columns]
            rep_calls=rep_calls.merge(sg[fc],on="interaction_id",how="left")
        st.markdown('<div class="section-head">Call History</div>',unsafe_allow_html=True)
        st.markdown(f'<div style="font-family:IBM Plex Mono,monospace;font-size:0.66rem;color:{GRAY};margin-bottom:0.6rem;letter-spacing:1px;">{len(rep_calls):,} calls on record</div>',unsafe_allow_html=True)
        show=[c for c in ["interaction_id","call_timestamp","call_reason","disposition","resolution_flag","credit_amount","credit_type","flag_store_promise","flag_temporary_credit","flag_unresolved_issue","rep_gaming_propensity"] if c in rep_calls.columns]
        # Deduplicate: one row per interaction, keep largest credit
        if "credit_amount" in rep_calls.columns:
            rep_calls = rep_calls.sort_values("credit_amount", ascending=False)
            rep_calls = rep_calls.drop_duplicates(subset=["interaction_id"], keep="first")
        rep_calls = rep_calls.sort_values("call_timestamp", ascending=False).reset_index(drop=True)
        st.dataframe(rep_calls[show],width='stretch',height=400,hide_index=True)

def page_figures():
    page_header("Analysis Figures","Generated Integrity Signal Visualizations")
    if not os.path.exists(FIGURES_DIR):
        st.info("Run `python3 -m src.reports.generate_figures` first."); return
    figs=sorted([f for f in os.listdir(FIGURES_DIR) if f.endswith(".png")])
    if not figs:
        st.info("Run `python3 -m src.reports.generate_figures` first."); return
    st.markdown(f'<div style="font-family:IBM Plex Mono,monospace;font-size:0.66rem;color:{GRAY};margin-bottom:1rem;letter-spacing:1px;">{len(figs)} figures available</div>',unsafe_allow_html=True)
    cols=st.columns(2)
    for i,f in enumerate(figs):
        with cols[i%2]:
            cap=f.replace("fig","Figure ").replace("_"," ").replace(".png","").title()
            st.markdown(f'<div style="font-family:IBM Plex Mono,monospace;font-size:0.63rem;color:{MAGENTA};letter-spacing:2px;text-transform:uppercase;margin:0.8rem 0 0.4rem;">{cap}</div>',unsafe_allow_html=True)
            st.image(os.path.join(FIGURES_DIR,f),use_container_width=True)

def main():
    inject_css()
    scores_df=load_scores()
    if scores_df is None:
        st.error("No scoring data. Run `python3 -m src.scoring.gaming_score` first."); st.stop()
    page,risk_filter,score_range,search=render_sidebar()
    if page=="System Overview": page_overview(scores_df)
    elif page=="Rep Risk Table": page_rep_table(scores_df,risk_filter,score_range,search)
    elif page=="Rep Investigation": page_investigation(scores_df,risk_filter,score_range,search)
    elif page=="Analysis Figures": page_figures()

if __name__=="__main__":
    main()
