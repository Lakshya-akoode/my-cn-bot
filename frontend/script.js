// Generate or retrieve session ID
let sessionId = localStorage.getItem('session_id');
if (!sessionId) {
    sessionId = 'sess_' + Math.random().toString(36).substr(2, 9);
    localStorage.setItem('session_id', sessionId);
}

const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');

function addMessage(text, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', sender);

    if (sender === 'bot') {
        messageDiv.innerHTML = marked.parse(text);
    } else {
        messageDiv.textContent = text;
    }

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showTypingIndicator() {
    const indicatorDiv = document.createElement('div');
    indicatorDiv.classList.add('typing-indicator');
    indicatorDiv.id = 'typing-indicator';
    indicatorDiv.innerHTML = `
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
    `;
    chatMessages.appendChild(indicatorDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

async function sendMessage(text = null) {
    const message = text || userInput.value.trim();
    if (!message) return;

    // If triggered from button, don't clear input if it was empty, but if clicked, we just send "message"
    if (!text) userInput.value = '';

    addMessage(message, 'user');

    // Remove any existing quick actions after selection
    const existingActions = document.querySelector('.quick-actions-container');
    if (existingActions) existingActions.remove();

    showTypingIndicator(); // Show indicator

    try {
        const response = await fetch(`${process.env.BACKEND_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: message,
                session_id: sessionId
            })
        });

        removeTypingIndicator(); // Hide indicator

        if (!response.ok) {
            throw new Error('Network response was not ok');
        }

        const data = await response.json();
        addMessage(data.reply, 'bot');

        // Handle UI Actions
        if (data.ui_action === 'date_picker') {
            showDatePicker();
        }
    } catch (error) {
        removeTypingIndicator(); // Ensure indicator is hidden on error
        console.error('Error:', error);
        addMessage('Sorry, something went wrong.', 'bot');
    }
}

// Date Picker Function
function showDatePicker() {
    // Check if one already exists to avoid duplicates
    if (document.querySelector('.date-picker-container')) return;

    const container = document.createElement('div');
    container.className = 'date-picker-container';

    const input = document.createElement('input');
    input.type = 'datetime-local';
    input.className = 'date-picker-input';

    // Set min date to current time
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    input.min = now.toISOString().slice(0, 16);

    const confirmBtn = document.createElement('button');
    confirmBtn.className = 'date-picker-confirm-btn';
    confirmBtn.textContent = 'Confirm Date';

    confirmBtn.onclick = () => {
        if (!input.value) {
            alert('Please select a date and time.');
            return;
        }
        const selectedDate = new Date(input.value);
        const formattedDate = selectedDate.toLocaleString('en-US', {
            weekday: 'short',
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: 'numeric',
            minute: '2-digit'
        });

        sendMessage(formattedDate);
        container.remove();
    };

    container.appendChild(input);
    container.appendChild(confirmBtn);

    chatMessages.appendChild(container);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Quick Replies Function
function addQuickReplies(options) {
    const container = document.createElement('div');
    container.className = 'quick-actions-container';

    options.forEach(option => {
        const btn = document.createElement('button');
        btn.className = 'quick-action-btn';
        btn.textContent = option;
        btn.onclick = () => sendMessage(option);
        container.appendChild(btn);
    });

    chatMessages.appendChild(container);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

sendBtn.addEventListener('click', sendMessage);

userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

// Initial greeting
const welcomeMsg = `Hello, I am the MYCN Medical Assistant.

I can help you with:`;

addMessage(welcomeMsg, 'bot');
addQuickReplies([
    "Information about our services and treatments",
    "Doctor and clinic details",
    "Book appointment"
]);
