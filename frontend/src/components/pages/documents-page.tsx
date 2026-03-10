import { useState, useRef } from "react"
import {
  FileText,
  Upload,
  Search,
  Grid3X3,
  List,
  MoreVertical,
  Download,
  Trash2,
  File,
  FileSpreadsheet,
  Loader2,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { useDocuments } from "@/hooks/use-documents"
import { useToast } from "@/hooks/use-toast"
import { FilePreviewModal } from "@/components/file-preview-modal"
import type { Document } from "@/types/api"
import { useTranslation } from "@/lib/i18n"

function getFileIcon(type: string) {
  switch (type) {
    case "pdf":
      return <FileText className="h-5 w-5 text-red-500" />
    case "doc":
      return <File className="h-5 w-5 text-blue-500" />
    case "csv":
      return <FileSpreadsheet className="h-5 w-5 text-emerald-500" />
    case "txt":
      return <FileText className="h-5 w-5 text-purple-500" />
    default:
      return <File className="h-5 w-5 text-muted-foreground" />
  }
}

function getFileColor(type: string) {
  switch (type) {
    case "pdf":
      return "bg-red-50 border-red-100"
    case "doc":
      return "bg-blue-50 border-blue-100"
    case "csv":
      return "bg-emerald-50 border-emerald-100"
    case "txt":
      return "bg-purple-50 border-purple-100"
    default:
      return "bg-secondary"
  }
}

function getFileTypeFromMime(mimeType: string) {
  if (mimeType.includes('pdf')) return 'pdf'
  if (mimeType.includes('word') || mimeType.includes('document')) return 'doc'
  if (mimeType.includes('csv') || mimeType.includes('sheet') || mimeType.includes('excel')) return 'csv'
  if (mimeType.includes('text/plain') || mimeType === 'text') return 'txt'
  return 'file'
}

export function DocumentsPage() {
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid")
  const [searchQuery, setSearchQuery] = useState("")
  const [filterType, setFilterType] = useState("all")
  const [isDragging, setIsDragging] = useState(false)
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [title, setTitle] = useState("")
  const [category, setCategory] = useState("")
  const [tags, setTags] = useState("")
  const [previewDoc, setPreviewDoc] = useState<Document | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  
  const { documents, loading, uploadDocument, deleteDocument } = useDocuments()
  const { toast } = useToast()
  const { t } = useTranslation()

  const filteredDocs = documents.filter((doc) => {
    const matchesSearch = doc.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         doc.file_name.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesType = filterType === "all" || getFileTypeFromMime(doc.file_type) === filterType
    return matchesSearch && matchesType
  })

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setSelectedFile(file)
      setTitle(file.name)
    }
  }

  const handleUpload = async () => {
    if (!selectedFile) {
      toast({
        title: t("common.error"),
        description: t("docs.selectFile"),
        variant: "destructive",
      })
      return
    }

    setUploading(true)
    try {
      await uploadDocument({
        file: selectedFile,
        title: title || undefined,
        category: category || undefined,
        tags: tags ? tags.split(',').map(t => t.trim()) : undefined,
      })
      
      toast({
        title: t("common.success"),
        description: t("docs.uploadSuccess"),
      })
      
      setUploadDialogOpen(false)
      setSelectedFile(null)
      setTitle("")
      setCategory("")
      setTags("")
    } catch (error: any) {
      toast({
        title: t("docs.uploadFailed"),
        description: error.message || t("docs.failedUpload"),
        variant: "destructive",
      })
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async (docId: string) => {
    try {
      await deleteDocument(docId)
      toast({
        title: t("common.success"),
        description: t("docs.deleteSuccess"),
      })
    } catch (error: any) {
      toast({
        title: t("docs.deleteFailed"),
        description: error.message || "Failed to delete document",
        variant: "destructive",
      })
    }
  }

  const handleDownload = async (docId: string, fileName: string) => {
    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_BASE_URL}/api/documents/${docId}/download`,
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('access_token')}`,
          },
        }
      )
      
      if (!response.ok) throw new Error('Download failed')
      
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = fileName
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (error: any) {
      toast({
        title: t("docs.downloadFailed"),
        description: error.message || "Failed to download document",
        variant: "destructive",
      })
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  return (
    <div className="space-y-6 p-4 md:p-6 lg:p-8">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t("docs.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("docs.subtitle")}</p>
        </div>
        <Dialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen}>
          <DialogTrigger asChild>
            <Button className="gap-2 bg-primary text-primary-foreground hover:bg-primary/90">
              <Upload className="h-4 w-4" />
              {t("docs.uploadFile")}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t("docs.uploadDocument")}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-4">
              <div>
                <Label htmlFor="file">{t("docs.file")}</Label>
                <Input
                  ref={fileInputRef}
                  id="file"
                  type="file"
                  accept=".pdf,.doc,.docx,.txt,.csv"
                  onChange={handleFileSelect}
                  className="mt-1"
                />
                {selectedFile && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Selected: {selectedFile.name} ({formatFileSize(selectedFile.size)})
                  </p>
                )}
              </div>
              <div>
                <Label htmlFor="title">{t("docs.titleOptional")}</Label>
                <Input
                  id="title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder={t("docs.titlePlaceholder")}
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="category">{t("docs.categoryOptional")}</Label>
                <Input
                  id="category"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  placeholder={t("docs.categoryPlaceholder")}
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="tags">{t("docs.tagsOptional")}</Label>
                <Input
                  id="tags"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  placeholder={t("docs.tagsPlaceholder")}
                  className="mt-1"
                />
              </div>
              <div className="flex gap-2">
                <Button
                  onClick={handleUpload}
                  disabled={!selectedFile || uploading}
                  className="flex-1"
                >
                  {uploading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {t("common.upload")}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    setUploadDialogOpen(false)
                    setSelectedFile(null)
                    setTitle("")
                    setCategory("")
                    setTags("")
                  }}
                  disabled={uploading}
                >
                  {t("common.cancel")}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Drag & Drop Zone */}
      <div
        className={cn(
          "rounded-xl border-2 border-dashed transition-all",
          isDragging
            ? "border-primary bg-accent/50 p-8"
            : "border-transparent p-0"
        )}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => { e.preventDefault(); setIsDragging(false) }}
      >
        {isDragging && (
          <div className="flex items-center justify-center">
            <div className="text-center">
              <Upload className="mx-auto mb-2 h-8 w-8 text-primary" />
              <p className="text-sm font-medium text-foreground">{t("docs.dropToUpload")}</p>
            </div>
          </div>
        )}
      </div>

      {/* Filters & View Toggle */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-1 items-center gap-3">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder={t("docs.searchPlaceholder")}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-9 bg-card pl-9 text-sm"
            />
          </div>
          <Select value={filterType} onValueChange={setFilterType}>
            <SelectTrigger className="w-[120px] h-9 bg-card">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("docs.allTypes")}</SelectItem>
              <SelectItem value="pdf">{t("docs.pdf")}</SelectItem>
              <SelectItem value="doc">{t("docs.documents")}</SelectItem>
              <SelectItem value="txt">{t("docs.txt")}</SelectItem>
              <SelectItem value="csv">{t("docs.csvExcel")}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-1 rounded-lg border border-border bg-card p-1">
          <Button
            size="icon"
            variant={viewMode === "grid" ? "default" : "ghost"}
            className={cn("h-7 w-7", viewMode === "grid" ? "bg-primary text-primary-foreground" : "text-muted-foreground")}
            onClick={() => setViewMode("grid")}
          >
            <Grid3X3 className="h-3.5 w-3.5" />
          </Button>
          <Button
            size="icon"
            variant={viewMode === "list" ? "default" : "ghost"}
            className={cn("h-7 w-7", viewMode === "list" ? "bg-primary text-primary-foreground" : "text-muted-foreground")}
            onClick={() => setViewMode("list")}
          >
            <List className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* File Grid */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      ) : filteredDocs.length === 0 ? (
        <Card className="p-12">
          <div className="flex flex-col items-center justify-center text-center">
            <FileText className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium text-foreground mb-2">{t("docs.noDocuments")}</h3>
            <p className="text-sm text-muted-foreground mb-4">
              {t("docs.uploadFirst")}
            </p>
          </div>
        </Card>
      ) : viewMode === "grid" ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filteredDocs.map((doc) => (
            <Card
              key={doc.id}
              className="group cursor-pointer transition-all hover:shadow-md"
              onDoubleClick={() => setPreviewDoc(doc)}
              title={t("docs.dblClickPreview")}
            >
              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div className={cn("flex h-12 w-12 items-center justify-center rounded-xl border", getFileColor(getFileTypeFromMime(doc.file_type)))}>
                    {getFileIcon(getFileTypeFromMime(doc.file_type))}
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={(e) => { e.stopPropagation(); handleDownload(doc.id, doc.file_name) }}>
                        <Download className="mr-2 h-4 w-4" /> {t("common.download")}
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem 
                        className="text-destructive"
                        onClick={(e) => { e.stopPropagation(); handleDelete(doc.id) }}
                      >
                        <Trash2 className="mr-2 h-4 w-4" /> {t("common.delete")}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
                <div className="mt-3">
                  <p className="truncate text-sm font-medium text-foreground">{doc.title}</p>
                  <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                    <span>{formatFileSize(doc.file_size)}</span>
                    <span>&middot;</span>
                    <span>{new Date(doc.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
                <div className="mt-3 flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">{doc.category}</span>
                  {doc.is_processed && (
                    <Badge variant="secondary" className="text-xs">
                      {t("common.processed")}
                    </Badge>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <div className="divide-y divide-border">
            {/* Table header */}
            <div className="hidden items-center gap-4 px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider sm:flex">
              <span className="flex-1">{t("docs.name")}</span>
              <span className="w-24 text-right">{t("docs.size")}</span>
              <span className="w-28">{t("docs.modified")}</span>
              <span className="w-24">{t("docs.category")}</span>
              <span className="w-8" />
            </div>
            {filteredDocs.map((doc) => (
              <div
                key={doc.id}
                className="group flex items-center gap-4 px-4 py-3 transition-colors hover:bg-secondary cursor-pointer"
                onDoubleClick={() => setPreviewDoc(doc)}
                title={t("docs.dblClickPreview")}
              >
                <div className="flex flex-1 items-center gap-3 overflow-hidden">
                  {getFileIcon(getFileTypeFromMime(doc.file_type))}
                  <span className="truncate text-sm font-medium text-foreground">{doc.title}</span>
                  {doc.is_processed && (
                    <Badge variant="secondary" className="shrink-0 text-xs">
                      {t("common.processed")}
                    </Badge>
                  )}
                </div>
                <span className="hidden w-24 text-right text-sm text-muted-foreground sm:block">
                  {formatFileSize(doc.file_size)}
                </span>
                <span className="hidden w-28 text-sm text-muted-foreground sm:block">
                  {new Date(doc.created_at).toLocaleDateString()}
                </span>
                <span className="hidden w-24 text-sm text-muted-foreground sm:block">{doc.category}</span>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <MoreVertical className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={(e) => { e.stopPropagation(); handleDownload(doc.id, doc.file_name) }}>
                      <Download className="mr-2 h-4 w-4" /> {t("common.download")}
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem 
                      className="text-destructive"
                      onClick={(e) => { e.stopPropagation(); handleDelete(doc.id) }}
                    >
                      <Trash2 className="mr-2 h-4 w-4" /> {t("common.delete")}
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* File Preview Modal */}
      <FilePreviewModal
        doc={previewDoc}
        onClose={() => setPreviewDoc(null)}
      />
    </div>
  )
}
