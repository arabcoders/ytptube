import { describe, it, expect } from 'bun:test'
import { MatchFilterParser } from '~/utils/ytdlp'

function normalize(filters: string[]): Set<string> {
  return new Set(filters.map(f => f.split("&").map(x => x.trim()).sort().join("&")));
}

describe("MatchFilterParser", () => {
  it("handles simple AND", () => {
    const parser = new MatchFilterParser("filesize>1000000 & duration<600");

    expect(parser.evaluate({ filesize: 2_000_000, duration: 200 })).toBe(true);
    expect(parser.evaluate({ filesize: 500_000, duration: 200 })).toBe(false);
    expect(parser.evaluate({ filesize: 2_000_000, duration: 800 })).toBe(false);
  });

  it("handles OR", () => {
    const parser = new MatchFilterParser("uploader='BBC' || uploader='NHK'");

    expect(parser.evaluate({ uploader: "BBC" })).toBe(true);
    expect(parser.evaluate({ uploader: "NHK" })).toBe(true);
    expect(parser.evaluate({ uploader: "CNN" })).toBe(false);
  });

  it("handles grouping", () => {
    const parser = new MatchFilterParser("(filesize>1000000 & duration<600) || uploader='BBC'");

    expect(parser.evaluate({ filesize: 2_000_000, duration: 200 })).toBe(true);
    expect(parser.evaluate({ uploader: "BBC" })).toBe(true);
    expect(parser.evaluate({ filesize: 500_000, duration: 200, uploader: "CNN" })).toBe(false);
  });

  it("handles unary presence", () => {
    expect(new MatchFilterParser("duration").evaluate({ duration: 100 })).toBe(true);
    expect(new MatchFilterParser("duration").evaluate({})).toBe(false);
    expect(new MatchFilterParser("!duration").evaluate({})).toBe(true);
    expect(new MatchFilterParser("!duration").evaluate({ duration: 100 })).toBe(false);
  });

  it("parses duration with numeric values", () => {
    expect(new MatchFilterParser("duration<120").evaluate({ duration: 30 })).toBe(true);
    expect(new MatchFilterParser("duration<120").evaluate({ duration: 200 })).toBe(false);

    expect(new MatchFilterParser("duration<90").evaluate({ duration: 30 })).toBe(true);
    expect(new MatchFilterParser("duration<90").evaluate({ duration: 120 })).toBe(false);

    expect(new MatchFilterParser("duration<3600").evaluate({ duration: 3599 })).toBe(true);
    expect(new MatchFilterParser("duration<3600").evaluate({ duration: 3700 })).toBe(false);
  });

  it("parses filesize with numeric values", () => {
    expect(new MatchFilterParser("filesize>1000000").evaluate({ filesize: 2_000_000 })).toBe(true);
    expect(new MatchFilterParser("filesize>1000000").evaluate({ filesize: 500_000 })).toBe(false);

    expect(new MatchFilterParser("filesize>=1073741824").evaluate({ filesize: 2 ** 30 })).toBe(true);
    expect(new MatchFilterParser("filesize>=1073741824").evaluate({ filesize: 1000000 })).toBe(false);
  });

  it("handles string operators", () => {
    const d = { uploader: "BBC News Channel" };

    expect(new MatchFilterParser("uploader*='News'").evaluate(d)).toBe(true);
    expect(new MatchFilterParser("uploader^='BBC'").evaluate(d)).toBe(true);
    expect(new MatchFilterParser("uploader$='Channel'").evaluate(d)).toBe(true);
    expect(new MatchFilterParser("uploader~='News\\s+Channel'").evaluate(d)).toBe(true);

    expect(new MatchFilterParser("uploader*='CNN'").evaluate(d)).toBe(false);
    expect(new MatchFilterParser("uploader^='CNN'").evaluate(d)).toBe(false);
    expect(new MatchFilterParser("uploader$='BBC'").evaluate(d)).toBe(false);
    expect(new MatchFilterParser("uploader~='News\\s+Network'").evaluate(d)).toBe(false);
  });

  it("handles spaces around operators", () => {
    const d = {
      "channel_id": "UC-7oMv6E4Uz2tF51w5Sj49w",
      "uploader": "BBC"
    };

    expect(new MatchFilterParser("channel_id = 'UC-7oMv6E4Uz2tF51w5Sj49w'").evaluate(d)).toBe(true);
    expect(new MatchFilterParser("channel_id = 'different-id'").evaluate(d)).toBe(false);

    expect(new MatchFilterParser("channel_id = 'UC-7oMv6E4Uz2tF51w5Sj49w' & uploader = 'BBC'").evaluate(d)).toBe(true);
    expect(new MatchFilterParser("channel_id = 'different-id' & uploader = 'BBC'").evaluate(d)).toBe(false);

    expect(new MatchFilterParser("channel_id = 'UCfmrcEdes7yDtEISGPM1T-A' & availability = subscriber_only").evaluate(d)).toBe(false);
  });

  it("reproduces original bug report", () => {
    const testData = {
      "age_limit": 0,
      "comment_count": 6,
      "channel_id": "UC-7oMv6E4Uz2tF51w5Sj49w",
      "uploader_url": "https://www.youtube.com/@PlayFramePlus"
    };

    const filter = "channel_id = 'UCfmrcEdes7yDtEISGPM1T-A' & availability = subscriber_only";
    expect(new MatchFilterParser(filter).evaluate(testData)).toBe(false);

    expect(new MatchFilterParser("channel_id = 'UCfmrcEdes7yDtEISGPM1T-A'").evaluate(testData)).toBe(false);
    expect(new MatchFilterParser("availability = subscriber_only").evaluate(testData)).toBe(false);

    expect(new MatchFilterParser("channel_id = 'UC-7oMv6E4Uz2tF51w5Sj49w'").evaluate(testData)).toBe(true);
  });

  it("tests OR operator precedence", () => {
    const testData = {
      "age_limit": 0,
      "fps": 120,
      "like_count": 81,
    };

    const expr1 = "(age_limit=0 & fps=120) || like_count=81";
    expect(new MatchFilterParser(expr1).evaluate(testData)).toBe(true);

    const expr2 = "age_limit=0 & fps=120 || like_count=81";
    expect(new MatchFilterParser(expr2).evaluate(testData)).toBe(true);

    const testDataPartial = {
      "age_limit": 0,
      "fps": 60,
      "like_count": 81,
    };

    expect(new MatchFilterParser(expr1).evaluate(testDataPartial)).toBe(true);
    expect(new MatchFilterParser(expr2).evaluate(testDataPartial)).toBe(true);

    const testDataEdge = {
      "age_limit": 1,
      "fps": 60,
      "like_count": 81,
    };

    expect(new MatchFilterParser(expr1).evaluate(testDataEdge)).toBe(true);
    expect(new MatchFilterParser(expr2).evaluate(testDataEdge)).toBe(true);
  });

  it("tests complex OR precedence scenarios", () => {
    const testDataOrOnly = {
      "age_limit": 1,
      "fps": 60,
      "like_count": 81,
    };

    const expr = "age_limit=0 & fps=120 || like_count=81";
    expect(new MatchFilterParser(expr).evaluate(testDataOrOnly)).toBe(true);

    const testDataAndOnly = {
      "age_limit": 0,
      "fps": 120,
      "like_count": 50,
    };

    expect(new MatchFilterParser(expr).evaluate(testDataAndOnly)).toBe(true);

    const testDataOnlyOr = {
      "age_limit": 1,
      "fps": 60,
      "like_count": 50,
      "view_count": 1000,
    };

    const exprChain = "age_limit=0 & fps=120 || like_count=81 || view_count=1000";
    expect(new MatchFilterParser(exprChain).evaluate(testDataOnlyOr)).toBe(true);
  });

  it("exports filters correctly", () => {
    const simpleParser = new MatchFilterParser("filesize>1000000 & duration<600");
    const simpleExported = simpleParser.export();
    expect(simpleExported).toEqual(["filesize>1000000&duration<600"]);

    const orParser = new MatchFilterParser("filesize>1000000 || uploader='BBC'");
    const orExported = orParser.export();
    expect(normalize(orExported)).toEqual(normalize(["filesize>1000000", "uploader='BBC'"]));

    const complexParser = new MatchFilterParser("(filesize>1000000 & duration<600) || uploader='BBC'");
    const complexExported = complexParser.export();
    expect(normalize(complexExported)).toEqual(normalize(["filesize>1000000&duration<600", "uploader='BBC'"]));

    const testData = { filesize: 2000000, duration: 300 };
    for (const filter of complexExported) {
      const filterParser = new MatchFilterParser(filter);
      if (filterParser.evaluate(testData)) {
        expect(true).toBe(true);
        break;
      }
    }
  });
});
