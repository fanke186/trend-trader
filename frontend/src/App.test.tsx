import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('App shell', () => {
  it('renders the command center layout', () => {
    render(<App />)
    expect(screen.getByText('trend-trader')).toBeInTheDocument()
    expect(screen.getByText('AI 指挥台')).toBeInTheDocument()
  })
})
