import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import { cn } from '@/lib/utils'
import { useNavigate } from 'react-router-dom'
import type { DocMapItem } from '@/types/api'
import { isValidElement, useMemo, useState } from 'react'
import { Check, Copy } from 'lucide-react'

import 'katex/dist/katex.min.css'

interface MarkdownMessageProps {
  content: string
  role: 'user' | 'assistant'
  docMap?: DocMapItem[]
}

/**
 * Preprocess AI content to convert [filename] citations into markdown links.
 * The pattern matches `[filename.ext]` that appear in the text (not already
 * part of a markdown link) and converts them to `[filename.ext](/documents?preview=document_id)`.
 */
function preprocessCitations(content: string, docMap: DocMapItem[]): string {
  if (!docMap || docMap.length === 0) return content

  let processed = content

  // Only use raw filename alias when it is unique to avoid wrong link mapping.
  const rawNameCounts = new Map<string, number>()
  for (const item of docMap) {
    const raw = (item.raw_file_name || '').trim()
    if (!raw) continue
    rawNameCounts.set(raw, (rawNameCounts.get(raw) || 0) + 1)
  }

  for (const { file_name, raw_file_name, document_id } of docMap) {
    if (!file_name || !document_id) continue

    const aliases = [file_name]
    const raw = (raw_file_name || '').trim()
    if (raw && rawNameCounts.get(raw) === 1) {
      aliases.push(raw)
    }

    for (const alias of aliases) {
      if (!alias) continue

      // Escape special regex characters in alias
      const escaped = alias.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

      // Match [filename] that is NOT already a markdown link
      // i.e. not followed by (url) and not preceded by !
      // Negative lookbehind for ! (image) and negative lookahead for (
      const regex = new RegExp(
        `(?<!!)\\[${escaped}\\](?!\\()`,
        'g'
      )

      processed = processed.replace(
        regex,
        `[📄 ${file_name}](/documents?preview=${document_id})`
      )
    }
  }

  return processed
}

function isLikelyCodeLine(line: string): boolean {
  const trimmed = line.trim()
  if (!trimmed) return false

  if (/^```/.test(trimmed)) return false

  if (/^(def|class|import|from|return|if|elif|else|for|while|try|except|finally|with)\b/.test(trimmed)) {
    return true
  }

  if (/^(public|private|protected|static|final|class|interface|enum|void|int|long|double|float|boolean|String|new)\b/.test(trimmed)) {
    return true
  }

  if (/^(function|const|let|var|export|async|await)\b/.test(trimmed)) {
    return true
  }

  if (/System\.out\.println|console\.log|=>/.test(trimmed)) {
    return true
  }

  if (/=/.test(trimmed) && /[(){}\[\];]/.test(trimmed)) {
    return true
  }

  return /[{};]$/.test(trimmed)
}

function detectCodeLanguage(codeLines: string[]): string {
  const sample = codeLines.join('\n')

  if (/\b(def|import|from|elif|except|print\()\b/.test(sample)) return 'python'
  if (/\b(public class|System\.out\.println|String\s+\w+|int\s+\w+)\b/.test(sample)) return 'java'
  if (/\b(function|const|let|var|console\.log|=>)\b/.test(sample)) return 'javascript'

  return 'text'
}

function autoFenceLikelyCodeBlocks(content: string): string {
  const lines = content.replace(/\r\n/g, '\n').split('\n')
  const output: string[] = []

  let inFence = false
  let pendingCode: string[] = []
  let likelyCount = 0

  const flushPending = () => {
    if (pendingCode.length === 0) return

    if (likelyCount >= 3) {
      const language = detectCodeLanguage(pendingCode)
      output.push(`\n\`\`\`${language}`)
      output.push(...pendingCode)
      output.push('\`\`\`\n')
    } else {
      output.push(...pendingCode)
    }

    pendingCode = []
    likelyCount = 0
  }

  for (const line of lines) {
    const trimmed = line.trim()

    if (/^```/.test(trimmed)) {
      flushPending()
      inFence = !inFence
      output.push(line)
      continue
    }

    if (inFence) {
      output.push(line)
      continue
    }

    if (isLikelyCodeLine(line) || (pendingCode.length > 0 && trimmed === '')) {
      pendingCode.push(line)
      if (isLikelyCodeLine(line)) likelyCount++
      continue
    }

    flushPending()
    output.push(line)
  }

  flushPending()

  return output.join('\n').replace(/\n{3,}/g, '\n\n')
}

function collapseTinyCodeBlocks(content: string): string {
  return content.replace(/```([\w-]*)\n([\s\S]*?)\n```/g, (full, _lang, codeBody) => {
    const normalized = String(codeBody || '').trim()

    // Keep real code blocks. Only collapse token-like mini blocks that create choppy UX.
    if (!normalized || normalized.includes('\n') || normalized.length > 36) {
      return full
    }

    if (/^[\w.[\]()+\-*/<>!=:,]+$/.test(normalized)) {
      return `\`${normalized}\``
    }

    return full
  })
}

