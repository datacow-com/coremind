import React, { useState, useRef, useEffect } from 'react'
import { Send, Upload, FileText } from 'lucide-react'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Array<{
    chunk_id: string
    content: string
    score: number
    document_name: string
    page_number: number
  }>
}

interface Document {
  id: string
  filename: string
  processing_status: string
  processed_pages: number
  total_pages: number
}

const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [documents, setDocuments] = useState<Document[]>([])
  const [selectedDocument, setSelectedDocument] = useState<string | null>(null)
  const [pdfPreview, setPdfPreview] = useState<string | null>(null)
  const [previewImg, setPreviewImg] = useState<string | null>(null)
  const [previewBBoxes, setPreviewBBoxes] = useState<Array<{x:number,y:number,w:number,h:number}>>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const extractDocumentId = (documentName: string): string | null => {
    try {
      const base = documentName.split('/').pop() || documentName
      const id = base.replace('.pdf','')
      return id
    } catch {
      return null
    }
  }

  const loadPreviewForSource = async (source: { document_name: string, page_number: number }) => {
    const docId = extractDocumentId(source.document_name)
    if (!docId || !source.page_number) {
      setPdfPreview(`Document: ${source.document_name}, Page: ${source.page_number}`)
      setPreviewImg(null)
      setPreviewBBoxes([])
      return
    }
    try {
      const res = await fetch(`/api/documents/${docId}/pages/${source.page_number}`)
      if (res.ok) {
        const data = await res.json()
        setPdfPreview(`Document: ${source.document_name}, Page: ${source.page_number}`)
        setPreviewImg(`data:image/png;base64,${data.image_base64}`)
        setPreviewBBoxes(data.bboxes || [])
      } else {
        setPdfPreview(`Document: ${source.document_name}, Page: ${source.page_number}`)
        setPreviewImg(null)
        setPreviewBBoxes([])
      }
    } catch {
      setPdfPreview(`Document: ${source.document_name}, Page: ${source.page_number}`)
      setPreviewImg(null)
      setPreviewBBoxes([])
    }
  }

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSendMessage = async () => {
    if (!input.trim() || isLoading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: input,
          conversation_id: conversationId,
          document_ids: selectedDocument ? [selectedDocument] : undefined,
          top_k: 5,
          temperature: 0.7
        })
      })

      if (!response.ok) {
        throw new Error('Failed to get response')
      }

      const data = await response.json()
      
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.answer,
        sources: data.sources
      }

      setMessages(prev => [...prev, assistantMessage])
      setConversationId(data.conversation_id)
      
      // Auto preview first source
      if (data.sources && data.sources.length > 0) {
        const firstSource = data.sources[0]
        await loadPreviewForSource(firstSource)
      }
      
    } catch (error) {
      console.error('Error sending message:', error)
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your request. Please try again.'
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch('/api/documents/upload', {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        throw new Error('Failed to upload file')
      }

      const data = await response.json()
      
      // Add a new document to the list
      const newDocument: Document = {
        id: data.document_id,
        filename: data.filename,
        processing_status: 'processing',
        processed_pages: 0,
        total_pages: 0
      }
      
      setDocuments(prev => [...prev, newDocument])
      
      // Poll for status updates
      const pollStatus = async () => {
        try {
          const statusResponse = await fetch(`/api/documents/${data.document_id}/status`)
          if (statusResponse.ok) {
            const statusData = await statusResponse.json()
            setDocuments(prev => prev.map(doc => 
              doc.id === data.document_id 
                ? { ...doc, processing_status: statusData.processing_status, processed_pages: statusData.processed_pages, total_pages: statusData.total_pages }
                : doc
            ))
            
            if (statusData.processing_status === 'completed' || statusData.processing_status === 'failed') {
              clearInterval(interval)
            }
          }
        } catch (error) {
          console.error('Error polling status:', error)
          clearInterval(interval)
        }
      }
      
      const interval = setInterval(pollStatus, 2000)
      
    } catch (error) {
      console.error('Error uploading file:', error)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  return (
    <div className="flex h-full">
      {/* Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="bg-white border-b px-6 py-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-800">Chat with your documents</h2>
            <div className="flex items-center space-x-3">
              <select
                value={selectedDocument || ''}
                onChange={(e) => setSelectedDocument(e.target.value || null)}
                className="px-3 py-2 border border-gray-300 rounded-md text-sm"
              >
                <option value="">All documents</option>
                {documents.map(doc => (
                  <option key={doc.id} value={doc.id}>
                    {doc.filename} ({doc.processing_status})
                  </option>
                ))}
              </select>
              
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                onChange={handleFileUpload}
                className="hidden"
              />
              
              <button
                onClick={() => fileInputRef.current?.click()}
                className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
              >
                <Upload className="h-4 w-4" />
                <span>Upload PDF</span>
              </button>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 ? (
            <div className="text-center text-gray-500 mt-20">
              <FileText className="h-16 w-16 mx-auto mb-4 text-gray-300" />
              <h3 className="text-lg font-medium mb-2">Welcome to OmniRAG</h3>
              <p className="text-sm">Upload a PDF document and start asking questions about its content.</p>
              <p className="text-xs mt-2">The AI will use visual parsing to understand your documents.</p>
            </div>
          ) : (
            messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-3xl rounded-lg px-4 py-2 ${
                    message.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-white border border-gray-200 text-gray-800'
                  }`}
                >
                  <div className="whitespace-pre-wrap">{message.content}</div>
                  
                  {message.sources && message.sources.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-200">
                      <p className="text-xs text-gray-500 mb-2">Sources:</p>
                      <div className="space-y-1">
                        {message.sources.map((source, index) => (
                          <button
                            key={source.chunk_id}
                            className="text-xs text-blue-600 hover:underline"
                            onClick={() => loadPreviewForSource(source)}
                          >
                            <span className="font-medium">[{index + 1}]</span> {source.document_name} (p. {source.page_number})
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
          
          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-white border border-gray-200 rounded-lg px-4 py-2">
                <div className="flex space-x-2">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="bg-white border-t px-6 py-4">
          <div className="flex space-x-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask a question about your documents..."
              className="flex-1 resize-none border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              rows={2}
              disabled={isLoading}
            />
            <button
              onClick={handleSendMessage}
              disabled={!input.trim() || isLoading}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Send className="h-5 w-5" />
            </button>
          </div>
        </div>
      </div>

      {/* PDF Preview Panel */}
      <div className="w-96 bg-white border-l">
        <div className="p-4 border-b">
          <h3 className="font-semibold text-gray-800">PDF Preview</h3>
        </div>
        <div className="p-4">
          {pdfPreview ? (
            <div className="text-sm text-gray-600">
              <p className="mb-2">{pdfPreview}</p>
              {previewImg ? (
                <div className="relative border rounded overflow-hidden">
                  <img src={previewImg} alt="preview" className="max-w-full" />
                  {previewBBoxes.map((b, i) => (
                    <div
                      key={i}
                      style={{
                        position: 'absolute',
                        left: b.x,
                        top: b.y,
                        width: b.w,
                        height: b.h,
                        border: '2px solid rgba(59,130,246,0.8)',
                        boxShadow: '0 0 0 2px rgba(59,130,246,0.3) inset'
                      }}
                    />
                  ))}
                </div>
              ) : (
                <div className="mt-4 p-4 bg-gray-100 rounded-lg">
                  <p className="text-xs text-gray-500">Preview unavailable</p>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center text-gray-500">
              <FileText className="h-12 w-12 mx-auto mb-3 text-gray-300" />
              <p className="text-sm">PDF preview will appear here when sources are referenced</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default ChatPage
