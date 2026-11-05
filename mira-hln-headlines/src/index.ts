import { AppServer, type AppSession } from "@mentra/sdk";
import { HeadlineCache } from "./feed";
import { HeadlineViewer } from "./viewer";

const PACKAGE_NAME = process.env.PACKAGE_NAME ?? (() => { throw new Error("PACKAGE_NAME ontbreekt in .env"); })();
const MENTRAOS_API_KEY = process.env.MENTRAOS_API_KEY ?? (() => { throw new Error("MENTRAOS_API_KEY ontbreekt in .env"); })();
const PORT = Number(process.env.PORT ?? 3000);

const FEED_URL = process.env.HLN_RSS_URL ?? "https://www.hln.be/home/rss.xml";
const ROTATE_MS = Number(process.env.ROTATE_SECONDS ?? 15) * 1000;
const REFRESH_MS = Number(process.env.REFRESH_MINUTES ?? 5) * 60_000;
const MAX_HEADLINES = Number(process.env.MAX_HEADLINES ?? 15);

/** Eén gedeelde cache voor alle gebruikers. */
const cache = new HeadlineCache(FEED_URL, MAX_HEADLINES, REFRESH_MS);

class HlnHeadlinesApp extends AppServer {
  private viewers = new Map<string, HeadlineViewer>();

  protected async onSession(session: AppSession, sessionId: string, userId: string): Promise<void> {
    session.logger.info(`Nieuwe sessie ${sessionId} voor ${userId}`);
    const viewer = new HeadlineViewer(session, cache, { rotateMs: ROTATE_MS, refreshMs: REFRESH_MS });
    this.viewers.set(sessionId, viewer);
    await viewer.start();
  }

  protected async onStop(sessionId: string, userId: string, reason: string): Promise<void> {
    this.viewers.get(sessionId)?.stop();
    this.viewers.delete(sessionId);
    console.log(`Sessie ${sessionId} (${userId}) gestopt: ${reason}`);
  }
}

const app = new HlnHeadlinesApp({
  packageName: PACKAGE_NAME,
  apiKey: MENTRAOS_API_KEY,
  port: PORT,
});

app.start().catch((err) => {
  console.error("Kon de app niet starten:", err);
  process.exit(1);
});
