const API_BASE = "http://localhost:8000";
const WS_PATH = "/ws/rooms";
const STORAGE_TOKEN_KEY = "secure-chat-token";
const STORAGE_USER_KEY = "secure-chat-username";

const state = {
  token: null,
  username: null,
  currentRoomId: null,
  currentRoomName: "",
  websocket: null,
  displayedMessageIds: new Set(), // Track displayed messages to prevent duplicates
  recentSystemMessages: new Map(), // Track recent system messages to prevent duplicates
};

const elements = {
  authPanel: document.getElementById("auth-panel"),
  roomsPanel: document.getElementById("rooms-panel"),
  loginForm: document.getElementById("login-form"),
  registerForm: document.getElementById("register-form"),
  logoutBtn: document.getElementById("logout-btn"),
  loginUsername: document.getElementById("login-username"),
  loginPassword: document.getElementById("login-password"),
  registerUsername: document.getElementById("register-username"),
  registerPassword: document.getElementById("register-password"),
  roomsList: document.getElementById("rooms-list"),
  roomTitle: document.getElementById("room-title"),
  roomTopic: document.getElementById("room-topic"),
  connectionStatus: document.getElementById("connection-status"),
  messages: document.getElementById("messages"),
  messageTemplate: document.getElementById("message-template"),
  messageForm: document.getElementById("message-form"),
  messageInput: document.getElementById("message-input"),
  fileInput: document.getElementById("file-input"),
  fileBtn: document.getElementById("file-btn"),
  emojiBtn: document.getElementById("emoji-btn"),
  emojiPicker: document.getElementById("emoji-picker"),
  activeUsername: document.getElementById("active-username"),
};

const emojiSet = [
  "😀","😁","😂","🤣","😅","😊","😍","😘","😎","🤩","🥳","🤔","🤨","😴","😇","🙃","🤯","😱",
  "😭","😡","👍","👎","🙏","👏","💪","🔥","✨","🎉","🚀","❤️","🧡","💛","💚","💙","💜","🤍","🤎",
  "💡","📚","🧠","💬","🎧","🖥️","📱","📝","📎","📷","🎥","🎮","🍕","☕","🌟","✅","❗","⚠️","⏰"
];

function notify(message) {
  if (typeof Notification === "undefined") return;
  if (!document.hidden) return;

  if (Notification.permission === "granted") {
    new Notification("New message", { body: message });
  } else if (Notification.permission !== "denied") {
    Notification.requestPermission();
  }
  document.title = "🔔 " + state.currentRoomName;
}

function clearNotificationBadge() {
  document.title = "Secure Chat";
}

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    clearNotificationBadge();
  }
});

async function apiRequest(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const headers = options.headers ? { ...options.headers } : {};
  if (state.token) {
    headers.Authorization = `Bearer ${state.token}`;
  }
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(url, { ...options, headers });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    // Handle FastAPI validation errors (422)
    if (response.status === 422 && errorData.detail) {
      const errors = Array.isArray(errorData.detail)
        ? errorData.detail.map((e) => `${e.loc.join(".")}: ${e.msg}`).join(", ")
        : errorData.detail;
      throw new Error(errors || "Validation error");
    }
    throw new Error(errorData.detail || `Request failed: ${response.status}`);
  }
  return response.status === 204 ? null : await response.json();
}

function showError(message) {
  elements.connectionStatus.textContent = message;
  elements.connectionStatus.classList.remove("online");
  elements.connectionStatus.classList.add("offline");
}

function setConnected(connected) {
  elements.connectionStatus.textContent = connected ? "Online" : "Offline";
  elements.connectionStatus.classList.toggle("online", connected);
  elements.connectionStatus.classList.toggle("offline", !connected);
}

function togglePanels(isAuthenticated) {
  elements.authPanel.classList.toggle("hidden", isAuthenticated);
  elements.roomsPanel.classList.toggle("hidden", !isAuthenticated);
}

function renderEmojiPicker() {
  elements.emojiPicker.innerHTML = "";
  emojiSet.forEach((emoji) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = emoji;
    btn.addEventListener("click", () => {
      elements.messageInput.value += emoji;
      elements.messageInput.focus();
    });
    elements.emojiPicker.appendChild(btn);
  });
}

function renderRooms(rooms) {
  elements.roomsList.innerHTML = "";
  rooms.forEach((room) => {
    const li = document.createElement("li");
    li.textContent = room.name;
    li.dataset.roomId = room.id;
    li.addEventListener("click", () => selectRoom(room));
    if (state.currentRoomId === room.id) {
      li.classList.add("active");
    }
    elements.roomsList.appendChild(li);
  });
}

