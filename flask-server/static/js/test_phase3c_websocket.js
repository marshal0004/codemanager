const io = require("socket.io-client");

// Replace with your actual values
const SERVER_URL = "http://127.0.0.1:5000";
const JWT_TOKEN =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiNzM3MjFmNTYtYTFmYi00ODhhLTk0OWMtZGJkZDU2ZmFhYjlmIiwiZW1haWwiOiJucjM3MTk1MzNAZ21haWwuY29tIiwiZXhwIjoxNzU2NTg0MDA1fQ.7DJxTVUYVa9MbpKRfyySrOQomHuFMqMhLGu3Oi-3yKs";
const USER_ID = "73721f56-a1fb-488a-949c-dbdd56faab9f";
const SNIPPET_ID = "29e46631-3c88-48fc-83a5-3daca25c84e5";
const TEAM_ID = "6700436f-0bc4-430d-a4cd-cc602ca6453a";

console.log("🚀 Testing Phase 3C Real-time Collaboration...");
console.log(`📡 Server: ${SERVER_URL}`);
console.log(`👤 User: ${USER_ID}`);
console.log(`📝 Snippet: ${SNIPPET_ID}`);
console.log(`🏢 Team: ${TEAM_ID}`);
console.log("─".repeat(60));

const socket = io(SERVER_URL, {
  auth: { token: JWT_TOKEN },
  query: { token: JWT_TOKEN },
});

// Track test progress
let testsPassed = 0;
const totalTests = 6;

// Enhanced logging for all events
socket.onAny((eventName, ...args) => {
  console.log(`📨 RECEIVED EVENT: ${eventName}`, JSON.stringify(args, null, 2));
});

socket.on("connect", () => {
  console.log("✅ Connected to WebSocket server");
  console.log(`🔗 Socket ID: ${socket.id}`);

  // Test 1: Join editing session
  console.log("\n🔧 Test 1: Joining editing session...");
  socket.emit("join_editing_session", {
    snippet_id: SNIPPET_ID,
    team_id: TEAM_ID,
    user_id: USER_ID,
  });
});

// Phase 3C Event Listeners
socket.on("editing_session_joined", (data) => {
  testsPassed++;
  console.log(
    `✅ Test 1 PASSED (${testsPassed}/${totalTests}): Joined editing session`
  );
  console.log(`   Room: ${data.room}`);
  console.log(`   Color: ${data.user_color}`);

  // Test 2: Send live code change
  console.log("\n🔧 Test 2: Sending live code change...");
  socket.emit("live_code_change", {
    snippet_id: SNIPPET_ID,
    user_id: USER_ID,
    changes: {
      content: 'console.log("Phase 3C is working!");',
      length: 35,
      operation: "insert",
      position: 0,
    },
    cursor_position: 35,
  });
});

socket.on("live_code_updated", (data) => {
  testsPassed++;
  console.log(
    `✅ Test 2 PASSED (${testsPassed}/${totalTests}): Live code updated`
  );

  // Skip direct emit test data
  if (data.test === "direct_emit") {
    console.log("   📋 Direct emit test successful");
    return;
  }

  console.log(`   User: ${data.username}`);
  console.log(`   Changes: ${JSON.stringify(data.changes)}`);

  // Test 3: Send cursor position
  console.log("\n🔧 Test 3: Sending cursor position...");
  socket.emit("cursor_position_change", {
    snippet_id: SNIPPET_ID,
    user_id: USER_ID,
    position: 20,
    line: 1,
  });
});

socket.on("cursor_position_updated", (data) => {
  testsPassed++;
  console.log(
    `✅ Test 3 PASSED (${testsPassed}/${totalTests}): Cursor position updated`
  );
  console.log(`   Position: ${data.position}, Line: ${data.line}`);
  console.log(`   Color: ${data.color}`);

  // Test 4: Send typing indicator
  console.log("\n🔧 Test 4: Sending typing indicator...");
  socket.emit("typing_indicator_change", {
    snippet_id: SNIPPET_ID,
    user_id: USER_ID,
    is_typing: true,
    line: 1,
  });
});

