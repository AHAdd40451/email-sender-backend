
const API_BASE_URL = 'https://email-sender-backend-dyxz.onrender.com';

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

    for (const recipient of request.data.recipients) {
      if (!currentState.isRunning) break;
      
      try {
        await sendEmail(recipient, request.data);
      } catch (error) {
        currentState.stats.emailsFailed++;
        currentState.failedEmails.push({
          email: recipient,
          error: error.message,
          timestamp: new Date().toISOString()
        });
        addLog(`Failed to send to ${recipient}: ${error.message}`, 'error');
      }
    }

    currentState.isRunning = false;
    await saveState();
    sendResponse({ success: true });
  } catch (error) {
    currentState.isRunning = false;
    await saveState();
    sendResponse({ success: false, error: error.message });
  }
}

async function sendEmail(recipient, data) {
  const socket = io(`${API_BASE_URL}`, {
    transports: ['websocket'],
    upgrade: false
  });

  return new Promise((resolve, reject) => {
    socket.emit('send_email', {
      recipient,
      senderName: data.senderName || 'Default Sender',
      subject: data.subject,
      body: data.body,
      attachments: data.attachments || [],
      ...data
    });

    socket.on('log_update', (logData) => {
      addLog(logData.message, logData.type);
    });

    socket.on('email_result', (result) => {
      if (result.status === 'success') {
        currentState.stats.emailsSent++;
        currentState.sentEmails.push(recipient);
        resolve();
      } else {
        reject(new Error(result.message || 'Failed to send email'));
      }
      socket.disconnect();
    });

    socket.on('connect_error', (error) => {
      reject(new Error('Failed to connect to server'));
      socket.disconnect();
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