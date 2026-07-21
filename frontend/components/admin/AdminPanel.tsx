'use client'

import React, { useState, useEffect, useCallback } from 'react'
import {
  Users,
  ScrollText,
  CheckCircle2,
  XCircle,
  PauseCircle,
  PlayCircle,
  ChevronLeft,
  ChevronRight,
  Loader2,
  AlertCircle,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react'
import { apiCall } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type UserStatus = 'pending' | 'approved' | 'suspended'

interface ManagedUser {
  id: string
  email: string
  full_name: string
  role: 'admin' | 'user'
  status: UserStatus
  created_at: string
}

interface AuditLog {
  id: string
  user_id: string
  action: string
  resource_id: string | null
  metadata: Record<string, unknown>
  created_at: string
}

interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: UserStatus }) {
  const styles: Record<UserStatus, string> = {
    pending:   'bg-amber-500/15 text-amber-400 border-amber-500/25',
    approved:  'bg-emerald-500/15 text-emerald-400 border-emerald-500/25',
    suspended: 'bg-red-500/15 text-red-400 border-red-500/25',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border ${styles[status]}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Users tab
// ---------------------------------------------------------------------------

const STATUS_FILTERS: Array<{ label: string; value: UserStatus | 'all' }> = [
  { label: 'All',       value: 'all' },
  { label: 'Pending',   value: 'pending' },
  { label: 'Approved',  value: 'approved' },
  { label: 'Suspended', value: 'suspended' },
]

function UsersTab() {
  const [users, setUsers]             = useState<ManagedUser[]>([])
  const [statusFilter, setStatusFilter] = useState<UserStatus | 'all'>('all')
  const [loading, setLoading]         = useState(false)
  const [error, setError]             = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  const fetchUsers = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = statusFilter !== 'all' ? `?status=${statusFilter}` : ''
      const data = await apiCall<ManagedUser[] | PaginatedResponse<ManagedUser>>(
        `/api/admin/users${params}`
      )
      setUsers(Array.isArray(data) ? data : (data as PaginatedResponse<ManagedUser>).items)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load users.')
    } finally {
      setLoading(false)
    }
  }, [statusFilter])

  useEffect(() => { fetchUsers() }, [fetchUsers])

  const performAction = async (userId: string, action: 'approve' | 'reject' | 'suspend' | 'reinstate') => {
    setActionLoading(userId + action)
    try {
      await apiCall(`/api/admin/users/${userId}/${action}`, { method: 'POST' })
      await fetchUsers()
    } catch (err) {
      setError(err instanceof Error ? err.message : `Action "${action}" failed.`)
    } finally {
      setActionLoading(null)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-1 p-1 rounded-lg bg-gray-800 border border-gray-700/50">
          {STATUS_FILTERS.map(f => (
            <button
              key={f.value}
              onClick={() => setStatusFilter(f.value)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors duration-150
                ${statusFilter === f.value
                  ? 'bg-violet-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-white hover:bg-gray-700'}`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <button
          onClick={fetchUsers}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
            text-gray-400 hover:text-white bg-gray-800 border border-gray-700
            hover:bg-gray-700 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-950/50 border border-red-700/50 text-red-300 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Table */}
      {loading && users.length === 0 ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 animate-spin text-violet-400" />
        </div>
      ) : users.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-16 text-gray-500">
          <Users className="w-10 h-10 text-gray-700" />
          <p className="text-sm">No users found.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-700/50">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-800/60 border-b border-gray-700/50">
                {['User', 'Role', 'Status', 'Joined', 'Actions'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {users.map(u => (
                <tr key={u.id} className="hover:bg-gray-800/30 transition-colors">
                  {/* User */}
                  <td className="px-4 py-3">
                    <div className="flex flex-col gap-0.5">
                      <span className="text-white font-medium">{u.full_name || '—'}</span>
                      <span className="text-xs text-gray-400">{u.email}</span>
                    </div>
                  </td>

                  {/* Role */}
                  <td className="px-4 py-3">
                    {u.role === 'admin' ? (
                      <span className="flex items-center gap-1 text-amber-400 text-xs font-semibold">
                        <ShieldCheck className="w-3.5 h-3.5" /> Admin
                      </span>
                    ) : (
                      <span className="text-gray-400 text-xs">User</span>
                    )}
                  </td>

                  {/* Status */}
                  <td className="px-4 py-3">
                    <StatusBadge status={u.status} />
                  </td>

                  {/* Joined */}
                  <td className="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">
                    {fmtDate(u.created_at)}
                  </td>

                  {/* Actions */}
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {u.status === 'pending' && (
                        <>
                          <ActionButton
                            icon={<CheckCircle2 className="w-3.5 h-3.5" />}
                            label="Approve"
                            color="emerald"
                            loading={actionLoading === u.id + 'approve'}
                            onClick={() => performAction(u.id, 'approve')}
                          />
                          <ActionButton
                            icon={<XCircle className="w-3.5 h-3.5" />}
                            label="Reject"
                            color="red"
                            loading={actionLoading === u.id + 'reject'}
                            onClick={() => performAction(u.id, 'reject')}
                          />
                        </>
                      )}
                      {u.status === 'approved' && (
                        <ActionButton
                          icon={<PauseCircle className="w-3.5 h-3.5" />}
                          label="Suspend"
                          color="amber"
                          loading={actionLoading === u.id + 'suspend'}
                          onClick={() => performAction(u.id, 'suspend')}
                        />
                      )}
                      {u.status === 'suspended' && (
                        <ActionButton
                          icon={<PlayCircle className="w-3.5 h-3.5" />}
                          label="Reinstate"
                          color="emerald"
                          loading={actionLoading === u.id + 'reinstate'}
                          onClick={() => performAction(u.id, 'reinstate')}
                        />
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// Small action button
interface ActionButtonProps {
  icon: React.ReactNode
  label: string
  color: 'emerald' | 'red' | 'amber'
  loading: boolean
  onClick: () => void
}

const colorClasses: Record<string, string> = {
  emerald: 'text-emerald-400 border-emerald-700/40 hover:bg-emerald-500/10',
  red:     'text-red-400 border-red-700/40 hover:bg-red-500/10',
  amber:   'text-amber-400 border-amber-700/40 hover:bg-amber-500/10',
}

function ActionButton({ icon, label, color, loading, onClick }: ActionButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium
        border bg-transparent transition-colors disabled:opacity-50 disabled:cursor-not-allowed
        ${colorClasses[color]}`}
    >
      {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : icon}
      {label}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Audit logs tab
// ---------------------------------------------------------------------------

const PAGE_SIZE = 20

function AuditLogsTab() {
  const [logs, setLogs]           = useState<AuditLog[]>([])
  const [total, setTotal]         = useState(0)
  const [page, setPage]           = useState(1)
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState<string | null>(null)

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const fetchLogs = useCallback(async (p: number) => {
    setLoading(true)
    setError(null)
    try {
      const data = await apiCall<PaginatedResponse<AuditLog>>(
        `/api/admin/audit-logs?page=${p}&page_size=${PAGE_SIZE}`
      )
      setLogs(data.items)
      setTotal(data.total)
      setPage(p)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load audit logs.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchLogs(1) }, [fetchLogs])

  return (
    <div className="flex flex-col gap-4">
      {/* Header row */}
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-gray-400">
          {total > 0 ? `${total} total event${total !== 1 ? 's' : ''}` : 'Audit events'}
        </p>
        <button
          onClick={() => fetchLogs(page)}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
            text-gray-400 hover:text-white bg-gray-800 border border-gray-700
            hover:bg-gray-700 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-950/50 border border-red-700/50 text-red-300 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Table */}
      {loading && logs.length === 0 ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 animate-spin text-violet-400" />
        </div>
      ) : logs.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-16 text-gray-500">
          <ScrollText className="w-10 h-10 text-gray-700" />
          <p className="text-sm">No audit events yet.</p>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-gray-700/50">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-800/60 border-b border-gray-700/50">
                  {['Timestamp', 'User ID', 'Action', 'Resource', 'Trace ID'].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60">
                {logs.map(log => {
                  const traceId =
                    typeof log.metadata?.trace_id === 'string'
                      ? log.metadata.trace_id
                      : typeof log.metadata?.traceparent === 'string'
                      ? (log.metadata.traceparent as string).split('-')[1] ?? '—'
                      : '—'

                  return (
                    <tr key={log.id} className="hover:bg-gray-800/30 transition-colors align-top">
                      <td className="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">
                        {fmtDate(log.created_at)}
                      </td>
                      <td className="px-4 py-3 text-xs font-mono text-gray-300 max-w-[120px] truncate" title={log.user_id}>
                        {log.user_id}
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-violet-500/10 text-violet-300 border border-violet-500/20">
                          {log.action}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-400 max-w-[140px] truncate" title={log.resource_id ?? ''}>
                        {log.resource_id ?? '—'}
                      </td>
                      <td className="px-4 py-3 text-xs font-mono text-gray-500 max-w-[160px] truncate" title={traceId}>
                        {traceId}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-gray-500">
              Page {page} of {totalPages}
            </p>
            <div className="flex items-center gap-1">
              <button
                onClick={() => fetchLogs(page - 1)}
                disabled={page <= 1 || loading}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium
                  text-gray-400 hover:text-white bg-gray-800 border border-gray-700
                  hover:bg-gray-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                Prev
              </button>
              <button
                onClick={() => fetchLogs(page + 1)}
                disabled={page >= totalPages || loading}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium
                  text-gray-400 hover:text-white bg-gray-800 border border-gray-700
                  hover:bg-gray-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Next
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// AdminPanel — top-level page component
// ---------------------------------------------------------------------------

type TabId = 'users' | 'audit'

const TABS: Array<{ id: TabId; label: string; icon: React.ReactNode }> = [
  { id: 'users', label: 'Users',       icon: <Users       className="w-4 h-4" /> },
  { id: 'audit', label: 'Audit Logs',  icon: <ScrollText  className="w-4 h-4" /> },
]

export default function AdminPanel() {
  const [activeTab, setActiveTab] = useState<TabId>('users')

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Page header */}
      <div
        className="border-b border-gray-800 bg-gray-900/80 px-6 py-5"
        style={{ backdropFilter: 'blur(8px)' }}
      >
        <div className="max-w-6xl mx-auto flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-amber-500/15 border border-amber-500/30">
            <ShieldCheck className="w-4 h-4 text-amber-400" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white">Admin Panel</h1>
            <p className="text-xs text-gray-400">Manage users and review audit events</p>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-6 flex flex-col gap-6">
        {/* Tabs */}
        <div className="flex items-center gap-1 p-1 w-fit rounded-lg bg-gray-800 border border-gray-700/50">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors duration-150
                ${activeTab === tab.id
                  ? 'bg-violet-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-white hover:bg-gray-700/60'}`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div>
          {activeTab === 'users' && <UsersTab />}
          {activeTab === 'audit' && <AuditLogsTab />}
        </div>
      </div>
    </div>
  )
}
