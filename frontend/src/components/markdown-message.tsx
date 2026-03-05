import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '@/lib/utils'

interface MarkdownMessageProps {
  content: string
  role: 'user' | 'assistant'
}

export function MarkdownMessage({ content, role }: MarkdownMessageProps) {
  // User messages don't need markdown rendering
  if (role === 'user') {
    return <p className="whitespace-pre-wrap text-sm">{content}</p>
  }

  // Assistant messages with markdown rendering
  return (
    <div className="prose prose-sm max-w-none dark:prose-invert">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
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
            <strong className="font-bold text-primary" {...props} />
          ),

          // Emphasis/Italic
          em: ({ node, ...props }) => (
            <em className="italic text-foreground" {...props} />
          ),

          // Code
          code: ({ node, inline, className, children, ...props }: any) => {
            if (inline) {
              return (
                <code
                  className="px-1.5 py-0.5 rounded bg-muted text-xs font-mono text-primary"
                  {...props}
                >
                  {children}
                </code>
              )
            }
            return (
              <code
                className={cn(
                  'block p-3 rounded-lg bg-muted/50 text-xs font-mono overflow-x-auto mb-3',
                  className
                )}
                {...props}
              >
                {children}
              </code>
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

          // Links
          a: ({ node, ...props }) => (
            <a
              className="text-primary hover:underline font-medium"
              target="_blank"
              rel="noopener noreferrer"
              {...props}
            />
          ),

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
        {content}
      </ReactMarkdown>
    </div>
  )
}
