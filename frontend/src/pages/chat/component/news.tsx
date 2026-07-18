import IconViews from '@/assets/chat/views.png'
import newsData from '@/configs/data/news'
import { useRequest } from 'ahooks'
import { Space } from 'antd'
import styles from './news.module.scss'

export default function News() {
  const { data } = useRequest(async () => {
    return {
      list: newsData.map((o) => ({
        ...o,
        desc: o.content.slice(0, 200),
      })),
    }
  })

  return (
    <div className={styles['news-list']}>
      <div className={styles['news-list__total']}>
        离线演示来源 <b>{data?.list.length ?? 0}</b> · 在线模式以后端采集结果为准
      </div>

      <div className={styles['news-list__content']}>
        {data?.list.map((item) => (
          <a
            className={styles['news-list__item']}
            key={item.url}
            href={item.url}
            target="_blank"
          >
            <div className={styles['news-list__item-title']}>{item.title}</div>
            <div className={styles['news-list__item-desc']}>{item.desc}</div>
            <div className={styles['news-list__item-footer']}>
              <Space size={10}>
                <div className={styles['views']}>发布日期 {item.date}</div>

                <div className={styles['views']}>
                  <img src={IconViews} />
                  可回溯
                </div>

                <div className={styles['tag']}>{item.source}</div>
              </Space>
            </div>
          </a>
        ))}
      </div>
    </div>
  )
}
