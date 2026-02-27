import { useState } from "react"
import { cn } from "@/lib/utils"
import { useApp } from "@/lib/app-context"
import { AppSidebar } from "./app-sidebar"
import { MobileHeader, MobileBottomNav } from "./mobile-nav"
import { AppRoutes } from "@/routes"

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false)
  const { isAuthenticated } = useApp()

  return (
    <div className="flex min-h-screen bg-background">
      {/* Desktop sidebar - only show when authenticated */}
      {isAuthenticated && (
        <div className="hidden md:block">
          <AppSidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
        </div>
      )}

      {/* Main content */}
      <main
        className={cn(
          "flex-1 transition-all duration-300",
          isAuthenticated && "md:ml-[240px]",
          isAuthenticated && collapsed && "md:ml-[68px]",
          isAuthenticated && "pb-16 md:pb-0"
        )}
      >
        {/* Mobile header - only show when authenticated */}
        {isAuthenticated && <MobileHeader />}

        {/* Page content */}
        <div className="h-full">
          <AppRoutes />
        </div>
      </main>

      {/* Mobile bottom nav - only show when authenticated */}
      {isAuthenticated && <MobileBottomNav />}
    </div>
  )
}
