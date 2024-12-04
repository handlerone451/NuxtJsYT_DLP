<template>
  <UCard v-if="videoDetails" class="mt-4 border-2 border-green-500">
    <div class="flex flex-col gap-4">
      <h3 class="text-lg font-semibold text-center">{{ videoDetails.title }}</h3>
      <div class="relative w-full max-w-2xl mx-auto">
        <div class="relative w-full" style="padding-top: 56.25%;">
          <img
            :src="videoDetails.thumbnail"
            :alt="videoDetails.title"
            class="absolute top-0 left-0 w-full h-full object-cover rounded"
          />
          <div class="absolute bottom-2 right-2 bg-black bg-opacity-75 px-2 py-1 rounded text-sm">
            {{ videoDetails.duration }}
          </div>
        </div>
      </div>
    </div>
  </UCard>
</template>

<script setup lang="ts">
interface Props {
  videoDetails: {
    title: string;
    thumbnail: string;
    duration: string;
  } | null;
}

defineProps<Props>();
</script>