'use client'
import { signIn } from 'next-auth/react'
import { useState } from 'react'

export default function LoginPage() {
  const [error, setError] = useState('')
  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    const result = await signIn('credentials', {
      username: form.get('username'),
      password: form.get('password'),
      redirect: false,
    })
    if (result?.error) setError('Invalid credentials')
    else window.location.href = '/'
  }

  return (
    <div className="max-w-sm mx-auto mt-20">
      <h1 className="text-2xl font-bold mb-6">Admin Login</h1>
      {error && <p className="text-red-500 mb-4">{error}</p>}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div><label>Username</label>
          <input name="username" className="w-full border rounded px-3 py-2" />
        </div>
        <div><label>Password</label>
          <input name="password" type="password" className="w-full border rounded px-3 py-2" />
        </div>
        <button type="submit" className="w-full py-2 bg-primary text-primary-foreground rounded">Login</button>
      </form>
    </div>
  )
}
