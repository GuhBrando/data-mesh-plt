import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Input } from '../../components/ui/Input'
import Button from '../../components/ui/Button'
import type { User } from '../../types'

const schema = z.object({
  username: z.string().min(2, 'Username must be at least 2 characters'),
  email: z.string().email('Must be a valid email address'),
})

type FormValues = z.infer<typeof schema>

interface UserFormProps {
  defaultValues?: User
  onSubmit: (values: FormValues) => void
  onCancel: () => void
  isSubmitting: boolean
  apiError?: string
}

export default function UserForm({
  defaultValues,
  onSubmit,
  onCancel,
  isSubmitting,
  apiError,
}: UserFormProps) {
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: defaultValues
      ? { username: defaultValues.username, email: defaultValues.email }
      : { username: '', email: '' },
  })

  useEffect(() => {
    if (defaultValues) {
      reset({ username: defaultValues.username, email: defaultValues.email })
    }
  }, [defaultValues, reset])

  useEffect(() => {
    if (apiError && /email already in use/i.test(apiError)) {
      setError('email', { message: 'This email is already in use' })
    }
  }, [apiError, setError])

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
      <Input
        label="Username"
        placeholder="janedoe"
        error={errors.username?.message}
        {...register('username')}
      />
      <Input
        label="Email"
        type="email"
        placeholder="jane@example.com"
        error={errors.email?.message}
        {...register('email')}
      />

      {apiError && !/email already in use/i.test(apiError) && (
        <p className="text-sm text-bad">{apiError}</p>
      )}

      <div className="flex justify-end gap-3 pt-2">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" loading={isSubmitting}>
          {defaultValues ? 'Save Changes' : 'Create User'}
        </Button>
      </div>
    </form>
  )
}
