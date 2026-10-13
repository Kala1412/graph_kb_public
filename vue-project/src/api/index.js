import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000/api'

const api = axios.create({
    baseURL: API_BASE,
    // 知识库查询通常需要 5-15 秒
    timeout: 60000,
    headers: {}
})
let isRefreshing = false        // 是否正在刷新
let failedQueue = []            // 刷新期间积压的请求队列

function clearAuthState() {
    localStorage.removeItem('token')
    localStorage.removeItem('refreshToken')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('role')
}

function processQueue(error, token = null) {
    failedQueue.forEach(prom => {
        if (error) {
            prom.reject(error)
        } else {
            prom.resolve(token)
        }
    })
    failedQueue = []
}


api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token')
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }

    if (config.url?.includes('/knowledge/query')) {
        config.timeout = 120000
    }

    // 纠正 Content-Type 判断：排除 URLSearchParams 和 FormData
    if (config.data &&
        typeof config.data === 'object' &&
        !(config.data instanceof FormData) &&
        !(config.data instanceof URLSearchParams)) {
        config.headers['Content-Type'] = 'application/json'
    }
    return config
}, (error) => Promise.reject(error))


api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config

        // 条件：收到 401 && 不是刷新接口本身 && 该请求没重试过
        if (error.response?.status === 401
            && !originalRequest.url.includes('/auth/refresh')
            && !originalRequest._retry) {

            // 如果已经在刷新中，排队等结果
            if (isRefreshing) {
                return new Promise((resolve, reject) => {
                    failedQueue.push({ resolve, reject })
                }).then(token => {
                    originalRequest.headers.Authorization = `Bearer ${token}`
                    return api(originalRequest)
                }).catch(err => Promise.reject(err))
            }

            originalRequest._retry = true
            isRefreshing = true

            const refreshToken = localStorage.getItem('refreshToken')

            if (!refreshToken) {
                forceLogout()
                return Promise.reject(error)
            }

            try {
                const res = await axios.post(`${API_BASE}/auth/refresh`, {
                    refresh_token: refreshToken
                })

                const { access_token, refresh_token: newRefreshToken } = res.data

                localStorage.setItem('token', access_token)
                localStorage.setItem('refreshToken', newRefreshToken)
                if (res.data?.role) {
                    localStorage.setItem('role', res.data.role)
                } else {
                    localStorage.removeItem('role')
                }

                processQueue(null, access_token)

                originalRequest.headers.Authorization = `Bearer ${access_token}`
                return api(originalRequest)
            } catch (refreshError) {
                // Refresh Token 也过期了（24 小时无活动），强制登出
                processQueue(refreshError, null)
                forceLogout()
                return Promise.reject(refreshError)
            } finally {
                isRefreshing = false
            }
        }

        return Promise.reject(error)
    }
)

function forceLogout() {
    clearAuthState()
    window.location.href = '/login'
}

async function tryRefreshToken() {
    const refreshToken = localStorage.getItem('refreshToken')
    if (!refreshToken) {
        return null
    }

    if (isRefreshing) {
        try {
            const token = await new Promise((resolve, reject) => {
                failedQueue.push({ resolve, reject })
            })
            return token
        } catch {
            return null
        }
    }

    isRefreshing = true
    try {
        const res = await axios.post(`${API_BASE}/auth/refresh`, {
            refresh_token: refreshToken
        })

        const { access_token, refresh_token: newRefreshToken } = res.data || {}
        if (!access_token) {
            throw new Error('刷新 token 失败')
        }

        localStorage.setItem('token', access_token)
        if (newRefreshToken) {
            localStorage.setItem('refreshToken', newRefreshToken)
        }
        if (res.data?.role) {
            localStorage.setItem('role', res.data.role)
        } else {
            localStorage.removeItem('role')
        }

        processQueue(null, access_token)
        return access_token
    } catch (err) {
        processQueue(err, null)
        forceLogout()
        return null
    } finally {
        isRefreshing = false
    }
}


export default api

export async function loginRequest(username, password) {
    const params = new URLSearchParams()
    params.append('username', username)
    params.append('password', password)
    const res = await api.post('/auth/login', params,{
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
    })
    localStorage.setItem('token', res.data.access_token)
    localStorage.setItem('refreshToken', res.data.refresh_token)  // 新增
    if (res.data?.role) {
        localStorage.setItem('role', res.data.role)
    } else {
        localStorage.removeItem('role')
    }
    return res.data
}

export async function registerRequest(payload) {
    const res = await api.post('/users/', payload)
    return res.data
}

