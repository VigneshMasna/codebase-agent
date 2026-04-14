import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/layout/Layout'
import Dashboard     from './pages/Dashboard'
import GraphExplorer from './pages/GraphExplorer'
import ScanResults   from './pages/ScanResults'
import Chat          from './pages/Chat'
import { IngestProvider } from './context/IngestContext'

export default function App() {
  return (
    <IngestProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index          element={<Dashboard />}     />
            <Route path="/graph"  element={<GraphExplorer />} />
            <Route path="/scan"   element={<ScanResults />}   />
            <Route path="/chat"   element={<Chat />}          />
          </Route>
        </Routes>
      </BrowserRouter>
    </IngestProvider>
  )
}
