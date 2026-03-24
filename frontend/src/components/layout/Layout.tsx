import type { ReactNode } from 'react'

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[#0a0a1a] text-[#e0e0e0] font-sans">
      <div className="max-w-[1200px] mx-auto px-5 py-6">
        {children}
      </div>
    </div>
  )
}
