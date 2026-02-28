async function fetchJSON(url, opts){
  const r = await fetch(url, opts);
  return r.json();
}

async function ensureProject(){
  const res = await fetchJSON('/api/planner/projects');
  if(res.status==='success'){
    if(!res.data.includes('tasks')){
      await fetch('/api/planner/create_project',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({name:'tasks'})
      });
    }
  }
}

async function loadTasks(){
  const res = await fetchJSON('/api/planner/project/tasks');
  if(res.status==='success'){
    renderTasks(res.data);
  } else {
    alert('Не удалось загрузить задачи');
  }
}

function renderTasks(tasks){
  const ul = document.getElementById('tasksList');
  ul.innerHTML = '';
  tasks.forEach(t=>{
    const li = document.createElement('li');
    const nameSpan = document.createElement('span');
    nameSpan.className='name';
    nameSpan.textContent = t.filename.replace(/\.[^/.]+$/,'');
    if(t.completed) li.classList.add('completed');
    nameSpan.onclick = ()=>{ selectTask(t); };
    li.appendChild(nameSpan);
    const delBtn = document.createElement('button');
    delBtn.textContent='🗑️';
    delBtn.onclick = (e)=>{ e.stopPropagation(); deleteTask(t); };
    li.appendChild(delBtn);
    ul.appendChild(li);
  });
}

let currentTask = null;

function selectTask(task){
  currentTask = task;
  document.getElementById('taskDetail').style.display='block';
  document.getElementById('detailName').textContent = task.filename.replace(/\.[^/.]+$/,'');
  document.getElementById('detailContent').value = task.content || '';
  ['I','S','W','E','C','H','ST','$'].forEach(k=>{ const el=document.getElementById('d'+(k==='$'?'$':k)); if(el) el.value=''; });
}

async function deleteTask(task){
  if(!confirm('Удалить задачу?')) return;
  const resp = await fetchJSON('/api/planner/task', { method:'DELETE', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ project:'tasks', filename: task.filename }) });
  if(resp.status==='success'){
    await loadTasks();
    document.getElementById('taskDetail').style.display='none';
  } else alert('Ошибка удаления');
}

async function saveDetail(){
  if(!currentTask) return;
  const content = document.getElementById('detailContent').value;
  const resp = await fetchJSON('/api/planner/task',{ method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ project:'tasks', filename: currentTask.filename, content }) });
  if(resp.status==='success'){
    await loadTasks();
  } else alert('Ошибка сохранения');
}

async function markDone(){
  if(!currentTask) return;
  const deltas = {};
  ['I','S','W','E','C','H','ST','$'].forEach(k=>{ const el=document.getElementById('d'+(k==='$'?'$':k)); if(el && el.value) deltas[k]=parseFloat(el.value)||0; });
  const resp = await fetchJSON('/api/planner/complete', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ project:'tasks', filename:currentTask.filename, mark:true, deltas }) });
  if(resp.status==='success'){
    await loadTasks();
    document.getElementById('taskDetail').style.display='none';
  } else alert('Ошибка отметки');
}

// create new task
async function addTask(){
  const name = document.getElementById('newTaskName').value.trim();
  if(!name) return alert('Введите название');
  const resp = await fetchJSON('/api/planner/task', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ project:'tasks', filename: name + '.txt', content: '' }) });
  if(resp.status==='success'){
    document.getElementById('newTaskName').value='';
    await loadTasks();
  } else alert('Ошибка создания: '+(resp.message||''));
}

window.addEventListener('load', async ()=>{
  await ensureProject();
  loadTasks();
  document.getElementById('addTaskBtn').onclick = addTask;
  document.getElementById('saveDetailBtn').onclick = saveDetail;
  document.getElementById('deleteBtn').onclick = ()=>{ if(currentTask) deleteTask(currentTask); };
  document.getElementById('markDoneBtn').onclick = markDone;
});
