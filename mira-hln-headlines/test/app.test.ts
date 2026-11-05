import { describe, expect, test } from "bun:test";
import { HeadlineCache, parseFeed, type Headline } from "../src/feed";
import { HeadlineViewer, parseCommand } from "../src/viewer";

const RSS = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>HLN</title>
  <item>
    <title><![CDATA[Eerste &amp; belangrijkste nieuws]]></title>
    <link>https://www.hln.be/binnenland/a1</link>
    <description><![CDATA[<p>Een <b>samenvatting</b> van het nieuws.</p>]]></description>
    <pubDate>Thu, 05 Nov 2026 16:30:00 GMT</pubDate>
  </item>
  <item>
    <title>Tweede headline</title>
    <link>https://www.hln.be/sport/a2</link>
  </item>
  <item><title></title><link>https://x</link></item>
</channel></rss>`;

describe("parseFeed", () => {
  test("parset RSS, CDATA, HTML en lege items", () => {
    const items = parseFeed(RSS);
    expect(items).toHaveLength(2);
    expect(items[0].title).toBe("Eerste & belangrijkste nieuws");
    expect(items[0].description).toBe("Een samenvatting van het nieuws.");
    expect(items[0].link).toBe("https://www.hln.be/binnenland/a1");
    expect(items[0].published?.toISOString()).toBe("2026-11-05T16:30:00.000Z");
    expect(items[1].published).toBeUndefined();
  });

  test("enkel item wordt ook een lijst", () => {
    const xml = `<rss><channel><item><title>Solo</title><link>l</link></item></channel></rss>`;
    expect(parseFeed(xml).map((h) => h.title)).toEqual(["Solo"]);
  });
});

describe("parseCommand", () => {
  test.each([
    ["Volgende.", "next"],
    ["ga terug", "previous"],
    ["lees meer", "details"],
    ["vernieuw", "refresh"],
    ["Pauze!", "pause"],
    ["hervat", "resume"],
    ["voorlezen", "read"],
    ["het regent vandaag", null],
  ])("%s -> %s", (input, expected) => {
    expect(parseCommand(input)).toBe(expected as any);
  });
});

describe("HeadlineCache", () => {
  test("cachet en valt terug op oude data bij fout", async () => {
    let calls = 0;
    let fail = false;
    const cache = new HeadlineCache("u", 10, 60_000, async () => {
      calls++;
      if (fail) throw new Error("down");
      return [{ title: `t${calls}`, description: "", link: `l${calls}` }];
    });
    expect((await cache.get())[0].title).toBe("t1");
    expect((await cache.get())[0].title).toBe("t1");
    expect(calls).toBe(1);
    fail = true;
    expect((await cache.get(true))[0].title).toBe("t1");
  });
});

describe("HeadlineViewer", () => {
  function fakeSession() {
    const shown: string[][] = [];
    const handlers: Record<string, (d: any) => void> = {};
    const session: any = {
      layouts: {
        showTextWall: (t: string) => shown.push(["wall", t]),
        showReferenceCard: (a: string, b: string) => shown.push([a, b]),
      },
      events: {
        onButtonPress: (h: any) => ((handlers.button = h), () => {}),
        onTouchEvent: (h: any) => ((handlers.touch = h), () => {}),
        onTranscriptionForLanguage: (_l: string, h: any) => ((handlers.voice = h), () => {}),
      },
      dashboard: { content: { writeToMain: (t: string) => shown.push(["dash", t]) } },
      audio: { speak: async () => ({}) },
      logger: { info() {}, warn() {}, error() {} },
    };
    return { session, shown, handlers };
  }

  test("toont headlines en reageert op knop, swipe en stem", async () => {
    const list: Headline[] = [
      { title: "A", description: "over A", link: "a" },
      { title: "B", description: "", link: "b" },
    ];
    const cache = new HeadlineCache("u", 10, 60_000, async () => list);
    const { session, shown, handlers } = fakeSession();
    const viewer = new HeadlineViewer(session, cache, { rotateMs: 60_000, refreshMs: 60_000 });
    await viewer.start();

    expect(shown).toContainEqual(["dash", "HLN: A"]);
    expect(shown.at(-1)).toEqual(["HLN 1/2", "A"]);

    handlers.button({ pressType: "short" });
    expect(shown.at(-1)).toEqual(["HLN 2/2", "B"]);

    handlers.touch({ gesture_name: "forward_swipe" });
    expect(shown.at(-1)).toEqual(["HLN 1/2", "A"]);

    handlers.voice({ isFinal: true, text: "Vorige" });
    await Bun.sleep(0);
    expect(shown.at(-1)).toEqual(["HLN 2/2", "B"]);

    handlers.voice({ isFinal: true, text: "Volgende" });
    handlers.voice({ isFinal: true, text: "lees meer" });
    await Bun.sleep(0);
    expect(shown.at(-1)).toEqual(["A", "over A"]);

    viewer.stop();
  });
});
