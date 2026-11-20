import { useEffect, useRef } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import BottomNav from './BottomNav'
import MobileHeader from './MobileHeader'

export default function Layout() {
  const { pathname } = useLocation()
  const mainRef = useRef<HTMLElement>(null)

  // A new page starts at the top, the way a full navigation would.
  useEffect(() => {
    mainRef.current?.scrollTo?.({ top: 0 })
  }, [pathname])

  return (
    <div className="flex h-screen bg-bg">
      <Sidebar />
      <main ref={mainRef} className="relative flex min-w-0 flex-1 flex-col overflow-y-auto bg-bg">
        {/* Route bar: a 2px accent sweep on every page change. */}
        <div
          key={`route-${pathname}`}
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-0 z-50 h-0.5 origin-left bg-accent opacity-0 animate-route"
        />
        <MobileHeader />
        <TopBar />
        {/* pb-20 clears the 64px BottomNav on mobile; md:pb-16 restores the desktop bottom space */}
        <div
          key={pathname}
          className="mx-auto w-full max-w-[1320px] animate-swap p-4 pb-20 md:px-7 md:pb-16 md:pt-6"
        >
          <Outlet />
        </div>
      </main>
      <BottomNav />
    </div>
  )
}
