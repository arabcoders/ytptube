import { afterAll, beforeAll, describe, expect, it } from 'bun:test';

const ASS_CONTENT = `[Script Info]
ScriptType: v4.00+
ScaledBorderAndShadow: Yes
PlayResX: 1280
PlayResY: 720

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,40,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,90,0,0,1,3,2,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:01:00.00,Default,,0,0,0,,Outlined`;

const userAgent = Object.getOwnPropertyDescriptor(navigator, 'userAgent');
const platform = Object.getOwnPropertyDescriptor(navigator, 'platform');
const maxTouchPoints = Object.getOwnPropertyDescriptor(navigator, 'maxTouchPoints');
const originalCss = Object.getOwnPropertyDescriptor(window, 'CSS');
const originalCanvasContext = window.HTMLCanvasElement.prototype.getContext;
const originalCancelAnimationFrame = globalThis.cancelAnimationFrame;
const originalRequestAnimationFrame = globalThis.requestAnimationFrame;
const originalResizeObserver = globalThis.ResizeObserver;
const originalTextMetrics = globalThis.TextMetrics;

beforeAll(() => {
  Object.defineProperties(navigator, {
    userAgent: {
      configurable: true,
      value: 'Mozilla/5.0 (iPhone) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1',
    },
    platform: { configurable: true, value: 'iPhone' },
    maxTouchPoints: { configurable: true, value: 5 },
  });
  Object.defineProperty(window, 'CSS', {
    configurable: true,
    value: { registerProperty: undefined },
  });
  globalThis.TextMetrics = class TextMetrics {
    readonly width = 0;
  } as unknown as typeof TextMetrics;
  window.HTMLCanvasElement.prototype.getContext = (() => ({
    measureText: () => ({ fontBoundingBoxAscent: 1, fontBoundingBoxDescent: 1 }),
  })) as typeof window.HTMLCanvasElement.prototype.getContext;
  globalThis.requestAnimationFrame = () => 1;
  globalThis.cancelAnimationFrame = () => {};
  globalThis.ResizeObserver = class ResizeObserver {
    disconnect() {}

    observe() {}

    unobserve() {}
  };
});

afterAll(() => {
  for (const [key, descriptor] of Object.entries({ userAgent, platform, maxTouchPoints })) {
    if (descriptor) {
      Object.defineProperty(navigator, key, descriptor);
    } else {
      Reflect.deleteProperty(navigator, key);
    }
  }
  if (originalCss) {
    Object.defineProperty(window, 'CSS', originalCss);
  } else {
    delete (window as unknown as Record<string, unknown>).CSS;
  }
  window.HTMLCanvasElement.prototype.getContext = originalCanvasContext;
  globalThis.cancelAnimationFrame = originalCancelAnimationFrame;
  globalThis.requestAnimationFrame = originalRequestAnimationFrame;
  globalThis.ResizeObserver = originalResizeObserver;
  globalThis.TextMetrics = originalTextMetrics;
});

describe('ASS.js iOS patch', () => {
  it('uses CSS stroke', async () => {
    const { default: Ass } = await import('assjs');
    const container = document.createElement('div');
    const video = document.createElement('video');
    container.append(video);
    document.body.append(container);

    const ass = new Ass(ASS_CONTENT, video, { container });
    video.dispatchEvent(new window.Event('seeking'));

    const text = container.querySelector<HTMLElement>('[data-text]');
    expect(text?.dataset.stroke).toBe('webkit');
    expect(text?.dataset.hasBorder).toBe('');
    expect(text?.dataset.hasShadow).toBe('');
    expect(text?.querySelector('svg')).toBeNull();
    const css = document.querySelector('#ASS-global-style')?.textContent;
    expect(css).toContain(
      '[data-stroke=webkit][data-has-border]{paint-order:stroke fill;-webkit-text-stroke:',
    );
    expect(css).toContain('[data-stroke=webkit][data-has-shadow]{text-shadow:');
    expect(css).toContain('content:none;display:none');
    expect(css).not.toContain('[data-stroke=webkit][data-has-border]:after');

    ass.destroy();
    container.remove();
  });
});
