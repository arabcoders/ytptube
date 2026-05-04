export function usePlayerShortcutHelp() {
  return useState<boolean>('player-shortcut-help', () => false);
}
