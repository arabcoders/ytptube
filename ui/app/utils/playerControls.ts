type TapState = {
  touch: boolean;
  paused: boolean;
  visible: boolean;
};

const nextTapVisible = ({ touch, paused, visible }: TapState): boolean => {
  if (paused) {
    return visible;
  }

  if (visible) {
    return false;
  }

  return touch;
};

export { nextTapVisible };
export type { TapState };
