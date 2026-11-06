let currentUser = null;
let activeCourseCode = null;
let activeSessionId = null;
let currentAuthMode = 'login';
let currentSemesterView = 1;

document.addEventListener("DOMContentLoaded", async () => {
  const token = localStorage.getItem("token");
  if (token) {
    try {
      const res = await fetch("/api/auth/me", {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        currentUser = await res.json();
        showDashboard();
        return;
      }
    } catch (e) {
      console.error(e);
    }
  }
  showAuthView();
});

// --- Auth Handling ---
function switchAuthTab(mode) {
  currentAuthMode = mode;
  const isLogin = mode === 'login';
  document.getElementById("tabLogin").className = isLogin 
    ? "flex-1 pb-3 text-center font-medium border-b-2 border-indigo-500 text-indigo-400" 
    : "flex-1 pb-3 text-center font-medium border-b-2 border-transparent text-slate-400";
  document.getElementById("tabSignup").className = !isLogin 
    ? "flex-1 pb-3 text-center font-medium border-b-2 border-indigo-500 text-indigo-400" 
    : "flex-1 pb-3 text-center font-medium border-b-2 border-transparent text-slate-400";

  document.getElementById("fullNameGroup").classList.toggle("hidden", isLogin);
  document.getElementById("roleGroup").classList.toggle("hidden", isLogin);
  document.getElementById("authSubmitBtn").innerText = isLogin ? "Sign In" : "Create Account";
  document.getElementById("authError").classList.add("hidden");
}

async function handleAuth(e) {
  e.preventDefault();
  const errorEl = document.getElementById("authError");
  errorEl.classList.add("hidden");

  const email = document.getElementById("authEmail").value;
  const password = document.getElementById("authPassword").value;

  try {
    if (currentAuthMode === 'signup') {
      const full_name = document.getElementById("authFullName").value;
      const role = document.getElementById("authRole").value;

      const res = await fetch("/api/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, full_name, password, role })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Sign up failed");
      }
      switchAuthTab('login');
      alert("Account created successfully! Please sign in.");
      return;
    }

    const formData = new URLSearchParams();
    formData.append("username", email);
    formData.append("password", password);

    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: formData
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Invalid login credentials");
    }

    const data = await res.json();
    localStorage.setItem("token", data.access_token);

    const userRes = await fetch("/api/auth/me", {
      headers: { Authorization: `Bearer ${data.access_token}` }
    });
    currentUser = await userRes.json();
    showDashboard();

  } catch (err) {
    errorEl.innerText = err.message;
    errorEl.classList.remove("hidden");
  }
}

function logout() {
  localStorage.removeItem("token");
  currentUser = null;
  activeCourseCode = null;
  activeSessionId = null;
  showAuthView();
}

function showAuthView() {
  document.getElementById("authView").classList.remove("hidden");
  document.getElementById("dashboardView").classList.add("hidden");
  document.getElementById("adminView").classList.add("hidden");
  document.getElementById("chatView").classList.add("hidden");
  document.getElementById("navUserSection").classList.add("hidden");
}

function showDashboard() {
  document.getElementById("authView").classList.add("hidden");
  document.getElementById("dashboardView").classList.remove("hidden");
  document.getElementById("adminView").classList.add("hidden");
  document.getElementById("chatView").classList.add("hidden");

  const navSection = document.getElementById("navUserSection");
  navSection.classList.remove("hidden");
  navSection.classList.add("flex");
  document.getElementById("navUserInfo").innerText = currentUser.full_name;
  
  const badge = document.getElementById("navRoleBadge");
  badge.innerText = currentUser.role;
  badge.className = `text-xs uppercase px-2.5 py-0.5 rounded-full font-semibold ${
    currentUser.role === 'admin' ? 'bg-rose-500/20 text-rose-300' :
    currentUser.role === 'faculty' ? 'bg-amber-500/20 text-amber-300' : 'bg-emerald-500/20 text-emerald-300'
  }`;

  document.getElementById("adminPanelNavBtn").classList.toggle("hidden", currentUser.role !== 'admin');

  filterSemester(currentSemesterView);
}

