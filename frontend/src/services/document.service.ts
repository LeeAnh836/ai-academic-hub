// ============================================
// Document Service
// ============================================
import { api } from './api'
import type { Document, DocumentShare } from '@/types/api'

export interface DocumentUploadParams {
  file: File
  title?: string
  category?: string
  tags?: string[]
}

export const documentService = {
  // List user documents
  listDocuments: async (skip = 0, limit = 10): Promise<Document[]> => {
    return api.get<Document[]>(`/api/documents?skip=${skip}&limit=${limit}`)
  },

  // Upload document
  uploadDocument: async (params: DocumentUploadParams): Promise<Document> => {
    const formData = new FormData()
    formData.append('file', params.file)
    
    if (params.title) {
      formData.append('title', params.title)
    }
    if (params.category) {
      formData.append('category', params.category)
    }
    if (params.tags && params.tags.length > 0) {
      formData.append('tags', JSON.stringify(params.tags))
    }

    return api.post<Document>('/api/documents/upload', formData)
  },

  // Get document by ID
  getDocument: async (documentId: string): Promise<Document> => {
    return api.get<Document>(`/api/documents/${documentId}`)
  },

  // Download document
  downloadDocument: async (documentId: string): Promise<Blob> => {
    const response = await fetch(`/api/documents/${documentId}/download`, {
      headers: {
        Authorization: `Bearer ${localStorage.getItem('access_token')}`,
      },
    })
    
    if (!response.ok) {
      throw new Error('Download failed')
    }
    
    return response.blob()
  },

  // Update document
  updateDocument: async (
    documentId: string,
    data: { title?: string; category?: string; tags?: string[] }
  ): Promise<Document> => {
    return api.put<Document>(`/api/documents/${documentId}`, data)
  },

  // Delete document
  deleteDocument: async (documentId: string): Promise<{ message: string }> => {
    return api.delete(`/api/documents/${documentId}`)
  },

  // Share document
  shareDocument: async (
    documentId: string,
    data: {
      shared_with?: string
      group_id?: string
      permission_level: string
      expires_at?: string
    }
  ): Promise<DocumentShare> => {
    return api.post<DocumentShare>(`/api/documents/${documentId}/share`, data)
  },

  // List shared documents
  listSharedDocuments: async (skip = 0, limit = 10): Promise<Document[]> => {
    return api.get<Document[]>(`/api/documents/shared?skip=${skip}&limit=${limit}`)
  },

  // Get processing status
  getProcessingStatus: async (documentId: string): Promise<{
    is_processed: boolean
    processing_status: string
    chunk_count: number
  }> => {
    return api.get(`/api/documents/${documentId}/status`)
  },
}