export async function chatStreamRequest(
    query,          // 用户问题
    kbId = null,
    threadId = 'default_user',
    topK = 5,      // 新增参数，默认 5
    mode = 'hybrid',   // 新增参数，默认 hybrid（融合检索）
    enableRerank = null, // 新增：手动控制是否重排
    images = [],
    onToken,
    onMetadata,
    onError,
    onDone,
    abortSignal = null  // 新增: 支持中止信号
) {

    const token = localStorage.getItem('token')
    const url = `${API_BASE}/agent/chat/stream`
    const hasImages = Array.isArray(images) && images.length > 0

    // 发送分支说明：
    // - 无图片时走 JSON，保持旧调用完全兼容；
    // - 有图片时走 FormData，启用 multipart 文件上传。
    const buildRequestOptions = (authToken) => {
        const headers = {}
        if (authToken) {
            headers.Authorization = `Bearer ${authToken}`
        }

        if (!hasImages) {
            headers['Content-Type'] = 'application/json'
            return {
                headers,
                body: JSON.stringify({
                    query,
                    kb_id: kbId,
                    thread_id: threadId,
                    top_k: topK,
                    mode: mode,
                    enable_rerank: enableRerank
                })
            }
        }

        const formData = new FormData()
        formData.append('query', query || '')
        formData.append('thread_id', threadId || 'default_user')
        formData.append('top_k', String(topK))
        formData.append('mode', mode || 'hybrid')
        if (kbId !== null && kbId !== undefined) {
            formData.append('kb_id', String(kbId))
        }
        if (enableRerank !== null && enableRerank !== undefined) {
            formData.append('enable_rerank', String(enableRerank))
        }
        images.forEach((file) => {
            formData.append('images', file)
        })

        // FormData 请求不要手动设置 Content-Type，浏览器会自动带上 boundary。
        return { headers, body: formData }
    }

    try {
        let requestOptions = buildRequestOptions(token)
        let response = await fetch(url, {
            method: 'POST',
            headers: requestOptions.headers,
            body: requestOptions.body,
            signal: abortSignal  // 传递中止信号
        })

        if (response.status === 401) {
            const newToken = await tryRefreshToken()
            if (newToken) {
                requestOptions = buildRequestOptions(newToken)
                response = await fetch(url, {
                    method: 'POST',
                    headers: requestOptions.headers,
                    body: requestOptions.body,
                    signal: abortSignal
                })
            } else {
                if (onError) onError('登录已过期，请重新登录')
                return
            }
        }

        if (!response.ok) {
            if (response.status === 401) {
                clearAuthState()
                window.location.href = '/login'
            }
            throw new Error(`HTTP ${response.status}: ${response.statusText}`)
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder('utf-8')
        let buffer = ''
        let currentEvent = { type: '', data: '' } // 使用对象记录当前事件状态

        while (true) {

            if (abortSignal?.aborted) {
                console.log('🛑 请求已中止')
                reader.cancel()
                break
            }

            const { done, value } = await reader.read()

            if (done) {
                console.log('✅ 流式完成')
                break
            }

            buffer += decoder.decode(value, { stream: true })

            // SSE 的标准分隔符是双换行 \n\n
            let parts = buffer.split('\n\n')

            // 保留最后一个不完整的行（可能被截断的行）
            buffer = parts.pop() || ''

            for (const part of parts) {
                if (!part.trim()) continue

                const lines = part.split('\n')
                let eventType = 'message' // 默认类型
                let eventData = ''

                for (const line of lines) {
                    if (line.startsWith('event:')) {
                        eventType = line.substring(6).trim()
                    } else if (line.startsWith('data:')) {
                        eventData = line.substring(5).trim()
                    }
                }

                if (eventData) {
                    try {
                        const data = JSON.parse(eventData)
                        if (eventType === 'token' && onToken) {
                            onToken(data.content || '')
                        } else if (eventType === 'metadata' && onMetadata) {
                            onMetadata(data)
                        } else if (eventType === 'done' && onDone) {
                            onDone(data)
                        } else if (eventType === 'error' && onError) {
                            onError(new Error(data.message))
                        }
                    } catch (e) {
                        console.error('SSE 格式解析失败:', e, part)
                    }
                }
            }
        }
    } catch (err) {
        if (err.name === 'AbortError') {
            console.log('🛑 请求被用户中止')
        } else if (onError) {
            onError(err)
        }
    }
}

export async function streamQueryKnowledgeBase(kbId, query, mode = 'hybrid', topK = 5, onProgress, onResult, onComplete, onError) {

    const token = localStorage.getItem('token')
    const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000/api'
    const url = `${API_BASE}/knowledge/query/stream`

    try {
        const formData = new FormData()
        formData.append('kb_id', kbId)
        formData.append('query', query)
        formData.append('mode', mode)
        formData.append('top_k', topK)

        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Authorization': token ? `Bearer ${token}` : ''
            },
            body: formData
        })

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`)
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder('utf-8')
        let buffer = ''
        let totalResults = 0

        while (true) {
            const { done, value } = await reader.read()

            if (done) {
                break
            }

            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')

            // 保留最后一个不完整的行
            buffer = lines[lines.length - 1]

            for (let i = 0; i < lines.length - 1; i++) {
                const line = lines[i]

                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6))

                        if (data.type === 'progress') {
                            onProgress && onProgress(data.progress, data.message)
                        } else if (data.type === 'result') {
                            totalResults++
                            onResult && onResult(data.data)
                        } else if (data.type === 'complete') {
                            onComplete && onComplete(data.total, data.kb_name, data.query)
                        } else if (data.type === 'error') {
                            onError && onError(new Error(data.message))
                        }
                    } catch (e) {
                        console.error('SSE 解析错误:', e)
                    }
                }
            }
        }
    } catch (error) {
        onError && onError(error)
    }
}

export async function getKnowledgeGraph(kbId, limit = 100) {
    try {
        const res = await api.post('/knowledge/queryGraph', {
            kb_id: kbId,    // null 时后端查全部
            limit: limit
        })
        return res.data
    } catch (error) {
        console.error('获取知识图谱失败:', error)
        throw error
    }
}

export const getDashboardStats = () => api.get('/dashboard/stats')
export const getDashboardHealth = () => api.get('/dashboard/health')


export const fetchSessions = () => api.get('/agent/sessions')

export const fetchSessionMessages = (sessionId) =>
    api.get(`/agent/sessions/${sessionId}/messages`)

export const deleteSessionApi = (sessionId) =>
    api.delete(`/agent/sessions/${sessionId}`)

export const renameSessionApi = (sessionId, title) =>
    api.put(`/agent/sessions/${sessionId}`, { title })

export const fetchAllUsers = (params = {}) =>
    api.get('/users/', {
        params: {
            skip: 0,
            limit: 1000,
            ...params
        }
    })

export const fetchKnowledgeList = () => api.get('/knowledge/list')

export const fetchAdminSessions = () => api.get('/agent/sessions')

export const fetchAuditLogs = (params = {}) =>
    api.get('/audit/logs', { params })


// 获取普通用户可见的讨论分类；管理员带 token 调用时会拿到全部分类。
export const fetchForumCategories = () => api.get('/forum/categories')

export const fetchForumPosts = (params = {}) =>
    api.get('/forum/posts', { params })

export const createForumPost = (payload) =>
    api.post('/forum/posts', payload)

export const fetchForumPostDetail = (postId) =>
    api.get(`/forum/posts/${postId}`)

export const likeForumPost = (postId) =>
    api.post(`/forum/posts/${postId}/like`)

export const unlikeForumPost = (postId) =>
    api.delete(`/forum/posts/${postId}/like`)

export const fetchForumComments = (postId) =>
    api.get(`/forum/posts/${postId}/comments`)

// parent_comment_id 为空表示一级评论；有值表示回复某条一级评论。
export const createForumComment = (postId, payload) =>
    api.post(`/forum/posts/${postId}/comments`, payload)

export const likeForumComment = (commentId) =>
    api.post(`/forum/comments/${commentId}/like`)

export const unlikeForumComment = (commentId) =>
    api.delete(`/forum/comments/${commentId}/like`)

export const fetchAdminForumCategories = () => api.get('/forum/admin/categories')

export const createAdminForumCategory = (payload) =>
    api.post('/forum/admin/categories', payload)

export const updateAdminForumCategory = (categoryId, payload) =>
    api.put(`/forum/admin/categories/${categoryId}`, payload)

// 管理员治理接口：只改状态，不改正文内容。
export const updateAdminForumPostStatus = (postId, status) =>
    api.put(`/forum/admin/posts/${postId}/status`, { status })

export const updateAdminForumCommentStatus = (commentId, status) =>
    api.put(`/forum/admin/comments/${commentId}/status`, { status })


export const getMyProfile = () => api.get('/users/me')

export const updateMyProfile = (payload) =>
    api.put('/users/me/profile', payload)

export const changeMyPassword = (payload) =>
    api.put('/users/me/password', payload)

export const uploadMyAvatar = (formData) =>
    api.post('/users/me/avatar', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    })

export const listMyMedicalProfileRecords = (params = {}) =>
    api.get('/medical-profiles/', { params })

export const createMyMedicalProfileRecord = (payload) =>
    api.post('/medical-profiles/', payload)

export const updateMyMedicalProfileRecord = (recordId, payload) =>
    api.put(`/medical-profiles/${recordId}`, payload)

export const deleteMyMedicalProfileRecord = (recordId) =>
    api.delete(`/medical-profiles/${recordId}`)

export const listMedicalProfileRecords = (params = {}) =>
    api.get('/medical-profiles/', { params })

export const createMedicalProfileRecord = (payload) =>
    api.post('/medical-profiles/', payload)

export const updateMedicalProfileRecord = (recordId, payload) =>
    api.put(`/medical-profiles/${recordId}`, payload)

export const deleteMedicalProfileRecord = (recordId) =>
    api.delete(`/medical-profiles/${recordId}`)
