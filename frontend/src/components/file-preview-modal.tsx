import { useEffect, useState, useCallback, useRef } from "react"
import { X, Download, Printer, Loader2, AlertCircle, FileText, File, RefreshCw, ImageIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { useTranslation } from "@/lib/i18n"
import Papa from "papaparse"
import { apiRequest } from "@/services/api"
import type { Document } from "@/types/api"

interface FilePreviewModalProps {
  doc: Document | null
  onClose: () => void
}

type FileKind = "pdf" | "docx" | "csv" | "txt" | "image" | "unsupported"

type PreviewState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "pdf"; blobUrl: string }
  | { status: "image"; blobUrl: string }
  | { status: "docx"; container: HTMLElement }
  | { status: "text"; content: string }
  | { status: "csv"; headers: string[]; rows: string[][] }
  | { status: "unsupported" }
  | { status: "error"; message: string; detail?: string }

function resolveKind(mimeType: string, fileName: string): FileKind {
  const ext = fileName.split(".").pop()?.toLowerCase() ?? ""
  if (mimeType.startsWith("image/") || ["jpg", "jpeg", "png", "webp", "heic", "gif"].includes(ext)) return "image"
  if (mimeType.includes("pdf") || ext === "pdf") return "pdf"
  if (mimeType.includes("wordprocessingml") || mimeType.includes("msword") || ext === "docx" || ext === "doc") return "docx"
  if (mimeType.includes("csv") || ext === "csv") return "csv"
  if (mimeType.includes("text/plain") || mimeType.includes("text") || ext === "txt") return "txt"
  return "unsupported"
}

async function fetchDocBlob(docId: string): Promise<Blob> {
  // apiRequest handles 401 → auto token refresh → retry automatically
  const response = await apiRequest<Response>(`/api/documents/${docId}/preview`)
  return response.blob()
}

