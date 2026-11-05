# HLN Headlines voor je smart glasses (MentraOS)

Deze MentraOS-app toont de laatste headlines van [HLN](https://www.hln.be) op je smart glasses.
De app is gebouwd met de officiële [`@mentra/sdk`](https://www.npmjs.com/package/@mentra/sdk).
Het is dezelfde SDK waarmee de ingebouwde Mira-assistent werkt.

## Wat doet de app?

- Haalt de HLN-RSS-feed op (standaard `https://www.hln.be/home/rss.xml`) en ververst die elke 5 minuten.
- Toont één headline per kaart: `HLN 3/15 · 17:30`. De headlines wisselen automatisch elke 15 seconden.
- Zet de belangrijkste headline ook op je dashboard.

### Bediening

| Actie | Knop | Touchpad | Stem (NL) |
|---|---|---|---|
| Volgende headline | kort drukken | swipe vooruit | "volgende" |
| Vorige headline | – | swipe achteruit | "vorige" / "terug" |
| Samenvatting tonen | – | tik | "meer" / "lees meer" |
| Vernieuwen | lang drukken | – | "vernieuw" |
| Pauzeren / hervatten | – | dubbel tikken | "pauze" / "hervat" |
| Voorlezen | – | – | "voorlezen" |

## Installatie

1. Installeer [Bun](https://bun.sh) en [ngrok](https://ngrok.com). Maak in ngrok een gratis *static domain* aan.
2. Ga naar [console.mentra.glass](https://console.mentra.glass). Meld je aan met hetzelfde account als in de MentraOS-app op je telefoon.
   - Klik op **Create App**. Kies een package name, bijvoorbeeld `com.werner.hlnheadlines`.
   - Vul bij **Public URL** je ngrok-URL in.
   - Voeg de permissie **Microphone** toe. Die is nodig voor de spraakcommando's.
   - Kopieer de **API key**.
3. Configureer en start de app:

   ```bash
   cd mira-hln-headlines
   bun install
   cp .env.example .env   # vul PACKAGE_NAME en MENTRAOS_API_KEY in
   bun run dev
   ```

4. Zet de app open naar het internet:

   ```bash
   ngrok http --url=<jouw-static-domain> 3000
   ```

5. Open de MentraOS-app op je telefoon en start **HLN Headlines**.

## Configuratie (`.env`)

| Variabele | Standaard | Uitleg |
|---|---|---|
| `PACKAGE_NAME` | – | Moet gelijk zijn aan de naam in de console |
| `MENTRAOS_API_KEY` | – | API key uit de console |
| `PORT` | `3000` | Poort van de server |
| `HLN_RSS_URL` | `https://www.hln.be/home/rss.xml` | Feed-URL. Je kan bv. ook een rubriekfeed gebruiken |
| `ROTATE_SECONDS` | `15` | Hoe lang een headline in beeld blijft |
| `REFRESH_MINUTES` | `5` | Hoe vaak de feed ververst wordt |
| `MAX_HEADLINES` | `15` | Maximum aantal headlines in de lijst |

## Ontwikkeling

```bash
bun test
```

```bash
bun run typecheck
```

Voor permanent gebruik zonder ngrok kan je de app hosten op een cloudplatform zoals Railway, Fly.io of Render.
Zet daarna de Public URL in de console op dat adres.
