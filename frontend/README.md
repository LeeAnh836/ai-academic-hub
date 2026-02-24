# Frontend - JVB Learning Platform

React + TypeScript + Vite frontend for JVB Learning Platform.

## 🚀 Quick Start

### Option 1: Docker (Recommended)

From project root:
```bash
docker compose up -d
```

Access at: http://localhost:5173

### Option 2: Local Development

```bash
# Install dependencies
npm install

# Copy .env.example to .env
cp .env.example .env

# Start dev server
npm run dev
```

Access at: http://localhost:5173

## 🛠️ Tech Stack

- **Framework:** React 19
- **Build Tool:** Vite 7  
- **Language:** TypeScript
- **Styling:** Tailwind CSS
- **UI Components:** shadcn/ui (Radix UI)
- **State Management:** React Context API
- **HTTP Client:** Fetch API with auto token refresh

## 📁 Project Structure

```
src/
├── components/      # UI Components
│   ├── pages/      # Page components (Login, Dashboard, etc.)
│   └── ui/         # Reusable UI components (shadcn/ui)
├── hooks/          # Custom React hooks
│   ├── use-auth.ts        # Authentication hooks
│   ├── use-documents.ts   # Document management
│   ├── use-chat.ts        # Chat functionality
│   └── use-groups.ts      # Group management
├── services/       # API service layer
│   ├── api.ts             # Base API client
│   ├── auth.service.ts    # Auth APIs
│   ├── document.service.ts # Document APIs
│   ├── chat.service.ts    # Chat APIs
│   └── group.service.ts   # Group APIs
├── types/          # TypeScript types
├── lib/            # Utilities & contexts
└── App.tsx         # Main app component
```

## 🔧 Available Scripts

```bash
npm run dev      # Start dev server (http://localhost:5173)
npm run build    # Build for production
npm run preview  # Preview production build
npm run lint     # Run ESLint
```

## 🌐 Environment Variables

Create a `.env` file:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## 📚 Key Features

- ✅ Authentication (Login/Register with JWT)
- ✅ Auto token refresh
- ✅ Document upload & management
- ✅ AI Chat with RAG
- ✅ Group management
- ✅ Responsive design (mobile-friendly)
- ✅ Dark/Light theme support
- ✅ Real-time form validation

## 🐳 Docker

The frontend is containerized and runs with Docker Compose.

**Dockerfile features:**
- Node.js 20 Alpine
- Hot reload enabled (file watching with polling)
- Volume mounting for development
- Exposed on port 5173

**Docker commands:**
```bash
# Build and start
docker compose up -d frontend

# View logs
docker compose logs -f frontend

# Restart
docker compose restart frontend

# Rebuild
docker compose up -d --build frontend
```

## 🔥 Development Tips

### Hot Reload
Vite HMR (Hot Module Replacement) works automatically. Changes are reflected instantly in the browser.

### API Integration
All API calls go through the `api.ts` service which handles:
- Automatic Bearer token injection
- Token refresh on 401 errors
- Request queueing during token refresh
- Error handling

### Adding New Pages
1. Create component in `src/components/pages/`
2. Add route in `app-shell.tsx`
3. Add navigation item in `app-sidebar.tsx`

### Using API Services
```typescript
import { useDocuments } from '@/hooks/use-documents'

function MyComponent() {
  const { documents, loading, uploadDocument } = useDocuments()
  
  // Use documents, uploadDocument, etc.
}
```

## 📖 Documentation

- [INTEGRATION_REPORT.md](../INTEGRATION_REPORT.md) - Frontend-Backend integration details
- [INTEGRATION_GUIDE.md](../INTEGRATION_GUIDE.md) - API usage guide

---

## Original Vite Template Info

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) (or [oxc](https://oxc.rs) when used in [rolldown-vite](https://vite.dev/guide/rolldown)) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## React Compiler

The React Compiler is currently not compatible with SWC. See [this issue](https://github.com/vitejs/vite-plugin-react/issues/428) for tracking the progress.

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```
