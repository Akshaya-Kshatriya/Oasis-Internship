const API_BASE = "";
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
    if (state.displayedMessageIds.has(message.id)) {
      return; // Already displayed, skip
    }
    state.displayedMessageIds.add(message.id);
  }

  const node = elements.messageTemplate.content.firstElementChild.cloneNode(true);
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
}

async function loadRooms() {
  try {
    const rooms = await apiRequest("/rooms");
    renderRooms(rooms);
    // Only auto-select if we don't have a current room and we're not restoring a session
    if (!state.currentRoomId && rooms.length) {
      // Don't auto-select - let user choose
    }
  } catch (error) {
    showError(error.message);
  }
}

async function loadHistory(roomId) {
  try {
    const messages = await apiRequest(`/rooms/${roomId}/messages`);
    clearMessages();
    messages.forEach((message) => appendMessage(message, { suppressNotify: true }));
  } catch (error) {
    showError(error.message);
  }
}

function connectWebSocket(roomId) {
  // Don't create duplicate connections for the same room
  if (state.websocket && state.websocket.readyState === WebSocket.OPEN && state.currentRoomId === roomId) {
    return; // Already connected to this room
  }

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const host = window.location.host;
  const wsUrl = `${protocol}://${host}${WS_PATH}/${roomId}?token=${state.token}`;

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
    setConnected(true);
    clearNotificationBadge();
  });

  socket.addEventListener("message", (event) => {
    try {
      const data = JSON.parse(event.data);
      const { event: evt, payload } = data;
      if (evt === "message") {
        // Real-time message - append immediately
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
    setConnected(false);
    state.websocket = null;
    // Auto-reconnect if not a normal closure and we still have a room selected
    if (event.code !== 1000 && state.currentRoomId && state.token) {
      setTimeout(() => {
        if (state.currentRoomId && !state.websocket) {
          connectWebSocket(state.currentRoomId);
        }
      }, 3000);
    }
  });

  socket.addEventListener("error", (error) => {
    console.error("WebSocket error:", error);
    setConnected(false);
  });
}

async function selectRoom(room) {
  state.currentRoomId = room.id;
  state.currentRoomName = room.name;
  elements.roomTitle.textContent = room.name;
  elements.roomTopic.textContent = room.topic || "";
  clearNotificationBadge();
  await loadHistory(room.id);
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
    // If a room was previously selected, reconnect to it
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
    return;
  }
  state.websocket.send(JSON.stringify({ content, message_type: "text" }));
  elements.messageInput.value = "";
  elements.messageInput.focus();
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


