/* Only local textContent is used for user-submitted content: no unsafe HTML injection. */
'use strict';
const byId = id => document.getElementById(id);
let cachedReports = [];
let networkConnected = true;

function element(tag, className, text) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined) e.textContent = String(text);
  return e;
}
function announce(message, error = false) {
  const n = byId('notice');
  n.textContent = message;
  n.className = 'notice' + (error ? ' error' : '');
}
async function call(path, options = {}) {
  const response = await fetch(path, {
    headers: {'Content-Type':'application/json'}, ...options
  });
  let data;
  try { data = await response.json(); } catch { throw Error(`HTTP ${response.status}`); }
  if (!response.ok) throw Error(data.error || `HTTP ${response.status}`);
  return data;
}
function tag(label, variant) { return element('span', 'tag ' + (variant || ''), label); }
function shortId(id) { return id.slice(0, 8); }

function reportCard(report) {
  const card = element('div', 'report' + (report.conflict ? ' conflict-card' : ''));
  if (report.conflict) {
    const top = element('div', 'tags'); top.append(tag('VERSION CONFLICT', 'conflict')); card.append(top);
    card.append(element('h3', '', 'Report ' + shortId(report.id)));
    card.append(element('p', '', 'Two or more independent edits were detected. Choose a version to resolve.'));
    const candidates = element('div', 'candidates');
    report.candidates.forEach(candidate => {
      const row = element('div', 'candidate');
      row.append(element('strong', '', candidate.data.title));
      row.append(element('p', '', `${candidate.data.status} · ${candidate.data.description || 'No description'} · Edit at ${candidate.data.campus}`));
      row.append(element('div', 'meta', `Vector: ${JSON.stringify(candidate.vector_clock)}`));
      const button = element('button', 'small-button', 'Keep this version');
      button.addEventListener('click', async () => {
        if (!confirm('Resolve conflict by keeping this candidate? All conflict histories stay recorded.')) return;
        try {
          await call('/api/items/' + encodeURIComponent(report.id) + '/resolve', {
            method:'POST', body:JSON.stringify({winning_version_id:candidate.version_id})
          });
          announce('Conflict resolved locally. Synchronize to propagate the resolution.');
          await refresh();
        } catch (e) { announce(e.message, true); }
      });
      row.append(button); candidates.append(row);
    });
    card.append(candidates);
    return card;
  }
  const head = element('div', 'report-head');
  const tags = element('div', 'tags');
  tags.append(tag(report.kind, report.kind === 'FOUND' ? 'found' : ''));
  tags.append(tag(report.status, report.status === 'RESOLVED' ? 'resolved' : ''));
  head.append(tags);
  head.append(element('span', 'meta', shortId(report.id)));
  card.append(head);
  card.append(element('h3', '', report.title));
  if (report.description) card.append(element('p', '', report.description));
  const bottom = element('div', 'report-bottom');
  bottom.append(element('span', 'meta', `${report.category} · ${report.campus}`));
  if (report.status === 'OPEN') {
    const button = element('button', 'small-button', 'Mark resolved');
    button.addEventListener('click', async () => {
      try {
        await call('/api/items/' + encodeURIComponent(report.id), {method:'PATCH', body:JSON.stringify({status:'RESOLVED'})});
        announce('Report updated locally. Synchronize to share the change.'); await refresh();
      } catch (e) { announce(e.message, true); }
    });
    bottom.append(button);
  }
  card.append(bottom);
  return card;
}
function renderReports() {
  const search = byId('search').value.toLowerCase().trim();
  const reports = cachedReports.filter(r => !search || JSON.stringify(r).toLowerCase().includes(search));
  const holder = byId('reports'); holder.replaceChildren();
  if (!reports.length) { holder.append(element('p','muted','No matching reports yet.')); return; }
  reports.forEach(r => holder.append(reportCard(r)));
}
async function refresh() {
  try {
    const [health, listing, suggestions] = await Promise.all([
      call('/api/health'), call('/api/items'), call('/api/matches')
    ]);
    networkConnected = health.connected;
    cachedReports = listing.items;
    byId('report-count').textContent = listing.items.length;
    byId('conflict-count').textContent = listing.items.filter(i => i.conflict).length;
    byId('version-count').textContent = health.versions;
    byId('peer-name').textContent = new URL(health.peer).host;
    byId('connection-label').textContent = health.connected ? 'Sync enabled' : 'Partitioned';
    byId('network-button').textContent = health.connected ? 'Simulate disconnection' : 'Restore connection';
    renderReports();
    const matchHolder = byId('matches'); matchHolder.replaceChildren();
    if (!suggestions.matches.length) matchHolder.append(element('p','muted','No suggested lost/found pairs yet.'));
    suggestions.matches.forEach(m => {
      const row = element('div','match');
      row.append(element('strong','',`${m.lost.title} ↔ ${m.found.title}`));
      row.append(element('span','',`Shared keywords: ${m.shared_keywords.join(', ')} · Human confirmation required`));
      matchHolder.append(row);
    });
  } catch (e) { announce('Could not refresh dashboard: ' + e.message, true); }
}
byId('new-form').addEventListener('submit', async e => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target));
  try {
    await call('/api/items', {method:'POST',body:JSON.stringify(data)});
    e.target.reset(); announce('Report saved in this campus database.'); await refresh();
  } catch (err) { announce(err.message, true); }
});
byId('sync-button').addEventListener('click', async () => {
  const button = byId('sync-button'); button.disabled = true;
  try {
    const result = await call('/api/sync', {method:'POST'});
    announce(`Sync succeeded. ${result.new_local_versions} new versions received; ${result.reports} reports present.`);
  } catch (e) { announce('Sync failed: ' + e.message, true); }
  finally { button.disabled = false; await refresh(); }
});
byId('network-button').addEventListener('click', async () => {
  try {
    const target = !networkConnected;
    await call('/api/admin/network', {method:'PUT',body:JSON.stringify({connected:target})});
    announce(target ? 'This campus can synchronize again.' : 'This campus is isolated: local operations still work. Disconnect the other campus as well to model a full partition.');
    await refresh();
  } catch (e) { announce(e.message, true); }
});
byId('search').addEventListener('input', renderReports);
refresh();
