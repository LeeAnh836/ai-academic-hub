/**
 * JWT Token Utilities
 * Decode và validate JWT tokens without verifying signature
 */

interface JWTPayload {
  user_id: string
  email: string
  username: string
  type: 'access' | 'refresh'
  exp: number
  iat: number
}

/**
 * Decode JWT token (without verifying signature)
 * Frontend không cần verify signature vì backend sẽ verify
 */
export const decodeJWT = (token: string): JWTPayload | null => {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) {
      return null
    }

    const payload = parts[1]
    const decoded = atob(payload.replace(/-/g, '+').replace(/_/g, '/'))
    return JSON.parse(decoded)
  } catch (error) {
    console.error('Failed to decode JWT:', error)
    return null
  }
}

/**
 * Check if token is expired
 * Returns true if token is expired or invalid
 */
export const isTokenExpired = (token: string): boolean => {
  const payload = decodeJWT(token)
  if (!payload || !payload.exp) {
    return true
  }

  // Get current time in seconds
  const currentTime = Math.floor(Date.now() / 1000)
  
  // Token expired if exp < current time
  return payload.exp < currentTime
}

/**
 * Get token expiration time
 * Returns timestamp in seconds, or null if invalid
 */
export const getTokenExpiration = (token: string): number | null => {
  const payload = decodeJWT(token)
  return payload?.exp || null
}

/**
 * Get time until token expires
 * Returns seconds until expiration, or 0 if expired/invalid
 */
export const getTokenTimeRemaining = (token: string): number => {
  const exp = getTokenExpiration(token)
  if (!exp) return 0

  const currentTime = Math.floor(Date.now() / 1000)
  const remaining = exp - currentTime

  return remaining > 0 ? remaining : 0
}

/**
 * Check if token will expire soon (within threshold)
 * Default threshold: 5 minutes
 */
export const isTokenExpiringSoon = (token: string, thresholdSeconds: number = 300): boolean => {
  const remaining = getTokenTimeRemaining(token)
  return remaining > 0 && remaining < thresholdSeconds
}

/**
 * Validate token structure and expiration
 * Returns true if token is valid and not expired
 */
export const isValidToken = (token: string): boolean => {
  if (!token) return false
  
  const payload = decodeJWT(token)
  if (!payload) return false
  
  return !isTokenExpired(token)
}

/**
 * Get user info from token
 */
export const getUserFromToken = (token: string): { user_id: string; email: string; username: string } | null => {
  const payload = decodeJWT(token)
  if (!payload) return null

  return {
    user_id: payload.user_id,
    email: payload.email,
    username: payload.username,
  }
}
