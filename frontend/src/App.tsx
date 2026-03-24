import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from '@/components/layout/Layout'
import DashboardPage from '@/pages/DashboardPage'
import CumulativePage from '@/pages/CumulativePage'
import AllTimePage from '@/pages/AllTimePage'
import H2HPage from '@/pages/H2HPage'

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/cumulative" element={<CumulativePage />} />
          <Route path="/all-time" element={<AllTimePage />} />
          <Route path="/head-to-head" element={<H2HPage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
