import config from './config.js';
const { API_BASE_URL } = config;
const BATCH_SIZE = 25; // Optimal for Railway free tier

let currentState;

async function initializeState() {
  const state = await chrome.storage.local.get('emailState');
  if (state.emailState) {
    currentState = state.emailState;
  } else {
    currentState = {
      isRunning: false,
      logs: [],
      stats: {
        emailsSent: 0,
        emailsFailed: 0,
        totalRecipients: 0
      },
      sentEmails: [],
      failedEmails: []
    };
    await chrome.storage.local.set({ emailState: currentState });
  }
}

// Initialize state when service worker starts
chrome.runtime.onInstalled.addListener(() => {
  initializeState();
});

async function saveState() {
  await chrome.storage.local.set({ emailState: currentState });
}

function addLog(message, type = 'info') {
  const log = {
    message,
    type,
    timestamp: new Date().toISOString()
  };
  currentState.logs.push(log);
  saveState();
  chrome.runtime.sendMessage({
    action: 'newLog',
    log,
    stats: currentState.stats
  }).catch(() => {});
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'sendEmails') {
    handleSendEmails(request, sendResponse);
    return true;
  }
  if (request.action === 'stopSending') {
    handleStopSending(sendResponse);
    return true;
  }
  if (request.action === 'resetAll') {
    handleResetAll(sendResponse);
    return true;
  }
});

async function handleSendEmails(request, sendResponse) {
  try {
    currentState.isRunning = true;
    currentState.stats.totalRecipients = request.data.recipients.length;
    await saveState();

    // Create batches
    const batches = [];
    for (let i = 0; i < request.data.recipients.length; i += BATCH_SIZE) {
      batches.push(request.data.recipients.slice(i, i + BATCH_SIZE));
    }

    // Single WebSocket connection for all batches
    const socket = io(`${API_BASE_URL}`, {
      transports: ['websocket'],
      upgrade: false,
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 3
    });

    for (const batch of batches) {
      if (!currentState.isRunning) break;

      try {
        await sendEmailBatch(socket, batch, request.data);
        // Add delay between batches
        await new Promise(resolve => setTimeout(resolve, 2000));
      } catch (error) {
        console.error('Batch error:', error);
      }
    }

    socket.disconnect();
    currentState.isRunning = false;
    await saveState();
    sendResponse({ success: true });
  } catch (error) {
    currentState.isRunning = false;
    await saveState();
    sendResponse({ success: false, error: error.message });
  }
}

async function sendEmailBatch(socket, recipients, data) {
  return new Promise((resolve, reject) => {
    socket.emit('send_email_batch', {
      recipients,
      senderName: data.senderName || 'Default Sender',
      subject: data.subject,
      body: data.body,
      attachments: data.attachments || [],
      ...data
    });

    socket.on('batch_result', (result) => {
      if (result.status === 'success') {
        result.successful.forEach(email => {
          currentState.stats.emailsSent++;
          currentState.sentEmails.push(email);
        });
        result.failed.forEach(failure => {
          currentState.stats.emailsFailed++;
          currentState.failedEmails.push({
            email: failure.email,
            error: failure.error,
            timestamp: new Date().toISOString()
          });
          addLog(`Failed to send to ${failure.email}: ${failure.error}`, 'error');
        });
        resolve();
      } else {
        reject(new Error(result.message || 'Batch failed'));
      }
    });
  });
}

async function handleStopSending(sendResponse) {
  currentState.isRunning = false;
  await saveState();
  sendResponse({ 
    success: true, 
    state: {
      sentEmails: currentState.sentEmails,
      failedEmails: currentState.failedEmails,
      stats: currentState.stats
    }
  });
}

async function handleResetAll(sendResponse) {
  currentState = {
    isRunning: false,
    logs: [],
    stats: {
      emailsSent: 0,
      emailsFailed: 0,
      totalRecipients: 0
    },
    sentEmails: [],
    failedEmails: []
  };
  await saveState();
  sendResponse({ success: true });
}