import api from './client'

export async function downloadReportPdf(workspaceId) {
  const response = await api.get('/api/aws/report', { params: { workspace_id: workspaceId } })
  const report = response.data?.data
  if (!report?.download_url) throw new Error('The report response did not include a download URL.')

  const filename = String(report.filename || 'cloudguard-disaster-recovery-report.pdf')
  const anchor = document.createElement('a')
  anchor.href = report.download_url
  anchor.download = filename.toLowerCase().endsWith('.pdf') ? filename : `${filename}.pdf`
  anchor.rel = 'noopener noreferrer'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  return filename
}
