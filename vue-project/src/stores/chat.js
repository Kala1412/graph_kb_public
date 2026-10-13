import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import {
    fetchSessions,
    fetchSessionMessages,
    deleteSessionApi,
    renameSessionApi
} from '@/api/index'

export const useChatStore = defineStore('chat', () => {
    const sessions = ref([])                    // 会话列表（从后端加载）
    const activeSessionId = ref(null)          // 当前活跃会话 ID
    const conversationsMap = ref(new Map())    // 运行时消息缓存 Map<sessionId, Message[]>
    const activeKbId = ref(null)               // 当前知识库 ID
    const isLoading = ref(false)               // 全局 loading
    const sidebarCollapsed = ref(false)        // 侧边栏状态
    let abortController = null                 // 中止控制器

    const getActiveSession = computed(() => {
        return sessions.value.find(s => s.id === activeSessionId.value) || null
    })


    const loadSessions = async () => {
        try {
            const res = await fetchSessions()
            sessions.value = res.data || []
        } catch (err) {
            console.error('加载会话列表失败:', err)
        }
    }

    const loadMessages = async (sessionId) => {
        if (!sessionId) return
        // 如果已有缓存且非空，不重复请求
        if (conversationsMap.value.has(sessionId) && conversationsMap.value.get(sessionId).length > 0) {
            return
        }
        try {
            const res = await fetchSessionMessages(sessionId)
            const messages = (res.data || []).map(msg => ({
                role: msg.role,
                content: msg.content,
                timestamp: new Date(msg.created_at).getTime(),
                references: Array.isArray(msg.references) ? msg.references : [],
                graph_path: Array.isArray(msg.graph_path) ? msg.graph_path : [],
                // 附件由后端结构化返回，前端不从 content 里解析，避免脆弱字符串规则。
                attachments: Array.isArray(msg.attachments) ? msg.attachments : []
            }))
            conversationsMap.value.set(sessionId, messages)
            conversationsMap.value = new Map(conversationsMap.value) // 触发响应式
        } catch (err) {
            console.error(`加载会话 ${sessionId} 的消息失败:`, err)
        }
    }

    const createSession = (title = '新对话', kbId = null) => {
        const sessionId = `session_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
        const newSession = {
            id: sessionId,
            title: title || '新对话',
            kb_id: kbId,
            created_at: new Date().toISOString()
        }
        sessions.value.unshift(newSession)
        activeSessionId.value = sessionId
        return sessionId
    }

    const deleteSession = async (sessionId) => {
        try {
            await deleteSessionApi(sessionId)
        } catch (err) {
            // 如果后端 404（该会话还没发过消息，仅存在前端），忽略
            if (err.response?.status !== 404 && err.response?.status !== 403) {
                throw err
            }
        }
        const index = sessions.value.findIndex(s => s.id === sessionId)
        if (index > -1) {
            sessions.value.splice(index, 1)
            conversationsMap.value.delete(sessionId)
        }
        if (activeSessionId.value === sessionId) {
            activeSessionId.value = sessions.value.length > 0 ? sessions.value[0].id : null
        }
    }

    const renameSession = async (sessionId, newTitle) => {
        try {
            await renameSessionApi(sessionId, newTitle)
        } catch (err) {
            if (err.response?.status !== 404) {
                throw err
            }
        }
        const session = sessions.value.find(s => s.id === sessionId)
        if (session) {
            session.title = newTitle
        }
    }

    const refreshSessionTitle = async (sessionId) => {
        try {
            const res = await fetchSessions()
            const updated = (res.data || []).find(s => s.id === sessionId)
            if (updated) {
                const local = sessions.value.find(s => s.id === sessionId)
                if (local) {
                    local.title = updated.title
                }
            }
        } catch (err) {
            console.error('刷新标题失败:', err)
        }
    }


    const getMessages = (sessionId = null) => {
        const id = sessionId || activeSessionId.value
        if (!id) return []
        if (!conversationsMap.value.has(id)) {
            conversationsMap.value.set(id, [])
        }
        return conversationsMap.value.get(id)
    }

    const addMessage = (sessionId, message) => {
        const messages = getMessages(sessionId)
        messages.push(message)
        conversationsMap.value = new Map(conversationsMap.value)
    }

    const updateLastMessage = (sessionId, updates) => {
        const messages = getMessages(sessionId)
        if (messages.length > 0) {
            const lastIndex = messages.length - 1
            const updatedMsg = { ...messages[lastIndex], ...updates }
            messages.splice(lastIndex, 1, updatedMsg)
            conversationsMap.value = new Map(conversationsMap.value)
        }
    }

    const updateMessageAt = (sessionId, index, updates) => {
        const messages = getMessages(sessionId)
        if (index < 0 || index >= messages.length) return
        const updatedMsg = { ...messages[index], ...updates }
        messages.splice(index, 1, updatedMsg)
        conversationsMap.value = new Map(conversationsMap.value)
    }

    const clearMessages = (sessionId) => {
        if (!sessionId) return
        conversationsMap.value.set(sessionId, [])
        conversationsMap.value = new Map(conversationsMap.value)
    }

    const setLoading = (value) => { isLoading.value = value }

    const createAbortController = () => {
        if (abortController) abortController.abort()
        abortController = new AbortController()
        return abortController
    }

    const abortCurrentRequest = () => {
        if (abortController) {
            abortController.abort()
            abortController = null
            setLoading(false)
        }
    }

    const toggleSidebar = () => { sidebarCollapsed.value = !sidebarCollapsed.value }

    return {
        sessions, activeSessionId, sidebarCollapsed,
        activeKbId, isLoading, conversationsMap,
        getActiveSession,
        loadSessions, loadMessages, createSession,
        deleteSession, renameSession, refreshSessionTitle,
        getMessages, addMessage, updateLastMessage, updateMessageAt,
        clearMessages, setLoading,
        createAbortController, abortCurrentRequest,
        toggleSidebar, getSessions: () => sessions.value
    }
})
