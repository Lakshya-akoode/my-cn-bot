// Generate a new session ID every time the page loads (including reloads)
const sessionId = 'sess_' + Math.random().toString(36).substr(2, 9);

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
        const response = await fetch(`http://64.227.171.48:8000/chat`, {
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
        
        // Business Hours Validation
        const day = selectedDate.getDay(); // 0 = Sunday, 1 = Monday, ...
        const hour = selectedDate.getHours();
        
        // Hours:
        // Mon-Wed, Fri: 10am - 5pm (17)
        // Thu: 11am - 7pm (19)
        // Sat: 9am - 3pm (15)
        // Sun: Closed

        let isOpen = false;
        let openTime = "";
        
        if (day === 0) {
            // Sunday
            isOpen = false;
            openTime = "Closed";
        } else if (day === 6) {
            // Saturday: 9-15
            isOpen = hour >= 9 && hour < 15;
            openTime = "9:00 AM - 3:00 PM";
        } else if (day === 4) {
             // Thursday: 11-19
             isOpen = hour >= 11 && hour < 19;
             openTime = "11:00 AM - 7:00 PM";
        } else {
            // Mon, Tue, Wed, Fri: 10-17
            isOpen = hour >= 10 && hour < 17;
            openTime = "10:00 AM - 5:00 PM";
        }

        if (!isOpen) {
             const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
             alert(`We are closed at that time on ${days[day]}s.\n\nBusiness Hours for ${days[day]}:\n${openTime}`);
             return;
        }

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

sendBtn.addEventListener('click', () => sendMessage());

userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

// Initial greeting
const welcomeMsg = `Hello, I am the CN Medical Assistant.

I can help you with:`;

addMessage(welcomeMsg, 'bot');
addQuickReplies([
    "Information about our services and treatments",
    "Providers and clinic details",
    "Clinic days and hours open",
    "Request appointment"
]);
