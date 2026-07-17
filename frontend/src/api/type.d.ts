/**
 * Copyright © 2026 深圳市深维智见教育科技有限公司 版权所有
 */

declare namespace API {
  type Result<T> = T & {
    status: 'success' | 'error'
    message: string
  }
}
