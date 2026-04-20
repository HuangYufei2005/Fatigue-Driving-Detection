// utils.js - 工具函数

/**
 * 格式化时间戳
 * @returns {string} 格式：HH:MM:SS
 */
function getFormattedTime() {
    const now = new Date();
    return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
}

/**
 * 调试输出到页面
 * @param {string} message 
 */

function debugLog(message) {
    const timeStr = getFormattedTime();
    console.log(`[${timeStr}] ${message}`);
    
    // 优先使用成员1的addLog
    if (typeof window.addLog === 'function') {
        window.addLog(message, 'info');
    } else {
        // 降级：直接写入日志区
        const logContent = document.getElementById('logContent');
        if (logContent) {
            const logItem = document.createElement('div');
            logItem.className = 'log-item info';
            logItem.innerHTML = `<span class="time">[${timeStr}]</span>${message}`;
            logContent.appendChild(logItem);
            logContent.scrollTop = logContent.scrollHeight;
        }
    }
}

/**
 * Base64编码转换（用于调试）
 * @param {string} str 
 * @returns {string}
 */
function toBase64(str) {
    return btoa(unescape(encodeURIComponent(str)));
}