const floatingSurface =
  'ytp-floating-surface rounded-lg bg-(--ytp-floating-bg) shadow-(--ytp-floating-shadow) ring-0';

export default defineAppConfig({
  ui: {
    primary: 'indigo',
    colors: {
      primary: 'indigo',
      secondary: 'amber',
      success: 'emerald',
      neutral: 'stone',
    },
    formField: {
      slots: {
        label: 'block font-semibold text-default',
        container: 'space-y-2',
        description: 'text-sm text-toned',
        hint: 'text-sm text-toned',
        help: 'text-sm text-toned',
        error: 'text-sm text-error',
      },
    },
    empty: {
      variants: {
        variant: {
          outline: {
            root: 'border border-dashed border-default bg-muted/10 ring-0',
          },
        },
      },
      defaultVariants: {
        variant: 'outline',
      },
    },
    input: {
      variants: {
        variant: {
          outline: 'bg-elevated/40 hover:bg-elevated/55 disabled:bg-elevated/20',
        },
      },
    },
    textarea: {
      variants: {
        variant: {
          outline: 'bg-elevated/40 hover:bg-elevated/55 disabled:bg-elevated/20',
        },
      },
    },
    tooltip: {
      slots: {
        content: 'pointer-events-auto',
      },
    },
    toast: {
      slots: {
        root: 'shell-surface bg-transparent',
      },
    },
    modal: {
      slots: {
        content: 'shell-surface bg-transparent',
      },
    },
    slideover: {
      slots: {
        content: 'shell-surface bg-transparent',
      },
    },
    card: {
      slots: {
        root: 'min-w-0 max-w-full rounded-lg overflow-hidden',
      },
      variants: {
        variant: {
          outline: {
            root: 'border border-(--ytp-surface-border-soft) bg-elevated/20 divide-y divide-default ring-0',
          },
          soft: {
            root: 'bg-elevated/20 divide-y divide-default',
          },
          subtle: {
            root: 'border border-(--ytp-surface-border-soft) bg-elevated/20 divide-y divide-default ring-0',
          },
        },
      },
    },
    dropdownMenu: {
      slots: {
        content: floatingSurface,
      },
    },
    popover: {
      slots: {
        content: floatingSurface,
      },
    },
    select: {
      slots: {
        content: floatingSurface,
      },
      variants: {
        variant: {
          outline: 'bg-elevated/40 hover:bg-elevated/55 disabled:bg-elevated/20',
        },
      },
    },
    selectMenu: {
      slots: {
        content: floatingSurface,
      },
      variants: {
        variant: {
          outline: 'bg-elevated/40 hover:bg-elevated/55 disabled:bg-elevated/20',
        },
      },
    },
    button: {
      compoundVariants: [
        {
          color: 'neutral',
          variant: 'outline',
          class:
            'bg-transparent hover:bg-elevated/30 active:bg-elevated/40 disabled:bg-transparent aria-disabled:bg-transparent',
        },
        {
          color: 'neutral',
          variant: 'soft',
          class:
            'bg-elevated/30 hover:bg-elevated/45 active:bg-elevated/55 disabled:bg-elevated/20 aria-disabled:bg-elevated/20',
        },
        {
          color: 'neutral',
          variant: 'ghost',
          class: 'hover:bg-elevated/30 active:bg-elevated/40 focus-visible:bg-elevated/30',
        },
      ],
      defaultVariants: {
        size: 'sm',
      },
    },
  },
});