function appendMessage(message, { suppressNotify = false } = {}) {
  // For non-system messages, check if we've already displayed this message
  if (message.id && message.message_type !== "system") {
    // Convert message.id to string for comparison
    const messageIdStr = String(message.id);
    const isTempMessage = messageIdStr.startsWith("temp-");
    
    // Skip if already displayed (unless it's a temp message)
    if (!isTempMessage && state.displayedMessageIds.has(message.id)) {
      return; // Already displayed, skip
    }
    // If we have a temp message with same content from same user, remove it
    if (!isTempMessage) {
      const tempMessages = elements.messages.querySelectorAll(`[data-message-id^="temp-"]`);
      tempMessages.forEach(tempMsg => {
        const tempContent = tempMsg.querySelector(".message-body")?.textContent?.trim();
        const tempAuthor = tempMsg.querySelector(".message-author")?.textContent?.trim();
        if (tempContent === message.content && tempAuthor === message.username) {
          tempMsg.remove();
        }
      });
    }
    state.displayedMessageIds.add(message.id);
  }

  const node = elements.messageTemplate.content.firstElementChild.cloneNode(true);
  // Add data attribute for message ID to help with optimistic updates
  if (message.id) {
    node.setAttribute("data-message-id", String(message.id));
  }
  const author = node.querySelector(".message-author");
  const time = node.querySelector(".message-time");
  const body = node.querySelector(".message-body");

  if (message.message_type === "system") {
    node.classList.add("system-message");
    author.textContent = "System";
    time.textContent = "";
    body.textContent = message.content;
  } else {
    author.textContent = message.username;
    time.textContent = new Date(message.created_at).toLocaleTimeString();
    switch (message.message_type) {
      case "image": {
        body.innerHTML = `
          <div>${message.content || ""}</div>
          <img src="${message.file_url}" alt="${message.content || "image"}" />
        `;
        break;
      }
      case "video": {
        body.innerHTML = `
          <div>${message.content || ""}</div>
          <video controls src="${message.file_url}"></video>
        `;
        break;
      }
      case "file": {
        body.innerHTML = `
          <div>${message.content || ""}</div>
          <a href="${message.file_url}" target="_blank" rel="noopener">Download</a>
        `;
        break;
      }
      default: {
        body.textContent = message.content;
      }
    }
  }

  elements.messages.appendChild(node);
  elements.messages.scrollTo({
    top: elements.messages.scrollHeight,
    behavior: "smooth",
  });

  if (
    !suppressNotify &&
    message.username &&
    message.username !== state.username &&
    message.message_type !== "system"
  ) {
    notify(`${message.username}: ${message.content || message.message_type}`);
  }
}

function clearMessages() {
  elements.messages.innerHTML = "";
  state.displayedMessageIds.clear(); // Clear tracked message IDs when clearing messages
  state.recentSystemMessages.clear(); // Also clear system message tracking
}

async function loadRooms() {
  try {
    const rooms = await apiRequest("/rooms");
    renderRooms(rooms);
    // Auto-select General room if no room is currently selected
    if (!state.currentRoomId && rooms.length) {
      const generalRoom = rooms.find(room => room.name.toLowerCase() === "general") || rooms[0];
      if (generalRoom) {
        await selectRoom(generalRoom);
      }
    }
  } catch (error) {
    showError(error.message);
  }
}

async function loadHistory(roomId) {
  try {
    console.log("Loading message history for room:", roomId);
    const messages = await apiRequest(`/rooms/${roomId}/messages`);
    console.log("Loaded messages:", messages.length);
    clearMessages();
    messages.forEach((message) => {
      appendMessage(message, { suppressNotify: true });
    });
  } catch (error) {
    console.error("Error loading history:", error);
    showError(error.message);
  }
}

