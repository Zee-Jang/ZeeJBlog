import { onUnmounted, ref } from 'vue'

/** Lightweight copy feedback for invite pages (toast text + auto clear). */
export function useCopyToast(ms = 2200) {
  const toast = ref('')
  let timer: number | undefined

  function showToast(message: string) {
    toast.value = message
    if (timer) window.clearTimeout(timer)
    timer = window.setTimeout(() => {
      toast.value = ''
      timer = undefined
    }, ms)
  }

  async function copyText(text: string, okMessage: string, failMessage?: string) {
    try {
      await navigator.clipboard.writeText(text)
      showToast(okMessage)
      return true
    } catch {
      showToast(failMessage || okMessage)
      return false
    }
  }

  onUnmounted(() => {
    if (timer) window.clearTimeout(timer)
  })

  return { toast, showToast, copyText }
}
