import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { MessageSquare, FileText, Settings, Database, Search } from 'lucide-react'

interface LayoutProps {
  children: React.ReactNode
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const location = useLocation()

  const navigation = [
    { name: 'Chat', href: '/', icon: MessageSquare },
    { name: 'Documents', href: '/documents', icon: FileText },
    { name: 'Vector Store', href: '/vector-store', icon: Database },
    { name: 'Settings', href: '/settings', icon: Settings },
  ]

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <div className="w-64 bg-white shadow-sm">
        <div className="p-6">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
              <Search className="h-5 w-5 text-white" />
            </div>
            <h1 className="text-xl font-bold text-gray-900">OmniRAG</h1>
          </div>
        </div>
        
        <nav className="mt-6">
          <ul className="space-y-2 px-3">
            {navigation.map((item) => {
              const Icon = item.icon
              const isActive = location.pathname === item.href
              
              return (
                <li key={item.name}>
                  <Link
                    to={item.href}
                    className={`flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-blue-50 text-blue-700 border-r-2 border-blue-700'
                        : 'text-gray-700 hover:bg-gray-50 hover:text-gray-900'
                    }`}
                  >
                    <Icon className="h-5 w-5" />
                    <span>{item.name}</span>
                  </Link>
                </li>
              )
            })}
          </ul>
        </nav>
        
        <div className="mt-auto p-6">
          <div className="text-xs text-gray-500">
            <p>Powered by LangGraph</p>
            <p className="mt-1">Visual PDF Parsing</p>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {children}
      </div>
    </div>
  )
}

export default Layout