function connectWebSocket(roomId) {
  // Don't create duplicate connections for the same room
  if (state.websocket && state.websocket.readyState === WebSocket.OPEN && state.currentRoomId === roomId) {
    return; // Already connected to this room
  }

  // Check if we have a token
  if (!state.token) {
    console.error("Cannot connect WebSocket: No authentication token");
    showError("Not authenticated. Please log in again.");
    return;
  }

  // Use API_BASE to construct WebSocket URL (backend host, not frontend host)
  const apiUrl = new URL(API_BASE);
  const protocol = apiUrl.protocol === "https:" ? "wss" : "ws";
  const host = apiUrl.host;
  const wsUrl = `${protocol}://${host}${WS_PATH}/${roomId}?token=${state.token}`;

  console.log("Connecting to WebSocket:", wsUrl.replace(state.token, "***"));

  // Close existing connection if any
  if (state.websocket) {
    state.websocket.removeEventListener("open", () => {});
    state.websocket.removeEventListener("message", () => {});
    state.websocket.removeEventListener("close", () => {});
    state.websocket.removeEventListener("error", () => {});
    state.websocket.close();
    state.websocket = null;
  }

  const socket = new WebSocket(wsUrl);
  state.websocket = socket;

  socket.addEventListener("open", () => {
    console.log("WebSocket connected successfully");
    setConnected(true);
    clearNotificationBadge();
  });

  socket.addEventListener("message", (event) => {
    try {
      const data = JSON.parse(event.data);
      console.log("WebSocket message received:", data);
      const { event: evt, payload } = data;
      if (evt === "message") {
        // Real-time message - append immediately
        // This will replace any optimistic message with the same content
        console.log("Appending real-time message:", payload);
        appendMessage(payload);
      } else if (evt === "system") {
        // Prevent duplicate system messages within 2 seconds
        const msgKey = payload.message;
        const now = Date.now();
        const lastTime = state.recentSystemMessages.get(msgKey);
        
        if (!lastTime || (now - lastTime) > 2000) {
          state.recentSystemMessages.set(msgKey, now);
          // Clean up old entries (older than 5 seconds)
          for (const [key, time] of state.recentSystemMessages.entries()) {
            if (now - time > 5000) {
              state.recentSystemMessages.delete(key);
            }
          }
          
          appendMessage({
            message_type: "system",
            content: payload.message,
            created_at: new Date().toISOString(),
            username: "system",
          });
        }
      } else if (evt === "error") {
        showError(payload.message);
      }
    } catch (err) {
      console.error("Failed to parse message", err);
    }
  });

  socket.addEventListener("close", (event) => {
    console.log("WebSocket closed:", event.code, event.reason);
    setConnected(false);
    state.websocket = null;
    
    // Show error message for specific close codes
    if (event.code === 1008) {
      showError("Authentication failed. Please log in again.");
    } else if (event.code !== 1000) {
      showError(`Connection closed (code: ${event.code})`);
    }
    
    // Auto-reconnect if not a normal closure and we still have a room selected
    if (event.code !== 1000 && state.currentRoomId && state.token) {
      console.log("Attempting to reconnect in 3 seconds...");
      setTimeout(() => {
        if (state.currentRoomId && !state.websocket) {
          connectWebSocket(state.currentRoomId);
        }
      }, 3000);
    }
  });

  socket.addEventListener("error", (error) => {
    console.error("WebSocket error:", error);
    console.error("WebSocket URL was:", wsUrl.replace(state.token, "***"));
    setConnected(false);
    showError("WebSocket connection error. Check console for details.");
  });
}

async function selectRoom(room) {
  console.log("Selecting room:", room);
  state.currentRoomId = room.id;
  state.currentRoomName = room.name;
  elements.roomTitle.textContent = room.name;
  elements.roomTopic.textContent = room.topic || "";
  clearNotificationBadge();
  await loadHistory(room.id);
  console.log("Connecting WebSocket for room:", room.id, "with token:", state.token ? "present" : "missing");
  connectWebSocket(room.id);

  document
    .querySelectorAll("#rooms-list li")
    .forEach((li) => li.classList.toggle("active", Number(li.dataset.roomId) === room.id));
}

async function handleAuth({ username, password }, isRegister = false) {
  // Validate input
  if (!username || !password) {
    throw new Error("Username and password are required");
  }
  
  if (isRegister) {
    if (username.length < 3 || username.length > 50) {
      throw new Error("Username must be between 3 and 50 characters");
    }
    if (password.length < 8 || password.length > 64) {
      throw new Error("Password must be between 8 and 64 characters");
    }
  }
  
  const path = isRegister ? "/auth/register" : "/auth/login";
  const payload = { username: username.trim(), password };
  
  try {
    const response = await apiRequest(path, {
      method: "POST",
      body: JSON.stringify(payload),
    });

    if (!isRegister) {
      state.token = response.access_token;
      state.username = username.trim();
      localStorage.setItem(STORAGE_TOKEN_KEY, state.token);
      localStorage.setItem(STORAGE_USER_KEY, state.username);
      elements.activeUsername.textContent = state.username;
      togglePanels(true);
      await loadRooms();
    } else {
      alert("Registration successful. You can sign in now.");
    }
  } catch (error) {
    throw error;
  }
}

