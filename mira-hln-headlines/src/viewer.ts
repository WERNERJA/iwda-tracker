import type { AppSession } from "@mentra/sdk";
import type { Headline, HeadlineCache } from "./feed";

export type Command = "next" | "previous" | "details" | "refresh" | "pause" | "resume" | "read";

/** Spraakcommando's (Nederlands en Engels) -> actie. Eerste match wint. */
const VOICE_COMMANDS: Array<[RegExp, Command]> = [
  [/\b(volgende|verder|next)\b/, "next"],
  [/\b(vorige|terug|previous|back)\b/, "previous"],
  [/\b(meer|details|lees meer|more)\b/, "details"],
  [/\b(vernieuw|ververs|update|refresh)\b/, "refresh"],
  [/\b(pauze|pauzeer|stop|wacht|pause)\b/, "pause"],
  [/\b(start|hervat|doorgaan|resume|play)\b/, "resume"],
  [/\b(voorlezen|lees voor|read)\b/, "read"],
];

export function parseCommand(spoken: string): Command | null {
  const s = spoken.toLowerCase().replace(/[.,!?]/g, " ");
  for (const [re, cmd] of VOICE_COMMANDS) if (re.test(s)) return cmd;
  return null;
}

export interface ViewerOptions {
  rotateMs: number;
  refreshMs: number;
}

/**
 * Beheert wat één gebruiker op zijn bril ziet: een roterende lijst HLN-headlines
 * die je met de knop, het touchpad of je stem kan bedienen.
 */
export class HeadlineViewer {
  private headlines: Headline[] = [];
  private index = 0;
  private paused = false;
  private rotateTimer: ReturnType<typeof setInterval> | null = null;
  private refreshTimer: ReturnType<typeof setInterval> | null = null;
  private cleanups: Array<() => void> = [];

  constructor(
    private readonly session: AppSession,
    private readonly cache: HeadlineCache,
    private readonly opts: ViewerOptions,
  ) {}

  async start(): Promise<void> {
    this.session.layouts.showTextWall("HLN headlines laden…");
    this.bindInputs();
    await this.refresh(false);
    this.refreshTimer = setInterval(() => void this.refresh(false), this.opts.refreshMs);
    this.restartRotation();
  }

  stop(): void {
    if (this.rotateTimer) clearInterval(this.rotateTimer);
    if (this.refreshTimer) clearInterval(this.refreshTimer);
    this.rotateTimer = this.refreshTimer = null;
    for (const off of this.cleanups) off();
    this.cleanups = [];
  }

  async handle(cmd: Command): Promise<void> {
    switch (cmd) {
      case "next":
        this.move(1);
        break;
      case "previous":
        this.move(-1);
        break;
      case "details":
        this.showDetails();
        break;
      case "refresh":
        this.session.layouts.showTextWall("Headlines vernieuwen…", { durationMs: 2000 });
        await this.refresh(true);
        break;
      case "pause":
        this.paused = true;
        this.render("⏸ ");
        break;
      case "resume":
        this.paused = false;
        this.move(0);
        break;
      case "read":
        await this.readAloud();
        break;
    }
  }

  private bindInputs(): void {
    const { events } = this.session;

    // Fysieke knop: kort = volgende, lang = vernieuwen.
    this.cleanups.push(
      events.onButtonPress((b) => void this.handle(b.pressType === "long" ? "refresh" : "next")),
    );

    // Touchpad (indien aanwezig op de bril).
    this.cleanups.push(
      events.onTouchEvent((t) => {
        const map: Record<string, Command> = {
          forward_swipe: "next",
          backward_swipe: "previous",
          single_tap: "details",
          double_tap: this.paused ? "resume" : "pause",
        };
        const cmd = map[t.gesture_name];
        if (cmd) void this.handle(cmd);
      }),
    );

    // Spraakbediening in het Nederlands.
    this.cleanups.push(
      events.onTranscriptionForLanguage(
        "nl-BE",
        (data) => {
          if (!data.isFinal) return;
          const cmd = parseCommand(data.text);
          if (cmd) void this.handle(cmd);
        },
        { hints: ["nl", "en"] },
      ),
    );
  }

  private async refresh(force: boolean): Promise<void> {
    try {
      const list = await this.cache.get(force);
      const currentLink = this.headlines[this.index]?.link;
      this.headlines = list;
      // Blijf bij dezelfde headline als die nog in de lijst staat, anders terug naar de nieuwste.
      const keep = list.findIndex((h) => h.link === currentLink);
      this.index = force || keep < 0 ? 0 : keep;
      this.updateDashboard();
      this.render();
    } catch (err) {
      this.session.logger.error({ err }, "Kon HLN-feed niet ophalen");
      if (!this.headlines.length) {
        this.session.layouts.showReferenceCard("HLN", "Kon de headlines niet laden. Lang drukken om opnieuw te proberen.");
      }
    }
  }

  private move(delta: number): void {
    if (!this.headlines.length) return;
    const n = this.headlines.length;
    this.index = (((this.index + delta) % n) + n) % n;
    this.render();
    this.restartRotation();
  }

  private restartRotation(): void {
    if (this.rotateTimer) clearInterval(this.rotateTimer);
    this.rotateTimer = setInterval(() => {
      if (!this.paused) this.move(1);
    }, this.opts.rotateMs);
  }

  private render(prefix = this.paused ? "⏸ " : ""): void {
    const h = this.headlines[this.index];
    if (!h) return;
    const title = `${prefix}HLN ${this.index + 1}/${this.headlines.length}${timeLabel(h.published)}`;
    this.session.layouts.showReferenceCard(title, h.title);
  }

  private showDetails(): void {
    const h = this.headlines[this.index];
    if (!h) return;
    const body = h.description ? truncate(h.description, 220) : "Geen samenvatting beschikbaar.";
    this.session.layouts.showReferenceCard(truncate(h.title, 60), body);
    this.restartRotation(); // geef de gebruiker de volle rotatietijd om te lezen
  }

  private async readAloud(): Promise<void> {
    const h = this.headlines[this.index];
    if (!h) return;
    try {
      await this.session.audio.speak(h.description ? `${h.title}. ${h.description}` : h.title);
    } catch (err) {
      this.session.logger.warn({ err }, "Voorlezen niet beschikbaar");
    }
  }

  private updateDashboard(): void {
    const top = this.headlines[0];
    if (!top) return;
    try {
      this.session.dashboard.content.writeToMain(`HLN: ${truncate(top.title, 80)}`);
    } catch {
      // Dashboard is optioneel; niet elke bril/versie ondersteunt het.
    }
  }
}

export function truncate(s: string, max: number): string {
  return s.length <= max ? s : s.slice(0, max - 1).trimEnd() + "…";
}

function timeLabel(d?: Date): string {
  if (!d) return "";
  const time = d.toLocaleTimeString("nl-BE", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Brussels",
  });
  return ` · ${time}`;
}
