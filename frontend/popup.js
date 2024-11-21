const DEBUG = true;

function log(...args) {
    if (DEBUG) {
        console.log(...args);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // Tab handling
    const tabs = document.querySelectorAll('.tab-btn');
    let emailList = new Set();
    const emailListElement = document.getElementById('email-list');
    const logEntries = document.getElementById('log-entries');

    // Tab switching
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            const contents = document.querySelectorAll('.tab-content');
            contents.forEach(c => c.classList.remove('active'));
            document.getElementById(tab.dataset.tab).classList.add('active');
        });
    });

    // Email list functions
    function saveEmailList() {
        chrome.storage.local.get('emailState', (state) => {
            const currentState = state.emailState || {};
            currentState.emailList = Array.from(emailList);
            chrome.storage.local.set({ emailState: currentState });
        });
    }

    function loadEmailList() {
        chrome.storage.local.get('emailState', (state) => {
            if (state.emailState?.emailList) {
                emailList = new Set(state.emailState.emailList);
                updateEmailList();
            }
        });
    }

    function addEmail(email) {
        if (email && !emailList.has(email)) {
            emailList.add(email);
            updateEmailList();
            saveEmailList();
        }
    }

    function removeEmail(email) {
        emailList.delete(email);
        updateEmailList();
        saveEmailList();
    }

    function updateEmailList() {
        emailListElement.innerHTML = '';
        emailList.forEach(email => {
            const div = document.createElement('div');
            div.className = 'email-item';
            div.innerHTML = `
                <span>${email}</span>
                <button class="delete-btn">Delete</button>
            `;
            div.querySelector('.delete-btn').addEventListener('click', () => removeEmail(email));
            emailListElement.appendChild(div);
        });
    }

    // Add email button
    document.getElementById('add-email').addEventListener('click', () => {
        const email = prompt('Enter email address:');
        if (email) addEmail(email);
    });

    // Import CSV
    document.getElementById('import-csv').addEventListener('click', () => {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.csv';
        input.onchange = e => {
            const file = e.target.files[0];
            const reader = new FileReader();
            reader.onload = event => {
                const text = event.target.result;
                const rows = text.split('\n');
                rows.forEach(row => {
                    const email = row.trim();
                    if (email && email !== 'email') addEmail(email);
                });
            };
            reader.readAsText(file);
        };
        input.click();
    });

    // Export CSV
    document.getElementById('export-csv').addEventListener('click', () => {
        const csv = Array.from(emailList).join('\n');
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'email_list.csv';
        a.click();
    });

    // Save settings
    document.getElementById('save-settings').addEventListener('click', () => {
        saveInputValues();
        showStatus('Settings saved successfully!');
    });

    // Send emails
    document.getElementById('send-emails').addEventListener('click', async () => {
        if (emailList.size === 0) {
            showStatus('Please add some email addresses first!');
            return;
        }

        addLogEntry('Starting new email process...', 'info');
        
        const settings = await chrome.storage.local.get('emailState');
        const config = {
            ...settings.emailState?.inputValues,
            emailList: Array.from(emailList),
            emailSubject: document.getElementById('email-subject').value,
            emailTemplate: document.getElementById('email-body').value
        };

        showStatus('Starting email process...');
        updateProgress(0);
        
        try {
            const response = await fetch('https://email-sender-backend-dyxz.onrender.com/send-emails', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(config)
            });

            const result = await response.json();
            showStatus(result.message);
            updateProgress(100);

        } catch (error) {
            showStatus(`Error: ${error.message}`);
            addLogEntry(`Error: ${error.message}`, 'error');
        }
    });

    // Helper functions
    function showStatus(message) {
        document.getElementById('status').textContent = message;
    }

    function updateProgress(percent) {
        document.querySelector('.progress-fill').style.width = `${percent}%`;
    }

    // Initialize Socket.IO connection
    async function initializeSocketAndLogs() {
        log('Initializing socket connection...');
        
        await loadExistingLogs();

        const socket = io('https://email-sender-backend-dyxz.onrender.com', {
            transports: ['polling'],
            upgrade: false,
            reconnection: true,
            reconnectionAttempts: 5,
            reconnectionDelay: 1000,
            path: '/socket.io/',
            withCredentials: false,
        });

        socket.on('connect', () => {
            log('Socket connected successfully');
            console.log('Connected to server');
            addLogEntry('Connected to server', 'info');
            showStatus('Connected to server');
        });

        socket.on('connect_error', (error) => {
            log('Socket connection error:', error);
            console.error('Connection error:', error);
            addLogEntry(`Connection error: ${error.message}`, 'error');
            showStatus(`Connection error: ${error.message}`);
        });

        socket.on('log_update', (log) => {
            console.log('Received log:', log);
            const entry = document.createElement('div');
            entry.className = `log-entry ${log.type}`;
            const timestamp = new Date(log.timestamp).toLocaleTimeString();
            entry.textContent = `[${timestamp}] ${log.message}`;
            logEntries.appendChild(entry);
            logEntries.scrollTop = logEntries.scrollHeight;
        });

        socket.on('disconnect', () => {
            console.log('Disconnected from server');
            addLogEntry('Disconnected from server', 'warning');
        });

        socket.on('reconnect', (attemptNumber) => {
            console.log('Reconnected to server');
            addLogEntry('Reconnected to server', 'info');
        });

        socket.on('error', (error) => {
            console.error('Socket error:', error);
            addLogEntry('Socket error: ' + error.message, 'error');
        });

        return socket;
    }

    function addLogEntry(message, level = 'info') {
        const entry = document.createElement('div');
        entry.className = `log-entry ${level}`;
        const timestamp = new Date().toLocaleTimeString();
        entry.textContent = `[${timestamp}] ${message}`;
        
        logEntries.appendChild(entry);
        logEntries.scrollTop = logEntries.scrollHeight;
    }

    document.getElementById('clear-logs').addEventListener('click', async () => {
        try {
            const logEntries = document.getElementById('log-entries');
            logEntries.innerHTML = '';
            
            await fetch('https://email-sender-backend-dyxz.onrender.com/clear-logs', { 
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const entry = document.createElement('div');
            entry.className = 'log-entry info';
            entry.textContent = 'Logs cleared';
            logEntries.appendChild(entry);
        } catch (error) {
            console.error('Error clearing logs:', error);
            const entry = document.createElement('div');
            entry.className = 'log-entry error';
            entry.textContent = 'Failed to clear logs';
            logEntries.appendChild(entry);
        }
    });

    async function loadExistingLogs() {
        try {
            logEntries.innerHTML = '';
            
            const response = await fetch('https://email-sender-backend-dyxz.onrender.com/get-logs');
            const result = await response.json();
            
            if (result.logs) {
                result.logs.forEach(log => {
                    const entry = document.createElement('div');
                    entry.className = `log-entry ${log.type}`;
                    const timestamp = new Date(log.timestamp).toLocaleTimeString();
                    entry.textContent = `[${timestamp}] ${log.message}`;
                    logEntries.appendChild(entry);
                });
                
                logEntries.scrollTop = logEntries.scrollHeight;
            }
        } catch (error) {
            console.error('Error loading logs:', error);
            addLogEntry('Failed to load server logs', 'error');
        }
    }

    function saveInputValues() {
        chrome.storage.local.get('emailState', (state) => {
            const currentState = state.emailState || {};
            currentState.inputValues = {
                smtpServer: document.getElementById('smtp-server').value,
                smtpPort: document.getElementById('smtp-port').value,
                username: document.getElementById('username').value,
                password: document.getElementById('password').value,
                senderName: document.getElementById('sender-name').value,
                delay: document.getElementById('delay').value,
                emailSubject: document.getElementById('email-subject').value,
                emailTemplate: document.getElementById('email-body').value
            };
            chrome.storage.local.set({ emailState: currentState });
        });
    }

    function loadInputValues() {
        chrome.storage.local.get('emailState', (state) => {
            if (state.emailState?.inputValues) {
                const values = state.emailState.inputValues;
                document.getElementById('smtp-server').value = values.smtpServer || '';
                document.getElementById('smtp-port').value = values.smtpPort || '';
                document.getElementById('username').value = values.username || '';
                document.getElementById('password').value = values.password || '';
                document.getElementById('sender-name').value = values.senderName || '';
                document.getElementById('delay').value = values.delay || '';
                document.getElementById('email-subject').value = values.emailSubject || '';
                document.getElementById('email-body').value = values.emailTemplate || '';
            }
        });
    }

    // Initialize
    loadInputValues();
    loadEmailList();
    initializeSocketAndLogs();
});