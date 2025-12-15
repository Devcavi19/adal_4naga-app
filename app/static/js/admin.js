// Admin Dashboard JavaScript
// Auto-refresh, charts, data tables, export, notifications

// State
let currentPage = 1;
let currentFilters = {};
let queriesChart = null;
let keywordsChart = null;
let trendsDailyChart = null;
let trendsHourlyChart = null;
let autoRefreshInterval = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupNavigation();
    setupNotifications();
    setupFilters();
    setupExport();
    setupMaintenance();
    setupSidebar();
    
    // Load initial data
    loadOverview();
    
    // Start auto-refresh (every 30 seconds)
    startAutoRefresh();
});

// ============================================
// Navigation
// ============================================

function setupNavigation() {
    const navItems = document.querySelectorAll('.admin-nav-item');
    
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const section = item.dataset.section;
            switchSection(section);
            
            // Update active state
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');
        });
    });
}

function switchSection(section) {
    // Hide all sections
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    
    // Show selected section
    const sectionElement = document.getElementById(`${section}-section`);
    if (sectionElement) {
        sectionElement.classList.add('active');
    }
    
    // Update page title
    const titles = {
        'overview': 'Dashboard Overview',
        'queries': 'Query Logs',
        'trends': 'Trends & Analytics',
        'users': 'User Activity',
        'feedback': 'User Feedback',
        'maintenance': 'Maintenance'
    };
    document.getElementById('page-title').textContent = titles[section] || 'Dashboard';
    
    // Load section data
    loadSectionData(section);
}

function loadSectionData(section) {
    switch(section) {
        case 'overview':
            loadOverview();
            break;
        case 'queries':
            loadQueryLogs();
            break;
        case 'trends':
            loadTrends();
            break;
        case 'users':
            loadUserActivity();
            break;
    }
}

// ============================================
// Auto-Refresh
// ============================================

function startAutoRefresh() {
    // Refresh every 30 seconds
    autoRefreshInterval = setInterval(() => {
        const activeSection = document.querySelector('.admin-nav-item.active');
        if (activeSection) {
            const section = activeSection.dataset.section;
            if (section === 'overview') {
                loadOverview();
            }
        }
        
        // Always refresh notifications
        loadNotifications();
    }, 30000);
}

// ============================================
// Overview Dashboard
// ============================================

async function loadOverview() {
    try {
        const response = await fetch('/api/admin/analytics/overview');
        const data = await response.json();
        
        if (!response.ok) {
            console.error('Failed to load overview:', data);
            return;
        }
        
        // Update stat cards
        document.getElementById('stat-queries-today').textContent = data.queries_today || 0;
        document.getElementById('stat-queries-week').textContent = data.queries_week || 0;
        document.getElementById('stat-active-users').textContent = data.active_users || 0;
        // COMPETITION: Temporarily hidden - uncomment to show response time. Backend continues calculating avg_response_time_ms.
        // document.getElementById('stat-response-time').textContent = data.avg_response_time_ms ? `${data.avg_response_time_ms}ms` : '-';
        document.getElementById('stat-satisfaction').textContent = data.satisfaction_rate ? `${data.satisfaction_rate}%` : '-';
        document.getElementById('stat-feedback-count').textContent = data.total_feedback || 0;
        
        // Update notification badge
        const notifBadge = document.getElementById('notification-badge');
        if (data.unread_notifications > 0) {
            notifBadge.textContent = data.unread_notifications;
            notifBadge.style.display = 'block';
        } else {
            notifBadge.style.display = 'none';
        }
        
        // Update charts
        updateQueriesChart(data);
        updateKeywordsChart(data.top_keywords || []);
        
    } catch (error) {
        console.error('Error loading overview:', error);
    }
}

function updateQueriesChart(data) {
    const ctx = document.getElementById('queries-chart');
    if (!ctx) return;
    
    // Simple last 7 days data
    const labels = ['6 days ago', '5 days ago', '4 days ago', '3 days ago', '2 days ago', 'Yesterday', 'Today'];
    const values = [
        Math.floor(data.queries_week / 7),
        Math.floor(data.queries_week / 7),
        Math.floor(data.queries_week / 7),
        Math.floor(data.queries_week / 7),
        Math.floor(data.queries_week / 7),
        Math.floor(data.queries_week / 7),
        data.queries_today || 0
    ];
    
    if (queriesChart) {
        queriesChart.data.labels = labels;
        queriesChart.data.datasets[0].data = values;
        queriesChart.update();
    } else {
        queriesChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Queries',
                    data: values,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }
}

