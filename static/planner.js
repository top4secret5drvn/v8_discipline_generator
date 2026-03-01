async function fetchJSON(url, opts){
  const r = await fetch(url, opts);
  return r.json();
}

async function loadProjects(){
  const res = await fetchJSON('/api/planner/projects');
  if(res.status === 'success'){
    renderProjects(res.data);
  } else {
    alert('Ошибка загрузки проектов: '+(res.message||''))
  }
}

function renderProjects(list){
  const el = document.getElementById('projectsList');
  el.innerHTML = '';
  list.forEach(p=>{
    const li = document.createElement('li');
    const isTraining = p.startsWith('!');
    const displayName = isTraining ? p.slice(1) : p;
    if(isTraining) li.classList.add('training');

    const nameSpan = document.createElement('span');
    nameSpan.textContent = displayName;
    nameSpan.style.cursor = 'pointer';
    nameSpan.onclick = ()=>{ document.querySelectorAll('#projectsList li').forEach(n=>n.classList.remove('active')); li.classList.add('active'); loadProject(p); };

    const chk = document.createElement('input');
    chk.type = 'checkbox';
    chk.checked = isTraining;
    chk.title = 'Отметить как обучающий проект';
    chk.style.marginRight = '8px';
    chk.onclick = async (ev)=>{ ev.stopPropagation(); // prevent li click
      const resp = await fetch('/api/planner/toggle_training', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ project: p }) });
      const data = await resp.json();
      if(data.status === 'success'){
        // reload projects and try to preserve selection
        await loadProjects();
      } else {
        alert('Ошибка переключения проекта: '+(data.message||''));
      }
    };

    li.appendChild(chk);
    li.appendChild(nameSpan);
    el.appendChild(li);
  });
}

// Create project
document.addEventListener('click', (e)=>{
  if(e.target && e.target.id === 'createProjectBtn'){
    const name = document.getElementById('newProjectName').value.trim();
    if(!name){ alert('Введите имя папки'); return; }
    fetch('/api/planner/create_project', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name}) })
      .then(r=>r.json()).then(res=>{ if(res.status==='success'){ loadProjects(); document.getElementById('newProjectName').value=''; } else alert(res.message||'Ошибка'); })
  }
});

async function loadProject(name){
  document.getElementById('projectTitle').textContent = name;
  const res = await fetchJSON('/api/planner/project/'+encodeURIComponent(name));
  if(res.status !== 'success'){
    alert('Не удалось загрузить проект'); return;
  }
  renderRoadmap(name, res.data);
}

function renderRoadmap(project, tasks){
  const col = document.getElementById('nodesCol');
  const svg = document.getElementById('roadmapSvg');
  const progressFill = document.getElementById('progressFill');
  col.innerHTML = '';
  svg.innerHTML = '';

  // Vertical zig-zag: alternate x offset for each node
  const nodeHeight = 160;
  const offsets = [0, 160, 320, 160, 320, 0, 160, 320];

  // calculate progress
  const isTrainingProject = project.startsWith('!');
  let perc = 0;
  if(isTrainingProject){
    // each x == 1/3 of task completion
    const totalParts = tasks.length * 3 || 1;
    let gained = 0;
    tasks.forEach(t=>{
      const name = t.filename;
      const m = name.match(/(?:\s([x]+))(?:\s|\.|$)/);
      const xs = m ? (m[1] || '') : '';
      const count = Math.min(3, xs.length);
      gained += count;
    });
    perc = Math.round((gained / totalParts) * 100);
  } else {
    const total = tasks.length || 1;
    const done = tasks.filter(t=>t.completed).length;
    perc = Math.round((done/total)*100);
  }
  progressFill.style.width = perc + '%';
  const percEl = document.getElementById('progressPercent');
  if(percEl) percEl.textContent = perc + '%';

  tasks.forEach((t, i)=>{
    const container = document.createElement('div');
    container.style.display = 'flex';
    container.style.alignItems = 'flex-start';
    container.style.gap = '12px';
    container.style.marginBottom = '24px';
    
    const wrapper = document.createElement('div');
    wrapper.className = 'node' + (t.completed? ' completed':'');
    wrapper.style.flexShrink = '0';
    wrapper.style.display = 'flex';
    wrapper.style.alignItems = 'center';
    wrapper.style.justifyContent = 'center';
    
    // training style
    const isTraining = project.startsWith('!');
    if(isTraining){
      // detect x count
      const m = t.filename.match(/(?:\s([x]+))(?:\s|\.|$)/);
      const xs = m ? (m[1] || '') : '';
      const xcount = xs.length;
      if(xcount > 0 && xcount < 3){
        wrapper.classList.add('training');
        wrapper.classList.add('pending');
      } else if(xcount >= 3){
        wrapper.classList.add('training');
        wrapper.classList.add('completed');
      } else {
        wrapper.classList.add('training');
      }
    }

    wrapper.onclick = ()=>{ showDetail(project, t, wrapper); };

    // Text section for labels
    const textSection = document.createElement('div');
    textSection.style.display = 'flex';
    textSection.style.flexDirection = 'column';
    textSection.style.justifyContent = 'flex-start';
    textSection.style.paddingTop = '2px';
    
    const title = document.createElement('div');
    title.className = 'title';
    let titleText = t.filename.replace(/\.[^/.]+$/, '');
    if(t.completed){
      const m = titleText.match(/^(.*)\s(\d{4}-\d{2}-\d{2})\sвыполнено$/i);
      if(m){
        titleText = m[1] + ' (' + m[2] + ')';
      }
    }
    title.textContent = titleText;
    textSection.appendChild(title);

    container.appendChild(wrapper);
    container.appendChild(textSection);
    col.appendChild(container);
  });

  // Draw connecting dotted path with SVG lines between centers
  const nodesCol = document.getElementById('nodesCol');
  const nodes = nodesCol.querySelectorAll('.node');
  svg.innerHTML = '';
  
  if(nodes.length > 0){
    let minY = Infinity, maxY = -Infinity;
    const nodePos = [];
    
    nodes.forEach((node, i) => {
      const rect = node.getBoundingClientRect();
      const colRect = nodesCol.getBoundingClientRect();
      const relY = rect.top - colRect.top + nodesCol.scrollTop;
      const relX = rect.left - colRect.left + nodesCol.scrollLeft;
      const cy = relY + rect.height / 2;
      const cx = relX + rect.width / 2;
      
      nodePos.push({x: cx, y: cy});
      minY = Math.min(minY, cy);
      maxY = Math.max(maxY, cy);
    });
    
    const totalHeight = maxY - minY + 100;
    svg.setAttribute('height', Math.max(400, totalHeight));
    
    for(let i = 1; i < nodePos.length; i++){
      const a = nodePos[i-1];
      const b = nodePos[i];
      const line = document.createElementNS('http://www.w3.org/2000/svg','path');
      const d = `M ${a.x} ${a.y} L ${b.x} ${b.y}`;
      line.setAttribute('d', d);
      line.setAttribute('stroke', '#ddd');
      line.setAttribute('stroke-width', '3');
      line.setAttribute('fill', 'none');
      line.setAttribute('stroke-dasharray', '6,6');
      svg.appendChild(line);
    }
  }
}

