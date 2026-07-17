/**
 * Copyright © 2026 深圳市深维智见教育科技有限公司 版权所有
 */

import IconCompleted from '@/assets/chat/completed.svg'
import IconFile from '@/assets/chat/file.svg'
import IconSelectFile from '@/assets/chat/select-file.svg'
import { RightOutlined } from '@ant-design/icons'
import { Button, Checkbox } from 'antd'
import { useState } from 'react'
import styles from './select-file.module.scss'

export default function ChooseFile(props: {
  list?: API.Document[]
  onSubmit?: (list: API.Document[]) => void
}) {
  const { list, onSubmit } = props

  const [selectedFileList, setSelectedFileList] = useState<string[]>([])

  return (
    <div className={styles['select-file']}>
      <div className={styles['select-file__header']}>
        <img className={styles['icon']} src={IconSelectFile} />
        检索到 {list?.length ?? 0} 份相关文档
      </div>

      <Checkbox.Group
        className={styles['select-file__content']}
        value={selectedFileList}
        onChange={(value) => setSelectedFileList(value)}
      >
        {list?.map((file) => (
          <Checkbox key={file.document_id} value={file.document_id}>
            <img className={styles['icon']} src={IconFile} />
            <div className={styles['name']} title={file.document_name}>
              {file.document_name}
            </div>
            {/* <div className={styles['date']}>{file.date}</div> */}
          </Checkbox>
        ))}
      </Checkbox.Group>

      <div className={styles['select-file__footer']}>
        <div>
          已选择 <b>{selectedFileList.length}</b> 份文档
        </div>

        <Button
          type="primary"
          size="small"
          disabled={selectedFileList.length === 0}
          onClick={() => {
            onSubmit?.(
              list?.filter((file) =>
                selectedFileList.includes(file.document_id),
              ) ?? [],
            )
          }}
        >
          添加到本次研究
        </Button>
      </div>
    </div>
  )
}

function SelectFileSearching() {
  return (
    <div className={styles['select-file-searching']}>
      <div className={styles['icon']}></div>
      <div className={styles['title']}>正在检索专业知识库</div>
    </div>
  )
}
ChooseFile.Searching = SelectFileSearching

function SelectFileComplete(props: {
  contractsLength: number
  citationsLength: number
  onClick?: () => void
}) {
  const { contractsLength, citationsLength, onClick } = props

  return (
    <div className={styles['select-file-complete']} onClick={onClick}>
      <img className={styles['icon']} src={IconCompleted} />
      <div className={styles['title']}>研究依据</div>
      <div className={styles['desc']}>
        共引用 {citationsLength ?? 0} 条内容，来自 {contractsLength ?? 0} 份文档
      </div>
      <RightOutlined className={styles['arrow']} />
    </div>
  )
}

ChooseFile.Complete = SelectFileComplete
