import { Spin } from 'antd'
import { Suspense, lazy } from 'react'
import { AuthGuard } from '@/components/auth-guard'
import { BaseLayout } from '@/layout/base'
import NotFound from '@/pages/404'
import LoginPage from '@/pages/auth/login'
import Index from '@/pages/index'
import {
  Navigate,
  Outlet,
  RouteObject,
  createBrowserRouter,
} from 'react-router-dom'

// ── Route-level code splitting (P1-10) ──
// Pages that are not entry points are loaded on demand via
// React.lazy + dynamic import(). Each chunk's loading Promise is
// resolved at navigation time, and Suspense renders a Spin fallback
// while the chunk is being fetched.
const Chat            = lazy(() => import('@/pages/chat'))
const NewChat         = lazy(() => import('@/pages/chat/newchat'))
const DemoPage        = lazy(() => import('@/pages/demo'))
const KnowledgePage   = lazy(() => import('@/pages/knowledge'))
const MemoryPage      = lazy(() => import('@/pages/memory'))
const DatabasePage    = lazy(() => import('@/pages/database'))
const NewsPage        = lazy(() => import('@/pages/news'))
const BiddingPage     = lazy(() => import('@/pages/bidding'))

const Lazy: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Suspense fallback={<Spin size="large" style={{ display: 'block', margin: '80px auto' }} />}>
    {children}
  </Suspense>
)

function withLazy(Component: React.ComponentType) {
  return function LazyWrapper() {
    return (
      <Lazy>
        <Component />
      </Lazy>
    )
  }
}

export type IRouteObject = {
  children?: IRouteObject[]
  name?: string
  auth?: boolean
  pure?: boolean
  meta?: any
} & Omit<RouteObject, 'children'>

export const routes: IRouteObject[] = [
  {
    path: '/',
    Component: Index,
  },
  {
    path: '/chat',
    children: [
      {
        path: '',
        Component: withLazy(NewChat),
      },
      {
        path: ':id',
        Component: withLazy(Chat),
      },
    ],
  },
  {
    path: '/knowledge',
    Component: withLazy(KnowledgePage),
  },
  {
    path: '/memory',
    Component: withLazy(MemoryPage),
  },
  {
    path: '/database',
    Component: withLazy(DatabasePage),
  },
  {
    path: '/news',
    Component: withLazy(NewsPage),
  },
  {
    path: '/bidding',
    Component: withLazy(BiddingPage),
  },
  {
    path: '/404',
    Component: NotFound,
    pure: true,
  },
]

export const router = createBrowserRouter(
  [
    {
      path: '/login',
      element: <LoginPage />,
    },
    {
      path: '/demo',
      element: (
        <Lazy>
          <DemoPage />
        </Lazy>
      ),
    },
    {
      path: '/',
      element: (
        <AuthGuard>
          <BaseLayout>
            <Outlet />
          </BaseLayout>
        </AuthGuard>
      ),
      children: routes,
    },
    {
      path: '*',
      element: <Navigate to="/404" />,
    },
  ] as RouteObject[],
  {
    basename: import.meta.env.BASE_URL,
  },
)
