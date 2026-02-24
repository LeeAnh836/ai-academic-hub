// ============================================
// API Response Types
// ============================================

// Base Response Types
export interface MessageResponse {
  message: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

// ============================================
// User Types
// ============================================
export interface User {
  id: string
  email: string
  username: string
  full_name: string | null
  student_id: string | null
  role: "admin" | "user"
  is_active: boolean
  is_verified: boolean
  avatar_url: string | null
  created_at: string
  updated_at: string
}

export interface UserSettings {
  id: string
  user_id: string
  theme: string
  language: string
  notifications_enabled: boolean
  email_notifications: boolean
  two_factor_enabled: boolean
}

// ============================================
// Document Types
// ============================================
export interface Document {
  id: string
  user_id: string
  title: string
  file_name: string
  file_path: string
  file_size: number
  file_type: string
  category: string
  tags: string[]
  is_processed: boolean
  processing_status: string
  chunk_count: number
  created_at: string
  updated_at: string
}

export interface DocumentShare {
  id: string
  document_id: string
  shared_by: string
  shared_with: string | null
  group_id: string | null
  permission_level: string
  expires_at: string | null
  created_at: string
}

// ============================================
// Chat Types
// ============================================
export interface ChatSession {
  id: string
  user_id: string
  title: string
  session_type: string
  context_documents: string[]
  model_name: string
  message_count: number
  total_tokens: number
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: string
  session_id: string
  user_id: string
  role: "user" | "assistant" | "system"
  content: string
  retrieved_chunks: string[]  // Array of chunk IDs
  total_tokens: number
  confidence_score: number | null
  created_at: string
}

export interface ContextChunk {
  chunk_id: string
  document_id: string
  chunk_text: string
  chunk_index: number
  score: number
  file_name: string
  title?: string
}

export interface ChatAskResponse {
  session_id: string
  user_message: ChatMessage
  ai_message: ChatMessage
  contexts: ContextChunk[]
  processing_time: number
  model_used: string
}

// ============================================
// Group Types
// ============================================
export interface Group {
  id: string
  group_name: string
  group_type: string
  is_public: boolean
  description: string | null
  created_by: string
  member_count: number
  created_at: string
  updated_at: string
}

export interface GroupMember {
  id: string
  group_id: string
  user_id: string
  role: string
  joined_at: string
  user?: User
}

export interface GroupMessage {
  id: string
  group_id: string
  user_id: string
  content: string
  message_type: string
  attachments: any[]
  created_at: string
  user?: User
}

// ============================================
// Request Types
// ============================================
export interface RegisterRequest {
  email: string
  username: string
  password: string
  full_name?: string
  student_id: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface ChatAskRequest {
  question: string
  session_id?: string
  model_name?: string
  context_documents?: string[]
  use_rag?: boolean
}

export interface DocumentUploadRequest {
  file: File
  title?: string
  category?: string
  tags?: string[]
}

export interface GroupCreateRequest {
  group_name: string
  group_type: string
  is_public: boolean
  description?: string
}