function transformOutsideCodeFences(content: string, transformer: (segment: string) => string): string {
  const parts = content.split(/(```[\s\S]*?```)/g)
  return parts
    .map((part, index) => (index % 2 === 1 ? part : transformer(part)))
    .join('')
}

function normalizeMathDelimiters(content: string): string {
  return transformOutsideCodeFences(content, (segment) => {
    let normalized = segment

    // Convert \[ ... \] into $$ ... $$
    normalized = normalized.replace(/\\\[([\s\S]*?)\\\]/g, (_, expr: string) => {
      const mathExpr = expr.trim()
      if (!mathExpr) return _
      return `\n$$\n${mathExpr}\n$$\n`
    })

    // Convert \( ... \) into $ ... $
    normalized = normalized.replace(/\\\((.+?)\\\)/g, (_, expr: string) => {
      const mathExpr = expr.trim()
      if (!mathExpr) return _
      return `$${mathExpr}$`
    })

    // If a line looks like raw LaTeX command without delimiters, wrap as block math.
    normalized = normalized.replace(
      /^(\s*\\(?:frac|sqrt|sum|int|lim|alpha|beta|gamma|delta|pi|theta|sin|cos|tan)\b[^\n$]*)$/gm,
      (_full: string, expr: string) => `$$\n${expr.trim()}\n$$`
    )

    return normalized
  })
}

function CodeBlock({ code, language }: { code: string; language?: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="mb-4 overflow-hidden rounded-xl border border-border bg-muted/70 text-foreground shadow-sm">
      <div className="flex items-center justify-between border-b border-border/80 bg-muted/90 px-3 py-2">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-foreground/80">
          {language || 'code'}
        </span>
        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground transition hover:bg-secondary hover:text-foreground"
          aria-label="Copy code"
        >
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre className="overflow-x-auto bg-background/55 p-3 text-xs leading-6">
        <code className="font-mono">{code}</code>
      </pre>
    </div>
  )
}

