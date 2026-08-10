export type UserRole = 'admin' | 'visitor'
export type PostKind = 'muse' | 'diary'
export type MessageStatus = 'sent' | 'read'
export type ChatRequestStatus =
  | 'pending'
  | 'accepted'
  | 'rejected'
  | 'blocked'
  | 'cancelled'
  | 'expired'

export interface User {
  id: number
  email: string
  nickname: string
  name: string
  role: UserRole
  avatar_url?: string | null
  bio?: string
  allow_message_requests?: boolean
  show_email?: boolean
  show_join_date?: boolean
  created_at: string
  muted_until?: string | null
  mute_reason?: string
  is_muted?: boolean
  bot_preset?: string
  bot_enabled?: boolean
  bot_rounds_limit?: number
  bot_rounds_used?: number
  bot_rounds_remaining?: number
  bot_msgs_per_round?: number
  bot_msgs_this_round?: number
  bot_msgs_remaining?: number
}

export interface PublicUser {
  id: number
  nickname: string
  avatar_url: string | null
  bio: string
  allow_message_requests: boolean
  created_at: string | null
  email: string | null
  is_muted?: boolean
  is_bot?: boolean
  is_admin?: boolean
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

export interface Post {
  id: number
  kind: PostKind
  title: string
  body: string
  created_at: string
  author_name: string
  on_home?: boolean
}

export interface Project {
  id: number
  slug: string
  title: string
  summary: string
  stack: string[]
  status: string
  demo_url: string | null
  github_url?: string | null
  readme?: string
  note: string
  owner_id?: number | null
  owner_name?: string
  sort_order: number
  created_at?: string | null
}

export interface ChatMessage {
  id: number
  thread_id: number
  sender_id: number
  sender_name: string
  sender_avatar_url?: string | null
  content: string
  status: MessageStatus
  created_at: string
  read_at: string | null
  is_mine: boolean
  localStatus?: 'sending' | 'failed'
}

export interface ChatThread {
  id: number
  peer_id: number
  peer_name: string
  status: string
  updated_at: string
  unread_count: number
  last_message: string | null
  peer_active?: boolean
  peer_is_bot?: boolean
  peer_is_admin?: boolean
}

export interface ChatRequest {
  id: number
  sender_id: number
  sender_name: string
  receiver_id: number
  receiver_name: string
  message: string
  status: ChatRequestStatus
  created_at: string
  responded_at: string | null
}

export interface NotificationItem {
  id: number
  type: string
  title: string
  content: string
  related_id: number | null
  is_read: boolean
  created_at: string
}
