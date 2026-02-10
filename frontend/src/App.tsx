import { AppProvider } from "@/lib/app-context"
import { AppShell } from "@/components/app-shell"
import { ThemeProvider } from "@/components/theme-provider"

function App() {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      <AppProvider>
        <AppShell />
      </AppProvider>
    </ThemeProvider>
  )
}

export default App
