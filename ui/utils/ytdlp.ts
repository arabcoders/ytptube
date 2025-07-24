const NUMBER_RE = /\d+(?:\.\d+)?/;

function match_str(filterStr: string, dct: Record<string, any>, incomplete: boolean | Set<string> = false): boolean {
  if (!filterStr) {
    return true;
  }

  return filterStr
    .split(/(?<!\\)&/)
    .every(filterPart => _match_one(filterPart.replace(/\\&/g, '&'), dct, incomplete));
}

function lookup_unit_table(unitTable: Record<string, number>, s: string, strict = false): number | null {
  const numRe = strict ? NUMBER_RE : /\d+[,.]?\d*/;
  const unitsRe = Object.keys(unitTable).map(u => u.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
  const re = new RegExp(`^(?<num>${numRe.source})\\s*(?<unit>${unitsRe})\\b`, strict ? '' : 'i');

  const m = s.match(re);
  if (!m?.groups?.num || !m.groups.unit) {
    return null;

  }

  const numStr = m.groups.num.replace(',', '.');
  const unit = m.groups.unit;
  const mult = unitTable[unit];
  if (undefined === mult) {
    return null;
  }

  return Math.round(parseFloat(numStr) * mult);
}

function parse_filesize(s: string | null): number | null {
  if (!s) return null;

  const UNIT_TABLE: Record<string, number> = {
    B: 1, bytes: 1, b: 1,
    KiB: 1024, KB: 1000, kB: 1024, kb: 1000, kilobytes: 1000, kibibytes: 1024,
    MiB: 1024 ** 2, MB: 1000 ** 2, megabytes: 1000 ** 2, mebibytes: 1024 ** 2,
    GiB: 1024 ** 3, GB: 1000 ** 3, gigabytes: 1000 ** 3, gibibytes: 1024 ** 3,
    TiB: 1024 ** 4, TB: 1000 ** 4, terabytes: 1000 ** 4, tebibytes: 1024 ** 4,
  };

  return lookup_unit_table(UNIT_TABLE, s);
}

function parse_duration(s: string): number | null {
  if (!s.trim()) {
    return null;
  }

  const durationRe = /^(?:(?:(?<days>\d+):)?(?<hours>\d+):)?(?<mins>\d+):(?<secs>\d{1,2})(?<ms>[.:]\d+)?Z?$/;
  const m = s.match(durationRe);
  if (!m?.groups) {
    return null;
  }

  const { days, hours, mins, secs, ms } = m.groups;

  return (
    (parseFloat(days ?? '0') * 86400) +
    (parseFloat(hours ?? '0') * 3600) +
    (parseFloat(mins ?? '0') * 60) + parseFloat(secs ?? '0') + parseFloat((ms ?? '0').replace(':', '.'))
  );
}

function _match_one(filterPart: string, dct: Record<string, any>, incomplete: boolean | Set<string>): boolean {
  const STRING_OPERATORS: Record<string, (a: string, b: string) => boolean> = {
    '*=': (a, b) => a.includes(b),
    '^=': (a, b) => a.startsWith(b),
    '$=': (a, b) => a.endsWith(b),
    '~=': (a, b) => new RegExp(b).test(a),
  };

  const COMPARISON_OPERATORS: Record<string, (a: any, b: any) => boolean> = {
    '*=': STRING_OPERATORS['*=']!,
    '^=': STRING_OPERATORS['^=']!,
    '$=': STRING_OPERATORS['$=']!,
    '~=': STRING_OPERATORS['~=']!,
    '<=': (a, b) => a <= b,
    '<': (a, b) => a < b,
    '>=': (a, b) => a >= b,
    '>': (a, b) => a > b,
    '=': (a, b) => a == b,
  };

  const isIncomplete = typeof incomplete === 'boolean' ? (_: string) => incomplete : (k: string) => incomplete.has(k);

  const cmpOps = Object.keys(COMPARISON_OPERATORS).map(op => op.replace(/([.*+?^${}()|\[\]\\])/g, '\\$1')).join('|');
  const operatorRe = new RegExp(`^(?<key>[a-z_]+)\\s*(?<negation>!\\s*)?(?<op>${cmpOps})(?<noneInclusive>\\s*\\?)?\\s*(?:(?<quote>["'])(?<quoted>.+?)(?:\\k<quote>)|(?<plain>.+))$`);

  const m = filterPart.trim().match(operatorRe);
  if (m?.groups) {
    const { key, negation, op, noneInclusive, quote, quoted, plain } = m.groups;
    const unnegatedOp = COMPARISON_OPERATORS[op!];
    if (!unnegatedOp) {
      throw new Error(`Invalid operator '${op}'`);
    }

    const opFn = negation ? (a: any, b: any) => !unnegatedOp(a, b) : unnegatedOp;

    let value = quoted ?? plain ?? '';
    if (quote) value = value.replace(new RegExp(`\\\\${quote}`, 'g'), quote);

    const actual = dct[key!];
    let numeric: number | null = null;

    if (typeof actual === 'number') {
      numeric = Number(value);
      if (Number.isNaN(numeric)) {
        numeric = parse_filesize(value) ?? parse_filesize(`${value}B`) ?? parse_duration(value);
      }
    }

    if (numeric !== null && op! in STRING_OPERATORS) {
      throw new Error(`Operator ${op} only supports string values!`);
    }

    if (actual == null) {
      return isIncomplete(key!) || Boolean(noneInclusive);
    }

    return opFn(actual, numeric !== null ? numeric : value);
  }

  const UNARY_OPERATORS: Record<string, (v: any) => boolean> = {
    '': v => typeof v === 'boolean' ? v === true : v != null,
    '!': v => typeof v === 'boolean' ? v === false : v == null,
  };

  const unaryRe = new RegExp(`^(?<op>!?)\\s*(?<key>[a-z_]+)$`);
  const mu = filterPart.trim().match(unaryRe);
  if (mu?.groups) {
    const { op, key } = mu.groups;
    const actual = dct[key!];

    if (actual === undefined && isIncomplete(key!)) {
      return true;
    }

    const unaryOp = UNARY_OPERATORS[op!];

    if (!unaryOp) {
      throw new Error(`Invalid unary operator '${op}'`);
    }

    return unaryOp(actual);
  }

  throw new Error(`Invalid filter part '${filterPart}'`);
}

export { match_str, lookup_unit_table, parse_filesize, parse_duration, _match_one }
