import config from './config.js';
const { API_BASE_URL } = config;

// Initialize background service
chrome.runtime.onInstalled.addListener(() => {
    console.log('Background service worker installed');
});

// Listen for messages from popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log('Received message:', message);

    switch (message.type) {
        case 'GET_CONNECTION_STATUS':
            sendResponse({ status: 'success' });
            break;
    }

    if (message.action === 'sendEmails') {
        console.log('Handling sendEmails action with data:', message.data);
        handleEmailSending(message.data);
        return true;
    }
    
    if (message.action === 'getStatus') {
        sendResponse(sendingStatus);
        return false;
    }

    if (message.action === 'cancelSending') {
        if (currentEmailRequest) {
            currentEmailRequest.abort();
            currentEmailRequest = null;
            updateStatus({
                isLoading: false,
                error: 'Email sending cancelled'
            });
        }
        return false;
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

let currentEmailRequest = null;
let sendingStatus = {
    isLoading: false,
    progress: null,
    error: null
};

function updateStatus(newStatus) {
    sendingStatus = { ...sendingStatus, ...newStatus };
    // Notify popup about status change
    chrome.runtime.sendMessage({
        action: 'statusUpdate',
        status: sendingStatus
    });
}

async function handleEmailSending(data) {
    try {
        console.log('Starting email send with data:', data);
        if (!data || !data.token) {
            throw new Error('Missing required data or token');
        }

        updateStatus({
            isLoading: true,
            progress: 'Starting email send...',
            error: null
        });

        const controller = new AbortController();
        currentEmailRequest = controller;

        console.log('Sending request to:', `${API_BASE_URL}/send-emails`);
        const response = await fetch(`${API_BASE_URL}/send-emails`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${data.token}`
            },
            body: JSON.stringify({
                emails: data.emails,
                subject: data.subject,
                body: data.body,
                attachments: data.attachments
            }),
            signal: controller.signal
        });

        console.log('Response received:', response.status);
        const responseData = await response.json();
        console.log('Response data:', responseData);

        if (!response.ok) {
            throw new Error(responseData.message || 'Failed to send emails');
        }

        updateStatus({
            isLoading: false,
            progress: responseData.message,
            error: null
        });

    } catch (error) {
        console.error('Error sending emails:', error);
        updateStatus({
            isLoading: false,
            progress: null,
            error: error.message
        });
    } finally {
        currentEmailRequest = null;
    }
}
