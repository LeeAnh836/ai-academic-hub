import { useState } from "react"
import { useTheme } from "next-themes"
import { User, Mail, Lock, Camera, Moon, Sun, Eye, EyeOff, Save, Award as IdCard } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { useApp } from "@/lib/app-context"
import { useTranslation } from "@/lib/i18n"
import { getUserInitials, getUserDisplayName, getRoleLabel, formatStudentId } from "@/utils/user.utils"
import { useCurrentUser } from "@/hooks/use-auth"

export function ProfilePage() {
  const { user } = useApp()
  const { t } = useTranslation()
  const { updateUser } = useCurrentUser()
  const { theme, setTheme } = useTheme()
  const [showPassword, setShowPassword] = useState(false)
  const [darkMode, setDarkMode] = useState(theme === "dark")
  const [fullName, setFullName] = useState(user?.full_name || "")
  const [isUpdating, setIsUpdating] = useState(false)
  
  if (!user) return null

  const handleUpdateProfile = async () => {
    setIsUpdating(true)
    try {
      await updateUser({ full_name: fullName })
    } catch (error) {
      console.error("Failed to update profile:", error)
    } finally {
      setIsUpdating(false)
    }
  }

  const toggleTheme = (checked: boolean) => {
    setDarkMode(checked)
    setTheme(checked ? "dark" : "light") // persist via next-themes → localStorage
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-4 md:p-6 lg:p-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">{t("profile.title")}</h1>
        <p className="text-sm text-muted-foreground">{t("profile.subtitle")}</p>
      </div>

      {/* Avatar & Name */}
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center gap-6">
            <div className="relative">
              <Avatar className="h-20 w-20">
                <AvatarFallback className="bg-primary text-primary-foreground text-xl font-semibold">
                  {getUserInitials(user)}
                </AvatarFallback>
              </Avatar>
              <button className="absolute bottom-0 right-0 flex h-7 w-7 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-md transition-transform hover:scale-110">
                <Camera className="h-3.5 w-3.5" />
              </button>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-foreground">{getUserDisplayName(user, t)}</h2>
              <p className="text-sm text-muted-foreground">{user.email}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {getRoleLabel(user.role, t)} &middot; {formatStudentId(user.student_id, t)}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Personal Information */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base text-foreground">{t("profile.personalInfo")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label className="text-sm text-foreground">{t("profile.fullName")}</Label>
              <div className="relative mt-1">
                <User className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input 
                  value={fullName} 
                  onChange={(e) => setFullName(e.target.value)}
                  className="bg-secondary pl-9" 
                />
              </div>
            </div>
            <div>
              <Label className="text-sm text-foreground">{t("profile.email")}</Label>
              <div className="relative mt-1">
                <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input value={user.email} className="bg-secondary pl-9" readOnly />
              </div>
            </div>
          </div>
          <div>
            <Label className="text-sm text-foreground">{t("profile.studentId")}</Label>
            <div className="relative mt-1">
              <IdCard className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input value={formatStudentId(user.student_id, t)} className="bg-secondary pl-9" readOnly />
            </div>
          </div>
          <Button 
            className="gap-2 bg-primary text-primary-foreground hover:bg-primary/90"
            onClick={handleUpdateProfile}
            disabled={isUpdating}
          >
            <Save className="h-4 w-4" />
            {isUpdating ? t("common.saving") : t("common.save")}
          </Button>
        </CardContent>
      </Card>

      {/* Change Password */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base text-foreground">{t("profile.changePassword")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label className="text-sm text-foreground">{t("profile.currentPassword")}</Label>
            <div className="relative mt-1">
              <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                type={showPassword ? "text" : "password"}
                placeholder={t("profile.currentPasswordPlaceholder")}
                className="bg-secondary pl-9 pr-9"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label className="text-sm text-foreground">{t("profile.newPassword")}</Label>
              <div className="relative mt-1">
                <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input type="password" placeholder={t("profile.newPasswordPlaceholder")} className="bg-secondary pl-9" />
              </div>
            </div>
            <div>
              <Label className="text-sm text-foreground">{t("profile.confirmPassword")}</Label>
              <div className="relative mt-1">
                <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input type="password" placeholder={t("profile.confirmPasswordPlaceholder")} className="bg-secondary pl-9" />
              </div>
            </div>
          </div>
          <Button className="gap-2 bg-primary text-primary-foreground hover:bg-primary/90">
            <Lock className="h-4 w-4" />
            {t("profile.updatePassword")}
          </Button>
        </CardContent>
      </Card>

      {/* Preferences */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base text-foreground">{t("profile.preferences")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {darkMode ? <Moon className="h-5 w-5 text-muted-foreground" /> : <Sun className="h-5 w-5 text-muted-foreground" />}
              <div>
                <p className="text-sm font-medium text-foreground">{t("profile.darkMode")}</p>
                <p className="text-xs text-muted-foreground">{t("profile.darkModeDesc")}</p>
              </div>
            </div>
            <Switch checked={darkMode} onCheckedChange={toggleTheme} />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
