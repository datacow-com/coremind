// no default React import needed with react-jsx
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import ChatPage from './pages/ChatPage'
import DocumentsPage from './pages/DocumentsPage'
import VectorStorePage from './pages/VectorStorePage'
import SettingsPage from './pages/SettingsPage'

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/vector-store" element={<VectorStorePage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </Layout>
    </Router>
  )
}

export default App
