import { useState } from "react"
import {
  FileText,
  Upload,
  Search,
  Grid3X3,
  List,
  MoreVertical,
  Download,
  Trash2,
  Share2,
  Eye,
  File,
  FileSpreadsheet,
  Presentation,
  FolderUp,
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
import { mockDocuments } from "@/lib/mock-data"

function getFileIcon(type: string) {
  switch (type) {
    case "pdf":
      return <FileText className="h-5 w-5 text-red-500" />
    case "doc":
      return <File className="h-5 w-5 text-blue-500" />
    case "xls":
      return <FileSpreadsheet className="h-5 w-5 text-emerald-500" />
    case "ppt":
      return <Presentation className="h-5 w-5 text-orange-500" />
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
    case "xls":
      return "bg-emerald-50 border-emerald-100"
    case "ppt":
      return "bg-orange-50 border-orange-100"
    default:
      return "bg-secondary"
  }
}

export function DocumentsPage() {
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid")
  const [searchQuery, setSearchQuery] = useState("")
  const [filterType, setFilterType] = useState("all")
  const [isDragging, setIsDragging] = useState(false)

  const filteredDocs = mockDocuments.filter((doc) => {
    const matchesSearch = doc.name.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesType = filterType === "all" || doc.type === filterType
    return matchesSearch && matchesType
  })

  return (
    <div className="space-y-6 p-4 md:p-6 lg:p-8">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Documents</h1>
          <p className="text-sm text-muted-foreground">Manage and share your study files</p>
        </div>
        <Dialog>
          <DialogTrigger asChild>
            <Button className="gap-2 bg-primary text-primary-foreground hover:bg-primary/90">
              <Upload className="h-4 w-4" />
              Upload File
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Upload Files</DialogTitle>
            </DialogHeader>
            <div className="pt-4">
              <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-border p-10 text-center transition-colors hover:border-primary/50 hover:bg-accent/50">
                <FolderUp className="mb-4 h-10 w-10 text-muted-foreground" />
                <p className="text-sm font-medium text-foreground">Drag and drop files here</p>
                <p className="mt-1 text-xs text-muted-foreground">or click to browse</p>
                <Button variant="outline" className="mt-4 bg-transparent">
                  Browse Files
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
              <p className="text-sm font-medium text-foreground">Drop files to upload</p>
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
              placeholder="Search documents..."
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
              <SelectItem value="all">All Types</SelectItem>
              <SelectItem value="pdf">PDF</SelectItem>
              <SelectItem value="doc">Documents</SelectItem>
              <SelectItem value="xls">Spreadsheets</SelectItem>
              <SelectItem value="ppt">Presentations</SelectItem>
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
      {viewMode === "grid" ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filteredDocs.map((doc) => (
            <Card key={doc.id} className="group cursor-pointer transition-all hover:shadow-md">
              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div className={cn("flex h-12 w-12 items-center justify-center rounded-xl border", getFileColor(doc.type))}>
                    {getFileIcon(doc.type)}
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
                      >
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem>
                        <Eye className="mr-2 h-4 w-4" /> Preview
                      </DropdownMenuItem>
                      <DropdownMenuItem>
                        <Download className="mr-2 h-4 w-4" /> Download
                      </DropdownMenuItem>
                      <DropdownMenuItem>
                        <Share2 className="mr-2 h-4 w-4" /> Share
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem className="text-destructive">
                        <Trash2 className="mr-2 h-4 w-4" /> Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
                <div className="mt-3">
                  <p className="truncate text-sm font-medium text-foreground">{doc.name}</p>
                  <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                    <span>{doc.size}</span>
                    <span>&middot;</span>
                    <span>{doc.updatedAt}</span>
                  </div>
                </div>
                <div className="mt-3 flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">{doc.owner}</span>
                  {doc.shared && (
                    <Badge variant="secondary" className="text-xs">
                      Shared
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
              <span className="flex-1">Name</span>
              <span className="w-24 text-right">Size</span>
              <span className="w-28">Modified</span>
              <span className="w-24">Owner</span>
              <span className="w-8" />
            </div>
            {filteredDocs.map((doc) => (
              <div
                key={doc.id}
                className="group flex items-center gap-4 px-4 py-3 transition-colors hover:bg-secondary"
              >
                <div className="flex flex-1 items-center gap-3 overflow-hidden">
                  {getFileIcon(doc.type)}
                  <span className="truncate text-sm font-medium text-foreground">{doc.name}</span>
                  {doc.shared && (
                    <Badge variant="secondary" className="shrink-0 text-xs">
                      Shared
                    </Badge>
                  )}
                </div>
                <span className="hidden w-24 text-right text-sm text-muted-foreground sm:block">{doc.size}</span>
                <span className="hidden w-28 text-sm text-muted-foreground sm:block">{doc.updatedAt}</span>
                <span className="hidden w-24 text-sm text-muted-foreground sm:block">{doc.owner}</span>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
                    >
                      <MoreVertical className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem>
                      <Eye className="mr-2 h-4 w-4" /> Preview
                    </DropdownMenuItem>
                    <DropdownMenuItem>
                      <Download className="mr-2 h-4 w-4" /> Download
                    </DropdownMenuItem>
                    <DropdownMenuItem>
                      <Share2 className="mr-2 h-4 w-4" /> Share
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem className="text-destructive">
                      <Trash2 className="mr-2 h-4 w-4" /> Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
