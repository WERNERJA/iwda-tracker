import { XMLParser } from "fast-xml-parser";

export interface Headline {
  title: string;
  description: string;
  link: string;
  published?: Date;
}

const parser = new XMLParser({
  ignoreAttributes: false,
  cdataPropName: "__cdata",
  processEntities: true,
  htmlEntities: true,
});

/** Haalt tekst uit een veld dat een string, getal of CDATA-object kan zijn. */
function text(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string" || typeof value === "number") return String(value);
  if (typeof value === "object") {
    const v = value as Record<string, unknown>;
    if ("__cdata" in v) return text(v.__cdata);
    if ("#text" in v) return text(v["#text"]);
  }
  return "";
}

/** Verwijdert HTML-tags en overtollige witruimte zodat de tekst leesbaar is op de bril. */
export function clean(input: string): string {
  return input
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'")
    .replace(/\s+/g, " ")
    .trim();
}

/** Parset een RSS 2.0- of Atom-feed naar een lijst headlines. */
export function parseFeed(xml: string): Headline[] {
  const doc = parser.parse(xml);

  const rssItems = doc?.rss?.channel?.item;
  const atomItems = doc?.feed?.entry;
  const raw = rssItems ?? atomItems ?? [];
  const items: any[] = Array.isArray(raw) ? raw : [raw];

  return items
    .map((item) => {
      const link =
        typeof item.link === "object" && item.link?.["@_href"]
          ? item.link["@_href"]
          : text(item.link);
      const date = text(item.pubDate ?? item.updated ?? item.published);
      const parsed = date ? new Date(date) : undefined;
      return {
        title: clean(text(item.title)),
        description: clean(text(item.description ?? item.summary)),
        link: link.trim(),
        published: parsed && !isNaN(parsed.getTime()) ? parsed : undefined,
      } satisfies Headline;
    })
    .filter((h) => h.title.length > 0);
}

/** Haalt de feed op en geeft de headlines terug. */
export async function fetchHeadlines(url: string, max: number): Promise<Headline[]> {
  const res = await fetch(url, {
    headers: {
      "User-Agent": "mira-hln-headlines/1.0 (MentraOS app)",
      Accept: "application/rss+xml, application/xml, text/xml",
    },
    signal: AbortSignal.timeout(10_000),
  });
  if (!res.ok) throw new Error(`Feed gaf HTTP ${res.status}`);
  return parseFeed(await res.text()).slice(0, max);
}

/** Houdt een gedeelde, periodiek ververste cache bij zodat niet elke sessie apart HLN bevraagt. */
export class HeadlineCache {
  private headlines: Headline[] = [];
  private lastFetch = 0;
  private inFlight: Promise<Headline[]> | null = null;

  constructor(
    private readonly url: string,
    private readonly max: number,
    private readonly ttlMs: number,
    private readonly fetcher: typeof fetchHeadlines = fetchHeadlines,
  ) {}

  async get(force = false): Promise<Headline[]> {
    const fresh = Date.now() - this.lastFetch < this.ttlMs;
    if (!force && fresh && this.headlines.length) return this.headlines;
    if (this.inFlight) return this.inFlight;

    this.inFlight = this.fetcher(this.url, this.max)
      .then((list) => {
        if (list.length) {
          this.headlines = list;
          this.lastFetch = Date.now();
        }
        return this.headlines;
      })
      .catch((err) => {
        // Bij een fout tonen we de laatst bekende headlines (als die er zijn).
        if (this.headlines.length) return this.headlines;
        throw err;
      })
      .finally(() => {
        this.inFlight = null;
      });
    return this.inFlight;
  }
}
