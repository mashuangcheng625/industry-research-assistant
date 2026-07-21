import { request } from './request'

export type TaskStatus =
  | 'queued'
  | 'running'
  | 'retrying'
  | 'succeeded'
  | 'failed'
  | 'cancelled'

export interface TaskRecord {
  task_id: string
  task_type: string
  status: TaskStatus
  created_at: string
  started_at: string | null
  finished_at: string | null
  attempts: number
  max_retries: number
  timeout_seconds: number
  cancel_requested: boolean
  error: string | null
  has_result: boolean
  result: unknown | null
}

export interface TaskListResponse {
  tasks: TaskRecord[]
  total: number
}

export async function getTasks(limit = 50): Promise<TaskListResponse> {
  const response = await request.get<TaskListResponse>('/tasks', {
    params: { limit },
    loading: false,
    errorToast: false,
    cancelRepeat: false,
  })
  return response.data
}

export async function getTask(taskId: string): Promise<TaskRecord> {
  const response = await request.get<TaskRecord>(
    `/tasks/${encodeURIComponent(taskId)}`,
    {
      loading: false,
      errorToast: false,
      cancelRepeat: false,
    },
  )
  return response.data
}

export async function cancelTask(taskId: string): Promise<TaskRecord> {
  const response = await request.post<TaskRecord>(
    `/tasks/${encodeURIComponent(taskId)}/cancel`,
    {},
    {
      loading: false,
      errorToast: false,
      cancelRepeat: false,
    },
  )
  return response.data
}
