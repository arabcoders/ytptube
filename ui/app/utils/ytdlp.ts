const NUMBER_RE = /\d+(?:\.\d+)?/;

function lookup_unit_table(unitTable: Record<string, number>, s: string, strict = false): number | null {
  const numRe = strict ? NUMBER_RE : /\d+[,.]?\d*/;
  const unitsRe = Object.keys(unitTable)
    .map(u => u.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("|");
  const re = new RegExp(`^(?<num>${numRe.source})\\s*(?<unit>${unitsRe})\\b`, strict ? "" : "i");

  const m = s.match(re);
  if (!m?.groups?.num || !m.groups.unit) {
    return null;
  }

  const numStr = m.groups.num.replace(",", ".");
  const unit = m.groups.unit;
  const mult = unitTable[unit];
  if (undefined === mult) return null;

  return Math.round(parseFloat(numStr) * mult);
}

function parse_filesize(s: string | null): number | null {
  if (!s) return null;
  const UNIT_TABLE: Record<string, number> = {
    B: 1,
    b: 1,
    bytes: 1,
    KiB: 1024, KB: 1000, kB: 1024, kb: 1000, kilobytes: 1000, kibibytes: 1024,
    MiB: 1024 ** 2, MB: 1000 ** 2, megabytes: 1000 ** 2, mebibytes: 1024 ** 2,
    GiB: 1024 ** 3, GB: 1000 ** 3, gigabytes: 1000 ** 3, gibibytes: 1024 ** 3,
    TiB: 1024 ** 4, TB: 1000 ** 4, terabytes: 1000 ** 4, tebibytes: 1024 ** 4,
    PiB: 1024 ** 5, PB: 1000 ** 5, petabytes: 1000 ** 5, pebibytes: 1024 ** 5,
  };
  return lookup_unit_table(UNIT_TABLE, s);
}

function parse_duration(s: string): number | null {
  if (!s?.trim()) return null;

  // Support ISO-ish short forms: "2m", "10s", "1h", "1d"
  const simpleRe = /^(?<num>\d+(?:\.\d+)?)(?<unit>[smhd])$/i;
  const sm = s.match(simpleRe);
  if (sm?.groups?.num && sm.groups.unit) {
    const num = parseFloat(sm.groups.num);
    switch (sm.groups.unit.toLowerCase()) {
      case "s": return num;
      case "m": return num * 60;
      case "h": return num * 3600;
      case "d": return num * 86400;
    }
  }

  // Support hh:mm:ss[.ms]
  const hmsRe = /^(?:(?:(?<days>\d+):)?(?<hours>\d+):)?(?<mins>\d+):(?<secs>\d{1,2})(?<ms>[.:]\d+)?Z?$/;
  const m = s.match(hmsRe);
  if (m?.groups) {
    const { days, hours, mins, secs, ms } = m.groups;
    return (
      (parseFloat(days ?? "0") * 86400) +
      (parseFloat(hours ?? "0") * 3600) +
      (parseFloat(mins ?? "0") * 60) +
      parseFloat(secs ?? "0") +
      parseFloat((ms ?? "0").replace(":", "."))
    );
  }

  return null;
}


// ---------- Match One ----------
function _match_one(filterPart: string, dct: Record<string, any>): boolean {
  const STRING_OPERATORS: Record<string, (a: string, b: string) => boolean> = {
    "*=": (a, b) => a.includes(b),
    "^=": (a, b) => a.startsWith(b),
    "$=": (a, b) => a.endsWith(b),
    "~=": (a, b) => new RegExp(b).test(a),
  };
  const COMPARISON_OPERATORS: Record<string, (a: any, b: any) => boolean> = {
    "*=": STRING_OPERATORS["*="]!,
    "^=": STRING_OPERATORS["^="]!,
    "$=": STRING_OPERATORS["$="]!,
    "~=": STRING_OPERATORS["~="]!,
    "<=": (a, b) => a <= b,
    "<": (a, b) => a < b,
    ">=": (a, b) => a >= b,
    ">": (a, b) => a > b,
    "=": (a, b) => a == b,
  };
  const UNARY_OPERATORS: Record<string, (v: any) => boolean> = {
    "": v => (typeof v === "boolean" ? v === true : v != null),
    "!": v => (typeof v === "boolean" ? v === false : v == null),
  };

  const cmpOps = Object.keys(COMPARISON_OPERATORS)
    .map(op => op.replace(/([.*+?^${}()|\[\]\\])/g, "\\$1"))
    .join("|");

  const operatorRe = new RegExp(
    `^(?<key>[a-z_]+)\\s*(?<negation>!\\s*)?(?<op>${cmpOps})(?<noneInclusive>\\s*\\?)?\\s*(?:(?<quote>["'])(?<quoted>.+?)(?:\\k<quote>)|(?<plain>.+?))?$`
  );

  const m = filterPart.trim().match(operatorRe);
  if (m?.groups) {
    const { key, negation, op, quote, quoted, plain } = m.groups;
    const unnegatedOp = COMPARISON_OPERATORS[op!];
    if (!unnegatedOp) throw new Error(`Invalid operator '${op}'`);

    // Handle incomplete expressions (missing value)
    const value = quoted ?? plain ?? "";
    if (!value && op !== "=" && op !== "!") {
      return false; // Incomplete non-equality expression
    }

    const opFn = negation ? (a: any, b: any) => !unnegatedOp(a, b) : unnegatedOp;
    let processedValue = value;
    if (quote) processedValue = processedValue.replace(new RegExp(`\\\\${quote}`, "g"), quote);

    const actual = dct[key!];
    if (actual === undefined || actual === null) {
      return false;
    }

    let numeric: number | null = null;
    // Try to convert comparison value to numeric first
    numeric = Number(processedValue);
    if (Number.isNaN(numeric)) {
      numeric = parse_filesize(processedValue) ?? parse_filesize(`${processedValue}B`) ?? parse_duration(processedValue);
    }

    // Also try to convert actual value to numeric if we have a numeric comparison
    let finalActual = actual;
    if (numeric !== null && typeof actual === "string") {
      const numericActual = Number(actual);
      if (!Number.isNaN(numericActual)) {
        finalActual = numericActual;
      } else {
        const parsedActual = parse_filesize(actual) ?? parse_duration(actual);
        if (parsedActual !== null) {
          finalActual = parsedActual;
        }
      }
    }

    if (numeric !== null && op! in STRING_OPERATORS) {
      throw new Error(`Operator ${op} only supports string values!`);
    }
    return opFn(finalActual, numeric !== null ? numeric : processedValue);
  }

  // unary operator
  const unaryRe = /^(?<op>!?)\s*(?<key>[a-z_]+)$/;
  const mu = filterPart.trim().match(unaryRe);
  if (mu?.groups) {
    const { op, key } = mu.groups;
    const actual = dct[key!];
    return UNARY_OPERATORS[op!]!(actual);
  }

  throw new Error(`Invalid filter part '${filterPart}'`);
}

// ---------- Parser ----------
type Node = ["ATOM", string] | ["AND", Node, Node] | ["OR", Node, Node];

class MatchFilterParser {
  expr: string;
  tokens: [string, string][];
  pos: number;
  ast: Node;

  constructor(expr: string) {
    this.expr = expr;
    this.tokens = this._tokenize(expr);
    this.pos = 0;
    this.ast = this._parseOr();
  }

  static run(expr: string, dct: Record<string, any> = {}): boolean {
    return new MatchFilterParser(expr).evaluate(dct);
  }

  evaluate(dct: Record<string, any>): boolean {
    return this._eval(this.ast, dct);
  }

  export(): string[] {
    return this._export(this.ast).map(parts => parts.join("&"));
  }

  private _tokenize(expr: string): [string, string][] {
    // First, let's normalize spaces around operators to make parsing easier
    // Replace spaced operators with non-spaced ones
    let normalizedExpr = expr;
    const operators = ["<=", ">=", "<", ">", "\\*=", "\\^=", "\\$=", "~=", "="];
    for (const op of operators) {
      // Replace "key op value" with "keyopvalue" (removing extra spaces)
      const pattern = new RegExp(`([a-z_]+)\\s*(!?)\\s*(${op})\\s*`, "g");
      normalizedExpr = normalizedExpr.replace(pattern, "$1$2$3");
    }

    const tokenSpec: [RegExp, string | null][] = [
      [/\|\|/, "OR"],
      [/&/, "AND"],
      [/\(/, "LPAREN"],
      [/\)/, "RPAREN"],
      [/[^\s&|()]+/, "ATOM"],
      [/\s+/, null],
    ];
    const regex = new RegExp(
      tokenSpec.map(([pat, name], i) => `(?<T${i}>${pat.source})`).join("|"),
      "g"
    );
    const tokens: [string, string][] = [];
    let m: RegExpExecArray | null;
    while ((m = regex.exec(normalizedExpr)) !== null) {
      for (let i = 0; i < tokenSpec.length; i++) {
        if (m.groups?.[`T${i}`]) {
          const tokenSpecEntry = tokenSpec[i];
          if (tokenSpecEntry) {
            const kind = tokenSpecEntry[1];
            if (kind) tokens.push([kind, m[0]]);
          }
          break;
        }
      }
    }
    return tokens;
  }

  private _accept(kind: string): boolean {
    if (this.pos < this.tokens.length && this.tokens[this.pos]?.[0] === kind) {
      this.pos++;
      return true;
    }
    return false;
  }

  private _expect(kind: string): [string, string] {
    if (this.pos < this.tokens.length && this.tokens[this.pos]?.[0] === kind) {
      return this.tokens[this.pos++]!;
    }
    throw new SyntaxError(`Expected ${kind}`);
  }

  private _parseOr(): Node {
    let left = this._parseAnd();
    while (this._accept("OR")) {
      const right = this._parseAnd();
      left = ["OR", left, right];
    }
    return left;
  }

  private _parseAnd(): Node {
    let left = this._parseAtom();
    while (this._accept("AND")) {
      const right = this._parseAtom();
      left = ["AND", left, right];
    }
    return left;
  }

  private _parseAtom(): Node {
    if (this._accept("LPAREN")) {
      const node = this._parseOr();
      this._expect("RPAREN");
      return node;
    }
    const tok = this._expect("ATOM");
    return ["ATOM", tok[1].trim()];
  }

  private _eval(node: Node, dct: Record<string, any>): boolean {
    if (node[0] === "ATOM") {
      return _match_one(node[1], dct);
    }
    if (node[0] === "AND") {
      return this._eval(node[1], dct) && this._eval(node[2], dct);
    }
    if (node[0] === "OR") {
      return this._eval(node[1], dct) || this._eval(node[2], dct);
    }
    throw new Error("Invalid AST node " + node[0]);
  }

  private _export(node: Node): string[][] {
    if (node[0] === "ATOM") return [[node[1]]];
    if (node[0] === "AND") {
      const left = this._export(node[1]);
      const right = this._export(node[2]);
      return left.flatMap(l => right.map(r => [...l, ...r]));
    }
    if (node[0] === "OR") {
      return [...this._export(node[1]), ...this._export(node[2])];
    }
    throw new Error("Invalid AST node " + node[0]);
  }
}

const match_str = (expr: string, dct: Record<string, any>): boolean => MatchFilterParser.run(expr, dct)

export { MatchFilterParser, match_str }
