import { z } from 'zod'

export const loginSchema = z.object({
  email: z.string().trim().pipe(z.email('Enter a valid email address.')),
  password: z.string().min(1, 'Enter your password.'),
})

export const profileSchema = z.object({
  id: z.uuid(),
  role: z.enum(['student', 'admin']),
  email: z.string().nullable(),
  display_name: z.string().nullable(),
})

export type LoginInput = z.infer<typeof loginSchema>
export type Profile = z.infer<typeof profileSchema>
export type Role = Profile['role']