export function MarkdownMessage({ content, role, docMap }: MarkdownMessageProps) {
  const navigate = useNavigate()

  // User messages don't need markdown rendering
  if (role === 'user') {
    return <p className="whitespace-pre-wrap text-sm">{content}</p>
  }

  // Preprocess citations to add clickable links
  const processedContent = useMemo(
    () => normalizeMathDelimiters(autoFenceLikelyCodeBlocks(collapseTinyCodeBlocks(preprocessCitations(content, docMap || [])))),
    [content, docMap]
  )

  // Handle clicks on internal document links
  const handleLinkClick = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    if (href.startsWith('/documents?preview=')) {
      e.preventDefault()
      navigate(href)
    }
  }

  // Assistant messages with markdown rendering
  return (
    <div className="prose prose-sm max-w-none break-words min-w-0 dark:prose-invert">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          // Headings
          h1: ({ node, ...props }) => (
            <h1 className="text-xl font-bold mt-6 mb-4 text-foreground" {...props} />
          ),
          h2: ({ node, ...props }) => (
            <h2 className="text-lg font-bold mt-5 mb-3 text-foreground" {...props} />
          ),
          h3: ({ node, ...props }) => (
            <h3 className="text-base font-semibold mt-4 mb-2 text-foreground" {...props} />
          ),
          h4: ({ node, ...props }) => (
            <h4 className="text-sm font-semibold mt-3 mb-2 text-foreground" {...props} />
          ),

          // Paragraphs
          p: ({ node, ...props }) => (
            <p className="mb-3 text-sm leading-relaxed text-foreground" {...props} />
          ),

          // Lists
          ul: ({ node, ...props }) => (
            <ul className="list-disc list-inside mb-3 space-y-1 text-sm text-foreground" {...props} />
          ),
          ol: ({ node, ...props }) => (
            <ol className="list-decimal list-inside mb-3 space-y-1 text-sm text-foreground" {...props} />
          ),
          li: ({ node, ...props }) => (
            <li className="ml-2 text-foreground" {...props} />
          ),

          // Strong/Bold
          strong: ({ node, ...props }) => (
            <strong className="font-semibold text-foreground" {...props} />
          ),

          // Emphasis/Italic
          em: ({ node, ...props }) => (
            <em className="italic text-foreground" {...props} />
          ),

          // Inline code only; block code is handled by `pre`.
          code: ({ node, children, ...props }: any) => (
            <code
              className="rounded bg-muted/80 px-1.5 py-0.5 text-xs font-mono text-foreground"
              {...props}
            >
              {children}
            </code>
          ),

          pre: ({ children }: any) => {
            const firstChild = Array.isArray(children) ? children[0] : children

            if (isValidElement(firstChild)) {
              const childProps: any = firstChild.props || {}
              const className = childProps.className || ''
              const match = /language-([\w-]+)/.exec(className)
              const language = match?.[1]
              const code = String(childProps.children || '').replace(/\n$/, '')

              return <CodeBlock code={code} language={language} />
            }

            return (
              <pre className="overflow-x-auto rounded-md border border-border bg-muted/60 p-3 text-xs leading-6 text-foreground">
                {children}
              </pre>
            )
          },

          // Blockquote
          blockquote: ({ node, ...props }) => (
            <blockquote
              className="border-l-4 border-primary pl-4 italic text-muted-foreground my-3"
              {...props}
            />
          ),

          // Horizontal rule
          hr: ({ node, ...props }) => (
            <hr className="my-4 border-border" {...props} />
          ),

          // Links — internal document links use navigate, external links open in new tab
          a: ({ node, href, children, ...props }) => {
            const isDocLink = href?.startsWith('/documents?preview=')
            return (
              <a
                className={cn(
                  "font-medium cursor-pointer",
                  isDocLink
                    ? "text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center gap-0.5"
                    : "text-primary hover:underline"
                )}
                href={isDocLink ? undefined : href}
                target={isDocLink ? undefined : "_blank"}
                rel={isDocLink ? undefined : "noopener noreferrer"}
                onClick={(e) => {
                  if (isDocLink && href) {
                    handleLinkClick(e, href)
                  }
                }}
                {...props}
              >
                {children}
              </a>
            )
          },

          // Tables
          table: ({ node, ...props }) => (
            <div className="overflow-x-auto mb-3">
              <table className="min-w-full border border-border text-sm" {...props} />
            </div>
          ),
          thead: ({ node, ...props }) => (
            <thead className="bg-muted" {...props} />
          ),
          tbody: ({ node, ...props }) => (
            <tbody {...props} />
          ),
          tr: ({ node, ...props }) => (
            <tr className="border-b border-border" {...props} />
          ),
          th: ({ node, ...props }) => (
            <th className="px-3 py-2 text-left font-semibold text-foreground" {...props} />
          ),
          td: ({ node, ...props }) => (
            <td className="px-3 py-2 text-foreground" {...props} />
          ),
        }}
      >
        {processedContent}
      </ReactMarkdown>
    </div>
  )
}
