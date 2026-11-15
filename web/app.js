const token = document.querySelector('meta[name="lab-token"]').content;
const notice = document.querySelector('#notice');
const jobs = document.querySelector('#jobs');
async function request(path, body) {
  const response = await fetch(path, {method: 'POST', headers: {'Content-Type':'application/json', 'X-Lab-Token':token}, body:JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Request failed');
  return result;
}
document.querySelector('#start').addEventListener('click', async () => {
  try { await request('/api/jobs', {seconds:Number(document.querySelector('#seconds').value)}); notice.textContent='Workflow started. Watch its status below.'; await refresh(); }
  catch (error) { notice.textContent=error.message; }
});
function text(tag, content) {const node=document.createElement(tag); node.textContent=content; return node;}
let fingerprint='';
async function refresh() {
  try {
    const response = await fetch('/api/jobs');
    if (!response.ok) throw new Error('Could not read workflow status');
    const data = await response.json();
    document.querySelector('#start').disabled=data.some(j=>['starting','running','stopping'].includes(j.status));
    const next=JSON.stringify(data);
    if(next===fingerprint) return;
    fingerprint=next; jobs.replaceChildren();
    if(!data.length) jobs.append(text('p','No workflows yet.'));
    for(const job of data) {
      const card=document.createElement('article');
      card.append(text('h3',`${job.status.toUpperCase()} · ${job.seconds}s recording`),text('p',`Job ${job.id}`));
      if(job.error) card.append(text('p',job.error));
      for(const event of job.events) card.append(text('p',`${new Date(event.at).toLocaleTimeString()} — ${event.message}`));
      if(['starting','running','stopping'].includes(job.status)) {
        const stop=text('button','Stop workflow'); stop.addEventListener('click', async()=>{try{await request(`/api/jobs/${job.id}/stop`,{});await refresh();}catch(e){notice.textContent=e.message;}}); card.append(stop);
      }
      if(job.probe) {
        card.append(text('pre',JSON.stringify(job.probe,null,2)));
        const video=document.createElement('video'); video.controls=true; video.preload='metadata'; video.src=`/media/${job.id}/recording.mp4`; card.append(video);
      }
      jobs.append(card);
    }
  } catch(error) {notice.textContent=error.message;}
}
refresh(); setInterval(refresh,1500);
