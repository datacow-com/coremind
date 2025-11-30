import { useState, useRef, useEffect } from 'react'
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
  const [topK, setTopK] = useState<number>(5)
  const [streaming, setStreaming] = useState<boolean>(true)
  const [phase, setPhase] = useState<string>('idle')
  const [phaseHistory, setPhaseHistory] = useState<string[]>([])
  const [streamError, setStreamError] = useState<string | null>(null)
  const [vectorWeight, setVectorWeight] = useState<number>(0.6)
  const [keywordWeight, setKeywordWeight] = useState<number>(0.4)
  const [webSearchEnabled, setWebSearchEnabled] = useState<boolean>(true)
  const [requestId, setRequestId] = useState<string | null>(null)
  const [genStats, setGenStats] = useState<{chars:number,words:number}|null>(null)
  const [fallbackMsg, setFallbackMsg] = useState<string | null>(null)
  const [retrievalCount, setRetrievalCount] = useState<number | null>(null)
  const [rerankAvg, setRerankAvg] = useState<number | null>(null)
  const [tokenRate, setTokenRate] = useState<{cps:number,wps:number}|null>(null)
  const [exportLinks, setExportLinks] = useState<Record<string, string>>({})
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

  useEffect(() => {
    const loadDocs = async () => {
      try {
        const r = await fetch('/api/documents')
        if (r.ok) {
          const data = await r.json()
          setDocuments(data.documents || [])
        }
      } catch (e) {
        // noop
      }
    }
    loadDocs()
  }, [])

  useEffect(() => {
    const loadDefaults = async () => {
      try {
        const token = await fetch('/api/auth/demo', { method: 'POST' }).then(r => r.ok ? r.json() : Promise.reject('auth failed')).then(d => d.access_token as string)
        const res = await fetch('/api/models/providers', { headers: { Authorization: `Bearer ${token}` } })
        if (res.ok) {
          const data = await res.json()
          const s = data.config?.settings
          if (s) {
            setVectorWeight(s.vector_weight ?? 0.6)
            setKeywordWeight(s.keyword_weight ?? 0.4)
            setWebSearchEnabled(s.web_search_enabled ?? true)
          }
        }
      } catch {}
    }
    loadDefaults()
  }, [])

  useEffect(() => {
    const onSettingsUpdate = (e: any) => {
      const d = e.detail || {}
      if (typeof d.vector_weight === 'number') setVectorWeight(d.vector_weight)
      if (typeof d.keyword_weight === 'number') setKeywordWeight(d.keyword_weight)
      if (typeof d.web_search_enabled === 'boolean') setWebSearchEnabled(d.web_search_enabled)
    }
    window.addEventListener('settings:update', onSettingsUpdate as any)
    return () => window.removeEventListener('settings:update', onSettingsUpdate as any)
  }, [])

  useEffect(() => {
    try {
      const saved = localStorage.getItem('omnirag_conversation_id')
      if (saved) setConversationId(saved)
    } catch {}
  }, [])

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
      if (streaming) {
        const assistantMessage: Message = { id: (Date.now() + 1).toString(), role: 'assistant', content: '' }
        setMessages(prev => [...prev, assistantMessage])
        const payload = {
          query: input,
          conversation_id: conversationId,
          document_ids: selectedDocument ? [selectedDocument] : undefined,
          top_k: topK,
          temperature: 0.7,
          vector_weight: vectorWeight,
          keyword_weight: keywordWeight,
          web_search_enabled: webSearchEnabled,
        }
        const maxAttempts = 3
        let attempt = 0
        let finished = false
        setStreamError(null)
        while (attempt < maxAttempts && !finished) {
          try {
            const response = await fetch('/api/chat/stream', {
              method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
            })
            const reader = response.body?.getReader()
            const decoder = new TextDecoder()
            let buf = ''
            while (true) {
              const r = await reader?.read()
              if (!r || r.done) break
              buf += decoder.decode(r.value, { stream: true })
              const parts = buf.split('\n\n')
              buf = parts.pop() || ''
              for (const chunk of parts) {
                const line = chunk.trim()
                if (!line.startsWith('data:')) continue
                const jsonStr = line.slice(5).trim()
                try {
                  const evt = JSON.parse(jsonStr)
                  if (evt.type === 'phase') {
                    const name = evt.name as string
                    const status = evt.status as string
                    setPhase(`${name}:${status}`)
                    setPhaseHistory(prev => [...prev, `${name}:${status}`].slice(-6))
                    if (name === 'generate' && status === 'end') {
                      const chars = parseInt(evt.gen_chars || 0)
                      const words = parseInt(evt.gen_words || 0)
                      setGenStats({ chars, words })
                      const cps = parseFloat(evt.chars_per_sec || 0)
                      const wps = parseFloat(evt.words_per_sec || 0)
                      setTokenRate({ cps, wps })
                    } else if (name === 'generate' && status === 'fallback') {
                      setFallbackMsg('Stream failed: fallback to non-stream response')
                    } else if (name === 'retrieve' && status === 'end') {
                      const cnt = parseInt(evt.count || 0)
                      setRetrievalCount(cnt)
                    } else if (name === 'rerank' && status === 'end') {
                      const avg = parseFloat(evt.avg_score || 0)
                      setRerankAvg(avg)
                    }
                  } else if (evt.type === 'answer' && evt.delta) {
                    setMessages(prev => prev.map(m => m.id === assistantMessage.id ? { ...m, content: (m.content || '') + evt.delta } : m))
                  } else if (evt.type === 'final') {
                    setConversationId(evt.conversation_id)
                    try { if (evt.conversation_id) localStorage.setItem('omnirag_conversation_id', evt.conversation_id) } catch {}
                    if (evt.sources && evt.sources.length > 0) {
                      const firstSource = evt.sources[0]
                      await loadPreviewForSource(firstSource)
                      setMessages(prev => prev.map(m => m.id === assistantMessage.id ? { ...m, sources: evt.sources } : m))
                    }
                    if (evt.answer) {
                      setMessages(prev => prev.map(m => m.id === assistantMessage.id ? { ...m, content: (m.content || '') + evt.answer } : m))
                    }
                    finished = true
                  } else if (evt.type === 'meta') {
                    if (evt.request_id) setRequestId(String(evt.request_id))
                  }
                } catch {}
              }
            }
            if (!finished) throw new Error('stream interrupted')
          } catch (e) {
            attempt++
            setStreamError(`Stream interrupted, retry ${attempt}/${maxAttempts}`)
            await new Promise(res => setTimeout(res, Math.pow(2, attempt) * 500))
          }
        }
      } else {
        const response = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: input,
            conversation_id: conversationId,
            document_ids: selectedDocument ? [selectedDocument] : undefined,
            top_k: topK,
            temperature: 0.7,
            vector_weight: vectorWeight,
            keyword_weight: keywordWeight,
            web_search_enabled: webSearchEnabled,
          })
        })
        if (!response.ok) throw new Error('Failed to get response')
        const data = await response.json()
        const assistantMessage: Message = { id: (Date.now() + 1).toString(), role: 'assistant', content: data.answer, sources: data.sources }
        setMessages(prev => [...prev, assistantMessage])
        setConversationId(data.conversation_id)
        try { if (data.conversation_id) localStorage.setItem('omnirag_conversation_id', data.conversation_id) } catch {}
        if (data.sources && data.sources.length > 0) {
          const firstSource = data.sources[0]
          await loadPreviewForSource(firstSource)
        }
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

  const startNewChat = () => {
    setMessages([])
    setConversationId(null)
    try {
      localStorage.removeItem('omnirag_conversation_id')
    } catch {}
  }

  const clearPreview = () => {
    setPdfPreview(null)
    setPreviewImg(null)
    setPreviewBBoxes([])
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
                <button
                  onClick={startNewChat}
                  className="px-3 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
                >New Chat</button>
                <button
                  onClick={async () => {
                    try {
                      const token = await fetch('/api/auth/demo', { method: 'POST' }).then(r => r.ok ? r.json() : Promise.reject('auth failed')).then(d => d.access_token as string)
                      const res = await fetch('/api/models/providers', { headers: { Authorization: `Bearer ${token}` } })
                      if (res.ok) {
                        const data = await res.json()
                        const s = data.config?.settings
                        if (s) {
                          setVectorWeight(s.vector_weight ?? 0.6)
                          setKeywordWeight(s.keyword_weight ?? 0.4)
                          setWebSearchEnabled(s.web_search_enabled ?? true)
                        }
                      }
                    } catch {}
                  }}
                  className="px-3 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
                >Reset Defaults</button>
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

              <div className="flex items-center space-x-2 text-sm">
                <label className="text-gray-600">Top K</label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={topK}
                  onChange={(e) => setTopK(Math.max(1, Math.min(10, parseInt(e.target.value || '5'))))}
                  className="w-16 border border-gray-300 rounded px-2 py-1"
                />
              </div>

              <div className="flex items-center space-x-2 text-sm">
                <label className="text-gray-600">Vector</label>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.1}
                  value={vectorWeight}
                  onChange={(e) => setVectorWeight(Math.max(0, Math.min(1, parseFloat(e.target.value || '0.6'))))}
                  className="w-16 border border-gray-300 rounded px-2 py-1"
                />
                <label className="text-gray-600">Keyword</label>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.1}
                  value={keywordWeight}
                  onChange={(e) => setKeywordWeight(Math.max(0, Math.min(1, parseFloat(e.target.value || '0.4'))))}
                  className="w-16 border border-gray-300 rounded px-2 py-1"
                />
              </div>

              <div className="flex items-center space-x-2 text-sm">
                <label className="text-gray-600">Stream</label>
                <input type="checkbox" checked={streaming} onChange={(e) => setStreaming(e.target.checked)} />
              </div>
              <div className="flex items-center space-x-2 text-sm">
                <label className="text-gray-600">WebSearch</label>
                <input type="checkbox" checked={webSearchEnabled} onChange={(e) => setWebSearchEnabled(e.target.checked)} />
              </div>
              {streaming && (
                <div className="text-xs text-gray-600">
                  <span className="mr-2">Phase: {phase}</span>
                  {streamError && <span className="text-red-600">{streamError}</span>}
                  {phaseHistory.length > 0 && (
                    <span className="ml-2 text-gray-400">[{phaseHistory.join(' > ')}]</span>
                  )}
                  {requestId && (
                    <span className="ml-2 text-gray-400">req: {requestId}</span>
                  )}
                  {genStats && (
                    <span className="ml-2 text-gray-400">gen: {genStats.chars} chars / {genStats.words} words</span>
                  )}
                  {tokenRate && (
                    <span className="ml-2 text-gray-400">rate: {tokenRate.cps.toFixed(1)} c/s / {tokenRate.wps.toFixed(1)} w/s</span>
                  )}
                  {retrievalCount !== null && (
                    <span className="ml-2 text-gray-400">hits: {retrievalCount}</span>
                  )}
                  {rerankAvg !== null && (
                    <span className="ml-2 text-gray-400">avg: {rerankAvg.toFixed(3)}</span>
                  )}
                  {fallbackMsg && (
                    <span className="ml-2 text-yellow-600">{fallbackMsg}</span>
                  )}
                </div>
              )}
              
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
                      <div className="mt-2 flex items-center space-x-2">
                        <button className="text-xs px-2 py-1 border rounded hover:bg-gray-50" onClick={() => handleExportTables(message)}>Export Tables CSV</button>
                        {exportLinks[message.id] && (
                          <a className="text-xs text-blue-600 hover:underline" href={exportLinks[message.id]} target="_blank" rel="noreferrer">Download CSV</a>
                        )}
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
        <div className="p-4 border-b flex items-center justify-between">
          <h3 className="font-semibold text-gray-800">PDF Preview</h3>
          <button onClick={clearPreview} className="text-xs px-2 py-1 border rounded hover:bg-gray-50">Clear</button>
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
  const handleExportTables = async (message: Message) => {
    try {
      const tables = (message.sources || [])
        .map(s => s.content || '')
        .filter(c => c.includes('|'))
      if (tables.length === 0) return
      const res = await fetch('/api/execute/export/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tables }) })
      if (!res.ok) return
      const data = await res.json()
      if (data.download_url) setExportLinks(prev => ({ ...prev, [message.id]: data.download_url }))
    } catch {}
  }
