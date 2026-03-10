import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Loader2 } from "lucide-react"
import { useAuth } from "@/hooks/use-auth"
import { useApp } from "@/lib/app-context"
import { useTranslation } from "@/lib/i18n"

export function LoginPage() {
  const [isLogin, setIsLogin] = useState(true)
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [username, setUsername] = useState("")
  const [fullName, setFullName] = useState("")
  const [studentId, setStudentId] = useState("")
  
  const { login, register, loading, error } = useAuth()
  const { setUser, refreshUser } = useApp()
  const { t } = useTranslation()

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const result = await login({ email, password })
      setUser(result.user)
      await refreshUser()
    } catch (err) {
      console.error("Login failed:", err)
    }
  }

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // Validate student ID
    if (studentId.length !== 8) {
      return
    }
    
    try {
      await register({
        email,
        username,
        password,
        full_name: fullName || undefined,
        student_id: studentId,
      })
      // After successful registration, switch to login
      setIsLogin(true)
      setPassword("")
    } catch (err) {
      console.error("Register failed:", err)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-background via-secondary/20 to-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-bold text-center">
            {isLogin ? t("auth.welcomeBack") : t("auth.createAccount")}
          </CardTitle>
          <CardDescription className="text-center">
            {isLogin
              ? t("auth.loginDesc")
              : t("auth.registerDesc")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <form onSubmit={isLogin ? handleLogin : handleRegister} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">{t("auth.email")}</Label>
              <Input
                id="email"
                type="email"
                placeholder={t("auth.emailPlaceholder")}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={loading}
              />
            </div>

            {!isLogin && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="username">{t("auth.username")}</Label>
                  <Input
                    id="username"
                    type="text"
                    placeholder={t("auth.usernamePlaceholder")}
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                    disabled={loading}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="fullName">{t("auth.fullNameOptional")}</Label>
                  <Input
                    id="fullName"
                    type="text"
                    placeholder={t("auth.fullNamePlaceholder")}
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    disabled={loading}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="studentId">{t("auth.studentId")}</Label>
                  <Input
                    id="studentId"
                    type="text"
                    placeholder={t("auth.studentIdPlaceholder")}
                    value={studentId}
                    onChange={(e) => setStudentId(e.target.value)}
                    minLength={8}
                    maxLength={8}
                    required
                    disabled={loading}
                  />
                  {studentId && studentId.length !== 8 && (
                    <p className="text-sm text-destructive">{t("auth.studentIdError")}</p>
                  )}
                </div>
              </>
            )}

            <div className="space-y-2">
              <Label htmlFor="password">{t("auth.password")}</Label>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                disabled={loading}
              />
            </div>

            <Button type="submit" className="w-full" disabled={loading}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isLogin ? t("auth.signIn") : t("auth.signUp")}
            </Button>
          </form>

          <div className="mt-4 text-center text-sm">
            {isLogin ? (
              <p className="text-muted-foreground">
                {t("auth.noAccount")}{" "}
                <button
                  type="button"
                  onClick={() => setIsLogin(false)}
                  className="text-primary hover:underline font-medium"
                  disabled={loading}
                >
                  {t("auth.signUpLink")}
                </button>
              </p>
            ) : (
              <p className="text-muted-foreground">
                {t("auth.hasAccount")}{" "}
                <button
                  type="button"
                  onClick={() => setIsLogin(true)}
                  className="text-primary hover:underline font-medium"
                  disabled={loading}
                >
                  {t("auth.signInLink")}
                </button>
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
