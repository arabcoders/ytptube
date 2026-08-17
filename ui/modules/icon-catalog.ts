import { readFile, writeFile } from 'node:fs/promises';
import { extname, isAbsolute, relative, resolve, sep } from 'node:path';
import { addVitePlugin, defineNuxtModule, updateTemplates, useLogger } from '@nuxt/kit';
import { IconUsageScanner } from '@nuxt/icon/utils';

export const CATALOG_FILE = 'app/utils/generatedIconCatalog.ts';
const ICON_TEMPLATE = /^nuxt-icon-client-bundle(?:$|[._-])/;
const SOURCE_EXTENSIONS = new Set(['.js', '.ts', '.vue']);

export const isRelevantSource = (path: string, rootDir: string): boolean => {
  const absolutePath = resolve(rootDir, path);
  const appDirectory = resolve(rootDir, 'app');
  const relativePath = relative(appDirectory, absolutePath);
  const catalogPath = resolve(rootDir, CATALOG_FILE);

  return (
    '' !== relativePath &&
    !isAbsolute(relativePath) &&
    relativePath !== '..' &&
    !relativePath.startsWith(`..${sep}`) &&
    SOURCE_EXTENSIONS.has(extname(absolutePath)) &&
    absolutePath !== catalogPath
  );
};

export const renderCatalog = (icons: Iterable<string>): string => {
  const names = [...icons]
    .map((icon) => icon.replace(/^i[-:]/, ''))
    .filter((icon) => icon.startsWith('lucide:'))
    .map((icon) => icon.slice('lucide:'.length))
    .sort();
  const iconifyNames = names.map((name) => `lucide:${name}`);
  const uiNames = names.map((name) => `i-lucide-${name}`);

  return `// Generated from Nuxt Icon's client bundle. Do not edit manually.\n\nexport const bundledIconNames = ${JSON.stringify(iconifyNames, null, 2)} as const;\n\nexport const bundledUiIconNames = ${JSON.stringify(uiNames, null, 2)} as const;\n\nconst bundledUiIconSet = new Set<string>(bundledUiIconNames);\n\nexport const isBundledUiIcon = (name?: string | null): name is (typeof bundledUiIconNames)[number] =>\n  typeof name === 'string' && bundledUiIconSet.has(name);\n`;
};

export const writeCatalogIfChanged = async (path: string, content: string): Promise<boolean> => {
  let previous: string | undefined;
  try {
    previous = await readFile(path, 'utf8');
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT') {
      throw error;
    }
  }

  if (previous === content) {
    return false;
  }

  await writeFile(path, content);
  return true;
};

export default defineNuxtModule({
  meta: { name: 'ytptube-icon-catalog' },
  setup(_options, nuxt) {
    const catalogPath = resolve(nuxt.options.rootDir, CATALOG_FILE);
    const iconOptions = nuxt.options.icon;
    const scanOptions = iconOptions && iconOptions.clientBundle?.scan;
    const scanner = nuxt.options.dev && scanOptions ? new IconUsageScanner(scanOptions) : undefined;
    const incrementalIcons = new Set<string>();
    let catalogChanged = false;

    nuxt.hook('icon:clientBundleIcons', async (icons) => {
      for (const icon of incrementalIcons) {
        icons.add(icon);
      }
      catalogChanged = await writeCatalogIfChanged(catalogPath, renderCatalog(icons));
    });

    if (!nuxt.options.dev) {
      return;
    }

    const logger = useLogger('ytptube-icon-catalog');
    const appDirectory = resolve(nuxt.options.rootDir, 'app');

    addVitePlugin({
      name: 'ytptube-icon-catalog-hmr',
      configureServer(server) {
        let updateTimer: ReturnType<typeof setTimeout> | undefined;
        let updating = false;
        let pendingUpdate = false;
        const pendingSourcePaths = new Set<string>();

        const regenerate = async (): Promise<void> => {
          if (updating) {
            pendingUpdate = true;
            return;
          }

          updating = true;
          try {
            do {
              pendingUpdate = false;
              catalogChanged = false;
              const destinations = new Set<string>();
              try {
                if (scanner) {
                  const sourcePaths = [...pendingSourcePaths];
                  pendingSourcePaths.clear();
                  await Promise.all(
                    sourcePaths.map(async (path) => {
                      const code = await readFile(path, 'utf8').catch(
                        (error: NodeJS.ErrnoException) => {
                          if ('ENOENT' === error.code) {
                            return '';
                          }
                          throw error;
                        },
                      );
                      scanner.extractFromCode(code, incrementalIcons);
                    }),
                  );
                }

                await updateTemplates({
                  filter: (template) => {
                    if (!ICON_TEMPLATE.test(template.filename)) {
                      return false;
                    }
                    destinations.add(template.dst);
                    return true;
                  },
                });

                const modules = [...destinations].flatMap((destination) => [
                  ...(server.environments.client.moduleGraph.getModulesByFile(destination) ?? []),
                ]);
                await Promise.all(
                  modules.map((module) => {
                    server.environments.client.moduleGraph.invalidateModule(module);
                    return server.environments.client.reloadModule(module);
                  }),
                );

                if (catalogChanged) {
                  const catalogModules =
                    server.environments.client.moduleGraph.getModulesByFile(catalogPath);
                  await Promise.all(
                    [...(catalogModules ?? [])].map((module) => {
                      server.environments.client.moduleGraph.invalidateModule(module);
                      return server.environments.client.reloadModule(module);
                    }),
                  );
                }
              } catch (error) {
                logger.error(error);
              }
            } while (pendingUpdate);
          } finally {
            updating = false;
          }
        };

        const scheduleUpdate = (path: string): void => {
          if (!isRelevantSource(path, nuxt.options.rootDir)) {
            return;
          }

          pendingSourcePaths.add(resolve(nuxt.options.rootDir, path));

          if (updateTimer) {
            clearTimeout(updateTimer);
          }
          updateTimer = setTimeout(() => void regenerate(), 50);
        };

        server.watcher.add(appDirectory);
        server.watcher.on('add', scheduleUpdate);
        server.watcher.on('change', scheduleUpdate);
        server.watcher.on('unlink', scheduleUpdate);
        server.httpServer?.once('close', () => {
          if (updateTimer) {
            clearTimeout(updateTimer);
          }
          server.watcher.off('add', scheduleUpdate);
          server.watcher.off('change', scheduleUpdate);
          server.watcher.off('unlink', scheduleUpdate);
        });
      },
    });
  },
});
