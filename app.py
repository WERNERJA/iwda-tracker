"""
IWDA ETF Tracker — iPhone-vriendelijk Streamlit Dashboard
iShares Core MSCI World UCITS ETF (IE00B4L5Y983)
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import requests

# ─── PAGINA INSTELLING ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="IWDA Tracker",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ─── CONFIGURATIE ─────────────────────────────────────────────────────────────
TICKER = "IWDA.AS"
ISIN = "IE00B4L5Y983"
DIP_DREMPEL_PCT = 5.0
RSI_DREMPEL = 40

# Persoonlijke data via Streamlit Secrets (veilig, niet in code)
AANDELEN = int(st.secrets.get("aandelen", 35))
GEMIDDELDE_AANKOOPPRIJS = float(st.secrets.get("aankoopprijs", 112.42))

# ─── STIJL (mobiel-vriendelijk) ───────────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: #1e1e2e;
        border-radius: 16px;
        padding: 16px 20px;
        margin: 6px 0;
        border-left: 4px solid #6c63ff;
    }
    .metric-label { color: #888; font-size: 13px; margin-bottom: 2px; }
    .metric-value { color: #fff; font-size: 26px; font-weight: 700; }
    .metric-sub   { color: #aaa; font-size: 13px; }

    .signal-koop  { background:#1a3a1a; border-left:4px solid #2ecc71; border-radius:12px; padding:12px 16px; margin:6px 0; }
    .signal-wacht { background:#2a2a1a; border-left:4px solid #f39c12; border-radius:12px; padding:12px 16px; margin:6px 0; }
    .signal-info  { background:#1a2a3a; border-left:4px solid #3498db; border-radius:12px; padding:12px 16px; margin:6px 0; }

    .signal-titel { font-weight:700; font-size:15px; margin-bottom:4px; }
    .signal-tekst { color:#ccc; font-size:13px; }

    .rsi-bar-wrap { background:#2a2a2a; border-radius:8px; height:12px; margin:8px 0; overflow:hidden; }
    .rsi-bar      { height:12px; border-radius:8px; }

    h1 { font-size: 24px !important; }
    .stButton > button { width: 100%; border-radius: 12px; }
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ─── DATA FUNCTIES ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)   # Cache 5 minuten
def haal_data():
    etf = yf.Ticker(TICKER)
    hist = etf.history(period="1y", interval="1d")
    return hist


def bereken_rsi(closes: pd.Series, periode: int = 14) -> float:
    delta = closes.diff()
    winst = delta.clip(lower=0)
    verlies = -delta.clip(upper=0)
    gem_w = winst.rolling(periode).mean()
    gem_v = verlies.rolling(periode).mean()
    rs = gem_w / gem_v
    return round((100 - (100 / (1 + rs))).iloc[-1], 1)


def analyseer(hist):
    closes = hist["Close"]
    prijs = round(float(closes.iloc[-1]), 2)
    hoog_52w = round(float(closes.max()), 2)
    laag_52w = round(float(closes.min()), 2)
    dip_pct = round((hoog_52w - prijs) / hoog_52w * 100, 1)
    ma50 = round(float(closes.rolling(50).mean().iloc[-1]), 2)
    ma200 = round(float(closes.rolling(200).mean().iloc[-1]), 2)
    rsi = bereken_rsi(closes)
    dag_wijz = round(float(closes.iloc[-1] - closes.iloc[-2]), 2)
    dag_pct = round((dag_wijz / float(closes.iloc[-2])) * 100, 2)
    waarde = round(prijs * AANDELEN, 2)
    winst_verlies = round((prijs - GEMIDDELDE_AANKOOPPRIJS) * AANDELEN, 2)
    return dict(
        prijs=prijs, hoog_52w=hoog_52w, laag_52w=laag_52w, dip_pct=dip_pct,
        ma50=ma50, ma200=ma200, rsi=rsi,
        dag_wijz=dag_wijz, dag_pct=dag_pct,
        waarde=waarde, winst_verlies=winst_verlies,
    )


def bepaal_signalen(d):
    signalen = []
    if d["dip_pct"] >= DIP_DREMPEL_PCT:
        signalen.append({"type": "KOOP", "sterkte": "STERK" if d["dip_pct"] >= 10 else "MATIG",
                         "titel": f"Dip van {d['dip_pct']}% t.o.v. hoogste punt",
                         "tekst": f"Prijs €{d['prijs']} is {d['dip_pct']}% onder 52-weekshoog €{d['hoog_52w']}"})
    if d["rsi"] < RSI_DREMPEL:
        signalen.append({"type": "KOOP", "sterkte": "STERK" if d["rsi"] < 30 else "MATIG",
                         "titel": f"RSI oversold: {d['rsi']}",
                         "tekst": f"RSI onder {RSI_DREMPEL} = markt te ver gedaald, herstel verwacht"})
    if d["prijs"] > d["ma50"] > d["ma200"]:
        signalen.append({"type": "INFO", "sterkte": "INFO",
                         "titel": "Positieve trend (Golden Cross actief)",
                         "tekst": f"Prijs > MA50 ({d['ma50']}) > MA200 ({d['ma200']})"})
    verlies_pct = round((GEMIDDELDE_AANKOOPPRIJS - d["prijs"]) / GEMIDDELDE_AANKOOPPRIJS * 100, 1)
    if verlies_pct >= DIP_DREMPEL_PCT:
        signalen.append({"type": "KOOP", "sterkte": "STERK",
                         "titel": f"{verlies_pct}% onder jouw aankoopprijs",
                         "tekst": f"Bijkopen verlaagt jouw gemiddelde aankoopprijs"})
    if not signalen:
        signalen.append({"type": "WACHT", "sterkte": "INFO",
                         "titel": "Geen bijkoopsignaal",
                         "tekst": "Prijs en RSI op neutraal niveau — rustig afwachten"})
    return signalen


def maak_grafiek(hist):
    closes = hist["Close"]
    ma50 = closes.rolling(50).mean()
    ma200 = closes.rolling(200).mean()
    data_recent = hist.tail(120)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.7, 0.3], vertical_spacing=0.06)

    # Kaarsgrafiek
    fig.add_trace(go.Candlestick(
        x=data_recent.index,
        open=data_recent["Open"], high=data_recent["High"],
        low=data_recent["Low"], close=data_recent["Close"],
        name="IWDA", increasing_line_color="#2ecc71",
        decreasing_line_color="#e74c3c", showlegend=False,
    ), row=1, col=1)

    fig.add_trace(go.Scatter(x=ma50.tail(120).index, y=ma50.tail(120),
                             line=dict(color="#f39c12", width=1.5), name="MA50"), row=1, col=1)
    fig.add_trace(go.Scatter(x=ma200.tail(120).index, y=ma200.tail(120),
                             line=dict(color="#9b59b6", width=1.5), name="MA200"), row=1, col=1)

    # Aankoopprijs lijn
    fig.add_hline(y=GEMIDDELDE_AANKOOPPRIJS, line_dash="dot",
                  line_color="#3498db", annotation_text=f"Aankoop €{GEMIDDELDE_AANKOOPPRIJS}",
                  annotation_position="bottom right", row=1, col=1)

    # Volume
    kleuren = ["#2ecc71" if c >= o else "#e74c3c"
               for c, o in zip(data_recent["Close"], data_recent["Open"])]
    fig.add_trace(go.Bar(x=data_recent.index, y=data_recent["Volume"],
                         marker_color=kleuren, name="Volume", showlegend=False), row=2, col=1)

    fig.update_layout(
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
        font=dict(color="white", size=11),
        margin=dict(l=0, r=0, t=10, b=0),
        height=380,
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.05, x=0),
    )
    fig.update_xaxes(gridcolor="#222", showgrid=True)
    fig.update_yaxes(gridcolor="#222", showgrid=True)
    return fig


# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("# 📈 IWDA Tracker")
st.markdown(f"**iShares Core MSCI World** · {ISIN}")
st.caption(f"Bijgewerkt: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

col_r, col_b = st.columns([3, 1])
with col_r:
    st.markdown("")
with col_b:
    if st.button("🔄 Ververs"):
        st.cache_data.clear()
        st.rerun()

# ── DATA LADEN ────────────────────────────────────────────────────────────────
with st.spinner("Prijsdata ophalen..."):
    hist = haal_data()
    d = analyseer(hist)
    signalen = bepaal_signalen(d)

# ── PRIJS & POSITIE ───────────────────────────────────────────────────────────
pijl = "▲" if d["dag_wijz"] >= 0 else "▼"
kleur_dag = "#2ecc71" if d["dag_wijz"] >= 0 else "#e74c3c"
kleur_wv = "#2ecc71" if d["winst_verlies"] >= 0 else "#e74c3c"

st.markdown(f"""
<div class="metric-card">
  <div class="metric-label">Huidige prijs</div>
  <div class="metric-value">€{d['prijs']}</div>
  <div class="metric-sub" style="color:{kleur_dag}">{pijl} {d['dag_wijz']:+.2f} ({d['dag_pct']:+.2f}%) vandaag</div>
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    st.markdown(f"""
    <div class="metric-card" style="border-left-color:#3498db">
      <div class="metric-label">Jouw {AANDELEN} aandelen</div>
      <div class="metric-value" style="font-size:22px">€{d['waarde']:,.2f}</div>
      <div class="metric-sub" style="color:{kleur_wv}">W/V: €{d['winst_verlies']:+.2f}</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
    <div class="metric-card" style="border-left-color:#9b59b6">
      <div class="metric-label">Aankoopprijs gem.</div>
      <div class="metric-value" style="font-size:22px">€{GEMIDDELDE_AANKOOPPRIJS}</div>
      <div class="metric-sub">Break-even</div>
    </div>
    """, unsafe_allow_html=True)