function showDetail(project, task, nodeEl){
  document.querySelectorAll('.nodes-col .node').forEach(n=>n.classList.remove('active'));
  nodeEl.classList.add('active');
  document.getElementById('detailTitle').textContent = task.filename;
  document.getElementById('detailContent').textContent = task.content || '(пусто)';
  document.getElementById('detailTextarea').value = task.content || '';
  // fill deltas with zeros
  ['I','S','W','E','C','H','ST','$'].forEach(k=>{ const el = document.getElementById('d'+(k==='$'?'$':k)); if(el) el.value=''; });

  const applyBtn = document.getElementById('applyDeltasBtn');
  applyBtn.onclick = async ()=>{
    const deltas = {};
    ['I','S','W','E','C','H','ST','$'].forEach(k=>{ const el = document.getElementById('d'+(k==='$'?'$':k)); if(el && el.value) deltas[k]=parseFloat(el.value) || 0; });
    // First, mark complete/rename and apply deltas in one call
    const resp = await fetchJSON('/api/planner/complete', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ project, filename: task.filename, mark:true, deltas }) });
    if(resp.status === 'success'){
      // refresh project view
      await loadProject(project);
    } else {
      alert('Ошибка применения: '+(resp.message||''));
    }
  };

  // save content
  document.getElementById('saveContentBtn').onclick = async ()=>{
    const content = document.getElementById('detailTextarea').value;
    const resp = await fetchJSON('/api/planner/task', { method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ project, filename: task.filename, content }) });
    if(resp.status === 'success'){
      await loadProject(project);
    } else alert('Ошибка сохранения: '+(resp.message||''));
  };

  document.getElementById('deleteTaskBtn').onclick = async ()=>{
    if(!confirm('Удалить задачу?')) return;
    const resp = await fetchJSON('/api/planner/task', { method:'DELETE', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ project, filename: task.filename }) });
    if(resp.status === 'success'){
      await loadProject(project);
      document.getElementById('detailTitle').textContent = 'Детали';
      document.getElementById('detailTextarea').value = '';
      document.getElementById('detailContent').textContent = 'Выберите узел слева';
    } else alert('Ошибка удаления: '+(resp.message||''));
  };
}

// Create new task (file) in current project
async function createTaskInProject(project, filename, content){
  return fetchJSON('/api/planner/task', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ project, filename, content }) });
}

// UI: add create task button in detail panel dynamically
window.addEventListener('load', ()=>{
  const panel = document.getElementById('detailPanel');
  const wrap = document.createElement('div');
  wrap.style.marginTop = '12px';
  wrap.innerHTML = '<input id="newTaskName" placeholder="Имя файла (task.txt)" style="width:100%;box-sizing:border-box" /><textarea id="newTaskContent" placeholder="Содержимое" style="width:100%;height:80px;margin-top:6px"></textarea><div style="text-align:right;margin-top:6px"><button id="createTaskBtn">Создать файл</button></div>';
  panel.appendChild(wrap);

  document.getElementById('createTaskBtn').onclick = async ()=>{
    const proj = document.getElementById('projectTitle').textContent;
    const fname = document.getElementById('newTaskName').value.trim();
    const content = document.getElementById('newTaskContent').value || '';
    if(!proj || proj === 'Выберите проект'){ alert('Выберите проект'); return; }
    if(!fname){ alert('Введите имя файла'); return; }
    const resp = await createTaskInProject(proj, fname, content);
    if(resp.status === 'success'){
      document.getElementById('newTaskName').value=''; document.getElementById('newTaskContent').value='';
      await loadProject(proj);
    } else alert('Ошибка создания: '+(resp.message||''));
  };
});

document.getElementById('refreshProjects').addEventListener('click', loadProjects);
window.addEventListener('load', ()=>{ loadProjects(); });