function updateKeywordsChart(keywords) {
    const ctx = document.getElementById('keywords-chart');
    if (!ctx) return;
    
    if (!keywords || keywords.length === 0) {
        // No data
        return;
    }
    
    const labels = keywords.slice(0, 10).map(k => k.keyword);
    const values = keywords.slice(0, 10).map(k => k.count);
    
    if (keywordsChart) {
        keywordsChart.data.labels = labels;
        keywordsChart.data.datasets[0].data = values;
        keywordsChart.update();
    } else {
        keywordsChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Occurrences',
                    data: values,
                    backgroundColor: '#10b981'
                }]
            },
            options: {
                responsive: true,
                indexAxis: 'y',
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true
                    }
                }
            }
        });
    }
}

// ============================================
// Query Logs
// ============================================

function setupFilters() {
    document.getElementById('apply-filters-btn')?.addEventListener('click', () => {
        currentFilters = {
            date_from: document.getElementById('filter-date-from').value,
            date_to: document.getElementById('filter-date-to').value,
            keyword: document.getElementById('filter-keyword').value,
            search_method: document.getElementById('filter-search-method').value
        };
        currentPage = 1;
        loadQueryLogs();
    });
    
    document.getElementById('reset-filters-btn')?.addEventListener('click', () => {
        document.getElementById('filter-date-from').value = '';
        document.getElementById('filter-date-to').value = '';
        document.getElementById('filter-keyword').value = '';
        document.getElementById('filter-search-method').value = '';
        currentFilters = {};
        currentPage = 1;
        loadQueryLogs();
    });
    
    document.getElementById('prev-page-btn')?.addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            loadQueryLogs();
        }
    });
    
    document.getElementById('next-page-btn')?.addEventListener('click', () => {
        currentPage++;
        loadQueryLogs();
    });
}

async function loadQueryLogs() {
    const container = document.getElementById('query-logs-table');
    if (!container) return;
    
    container.innerHTML = '<div class="loading"><i class="fas fa-spinner"></i><p>Loading query logs...</p></div>';
    
    try {
        const params = new URLSearchParams({
            page: currentPage,
            per_page: 50,
            ...currentFilters
        });
        
        const response = await fetch(`/api/admin/analytics/queries?${params}`);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to load queries');
        }
        
        if (!data.queries || data.queries.length === 0) {
            container.innerHTML = '<div class="empty-state"><i class="fas fa-inbox"></i><p>No query logs found</p></div>';
            return;
        }
        
        // Build table
        let html = '<table class="data-table"><thead><tr>';
        html += '<th>Date</th>';
        html += '<th>User</th>';
        html += '<th>Query</th>';
        html += '<th>Keywords</th>';
        html += '<th>Method</th>';
        // COMPETITION: Response Time column temporarily hidden. To reactivate: uncomment next line and responseTime row cell below.
        // html += '<th>Response Time</th>';
        html += '<th>Documents</th>';
        html += '</tr></thead><tbody>';
        
        data.queries.forEach(query => {
            const date = new Date(query.created_at).toLocaleString();
            const keywords = query.keywords ? query.keywords.slice(0, 3).map(k => `<span class="keyword-tag">${k}</span>`).join('') : '-';
            const method = query.search_method || '-';
            // COMPETITION: Temporarily hidden - uncomment to show response time column data
            // const responseTime = query.response_time_ms ? `${query.response_time_ms}ms` : '-';
            const docs = query.documents_retrieved || 0;
            
            html += '<tr>';
            html += `<td>${date}</td>`;
            html += `<td><span class="user-link">${query.anonymized_user}</span></td>`;
            html += `<td style="max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(query.query_text)}</td>`;
            html += `<td>${keywords}</td>`;
            html += `<td><span class="badge badge-info">${method}</span></td>`;
            // COMPETITION: Temporarily hidden - uncomment to show response time cell
            // html += `<td>${responseTime}</td>`;
            html += `<td>${docs}</td>`;
            html += '</tr>';
        });
        
        html += '</tbody></table>';
        container.innerHTML = html;
        
        // Update pagination
        const totalPages = Math.ceil(data.total / 50);
        document.getElementById('current-page').textContent = currentPage;
        document.getElementById('total-pages').textContent = totalPages;
        document.getElementById('prev-page-btn').disabled = currentPage <= 1;
        document.getElementById('next-page-btn').disabled = currentPage >= totalPages;
        document.getElementById('query-pagination').style.display = 'flex';
        
    } catch (error) {
        console.error('Error loading query logs:', error);
        container.innerHTML = `<div class="empty-state"><i class="fas fa-exclamation-circle"></i><p>Error loading query logs</p></div>`;
    }
}

