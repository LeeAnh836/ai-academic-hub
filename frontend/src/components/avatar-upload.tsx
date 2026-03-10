import { useState, useRef, useCallback } from "react"
import { Camera, Upload, X, Loader2 } from "lucide-react"
import Cropper from "react-easy-crop"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Slider } from "@/components/ui/slider"
import { useToast } from "@/hooks/use-toast"
import { useTranslation } from "@/lib/i18n"
import { userService } from "@/services/user.service"
import { getCroppedImg, type Area } from "@/utils/cropImage"

interface AvatarUploadProps {
  currentAvatarUrl?: string | null
  userInitials: string
  onAvatarUpdated?: (updatedUser: any) => void
}

export function AvatarUpload({ currentAvatarUrl, userInitials, onAvatarUpdated }: AvatarUploadProps) {
  const [open, setOpen] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [crop, setCrop] = useState({ x: 0, y: 0 })
  const [zoom, setZoom] = useState(1)
  const [croppedAreaPixels, setCroppedAreaPixels] = useState<Area | null>(null)
  const [avatarTimestamp, setAvatarTimestamp] = useState(Date.now())
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { toast } = useToast()
  const { t } = useTranslation()

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Validate file type
    if (!file.type.startsWith('image/')) {
      toast({
        title: t("avatar.invalidType"),
        description: t("avatar.invalidTypeDesc"),
        variant: "destructive",
      })
      return
    }

    // Validate file size (5MB)
    if (file.size > 5 * 1024 * 1024) {
      toast({
        title: t("avatar.tooLarge"),
        description: t("avatar.tooLargeDesc"),
        variant: "destructive",
      })
      return
    }

    // Create preview
    const reader = new FileReader()
    reader.onload = (e) => {
      setPreviewUrl(e.target?.result as string)
      setSelectedFile(file)
      setOpen(true)
    }
    reader.readAsDataURL(file)
  }

  const onCropComplete = useCallback((_croppedArea: Area, croppedAreaPixels: Area) => {
    setCroppedAreaPixels(croppedAreaPixels)
  }, [])

  const handleUpload = async () => {
    if (!selectedFile || !previewUrl || !croppedAreaPixels) return

    setUploading(true)
    try {
      // Create cropped image
      const croppedFile = await getCroppedImg(
        previewUrl,
        croppedAreaPixels,
        selectedFile.name
      )

      // Upload the cropped image
      const updatedUser = await userService.uploadAvatar(croppedFile)
      
      toast({
        title: t("common.success"),
        description: t("avatar.success"),
      })

      setAvatarTimestamp(Date.now())
      onAvatarUpdated?.(updatedUser)

      handleCancel()
    } catch (error: any) {
      toast({
        title: t("common.error"),
        description: error.message || t("avatar.failed"),
        variant: "destructive",
      })
    } finally {
      setUploading(false)
    }
  }

  const handleCancel = () => {
    setOpen(false)
    setPreviewUrl(null)
    setSelectedFile(null)
    setCrop({ x: 0, y: 0 })
    setZoom(1)
    setCroppedAreaPixels(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  return (
    <>
      <div className="relative">
        <Avatar className="h-20 w-20">
          {currentAvatarUrl && (
            <AvatarImage 
              src={`${currentAvatarUrl}?t=${avatarTimestamp}`} 
              alt="Avatar" 
            />
          )}
          <AvatarFallback className="bg-primary text-primary-foreground text-xl font-semibold">
            {userInitials}
          </AvatarFallback>
        </Avatar>
        <button
          onClick={() => fileInputRef.current?.click()}
          className="absolute bottom-0 right-0 flex h-7 w-7 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-md transition-transform hover:scale-110"
        >
          <Camera className="h-3.5 w-3.5" />
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={handleFileSelect}
        />
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t("avatar.uploadTitle")}</DialogTitle>
            <DialogDescription>
              {t("avatar.uploadDesc")}
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4">
            {previewUrl && (
              <>
                {/* Crop Area */}
                <div className="relative h-64 w-full bg-gray-100 rounded-lg overflow-hidden">
                  <Cropper
                    image={previewUrl}
                    crop={crop}
                    zoom={zoom}
                    aspect={1}
                    cropShape="round"
                    showGrid={false}
                    onCropChange={setCrop}
                    onZoomChange={setZoom}
                    onCropComplete={onCropComplete}
                  />
                </div>

                {/* Zoom Slider */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t("avatar.zoom")}</label>
                  <Slider
                    value={[zoom]}
                    min={1}
                    max={3}
                    step={0.1}
                    onValueChange={(value) => setZoom(value[0])}
                    className="w-full"
                  />
                </div>
              </>
            )}

            <div className="flex items-center gap-2">
              <Button
                onClick={handleUpload}
                disabled={!selectedFile || !croppedAreaPixels || uploading}
                className="flex-1"
              >
                {uploading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {t("avatar.uploading")}
                  </>
                ) : (
                  <>
                    <Upload className="mr-2 h-4 w-4" />
                    {t("common.upload")}
                  </>
                )}
              </Button>
              <Button
                onClick={handleCancel}
                variant="outline"
                disabled={uploading}
              >
                <X className="mr-2 h-4 w-4" />
                {t("common.cancel")}
              </Button>
            </div>

            <p className="text-xs text-muted-foreground text-center">
              {t("avatar.supportedFormats")}
            </p>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
