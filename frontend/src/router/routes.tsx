import { lazy } from 'react'
import { AuthGuard } from '@/components/auth-guard'
import { BaseLayout } from '@/layout/base'
import NotFound from '@/pages/404'
import LoginPage from '@/pages/auth/login'
import Index from '@/pages/index'
import { LazyRoute } from './lazy-route'
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
const TasksPage       = lazy(() => import('@/pages/tasks'))

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
        element: (
          <LazyRoute>
            <NewChat />
          </LazyRoute>
        ),
      },
      {
        path: ':id',
        element: (
          <LazyRoute>
            <Chat />
          </LazyRoute>
        ),
      },
    ],
  },
  {
    path: '/knowledge',
    element: (
      <LazyRoute>
        <KnowledgePage />
      </LazyRoute>
    ),
  },
  {
    path: '/memory',
    element: (
      <LazyRoute>
        <MemoryPage />
      </LazyRoute>
    ),
  },
  {
    path: '/database',
    element: (
      <LazyRoute>
        <DatabasePage />
      </LazyRoute>
    ),
  },
  {
    path: '/news',
    element: (
      <LazyRoute>
        <NewsPage />
      </LazyRoute>
    ),
  },
  {
    path: '/bidding',
    element: (
      <LazyRoute>
        <BiddingPage />
      </LazyRoute>
    ),
  },
  {
    path: '/tasks',
    element: (
      <LazyRoute>
        <TasksPage />
      </LazyRoute>
    ),
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
        <LazyRoute>
          <DemoPage />
        </LazyRoute>
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
