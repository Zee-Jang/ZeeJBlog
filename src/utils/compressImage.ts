/** Compress images in-browser before upload (target ~200–300KB). */

export async function compressImageFile(
  file: File,
  opts: { maxEdge?: number; maxBytes?: number; mime?: string } = {},
): Promise<Blob> {
  const maxEdge = opts.maxEdge ?? 512
  const maxBytes = opts.maxBytes ?? 280 * 1024
  const mime = opts.mime ?? 'image/jpeg'

  if (!file.type.startsWith('image/')) {
    throw new Error('NOT_IMAGE')
  }

  const bitmap = await createImageBitmap(file)
  const scale = Math.min(1, maxEdge / Math.max(bitmap.width, bitmap.height))
  const w = Math.max(1, Math.round(bitmap.width * scale))
  const h = Math.max(1, Math.round(bitmap.height * scale))

  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    bitmap.close()
    throw new Error('NO_CANVAS')
  }
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, w, h)
  ctx.drawImage(bitmap, 0, 0, w, h)
  bitmap.close()

  let quality = 0.82
  let blob = await canvasToBlob(canvas, mime, quality)
  while (blob.size > maxBytes && quality > 0.45) {
    quality -= 0.08
    blob = await canvasToBlob(canvas, mime, quality)
  }

  // Still too large: shrink dimensions further
  if (blob.size > maxBytes) {
    let edge = Math.round(maxEdge * 0.75)
    while (blob.size > maxBytes && edge >= 160) {
      const scaled = document.createElement('canvas')
      const sw = Math.round((w * edge) / maxEdge)
      const sh = Math.round((h * edge) / maxEdge)
      scaled.width = Math.max(1, sw)
      scaled.height = Math.max(1, sh)
      const sctx = scaled.getContext('2d')
      if (!sctx) break
      sctx.fillStyle = '#ffffff'
      sctx.fillRect(0, 0, scaled.width, scaled.height)
      sctx.drawImage(canvas, 0, 0, scaled.width, scaled.height)
      blob = await canvasToBlob(scaled, mime, 0.72)
      edge = Math.round(edge * 0.8)
    }
  }

  return blob
}

function canvasToBlob(canvas: HTMLCanvasElement, type: string, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (b) => (b ? resolve(b) : reject(new Error('ENCODE_FAIL'))),
      type,
      quality,
    )
  })
}

export function avatarSrc(url: string | null | undefined, apiBase?: string): string | null {
  if (!url) return null
  if (/^https?:\/\//i.test(url) || url.startsWith('data:')) return url
  const base = (apiBase ?? import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8001').replace(/\/$/, '')
  return url.startsWith('/') ? `${base}${url}` : `${base}/${url}`
}
