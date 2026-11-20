import { setupServer } from 'msw/node'

export const server = setupServer()
export const backend = 'http://localhost:5173/api/v1'
