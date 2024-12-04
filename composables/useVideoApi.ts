import { UseFetchOptions } from 'nuxt/app'

const BASE_URL = 'http://localhost:8080'

export function useVideoApi() {
  const toast = useToast()

  const fetchFormats = async (url: string) => {
    try {
      const response = await fetch(`${BASE_URL}/fetch_formats`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ url })
      })

      if (!response.ok) throw new Error('Failed to fetch formats')

      const data = await response.json()
      if (!Array.isArray(data)) throw new Error('Invalid format data')

      toast.add({
        title: 'Success',
        description: 'Video formats fetched successfully',
        color: 'green',
        position: 'top-right',
        timeout: 5000
      })

      return data.map(([resolution, id]) => ({
        label: resolution,
        value: id
      }))
    } catch (error) {
      toast.add({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to fetch video formats',
        color: 'red',
        position: 'top-right',
        timeout: 5000
      })
      throw error
    }
  }

  const downloadVideo = async (params: {
    url: string
    format_id: string
    convert_to_mp3: boolean
  }) => {
    try {
      const response = await fetch(`${BASE_URL}/download_video`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(params)
      })

      if (!response.ok) throw new Error('Download failed')

      toast.add({
        title: 'Success',
        description: 'Download Video successfully',
        color: 'green',
        position: 'top-right',
        timeout: 6000
      })
    } catch (error) {
      toast.add({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to start download',
        color: 'red',
        position: 'top-right',
        timeout: 5000
      })
      throw error
    }
  }

  return {
    fetchFormats,
    downloadVideo
  }
}