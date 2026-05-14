"""
IWDA ETF Tracker — iShares Core MSCI World UCITS ETF (IE00B4L5Y983)
Geeft bijkoop-signalen op basis van RSI, voortschrijdend gemiddelde en dip-drempel.
"""

import yfinance as yf
import pandas as pd
import requests
import subprocess
from datetime import datetime, timedelta

# ─── CONFIGURATIE ────────────────────────────────────────────────────────────
TICKER = "IWDA.AS"          # Amsterdam listing op Yahoo Finance
ISIN = "IE00B4L5Y983"
AANDELEN = 35               # Jouw huidige positie
GEMIDDELDE_AANKOOPPRIJS = 112.42  # Gemiddelde aankoopprijs per aandeel

DIP_DREMPEL_PCT = 5.0       # Bijkoop als prijs >5% onder 52-weeks hoogste punt
RSI_DREMPEL = 40            # Bijkoop als RSI < 40 (oversold)
MA_KORT = 50                # Kort voortschrijdend gemiddelde (dagen)
MA_LANG = 200               # Lang voortschrijdend gemiddelde (dagen)
# ─────────────────────────────────────────────────────────────────────────────


def bereken_rsi(closes: pd.Series, periode: int = 14) -> float:
    delta = closes.diff()
    winst = delta.clip(lower=0)
    verlies = -delta.clip(upper=0)
    gem_winst = winst.rolling(periode).mean()
    gem_verlies = verlies.rolling(periode).mean()
    rs = gem_winst / gem_verlies
    rsi = 100 - (100 / (1 + rs))
    return round(rsi.iloc[-1], 1)


def haal_prijsdata() -> pd.DataFrame:
    etf = yf.Ticker(TICKER)
    hist = etf.history(period="1y", interval="1d")
    return hist


def analyseer(hist: pd.DataFrame) -> dict:
    closes = hist["Close"]
    prijs_nu = round(closes.iloc[-1], 2)
    hoog_52w = round(closes.max(), 2)
    laag_52w = round(closes.min(), 2)
    dip_pct = round((hoog_52w - prijs_nu) / hoog_52w * 100, 1)

    ma50 = round(closes.rolling(MA_KORT).mean().iloc[-1], 2)
    ma200 = round(closes.rolling(MA_LANG).mean().iloc[-1], 2)
    rsi = bereken_rsi(closes)

    waarde_positie = round(prijs_nu * AANDELEN, 2)
    dagwijziging = round(closes.iloc[-1] - closes.iloc[-2], 2)
    dagwijziging_pct = round((dagwijziging / closes.iloc[-2]) * 100, 2)

    return {
        "prijs": prijs_nu,
        "dag_wijziging": dagwijziging,
        "dag_wijziging_pct": dagwijziging_pct,
        "hoog_52w": hoog_52w,
        "laag_52w": laag_52w,
        "dip_pct": dip_pct,
        "ma50": ma50,
        "ma200": ma200,
        "rsi": rsi,
        "waarde_positie": waarde_positie,
    }


def bepaal_signalen(data: dict) -> list[dict]:
    signalen = []

    # Signaal 1: Dip t.o.v. 52-weekshoogste
    if data["dip_pct"] >= DIP_DREMPEL_PCT:
        signalen.append({
            "type": "BIJKOOP",
            "reden": f"Prijs {data['dip_pct']}% onder 52-weekshoogste (drempel: {DIP_DREMPEL_PCT}%)",
            "sterkte": "STERK" if data["dip_pct"] >= 10 else "MATIG",
        })

    # Signaal 2: RSI oversold
    if data["rsi"] < RSI_DREMPEL:
        signalen.append({
            "type": "BIJKOOP",
            "reden": f"RSI = {data['rsi']} (onder {RSI_DREMPEL} = oversold)",
            "sterkte": "STERK" if data["rsi"] < 30 else "MATIG",
        })

    # Signaal 3: Prijs boven beide MA's = positieve trend
    if data["prijs"] > data["ma50"] > data["ma200"]:
        signalen.append({
            "type": "TREND",
            "reden": f"Prijs ({data['prijs']}) > MA50 ({data['ma50']}) > MA200 ({data['ma200']}) — opwaartse trend",
            "sterkte": "INFO",
        })

    # Signaal 4: MA50 kruist MA200 (Golden Cross)
    if data["ma50"] > data["ma200"] and data["prijs"] < data["ma50"]:
        signalen.append({
            "type": "BIJKOOP",
            "reden": f"Golden Cross: MA50 ({data['ma50']}) boven MA200 ({data['ma200']}), prijs dip eronder",
            "sterkte": "MATIG",
        })

    # Signaal 5: Aankoopprijs gekend
    if GEMIDDELDE_AANKOOPPRIJS:
        verlies_pct = round((GEMIDDELDE_AANKOOPPRIJS - data["prijs"]) / GEMIDDELDE_AANKOOPPRIJS * 100, 1)
        if verlies_pct >= DIP_DREMPEL_PCT:
            signalen.append({
                "type": "BIJKOOP",
                "reden": f"Prijs {verlies_pct}% onder jouw gemiddelde aankoopprijs (€{GEMIDDELDE_AANKOOPPRIJS})",
                "sterkte": "STERK",
            })

    if not signalen:
        signalen.append({
            "type": "WACHT",
            "reden": "Geen bijkoop-signalen actief — prijsniveau neutraal",
            "sterkte": "INFO",
        })

    return signalen


