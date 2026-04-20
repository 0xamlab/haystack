/** Redis client singleton (ioredis v5). */
import { Redis } from 'ioredis'
import { config } from './config.js'

let _client: Redis | null = null

export function getRedis(): Redis {
  if (!_client) {
    _client = new Redis(config.redisUrl, {
      maxRetriesPerRequest: 3,
      enableOfflineQueue:   false,
      lazyConnect:          false,
    })
    _client.on('error', (err: Error) => {
      console.error('[gateway:redis] error', err.message)
    })
  }
  return _client
}
