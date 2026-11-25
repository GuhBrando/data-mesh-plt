import { useState } from 'react'
import Button from './Button'
import Modal from './Modal'
import Spinner from './Spinner'

function download(fileName: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'application/yaml' }))
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  link.click()
  URL.revokeObjectURL(url)
}

interface YamlModalProps {
  title: string
  open: boolean
  content: string | undefined
  loading: boolean
  onClose: () => void
  /** Offers Copy and Download (under this name) once the YAML is there. */
  fileName?: string
}

/** A YAML document in a dialog, as the API serves it. */
export default function YamlModal({ title, open, content, loading, onClose, fileName }: YamlModalProps) {
  const [copied, setCopied] = useState(false)
  const ready = !loading && content !== undefined

  const copy = async () => {
    await navigator.clipboard.writeText(content ?? '')
    setCopied(true)
  }

  return (
    <Modal open={open} onClose={onClose} title={title} size="lg">
      {loading ? (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      ) : (
        <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg border border-line bg-bg p-4 font-mono text-xs text-tx2">
          {content}
        </pre>
      )}
      {fileName && ready && (
        <div className="mt-3 flex justify-end gap-2">
          <Button variant="secondary" onClick={copy}>
            {copied ? 'Copied' : 'Copy'}
          </Button>
          <Button onClick={() => download(fileName, content)}>Download</Button>
        </div>
      )}
    </Modal>
  )
}