export function FilePreviewModal({ doc, onClose }: FilePreviewModalProps) {
  const [state, setState] = useState<PreviewState>({ status: "idle" })
  const { t } = useTranslation()
  const docxContainerRef = useRef<HTMLDivElement>(null)
  const blobUrlRef = useRef<string | null>(null)

  const loadPreview = useCallback(async (document: Document) => {
    setState({ status: "loading" })
    if (blobUrlRef.current) { URL.revokeObjectURL(blobUrlRef.current); blobUrlRef.current = null }

    const kind = resolveKind(document.file_type, document.file_name)

    if (kind === "docx") {
      try {
        const blob = await fetchDocBlob(document.id)
        const { renderAsync } = await import("docx-preview")
        const container = window.document.createElement("div")
        container.className = "docx-preview-container"
        await renderAsync(blob, container, undefined, { className: "docx-rendered", inWrapper: true, ignoreWidth: false, ignoreHeight: false, renderHeaders: true, renderFooters: true, renderFootnotes: true })
        setState({ status: "docx", container })
      } catch (err: any) { setState({ status: "error", message: t("preview.cantPreviewWord"), detail: err.message }) }
      return
    }

    if (kind === "pdf") {
      try {
        const blob = await fetchDocBlob(document.id)
        const url = URL.createObjectURL(blob)
        blobUrlRef.current = url
        setState({ status: "pdf", blobUrl: url })
      } catch (err: any) { setState({ status: "error", message: t("preview.cantLoadPdf"), detail: err.message }) }
      return
    }

    if (kind === "image") {
      try {
        const blob = await fetchDocBlob(document.id)
        const url = URL.createObjectURL(blob)
        blobUrlRef.current = url
        setState({ status: "image", blobUrl: url })
      } catch (err: any) { setState({ status: "error", message: t("preview.cantLoadImage"), detail: err.message }) }
      return
    }

    if (kind === "txt") {
      try {
        const blob = await fetchDocBlob(document.id)
        const text = await blob.text()
        setState({ status: "text", content: text })
      } catch (err: any) { setState({ status: "error", message: t("preview.cantLoadText"), detail: err.message }) }
      return
    }

    if (kind === "csv") {
      try {
        const blob = await fetchDocBlob(document.id)
        const text = await blob.text()
        const result = Papa.parse<string[]>(text, { skipEmptyLines: true })
        const [headers = [], ...rows] = result.data as string[][]
        setState({ status: "csv", headers, rows })
      } catch (err: any) { setState({ status: "error", message: t("preview.cantReadCsv"), detail: err.message }) }
      return
    }

    setState({ status: "unsupported" })
  }, [])

  useEffect(() => {
    if (state.status === "docx" && docxContainerRef.current) {
      docxContainerRef.current.innerHTML = ""
      docxContainerRef.current.appendChild(state.container)
    }
  }, [state])

  useEffect(() => {
    if (doc) { loadPreview(doc) }
    else { setState({ status: "idle" }) }
    return () => { if (blobUrlRef.current) { URL.revokeObjectURL(blobUrlRef.current); blobUrlRef.current = null } }
  }, [doc, loadPreview])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [onClose])

  const handleDownload = async () => {
    if (!doc) return
    try {
      const response = await apiRequest<Response>(`/api/documents/${doc.id}/download`)
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = window.document.createElement("a")
      a.href = url
      a.download = doc.file_name
      window.document.body.appendChild(a)
      a.click()
      URL.revokeObjectURL(url)
      window.document.body.removeChild(a)
    } catch { /* ignore */ }
  }

  const handlePrint = () => {
    const iframe = window.document.querySelector<HTMLIFrameElement>("#preview-pdf-frame")
    if (iframe?.contentWindow) { iframe.contentWindow.focus(); iframe.contentWindow.print() }
    else { window.print() }
  }

  if (!doc) return null
  const kind = resolveKind(doc.file_type, doc.file_name)
  const ext = doc.file_name.split(".").pop()?.toUpperCase() ?? ""
  const kindColor: Record<FileKind, string> = { pdf: "text-red-500", docx: "text-blue-500", csv: "text-emerald-500", txt: "text-purple-500", image: "text-pink-500", unsupported: "text-muted-foreground" }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-2 sm:p-4 backdrop-blur-sm" onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="flex w-full max-w-5xl flex-col rounded-2xl bg-background shadow-2xl overflow-hidden" style={{ height: "90dvh" }} onClick={(e) => e.stopPropagation()}>

        {/* Toolbar */}
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border px-4 py-3">
          <div className="flex min-w-0 items-center gap-2">
            {kind === "image" ? (
              <ImageIcon className={cn("h-5 w-5 shrink-0", kindColor[kind])} />
            ) : (
              <FileText className={cn("h-5 w-5 shrink-0", kindColor[kind])} />
            )}
            <p className="truncate text-sm font-semibold text-foreground">{doc.title}</p>
            <span className="hidden shrink-0 rounded-md bg-secondary px-2 py-0.5 text-xs text-muted-foreground sm:block">{ext}</span>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <Button size="sm" variant="ghost" className="gap-1.5 text-xs hidden sm:flex" onClick={handleDownload}><Download className="h-4 w-4" />{t("preview.download")}</Button>
            <Button size="sm" variant="ghost" className="gap-1.5 text-xs hidden sm:flex" onClick={handlePrint}><Printer className="h-4 w-4" />{t("preview.print")}</Button>
            <Button size="icon" variant="ghost" className="h-8 w-8 shrink-0 sm:hidden" onClick={handleDownload} title={t("preview.download")}><Download className="h-4 w-4" /></Button>
            <Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground" onClick={onClose} title={t("preview.closeEsc")}><X className="h-4 w-4" /></Button>
          </div>
        </div>

        {/* Content */}
        <div className="relative min-h-0 flex-1 overflow-hidden">

          {state.status === "loading" && (
            <div className="flex h-full items-center justify-center">
              <div className="flex flex-col items-center gap-3">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <p className="text-sm text-muted-foreground">{t("preview.loadingContent")}</p>
                <div className="mt-4 w-64 space-y-3 opacity-40">
                  {[72, 88, 64, 80, 90, 68].map((w, i) => (
                    <div key={i} className="h-3 rounded bg-muted animate-pulse" style={{ width: `${w}%` }} />
                  ))}
                </div>
              </div>
            </div>
          )}

          {state.status === "pdf" && (
            <iframe id="preview-pdf-frame" src={state.blobUrl} className="h-full w-full border-0" title={doc.title} />
          )}

          {state.status === "image" && (
            <div className="flex h-full w-full items-center justify-center overflow-auto bg-muted/30 p-4">
              <img
                src={state.blobUrl}
                alt={doc.title}
                className="max-h-full max-w-full rounded-lg border border-border bg-background object-contain shadow-sm"
              />
            </div>
          )}

          {state.status === "docx" && (
            <div className="h-full w-full overflow-auto bg-[#f0f0f0] p-4">
              <div ref={docxContainerRef} className="mx-auto [&_.docx-wrapper]:bg-white [&_.docx-wrapper]:shadow-md [&_.docx-wrapper]:p-8" />
            </div>
          )}

          {state.status === "text" && (
            <div className="h-full overflow-auto p-6">
              <pre className="whitespace-pre-wrap break-words font-mono text-sm text-foreground leading-relaxed">{state.content}</pre>
            </div>
          )}

          {state.status === "csv" && (
            <div className="h-full overflow-auto p-4">
              {state.headers.length === 0 ? (
                <p className="py-12 text-center text-sm text-muted-foreground">{t("preview.emptyCsv")}</p>
              ) : (
                <div className="rounded-lg border border-border overflow-auto">
                  <table className="w-full border-collapse text-sm">
                    <thead>
                      <tr>
                        {state.headers.map((h, i) => (
                          <th key={i} className="sticky top-0 z-10 bg-secondary border-b border-border px-3 py-2 text-left text-xs font-semibold text-foreground whitespace-nowrap">{h || `Col ${i + 1}`}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {state.rows.map((row, ri) => (
                        <tr key={ri} className={cn("hover:bg-accent/50 transition-colors", ri % 2 === 0 ? "bg-background" : "bg-secondary/30")}>
                          {state.headers.map((_, ci) => (
                            <td key={ci} className="border-b border-border px-3 py-1.5 text-foreground max-w-[240px] truncate" title={row[ci] ?? ""}>{row[ci] ?? ""}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {state.status === "unsupported" && (
            <div className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
              <File className="h-16 w-16 text-muted-foreground" />
              <div>
                <p className="text-base font-semibold text-foreground">{t("preview.cantPreviewType")}</p>
                <p className="mt-1 text-sm text-muted-foreground">{t("preview.downloadToView")}</p>
              </div>
              <Button onClick={handleDownload} className="gap-2"><Download className="h-4 w-4" />{t("preview.downloadToViewBtn")}</Button>
            </div>
          )}

          {state.status === "error" && (
            <div className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
              <AlertCircle className="h-12 w-12 text-destructive" />
              <div>
                <p className="text-sm font-semibold text-foreground">{state.message}</p>
                {state.detail && <p className="mt-1 text-xs text-muted-foreground font-mono">{state.detail}</p>}
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" className="gap-1.5" onClick={() => loadPreview(doc)}><RefreshCw className="h-3.5 w-3.5" />{t("common.retry")}</Button>
                <Button size="sm" className="gap-1.5" onClick={handleDownload}><Download className="h-3.5 w-3.5" />{t("preview.download")}</Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
