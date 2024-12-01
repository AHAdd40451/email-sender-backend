import config from './config.js';
const { API_BASE_URL } = config;

// Initialize background service
chrome.runtime.onInstalled.addListener(() => {
    console.log('Background service worker installed');
});

// Listen for messages from popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    switch (message.type) {
        case 'GET_CONNECTION_STATUS':
            sendResponse({ status: 'success' });
            break;
    }
    return true;
});

function logInfo(...args) {
    console.log('[Background]', ...args);
}

function logWarning(...args) {
    console.warn('[Background]', ...args);
}

function logError(...args) {
    console.error('[Background]', ...args);
}

async function storeLogs(logEntry) {
    try {
        const { logs = [] } = await chrome.storage.local.get('logs');
        logs.unshift(logEntry);
        
        // Keep only last 1000 logs
        if (logs.length > 1000) {
            logs.pop();
        }
        
        await chrome.storage.local.set({ logs });
    } catch (error) {
        console.error('Error storing logs:', error);
    }
}
