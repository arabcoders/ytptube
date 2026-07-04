<template>
  <div class="space-y-1">
    <p class="text-[11px] font-semibold uppercase tracking-[0.18em] text-toned">
      <UIcon v-if="icon" :name="icon" class="mr-1 inline-block size-3" />
      {{ label }}
    </p>
    <div class="relative" @mousemove="onMouseMove" @mouseleave="onMouseLeave">
      <svg
        :viewBox="`0 0 ${width} ${height}`"
        class="w-full select-none"
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <linearGradient :id="`area-${uid}`" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" :stop-color="primaryColor" stop-opacity="0.25" />
            <stop offset="100%" :stop-color="primaryColor" stop-opacity="0.02" />
          </linearGradient>
        </defs>

        <line
          v-for="t in yTicks"
          :key="'g' + t.value"
          :x1="axisLeft"
          :x2="plotRight"
          :y1="t.y"
          :y2="t.y"
          stroke="oklch(0.55 0.02 280 / 0.12)"
          stroke-width="0.5"
        />

        <line
          :x1="axisLeft"
          :x2="axisLeft"
          :y1="plotTop"
          :y2="plotBottom"
          stroke="oklch(0.55 0.02 280 / 0.3)"
          stroke-width="1"
        />
        <line
          :x1="axisLeft"
          :x2="plotRight"
          :y1="plotBottom"
          :y2="plotBottom"
          stroke="oklch(0.55 0.02 280 / 0.3)"
          stroke-width="1"
        />

        <g v-for="t in yTicks" :key="'t' + t.value">
          <line
            :x1="axisLeft"
            :x2="axisLeft - 2"
            :y1="t.y"
            :y2="t.y"
            stroke="oklch(0.55 0.02 280 / 0.4)"
            stroke-width="1"
          />
          <text
            :x="axisLeft - 3"
            :y="t.y + 3"
            text-anchor="end"
            font-size="5"
            fill="oklch(0.55 0.02 280 / 0.7)"
          >
            {{ t.label }}
          </text>
        </g>

        <path v-if="areaPath" :d="areaPath" :fill="`url(#area-${uid})`" />

        <polyline
          v-if="linePoints"
          :points="linePoints"
          fill="none"
          :stroke="primaryColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        />

        <polyline
          v-if="linePoints"
          :points="linePoints"
          fill="none"
          stroke="transparent"
          stroke-width="18"
          pointer-events="stroke"
        />

        <template v-if="hoverIdx != null">
          <line
            :x1="xPos(hoverIdx)"
            :x2="xPos(hoverIdx)"
            :y1="plotTop"
            :y2="plotBottom"
            stroke="oklch(0.55 0.02 280 / 0.4)"
            stroke-width="0.5"
            stroke-dasharray="3 2"
          />
          <circle
            :cx="xPos(hoverIdx)"
            :cy="yPos(valToFraction(values[hoverIdx]!))"
            r="3"
            :fill="primaryColor"
            stroke="var(--color-bg-elevated, #fff)"
            stroke-width="1.5"
          />
          <text
            :x="hoverLabelX"
            :y="hoverLabelY"
            text-anchor="middle"
            font-size="5"
            :fill="primaryColor"
          >
            {{ fmt(values[hoverIdx]!) }}
          </text>
        </template>
      </svg>

      <div
        v-if="hasData && timestamps.length >= 2"
        class="flex justify-between"
        :style="{ paddingLeft: axisLeft + 'px', paddingRight: marginRight + 'px' }"
      >
        <span class="text-[8px] text-toned/60">{{ timeLabel(0) }}</span>
        <span class="text-[8px] text-toned/60">{{ timeLabel(timestamps.length - 1) }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
let _uid = 0;

const props = withDefaults(
  defineProps<{
    values: number[];
    timestamps?: number[];
    label: string;
    icon?: string;
    width?: number;
    height?: number;
    color?: string;
    formatValue?: (v: number) => string;
  }>(),
  {
    width: 360,
    height: 80,
    timestamps: () => [],
    color: 'info',
    icon: '',
    formatValue: (v: number) => String(Math.round(v)),
  },
);

const uid = computed(() => `chart-${++_uid}`);

const marginLeft = 28;
const marginRight = 4;
const marginTop = 4;
const marginBottom = 8;

const hasData = computed(() => props.values.length >= 2);

const primaryColor = computed(() => {
  switch (props.color) {
    case 'success':
      return 'oklch(0.56 0.22 145 / 0.8)';
    case 'error':
      return 'oklch(0.56 0.22 20 / 0.8)';
    case 'warning':
      return 'oklch(0.7 0.15 70 / 0.8)';
    case 'info':
      return 'oklch(0.6 0.15 260 / 0.8)';
    default:
      return 'oklch(0.55 0.02 280 / 0.6)';
  }
});

const maxVal = computed(() => Math.max(...props.values, 1e-9));
const minVal = computed(() => Math.min(...props.values));
const valRange = computed(() => maxVal.value - minVal.value || 1);

const axisLeft = marginLeft;
const plotRight = props.width - marginRight;
const plotTop = marginTop;
const plotBottom = props.height - marginBottom;
const plotW = plotRight - axisLeft;
const plotH = plotBottom - plotTop;

interface YTick {
  value: number;
  y: number;
  label: string;
}

const yTicks = computed<YTick[]>(() => {
  if (!hasData.value) return [];
  const ticks: YTick[] = [];
  for (const f of [0, 0.25, 0.5, 0.75, 1]) {
    const v = minVal.value + f * valRange.value;
    ticks.push({ value: v, y: plotBottom - f * plotH, label: props.formatValue!(v) });
  }
  return ticks;
});

const valToFraction = (v: number): number => (v - minVal.value) / valRange.value;
const yPos = (fraction: number): number => plotBottom - fraction * plotH;
const xPos = (i: number): number => {
  const step = plotW / Math.max(props.values.length - 1, 1);
  return axisLeft + i * step;
};

const linePoints = computed(() => {
  if (!hasData.value) return '';
  return props.values
    .map((v, i) => `${xPos(i).toFixed(1)},${yPos(valToFraction(v)).toFixed(1)}`)
    .join(' ');
});

const areaPath = computed(() => {
  if (!hasData.value) return '';
  const top = props.values
    .map((v, i) => `${xPos(i).toFixed(1)},${yPos(valToFraction(v)).toFixed(1)}`)
    .join(' L ');
  return `M ${top} L ${plotRight.toFixed(1)},${plotBottom.toFixed(1)} L ${axisLeft.toFixed(1)},${plotBottom.toFixed(1)} Z`;
});

const timeLabel = (i: number): string => {
  const ts = props.timestamps[i];
  if (ts == null) return '';
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

const fmt = (v: number): string => props.formatValue!(v);

// Hover
const hoverIdx = ref<number | null>(null);

const hoverLabelX = computed(() => {
  if (hoverIdx.value == null) return 0;
  const x = xPos(hoverIdx.value);
  const lastIdx = props.values.length - 1;
  if (hoverIdx.value === 0) return Math.max(x + 12, axisLeft + 12);
  if (hoverIdx.value === lastIdx) return Math.min(x - 12, plotRight - 12);
  return x;
});

const hoverLabelY = computed(() => {
  if (hoverIdx.value == null) return 0;
  const y = yPos(valToFraction(props.values[hoverIdx.value]!));
  const frac = valToFraction(props.values[hoverIdx.value]!);
  return frac > 0.5 ? y + 12 : y - 5;
});

const onMouseMove = (e: MouseEvent) => {
  const svg = (e.currentTarget as HTMLElement).querySelector('svg');
  if (!svg) {
    hoverIdx.value = null;
    return;
  }
  const rect = svg.getBoundingClientRect();
  const scaleX = props.width / rect.width;
  const svgX = (e.clientX - rect.left) * scaleX;

  if (svgX < axisLeft || svgX > plotRight) {
    hoverIdx.value = null;
    return;
  }

  const step = plotW / Math.max(props.values.length - 1, 1);
  const idx = Math.round((svgX - axisLeft) / step);
  hoverIdx.value = Math.max(0, Math.min(idx, props.values.length - 1));
};

const onMouseLeave = () => {
  hoverIdx.value = null;
};
</script>
