import { Spin } from 'antd'
import { Suspense, type ReactNode } from 'react'

type LazyRouteProps = {
  children: ReactNode
}

export function LazyRoute({ children }: LazyRouteProps) {
  return (
    <Suspense
      fallback={
        <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />
      }
    >
      {children}
    </Suspense>
  )
}
