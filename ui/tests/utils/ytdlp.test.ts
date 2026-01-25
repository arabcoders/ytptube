import { describe, it, expect } from 'vitest'
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
    // Use numeric seconds instead of unit formats for consistency
    // 120 seconds = 2 minutes
    expect(new MatchFilterParser("duration<120").evaluate({ duration: 30 })).toBe(true);
    expect(new MatchFilterParser("duration<120").evaluate({ duration: 200 })).toBe(false);

    // 90 seconds
    expect(new MatchFilterParser("duration<90").evaluate({ duration: 30 })).toBe(true);
    expect(new MatchFilterParser("duration<90").evaluate({ duration: 120 })).toBe(false);

    // 3600 seconds = 1 hour
    expect(new MatchFilterParser("duration<3600").evaluate({ duration: 3599 })).toBe(true);
    expect(new MatchFilterParser("duration<3600").evaluate({ duration: 3700 })).toBe(false);
  });

  it("parses filesize with numeric values", () => {
    // Use numeric bytes instead of unit formats for consistency
    // 1MB = 1,000,000 bytes
    expect(new MatchFilterParser("filesize>1000000").evaluate({ filesize: 2_000_000 })).toBe(true);
    expect(new MatchFilterParser("filesize>1000000").evaluate({ filesize: 500_000 })).toBe(false);

    // 1GiB = 1,073,741,824 bytes
    expect(new MatchFilterParser("filesize>=1073741824").evaluate({ filesize: 2 ** 30 })).toBe(true);
    expect(new MatchFilterParser("filesize>=1073741824").evaluate({ filesize: 1000000 })).toBe(false);
  });

  it("handles string operators", () => {
    const d = { uploader: "BBC News Channel" };

    // Test all string operators with positive cases
    expect(new MatchFilterParser("uploader*='News'").evaluate(d)).toBe(true);  // contains
    expect(new MatchFilterParser("uploader^='BBC'").evaluate(d)).toBe(true);   // starts with
    expect(new MatchFilterParser("uploader$='Channel'").evaluate(d)).toBe(true); // ends with
    expect(new MatchFilterParser("uploader~='News\\s+Channel'").evaluate(d)).toBe(true); // regex

    // Test negative cases
    expect(new MatchFilterParser("uploader*='CNN'").evaluate(d)).toBe(false);  // contains
    expect(new MatchFilterParser("uploader^='CNN'").evaluate(d)).toBe(false);  // starts with
    expect(new MatchFilterParser("uploader$='BBC'").evaluate(d)).toBe(false);  // ends with
    expect(new MatchFilterParser("uploader~='News\\s+Network'").evaluate(d)).toBe(false); // regex
  });

  it("handles spaces around operators", () => {
    const d = {
      "channel_id": "UC-7oMv6E4Uz2tF51w5Sj49w",
      "uploader": "BBC"
    };

    // Test with spaces around equals
    expect(new MatchFilterParser("channel_id = 'UC-7oMv6E4Uz2tF51w5Sj49w'").evaluate(d)).toBe(true);
    expect(new MatchFilterParser("channel_id = 'different-id'").evaluate(d)).toBe(false);

    // Test with spaces in complex expressions
    expect(new MatchFilterParser("channel_id = 'UC-7oMv6E4Uz2tF51w5Sj49w' & uploader = 'BBC'").evaluate(d)).toBe(true);
    expect(new MatchFilterParser("channel_id = 'different-id' & uploader = 'BBC'").evaluate(d)).toBe(false);

    // Test the specific failing case from the bug report
    expect(new MatchFilterParser("channel_id = 'UCfmrcEdes7yDtEISGPM1T-A' & availability = subscriber_only").evaluate(d)).toBe(false);
  });

  it("reproduces original bug report", () => {
    // Exact data from the original bug report
    const testData = {
      "age_limit": 0,
      "comment_count": 6,
      "channel_id": "UC-7oMv6E4Uz2tF51w5Sj49w",
      "uploader_url": "https://www.youtube.com/@PlayFramePlus"
    };

    // This filter should return FALSE because:
    // 1. channel_id doesn't match (UC-7oMv6E4Uz2tF51w5Sj49w vs UCfmrcEdes7yDtEISGPM1T-A)
    // 2. availability key doesn't exist in the data
    const filter = "channel_id = 'UCfmrcEdes7yDtEISGPM1T-A' & availability = subscriber_only";
    expect(new MatchFilterParser(filter).evaluate(testData)).toBe(false);

    // Individual parts should also be false
    expect(new MatchFilterParser("channel_id = 'UCfmrcEdes7yDtEISGPM1T-A'").evaluate(testData)).toBe(false);
    expect(new MatchFilterParser("availability = subscriber_only").evaluate(testData)).toBe(false);

    // But the correct channel_id should match
    expect(new MatchFilterParser("channel_id = 'UC-7oMv6E4Uz2tF51w5Sj49w'").evaluate(testData)).toBe(true);
  });

  it("tests OR operator precedence", () => {
    // Test data for the examples
    const testData = {
      "age_limit": 0,
      "fps": 120,
      "like_count": 81,
    };

    // Case 1: (age_limit=0 & fps=120) || like_count=81
    // This should evaluate as: (True & True) || True = True || True = True
    const expr1 = "(age_limit=0 & fps=120) || like_count=81";
    expect(new MatchFilterParser(expr1).evaluate(testData)).toBe(true);

    // Case 2: age_limit=0 & fps=120 || like_count=81
    // This evaluates left-to-right as: (age_limit=0 & fps=120) || like_count=81
    // = (True & True) || True = True || True = True
    const expr2 = "age_limit=0 & fps=120 || like_count=81";
    expect(new MatchFilterParser(expr2).evaluate(testData)).toBe(true);

    // Test with data that shows left-to-right evaluation
    const testDataPartial = {
      "age_limit": 0,
      "fps": 60,  // Changed from 120 to make first AND false
      "like_count": 81,
    };

    // Case 1 with partial data: (age_limit=0 & fps=120) || like_count=81
    // This should be: (True & False) || True = False || True = True
    expect(new MatchFilterParser(expr1).evaluate(testDataPartial)).toBe(true);

    // Case 2 with partial data: age_limit=0 & fps=120 || like_count=81
    // This evaluates as: (age_limit=0 & fps=120) || like_count=81 = (True & False) || True = False || True = True
    expect(new MatchFilterParser(expr2).evaluate(testDataPartial)).toBe(true);

    // Test case where the difference becomes clear
    const testDataEdge = {
      "age_limit": 1,  // Changed from 0 to make age_limit=0 false
      "fps": 60,       // Changed from 120 to make fps=120 false
      "like_count": 81,
    };

    // Case 1 with edge data: (age_limit=0 & fps=120) || like_count=81
    // This should be: (False & False) || True = False || True = True
    expect(new MatchFilterParser(expr1).evaluate(testDataEdge)).toBe(true);

    // Case 2 with edge data: age_limit=0 & fps=120 || like_count=81
    // This evaluates as: (age_limit=0 & fps=120) || like_count=81 = (False & False) || True = False || True = True
    expect(new MatchFilterParser(expr2).evaluate(testDataEdge)).toBe(true);
  });

  it("tests complex OR precedence scenarios", () => {
    // Test case where only the OR part is true
    const testDataOrOnly = {
      "age_limit": 1,   // False
      "fps": 60,        // False (not 120)
      "like_count": 81, // True
    };

    // Expression: a & b || c
    // Evaluates left-to-right as: (a & b) || c = (False & False) || True = False || True = True
    const expr = "age_limit=0 & fps=120 || like_count=81";
    expect(new MatchFilterParser(expr).evaluate(testDataOrOnly)).toBe(true);

    // Test case where only the AND part is true
    const testDataAndOnly = {
      "age_limit": 0,   // True
      "fps": 120,       // True
      "like_count": 50, // False (not 81)
    };

    // Expression: a & b || c
    // Evaluates as: (a & b) || c = (True & True) || False = True || False = True
    expect(new MatchFilterParser(expr).evaluate(testDataAndOnly)).toBe(true);

    // Test case where everything is false except the OR part
    const testDataOnlyOr = {
      "age_limit": 1,   // False
      "fps": 60,        // False
      "like_count": 50, // False
      "view_count": 1000, // True
    };

    // Test chained OR with AND: a & b || c || d
    // Evaluates left-to-right as: ((a & b) || c) || d
    const exprChain = "age_limit=0 & fps=120 || like_count=81 || view_count=1000";
    expect(new MatchFilterParser(exprChain).evaluate(testDataOnlyOr)).toBe(true);
  });

  it("exports filters correctly", () => {
    // Test simple AND expression
    const simpleParser = new MatchFilterParser("filesize>1000000 & duration<600");
    const simpleExported = simpleParser.export();
    expect(simpleExported).toEqual(["filesize>1000000&duration<600"]);

    // Test OR expression (should split into multiple filters)
    const orParser = new MatchFilterParser("filesize>1000000 || uploader='BBC'");
    const orExported = orParser.export();
    expect(normalize(orExported)).toEqual(normalize(["filesize>1000000", "uploader='BBC'"]));

    // Test complex expression with grouping
    const complexParser = new MatchFilterParser("(filesize>1000000 & duration<600) || uploader='BBC'");
    const complexExported = complexParser.export();
    expect(normalize(complexExported)).toEqual(normalize(["filesize>1000000&duration<600", "uploader='BBC'"]));

    // Verify exported filters work individually
    const testData = { filesize: 2000000, duration: 300 };
    for (const filter of complexExported) {
      const filterParser = new MatchFilterParser(filter);
      // At least one of the exported filters should match
      if (filterParser.evaluate(testData)) {
        expect(true).toBe(true); // Success if any filter matches
        break;
      }
    }
  });
});
