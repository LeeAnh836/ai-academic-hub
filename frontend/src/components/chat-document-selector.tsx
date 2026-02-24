import { useState } from "react"
import { Upload, FileText, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useDocuments } from "@/hooks/use-documents"
import { documentService } from "@/services/document.service"
import { useToast } from "@/hooks/use-toast"
import type { Document } from "@/types/api"
import { cn } from "@/lib/utils"

interface ChatDocumentSelectorProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  selectedDocIds: string[]
  onDocumentsChange: (docIds: string[]) => void
}

export function ChatDocumentSelector({
  open,
  onOpenChange,
  selectedDocIds,
  onDocumentsChange,
}: ChatDocumentSelectorProps) {
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadTitle, setUploadTitle] = useState("")
  const [uploading, setUploading] = useState(false)
  const { documents, loading, refetch } = useDocuments(true)
  const { toast } = useToast()

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0]
      setUploadFile(file)
      setUploadTitle(file.name.replace(/\.[^/.]+$/, ""))  // Remove extension
    }
  }

  const handleUpload = async () => {
    if (!uploadFile) return

    setUploading(true)
    try {
      const newDoc = await documentService.uploadDocument({
        file: uploadFile,
        title: uploadTitle || uploadFile.name,
        category: "document",
      })
      
      toast({
        title: "Success",
        description: `Document uploaded: ${newDoc.title}`,
      })
      
      // Add to selected documents
      onDocumentsChange([...selectedDocIds, newDoc.id])
      
      // Reset form
      setUploadFile(null)
      setUploadTitle("")
      
      // Refresh documents list
      await refetch()
    } catch (error: any) {
      toast({
        title: "Upload failed",
        description: error.message || "Failed to upload document",
        variant: "destructive",
      })
    } finally {
      setUploading(false)
    }
  }

  const toggleDocument = (docId: string) => {
    if (selectedDocIds.includes(docId)) {
      onDocumentsChange(selectedDocIds.filter(id => id !== docId))
    } else {
      onDocumentsChange([...selectedDocIds, docId])
    }
  }

  const getFileIcon = (_fileType: string) => {
    return <FileText className="h-4 w-4" />
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Attach Documents to Chat</DialogTitle>
        </DialogHeader>

        <div className="flex-1 space-y-6 overflow-hidden flex flex-col">
          {/* Upload Section */}
          <div className="border-b pb-4">
            <h3 className="text-sm font-medium mb-3">Upload New Document</h3>
            <div className="space-y-3">
              <div>
                <Label htmlFor="file-upload" className="cursor-pointer">
                  <div className="flex items-center justify-center w-full h-24 border-2 border-dashed rounded-lg hover:bg-accent transition-colors">
                    {uploadFile ? (
                      <div className="text-center">
                        <FileText className="h-8 w-8 mx-auto mb-2 text-primary" />
                        <p className="text-sm font-medium">{uploadFile.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {formatFileSize(uploadFile.size)}
                        </p>
                      </div>
                    ) : (
                      <div className="text-center">
                        <Upload className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                        <p className="text-sm text-muted-foreground">
                          Click to select PDF, DOCX, or TXT file
                        </p>
                      </div>
                    )}
                  </div>
                  <Input
                    id="file-upload"
                    type="file"
                    accept=".pdf,.docx,.txt"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                </Label>
              </div>

              {uploadFile && (
                <div className="flex gap-2">
                  <Input
                    placeholder="Document title (optional)"
                    value={uploadTitle}
                    onChange={(e) => setUploadTitle(e.target.value)}
                    className="flex-1"
                  />
                  <Button onClick={handleUpload} disabled={uploading}>
                    {uploading ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Uploading...
                      </>
                    ) : (
                      "Upload"
                    )}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setUploadFile(null)
                      setUploadTitle("")
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              )}
            </div>
          </div>

          {/* Select from Library */}
          <div className="flex-1 flex flex-col overflow-hidden">
            <h3 className="text-sm font-medium mb-3">
              Select from Library ({selectedDocIds.length} selected)
            </h3>
            <ScrollArea className="flex-1">
              {loading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-primary" />
                </div>
              ) : documents.length === 0 ? (
                <div className="text-center py-8 text-sm text-muted-foreground">
                  No documents yet. Upload one above!
                </div>
              ) : (
                <div className="space-y-2">
                  {documents.map((doc) => (
                    <button
                      key={doc.id}
                      onClick={() => toggleDocument(doc.id)}
                      className={cn(
                        "w-full flex items-start gap-3 p-3 rounded-lg border transition-colors text-left",
                        selectedDocIds.includes(doc.id)
                          ? "border-primary bg-primary/5"
                          : "border-border hover:bg-accent"
                      )}
                    >
                      <div className="shrink-0 mt-0.5">
                        {getFileIcon(doc.file_type)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{doc.title}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-xs text-muted-foreground">
                            {formatFileSize(doc.file_size)}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {doc.category}
                          </span>
                          {doc.is_processed ? (
                            <span className="text-xs text-green-600">✓ Processed</span>
                          ) : (
                            <span className="text-xs text-yellow-600">⏳ Processing...</span>
                          )}
                        </div>
                      </div>
                      {selectedDocIds.includes(doc.id) && (
                        <div className="shrink-0 mt-0.5">
                          <div className="h-5 w-5 rounded-full bg-primary flex items-center justify-center">
                            <span className="text-xs text-primary-foreground">✓</span>
                          </div>
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </ScrollArea>
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-4 border-t">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={() => onOpenChange(false)}>
            Done ({selectedDocIds.length} selected)
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