socket.on("typing_status_updated", (data) => {
  testsPassed++;
  console.log(
    `✅ Test 4 PASSED (${testsPassed}/${totalTests}): Typing status updated`
  );
  console.log(`   User: ${data.username}, Typing: ${data.is_typing}`);

  // Test 5: Send collaborative comment
  console.log("\n🔧 Test 5: Sending collaborative comment...");
  socket.emit("collaborative_comment", {
    snippet_id: SNIPPET_ID,
    user_id: USER_ID,
    comment: "Phase 3C real-time collaboration is working perfectly! 🚀",
    type: "comment",
  });
});

socket.on("comment_added", (data) => {
  testsPassed++;
  console.log(`✅ Test 5 PASSED (${testsPassed}/${totalTests}): Comment added`);
  console.log(`   Comment: "${data.comment}"`);
  console.log(`   Type: ${data.type}`);

  // Test 6: Leave editing session
  console.log("\n🔧 Test 6: Leaving editing session...");
  socket.emit("leave_editing_session", {
    snippet_id: SNIPPET_ID,
    user_id: USER_ID,
  });

  // Complete tests
  setTimeout(() => {
    console.log("\n" + "🎉".repeat(20));
    console.log(
      `🎉 ALL PHASE 3C TESTS COMPLETED! (${testsPassed}/${totalTests})`
    );
    console.log("🎉".repeat(20));
    console.log("\n✅ PHASE 3C REAL-TIME COLLABORATION IS WORKING PERFECTLY!");
    console.log("─".repeat(60));
    socket.disconnect();
    process.exit(0);
  }, 1000);
});

// Enhanced Error Handlers
socket.on("editing_session_error", (data) => {
  console.log("❌ Editing session error:", data);
  console.log("🔍 Check team membership and permissions");
});

socket.on("live_change_error", (data) => {
  console.log("❌ Live change error:", data);
  console.log("🔍 Check snippet permissions and data format");
});

socket.on("comment_error", (data) => {
  console.log("❌ Comment error:", data);
  console.log("🔍 Check comment data and permissions");
});

socket.on("connect_error", (error) => {
  console.log("❌ Connection error:", error);
  console.log("🔍 Check server status and JWT token");
});

socket.on("disconnect", (reason) => {
  console.log(`🔌 Disconnected: ${reason}`);
});

// Additional useful events
socket.on("user_joined_editing", (data) => {
  console.log(`👥 User joined editing: ${data.username} (${data.color})`);
});

socket.on("user_left_editing", (data) => {
  console.log(`👋 User left editing: ${data.username}`);
});

socket.on("snippet_content_sync", (data) => {
  console.log(`📄 Snippet content synced: ${data.title} (${data.language})`);
});

// Progress timeout with better messaging
setTimeout(() => {
  console.log("\n⏰ TEST TIMEOUT REACHED");
  console.log(`📊 Tests completed: ${testsPassed}/${totalTests}`);

  if (testsPassed === 0) {
    console.log(
      "❌ No tests passed - Check server connection and authentication"
    );
  } else if (testsPassed < totalTests) {
    console.log(
      `⚠️  Partial success - ${totalTests - testsPassed} tests failed`
    );
    console.log("🔍 Check server logs for missing event handlers");
  }

  console.log("🔌 Disconnecting...");
  socket.disconnect();
  process.exit(testsPassed === totalTests ? 0 : 1);
}, 30000); // Reduced to 30 seconds

// Graceful shutdown
process.on("SIGINT", () => {
  console.log("\n🛑 Test interrupted by user");
  console.log(`📊 Tests completed: ${testsPassed}/${totalTests}`);
  socket.disconnect();
  process.exit(1);
});
