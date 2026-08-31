import { existsSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = path.resolve(fileURLToPath(new URL('..', import.meta.url)))
const aliases = [
  ['@sau/', 'src/modules/sau/'],
  ['@commander/', 'src/modules/commander/'],
  ['@/', 'src/'],
]

export async function resolve(specifier, context, nextResolve) {
  for (const [prefix, target] of aliases) {
    if (specifier.startsWith(prefix)) {
      return nextResolve(pathToFileURL(resolveProjectPath(target, specifier.slice(prefix.length))).href, context)
    }
  }
  return nextResolve(specifier, context)
}

export async function load(url, context, nextLoad) {
  const result = await nextLoad(url, context)
  if (!url.startsWith('file:') || !/\.(mjs|js)$/.test(new URL(url).pathname)) {
    return result
  }
  const source = String(result.source)
    .replaceAll(
      'import.meta.env',
      '({ DEV: false, PROD: false, BASE_URL: "/", ...process.env })',
    )
  return { ...result, source }
}

function resolveProjectPath(target, specifier) {
  const candidate = path.join(root, target, specifier)
  if (existsSync(candidate) && statSync(candidate).isFile()) {
    return candidate
  }
  if (existsSync(candidate) && statSync(candidate).isDirectory()) {
    const indexFile = path.join(candidate, 'index.js')
    if (existsSync(indexFile)) {
      return indexFile
    }
  }
  if (!path.extname(candidate) && existsSync(`${candidate}.js`)) {
    return `${candidate}.js`
  }
  return candidate
}
