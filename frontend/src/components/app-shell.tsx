import { useState } from "react"
import { cn } from "@/lib/utils"
import { useApp } from "@/lib/app-context"
import { AppSidebar } from "./app-sidebar"
import { MobileHeader, MobileBottomNav } from "./mobile-nav"
import { DashboardPage } from "./pages/dashboard-page"
import { AIChatPage } from "./pages/ai-chat-page"
import { MessagesPage } from "./pages/messages-page"
import { DocumentsPage } from "./pages/documents-page"
import { GroupsPage } from "./pages/groups-page"
import { AdminPage } from "./pages/admin-page"
import { ProfilePage } from "./pages/profile-page"
import { LoginPage } from "./pages/login-page"
import { Loader2 } from "lucide-react"

export function AppShell() {
  const { currentPage, isAuthenticated, loading } = useApp()
  const [collapsed, setCollapsed] = useState(false)

  // Show loading spinner while checking authentication
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  // Show login page if not authenticated
  if (!isAuthenticated) {
    return <LoginPage />
  }

  const renderPage = () => {
    switch (currentPage) {
      case "dashboard":
        return <DashboardPage />
      case "ai-chat":
        return <AIChatPage />
      case "messages":
        return <MessagesPage />
      case "documents":
        return <DocumentsPage />
      case "groups":
        return <GroupsPage />
      case "admin":
        return <AdminPage />
      case "profile":
        return <ProfilePage />
      default:
        return <DashboardPage />
    }
  }

  return (
    <div className="flex min-h-screen bg-background">
      {/* Desktop sidebar */}
      <div className="hidden md:block">
        <AppSidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      </div>

      {/* Main content */}
      <main
        className={cn(
          "flex-1 transition-all duration-300",
          "md:ml-[240px]",
          collapsed && "md:ml-[68px]",
          "pb-16 md:pb-0"
        )}
      >
        {/* Mobile header */}
        <MobileHeader />

        {/* Page content */}
        <div className="h-full">{renderPage()}</div>
      </main>

      {/* Mobile bottom nav */}
      <MobileBottomNav />
    </div>
  )
}
