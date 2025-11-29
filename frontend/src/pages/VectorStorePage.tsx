import React, { useState, useEffect } from 'react'
import { Database, Search, Info, FileText } from 'lucide-react'

interface CollectionStats {
  name: string
  document_count: number
  chunk_count: number
  embedding_dimension: number
  distance_metric: string
}

interface SearchResult {
  chunk_id: string
  content: string
  score: number
  document_name: string
  page_number: number
}

const VectorStorePage: React.FC = () => {
  const [collections, setCollections] = useState<CollectionStats[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    fetchCollections()
  }, [])

  const fetchCollections = async () => {
    try {
      const response = await fetch('/api/vector-store/collections')
      if (response.ok) {
        const data = await response.json()
        setCollections(data.collections)
      }
    } catch (error) {
      console.error('Error fetching collections:', error)
    }
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) return

    setIsLoading(true)
    try {
      const response = await fetch('/api/vector-store/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: searchQuery,
          top_k: 10,
          collection_name: 'omnirag_documents'
        })
      })

      if (response.ok) {
        const data = await response.json()
        setSearchResults(data.results)
      }
    } catch (error) {
      console.error('Error searching vector store:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSearch()
    }
  }

  return (
    <div className="flex-1 flex flex-col">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-800">Vector Store</h2>
          <div className="flex items-center space-x-2 text-sm text-gray-500">
            <Info className="h-4 w-4" />
            <span>Milvus Vector Database</span>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {/* Collections Overview */}
        <div className="mb-8">
          <h3 className="text-md font-medium text-gray-900 mb-4">Collections</h3>
          <div className="grid gap-4">
            {collections.map((collection) => (
              <div key={collection.name} className="bg-white border rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <Database className="h-6 w-6 text-blue-600" />
                    <div>
                      <h4 className="font-medium text-gray-900">{collection.name}</h4>
                      <p className="text-sm text-gray-500">
                        {collection.document_count} documents • {collection.chunk_count} chunks
                      </p>
                    </div>
                  </div>
                  <div className="text-right text-sm text-gray-500">
                    <p>Dimension: {collection.embedding_dimension}</p>
                    <p>Metric: {collection.distance_metric}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Search Interface */}
        <div className="mb-8">
          <h3 className="text-md font-medium text-gray-900 mb-4">Vector Search</h3>
          <div className="bg-white border rounded-lg p-4">
            <div className="flex space-x-3 mb-4">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Enter search query..."
                className="flex-1 border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={handleSearch}
                disabled={isLoading || !searchQuery.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <Search className="h-4 w-4" />
              </button>
            </div>

            {searchResults.length > 0 && (
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-gray-700">Search Results ({searchResults.length})</h4>
                {searchResults.map((result) => (
                  <div key={result.chunk_id} className="border rounded-md p-3">
                    <div className="flex items-start justify-between mb-2">
                      <div className="text-sm font-medium text-gray-900">
                        {result.document_name} (p. {result.page_number})
                      </div>
                      <div className="text-xs text-gray-500">
                        Score: {result.score.toFixed(4)}
                      </div>
                    </div>
                    <p className="text-sm text-gray-700 line-clamp-3">{result.content}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white border rounded-lg p-4">
            <div className="flex items-center space-x-3">
              <Database className="h-8 w-8 text-blue-600" />
              <div>
                <p className="text-2xl font-bold text-gray-900">{collections.length}</p>
                <p className="text-sm text-gray-500">Collections</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white border rounded-lg p-4">
            <div className="flex items-center space-x-3">
              <FileText className="h-8 w-8 text-green-600" />
              <div>
                <p className="text-2xl font-bold text-gray-900">
                  {collections.reduce((sum, col) => sum + col.document_count, 0)}
                </p>
                <p className="text-sm text-gray-500">Documents</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white border rounded-lg p-4">
            <div className="flex items-center space-x-3">
              <Search className="h-8 w-8 text-purple-600" />
              <div>
                <p className="text-2xl font-bold text-gray-900">
                  {collections.reduce((sum, col) => sum + col.chunk_count, 0)}
                </p>
                <p className="text-sm text-gray-500">Chunks</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default VectorStorePage