# ── GRAFIEK ───────────────────────────────────────────────────────────────────
st.markdown("### 📊 Koersgrafiek (120 dagen)")
st.plotly_chart(maak_grafiek(hist), use_container_width=True, config={"displayModeBar": False})

# ── INDICATOREN ───────────────────────────────────────────────────────────────
st.markdown("### 🔢 Indicatoren")
col3, col4, col5 = st.columns(3)
col3.metric("MA50", f"€{d['ma50']}", delta=f"{round(d['prijs']-d['ma50'],2):+.2f}")
col4.metric("MA200", f"€{d['ma200']}", delta=f"{round(d['prijs']-d['ma200'],2):+.2f}")
col5.metric("52w Hoog", f"€{d['hoog_52w']}", delta=f"-{d['dip_pct']}%")

# RSI balk
rsi_kleur = "#2ecc71" if d["rsi"] < 40 else "#e74c3c" if d["rsi"] > 70 else "#f39c12"
rsi_label = "Oversold 🟢 KOPEN" if d["rsi"] < 40 else "Overbought 🔴 WACHTEN" if d["rsi"] > 70 else "Neutraal 🟡"
st.markdown(f"**RSI(14): {d['rsi']}** — {rsi_label}")
st.markdown(f"""
<div class="rsi-bar-wrap">
  <div class="rsi-bar" style="width:{d['rsi']}%; background:{rsi_kleur}"></div>
</div>
<div style="display:flex; justify-content:space-between; color:#666; font-size:11px">
  <span>0 — Oversold</span><span>30</span><span>50</span><span>70</span><span>100 — Overbought</span>
</div>
""", unsafe_allow_html=True)