def stuur_notificatie(titel: str, boodschap: str):
    script = f'display notification "{boodschap}" with title "{titel}" sound name "Ping"'
    subprocess.run(["osascript", "-e", script], capture_output=True)


def haal_politici_trades() -> list[dict]:
    """Haalt recente ETF/sector trades op van Capitol Trades (US politici)."""
    try:
        url = "https://www.capitoltrades.com/api/trades?assetType=etf&pageSize=10"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            trades = data.get("trades", data.get("data", []))
            return trades[:5]
    except Exception:
        pass
    return []


def druk_rapport():
    print("=" * 60)
    print(f"  IWDA TRACKER — iShares Core MSCI World")
    print(f"  ISIN: {ISIN}")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 60)

    print("\n Prijsdata ophalen...")
    hist = haal_prijsdata()
    data = analyseer(hist)

    # ── POSITIE ──
    dag_sym = "▲" if data["dag_wijziging"] >= 0 else "▼"
    print(f"\n JOUW POSITIE")
    print(f"  {AANDELEN} aandelen IWDA")
    print(f"  Huidige prijs : €{data['prijs']}  {dag_sym} {data['dag_wijziging']:+.2f} ({data['dag_wijziging_pct']:+.2f}%)")
    print(f"  Waarde        : €{data['waarde_positie']:,.2f}")
    if GEMIDDELDE_AANKOOPPRIJS:
        winst = round((data["prijs"] - GEMIDDELDE_AANKOOPPRIJS) * AANDELEN, 2)
        print(f"  Aankoopprijs  : €{GEMIDDELDE_AANKOOPPRIJS}  →  winst/verlies: €{winst:+.2f}")

    # ── MARKTDATA ──
    print(f"\n MARKTINDICATOREN")
    print(f"  52-weeks hoog : €{data['hoog_52w']}  ({data['dip_pct']}% onder huidig)")
    print(f"  52-weeks laag : €{data['laag_52w']}")
    print(f"  MA50          : €{data['ma50']}")
    print(f"  MA200         : €{data['ma200']}")
    print(f"  RSI(14)       : {data['rsi']}")

    # ── SIGNALEN ──
    signalen = bepaal_signalen(data)
    print(f"\n BIJKOOP-SIGNALEN")
    for s in signalen:
        icoon = {"BIJKOOP": "→ BIJKOPEN", "TREND": "→ TREND   ", "WACHT": "→ WACHT   "}.get(s["type"], "→")
        sterkte_str = f"[{s['sterkte']}]" if s["sterkte"] != "INFO" else ""
        print(f"  {icoon} {sterkte_str} {s['reden']}")

    # ── NOTIFICATIE ──
    bijkoop_signalen = [s for s in signalen if s["type"] == "BIJKOOP"]
    sterke_signalen = [s for s in bijkoop_signalen if s["sterkte"] == "STERK"]
    if sterke_signalen:
        stuur_notificatie(
            "IWDA — BIJKOPEN!",
            f"€{data['prijs']} | RSI {data['rsi']} | {sterke_signalen[0]['reden'][:60]}"
        )
    elif bijkoop_signalen:
        stuur_notificatie(
            "IWDA — Potentieel bijkopen",
            f"€{data['prijs']} | RSI {data['rsi']} | {bijkoop_signalen[0]['reden'][:60]}"
        )
    else:
        stuur_notificatie(
            "IWDA — Dagrapport",
            f"€{data['prijs']} ({data['dag_wijziging_pct']:+.2f}%) | RSI {data['rsi']} | Geen bijkoopsignaal"
        )

    # ── RSI INTERPRETATIE ──
    print(f"\n RSI UITLEG")
    if data["rsi"] < 30:
        print("  RSI < 30: Sterk oversold — goede bijkoop-kans")
    elif data["rsi"] < 40:
        print("  RSI < 40: Oversold — potentieel bijkoop-moment")
    elif data["rsi"] < 60:
        print("  RSI 40-60: Neutraal — geen actie nodig")
    elif data["rsi"] < 70:
        print("  RSI 60-70: Licht overbought — voorzichtig zijn")
    else:
        print("  RSI > 70: Overbought — niet ideaal om bij te kopen")

    # ── POLITICI ──
    print(f"\n POLITICI TRADES (Capitol Trades — US Congress)")
    trades = haal_politici_trades()
    if trades:
        for t in trades:
            naam = t.get("politician", {}).get("name", t.get("name", "?"))
            ticker = t.get("asset", {}).get("ticker", t.get("ticker", "?"))
            richting = t.get("type", t.get("transactionType", "?"))
            datum = t.get("transactionDate", t.get("date", "?"))
            print(f"  {datum}  {naam:<25} {richting:<5} {ticker}")
    else:
        print("  Geen data beschikbaar (Capitol Trades API offline of geblokkeerd)")
        print("  Bekijk zelf: https://www.capitoltrades.com/trades?assetType=etf")

    # ── DCA ADVIES ──
    print(f"\n DCA ADVIES (Dollar Cost Averaging)")
    print(f"  Voor MSCI World ETF: best maandelijks een vast bedrag bijkopen.")
    print(f"  Bijkoop-signalen zijn een BONUS — niet wachten op het perfecte moment.")
    print(f"  Strategie: vaste maandelijkse aankoop + extra bij RSI < 40 of dip > 5%")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    druk_rapport()