// ============================================
// Trends
// ============================================

async function loadTrends() {
    try {
        const response = await fetch('/api/admin/analytics/trends');
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to load trends');
        }
        
        updateTrendsDailyChart(data.queries_per_day || []);
        updateTrendsHourlyChart(data.queries_per_hour || []);
        
    } catch (error) {
        console.error('Error loading trends:', error);
    }
}

function updateTrendsDailyChart(data) {
    const ctx = document.getElementById('trends-daily-chart');
    if (!ctx) return;
    
    const labels = data.map(d => d.date);
    const values = data.map(d => d.count);
    
    if (trendsDailyChart) {
        trendsDailyChart.data.labels = labels;
        trendsDailyChart.data.datasets[0].data = values;
        trendsDailyChart.update();
    } else {
        trendsDailyChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Queries',
                    data: values,
                    borderColor: '#2563eb',
                    backgroundColor: 'rgba(37, 99, 235, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }
}

function updateTrendsHourlyChart(data) {
    const ctx = document.getElementById('trends-hourly-chart');
    if (!ctx) return;
    
    const labels = data.map(d => `${d.hour}:00`);
    const values = data.map(d => d.count);
    
    if (trendsHourlyChart) {
        trendsHourlyChart.data.labels = labels;
        trendsHourlyChart.data.datasets[0].data = values;
        trendsHourlyChart.update();
    } else {
        trendsHourlyChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Queries',
                    data: values,
                    backgroundColor: '#f59e0b'
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }
}

// ============================================
// User Activity
// ============================================

async function loadUserActivity() {
    const container = document.getElementById('user-activity-table');
    if (!container) return;
    
    container.innerHTML = '<div class="loading"><i class="fas fa-spinner"></i><p>Loading user activity...</p></div>';
    
    try {
        const response = await fetch('/api/admin/users/activity');
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to load user activity');
        }
        
        if (!data.users || data.users.length === 0) {
            container.innerHTML = '<div class="empty-state"><i class="fas fa-inbox"></i><p>No user activity found</p></div>';
            return;
        }
        
        // Build table
        let html = '<table class="data-table"><thead><tr>';
        html += '<th>User (Anonymized)</th>';
        html += '<th>Query Count</th>';
        // COMPETITION: Avg Response Time column temporarily hidden. To reactivate: uncomment next line and avgTime row cell below.
        // html += '<th>Avg Response Time</th>';
        html += '</tr></thead><tbody>';
        
        data.users.forEach(user => {
            // COMPETITION: Temporarily hidden - uncomment to show avg response time column
            // const avgTime = user.avg_response_time ? `${Math.round(user.avg_response_time)}ms` : '-';
            
            html += '<tr>';
            html += `<td><span class="user-link">${user.anonymized_user}</span></td>`;
            html += `<td>${user.query_count}</td>`;
            // COMPETITION: Temporarily hidden - uncomment to show avg response time data
            // html += `<td>${avgTime}</td>`;
            html += '</tr>';
        });
        
        html += '</tbody></table>';
        container.innerHTML = html;
        
    } catch (error) {
        console.error('Error loading user activity:', error);
        container.innerHTML = '<div class="empty-state"><i class="fas fa-exclamation-circle"></i><p>Error loading user activity</p></div>';
    }
}

// ============================================
// Notifications
// ============================================

function setupNotifications() {
    const bell = document.getElementById('notification-bell');
    const dropdown = document.getElementById('notification-dropdown');
    
    bell?.addEventListener('click', () => {
        dropdown.classList.toggle('show');
        if (dropdown.classList.contains('show')) {
            loadNotifications();
        }
    });
    
    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!bell?.contains(e.target) && !dropdown?.contains(e.target)) {
            dropdown?.classList.remove('show');
        }
    });
}

