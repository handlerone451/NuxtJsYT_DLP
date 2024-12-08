interface VideoDetails {
  title: string;
  thumbnail: string;
  duration: string;
}

export function useYoutubeApi() {
  const toast = useToast();
  const API_KEY = ''; // Replace with your actual API key
  const BASE_URL = 'https://www.googleapis.com/youtube/v3';

  const extractVideoId = (url: string): string | null => {
    const regExp = /^.*((youtu.be\/)|(v\/)|(\/u\/\w\/)|(embed\/)|(watch\?))\??v?=?([^#&?]*).*/;
    const match = url.match(regExp);
    return (match && match[7].length === 11) ? match[7] : null;
  };

  const fetchVideoDetails = async (url: string): Promise<VideoDetails | null> => {
    try {
      const videoId = extractVideoId(url);
      if (!videoId) throw new Error('Invalid YouTube URL');

      const response = await fetch(
        `${BASE_URL}/videos?part=snippet,contentDetails&id=${videoId}&key=${API_KEY}`
      );

      if (!response.ok) throw new Error('Failed to fetch video details');

      const data = await response.json();
      if (!data.items || data.items.length === 0) {
        throw new Error('Video not found');
      }

      const video = data.items[0];
      return {
        title: video.snippet.title,
        thumbnail: video.snippet.thumbnails.high.url,
        duration: video.contentDetails.duration.replace('PT', '').toLowerCase()
      };
    } catch (error) {
      toast.add({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to fetch video details',
        color: 'red',
        position: 'top-right',
        timeout: 5000
      });
      return null;
    }
  };

  return {
    fetchVideoDetails
  };
}