// --- Semester Switching & Sorting ---
async function filterSemester(sem) {
  currentSemesterView = sem;
  [1, 2, 3, 4].forEach(s => {
    const btn = document.getElementById(`semBtn-${s}`);
    if (btn) {
      btn.className = (s === sem)
        ? "px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 text-white"
        : "px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-slate-700 text-slate-300 hover:bg-slate-600";
    }
  });

  await fetchAndRenderCourses();
}

async function fetchAndRenderCourses() {
  const res = await fetch(`/api/courses/all?semester=${currentSemesterView}`);
  const courses = await res.json();

  const grid = document.getElementById("coursesGrid");
  grid.innerHTML = "";

  if (courses.length === 0) {
    grid.innerHTML = `<div class="col-span-full p-8 text-center text-slate-400 bg-slate-800/40 rounded-xl border border-slate-700/60">No subjects currently configured for Semester ${currentSemesterView}.</div>`;
    return;
  }

  courses.forEach(c => {
    const card = document.createElement("div");
    card.className = "bg-slate-800 border border-slate-700 hover:border-slate-600 p-5 rounded-xl flex flex-col justify-between";
    card.innerHTML = `
      <div>
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs font-bold uppercase tracking-wider text-indigo-400 bg-indigo-950/60 border border-indigo-800 px-2 py-0.5 rounded">${c.code}</span>
          <span class="text-[11px] text-slate-400 font-medium">Semester ${c.semester}</span>
        </div>
        <h3 class="font-semibold text-slate-100 text-base mb-1">${c.title}</h3>
      </div>
      <div class="mt-6 pt-4 border-t border-slate-700/60 flex items-center justify-between gap-2">
        <button onclick="openChatWorkspace('${c.code}', '${c.title}')" class="text-xs bg-indigo-600 hover:bg-indigo-500 font-medium px-3.5 py-1.5 rounded transition flex items-center space-x-1.5">
          <i class="fa-regular fa-comments"></i> <span>Open Subject</span>
        </button>
        ${(currentUser.role === 'faculty' || currentUser.role === 'admin') ? `
          <button onclick="openUploadModal('${c.code}')" class="text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 font-medium px-3 py-1.5 rounded transition flex items-center space-x-1">
            <i class="fa-solid fa-arrow-up-from-bracket"></i> <span>Add Material</span>
          </button>
        ` : ''}
      </div>
    `;
    grid.appendChild(card);
  });
}

// --- Admin Console Operations ---
async function openAdminPanel() {
  document.getElementById("dashboardView").classList.add("hidden");
  document.getElementById("chatView").classList.add("hidden");
  document.getElementById("adminView").classList.remove("hidden");

  await loadAdminSubjects();
  await loadAdminFaculty();
}