async function loadNotifications() {
    const container = document.getElementById('notification-list');
    if (!container) return;
    
    try {
        const response = await fetch('/api/admin/notifications');
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to load notifications');
        }
        
        if (!data.notifications || data.notifications.length === 0) {
            container.innerHTML = '<div class="empty-state" style="padding: 30px;"><p>No notifications</p></div>';
            return;
        }
        
        let html = '';
        data.notifications.forEach(notif => {
            const unreadClass = notif.is_read ? '' : 'unread';
            const time = new Date(notif.created_at).toLocaleString();
            
            html += `<div class="notification-item ${unreadClass}" data-id="${notif.id}">`;
            html += `<div class="notification-title">${notif.title}</div>`;
            html += `<div class="notification-message">${notif.message}</div>`;
            html += `<div class="notification-time">${time}</div>`;
            html += '</div>';
        });
        
        container.innerHTML = html;
        
        // Add click handlers to mark as read
        container.querySelectorAll('.notification-item').forEach(item => {
            item.addEventListener('click', async () => {
                const id = item.dataset.id;
                if (item.classList.contains('unread')) {
                    await markNotificationRead(id);
                    item.classList.remove('unread');
                    
                    // Update badge
                    const badge = document.getElementById('notification-badge');
                    const count = parseInt(badge.textContent) - 1;
                    if (count > 0) {
                        badge.textContent = count;
                    } else {
                        badge.style.display = 'none';
                    }
                }
            });
        });
        
    } catch (error) {
        console.error('Error loading notifications:', error);
        container.innerHTML = '<div class="empty-state" style="padding: 30px;"><p>Error loading notifications</p></div>';
    }
}

async function markNotificationRead(id) {
    try {
        await fetch(`/api/admin/notifications/${id}/mark-read`, {
            method: 'PUT'
        });
    } catch (error) {
        console.error('Error marking notification as read:', error);
    }
}

// ============================================
// Export
// ============================================

function setupExport() {
    document.getElementById('export-csv-btn')?.addEventListener('click', () => {
        exportData('csv');
    });
    
    document.getElementById('export-json-btn')?.addEventListener('click', () => {
        exportData('json');
    });
}

function exportData(format) {
    const params = new URLSearchParams({
        format: format,
        ...currentFilters
    });
    
    // Trigger download
    window.location.href = `/api/admin/analytics/export/queries?${params}`;
}

// ============================================
// Maintenance
// ============================================

function setupMaintenance() {
    document.getElementById('run-cleanup-btn')?.addEventListener('click', async () => {
        const btn = document.getElementById('run-cleanup-btn');
        const result = document.getElementById('maintenance-result');
        
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running...';
        
        try {
            const response = await fetch('/api/admin/maintenance/cleanup', {
                method: 'POST'
            });
            const data = await response.json();
            
            if (response.ok) {
                result.innerHTML = '<div class="badge badge-success">✓ Cleanup completed successfully</div>';
            } else {
                result.innerHTML = `<div class="badge badge-danger">✗ ${data.error}</div>`;
            }
        } catch (error) {
            result.innerHTML = '<div class="badge badge-danger">✗ Cleanup failed</div>';
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-trash-alt"></i> Run Cleanup (Delete Expired Data)';
        }
    });
    
    document.getElementById('run-aggregate-btn')?.addEventListener('click', async () => {
        const btn = document.getElementById('run-aggregate-btn');
        const result = document.getElementById('maintenance-result');
        
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running...';
        
        try {
            const response = await fetch('/api/admin/maintenance/aggregate', {
                method: 'POST'
            });
            const data = await response.json();
            
            if (response.ok) {
                result.innerHTML = '<div class="badge badge-success">✓ Aggregation completed successfully</div>';
            } else {
                result.innerHTML = `<div class="badge badge-danger">✗ ${data.error}</div>`;
            }
        } catch (error) {
            result.innerHTML = '<div class="badge badge-danger">✗ Aggregation failed</div>';
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-chart-pie"></i> Run Aggregation (Compute Daily Summary)';
        }
    });
}

// ============================================
// Sidebar
// ============================================

function setupSidebar() {
    const adminSidebar = document.getElementById('admin-sidebar');
    const adminRobotExpandBtn = document.getElementById('admin-robot-expand-btn');
    const adminSidebarCollapseBtn = document.getElementById('admin-sidebar-collapse-btn');
    
    // Load sidebar state from localStorage
    const sidebarState = localStorage.getItem('adminSidebarCollapsed');
    if (sidebarState === 'false') {
        adminSidebar.classList.remove('collapsed');
    }
    
    // Event listeners
    if (adminRobotExpandBtn) {
        adminRobotExpandBtn.addEventListener('click', expandAdminSidebar);
    }
    if (adminSidebarCollapseBtn) {
        adminSidebarCollapseBtn.addEventListener('click', collapseAdminSidebar);
    }
}

function expandAdminSidebar() {
    const adminSidebar = document.getElementById('admin-sidebar');
    adminSidebar.classList.remove('collapsed');
    localStorage.setItem('adminSidebarCollapsed', 'false');
}

function collapseAdminSidebar() {
    const adminSidebar = document.getElementById('admin-sidebar');
    adminSidebar.classList.add('collapsed');
    localStorage.setItem('adminSidebarCollapsed', 'true');
}

// ============================================
// Utilities
// ============================================

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
