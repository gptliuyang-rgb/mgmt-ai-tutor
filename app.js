// TODO：部署完后端后，把这里换成你的真实 API 地址
const API_URL = "https://mgmt-ai-tutor.onrender.com";

const chatWindow = document.getElementById("chatWindow");
const notesContent = document.getElementById("notesContent");
const chatForm = document.getElementById("chatForm");
const userInput = document.getElementById("userInput");
const startLessonBtn = document.getElementById("startLessonBtn");
const caseText = document.getElementById("caseText");

let conversation = [];

// 工具：往窗口里追加一条消息
function appendMessage(role, text, options = {}) {
  const wrapper = document.createElement("div");
  wrapper.className = `message message-${role}`;
  if (options.loading) {
    wrapper.classList.add("loading");
  }

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  bubble.textContent = text;

  wrapper.appendChild(bubble);
  chatWindow.appendChild(wrapper);
  chatWindow.scrollTop = chatWindow.scrollHeight;

  return wrapper;
}

// 读取当前 UI 上的设置
function getTeachingConfig() {
  const modeRadio = document.querySelector('input[name="mode"]:checked');
  const mode = modeRadio ? modeRadio.value : "case";
  const courseType = document.getElementById("courseType").value;
  const level = document.getElementById("level").value;
  const caseContent = caseText.value.trim();

  return { mode, courseType, level, caseContent };
}

// 调用后端 AI 接口
async function callTeachingAI() {
  const { mode, courseType, level, caseContent } = getTeachingConfig();

  const loadingElem = appendMessage(
    "assistant",
    "正在思考教学步骤，请稍候……",
    { loading: true }
  );

  const payload = {
    conversation,
    mode,
    courseType,
    level,
    caseContent,
  };

  try {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

    const data = await res.json();
    const reply = data.reply || "（未收到有效回复）";

    loadingElem.classList.remove("loading");
    loadingElem.querySelector(".message-bubble").textContent = reply;

    // 把 AI 回复加入对话上下文
    conversation.push({ role: "assistant", content: reply });

    // 如果后端有返回课堂小结，则更新右侧笔记
    if (data.notes) {
      notesContent.textContent = data.notes;
    }
  } catch (err) {
    console.error(err);
    loadingElem.classList.remove("loading");
    loadingElem.querySelector(".message-bubble").textContent =
      "调用 AI 接口失败，请稍后重试或检查服务器配置。";
  }
}

// 发送用户消息（通用）
function sendUserMessage(text) {
  if (!text) return;
  appendMessage("user", text);
  conversation.push({ role: "user", content: text });
  userInput.value = "";
  callTeachingAI();
}

// 聊天表单提交
chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = userInput.value.trim();
  sendUserMessage(text);
});

// “基于该案例开始教学”按钮
startLessonBtn.addEventListener("click", () => {
  const caseContent = caseText.value.trim();
  if (!caseContent) {
    alert("请先粘贴或输入一个企业管理/工商管理案例。");
    return;
  }

  // 重置对话（新的一节课）
  conversation = [];
  chatWindow.innerHTML = "";

  const introPrompt =
    "请围绕我提供的案例，像大学管理学老师一样，用结构化的方式上完整一节课。先简要复述案例，再提出引导性问题，然后讲授相关理论并应用到案例中，最后给出小结和思考题。";
  sendUserMessage(introPrompt);
});
