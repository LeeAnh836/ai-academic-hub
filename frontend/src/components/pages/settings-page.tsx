import { useState, useEffect } from "react"
import { useTheme } from "next-themes"
import { User, Mail, Lock, Moon, Sun, Bell, Globe, Eye, EyeOff, Save, Award as IdCard, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useApp } from "@/lib/app-context"
import { getUserInitials, getUserDisplayName, getRoleLabel, formatStudentId } from "@/utils/user.utils"
import { useCurrentUser } from "@/hooks/use-auth"
import { AvatarUpload } from "@/components/avatar-upload"
import { userService } from "@/services/user.service"
import { useToast } from "@/hooks/use-toast"
import { useTranslation } from "@/lib/i18n"

export function SettingsPage() {
  const { user, setUser } = useApp()
  const { updateUser } = useCurrentUser()
  const { toast } = useToast()
  const { setTheme: applyTheme } = useTheme()
  const { t, locale, setLocale } = useTranslation()
  
  // Profile state
  const [fullName, setFullName] = useState(user?.full_name || "")
  const [isUpdatingProfile, setIsUpdatingProfile] = useState(false)
  
  // Password state
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [isChangingPassword, setIsChangingPassword] = useState(false)
  
  // Settings state
  const [theme, setTheme] = useState<string>("light")
  const [notificationsEnabled, setNotificationsEnabled] = useState(true)
  const [emailNotifications, setEmailNotifications] = useState(true)
  const [isLoadingSettings, setIsLoadingSettings] = useState(true)
  const [isSavingSettings, setIsSavingSettings] = useState(false)

  // Load user settings
  useEffect(() => {
    const loadSettings = async () => {
      try {
        const settings = await userService.getUserSettings()
        setTheme(settings.theme)
        setNotificationsEnabled(settings.notifications_enabled)
        setEmailNotifications(settings.email_notifications)
        
        // Apply theme via next-themes (persists to localStorage)
        applyTheme(settings.theme)
      } catch (error) {
        console.error("Failed to load settings:", error)
      } finally {
        setIsLoadingSettings(false)
      }
    }
    
    loadSettings()
  }, [])
  
  if (!user) return null

  const handleUpdateProfile = async () => {
    if (!fullName.trim()) {
      toast({
        title: t("common.error"),
        description: t("settings.nameEmpty"),
        variant: "destructive",
      })
      return
    }

    setIsUpdatingProfile(true)
    try {
      await updateUser({ full_name: fullName })
      toast({
        title: t("common.success"),
        description: t("settings.profileUpdated"),
      })
    } catch (error: any) {
      toast({
        title: t("common.error"),
        description: error.message || t("settings.failedProfile"),
        variant: "destructive",
      })
    } finally {
      setIsUpdatingProfile(false)
    }
  }

  const handleChangePassword = async () => {
    if (!currentPassword || !newPassword || !confirmPassword) {
      toast({
        title: t("common.error"),
        description: t("settings.fillPasswords"),
        variant: "destructive",
      })
      return
    }

    if (newPassword !== confirmPassword) {
      toast({
        title: t("common.error"),
        description: t("settings.passwordsNoMatch"),
        variant: "destructive",
      })
      return
    }

    if (newPassword.length < 6) {
      toast({
        title: t("common.error"),
        description: t("settings.passwordMinLength"),
        variant: "destructive",
      })
      return
    }

    setIsChangingPassword(true)
    try {
      await userService.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      })
      
      toast({
        title: t("common.success"),
        description: t("settings.passwordChanged"),
      })
      
      // Clear fields
      setCurrentPassword("")
      setNewPassword("")
      setConfirmPassword("")
    } catch (error: any) {
      toast({
        title: t("common.error"),
        description: error.message || t("settings.failedPassword"),
        variant: "destructive",
      })
    } finally {
      setIsChangingPassword(false)
    }
  }

  const handleThemeChange = async (checked: boolean) => {
    const newTheme = checked ? "dark" : "light"
    setTheme(newTheme)
    applyTheme(newTheme) // persist via next-themes → localStorage
    
    // Save to backend
    try {
      await userService.updateUserSettings({ theme: newTheme })
    } catch (error) {
      console.error("Failed to save theme:", error)
    }
  }

  const handleSavePreferences = async () => {
    setIsSavingSettings(true)
    try {
      await userService.updateUserSettings({
        language: locale,
        notifications_enabled: notificationsEnabled,
        email_notifications: emailNotifications,
      })
      
      toast({
        title: t("common.success"),
        description: t("settings.preferencesSuccess"),
      })
    } catch (error: any) {
      toast({
        title: t("common.error"),
        description: error.message || t("settings.failedPreferences"),
        variant: "destructive",
      })
    } finally {
      setIsSavingSettings(false)
    }
  }

  const handleAvatarUpdated = (updatedUser: any) => {
    if (user) {
      setUser({ ...user, avatar_url: updatedUser.avatar_url, updated_at: updatedUser.updated_at })
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 md:p-6 lg:p-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">{t("settings.title")}</h1>
        <p className="text-sm text-muted-foreground">{t("settings.subtitle")}</p>
      </div>

      <Tabs defaultValue="profile" className="space-y-6">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="profile">{t("settings.profile")}</TabsTrigger>
          <TabsTrigger value="security">{t("settings.security")}</TabsTrigger>
          <TabsTrigger value="preferences">{t("settings.preferences")}</TabsTrigger>
        </TabsList>

        {/* Profile Tab */}
        <TabsContent value="profile" className="space-y-6">
          {/* Avatar & Basic Info */}
          <Card>
            <CardHeader>
              <CardTitle>{t("settings.profileInfo")}</CardTitle>
              <CardDescription>{t("settings.profileInfoDesc")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center gap-6">
                <AvatarUpload
                  currentAvatarUrl={user.avatar_url}
                  userInitials={getUserInitials(user)}
                  onAvatarUpdated={handleAvatarUpdated}
                />
                <div>
                  <h2 className="text-lg font-semibold text-foreground">{getUserDisplayName(user, t)}</h2>
                  <p className="text-sm text-muted-foreground">{user.email}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {getRoleLabel(user.role, t)} &middot; {formatStudentId(user.student_id, t)}
                  </p>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <Label className="text-sm text-foreground">{t("settings.fullName")}</Label>
                  <div className="relative mt-1">
                    <User className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input 
                      value={fullName} 
                      onChange={(e) => setFullName(e.target.value)}
                      className="bg-secondary pl-9" 
                      placeholder={t("settings.fullNamePlaceholder")}
                    />
                  </div>
                </div>
                <div>
                  <Label className="text-sm text-foreground flex items-center gap-2">
                    {t("settings.email")}
                    <span className="text-xs text-muted-foreground">{t("settings.readOnly")}</span>
                  </Label>
                  <div className="relative mt-1">
                    <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input value={user.email} className="bg-secondary/50 pl-9" readOnly />
                  </div>
                </div>
              </div>
              
              <div>
                <Label className="text-sm text-foreground flex items-center gap-2">
                  {t("settings.studentId")}
                  <span className="text-xs text-muted-foreground">{t("settings.readOnly")}</span>
                </Label>
                <div className="relative mt-1">
                  <IdCard className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input value={formatStudentId(user.student_id, t)} className="bg-secondary/50 pl-9" readOnly />
                </div>
              </div>
              
              <Button 
                className="gap-2 bg-primary text-primary-foreground hover:bg-primary/90"
                onClick={handleUpdateProfile}
                disabled={isUpdatingProfile || fullName === user.full_name}
              >
                {isUpdatingProfile ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    {t("common.saving")}
                  </>
                ) : (
                  <>
                    <Save className="h-4 w-4" />
                    {t("common.save")}
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Security Tab */}
        <TabsContent value="security" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>{t("settings.changePassword")}</CardTitle>
              <CardDescription>{t("settings.changePasswordDesc")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label className="text-sm text-foreground">{t("settings.currentPassword")}</Label>
                <div className="relative mt-1">
                  <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    type={showPassword ? "text" : "password"}
                    placeholder={t("settings.currentPasswordPlaceholder")}
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    className="bg-secondary pl-9 pr-9"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>
              
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <Label className="text-sm text-foreground">{t("settings.newPassword")}</Label>
                  <div className="relative mt-1">
                    <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input 
                      type="password" 
                      placeholder={t("settings.newPasswordPlaceholder")} 
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      className="bg-secondary pl-9" 
                    />
                  </div>
                </div>
                <div>
                  <Label className="text-sm text-foreground">{t("settings.confirmPassword")}</Label>
                  <div className="relative mt-1">
                    <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input 
                      type="password" 
                      placeholder={t("settings.confirmPasswordPlaceholder")} 
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className="bg-secondary pl-9" 
                    />
                  </div>
                </div>
              </div>
              
              <Button 
                className="gap-2 bg-primary text-primary-foreground hover:bg-primary/90"
                onClick={handleChangePassword}
                disabled={isChangingPassword}
              >
                {isChangingPassword ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    {t("settings.changing")}
                  </>
                ) : (
                  <>
                    <Lock className="h-4 w-4" />
                    {t("settings.updatePassword")}
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Preferences Tab */}
        <TabsContent value="preferences" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>{t("settings.appearance")}</CardTitle>
              <CardDescription>{t("settings.appearanceDesc")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {isLoadingSettings ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-8 w-8 animate-spin text-primary" />
                </div>
              ) : (
                <>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      {theme === "dark" ? (
                        <Moon className="h-5 w-5 text-muted-foreground" />
                      ) : (
                        <Sun className="h-5 w-5 text-muted-foreground" />
                      )}
                      <div>
                        <p className="text-sm font-medium text-foreground">{t("settings.darkMode")}</p>
                        <p className="text-xs text-muted-foreground">{t("settings.darkModeDesc")}</p>
                      </div>
                    </div>
                    <Switch 
                      checked={theme === "dark"} 
                      onCheckedChange={handleThemeChange} 
                    />
                  </div>

                  <div className="border-t border-border" />

                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Globe className="h-5 w-5 text-muted-foreground" />
                      <div>
                        <p className="text-sm font-medium text-foreground">{t("settings.language")}</p>
                        <p className="text-xs text-muted-foreground">{t("settings.languageDesc")}</p>
                      </div>
                    </div>
                    <select
                      value={locale}
                      onChange={(e) => setLocale(e.target.value as "en" | "vi")}
                      className="rounded-md border border-input bg-secondary px-3 py-2 text-sm"
                    >
                      <option value="en">{t("settings.english")}</option>
                      <option value="vi">{t("settings.vietnamese")}</option>
                    </select>
                  </div>

                  <div className="border-t border-border" />

                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Bell className="h-5 w-5 text-muted-foreground" />
                      <div>
                        <p className="text-sm font-medium text-foreground">{t("settings.pushNotifications")}</p>
                        <p className="text-xs text-muted-foreground">{t("settings.pushNotificationsDesc")}</p>
                      </div>
                    </div>
                    <Switch 
                      checked={notificationsEnabled} 
                      onCheckedChange={setNotificationsEnabled} 
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Mail className="h-5 w-5 text-muted-foreground" />
                      <div>
                        <p className="text-sm font-medium text-foreground">{t("settings.emailNotifications")}</p>
                        <p className="text-xs text-muted-foreground">{t("settings.emailNotificationsDesc")}</p>
                      </div>
                    </div>
                    <Switch 
                      checked={emailNotifications} 
                      onCheckedChange={setEmailNotifications} 
                    />
                  </div>

                  <Button 
                    className="gap-2 bg-primary text-primary-foreground hover:bg-primary/90"
                    onClick={handleSavePreferences}
                    disabled={isSavingSettings}
                  >
                    {isSavingSettings ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        {t("common.saving")}
                      </>
                    ) : (
                      <>
                        <Save className="h-4 w-4" />
                        {t("settings.savePreferences")}
                      </>
                    )}
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
