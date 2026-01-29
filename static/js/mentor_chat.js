document.addEventListener('DOMContentLoaded', function() {
    const MENTORS = {
        'olyvia': { name: 'Olyvia', role: 'CFO Advisor', avatar: 'big_Olivia.png', small: 'small_Olivia.png', tiny: 'tiny_Olivia.png', intro: "Greetings Tim, Olivia here as your CFO advisor. My expertise lies in conservative online arbitrage, business scaling, and Amazon operations—always prioritizing high margins and minimal exposure." },
        'joel': { name: 'Joel', role: 'The Flipper', avatar: 'big_Joel.png', small: 'small_Joel.png', tiny: 'tiny_Joel.png', intro: "Yo Tim! My name is Joel, I'll be your mentor today. I'm pumped to help you spot fast-turn deals, crush velocity, and get you in/out quick on Amazon arbitrage. Ask away—let's move product!" },
        'evelyn': { name: 'Evelyn', role: 'The Professor', avatar: 'big_Evelyn.png', small: 'small_Evelyn.png', tiny: 'tiny_Evelyn.png', intro: "Hello Tim, I'm Evelyn, your professorial mentor in online arbitrage. Allow me to explain concepts like market volatility and profit curves to build your knowledge in business development and Amazon Seller Central." },
        'errol': { name: 'Errol', role: 'The Quant', avatar: 'big_Errol.png', small: 'small_Errol.png', tiny: 'tiny_Errol.png', intro: "Hi Tim, I'm Errol, your Quant mentor. I live in the numbers: velocity stats, margin probabilities, historical patterns, Amazon data. I'll give you clean, objective recs backed by hard metrics. Ready when you are." }
    };

    // State
    let currentMentorKey = localStorage.getItem('agent_mentor');
    if (!currentMentorKey || !MENTORS[currentMentorKey]) {
        const keys = Object.keys(MENTORS);
        currentMentorKey = keys[Math.floor(Math.random() * keys.length)];
        localStorage.setItem('agent_mentor', currentMentorKey);
    }

    // DOM Elements
    const chatOverlay = document.getElementById('mentor-chat-overlay');
    const toggleLink = document.getElementById('mentor-link');
    const closeBtn = chatOverlay ? chatOverlay.querySelector('.close-overlay') : null;
    const chatBody = document.getElementById('chat-messages-area');
    const chatInput = document.getElementById('chat-input-field');
    const sendBtn = document.getElementById('chat-send-btn');

    // Mentor Profile DOM
    const mentorAvatarBig = document.getElementById('mentor-profile-avatar');
    const mentorIntroText = document.getElementById('mentor-intro-text');
    const mentorChoiceRow = document.getElementById('mentor-choice-row');

    function updateMentorUI() {
        if (!MENTORS[currentMentorKey]) return;
        const m = MENTORS[currentMentorKey];

        // Update Big Profile
        if (mentorAvatarBig) mentorAvatarBig.src = `/static/${m.avatar}`;
        if (mentorIntroText) mentorIntroText.textContent = m.intro;

        // Update Choice Row (Show everyone BUT current)
        if (mentorChoiceRow) {
            mentorChoiceRow.innerHTML = '';
            Object.keys(MENTORS).forEach(key => {
                if (key === currentMentorKey) return; // Skip current
                const other = MENTORS[key];
                const img = document.createElement('img');
                img.src = `/static/${other.tiny}`;
                img.className = 'mentor-choice-tiny';
                img.title = other.name;
                img.onclick = () => switchMentor(key);
                mentorChoiceRow.appendChild(img);
            });
        }

        // Update nav icon if we want (optional, not in spec but good for consistency)
        // const navIcon = toggleLink.querySelector('img');
        // if(navIcon) navIcon.src = `/static/${m.tiny}`;
    }

    function switchMentor(newKey) {
        currentMentorKey = newKey;
        localStorage.setItem('agent_mentor', currentMentorKey);
        updateMentorUI();

        // Trigger event for other components (like Deal Overlay) to update
        window.dispatchEvent(new CustomEvent('mentorChanged', { detail: { mentor: newKey } }));
    }

    // Listen for external updates (e.g. from Deal Overlay)
    window.addEventListener('mentorChanged', (e) => {
        if (e.detail.mentor && e.detail.mentor !== currentMentorKey) {
            currentMentorKey = e.detail.mentor;
            updateMentorUI();
        }
    });

    // Chat Logic
    function appendMessage(text, isUser) {
        if (!chatBody) return;
        const msgDiv = document.createElement('div');
        msgDiv.className = isUser ? 'chat-message user-message' : 'chat-message mentor-message';

        const avatar = document.createElement('img');
        avatar.className = 'chat-avatar';
        if (isUser) {
            avatar.src = '/static/small_User.png'; // Blank user avatar
        } else {
            avatar.src = `/static/${MENTORS[currentMentorKey].small}`;
        }

        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble';
        bubble.textContent = text;

        // Layout: User Right, Mentor Left
        if (isUser) {
            msgDiv.appendChild(bubble);
            msgDiv.appendChild(avatar);
        } else {
            msgDiv.appendChild(avatar);
            msgDiv.appendChild(bubble);
        }

        chatBody.appendChild(msgDiv);
        chatBody.scrollTop = chatBody.scrollHeight;
    }

    function showTypingIndicator() {
        if (!chatBody) return null;
        const msgDiv = document.createElement('div');
        msgDiv.className = 'chat-message mentor-message typing-indicator-msg';

        const avatar = document.createElement('img');
        avatar.className = 'chat-avatar';
        avatar.src = `/static/${MENTORS[currentMentorKey].small}`;

        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble italic-pulse';
        bubble.innerHTML = '... Analyzing your request'; // Initial text

        msgDiv.appendChild(avatar);
        msgDiv.appendChild(bubble);
        chatBody.appendChild(msgDiv);
        chatBody.scrollTop = chatBody.scrollHeight;

        // Sequence logic
        setTimeout(() => {
            if (bubble) bubble.innerHTML = '... Identifying key details';
        }, 1500);

        return msgDiv;
    }

    async function sendChat() {
        const text = chatInput.value.trim();
        if (!text) return;

        chatInput.value = ''; // Clear input
        appendMessage(text, true);

        // API Call
        const loadingMsg = showTypingIndicator();
        const bubbleText = loadingMsg.querySelector('.chat-bubble');

        try {
            const response = await fetch('/api/mentor-chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    mentor: currentMentorKey
                })
            });
            const data = await response.json();

            // Remove loading indicator
            if (loadingMsg) loadingMsg.remove();

            if (data.reply) {
                appendMessage(data.reply, false);
            } else if (data.error) {
                appendMessage("Error: " + data.error, false);
            }
        } catch (e) {
            if (loadingMsg) loadingMsg.remove();
            appendMessage("Error communicating with mentor.", false);
            console.error(e);
        }
    }

    // Event Listeners
    if (toggleLink) {
        toggleLink.onclick = (e) => {
            e.preventDefault();
            chatOverlay.style.display = chatOverlay.style.display === 'block' ? 'none' : 'block';
            updateMentorUI(); // Ensure UI is fresh on open
        };
    }

    if (closeBtn) {
        closeBtn.onclick = () => {
            chatOverlay.style.display = 'none';
        };
    }

    if (sendBtn) {
        sendBtn.onclick = sendChat;
    }

    if (chatInput) {
        chatInput.onkeydown = (e) => {
            if (e.key === 'Enter') {
                e.preventDefault(); // Prevent submit
                // Do nothing else as per spec: "Enter button does NOT submit"
            }
        };
    }

    // Initialize
    updateMentorUI();
});