# ── SIGNALEN ──────────────────────────────────────────────────────────────────
st.markdown("### 🚦 Bijkoop-signalen")
for s in signalen:
    if s["type"] == "KOOP":
        icoon = "🟢" if s["sterkte"] == "STERK" else "🟡"
        css = "signal-koop"
    elif s["type"] == "WACHT":
        icoon = "⏸️"
        css = "signal-wacht"
    else:
        icoon = "🔵"
        css = "signal-info"
    st.markdown(f"""
    <div class="{css}">
      <div class="signal-titel">{icoon} {s['titel']}</div>
      <div class="signal-tekst">{s['tekst']}</div>
    </div>
    """, unsafe_allow_html=True)

# ── DCA STRATEGIE ─────────────────────────────────────────────────────────────
st.markdown("### 💡 Strategie")
st.info("""
**DCA + Signalen aanpak:**
- 📅 Koop maandelijks een vast bedrag (bv. €100–€200)
- 📉 Extra bijkopen als RSI < 40 of prijs > 5% gedaald
- 🚫 Niet verkopen bij dips — MSCI World herstelt historisch altijd
- ⏳ Horizon: minimaal 10 jaar
""")

# ── FOOTER ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(f"Data via Yahoo Finance · IWDA.AS (Amsterdam) · Elke 5 min ververst")
st.caption("⚠️ Geen beleggingsadvies — enkel informatief")
