import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTheme } from '../contexts/ThemeContext'
import { useAuth } from '../contexts/AuthContext'
import { post } from '../lib/api'
import { getRefreshToken } from '../lib/auth'
import Mark from './brand/Mark'
import { Avatar } from './ui/Glyphs'
import { MoonIcon, SignOutIcon, SunIcon } from './icons'

export default function MobileHeader() {
  const { theme, toggle } = useTheme()
  const { user, logout } = useAuth()
  const [isLoggingOut, setIsLoggingOut] = useState(false)

  async function handleLogout() {
    setIsLoggingOut(true)
    try {
      const refreshToken = getRefreshToken()
      if (refreshToken) {
        await post('/auth/logout', { refresh_token: refreshToken })
      }
    } finally {
      logout()
    }
  }

  return (
    <header className="sticky top-0 z-40 flex shrink-0 items-center justify-between border-b border-line bg-side px-4 py-2.5 md:hidden">
      <Link to="/dashboard" className="flex items-center gap-2">
        <Mark size={24} />
        <span className="text-[13px] font-semibold text-tx">DataMesh</span>
      </Link>

      <div className="flex items-center gap-1">
        {user && (
          <Link
            to="/profile"
            className="mr-1 flex items-center gap-1.5 rounded-lg p-1 transition-colors hover:bg-hover"
            title="View profile"
          >
            <Avatar name={user.username} />
            <span className="max-w-[80px] truncate text-xs text-tx2">{user.username}</span>
          </Link>
        )}

        <button
          type="button"
          onClick={toggle}
          className="grid h-8 w-8 place-items-center rounded-lg text-tx2 transition-colors hover:bg-hover hover:text-tx"
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
        </button>

        <button
          type="button"
          onClick={handleLogout}
          disabled={isLoggingOut}
          className="flex h-8 items-center gap-1.5 rounded-lg px-2 text-xs text-tx2 transition-colors hover:bg-bad/10 hover:text-bad disabled:cursor-not-allowed disabled:opacity-50"
          title="Sign out"
        >
          <SignOutIcon size={14} />
          {isLoggingOut ? 'Signing out…' : 'Sign out'}
        </button>
      </div>
    </header>
  )
}
