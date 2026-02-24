// ============================================
// Document Hooks
// ============================================
import { useState, useEffect } from 'react'
import { documentService, type DocumentUploadParams } from '@/services/document.service'
import type { Document } from '@/types/api'

export const useDocuments = (autoFetch = true) => {
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchDocuments = async (skip = 0, limit = 100) => {
    setLoading(true)
    setError(null)
    try {
      const data = await documentService.listDocuments(skip, limit)
      setDocuments(data)
      return data
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to fetch documents'
      setError(errorMessage)
      throw err
    } finally {
      setLoading(false)
    }
  }

  const uploadDocument = async (params: DocumentUploadParams) => {
    setError(null)
    try {
      const newDoc = await documentService.uploadDocument(params)
      setDocuments(prev => [newDoc, ...prev])
      return newDoc
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to upload document'
      setError(errorMessage)
      throw err
    }
  }

  const deleteDocument = async (documentId: string) => {
    setError(null)
    try {
      await documentService.deleteDocument(documentId)
      setDocuments(prev => prev.filter(doc => doc.id !== documentId))
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to delete document'
      setError(errorMessage)
      throw err
    }
  }

  const updateDocument = async (
    documentId: string,
    data: { title?: string; category?: string; tags?: string[] }
  ) => {
    setError(null)
    try {
      const updated = await documentService.updateDocument(documentId, data)
      setDocuments(prev =>
        prev.map(doc => (doc.id === documentId ? updated : doc))
      )
      return updated
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to update document'
      setError(errorMessage)
      throw err
    }
  }

  useEffect(() => {
    if (autoFetch) {
      fetchDocuments()
    }
  }, [autoFetch])

  return {
    documents,
    loading,
    error,
    fetchDocuments,
    uploadDocument,
    deleteDocument,
    updateDocument,
    refetch: fetchDocuments,
  }
}

// Hook for single document
export const useDocument = (documentId: string | null) => {
  const [document, setDocument] = useState<Document | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchDocument = async () => {
    if (!documentId) return
    
    setLoading(true)
    setError(null)
    try {
      const data = await documentService.getDocument(documentId)
      setDocument(data)
      return data
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to fetch document'
      setError(errorMessage)
      throw err
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (documentId) {
      fetchDocument()
    }
  }, [documentId])

  return {
    document,
    loading,
    error,
    refetch: fetchDocument,
  }
}

// Hook for shared documents
export const useSharedDocuments = (autoFetch = true) => {
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchSharedDocuments = async (skip = 0, limit = 100) => {
    setLoading(true)
    setError(null)
    try {
      const data = await documentService.listSharedDocuments(skip, limit)
      setDocuments(data)
      return data
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to fetch shared documents'
      setError(errorMessage)
      throw err
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (autoFetch) {
      fetchSharedDocuments()
    }
  }, [autoFetch])

  return {
    documents,
    loading,
    error,
    fetchSharedDocuments,
    refetch: fetchSharedDocuments,
  }
}