async function loadAdminSubjects() {
  const res = await fetch("/api/courses/all");
  const courses = await res.json();
  const tbody = document.getElementById("adminSubjectsTable");
  tbody.innerHTML = "";

  courses.forEach(c => {
    const tr = document.createElement("tr");
    tr.className = "hover:bg-slate-700/30";
    tr.innerHTML = `
      <td class="p-2.5 font-mono text-indigo-400 font-semibold">${c.code}</td>
      <td class="p-2.5 font-medium text-slate-200">${c.title}</td>
      <td class="p-2.5"><span class="bg-slate-700 px-2 py-0.5 rounded text-[11px]">Sem ${c.semester}</span></td>
      <td class="p-2.5 text-right space-x-2">
        <button onclick="openUploadModal('${c.code}')" title="Upload Material" class="text-indigo-400 hover:text-indigo-300 p-1">
          <i class="fa-solid fa-upload"></i>
        </button>
        <button onclick="openEditSubjectModal('${c.code}', '${c.title}', ${c.semester})" title="Edit Subject" class="text-amber-400 hover:text-amber-300 p-1">
          <i class="fa-solid fa-pen-to-square"></i>
        </button>
        <button onclick="deleteSubject('${c.code}')" title="Delete Subject" class="text-rose-400 hover:text-rose-300 p-1">
          <i class="fa-solid fa-trash"></i>
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

async function loadAdminFaculty() {
  const token = localStorage.getItem("token");
  const res = await fetch("/api/courses/faculty-details", {
    headers: { Authorization: `Bearer ${token}` }
  });
  const faculty = await res.json();
  const list = document.getElementById("adminFacultyList");
  list.innerHTML = "";

  if (faculty.length === 0) {
    list.innerHTML = `<span class="text-xs text-slate-500">No faculty registered yet.</span>`;
    return;
  }

  faculty.forEach(f => {
    const card = document.createElement("div");
    card.className = "p-3 bg-slate-900/60 rounded-lg border border-slate-700/60 text-xs";
    card.innerHTML = `
      <div class="flex items-center justify-between">
        <strong class="text-slate-200">${f.full_name}</strong>
        <span class="text-[10px] uppercase font-bold text-amber-400 bg-amber-950/60 border border-amber-800 px-1.5 py-0.2 rounded">${f.role}</span>
      </div>
      <p class="text-slate-400 mt-0.5">${f.email}</p>
      <div class="mt-2 text-[11px] text-indigo-400 flex justify-between">
        <span>Uploaded Files: ${f.uploaded_docs_count}</span>
        <span class="text-slate-400">Joined: ${new Date(f.created_at).toLocaleDateString()}</span>
      </div>
    `;
    list.appendChild(card);
  });
}

async function submitAddSubject() {
  const code = document.getElementById("newSubjectCode").value.trim().toUpperCase();
  const title = document.getElementById("newSubjectTitle").value.trim();
  const semester = parseInt(document.getElementById("newSubjectSem").value, 10);
  if (!code || !title) return alert("Code and title are required.");

  const token = localStorage.getItem("token");
  const res = await fetch("/api/courses/", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ code, title, semester })
  });

  if (res.ok) {
    toggleModal('addSubjectModal', false);
    document.getElementById("newSubjectCode").value = "";
    document.getElementById("newSubjectTitle").value = "";
    await loadAdminSubjects();
  } else {
    const err = await res.json();
    alert(err.detail || "Failed to add subject");
  }
}

function openEditSubjectModal(code, title, semester) {
  document.getElementById("editSubjectCode").value = code;
  document.getElementById("editSubjectTitle").value = title;
  document.getElementById("editSubjectSem").value = semester;
  toggleModal('editSubjectModal', true);
}

async function submitEditSubject() {
  const code = document.getElementById("editSubjectCode").value;
  const title = document.getElementById("editSubjectTitle").value.trim();
  const semester = parseInt(document.getElementById("editSubjectSem").value, 10);
  const token = localStorage.getItem("token");

  const res = await fetch(`/api/courses/${code}`, {
    method: "PUT",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ title, semester })
  });

  if (res.ok) {
    toggleModal('editSubjectModal', false);
    await loadAdminSubjects();
  } else {
    const err = await res.json();
    alert(err.detail || "Update failed");
  }
}

async function deleteSubject(code) {
  if (!confirm(`Are you sure you want to delete ${code}? This will remove all associated notes, chunks, and sessions.`)) return;

  const token = localStorage.getItem("token");
  const res = await fetch(`/api/courses/${code}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` }
  });

  if (res.ok) {
    await loadAdminSubjects();
  } else {
    const err = await res.json();
    alert(err.detail || "Delete failed");
  }
}

// --- Upload Material Modal ---
function openUploadModal(courseCode) {
  document.getElementById("uploadCourseCode").value = courseCode;
  toggleModal('uploadModal', true);
}

async function submitUpload() {
  const fileInput = document.getElementById("uploadFileInput");
  if (!fileInput.files[0]) return alert("Please select a PDF file.");

  const course_code = document.getElementById("uploadCourseCode").value;
  const doc_type = document.getElementById("uploadDocType").value;
  const token = localStorage.getItem("token");

  const formData = new FormData();
  formData.append("course_code", course_code);
  formData.append("doc_type", doc_type);
  formData.append("file", fileInput.files[0]);

  const progress = document.getElementById("uploadProgress");
  const submitBtn = document.getElementById("uploadSubmitBtn");
  progress.classList.remove("hidden");
  submitBtn.disabled = true;

  try {
    const res = await fetch("/api/notes/upload", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: formData
    });
    const result = await res.json();
    if (!res.ok) throw new Error(result.detail || "Upload failed");
    alert(`Success! Indexed ${result.data.total_chunks} chunks into ${course_code}.`);
    toggleModal('uploadModal', false);
    fileInput.value = "";
    if (activeCourseCode) loadCourseDocuments(activeCourseCode);
  } catch (err) {
    alert(err.message);
  } finally {
    progress.classList.add("hidden");
    submitBtn.disabled = false;
  }
}

// --- Subject Workspace & Materials ---
function backToDashboard() {
  activeCourseCode = null;
  activeSessionId = null;
  showDashboard();
}

async function openChatWorkspace(courseCode, courseTitle) {
  activeCourseCode = courseCode;
  activeSessionId = null;
  document.getElementById("dashboardView").classList.add("hidden");
  document.getElementById("adminView").classList.add("hidden");
  document.getElementById("chatView").classList.remove("hidden");
  document.getElementById("activeCourseTitle").innerText = `${courseCode} - ${courseTitle}`;

  loadCourseDocuments(courseCode);
  await loadUserSessions(courseCode);
  clearChatStream();
}

async function loadCourseDocuments(courseCode) {
  const token = localStorage.getItem("token");
  const listEl = document.getElementById("courseDocsList");
  const badge = document.getElementById("docCountBadge");
  listEl.innerHTML = `<span class="text-slate-500">Loading files...</span>`;

  try {
    const res = await fetch(`/api/notes/course/${courseCode}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    const docs = await res.json();
    badge.innerText = `${docs.length} files`;
    listEl.innerHTML = "";
    if (docs.length === 0) {
      listEl.innerHTML = `<span class="text-slate-500">No materials uploaded yet.</span>`;
      return;
    }
    docs.forEach(d => {
      const item = document.createElement("div");
      item.className = "flex items-center justify-between text-slate-300 py-1.5 px-2 bg-slate-800/80 rounded border border-slate-700/50";
      item.innerHTML = `
        <div class="truncate max-w-[140px]" title="${d.filename}">
          <p class="truncate font-medium">${d.filename}</p>
          <span class="text-[9px] uppercase tracking-wider text-indigo-400">${d.doc_type}</span>
        </div>
        <div class="flex items-center space-x-1.5">
          <button onclick="viewDocument('${d.id}')" title="View in browser" class="text-indigo-400 hover:text-indigo-300 p-1">
            <i class="fa-regular fa-eye"></i>
          </button>
          <button onclick="downloadDocument('${d.id}')" title="Download PDF" class="text-slate-400 hover:text-slate-200 p-1">
            <i class="fa-solid fa-download"></i>
          </button>
        </div>
      `;
      listEl.appendChild(item);
    });
  } catch (e) {
    listEl.innerHTML = `<span class="text-rose-400">Failed to load materials.</span>`;
  }
}

async function viewDocument(docId) {
  const token = localStorage.getItem("token");
  const res = await fetch(`/api/notes/view/${docId}`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (res.ok) {
    const blob = await res.blob();
    const blobUrl = URL.createObjectURL(blob);
    window.open(blobUrl, "_blank");
  } else {
    alert("Could not load preview.");
  }
}

async function downloadDocument(docId) {
  const token = localStorage.getItem("token");
  const res = await fetch(`/api/notes/download/${docId}`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (res.ok) {
    const blob = await res.blob();
    const disposition = res.headers.get("content-disposition");
    let filename = "material.pdf";
    if (disposition && disposition.indexOf("filename=") !== -1) {
      filename = disposition.split("filename=")[1].replace(/["']/g, "");
    }
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } else {
    alert("Could not download file.");
  }
}

// --- Chat Operations ---
async function loadUserSessions(courseCode) {
  const token = localStorage.getItem("token");
  const listEl = document.getElementById("sessionsList");
  listEl.innerHTML = "";

  const res = await fetch(`/api/chat/sessions/${courseCode}`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  const sessions = await res.json();

  sessions.forEach(s => {
    const btn = document.createElement("button");
    btn.className = `w-full text-left px-2.5 py-2 rounded text-xs truncate transition ${
      s.id === activeSessionId ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/40' : 'text-slate-300 hover:bg-slate-700/50'
    }`;
    btn.innerText = s.title;
    btn.onclick = () => selectSession(s.id);
    listEl.appendChild(btn);
  });
}

function startNewSession() {
  activeSessionId = null;
  clearChatStream();
  loadUserSessions(activeCourseCode);
}

async function selectSession(sessionId) {
  activeSessionId = sessionId;
  await loadUserSessions(activeCourseCode);

  const token = localStorage.getItem("token");
  const res = await fetch(`/api/chat/history/${sessionId}`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  const data = await res.json();

  const container = document.getElementById("messagesContainer");
  container.innerHTML = "";
  data.messages.forEach(msg => appendMessage(msg.role, msg.content, msg.sources));
  container.scrollTop = container.scrollHeight;
}

function clearChatStream() {
  document.getElementById("messagesContainer").innerHTML = `
    <div class="p-4 rounded-lg bg-slate-900/60 border border-slate-700/60 text-sm text-slate-300">
      Workspace active for <strong>${activeCourseCode}</strong>. Ask any question about course materials or formulate sample exam papers.
    </div>
  `;
}

async function sendChatMessage(e) {
  e.preventDefault();
  const input = document.getElementById("chatInput");
  const query = input.value.trim();
  if (!query) return;

  const mode = document.querySelector('input[name="chatMode"]:checked').value;
  input.value = "";

  appendMessage("user", query);
  const container = document.getElementById("messagesContainer");
  container.scrollTop = container.scrollHeight;

  const thinkingId = "thinking-" + Date.now();
  const thinkingEl = document.createElement("div");
  thinkingEl.id = thinkingId;
  thinkingEl.className = "flex items-center space-x-2 text-xs text-indigo-400 p-3 bg-slate-900/40 rounded-lg";
  thinkingEl.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i><span>Retrieving vector chunks and generating response...</span>`;
  container.appendChild(thinkingEl);
  container.scrollTop = container.scrollHeight;

  const token = localStorage.getItem("token");

  try {
    const res = await fetch("/api/chat/query", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        course_code: activeCourseCode,
        session_id: activeSessionId,
        query: query,
        mode: mode
      })
    });

    const data = await res.json();
    document.getElementById(thinkingId).remove();

    if (!res.ok) throw new Error(data.detail || "Query failed");

    if (!activeSessionId) {
      activeSessionId = data.session_id;
      loadUserSessions(activeCourseCode);
    }

    appendMessage("assistant", data.answer, data.sources);
    container.scrollTop = container.scrollHeight;

  } catch (err) {
    document.getElementById(thinkingId).remove();
    appendMessage("assistant", `⚠️ **Error:** ${err.message}`);
    container.scrollTop = container.scrollHeight;
  }
}

function appendMessage(role, content, sources = []) {
  const container = document.getElementById("messagesContainer");
  const msgWrapper = document.createElement("div");
  msgWrapper.className = `flex flex-col ${role === 'user' ? 'items-end' : 'items-start'}`;

  const bubble = document.createElement("div");
  bubble.className = `max-w-2xl px-4 py-3 rounded-xl text-sm leading-relaxed ${
    role === 'user' 
      ? 'bg-indigo-600 text-white rounded-br-none' 
      : 'bg-slate-900/90 text-slate-200 border border-slate-700 rounded-bl-none'
  }`;

  bubble.innerHTML = marked.parse(content);
  msgWrapper.appendChild(bubble);

  if (role === 'assistant' && sources && sources.length > 0) {
    const sourcesDetails = document.createElement("details");
    sourcesDetails.className = "mt-2 text-xs text-slate-400 max-w-2xl bg-slate-900/40 border border-slate-800 rounded p-2";
    
    let sourcesList = `<summary class="cursor-pointer font-medium text-indigo-400 hover:underline">Referenced Citations (${sources.length})</summary><ul class="mt-2 space-y-1">`;
    sources.forEach(s => {
      sourcesList += `
        <li class="flex items-center justify-between text-[11px] bg-slate-800/80 px-2 py-1 rounded">
          <span>📄 <strong>${s.filename}</strong> (Page ${s.page_number})</span>
          <span class="text-slate-400 uppercase font-mono">${s.doc_type}</span>
        </li>
      `;
    });
    sourcesList += `</ul>`;
    sourcesDetails.innerHTML = sourcesList;
    msgWrapper.appendChild(sourcesDetails);
  }

  container.appendChild(msgWrapper);
}

function toggleModal(modalId, show) {
  const el = document.getElementById(modalId);
  if (show) {
    el.classList.remove("hidden");
    el.classList.add("flex");
  } else {
    el.classList.add("hidden");
    el.classList.remove("flex");
  }
}