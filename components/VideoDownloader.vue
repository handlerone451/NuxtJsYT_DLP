<template>
  <div class="w-full max-w-2xl mx-4">
    <UCard class="border-2 border-green-500">
      <template #header>
        <h2 class="text-xl font-semibold">Youtube Downloader</h2>
      </template>

      <form @submit.prevent="handleSubmit">
        <div class="space-y-4">
          <!-- URL Input -->
          <UFormGroup label="Video URL">
            <UInput
              v-model="formData.url"
              placeholder="Enter video URL"
              :disabled="isLoading"
            />
          </UFormGroup>

          <!-- Format Selection -->
          <UFormGroup label="Resolution">
            <USelect
              v-model="formData.selectedFormat"
              :options="formats"
              option-label="label"
              option-value="value"
              placeholder="Select resolution"
              :disabled="!formats.length || isLoading"
            />
          </UFormGroup>

          <!-- MP3 Conversion Toggle -->
          <UFormGroup>
            <div class="flex gap-4">
              <UCheckbox
                v-model="formData.convertToMp3"
                label="Convert to MP3"
                :disabled="isLoading"
              />
              <UCheckbox
                v-model="formData.autoplay"
                label="Auto-play after download"
                :disabled="isLoading"
              />
            </div>
          </UFormGroup>

          <!-- Action Buttons -->
          <div class="flex gap-4">
            <UButton
              type="button"
              @click="fetchFormats"
              :loading="isFetchingFormats"
              :disabled="!formData.url || isLoading"
            >
              Fetch Formats
            </UButton>

            <UButton
              type="submit"
              color="primary"
              :loading="isDownloading"
              :disabled="!formData.selectedFormat || isLoading"
            >
              Download
            </UButton>
          </div>
        </div>
      </form>
    </UCard>

    <!-- Download Progress -->
    <UCard v-if="isDownloading || downloadProgress.merging" class="mt-4">
      <div v-if="downloadProgress.video >= 0" class="mb-2">
        <div class="text-sm mb-1">Video Download: {{ Math.round(downloadProgress.video) }}%</div>
        <UProgress :value="downloadProgress.video" color="blue" class="h-2" />
      </div>
      <div v-if="downloadProgress.video >= 100 && downloadProgress.audio >= 0" class="mb-2">
        <div class="text-sm mb-1">Audio Download: {{ Math.round(downloadProgress.audio) }}%</div>
        <UProgress :value="downloadProgress.audio" color="green" class="h-2" />
      </div>
      <div v-if="downloadProgress.merging" class="mb-2">
        <div class="text-sm mb-1">Merging Files</div>
        <UProgress :value="100" :indeterminate="true" color="purple" class="h-2" />
      </div>
    </UCard>

    <!-- Video Details Card -->
    <VideoDetails :video-details="videoDetails" />
  </div>
</template>

<script setup lang="ts">
import { io } from 'socket.io-client';

const formData = ref({
  url: '',
  selectedFormat: '',
  convertToMp3: false,
  autoplay: false
});

const formats = ref([]);
const videoDetails = ref(null);
const isFetchingFormats = ref(false);
const isDownloading = ref(false);
const videoApi = useVideoApi();
const youtubeApi = useYoutubeApi();

const isLoading = computed(() => isFetchingFormats.value || isDownloading.value);

const downloadProgress = ref({
  video: -1,
  audio: -1,
  merging: false
});

// Initialize WebSocket connection
const socket = io('http://localhost:8080', {
  transports: ['websocket'],
  reconnection: true
});

onMounted(() => {
  socket.on('connect', () => {
    console.log('Connected to WebSocket server');
  });

  socket.on('download_progress', (progress) => {
    console.log('Progress received:', progress);
    
    if (progress.type === 'reset') {
      downloadProgress.value = {
        video: 0,
        audio: 0,
        merging: false
      };
      return;
    }
    
    if (progress.type === 'error') {
      console.error('Download error:', progress.message);
      isDownloading.value = false;
      return;
    }
    
    if (progress.type === 'complete') {
      downloadProgress.value.merging = false;
      isDownloading.value = false;
      return;
    }
    
    switch (progress.type) {
      case 'video':
        downloadProgress.value.video = progress.percent;
        break;
      case 'audio':
        // Only start showing audio progress after video is complete
        if (downloadProgress.value.video >= 100) {
          downloadProgress.value.audio = progress.percent;
        }
        break;
      case 'merging':
        if (progress.percent === 0) {
          downloadProgress.value.merging = true;
        } else if (progress.percent === 100) {
          downloadProgress.value.merging = false;
          isDownloading.value = false;
        }
        break;
    }
  });

  socket.on('connect_error', (error) => {
    console.error('WebSocket connection error:', error);
  });
});

onUnmounted(() => {
  socket.disconnect();
});

// Reset progress when starting new download
async function fetchFormats() {
  if (!formData.value.url) return;
  
  try {
    isFetchingFormats.value = true;
    formats.value = await videoApi.fetchFormats(formData.value.url);
    videoDetails.value = await youtubeApi.fetchVideoDetails(formData.value.url);
  } finally {
    isFetchingFormats.value = false;
  }
}

async function handleSubmit() {
  if (!formData.value.selectedFormat) return;

  try {
    isDownloading.value = true;
    downloadProgress.value = {
      video: -1,
      audio: -1,
      merging: false
    };

    await videoApi.downloadVideo({
      url: formData.value.url,
      format_id: formData.value.selectedFormat,
      convert_to_mp3: formData.value.convertToMp3,
      autoplay: formData.value.autoplay
    }).catch(error => {
      console.error('Download error:', error);
      throw error;
    });
  } finally {
    // Don't reset isDownloading here, let the socket event handle it
  }
}
</script>