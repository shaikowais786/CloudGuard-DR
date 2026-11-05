import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'sonner'
import App from './app/App'
import { AuthProvider } from './auth/AuthContext'
import './styles.css'
createRoot(document.getElementById('root')).render(<React.StrictMode><BrowserRouter><AuthProvider><App /><Toaster theme="dark" richColors position="bottom-right" closeButton/></AuthProvider></BrowserRouter></React.StrictMode>)
