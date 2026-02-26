import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Settings, LogOut, Zap } from 'lucide-react'

export default function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <nav className="navbar">
      <Link to="/" className="nav-brand">
        <Zap size={20} />
        <span>Siyada Leads</span>
      </Link>
      <div className="nav-right">
        <span className="nav-user">{user?.full_name || user?.email}</span>
        <Link to="/settings" className="nav-btn" title="Settings">
          <Settings size={18} />
        </Link>
        <button onClick={handleLogout} className="nav-btn" title="Log out">
          <LogOut size={18} />
        </button>
      </div>
    </nav>
  )
}
