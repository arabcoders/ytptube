export type DateInput = string | number | Date | null | undefined;

type DateTimeOptions = {
  long?: boolean;
  seconds?: boolean;
  timeZone?: boolean;
};

export const parseDate = (value: DateInput): Date | null => {
  if (null == value || value === '') {
    return null;
  }

  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }

  if (typeof value === 'number') {
    const date = new Date(value * 1000);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  const dateOnly = /^(\d{4})-?(\d{2})-?(\d{2})$/.exec(value);
  if (dateOnly) {
    const year = Number(dateOnly[1]);
    const month = Number(dateOnly[2]) - 1;
    const day = Number(dateOnly[3]);
    const date = new Date(year, month, day);
    return date.getFullYear() === year && date.getMonth() === month && date.getDate() === day
      ? date
      : null;
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
};

export const formatDateTime = (
  value: DateInput,
  locale: string,
  options: DateTimeOptions = {},
): string => {
  const date = parseDate(value);
  if (!date) {
    return '';
  }

  return new Intl.DateTimeFormat(locale, {
    year: 'numeric',
    month: options.long ? 'long' : '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: options.seconds ? '2-digit' : undefined,
    timeZoneName: options.timeZone === false ? undefined : 'longOffset',
  }).format(date);
};

export const formatClock = (value: DateInput, locale: string): string => {
  const date = parseDate(value);
  return date
    ? new Intl.DateTimeFormat(locale, {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      }).format(date)
    : '';
};

export const formatDateOnly = (value: DateInput, locale: string): string => {
  const date = parseDate(value);
  return date
    ? new Intl.DateTimeFormat(locale, {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
      }).format(date)
    : '';
};

export const formatLongDateTime = (value: DateInput, locale: string): string =>
  formatDateTime(value, locale, { long: true, seconds: true, timeZone: false });

export const formatUtc = (value: DateInput): string => {
  const date = parseDate(value);
  return date ? `${date.toISOString().slice(0, 19)}Z` : '';
};

export const toIsoString = (value: DateInput): string => parseDate(value)?.toISOString() ?? '';

export const humanizeDuration = (seconds: number, locale: string): string => {
  const duration = Math.abs(seconds);
  const minutes = Math.round(duration / 60);
  const hours = Math.round(duration / 3600);
  const days = Math.round(duration / 86400);
  const months = Math.round(duration / 2592000);
  const years = Math.round(duration / 31536000);

  let amount: number;
  let unit: Intl.NumberFormatOptions['unit'];
  if (duration < 45) [amount, unit] = [Math.round(duration), 'second'];
  else if (duration < 90) [amount, unit] = [1, 'minute'];
  else if (minutes < 45) [amount, unit] = [minutes, 'minute'];
  else if (minutes < 90) [amount, unit] = [1, 'hour'];
  else if (hours < 22) [amount, unit] = [hours, 'hour'];
  else if (hours < 36) [amount, unit] = [1, 'day'];
  else if (days < 26) [amount, unit] = [days, 'day'];
  else if (days < 46) [amount, unit] = [1, 'month'];
  else if (days < 320) [amount, unit] = [months, 'month'];
  else if (days < 548) [amount, unit] = [1, 'year'];
  else [amount, unit] = [years, 'year'];

  return new Intl.NumberFormat(locale, { style: 'unit', unit, unitDisplay: 'long' }).format(amount);
};
