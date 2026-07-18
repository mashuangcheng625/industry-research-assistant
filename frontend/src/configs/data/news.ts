// 离线 UI 夹具：仅在 mock 模式展示，真实新闻由后端采集并附带来源。
export default [
  {
    title: 'CHIPS R&D Metrology Program：半导体计量挑战示例',
    url: 'https://www.nist.gov/news-events/news/2023/06/new-chips-report-describes-metrology-grand-challenges-semiconductor-sector',
    source: 'NIST',
    content:
      '该公开资料用于演示材料、设备和晶圆制造方向的来源卡片。研究回答应引用入库切片的页码和原始链接，不应把本摘要当作完整证据。',
    date: '2023-06-05',
    host: 'www.nist.gov',
  },
  {
    title: 'National Advanced Packaging Manufacturing Program 愿景资料',
    url: 'https://www.nist.gov/news-events/news/2023/11/chips-america-releases-vision-approximately-3-billion-national-advanced',
    source: 'NIST',
    content:
      '该公开资料用于演示先进封装方向的政策与技术信号。系统展示时保留发布机构、日期和原始 URL，便于用户回溯。',
    date: '2023-11-20',
    host: 'www.nist.gov',
  },
  {
    title: 'OpenROAD Flow Scripts 官方设计流程文档',
    url: 'https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts',
    source: 'OpenROAD Project',
    content:
      '该官方项目文档用于演示芯片设计、EDA 流程与可复现版本引用。入库记录固定到具体 commit，避免上游文档变化导致评测漂移。',
    date: '2026-07-17',
    host: 'github.com',
  },
]
