/**
 * User utility functions
 * Xử lý các operations liên quan đến user data
 */

import type { User } from "@/types/api"

/**
 * Lấy initials từ tên user (cho avatar)
 * @param user - User object hoặc null
 * @returns Initials string (VD: "John Doe" -> "JD")
 */
export function getUserInitials(user: User | null): string {
  if (!user) return "?"
  
  const name = user.full_name || user.username || user.email
  
  // Nếu là full_name và có khoảng trắng, lấy chữ cái đầu của mỗi từ
  if (name.includes(" ")) {
    return name
      .split(" ")
      .filter(n => n.length > 0)
      .map(n => n[0].toUpperCase())
      .slice(0, 2) // Chỉ lấy tối đa 2 chữ cái
      .join("")
  }
  
  // Nếu không có khoảng trắng, lấy 2 ký tự đầu
  return name.slice(0, 2).toUpperCase()
}

/**
 * Lấy display name của user
 * @param user - User object hoặc null
 * @returns Display name
 */
export function getUserDisplayName(user: User | null): string {
  if (!user) return "Unknown User"
  return user.full_name || user.username || user.email
}

/**
 * Lấy role label của user
 * @param role - User role
 * @returns Localized role label
 */
export function getRoleLabel(role: string): string {
  const roleLabels: Record<string, string> = {
    admin: "Admin",
    user: "Student",
    moderator: "Moderator",
  }
  return roleLabels[role] || "User"
}

/**
 * Check if user is admin
 * @param user - User object hoặc null
 * @returns true nếu user là admin
 */
export function isAdmin(user: User | null): boolean {
  return user?.role === "admin"
}

/**
 * Format student ID
 * @param studentId - Student ID hoặc null
 * @returns Formatted student ID
 */
export function formatStudentId(studentId: string | null): string {
  if (!studentId) return "N/A"
  return studentId
}
