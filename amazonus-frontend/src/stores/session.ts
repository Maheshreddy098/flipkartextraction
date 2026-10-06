import { defineStore } from 'pinia'
import { call } from '@/api/client'

export const useSession = defineStore('session', {
  state: () => ({
    user: '',
    fullName: '',
    canPost: false,
    loaded: false,
  }),
  actions: {
    async load() {
      const info = await call<{ user: string; full_name: string; can_post: boolean }>('get_session_info')
      this.user = info.user
      this.fullName = info.full_name
      this.canPost = !!info.can_post
      this.loaded = true
    },
  },
})
