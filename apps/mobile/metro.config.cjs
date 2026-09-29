const { getDefaultConfig } = require('expo/metro-config');
const path = require('path');

const projectRoot = __dirname;
const workspaceRoot = path.resolve(projectRoot, '../..');

const config = getDefaultConfig(projectRoot);

// Watch all files in the monorepo
config.watchFolders = [workspaceRoot];

// Let Metro know where to resolve packages
config.resolver.nodeModulesPaths = [
  path.resolve(projectRoot, 'node_modules'),
  path.resolve(workspaceRoot, 'node_modules'),
];

// Enable symlinks for workspace packages
config.resolver.disableHierarchicalLookup = false;

// Resolve .js imports to .ts/.tsx files (for TypeScript sources with .js extensions in imports)
const originalResolveRequest = config.resolver.resolveRequest;
config.resolver.resolveRequest = (context, moduleName, platform) => {
  // If import ends with .js, try resolving .ts/.tsx first
  if (moduleName.endsWith('.js')) {
    const tsModuleName = moduleName.slice(0, -3) + '.ts';
    const tsxModuleName = moduleName.slice(0, -3) + '.tsx';
    try {
      return context.resolveRequest(context, tsModuleName, platform);
    } catch {
      try {
        return context.resolveRequest(context, tsxModuleName, platform);
      } catch {
        // Fall through to default resolution
      }
    }
  }
  
  // Default resolution
  if (originalResolveRequest) {
    return originalResolveRequest(context, moduleName, platform);
  }
  return context.resolveRequest(context, moduleName, platform);
};

module.exports = config;
