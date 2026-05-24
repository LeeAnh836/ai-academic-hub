# Frontend

Frontend là giao diện web của JVB Final. Dự án dùng React + TypeScript + Vite và tổ chức theo mô hình component, hook và service để tách rõ UI, logic trạng thái và gọi API.

## Mục tiêu của thư mục này

- Cung cấp UI cho đăng nhập/đăng ký.
- Hiển thị dashboard, tài liệu, chat AI, nhóm, tin nhắn, hồ sơ và trang quản trị.
- Làm lớp tương tác với backend qua các service có token refresh.
- Xử lý hiển thị nội dung rich text, markdown, công thức, bảng và preview file.

## Cấu trúc chính

```text
frontend/
├── public/              # Tài nguyên tĩnh
├── src/
│   ├── components/     # Component tái sử dụng và các trang
│   ├── hooks/          # Custom hooks cho auth, chat, documents, groups
│   ├── lib/            # Helper/context
│   ├── services/       # Lớp gọi API
│   ├── types/          # Kiểu TypeScript dùng chung
│   ├── utils/          # Hàm tiện ích
│   ├── App.tsx         # Root component
│   ├── main.tsx        # Entry React
│   └── routes.tsx      # Khai báo route
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
├── eslint.config.js
└── README.md
```

## Các phần quan trọng trong `src/`

### `components/`

Nơi chứa toàn bộ UI chính:

- `pages/`: các trang như login, dashboard, documents, ai-chat, groups, messages, profile, settings, admin.
- `ui/`: component nền tảng kiểu shadcn/ui.
- `app-shell.tsx` và `app-sidebar.tsx`: khung ứng dụng và điều hướng.
- `markdown-message.tsx`: render nội dung chat markdown.
- `file-preview-modal.tsx`: preview tài liệu và file đính kèm.
- `theme-provider.tsx`: quản lý theme.

### `hooks/`

Các hook đóng gói logic trạng thái:

- `use-auth.ts`: đăng nhập, đăng ký, xác thực.
- `use-documents.ts`: tải lên và quản lý tài liệu.
- `use-chat.ts`: luồng chat, gửi câu hỏi, nhận trả lời.
- `use-groups.ts`: quản lý nhóm.
- `use-mobile.tsx`, `use-toast.ts`: tiện ích UI.

### `services/`

Lớp giao tiếp API:

- `api.ts`: client gốc, xử lý token và refresh.
- `auth.service.ts`: API auth.
- `document.service.ts`: API tài liệu.
- `chat.service.ts`: API chat.
- `group.service.ts`, `messaging.service.ts`, `user.service.ts`, `admin.service.ts`.

### `utils/`

Các hàm hỗ trợ như format, JWT, crop ảnh và user helpers.

## Tech stack

- React 19
- TypeScript
- Vite 7
- Tailwind CSS
- shadcn/ui + Radix UI
- React Router
- React Hook Form + Zod
- `react-markdown`, `remark-gfm`, `remark-math`, `rehype-katex`

## Scripts

```bash
npm run dev
npm run build
npm run preview
npm run lint
```

## Biến môi trường

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Chạy local

### Cách 1: Docker Compose

Từ thư mục gốc dự án:

```powershell
docker compose up -d
```

### Cách 2: chạy trực tiếp

```bash
npm install
npm run dev
```

Mặc định frontend chạy ở `http://localhost:5173`.

## Những gì giao diện đang hỗ trợ

- Đăng nhập/đăng ký và quản lý session.
- Upload và xem tài liệu.
- Chat AI theo ngữ cảnh tài liệu.
- Nhóm và nhắn tin.
- Trang hồ sơ và cài đặt.
- Trang admin khi có quyền phù hợp.

## Lưu ý khi phát triển

- Mọi request API nên đi qua lớp service thay vì gọi trực tiếp từ component.
- Khi thêm page mới, cập nhật cả route lẫn navigation.
- File preview và markdown rendering đã có các xử lý riêng cho nội dung dài, code block, công thức và bảng.
- Với production build, cần đảm bảo `VITE_API_BASE_URL` trỏ đúng backend thật.
