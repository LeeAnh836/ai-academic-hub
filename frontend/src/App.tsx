import { BrowserRouter } from "react-router-dom"
import { AppProvider } from "@/lib/app-context"
import { AppShell } from "@/components/app-shell"
import { ThemeProvider } from "@/components/theme-provider"

function App() {
  return (
    <BrowserRouter>
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
        <AppProvider>
          <AppShell />
        </AppProvider>
      </ThemeProvider>
    </BrowserRouter>
  )
}

export default App
