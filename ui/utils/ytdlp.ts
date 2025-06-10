const NUMBER_RE = /\d+(?:\.\d+)?/;

function match_str(filterStr: string, dct: Record<string, any>, incomplete: boolean | Set<string> = false): boolean {
  return filterStr
    .split(/(?<!\\)&/)
    .every(filterPart => _match_one(filterPart.replace(/\\&/g, '&'), dct, incomplete));
}

function lookup_unit_table(unitTable: Record<string, number>, s: string, strict = false): number | null {
  const numRe = strict ? NUMBER_RE : /\d+[,.]?\d*/;
  const unitsRe = Object.keys(unitTable).map(u => u.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
  const re = new RegExp(`^(?<num>${numRe.source})\s*(?<unit>${unitsRe})\b`, strict ? '' : 'i');

  const m = s.match(re);
  if (!m || !m.groups) return null;

  const num = parseFloat(m.groups.num.replace(',', '.'));
  const mult = unitTable[m.groups.unit];

  return Math.round(num * mult);
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
  if (!s.trim()) return null;

  const durationRe = /^(?:(?:(?<days>\d+):)?(?<hours>\d+):)?(?<mins>\d+):(?<secs>\d{1,2})(?<ms>[.:]\d+)?Z?$/;
  const m = s.match(durationRe);
  if (!m || !m.groups) return null;

  const { days, hours, mins, secs, ms } = m.groups;

  return (
    (parseFloat(days || '0') * 86400) +
    (parseFloat(hours || '0') * 3600) +
    (parseFloat(mins || '0') * 60) +
    parseFloat(secs || '0') +
    parseFloat((ms || '0').replace(':', '.'))
  );
}

function _match_one(filterPart: string, dct: Record<string, any>, incomplete: boolean | Set<string>): boolean {
  const STRING_OPERATORS: Record<string, Function> = {
    '*=': (a: string, v: string) => a.includes(v),
    '^=': (a: string, v: string) => a.startsWith(v),
    '$=': (a: string, v: string) => a.endsWith(v),
    '~=': (a: string, v: string) => new RegExp(v).test(a),
  };

  const COMPARISON_OPERATORS: Record<string, Function> = {
    ...STRING_OPERATORS,
    '<=': (a: any, b: any) => a <= b,
    '<': (a: any, b: any) => a < b,
    '>=': (a: any, b: any) => a >= b,
    '>': (a: any, b: any) => a > b,
    '=': (a: any, b: any) => a == b,
  };

  const match = filterPart.trim().match(/^([a-z_]+)\s*(!)?\s*([*^$~=<>]+)\s*(?:"(.+)"|'(.+)'|(.+))$/);

  if (match) {
    const [, key, negation, op, qstr, sstr, ustr] = match;
    const value = qstr || sstr || ustr;
    const actual = dct[key];

    const compValue = parse_filesize(value) || parse_duration(value) || value;

    const _cmp = COMPARISON_OPERATORS[op];
    if (actual === undefined) return incomplete === true || (incomplete instanceof Set && incomplete.has(key));

    return negation ? !_cmp(actual, compValue) : _cmp(actual, compValue);
  }

  const UNARY_OPERATORS: Record<string, Function> = {
    '': (v: any) => v != null,
    '!': (v: any) => v == null,
  };

  const unaryMatch = filterPart.trim().match(/^(!)?([a-z_]+)$/);

  if (unaryMatch) {
    const [, op, key] = unaryMatch;
    const actual = dct[key];

    if (actual === undefined && (incomplete === true || (incomplete instanceof Set && incomplete.has(key)))) return true;

    return UNARY_OPERATORS[op || ''](actual);
  }

  throw new Error(`Invalid filter part '${filterPart}'`);
}


export { match_str, lookup_unit_table, parse_filesize, parse_duration, _match_one }
