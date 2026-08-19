import { readdir, readFile } from 'node:fs/promises'
import { join } from 'node:path'

const forbidden = [
  /https?:\/\/127\.0\.0\.1(?::\d+)?/,
  /https?:\/\/localhost:\d+/,
]

async function filesUnder(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const nested = await Promise.all(
    entries.map((entry) => {
      const path = join(directory, entry.name)
      return entry.isDirectory() ? filesUnder(path) : [path]
    }),
  )
  return nested.flat()
}

for (const path of await filesUnder('dist')) {
  if (!/\.(?:html|js|css)$/.test(path)) continue
  const content = await readFile(path, 'utf8')
  const match = forbidden.find((value) => value.test(content))
  if (match) {
    throw new Error(`Production build contains forbidden local URL ${match.source} in ${path}`)
  }
}

console.log('Production bundle URL check passed')
