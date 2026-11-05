import api from './client'

export async function fetchAll(path, workspaceId, extraParams = {}) {
  if (!workspaceId) return []
  const pageSize = 100
  let page = 1
  let total = Infinity
  const items = []
  try {
    while (items.length < total) {
      const response = await api.get(path, { params: { workspace_id: workspaceId, page, page_size: pageSize, ...extraParams } })
      const data = response.data?.data || {}
      const pageItems = Array.isArray(data.items) ? data.items : []
      items.push(...pageItems)
      total = Number(data.total ?? pageItems.length)
      if (!pageItems.length || items.length >= total) break
      page += 1
    }
  } catch (error) {
    // A workspace with no scans/resources is a normal empty state, not a page error.
    if (error?.response?.status === 404) return []
    throw error
  }
  return items
}

export function isNotFound(error) {
  return error?.response?.status === 404
}