async function restoreSession() {
  const savedToken = localStorage.getItem(STORAGE_TOKEN_KEY);
  const savedUser = localStorage.getItem(STORAGE_USER_KEY);
  if (savedToken && savedUser) {
    state.token = savedToken;
    state.username = savedUser;
    elements.activeUsername.textContent = savedUser;
    togglePanels(true);
    await loadRooms();
    // loadRooms will auto-select General if no room is selected
    // After loadRooms, check if a room was selected and load its history
    if (state.currentRoomId) {
      await loadHistory(state.currentRoomId);
      connectWebSocket(state.currentRoomId);
    }
  }
}

async function handleMessageSubmit(event) {
  event.preventDefault();
  const content = elements.messageInput.value.trim();
  if (!content || !state.websocket || state.websocket.readyState !== WebSocket.OPEN) {
    if (!state.websocket || state.websocket.readyState !== WebSocket.OPEN) {
      showError("Not connected. Please wait for connection...");
    }
    return;
  }
  
  // Clear input immediately for better UX
  elements.messageInput.value = "";
  elements.messageInput.focus();
  
  // Optimistically show the message immediately (will be replaced by server response)
  const tempId = `temp-${Date.now()}`;
  const optimisticMessage = {
    id: tempId,
    room_id: state.currentRoomId,
    user_id: null,
    username: state.username,
    content: content,
    message_type: "text",
    file_url: null,
    mime_type: null,
    created_at: new Date().toISOString(),
  };
  appendMessage(optimisticMessage, { suppressNotify: true });
  
  // Send to server
  try {
    state.websocket.send(JSON.stringify({ content, message_type: "text" }));
  } catch (error) {
    console.error("Error sending message:", error);
    showError("Failed to send message. Please try again.");
    // Remove optimistic message on error
    const messageElement = elements.messages.querySelector(`[data-message-id="${tempId}"]`);
    if (messageElement) {
      messageElement.remove();
    }
  }
}

async function handleFileUpload(file) {
  if (!file || !state.currentRoomId) return;
  const formData = new FormData();
  formData.append("file", file);

  try {
    await apiRequest(`/rooms/${state.currentRoomId}/upload`, {
      method: "POST",
      body: formData,
      headers: {},
    });
  } catch (error) {
    showError(error.message);
  }
}

elements.loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const username = elements.loginUsername.value;
  const password = elements.loginPassword.value;
  try {
    await handleAuth({ username, password }, false);
    event.target.reset();
  } catch (error) {
    showError(error.message);
  }
});

elements.registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const username = elements.registerUsername.value;
  const password = elements.registerPassword.value;
  try {
    await handleAuth({ username, password }, true);
    event.target.reset();
  } catch (error) {
    showError(error.message);
  }
});

elements.logoutBtn.addEventListener("click", () => {
  state.token = null;
  state.username = null;
  state.currentRoomId = null;
  state.currentRoomName = "";
  if (state.websocket) {
    state.websocket.close();
    state.websocket = null;
  }
  localStorage.removeItem(STORAGE_TOKEN_KEY);
  localStorage.removeItem(STORAGE_USER_KEY);
  togglePanels(false);
  clearMessages();
  setConnected(false);
  elements.roomTitle.textContent = "Select a room to start chatting";
  elements.roomTopic.textContent = "";
});

elements.messageForm.addEventListener("submit", handleMessageSubmit);

elements.messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.messageForm.dispatchEvent(new Event("submit"));
  }
});

elements.fileBtn.addEventListener("click", () => elements.fileInput.click());
elements.fileInput.addEventListener("change", async (event) => {
  const file = event.target.files[0];
  await handleFileUpload(file);
  elements.fileInput.value = "";
});

elements.emojiBtn.addEventListener("click", () => {
  elements.emojiPicker.classList.toggle("hidden");
});

document.addEventListener("click", (event) => {
  if (
    !elements.emojiPicker.classList.contains("hidden") &&
    !elements.emojiPicker.contains(event.target) &&
    event.target !== elements.emojiBtn
  ) {
    elements.emojiPicker.classList.add("hidden");
  }
});

renderEmojiPicker();
restoreSession();

if ("Notification" in window && Notification.permission === "default") {
  Notification.requestPermission();
}


