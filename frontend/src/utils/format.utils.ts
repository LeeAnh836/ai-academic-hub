/**
 * Format utility functions
 * Xử lý các định dạng date, time, file size, etc.
 */

/**
 * Format date to relative time (2m ago, 1h ago, etc.)
 * @param dateString - ISO date string hoặc Date object
 * @returns Relative time string
 */
export function formatRelativeTime(dateString: string | Date, t?: (key: string, params?: Record<string, string | number>) => string): string {
  const date = typeof dateString === 'string' ? new Date(dateString) : dateString
  const now = new Date()
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000)

  if (t) {
    if (seconds < 60) return t("time.justNow")
    if (seconds < 3600) return t("time.minutesAgo", { n: Math.floor(seconds / 60) })
    if (seconds < 86400) return t("time.hoursAgo", { n: Math.floor(seconds / 3600) })
    if (seconds < 2592000) return t("time.daysAgo", { n: Math.floor(seconds / 86400) })
    if (seconds < 31536000) return t("time.monthsAgo", { n: Math.floor(seconds / 2592000) })
    return t("time.yearsAgo", { n: Math.floor(seconds / 31536000) })
  }

  if (seconds < 60) return "Just now"
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  if (seconds < 2592000) return `${Math.floor(seconds / 86400)}d ago`
  if (seconds < 31536000) return `${Math.floor(seconds / 2592000)}mo ago`
  return `${Math.floor(seconds / 31536000)}y ago`
}

/**
 * Format date to readable format
 * @param dateString - ISO date string
 * @returns Formatted date (Jan 15, 2024)
 */
export function formatDate(dateString: string, locale?: string): string {
  const date = new Date(dateString)
  return date.toLocaleDateString(locale || "en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  })
}

/**
 * Format date and time
 * @param dateString - ISO date string
 * @returns Formatted date and time
 */
export function formatDateTime(dateString: string, locale?: string): string {
  const date = new Date(dateString)
  return date.toLocaleString(locale || "en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

/**
 * Format file size
 * @param bytes - File size in bytes
 * @returns Formatted file size (1.5 MB)
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B"
  
  const k = 1024
  const sizes = ["B", "KB", "MB", "GB", "TB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`
}

/**
 * Format number with commas
 * @param num - Number to format
 * @returns Formatted number (1,234,567)
 */
export function formatNumber(num: number, locale?: string): string {
  return num.toLocaleString(locale || "en-US")
}

/**
 * Truncate text
 * @param text - Text to truncate
 * @param maxLength - Maximum length
 * @returns Truncated text with ellipsis
 */
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength) + "..."
}
