import { Button, Result } from 'antd'
import { useNavigate } from 'react-router-dom'

export default function NotFound() {
  const navigate = useNavigate()

  return (
    <Result
      status="404"
      title="页面不存在"
      subTitle="你访问的页面不存在，或地址已经发生变化。"
      extra={
        <Button type="primary" onClick={() => navigate('/')}>
          返回研究首页
        </Button>
      }
    />
  )
}
